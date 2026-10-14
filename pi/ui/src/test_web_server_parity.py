#!/usr/bin/env python3
"""Capture every response the Pi web API gives, so a refactor can be proved harmless.

web_server.py held all of the read and command logic inline in its view functions. That
logic now lives in link_service.py so the Bluetooth link can share it, which means the
routes had to be rewritten as thin adapters. Rewriting a working API is exactly the kind
of change that silently alters a status code or a body, so this script dumps the whole
surface as canonical JSON:

    python3 test_web_server_parity.py before.json     # on the old code
    python3 test_web_server_parity.py after.json      # on the new code
    # then diff before.json after.json

A fresh app and a fresh server per case, so one case cannot colour another. Failures are
recorded rather than raised, so a case that raises still compares equal to itself.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Deterministic environment: a fixed token, and a secret key from the environment so
# nothing is written into the repo's data/ directory.
os.environ['MX5_WEB_TOKEN'] = 'parity-token'
os.environ['MX5_WEB_SECRET_KEY'] = 'parity-secret-key'

# Importing this stubs roof_controller, so no serial port is opened. It must come before
# web_server, which imports RoofController from that module.
from test_link_protocol import FakeDisplayApp  # noqa: E402

from web_server import WebRemoteServer  # noqa: E402

AUTH = {'Authorization': 'Bearer parity-token'}
NOAUTH = {}


def _no_esp32(app):
    app.esp32_handler = None


def _slept(app):
    app.sleeping = True


def _last_screen(app):
    app.current_screen = 7


# name, method, path, transport kwargs, app preparation
CASES = [
    ('status', 'get', '/api/status', {}, None),
    ('telemetry', 'get', '/api/telemetry', {}, None),

    ('screen_0', 'post', '/api/screen/0', {}, None),
    ('screen_3', 'post', '/api/screen/3', {}, None),
    ('screen_7', 'post', '/api/screen/7', {}, None),
    ('screen_8_rejected', 'post', '/api/screen/8', {}, None),
    ('screen_99_rejected', 'post', '/api/screen/99', {}, None),
    ('screen_minus1_rejected', 'post', '/api/screen/-1', {}, None),
    ('screen_next', 'post', '/api/screen/next', {}, None),
    ('screen_next_wraps', 'post', '/api/screen/next', {}, _last_screen),
    ('screen_prev', 'post', '/api/screen/prev', {}, None),

    ('wake_awake', 'post', '/api/wake', {}, None),
    ('wake_sleeping', 'post', '/api/wake', {}, _slept),

    ('imu_ok', 'post', '/api/calibrate_imu', {}, None),
    ('imu_no_esp32', 'post', '/api/calibrate_imu', {}, _no_esp32),

    ('roof_status', 'get', '/api/roof/status', {}, None),
    ('roof_speed', 'post', '/api/roof/speed', {'json': {'value': 25}}, None),
    ('roof_speed_zero', 'post', '/api/roof/speed', {'json': {'value': 0}}, None),
    ('roof_auto_on', 'post', '/api/roof/auto', {'json': {'value': 1}}, None),
    ('roof_auto_off', 'post', '/api/roof/auto', {'json': {'value': 0}}, None),
    ('roof_mode_valet', 'post', '/api/roof/mode', {'json': {'value': 0}}, None),
    ('roof_mode_oem', 'post', '/api/roof/mode', {'json': {'value': 2}}, None),
    ('roof_speed_missing', 'post', '/api/roof/speed', {'json': {}}, None),
    ('roof_speed_null', 'post', '/api/roof/speed', {'json': {'value': None}}, None),

    ('auth_missing', 'get', '/api/status', {}, None),
    ('auth_wrong', 'get', '/api/status', {}, None),

    ('index_page', 'get', '/', {}, None),
]

# Settings, each as its own case, plus the two rejection paths.
SETTINGS = [
    ('demo_mode', '1'),
    ('brightness', 55),
    ('volume', 40),
    ('shift_rpm', 6800),
    ('redline_rpm', 7500),
    ('use_mph', '0'),
    ('tire_low_psi', 27.5),
    ('tire_high_psi', 38),
    ('coolant_warn', 210),
    ('led_sequence', 3),
    ('clutch_display_mode', 2),
    ('unknown_setting', 1),
]
for _name, _value in SETTINGS:
    CASES.append(('setting_' + _name, 'post', '/api/settings/update',
                  {'json': {'name': _name, 'value': _value}}, None))
CASES.append(('setting_missing_name', 'post', '/api/settings/update',
              {'json': {'value': 1}}, None))


def run_case(name, method, path, kwargs, prep):
    """One request against a fresh app and server. Never raises."""
    app = FakeDisplayApp()
    if prep:
        prep(app)
    if name == 'auth_missing':
        headers = NOAUTH
    elif name == 'auth_wrong':
        headers = {'Authorization': 'Bearer not-the-token'}
    else:
        headers = AUTH

    try:
        server = WebRemoteServer(app)
        client = server.app.test_client()
        resp = getattr(client, method)(path, headers=headers, **kwargs)
        # Works against both the old layout (roof directly on the server) and the new
        # one (roof owned by the shared service behind server.link), so the same script
        # can capture the baseline and the refactored run.
        roof = getattr(getattr(server, 'link', None), 'roof', None)
        if roof is None:
            roof = getattr(server, 'roof', None)
        return {
            'status': resp.status_code,
            'body': resp.get_json(silent=True),
            # Effects, not just replies: a refactor can return the right JSON while
            # failing to actually apply the change.
            'effects': {
                'current_screen': app.current_screen,
                'sleeping': app.sleeping,
                'settings': vars(app.settings),
                'volume_set': app.sound.volume_set,
                'esp32_syncs': app.esp32_syncs,
                'led_sends': app.led_sends,
                'data_source_inits': app.data_source_inits,
                'imu_calibrations': app.esp32_handler.calibrated if app.esp32_handler else None,
                'roof_calls': list(roof.calls) if roof is not None else None,
                'roof_state': dict(roof.state) if roof is not None else None,
            },
        }
    except Exception as e:
        return {'error': '%s: %s' % (type(e).__name__, e)}


def main():
    result = {}
    for name, method, path, kwargs, prep in CASES:
        result[name] = run_case(name, method, path, kwargs, prep)

    text = json.dumps(result, indent=2, sort_keys=True, default=str)
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'w') as f:
            f.write(text + '\n')
        print("wrote %s (%d cases)" % (sys.argv[1], len(result)))
    else:
        print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
