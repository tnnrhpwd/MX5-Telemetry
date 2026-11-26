"""Starts the Bluetooth link, SPP first and BLE alongside it.

Configuration is by environment variable, matching the style already used for the web
server's token and CORS settings:

    MX5_BT          off | spp | ble | both      (default: both)
    MX5_BT_TOKEN    access token                (default: MX5_WEB_TOKEN, same secret)
    MX5_BT_SPP_CHANNEL  RFCOMM channel          (default: 3)
    MX5_BT_ADDRESS  local adapter MAC for SPP   (default: auto-detect via hciconfig)
    MX5_BT_NAME     BLE advertised name         (default: MX5 Pi Link)
    MX5_BT_IDLE_TIMEOUT  seconds of silence before an SPP peer is reclaimed (default: 300)

Both transports are on by default because they are fallbacks for each other: SPP is the
cheaper protocol but depends on an SDP record, and BLE needs no SDP but chunks its replies.
Starting one and failing is not a reason to give up on the other, so each is started
independently and a failure is reported rather than propagated.

Each transport is then supervised for the rest of the run: a start that failed at boot is
retried with exponential backoff, and a transport whose loop died later is restarted. The
phone reconnecting is handled by the servers themselves; this is about the Pi's end coming
back after a radio reset, a bluetoothd restart, or losing the race against systemd.

Nothing here is imported by web_server.py, so a Pi without any Bluetooth tooling still
serves the web page exactly as before.
"""

import logging
import os
import threading
import time

logger = logging.getLogger(__name__)

VALID_MODES = ('off', 'spp', 'ble', 'both')


def _env_bool(name, default):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


def _default_spp_factory(**kwargs):
    from bt_spp_server import SppServer
    return SppServer(**kwargs)


def _default_ble_factory(**kwargs):
    from bt_ble_server import BleServer, BLESS_AVAILABLE, BLESS_IMPORT_ERROR
    if not BLESS_AVAILABLE:
        raise RuntimeError('bless not installed (%s)' % BLESS_IMPORT_ERROR)
    return BleServer(**kwargs)


