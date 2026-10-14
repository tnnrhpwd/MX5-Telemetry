"""BLE (GATT) server for the MX5 link: the transport that needs no SDP.

Why this exists alongside bt_spp_server.py:

* GATT has no SDP. SPP's weak point is publishing a service record, which BlueZ moved out
  of `sdptool` and into D-Bus, so the SPP path depends on deprecated tooling. BLE cannot
  fail that way.
* Android exposes GATT as first-class API, so the client side is ordinary code.

The cost is throughput. GATT replies have to be chunked to the negotiated MTU, and a
telemetry snapshot is roughly a kilobyte, so one poll becomes several notifications. That
is fine at 4 Hz but it is why SPP is tried first and BLE is the second choice.

Uses `bless` (pip install bless), which wraps the BlueZ D-Bus GATT API. Python has no
stdlib BLE peripheral support, and hand-rolling the D-Bus GATT object tree is a lot of
untestable code for no gain. If bless is not installed this module imports fine and says
so, rather than taking the whole link down with it.

The RX characteristic receives request lines; TX notifies reply lines. The framing is the
same newline-delimited protocol as every other transport, so a reply split across several
notifications is reassembled by the client's own line buffer.
"""

import asyncio
import logging
import threading

logger = logging.getLogger(__name__)

# Fixed UUIDs so the Android side can hardcode them. This is a private service, not a
# registered Bluetooth SIG one, so the base is arbitrary but must match the client.
SERVICE_UUID = '6d783500-0001-4d58-3535-4d583554454c'
RX_UUID = '6d783500-0002-4d58-3535-4d583554454c'
TX_UUID = '6d783500-0003-4d58-3535-4d583554454c'

# Notification payload size. The real limit is the negotiated MTU (often 185-517 bytes);
# this stays under the common floor. Larger means fewer notifications but risks dropping
# writes on a peer that negotiated a smaller MTU.
CHUNK_BYTES = 180

try:
    from bless import (BlessServer, GATTAttributePermissions,
                       GATTCharacteristicProperties)
    BLESS_AVAILABLE = True
    BLESS_IMPORT_ERROR = None
except Exception as e:                                  # pragma: no cover - env dependent
    BLESS_AVAILABLE = False
    BLESS_IMPORT_ERROR = e


