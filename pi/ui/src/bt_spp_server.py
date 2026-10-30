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
import time

from link_protocol import StreamLink

logger = logging.getLogger(__name__)

# The standard Serial Port Profile UUID. Android's SPP constant is this exact value, so
# the two sides agree by convention rather than by configuration.
SPP_UUID = '00001101-0000-1000-8000-00805F9B34FB'

DEFAULT_CHANNEL = 3

RECV_BYTES = 4096

# How long to wait for the adapter to settle after publishing the SDP record.
SDP_SETTLE_SECONDS = 0.5

# How long a peer may stay silent before its session is reclaimed.
#
# The app polls several times a second while it is on screen, so silence for minutes
# means the peer is gone. It is deliberately generous, because an app that is only
# backgrounded stops polling and still holds a perfectly good socket, and that user
# should not pay a reconnect when they look back at the screen. It is also not load
# bearing for correctness any more: peers are served concurrently, so an abandoned
# socket no longer blocks anyone (see _serve_async). This is only housekeeping.
DEFAULT_IDLE_TIMEOUT = 300.0

# Socket read timeout, so each peer's loop can notice a stop request and its own idle
# deadline instead of blocking in recv() until the peer says something.
RECV_TIMEOUT = 1.0

# Peers that may be connected at once. One phone uses one, and a reconnect can briefly
# overlap its own predecessor, so four is already generous; more would just be ACL slots
# held by sessions nobody is using.
MAX_PEERS = 4

# Connections the kernel may queue while we are busy accepting. One was the old value and
# it is why a reconnect made while an old session was being torn down could be refused
# outright by the stack instead of waiting a few milliseconds.
ACCEPT_BACKLOG = 4


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


class _Peer:
    """One connected peer and the thread serving it.

    Only the bookkeeping needs to be shared: each peer still gets its own StreamLink, so
    its own authentication, its own line buffer, and its own replies. Nothing about one
    peer is visible to another.
    """

    __slots__ = ('conn', 'address', 'thread', 'last', 'opened')

    def __init__(self, conn, address):
        self.conn = conn
        self.address = address
        self.thread = None
        self.opened = time.monotonic()
        self.last = self.opened

    @property
    def label(self):
        return 'spp %s' % (self.address,)

    def close(self):
        try:
            self.conn.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.conn.close()
        except OSError:
            pass


