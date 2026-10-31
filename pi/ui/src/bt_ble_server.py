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
import time

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

# The smallest notification worth sending: an ATT MTU of 23 carries 20 bytes of payload,
# which is the floor every phone supports. A refused chunk halves down to this, then gives
# up rather than looping.
MIN_CHUNK_BYTES = 20

# Pause between notifications, so the stack actually flushes each one before the next.
NOTIFY_PACING_SECONDS = 0.005

# Replies that may be waiting to be notified before new ones are dropped. The client asks
# one question at a time, so anything above a handful means it has stopped reading.
MAX_PENDING_REPLIES = 16

# Silence after which a half-received line is assumed to be left over from a central that
# went away. The app polls several times a second and writes one request per poll, so a
# live session never leaves a fragment sitting for anywhere near this long.
PEER_GAP_SECONDS = 5.0

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
        # signaled, so the session is reset when a new central connects (see _on_connect).
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

        # Replies waiting to be notified, and the one task that sends them.
        #
        # One writer, not one task per reply. A reply is several notifications (about a
        # kilobyte at ~180 bytes each), and two of those interleaving on the loop splice
        # their chunks together: the central then reads a line that is half one reply and
        # half another, skips it, and eventually times out and reconnects. That showed up
        # as an occasional dropped poll rather than as anything that named itself.
        self._replies = None
        self._drain_task = None

        # When the last write arrived, so a fragment left by a vanished central can be
        # told apart from one belonging to a live request.
        self._last_write = 0.0

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

    def start(self, timeout=75):
        """Start the peripheral and wait until it is really advertising.

        Waiting matters. Registering the advertisement is asynchronous, so a start() that
        only spawns the thread reports success for a transport that can still fail a
        moment later. That has been observed: with a previous instance's advertisement not
        yet released, BlueZ refused the registration and the app printed a confident
        "Bluetooth link started" for a link that was already dead. Raising here instead
        lets bt_link.py record the reason and the banner tell the truth.

        The default is longer than BlueZ's 25 s D-Bus activation timeout on purpose: when
        bluetoothd has just died and systemd is bringing it back, every registration
        attempt inside that window fails, and a shorter wait gives up on a link that is
        about to work. main.py runs this on its own thread, so the wait costs the display
        nothing.
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

        self._replies = asyncio.Queue(maxsize=MAX_PENDING_REPLIES)
        self._drain_task = self._loop.create_task(self._drain_replies())

        await self._server.add_new_service(SERVICE_UUID)

        # RX: the central writes request lines here.
        #
        # Both write types are accepted, and that matters for Android. A write *request*
        # occupies the client's single GATT operation slot until its own write callback
        # arrives, and on at least one phone that callback never comes, so the connection
        # stayed busy for ever after the first chunk and every later chunk was refused.
        # A write *command* needs no acknowledgment, so nothing is left outstanding. The
        # protocol already replies to the request itself, so dropping the ATT-level
        # acknowledgment costs nothing.
        await self._server.add_new_characteristic(
            SERVICE_UUID, RX_UUID,
            GATTCharacteristicProperties.write
            | GATTCharacteristicProperties.write_without_response, None,
            GATTAttributePermissions.writeable)

        # TX: we notify reply lines from here. Readable as well, so a central can poll
        # instead if it does not want notifications.
        await self._server.add_new_characteristic(
            SERVICE_UUID, TX_UUID, GATTCharacteristicProperties.notify, b'',
            GATTAttributePermissions.readable | GATTAttributePermissions.writeable)

        # Registering the advertisement is the step that actually fails when the service
        # is restarted while a phone is connected: BlueZ still holds the previous
        # instance's advertisement, and refuses the new one outright. That left the BLE
        # transport dead for the life of the process, and worse, the phone could still
        # connect to the leftover GATT objects and subscribe, so it looked alive while
        # nothing answered. Retry instead of giving up on the first refusal; it clears
        # within a few seconds once the old client has gone.
        #
        # The window has to outlast BlueZ's 25 s D-Bus activation timeout, not just a
        # stuck advertisement: when bluetoothd has crashed, every attempt inside that
        # window fails with "Failed to activate service 'org.bluez': timed out", and the
        # old 14 s budget lost that race every single time. The transport then stayed dead
        # until mx5-bt-agent.py noticed 90 s later and restarted this whole service.
        ATTEMPTS = 12
        RETRY_SEC = 5
        last_error = None
        for attempt in range(1, ATTEMPTS + 1):
            try:
                await self._server.start()
                last_error = None
                break
            except Exception as e:
                last_error = e
                logger.warning(
                    "BLE advertisement registration attempt %d/%d failed: %s",
                    attempt, ATTEMPTS, e)
                if attempt < ATTEMPTS:
                    await asyncio.sleep(RETRY_SEC)

        if last_error is not None:
            raise last_error

        logger.info("BLE link advertising as %r (service %s)", self.name, SERVICE_UUID)

        # Past this line the advertisement is registered, so start() may report success.
        self._ready.set()

        # Idle until stopped; bless runs the D-Bus work on its own tasks.
        while not self._stop.is_set():
            await asyncio.sleep(0.5)

    async def _shutdown(self):
        if self._drain_task is not None:
            self._drain_task.cancel()
            self._drain_task = None
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

        now = time.monotonic()
        gap = now - self._last_write
        self._last_write = now

        # A half-received line left over from a central that went away would be spliced
        # onto this one, so the first request of a reconnected phone is consumed as
        # garbage and it times out once before working. BlueZ does not tell us when a
        # central disconnects, so this is inferred: a live session never leaves a partial
        # line sitting for seconds, because one request is a few hundred bytes written in
        # a single burst.
        if gap > PEER_GAP_SECONDS and self.link.session.pending_bytes():
            logger.info("BLE: dropping %d bytes left by a previous central",
                        self.link.session.pending_bytes())
            # A new session, which also means a new login: the fragment came from a
            # central that is no longer here.
            self.link.reset()

        out = self.link.on_bytes(value)
        if out:
            self._notify_soon(out)

        if self.link.closed:
            logger.warning("BLE link closed: %s", self.link.closed_reason)
            # A new central must authenticate again, since we cannot always tell when
            # one goes away.
            self.link.reset()

    def _notify_soon(self, payload):
        """Queue a reply for the single writer task.

        The write callback is synchronous, so the payload has to be handed to the loop
        rather than awaited here. run_coroutine_threadsafe is used rather than
        ensure_future so this stays correct if a future bless version dispatches the
        callback from another thread.
        """
        if self._loop is None or self._replies is None:
            logger.warning("BLE reply dropped: no event loop")
            return
        try:
            asyncio.run_coroutine_threadsafe(self._enqueue(payload), self._loop)
        except Exception as e:
            logger.warning("BLE reply could not be scheduled: %s", e)

    async def _enqueue(self, payload):
        """Put one reply on the queue, dropping it rather than growing without bound."""
        try:
            self._replies.put_nowait(payload)
        except asyncio.QueueFull:
            # A central that has stopped reading. Dropping this reply is right: the client
            # is already out of step and will time out, and holding it would only delay
            # the replies behind it.
            logger.warning("BLE reply dropped: %d already waiting to be sent",
                           self._replies.maxsize)

    async def _drain_replies(self):
        """Send queued replies one at a time, preserving order and chunk boundaries."""
        while True:
            payload = await self._replies.get()
            try:
                await self._notify(payload)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning("BLE reply abandoned: %s", e)

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

        # Start at the configured size and shrink if the stack refuses a payload.
        #
        # The real ceiling is the negotiated MTU, and nothing in the Python API reports
        # what that turned out to be: a phone that leaves it at the default 23 needs
        # 20-byte notifications, and one that negotiated 517 is happy with 180. Sending
        # 180 regardless works on most phones and fails completely on the ones that did
        # not negotiate, so a refusal halves the chunk instead of abandoning the reply.
        chunk = max(MIN_CHUNK_BYTES, min(self.chunk_bytes, len(payload)))
        sent = 0
        while sent < len(payload):
            part = payload[sent:sent + chunk]
            tx.value = part
            try:
                self._server.update_value(SERVICE_UUID, TX_UUID)
            except Exception as e:
                if len(part) > MIN_CHUNK_BYTES:
                    chunk = max(MIN_CHUNK_BYTES, chunk // 2)
                    logger.warning(
                        "BLE: %d-byte notification refused (%s), retrying at %d",
                        len(part), e, chunk)
                    continue
                logger.warning("BLE reply stopped at byte %d of %d: %s",
                               sent, len(payload), e)
                return
            self._notifications += 1
            sent += len(part)
            # Yield so the stack actually flushes between chunks.
            await asyncio.sleep(NOTIFY_PACING_SECONDS)
