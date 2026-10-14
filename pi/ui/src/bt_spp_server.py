"""Classic Bluetooth SPP (RFCOMM) server for the MX5 link.

The Android app opens an RFCOMM socket to the SPP UUID and speaks the line protocol from
link_protocol.py over it. This file only moves bytes; all of the meaning is elsewhere.

Two things have to be true for Android to reach this:

1. An RFCOMM socket must be listening on a channel. Python can do that directly with
   AF_BLUETOOTH.
2. An SDP service record advertising that channel under the SPP UUID must be published,
   because Android's createRfcommSocketToServiceRecord(uuid) does an SDP lookup before it
   will connect. Python has no stdlib way to publish one, so this shells out to `sdptool`,
   which is deprecated in BlueZ but still shipped on Raspberry Pi OS.

Step 2 is the fragile part and it is why the BLE binding exists as the alternative: GATT
has no SDP, so it cannot fail this way. `describe()` reports which pieces are present so
a failure says what is missing instead of just not connecting.

The listener is injectable so the accept/serve loop can be tested over a plain TCP socket
on a desk, which is what test_link_protocol.py does. Only _make_listener() is Pi-only.
"""

import errno
import logging
import socket
import subprocess
import threading

from link_protocol import StreamLink

logger = logging.getLogger(__name__)

# The standard Serial Port Profile UUID. Android's SPP constant is this exact value, so
# the two sides agree by convention rather than by configuration.
SPP_UUID = '00001101-0000-1000-8000-00805F9B34FB'

DEFAULT_CHANNEL = 3

RECV_BYTES = 4096

# How long to wait for the adapter to settle after publishing the SDP record.
SDP_SETTLE_SECONDS = 0.5


def sdptool_available():
    """True if `sdptool` is on PATH, which is what publishes the service record."""
    from shutil import which
    return which('sdptool') is not None


def _local_adapter_address():
    """The local Bluetooth adapter's address, or '' to mean "any".

    RFCOMM wants a bound address. An empty string binds any adapter, which is what we want
    on a Pi with one radio, and avoids hardcoding a MAC that differs per unit.
    """
    try:
        out = subprocess.run(['hciconfig'], capture_output=True, text=True, timeout=5)
        for line in out.stdout.splitlines():
            line = line.strip()
            if line.startswith('BD Address:'):
                return line.split(':', 1)[1].strip().split()[0]
    except (OSError, subprocess.SubprocessError):
        pass
    return ''