class BtLink:
    """Owns whichever Bluetooth transports are enabled, and their failures.

    The transports are supervised rather than started once. On a car the app is started by
    systemd at boot, and bluetoothd - or a USB dongle, or the adapter's own power-on - is
    routinely several seconds behind it. A single `start()` at boot therefore failed, and
    nothing ever tried again: the Pi answered on the tether and silently had no Bluetooth
    for the rest of the drive. Recovery used to depend on `mx5-bt-agent` noticing that no
    BLE advertisement existed 90s later and restarting this whole service, which also tears
    down CAN and the display. Here a failed or dead transport is retried with backoff, so
    it comes up as soon as the radio does and nothing else is disturbed.
    """

    def __init__(self, service, mode=None, token=None, spp_channel=None, name=None,
                 address=None, spp_factory=None, ble_factory=None,
                 supervisor_tick=2.0, retry_initial=5.0, retry_max=60.0):
        self.service = service

        self.mode = (mode or os.environ.get('MX5_BT', 'both')).strip().lower()
        if self.mode not in VALID_MODES:
            logger.warning("Unknown MX5_BT=%r, falling back to 'both'", self.mode)
            self.mode = 'both'

        # One secret for both transports. If the web token is set, the Bluetooth link
        # expects the same value, so there is nothing new to distribute.
        env_token = (os.environ.get('MX5_BT_TOKEN')
                     or os.environ.get('MX5_WEB_TOKEN') or '').strip()
        self.token = token if token is not None else (env_token or None)
        self.require_token = bool(self.token)

        # A radio has no notion of localhost, so the web server's fail-safe has no equivalent
        # here: with no token it binds loopback-only and stays private, while a Bluetooth link
        # with no token accepts every command from any device that pairs. That is the screen,
        # every setting, and the roof. Refusing to start is the safe half of that trade, and
        # MX5_BT_ALLOW_NO_TOKEN=1 is the deliberate opt-out for a bench test over a pipe you
        # trust.
        self.allow_no_token = _env_bool('MX5_BT_ALLOW_NO_TOKEN', False)
        self.refused_reason = None
        if self.enabled and not self.require_token and not self.allow_no_token:
            self.refused_reason = (
                'no token configured, so the link would accept commands from any paired'
                ' device. Set MX5_WEB_TOKEN (or MX5_BT_TOKEN), or set'
                ' MX5_BT_ALLOW_NO_TOKEN=1 to run unauthenticated on purpose.')

        try:
            self.spp_channel = int(spp_channel or os.environ.get('MX5_BT_SPP_CHANNEL', 3))
        except (TypeError, ValueError):
            self.spp_channel = 3

        self.name = name or os.environ.get('MX5_BT_NAME', 'MX5 Pi Link')
        # Left empty, bt_spp_server reads the address off the adapter with hciconfig.
        self.address = (address if address is not None
                        else os.environ.get('MX5_BT_ADDRESS', '')).strip()

        # How long an SPP peer may stay silent before its session is reclaimed. The app
        # polls several times a second while it is on screen, so this only ever catches a
        # peer that has actually gone; it is generous because a backgrounded app stops
        # polling and still holds a perfectly good socket.
        try:
            self.idle_timeout = float(os.environ.get('MX5_BT_IDLE_TIMEOUT', 300) or 300)
        except (TypeError, ValueError):
            self.idle_timeout = 300.0

        self._spp = None
        self._ble = None
        self.errors = {}

        # Retry bookkeeping. Factories are injectable so the retry path can be tested
        # without a radio, and so a test can make "start fails" a certainty rather than a
        # hope.
        self._spp_factory = spp_factory or _default_spp_factory
        self._ble_factory = ble_factory or _default_ble_factory
        self.supervisor_tick = float(supervisor_tick)
        self.retry_initial = float(retry_initial)
        self.retry_max = float(retry_max)
        self._stop = threading.Event()
        self._supervisor = None
        self._failures = {}     # transport name -> consecutive failed starts
        self._retry_at = {}     # transport name -> monotonic time of the next attempt

    # -- lifecycle -----------------------------------------------------------

    @property
    def enabled(self):
        return self.mode != 'off'

    def start(self):
        """Start the enabled transports. Returns True if anything is listening."""
        if not self.enabled:
            logger.info("Bluetooth link disabled (MX5_BT=off)")
            return False

        if self.refused_reason is not None:
            logger.error("Bluetooth link NOT started: %s", self.refused_reason)
            logger.error("  The web API and the USB tether are unaffected.")
            self.errors['spp'] = self.refused_reason
            self.errors['ble'] = self.refused_reason
            return False

        # The same path the supervisor uses, so a first attempt that is too early is
        # scheduled for a retry exactly like a later failure would be. The stop flag is
        # cleared first: it is what _start_spp/_start_ble check to decide whether a
        # transport that just came up should be adopted, and a start() after a stop() would
        # otherwise build a link and immediately close it.
        self._stop.clear()
        if self.mode in ('spp', 'both'):
            self._ensure('spp', self._start_spp)
        if self.mode in ('ble', 'both'):
            self._ensure('ble', self._start_ble)

        started = self._spp is not None or self._ble is not None
        if not started:
            logger.warning("Bluetooth link is not up yet; it keeps retrying in the "
                           "background. The web API and the USB tether are unaffected.")

        self._start_supervisor()
        return started

    def _start_spp(self):
        try:
            transport = self._spp_factory(
                service=self.service, token=self.token,
                require_token=self.require_token,
                channel=self.spp_channel,
                address=self.address,
                idle_timeout=self.idle_timeout)
            transport.start()
            if self._stop.is_set():
                # stop() ran while start() was blocking (BLE waits for the advertisement).
                # Adopting it now would leave a live transport behind a link that is shut.
                transport.stop()
                return False
            self._spp = transport
            self.errors.pop('spp', None)
            logger.info("SPP link up: %s", self._spp.describe())
            return True
        except Exception as e:
            self.errors['spp'] = str(e)
            logger.debug("SPP link not started: %s", e)
            self._spp = None
            return False

    def _start_ble(self):
        try:
            transport = self._ble_factory(
                service=self.service, token=self.token,
                require_token=self.require_token, name=self.name)
            transport.start()
            if self._stop.is_set():
                transport.stop()
                return False
            self._ble = transport
            self.errors.pop('ble', None)
            logger.info("BLE link up: %s", self._ble.describe())
            return True
        except Exception as e:
            self.errors['ble'] = str(e)
            logger.debug("BLE link not started: %s", e)
            self._ble = None
            return False

    # -- supervision ---------------------------------------------------------

    def _start_supervisor(self):
        if self._supervisor is not None and self._supervisor.is_alive():
            return
        self._stop.clear()
        self._supervisor = threading.Thread(target=self._supervise,
                                            name='bt-supervisor', daemon=True)
        self._supervisor.start()

    def _supervise(self):
        while not self._stop.wait(self.supervisor_tick):
            try:
                self._repair()
            except Exception:
                # A supervisor that dies is worse than the fault it watches: nothing else
                # will ever bring the link back. Keep ticking.
                logger.exception("Bluetooth supervisor tick failed; the link keeps running")

    def _repair(self):
        if self.refused_reason is not None:
            return          # no token: nothing here is allowed to start
        if self.mode in ('spp', 'both'):
            self._ensure('spp', self._start_spp)
        if self.mode in ('ble', 'both'):
            self._ensure('ble', self._start_ble)

    @staticmethod
    def _alive(transport):
        probe = getattr(transport, 'is_alive', None)
        return True if probe is None else bool(probe())

    def _ensure(self, name, start):
        """Bring one transport back if it is not up, honouring its backoff."""
        field = '_' + name
        transport = getattr(self, field)

        if transport is not None and self._alive(transport):
            self._failures[name] = 0
            self._retry_at.pop(name, None)
            return

        now = time.monotonic()
        if now < self._retry_at.get(name, 0.0):
            return

        if transport is not None:
            # It started once and stopped: the radio was reset, bluetoothd restarted, or
            # the accept loop raised. stop() clears the server's own thread handle, which
            # is what makes the start() below actually reopen instead of returning early.
            logger.warning("%s stopped; restarting it", name.upper())
            try:
                transport.stop()
            except Exception as e:
                logger.debug("stopping the dead %s transport failed: %s", name, e)
            setattr(self, field, None)

        if start():
            self._failures[name] = 0
            self._retry_at.pop(name, None)
            return

        count = self._failures.get(name, 0) + 1
        self._failures[name] = count
        delay = min(self.retry_initial * (2 ** min(count - 1, 6)), self.retry_max)
        self._retry_at[name] = now + delay
        if count == 1:
            logger.warning("%s is not up (%s); retrying with backoff from %.0fs",
                           name.upper(), self.errors.get(name), delay)
        else:
            logger.info("%s still not up (attempt %d); next try in %.0fs",
                        name.upper(), count, delay)

    def stop(self):
        self._stop.set()
        if self._supervisor is not None:
            # The BLE start inside a tick can block for its own timeout, so this join is
            # bounded: the supervisor is a daemon and the process is usually exiting here.
            self._supervisor.join(timeout=2)
            self._supervisor = None
        for transport in (self._spp, self._ble):
            if transport is not None:
                try:
                    transport.stop()
                except Exception as e:
                    logger.debug("Stopping a Bluetooth transport failed: %s", e)
        self._spp = None
        self._ble = None
        # A restart must not inherit a backoff, or `start()` after `stop()` would sit idle
        # until a timer that belonged to the previous run expired.
        self._retry_at.clear()
        self._failures.clear()

    # -- diagnostics ---------------------------------------------------------

    def status(self):
        """A summary for the startup log and for anything that wants to report it."""
        out = {'mode': self.mode, 'token_required': self.require_token,
               'idle_timeout': self.idle_timeout, 'errors': self.errors,
               'supervising': bool(self._supervisor is not None
                                   and self._supervisor.is_alive()),
               'failed_attempts': dict(self._failures)}
        if self.refused_reason is not None:
            out['refused'] = self.refused_reason
        if self._spp is not None:
            out['spp'] = self._spp.describe()
        if self._ble is not None:
            out['ble'] = self._ble.describe()
        return out