class BleServer:
    """Serves the line protocol over a GATT characteristic pair.

    Shaped like SppServer (start/stop/describe) so bt_link.py can treat them the same.
    """

    def __init__(self, service, token=None, require_token=True, name='MX5 Pi Link',
                 chunk_bytes=CHUNK_BYTES):
        self.service = service
        self.token = token
        self.require_token = require_token
        self.name = name
        self.chunk_bytes = chunk_bytes

        # One session for the peripheral. A BLE central disconnecting is not always
        # signalled, so the session is reset when a new central connects (see _on_connect).
        from link_protocol import StreamLink
        self.link = StreamLink(service, token, require_token, label='ble')

        self._server = None
        self._thread = None
        self._loop = None
        self._stop = threading.Event()
        # Registration is asynchronous, so start() waits on this before reporting success.
        self._ready = threading.Event()
        self._start_error = None
        self._notifications = 0
        self._writes = 0

    # -- diagnostics ---------------------------------------------------------

    def describe(self):
        return {
            'transport': 'ble',
            'service_uuid': SERVICE_UUID,
            'chunk_bytes': self.chunk_bytes,
            'bless': BLESS_AVAILABLE,
            'bless_error': None if BLESS_AVAILABLE else str(BLESS_IMPORT_ERROR),
            'writes': self._writes,
            'notifications': self._notifications,
        }

    # -- lifecycle -----------------------------------------------------------

    def start(self, timeout=10):
        """Start the peripheral and wait until it is really advertising.

        Waiting matters. Registering the advertisement is asynchronous, so a start() that
        only spawns the thread reports success for a transport that can still fail a
        moment later. That has been observed: with a previous instance's advertisement not
        yet released, BlueZ refused the registration and the app printed a confident
        "Bluetooth link started" for a link that was already dead. Raising here instead
        lets bt_link.py record the reason and the banner tell the truth.
        """
        if not BLESS_AVAILABLE:
            raise RuntimeError(
                'The BLE transport needs the `bless` package (pip install bless). '
                'Import failed with: %s' % BLESS_IMPORT_ERROR)
        if self._thread is not None:
            return

        self._stop.clear()
        self._ready.clear()
        self._start_error = None
        self._thread = threading.Thread(target=self._run, name='ble-link', daemon=True)
        self._thread.start()

        if not self._ready.wait(timeout):
            raise RuntimeError(
                'The BLE transport did not finish registering within %ss' % timeout)
        if self._start_error is not None:
            raise self._start_error

    def stop(self):
        self._stop.set()
        self._ready.set()  # release any start() still waiting
        if self._loop is not None:
            try:
                asyncio.run_coroutine_threadsafe(self._shutdown(), self._loop).result(3)
            except Exception as e:
                logger.debug("BLE shutdown: %s", e)
        if self._thread is not None:
            self._thread.join(timeout=3)
            self._thread = None

    def _run(self):
        """Own an event loop for the peripheral's lifetime."""
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._main())
        except Exception as e:
            # Only a failure before _ready is a *startup* failure; the same except also
            # catches a transport that dies long after boot, which start() must not report.
            if not self._ready.is_set():
                self._start_error = e
            logger.exception("BLE link stopped")
        finally:
            self._ready.set()
            try:
                loop.close()
            except Exception:
                pass
            self._loop = None

    async def _main(self):
        self._server = BlessServer(name=self.name, loop=self._loop)
        self._server.write_request_func = self._on_write
        self._server.read_request_func = self._on_read

        await self._server.add_new_service(SERVICE_UUID)

        # RX: the central writes request lines here.
        await self._server.add_new_characteristic(
            SERVICE_UUID, RX_UUID, GATTCharacteristicProperties.write, None,
            GATTAttributePermissions.writeable)

        # TX: we notify reply lines from here. Readable as well, so a central can poll
        # instead if it does not want notifications.
        await self._server.add_new_characteristic(
            SERVICE_UUID, TX_UUID, GATTCharacteristicProperties.notify, b'',
            GATTAttributePermissions.readable | GATTAttributePermissions.writeable)

        await self._server.start()
        logger.info("BLE link advertising as %r (service %s)", self.name, SERVICE_UUID)

        # Past this line the advertisement is registered, so start() may report success.
        self._ready.set()

        # Idle until stopped; bless runs the D-Bus work on its own tasks.
        while not self._stop.is_set():
            await asyncio.sleep(0.5)

    async def _shutdown(self):
        if self._server is not None:
            await self._server.stop()

    # -- GATT callbacks ------------------------------------------------------

    def _on_read(self, characteristic, **kwargs):
        """A central read the characteristic directly.

        Synchronous on purpose: bless does ``return self.read_request_func(characteristic)``
        and does not await it, so an async handler hands the D-Bus layer a coroutine
        object instead of bytes.
        """
        return characteristic.value

    def _on_write(self, characteristic, value=None, **kwargs):
        """A central wrote bytes: feed them to the protocol and schedule the replies.

        Two things about bless's contract are easy to get wrong, and both fail silently
        rather than loudly:

        * It calls ``write_request_func(characteristic, value)`` - two positional
          arguments. Accepting only the characteristic raised TypeError inside BlueZ's
          WriteValue handler, which the central sees as an opaque ATT "Unlikely Error"
          (0x0E) that names nothing about the cause.
        * It calls that function without awaiting it. An ``async def`` handler therefore
          returned a coroutine nobody ran: the write was accepted and did nothing.

        The value argument is authoritative. The BlueZ backend passes the payload as an
        argument rather than storing it, so characteristic.value can hold the previous
        write.
        """
        if value is None:
            # Other backends (and direct calls) do set the attribute instead.
            try:
                value = characteristic.value
            except Exception:
                return

        if value is None:
            return

        self._writes += 1
        value = value.encode('utf-8') if isinstance(value, str) else bytes(value)

        out = self.link.on_bytes(value)
        if out:
            self._notify_soon(out)

        if self.link.closed:
            logger.warning("BLE link closed: %s", self.link.closed_reason)
            # A new central must authenticate again, since we cannot always tell when
            # one goes away.
            self.link.reset()

    def _notify_soon(self, payload):
        """Schedule a reply on the server's own loop.

        The write callback is synchronous, so the notification has to be handed to the
        loop rather than awaited here. run_coroutine_threadsafe is used rather than
        ensure_future so this stays correct if a future bless version dispatches the
        callback from another thread.
        """
        if self._loop is None:
            logger.warning("BLE reply dropped: no event loop")
            return
        try:
            asyncio.run_coroutine_threadsafe(self._notify(payload), self._loop)
        except Exception as e:
            logger.warning("BLE reply could not be scheduled: %s", e)

    async def _notify(self, payload):
        """Send a reply, chunked to fit the MTU. Order is preserved, so the central can
        reassemble by accumulating until it sees a newline.

        get_characteristic is synchronous in bless. Awaiting it raised TypeError, and a
        bare except logged that at debug level, so every reply was dropped in silence
        while the write that prompted it succeeded: the client saw a server that accepted
        requests and never answered.
        """
        try:
            tx = self._server.get_characteristic(TX_UUID)
        except Exception as e:
            logger.warning("BLE reply dropped: get_characteristic failed: %s", e)
            return
        if tx is None:
            logger.warning("BLE reply dropped: no characteristic %s", TX_UUID)
            return

        for i in range(0, len(payload), self.chunk_bytes):
            tx.value = payload[i:i + self.chunk_bytes]
            try:
                self._server.update_value(SERVICE_UUID, TX_UUID)
            except Exception as e:
                logger.warning("BLE reply stopped: update_value failed: %s", e)
                return
            self._notifications += 1
            # Yield so the stack actually flushes between chunks.
            await asyncio.sleep(0.005)