class SppServer:
    """Serves the line protocol over RFCOMM, one connection at a time.

    Args:
        service: LinkService the protocol dispatches into.
        token: access token; None disables the check.
        require_token: whether a peer must authenticate before commands are accepted.
        channel: RFCOMM channel to listen on. Must match the SDP record.
        address: local adapter address, or '' for any.
        listener: pre-bound listening socket. Tests inject a TCP socket here; on the Pi
            this is left None and _make_listener() creates the Bluetooth one.
        publish_sdp: whether to run `sdptool add` on start.
    """

    def __init__(self, service, token=None, require_token=True, channel=DEFAULT_CHANNEL,
                 address='', listener=None, publish_sdp=True):
        self.service = service
        self.token = token
        self.require_token = require_token
        self.channel = channel
        self.address = address
        self._listener = listener
        self.publish_sdp = publish_sdp

        self._stop = threading.Event()
        self._thread = None
        self._sdp_published = False
        self._connections = 0

    # -- diagnostics ---------------------------------------------------------

    def describe(self):
        """What this server needs and what it found, for a startup log line."""
        return {
            'transport': 'spp',
            'uuid': SPP_UUID,
            'channel': self.channel,
            'sdptool': sdptool_available(),
            'sdp_published': self._sdp_published,
            'af_bluetooth': hasattr(socket, 'AF_BLUETOOTH'),
            'connections': self._connections,
        }

    # -- SDP -----------------------------------------------------------------

    def _publish_sdp(self):
        """Advertise the channel under the SPP UUID so Android can find it."""
        if not self.publish_sdp:
            return False
        if not sdptool_available():
            logger.warning(
                "sdptool not found, so no SDP record will be published. Android's "
                "createRfcommSocketToServiceRecord() needs one and will not connect. "
                "Install bluez-tools, or use the BLE transport, which needs no SDP.")
            return False
        try:
            result = subprocess.run(
                ['sdptool', 'add', '--channel=%d' % self.channel, 'SP'],
                capture_output=True, text=True, timeout=10, check=False)
        except (OSError, subprocess.SubprocessError) as e:
            logger.warning("sdptool failed: %s", e)
            return False

        # sdptool exits non-zero when the local SDP server is unreachable, and it is the
        # only thing here that can publish this record. Ignoring the exit code made the
        # log state that the record was published while every Android client failed its
        # SDP lookup, which pointed the reader at the client instead of at the Pi.
        if result.returncode != 0:
            logger.warning(
                "sdptool add --channel=%d exited %d, so NO SDP record was published "
                "(%s). Android's createRfcommSocketToServiceRecord() will not find this "
                "service. Check the local SDP server with `sdptool browse local`; the "
                "BLE transport needs no SDP.",
                self.channel, result.returncode,
                (result.stderr or result.stdout or '').strip() or 'no output')
            return False

        # Publishing is asynchronous inside bluetoothd; give it a moment so a client that
        # pairs immediately after startup still finds the record.
        threading.Event().wait(SDP_SETTLE_SECONDS)
        self._sdp_published = True
        logger.info("Published SPP on channel %d (uuid %s)", self.channel, SPP_UUID)
        return True

    # -- listening -----------------------------------------------------------

    def _make_listener(self):
        """Bind the RFCOMM socket. This is the only Pi-only part of this file."""
        if not hasattr(socket, 'AF_BLUETOOTH'):
            raise RuntimeError(
                'AF_BLUETOOTH is unavailable: this Python has no Bluetooth socket '
                'support (the Pi does; a desktop build may not).')

        sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM,
                             socket.BTPROTO_RFCOMM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        address = self.address or _local_adapter_address()
        try:
            sock.bind((address, self.channel))
        except OSError as e:
            sock.close()
            # The two ways this fails have opposite fixes, so do not describe them with
            # one message: a taken channel is not a missing adapter address, and blaming
            # the address sent the reader looking for a fault that was not there. On stock
            # BlueZ, bluetoothd's own SAP plugin reserves channel 3.
            if e.errno == errno.EADDRINUSE:
                raise RuntimeError(
                    "RFCOMM channel %d is already in use on address %r: %s. Another "
                    "process holds it - commonly bluetoothd itself, which reserves "
                    "channel 3 for the SAP plugin on stock BlueZ. Choose a free channel "
                    "with MX5_BT_SPP_CHANNEL, or stop whatever holds this one."
                    % (self.channel, address, e))
            # A bare 'bad bluetooth address' is unhelpful too: an empty address means no
            # adapter address could be read, which has a fix.
            raise RuntimeError(
                "Could not bind RFCOMM channel %d on address %r: %s. An empty address "
                "means no local adapter address was found: check that `hciconfig` is "
                "installed and the adapter is up, or set MX5_BT_ADDRESS to the Pi's own "
                "MAC (hciconfig -a prints it)."
                % (self.channel, address, e))

        sock.listen(1)
        return sock

    # -- lifecycle -----------------------------------------------------------

    def start(self):
        """Publish SDP and start accepting connections in a background thread.

        Raises when the SDP record was not published. Without a record an Android client
        cannot find this service: createRfcommSocketToServiceRecord() resolves the UUID
        through SDP, so it fails to connect no matter how healthy the listening socket
        looks. Reporting that as a successful start made the app claim a working SPP link
        on a Pi where the record could never be published. BLE needs no SDP and is
        unaffected.
        """
        if self._thread is not None:
            return
        if self._listener is None:
            # Publish before listening: a client that connects the instant we are up
            # should already be able to find us.
            self._publish_sdp()
            # Only an attempted-and-failed publish is an error. publish_sdp=False means the
            # caller chose to skip SDP, which is a legitimate configuration.
            if self.publish_sdp and not self._sdp_published:
                raise RuntimeError(
                    'No SDP record was published, so an Android client cannot find '
                    'this service by UUID. SPP is unusable until `sdptool browse '
                    'local` works; BLE needs no SDP.')
            self._listener = self._make_listener()

        self._stop.clear()
        self._thread = threading.Thread(target=self._accept_loop,
                                        name='spp-link', daemon=True)
        self._thread.start()
        logger.info("SPP link listening on channel %d", self.channel)

    def stop(self):
        self._stop.set()
        try:
            if self._listener is not None:
                self._listener.close()
        except OSError:
            pass
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def _accept_loop(self):
        while not self._stop.is_set():
            try:
                conn, peer = self._listener.accept()
            except OSError as e:
                if self._stop.is_set():
                    break
                # A closed listener during shutdown is expected; anything else, back off
                # briefly rather than spinning on a dead socket.
                if e.errno in (errno.EBADF, errno.EINVAL):
                    break
                logger.warning("SPP accept failed: %s", e)
                threading.Event().wait(1.0)
                continue

            self._connections += 1
            # Serialise: one peer at a time. RFCOMM is point-to-point in practice, and a
            # shared session would let two phones see each other's replies.
            self._serve(conn, peer)

    def _serve(self, conn, peer):
        """Run one peer to completion. Each peer gets its own session and its own login."""
        label = 'spp %s' % (peer,)
        link = StreamLink(self.service, self.token, self.require_token, label=label)
        logger.info("SPP peer connected: %s", peer)
        try:
            self._pump(conn, link, label)
        finally:
            try:
                conn.close()
            except OSError:
                pass
            logger.info("SPP peer disconnected: %s", peer)

    def _pump(self, conn, link, label):
        """Move bytes until the peer goes away or the link gives up on it."""
        while not self._stop.is_set():
            try:
                data = conn.recv(RECV_BYTES)
            except InterruptedError:
                continue
            except OSError as e:
                logger.debug("%s recv failed: %s", label, e)
                return

            if not data:
                return

            out = link.on_bytes(data)
            if out:
                try:
                    conn.sendall(out)
                except OSError as e:
                    logger.debug("%s send failed: %s", label, e)
                    return

            if link.closed:
                logger.warning("%s closed: %s", label, link.closed_reason)
                return
