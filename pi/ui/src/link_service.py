"""Every read and command the remote link exposes, with no transport in it.

These used to live inline inside the Flask view functions in web_server.py, which made
HTTP the only way in. The roof console, the web page and the Bluetooth link all want the
same operations, so they live here instead and each transport is a thin adapter over
this class. Nothing in this file knows about HTTP, sockets, or Bluetooth.

Commands return ``(payload, http_status)``. The status is only meaningful to the HTTP
adapter; it is carried here so that refactoring the routes out did not change a single
response code or body the web page already depends on.
"""

import logging
import time

from roof_controller import RoofController, RoofControllerError

logger = logging.getLogger(__name__)

# The round display has eight pages. The routes hardcoded 8 and the Bluetooth link is a
# replacement for those routes, not a new contract, so it stays 8 here too.
SCREEN_COUNT = 8

# Color schemes offered by the phone app. Must stay in sync with
# android/mx5-remote/Palette.SCHEMES and the ESP32 theme table.
THEME_SCHEMES = (
    'aurora', 'crimson', 'emerald', 'sakura', 'midnight', 'sunset',
    'ocean', 'cyberpunk', 'monokai', 'usa', 'forest', 'neutral',
)


def _truthy(value):
    """Interpret a setting value that may arrive as bool, int or string.

    The same endpoint is driven by the web page (strings), the Bluetooth line
    protocol (strings) and the phone app (JSON numbers), so a plain
    ``value == '1'`` check silently treats a JSON ``1`` as false.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def screen_index(app):
    """The display app's current screen as a plain int.

    The app holds current_screen as a Screen enum. That is neither JSON-serializable nor
    usable as a list index, so every payload and every lookup has to unwrap it first. The
    protocol and parity tests drive a stand-in whose current_screen is already an int,
    which is exactly why they passed while this failed against the real app.
    """
    return getattr(app.current_screen, 'value', app.current_screen)


def screen_name(app):
    """The name of the display app's current screen."""
    return app.screen_names[screen_index(app)]


def _can_is_live(app):
    """True when the CAN handler is actually receiving frames right now.

    Mirrors `CANHandler.is_receiving_data()`. The handler exposes it, but the
    stand-in app used by the protocol/parity tests has a `can_handler` without
    that method, so the fallback keeps those tests honest instead of crashing.
    """
    handler = getattr(app, 'can_handler', None)
    if handler is None:
        return False
    probe = getattr(handler, 'is_receiving_data', None)
    if probe is None:
        return True
    return bool(probe())


