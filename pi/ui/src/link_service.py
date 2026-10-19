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

# Colour schemes offered by the phone app. Must stay in sync with
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

    The app holds current_screen as a Screen enum. That is neither JSON-serialisable nor
    usable as a list index, so every payload and every lookup has to unwrap it first. The
    protocol and parity tests drive a stand-in whose current_screen is already an int,
    which is exactly why they passed while this failed against the real app.
    """
    return getattr(app.current_screen, 'value', app.current_screen)


def screen_name(app):
    """The name of the display app's current screen."""
    return app.screen_names[screen_index(app)]


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
            'throttle_percent': t.throttle_percent,
            'brake_percent': t.brake_percent,
            'coolant_temp_f': t.coolant_temp_f,
            'intake_temp_f': t.intake_temp_f,
            'ambient_temp_f': t.ambient_temp_f,
            'maf': t.maf,
            'fuel_level_percent': t.fuel_level_percent,
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
            'can_connected': getattr(app, 'can_handler', None) is not None,
            'demo_mode': app.settings.demo_mode,
            'sleeping': app.sleeping,
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
                app.settings.demo_mode = (value == '1' or value is True)
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
                app.settings.use_mph = (value == '1' or value is True)
            elif name == 'tire_low_psi':
                app.settings.tire_low_psi = float(value)
            elif name == 'tire_high_psi':
                app.settings.tire_high_psi = float(value)
            elif name == 'coolant_warn':
                app.settings.coolant_warn_f = int(value)
            elif name == 'led_sequence':
                app.settings.led_sequence = int(value)
                # Send LED sequence change to Arduino using the app's method
                if hasattr(app, '_send_led_sequence_to_arduino'):
                    app._send_led_sequence_to_arduino()
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
