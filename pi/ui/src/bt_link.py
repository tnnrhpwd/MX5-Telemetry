"""Starts the Bluetooth link, SPP first and BLE alongside it.

Configuration is by environment variable, matching the style already used for the web
server's token and CORS settings:

    MX5_BT          off | spp | ble | both      (default: both)
    MX5_BT_TOKEN    access token                (default: MX5_WEB_TOKEN, same secret)
    MX5_BT_SPP_CHANNEL  RFCOMM channel          (default: 3)
    MX5_BT_ADDRESS  local adapter MAC for SPP   (default: auto-detect via hciconfig)
    MX5_BT_NAME     BLE advertised name         (default: MX5 Pi Link)

Both transports are on by default because they are fallbacks for each other: SPP is the
cheaper protocol but depends on an SDP record, and BLE needs no SDP but chunks its replies.
Starting one and failing is not a reason to give up on the other, so each is started
independently and a failure is reported rather than propagated.

Nothing here is imported by web_server.py, so a Pi without any Bluetooth tooling still
serves the web page exactly as before.
"""

import logging
import os

logger = logging.getLogger(__name__)

VALID_MODES = ('off', 'spp', 'ble', 'both')


def _env_bool(name, default):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


class BtLink:
    """Owns whichever Bluetooth transports are enabled, and their failures."""

    def __init__(self, service, mode=None, token=None, spp_channel=None, name=None,
                 address=None):
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

        self._spp = None
        self._ble = None
        self.errors = {}

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

        started = False
        if self.mode in ('spp', 'both'):
            started |= self._start_spp()
        if self.mode in ('ble', 'both'):
            started |= self._start_ble()

        if not started:
            logger.warning("No Bluetooth transport started; see errors above. "
                           "The web API and the USB tether are unaffected.")
        return started

    def _start_spp(self):
        try:
            from bt_spp_server import SppServer
            self._spp = SppServer(self.service, token=self.token,
                                  require_token=self.require_token,
                                  channel=self.spp_channel,
                                  address=self.address)
            self._spp.start()
            logger.info("SPP link up: %s", self._spp.describe())
            return True
        except Exception as e:
            self.errors['spp'] = str(e)
            logger.warning("SPP link not started: %s", e)
            self._spp = None
            return False

    def _start_ble(self):
        try:
            from bt_ble_server import BleServer, BLESS_AVAILABLE, BLESS_IMPORT_ERROR
            if not BLESS_AVAILABLE:
                raise RuntimeError('bless not installed (%s)' % BLESS_IMPORT_ERROR)
            self._ble = BleServer(self.service, token=self.token,
                                  require_token=self.require_token, name=self.name)
            self._ble.start()
            logger.info("BLE link up: %s", self._ble.describe())
            return True
        except Exception as e:
            self.errors['ble'] = str(e)
            logger.warning("BLE link not started: %s", e)
            self._ble = None
            return False

    def stop(self):
        for transport in (self._spp, self._ble):
            if transport is not None:
                try:
                    transport.stop()
                except Exception as e:
                    logger.debug("Stopping a Bluetooth transport failed: %s", e)
        self._spp = None
        self._ble = None

    # -- diagnostics ---------------------------------------------------------

    def status(self):
        """A summary for the startup log and for anything that wants to report it."""
        out = {'mode': self.mode, 'token_required': self.require_token, 'errors': self.errors}
        if self.refused_reason is not None:
            out['refused'] = self.refused_reason
        if self._spp is not None:
            out['spp'] = self._spp.describe()
        if self._ble is not None:
            out['ble'] = self._ble.describe()
        return out