class LinkService:
    """The shared operations behind /api/* and the Bluetooth line protocol."""

    def __init__(self, display_app):
        """
        Args:
            display_app: Main display application instance (has screen, settings, etc.)
        """
        self.display_app = display_app
        # MX5things RCNC-2 roof controller (optional hardware; opens lazily).
        self.roof = RoofController()

    # -- reads ---------------------------------------------------------------

    def status(self):
        """Current screen, demo/sleep flags and every persisted setting."""
        app = self.display_app
        return {
            'screen': screen_index(app),
            'screen_name': screen_name(app),
            'demo_mode': app.settings.demo_mode,
            'sleeping': app.sleeping,
            'nav_locked': app.swc_handler.nav_locked if app.swc_handler else False,
            'settings': {
                'demo_mode': app.settings.demo_mode,
                'brightness': app.settings.brightness,
                'volume': app.settings.volume,
                'shift_rpm': app.settings.shift_rpm,
                'redline_rpm': app.settings.redline_rpm,
                'use_mph': app.settings.use_mph,
                'tire_low_psi': app.settings.tire_low_psi,
                'tire_high_psi': app.settings.tire_high_psi,
                'coolant_warn_f': app.settings.coolant_warn_f,
                'led_sequence': app.settings.led_sequence,
                'led_enabled': app.settings.led_enabled,
                'led_color_mode': app.settings.led_color_mode,
                'led_brightness': app.settings.led_brightness,
                'led_theme_dim': app.settings.led_theme_dim,
                'led_ramp': app.settings.led_ramp,
                'led_shift_rpm': app.settings.led_shift_rpm,
                'led_shift_hz': app.settings.led_shift_hz,
                'led_shift_color': app.settings.led_shift_color,
                'clutch_display_mode': app.settings.clutch_display_mode,
                'theme_scheme': app.settings.theme_scheme,
                'theme_dark': app.settings.theme_dark,
            },
        }

    def telemetry(self):
        """Full live telemetry snapshot.

        The web page only ever needed the current screen and the settings, so the live
        values went to the ESP32 over serial and were never exposed over HTTP. The car
        app replaces that display, so it needs everything the serial link carries. Keys
        are snake_case and match the attribute names on TelemetryData in main.py, so a
        field added there is easy to add here.
        """
        app = self.display_app
        t = app.telemetry
        return {
            'rpm': t.rpm,
            'speed_kmh': t.speed_kmh,
            'gear': t.gear,
            'gear_estimated': t.gear_estimated,
            'clutch_engaged': t.clutch_engaged,
            'recommended_gear': t.recommended_gear,
            'gear_color': t.gear_color,
            'is_in_neutral': t.is_in_neutral,
            'is_in_reverse': t.is_in_reverse,
            # Raw CAN values behind the reverse decision. ISSUE-14's last open
            # question is whether the PCM ever writes 0x201's speed field below
            # its centre; these two numbers answer it from an ordinary drive.
            'speed_raw': t.speed_raw,
            'transmission_range': t.transmission_range,
            'throttle_percent': t.throttle_percent,
            'brake_percent': t.brake_percent,
            'coolant_temp_f': t.coolant_temp_f,
            'intake_temp_f': t.intake_temp_f,
            'ambient_temp_f': t.ambient_temp_f,
            'maf': t.maf,
            'fuel_level_percent': t.fuel_level_percent,
            # Pre-hysteresis mean: what the fuel accounting runs on, and the honest
            # number for anything diagnosing the gas figures from a phone.
            'fuel_level_average': t.fuel_level_average,
            'voltage': t.voltage,
            'tire_pressure': list(t.tire_pressure),
            'tire_temp': list(t.tire_temp),
            'tpms_last_update_str': list(t.tpms_last_update_str),
            'tpms_connected': t.tpms_connected,
            'g_lateral': t.g_lateral,
            'g_longitudinal': t.g_longitudinal,
            'lap_time_ms': t.lap_time_ms,
            'best_lap_ms': t.best_lap_ms,
            'instant_mpg': t.instant_mpg,
            'instant_mpg_valid': t.instant_mpg_valid,
            'average_mpg': t.average_mpg,
            # 'maf' | 'fuel_gauge' | 'estimated' - where the average came from, so a
            # surprising figure can be traced without reading the calculator.
            'average_mpg_source': t.average_mpg_source,
            'range_miles': t.range_miles,
            'check_engine_light': t.check_engine_light,
            'abs_warning': t.abs_warning,
            'traction_control_off': t.traction_control_off,
            'traction_control_active': t.traction_control_active,
            'oil_status': t.oil_status,
            'battery_warning': t.battery_warning,
            'door_ajar': t.door_ajar,
            'seatbelt_warning': t.seatbelt_warning,
            'airbag_warning': t.airbag_warning,
            'brake_warning': t.brake_warning,
            'high_beam_on': t.high_beam_on,
            'fog_light_on': t.fog_light_on,
            'headlights_on': t.headlights_on,
            'high_beams_on': t.high_beams_on,
            'dtc_codes': list(t.dtc_codes),
            'dtc_count': t.dtc_count,
            'wheel_slip': list(t.wheel_slip),
            # A handler object existing is not the same as a bus that is talking.
            # The object is built at start-up whether or not the MCP2515 ever came
            # up, so this used to report "UP" over a dead link - and the System
            # page had no way to say the car had gone quiet.
            'can_connected': _can_is_live(app),
            'demo_mode': app.settings.demo_mode,
            'sleeping': app.sleeping,
            # LED strip health, reported by the Nano itself over its serial link. The
            # strip used to be a black box: a dead CAN link and a real 0 rpm looked the
            # same on the panel and in the app.
            'led': getattr(app, 'led_status', None) or {'connected': False},
        }

    def roof_status(self):
        """Settings dict for the web UI, or {'connected': False, ...}."""
        try:
            info = self.roof.status()
        except RoofControllerError as e:
            return {
                'connected': False,
                'released': self.roof.released,
                'error': str(e),
            }
        info['connected'] = True
        return info

    # -- display and settings ------------------------------------------------

    def set_screen(self, screen_num):
        """Change to a specific screen by index."""
        if 0 <= screen_num < SCREEN_COUNT:
            self.display_app.change_screen(screen_num)
            return {'success': True, 'screen': screen_num}, 200
        return {'success': False, 'error': 'Invalid screen number'}, 400

    def next_screen(self):
        new_screen = (screen_index(self.display_app) + 1) % SCREEN_COUNT
        self.display_app.change_screen(new_screen)
        return {'success': True, 'screen': new_screen}, 200

    def prev_screen(self):
        new_screen = (screen_index(self.display_app) - 1) % SCREEN_COUNT
        self.display_app.change_screen(new_screen)
        return {'success': True, 'screen': new_screen}, 200

    def update_setting(self, name, value):
        """Update any setting. Returns (payload, http_status)."""
        app = self.display_app
        if not name:
            return {'success': False, 'error': 'Missing setting name'}, 400

        try:
            # Handle each setting type appropriately
            if name == 'demo_mode':
                app.settings.demo_mode = _truthy(value)
                # Reinitialize data sources if demo mode changed
                app._init_data_sources()
            elif name == 'brightness':
                app.settings.brightness = int(value)
            elif name == 'volume':
                app.settings.volume = int(value)
                app.sound.set_volume(app.settings.volume)
            elif name == 'shift_rpm':
                app.settings.shift_rpm = int(value)
            elif name == 'redline_rpm':
                app.settings.redline_rpm = int(value)
            elif name == 'use_mph':
                app.settings.use_mph = _truthy(value)
            elif name == 'tire_low_psi':
                app.settings.tire_low_psi = float(value)
            elif name == 'tire_high_psi':
                app.settings.tire_high_psi = float(value)
            elif name == 'coolant_warn':
                app.settings.coolant_warn_f = int(value)
            elif name == 'led_sequence':
                seq = int(value)
                if not 1 <= seq <= 4:
                    return {'success': False, 'error': 'led_sequence must be 1-4'}, 400
                app.settings.led_sequence = seq
                self._push_led(app)
            elif name == 'led_enabled':
                app.settings.led_enabled = 1 if _truthy(value) else 0
                self._push_led(app)
            elif name == 'led_color_mode':
                mode = int(value)
                if mode not in (0, 1):
                    return {'success': False, 'error': 'led_color_mode must be 0 or 1'}, 400
                app.settings.led_color_mode = mode
                self._push_led(app)
            elif name == 'led_shift_rpm':
                rpm = int(value)
                # 0 is a legitimate value: it switches the shift light off. Any other
                # number has to be a real engine speed, or the strip would never reach it.
                if rpm != 0 and not 2000 <= rpm <= 8000:
                    return {'success': False, 'error': 'led_shift_rpm must be 0 or 2000-8000'}, 400
                app.settings.led_shift_rpm = rpm
                self._push_led(app)
            elif name == 'led_shift_hz':
                hz = int(value)
                if not 2 <= hz <= 15:
                    return {'success': False, 'error': 'led_shift_hz must be 2-15'}, 400
                app.settings.led_shift_hz = hz
                self._push_led(app)
            elif name == 'led_shift_color':
                color = str(value).strip().lower()
                if len(color) != 6:
                    return {'success': False, 'error': 'led_shift_color must be rrggbb'}, 400
                try:
                    int(color, 16)
                except ValueError:
                    return {'success': False, 'error': 'led_shift_color is not hex'}, 400
                app.settings.led_shift_color = color
                self._push_led(app)
            elif name == 'led_ramp':
                # "<rpm>:<rrggbb>,..." from the phone, forwarded to the strip as-is.
                # Reject anything that is not that shape rather than letting a malformed
                # string reach firmware that parses it byte by byte.
                text = str(value).strip()
                parts = [p for p in text.split(',') if p]
                if not 2 <= len(parts) <= 6:
                    return {'success': False, 'error': 'led_ramp needs 2-6 stops'}, 400
                for part in parts:
                    rpm, _, color = part.partition(':')
                    if not rpm.isdigit() or len(color) != 6:
                        return {'success': False, 'error': 'led_ramp stop must be rpm:rrggbb'}, 400
                    try:
                        int(color, 16)
                    except ValueError:
                        return {'success': False, 'error': 'led_ramp color is not hex'}, 400
                app.settings.led_ramp = text
                self._push_led(app)
            elif name == 'led_theme_dim':
                app.settings.led_theme_dim = 1 if _truthy(value) else 0
                self._push_led(app)
            elif name == 'led_brightness':
                level = int(value)
                if not 0 <= level <= 255:
                    return {'success': False, 'error': 'led_brightness must be 0-255'}, 400
                app.settings.led_brightness = level
                self._push_led(app)
            elif name == 'clutch_display_mode':
                app.settings.clutch_display_mode = int(value)
            elif name == 'theme_scheme':
                # The phone app owns the theme; the Pi only mirrors it so the
                # round display can follow when the phone is not connected.
                scheme = str(value)
                if scheme not in THEME_SCHEMES:
                    return {'success': False, 'error': 'Unknown theme scheme'}, 400
                app.settings.theme_scheme = scheme
            elif name == 'theme_dark':
                app.settings.theme_dark = _truthy(value)
            else:
                return {'success': False, 'error': 'Unknown setting'}, 400

            # Sync to ESP32 if available
            if app.esp32_handler:
                app._sync_settings_to_esp32()

            return {'success': True, 'name': name, 'value': value}, 200

        except Exception:
            logger.exception("Failed to update setting %r", name)
            return {'success': False, 'error': 'Internal error'}, 500

    def _push_led(self, app):
        """Push the LED settings to the strip and persist them on the Pi.

        Every LED key takes the same path: validate, store, send, save. Keeping it in one
        place is what stops a new key from being applied to the setting but never reaching
        the hardware.
        """
        if hasattr(app, 'apply_led_settings'):
            app.apply_led_settings()
            return
        # Desk-test fakes only record the sequence push.
        if hasattr(app, '_send_led_sequence_to_arduino'):
            app._send_led_sequence_to_arduino()
        if hasattr(app, '_send_led_config'):
            app._send_led_config()

    def led_command(self, command):
        """Forward a bench command (SELFTEST / IDENTIFY / DEMO) to the strip.

        An allow-list rather than a passthrough: this reaches firmware that parses byte by
        byte, and the app is the only caller that should ever be able to send `CFG:reset`.
        """
        app = self.display_app
        text = str(command or '').strip().upper()
        allowed = ('SELFTEST', 'IDENTIFY', 'PING', 'CFG?', 'DEMO:OFF')
        if text not in allowed and not (text.startswith('DEMO:') and text[5:].isdigit()):
            return {'success': False, 'error': 'Unknown LED command'}, 400
        if text.startswith('DEMO:') and text != 'DEMO:OFF':
            rpm = int(text[5:])
            if not 0 <= rpm <= 8000:
                return {'success': False, 'error': 'demo rpm must be 0-8000'}, 400
        if not hasattr(app, 'send_led_command'):
            return {'success': False, 'error': 'LED strip link unavailable'}, 503
        if not app.send_led_command(text):
            return {'success': False, 'error': 'LED strip not answering'}, 503
        return {'success': True, 'command': text}, 200

    def wake(self):
        """Wake display from sleep."""
        app = self.display_app
        if app.sleeping:
            app.sleeping = False
            app.last_activity = time.time()
        return {'success': True}, 200

    def calibrate_imu(self):
        """Calibrate IMU gyroscope zero point."""
        app = self.display_app
        try:
            if app.esp32_handler:
                app.esp32_handler.send_calibrate_imu()
                return {'success': True, 'message': 'Calibration command sent'}, 200
            return {'success': False, 'message': 'ESP32 not connected'}, 503
        except Exception:
            logger.exception("Failed to calibrate IMU")
            return {'success': False, 'message': 'Internal error'}, 500

    def reset_mpg(self):
        """Clear the stored fuel totals behind AVG MPG and RANGE.

        Those totals are a lifetime average. One contaminated stretch - a sender
        glitch, a MAF drop-out on the first drive - would otherwise skew the number
        for ever, with no way back short of deleting the JSON by hand over SSH. This
        is also how a tank can be compared against the pump from a clean slate.
        """
        app = self.display_app
        calc = getattr(app, 'mpg_calculator', None)
        if calc is None:
            return {'success': False, 'message': 'MPG calculator not available'}, 503
        try:
            calc.reset_lifetime_data()
            # Reflect it now rather than at the next loop iteration.
            app.telemetry.average_mpg = calc.average_mpg
            app.telemetry.average_mpg_source = calc.average_mpg_source
            app.telemetry.range_miles = calc.range_miles
            return {
                'success': True,
                'average_mpg': calc.average_mpg,
                'average_mpg_source': calc.average_mpg_source,
            }, 200
        except Exception:
            logger.exception("Failed to reset MPG totals")
            return {'success': False, 'message': 'Internal error'}, 500

    def sleep(self):
        """Put the display to sleep."""
        self.display_app.sleeping = True
        return {'success': True}, 200

    # -- roof controller (MX5things RCNC-2) ---------------------------------

    def roof_set(self, kind, value):
        """Apply one roof setting and return the refreshed status."""
        if value is None:
            return {'success': False, 'error': 'Missing value'}, 400
        try:
            if kind == 'speed':
                self.roof.set_speed(value)
            elif kind == 'auto':
                self.roof.set_auto(value)
            elif kind == 'mode':
                self.roof.set_mode(value)
            else:
                return {'success': False, 'error': 'Unknown roof command'}, 400
        except RoofControllerError as e:
            return {'success': False, 'error': str(e)}, 503
        return {'success': True, 'roof': self.roof_status()}, 200

    def roof_connect(self):
        """Claim the roof controller and report what it answers.

        Claiming is not a hold: the read that proves the module is there opens
        and closes the port itself, so the controller is never left busy.
        """
        try:
            info = self.roof.connect()
        except RoofControllerError as e:
            return {'success': False, 'error': str(e)}, 503
        info['connected'] = True
        return {'success': True, 'roof': info}, 200

    def roof_disconnect(self):
        """Hand the module back to the car so the roof keeps working."""
        self.roof.disconnect()
        return {'success': True, 'roof': self.roof_status()}, 200