class SppServer:
    """Serves the line protocol over RFCOMM, several peers at a time.

    Args:
        service: LinkService the protocol dispatches into.
        token: access token; None disables the check.
        require_token: whether a peer must authenticate before commands are accepted.
        channel: RFCOMM channel to listen on. Must match the SDP record.
        address: local adapter address, or '' for any.
        listener: pre-bound listening socket. Tests inject a TCP socket here; on the Pi
            this is left None and _make_listener() creates the Bluetooth one.
        publish_sdp: whether to run `sdptool add` on start.
        idle_timeout: seconds of silence after which a peer's session is reclaimed.
        max_peers: how many peers may be connected at once.
    """

    def __init__(self, service, token=None, require_token=True, channel=DEFAULT_CHANNEL,
                 address='', listener=None, publish_sdp=True,
                 idle_timeout=DEFAULT_IDLE_TIMEOUT, max_peers=MAX_PEERS):
        self.service = service
        self.token = token
        self.require_token = require_token
        self.channel = channel
        self.address = address
        self._listener = listener
        self.publish_sdp = publish_sdp
        self.idle_timeout = float(idle_timeout)
        self.max_peers = max(1, int(max_peers))

        self._stop = threading.Event()
        self._thread = None
        self._sdp_published = False
        self._connections = 0
        self._refused = 0
        self._reaped = 0

        # Peers currently being served. A set of _Peer, guarded by _peers_lock: the accept
        # thread adds, each peer thread removes, and stop() closes them all.
        self._peers = set()
        self._peers_lock = threading.Lock()

    # -- diagnostics ---------------------------------------------------------

    def describe(self):
        """What this server needs and what it found, for a startup log line."""
        with self._peers_lock:
            live = len(self._peers)
        return {
            'transport': 'spp',
            'uuid': SPP_UUID,
            'channel': self.channel,
            'sdptool': sdptool_available(),
            'sdp_published': self._sdp_published,
            'af_bluetooth': hasattr(socket, 'AF_BLUETOOTH'),
            'connections': self._connections,
            # A wedged link used to be invisible: connections kept arriving and none were
            # answered, and nothing in the log said so. These three make it visible.
            'peers': live,
            'refused': self._refused,
            'reaped': self._reaped,
            'idle_timeout': self.idle_timeout,
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

        sock.listen(ACCEPT_BACKLOG)
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

        # Join the accept thread first, so nothing new can arrive while peers are being
        # closed out from under it.
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

        # Close every live peer before joining, or a thread sitting in recv() with a
        # timeout would keep the join waiting and, worse, outlive the server.
        with self._peers_lock:
            peers = list(self._peers)
        for peer in peers:
            peer.close()
        for peer in peers:
            if peer.thread is not None:
                peer.thread.join(timeout=2)

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
            try:
                self._serve_async(conn, peer)
            except Exception:
                # Never let one bad peer take the listener down with it: that is the
                # failure mode this whole file exists to avoid.
                logger.exception("SPP could not start serving %s", peer)
                try:
                    conn.close()
                except OSError:
                    pass

    def _serve_async(self, conn, peer_address):
        """Hand one peer to its own thread.

        This used to be called inline, so exactly one peer was served at a time and the
        accept loop sat inside recv() until that peer hung up. A phone that went away
        without a clean disconnect (out of range, Bluetooth toggled, app killed while its
        socket was still open in the stack) therefore left the listener accepting new
        connections into the kernel backlog and never answering them. From the phone the
        link simply timed out, and nothing short of restarting the display app cleared it,
        which is why the only working advice was "unpair it and repair, or close and
        reopen the app".

        Peers share nothing, so they can be served independently.
        """
        try:
            conn.settimeout(RECV_TIMEOUT)
        except OSError as e:
            logger.debug("SPP could not set a read timeout on %s: %s", peer_address, e)

        peer = _Peer(conn, peer_address)
        with self._peers_lock:
            joined = len(self._peers) < self.max_peers
            if not joined:
                # Make room rather than refuse: the newcomer is almost always the phone
                # that just reconnected, and the peer holding a slot is the stale session
                # it reconnected from.
                joined = self._reap(force_one=True)
            if joined:
                self._peers.add(peer)

        if not joined:
            self._refused += 1
            logger.warning(
                "SPP: %d peers already connected and none idle, refusing %s",
                self._peer_count(), peer_address)
            peer.close()
            return

        thread = threading.Thread(target=self._serve, args=(peer,),
                                  name='spp-peer', daemon=True)
        peer.thread = thread
        thread.start()

    def _reap(self, force_one=False):
        """Drop finished peers, and optionally close the longest-idle one.

        The caller holds _peers_lock. Returns True when a slot is free afterwards.

        A finished peer is dropped here rather than by its own thread, so the accept loop
        is the single place that mutates the set on the way in and the peer thread on the
        way out; both discard, neither assumes anything about the other's timing.
        """
        for done in [p for p in self._peers if p.thread is None or not p.thread.is_alive()]:
            self._peers.discard(done)

        if len(self._peers) < self.max_peers:
            return True
        if not force_one:
            return False

        live = [p for p in self._peers if p.thread is not None and p.thread.is_alive()]
        if not live:
            return False
        oldest = min(live, key=lambda p: p.last)
        self._peers.discard(oldest)
        self._reaped += 1
        logger.warning(
            "SPP: reclaiming peer %s after %.0fs of silence to make room for a new one",
            oldest.address, time.monotonic() - oldest.last)
        oldest.close()
        # Its thread is still unwinding; the slot is free as soon as its socket is shut.
        return True

    def _serve(self, peer):
        """Run one peer to completion. Each peer gets its own session and its own login."""
        link = StreamLink(self.service, self.token, self.require_token, label=peer.label)
        logger.info("SPP peer connected: %s (peers now %d)",
                    peer.address, self._peer_count())
        try:
            reason = self._pump(peer, link)
            if reason == 'idle':
                with self._peers_lock:
                    self._reaped += 1
                logger.warning("SPP peer %s reclaimed: silent for %.0fs",
                               peer.address, self.idle_timeout)
            elif reason == 'refused':
                logger.warning("SPP peer %s closed: %s", peer.address, link.closed_reason)
        except Exception:
            logger.exception("SPP peer %s failed", peer.address)
        finally:
            peer.close()
            with self._peers_lock:
                self._peers.discard(peer)
            logger.info("SPP peer disconnected: %s", peer.address)

    def _peer_count(self):
        with self._peers_lock:
            return len(self._peers)

    def _pump(self, peer, link):
        """Move bytes until the peer goes away or the link gives up on it.

        Returns why it stopped: 'closed', 'idle', 'refused' or 'stopped'.
        """
        conn = peer.conn
        while not self._stop.is_set():
            try:
                data = conn.recv(RECV_BYTES)
            except InterruptedError:
                continue
            except socket.timeout:
                if time.monotonic() - peer.last >= self.idle_timeout:
                    return 'idle'
                continue
            except OSError as e:
                logger.debug("%s recv failed: %s", peer.label, e)
                return 'closed'

            if not data:
                return 'closed'

            peer.last = time.monotonic()
            out = link.on_bytes(data)
            if out:
                try:
                    conn.sendall(out)
                except socket.timeout:
                    logger.debug("%s send timed out, dropping the peer", peer.label)
                    return 'closed'
                except OSError as e:
                    logger.debug("%s send failed: %s", peer.label, e)
                    return 'closed'

            if link.closed:
                return 'refused'

        return 'stopped'
