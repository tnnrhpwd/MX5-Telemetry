#!/usr/bin/env python3
"""Desk test for the Bluetooth link protocol, with no Bluetooth involved.

The point of splitting link_protocol.py out of any transport is that it can be driven
here with a fake display app and a byte stream, which is the only way to check this
without a Pi, a paired phone, and a car. It runs as a plain script and under pytest:

    python3 test_link_protocol.py
    pytest test_link_protocol.py

pyserial is stubbed out because roof_controller imports it and the roof hardware is not
what is under test here.
"""

import json
import logging
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# -- stub the roof controller so this imports on a machine without pyserial -----

class _FakeRoofControllerError(Exception):
    pass


class _FakeRoofController:
    """Records what was asked of it; no serial port is opened."""

    def __init__(self):
        self.calls = []
        self.fail_with = None
        self.released = False
        self.state = {'mode': 1, 'auto': 0, 'speed_limit': 30, 'version': '44'}

    def status(self):
        self._guard()
        if self.fail_with:
            raise _FakeRoofControllerError(self.fail_with)
        info = dict(self.state)
        info['released'] = self.released
        return info

    def connect(self):
        self.calls.append(('connect',))
        self.released = False
        return self.status()

    def disconnect(self):
        self.calls.append(('disconnect',))
        self.released = True

    def set_speed(self, v):
        self._guard()
        self.calls.append(('speed', v))
        self.state['speed_limit'] = v

    def set_auto(self, v):
        self._guard()
        self.calls.append(('auto', v))
        self.state['auto'] = v

    def set_mode(self, v):
        self._guard()
        self.calls.append(('mode', v))
        self.state['mode'] = v

    def _guard(self):
        """Mirrors the driver: a released module refuses without being touched."""
        if self.released:
            raise _FakeRoofControllerError('roof controller released')


_roof_module = types.ModuleType('roof_controller')
_roof_module.RoofController = _FakeRoofController
_roof_module.RoofControllerError = _FakeRoofControllerError
sys.modules['roof_controller'] = _roof_module

from link_protocol import LinkProtocol, LinkSession, MAX_AUTH_FAILURES  # noqa: E402
from link_service import LinkService  # noqa: E402


# -- fake display app ---------------------------------------------------------

class FakeTelemetry:
    """Mirrors TelemetryData: real attributes, all zeroed."""

    def __init__(self):
        self.rpm = 0
        self.speed_kmh = 0.0
        self.gear = 0
        self.gear_estimated = True
        self.clutch_engaged = False
        self.recommended_gear = 1
        self.gear_color = 'green'
        self.is_in_neutral = True
        self.is_in_reverse = False
        self.throttle_percent = 0.0
        self.brake_percent = 0.0
        self.coolant_temp_f = 90
        self.intake_temp_f = 41
        self.ambient_temp_f = 41
        self.maf = 0.0
        self.fuel_level_percent = 0.0
        self.voltage = 0.0
        self.tire_pressure = [0.0, 0.0, 0.0, 0.0]
        self.tire_temp = [0.0, 0.0, 0.0, 0.0]
        self.tpms_last_update_str = ['waiting', 'waiting', 'waiting', 'waiting']
        self.tpms_connected = False
        self.g_lateral = 0.0
        self.g_longitudinal = 0.0
        self.lap_time_ms = 0
        self.best_lap_ms = 0
        self.instant_mpg = 0.0
        self.average_mpg = 0.0
        self.range_miles = 0
        self.check_engine_light = False
        self.abs_warning = False
        self.traction_control_off = False
        self.traction_control_active = False
        self.oil_status = False
        self.battery_warning = False
        self.door_ajar = False
        self.seatbelt_warning = False
        self.airbag_warning = False
        self.brake_warning = False
        self.high_beam_on = False
        self.fog_light_on = False
        self.headlights_on = False
        self.high_beams_on = False
        self.dtc_codes = []
        self.dtc_count = 0
        self.wheel_slip = [0.0, 0.0, 0.0, 0.0]


class FakeSettings:
    def __init__(self):
        self.demo_mode = False
        self.brightness = 80
        self.volume = 70
        self.shift_rpm = 6500
        self.redline_rpm = 7200
        self.use_mph = True
        self.tire_low_psi = 28.0
        self.tire_high_psi = 36.0
        self.coolant_warn_f = 220
        self.led_sequence = 1
        self.clutch_display_mode = 0


class FakeSwc:
    nav_locked = False


class FakeSound:
    def __init__(self):
        self.volume_set = []

    def set_volume(self, v):
        self.volume_set.append(v)


class FakeEsp32:
    def __init__(self):
        self.calibrated = 0

    def send_calibrate_imu(self):
        self.calibrated += 1


class FakeDisplayApp:
    def __init__(self):
        self.screen_names = ['Overview', 'RPM', 'TPMS', 'Engine',
                             'G-Force', 'Diagnostics', 'System', 'Settings']
        self.current_screen = 0
        self.sleeping = False
        self.last_activity = 0.0
        self.telemetry = FakeTelemetry()
        self.settings = FakeSettings()
        self.swc_handler = FakeSwc()
        self.sound = FakeSound()
        self.esp32_handler = FakeEsp32()
        self.can_handler = object()
        self.screen_changes = []
        self.data_source_inits = 0
        self.esp32_syncs = 0
        self.led_sends = 0

    def change_screen(self, n):
        self.current_screen = n
        self.screen_changes.append(n)

    def _init_data_sources(self):
        self.data_source_inits += 1

    def _sync_settings_to_esp32(self):
        self.esp32_syncs += 1

    def _send_led_sequence_to_arduino(self):
        self.led_sends += 1


TOKEN = 'test-token-abc123'


def build():
    """A fresh app, service, protocol and session for one test."""
    app = FakeDisplayApp()
    service = LinkService(app)
    protocol = LinkProtocol(service, token=TOKEN)
    return app, service, protocol, LinkSession(protocol)


def ask(session, **request):
    """Feed one request, return the single parsed reply."""
    line = json.dumps(request) + '\n'
    replies = session.feed(line.encode())
    assert len(replies) == 1, "expected exactly one reply, got %r" % (replies,)
    return json.loads(replies[0])


def hello(session, token=TOKEN):
    return ask(session, id=1, op='hello', token=token)


# -- authentication ----------------------------------------------------------

def test_hello_with_the_right_token_authenticates():
    _, _, _, session = build()
    reply = hello(session)
    assert reply['ok'] is True, reply
    assert reply['data']['authenticated'] is True


def test_hello_with_a_bad_token_is_refused():
    _, _, _, session = build()
    reply = hello(session, token='wrong')
    assert reply['ok'] is False
    assert 'token' in reply['error'].lower()


def test_ops_before_hello_are_refused():
    _, _, _, session = build()
    reply = ask(session, id=2, op='telemetry')
    assert reply['ok'] is False
    assert 'authenticated' in reply['error'].lower()


def test_the_id_is_echoed_so_a_client_can_match_replies():
    _, _, _, session = build()
    hello(session)
    assert ask(session, id=4242, op='ping')['id'] == 4242


def test_enough_bad_tokens_closes_the_link():
    _, _, _, session = build()
    for i in range(MAX_AUTH_FAILURES):
        assert hello(session, token='nope')['ok'] is False
    assert session.closed is True
    assert 'authentication' in session.close_reason.lower()


# -- reads -------------------------------------------------------------------

def test_telemetry_returns_the_full_snapshot():
    app, _, _, session = build()
    hello(session)
    app.telemetry.rpm = 3200
    app.telemetry.coolant_temp_f = 190
    app.telemetry.tire_pressure = [30.5, 31.0, 29.5, 30.0]

    data = ask(session, id=3, op='telemetry')['data']
    assert data['rpm'] == 3200
    assert data['coolant_temp_f'] == 190
    assert data['tire_pressure'] == [30.5, 31.0, 29.5, 30.0]
    # The fields the car app's screens rely on must all be present.
    for key in ('speed_kmh', 'gear', 'g_lateral', 'voltage', 'can_connected',
                'dtc_count', 'gear_color', 'tpms_last_update_str', 'demo_mode'):
        assert key in data, "missing %r" % key
    assert data['can_connected'] is True


def test_status_returns_the_settings_block():
    _, _, _, session = build()
    hello(session)
    data = ask(session, id=4, op='status')['data']
    assert data['screen'] == 0
    assert data['screen_name'] == 'Overview'
    for key in ('demo_mode', 'brightness', 'volume', 'shift_rpm', 'redline_rpm',
                'use_mph', 'tire_low_psi', 'tire_high_psi', 'coolant_warn_f',
                'led_sequence', 'clutch_display_mode'):
        assert key in data['settings'], "missing setting %r" % key


# -- display and settings ----------------------------------------------------

def test_screen_selects_a_page():
    app, _, _, session = build()
    hello(session)
    assert ask(session, id=5, op='screen', value=3)['data']['screen'] == 3
    assert app.current_screen == 3


def test_screen_rejects_an_out_of_range_page():
    app, _, _, session = build()
    hello(session)
    reply = ask(session, id=6, op='screen', value=99)
    assert reply['ok'] is True            # the link worked...
    assert reply['data']['success'] is False   # ...the command did not
    assert app.current_screen == 0        # and nothing moved


def test_screen_next_wraps_past_the_last_page():
    app, _, _, session = build()
    hello(session)
    app.current_screen = 7
    assert ask(session, id=7, op='screen.next')['data']['screen'] == 0


def test_screen_prev_wraps_before_the_first_page():
    app, _, _, session = build()
    hello(session)
    app.current_screen = 0
    assert ask(session, id=8, op='screen.prev')['data']['screen'] == 7


def test_setting_applies_and_is_visible_in_status():
    app, _, _, session = build()
    hello(session)
    reply = ask(session, id=9, op='setting', name='shift_rpm', value=6800)
    assert reply['data']['success'] is True
    assert app.settings.shift_rpm == 6800
    assert ask(session, id=10, op='status')['data']['settings']['shift_rpm'] == 6800


def test_setting_accepts_a_string_number_and_coerces_it():
    app, _, _, session = build()
    hello(session)
    assert ask(session, id=11, op='setting', name='brightness', value='55')['data']['success']
    assert app.settings.brightness == 55


def test_volume_setting_reaches_the_sound_object():
    app, _, _, session = build()
    hello(session)
    ask(session, id=12, op='setting', name='volume', value=40)
    assert app.sound.volume_set == [40]


def test_led_sequence_setting_pushes_to_the_arduino():
    app, _, _, session = build()
    hello(session)
    ask(session, id=13, op='setting', name='led_sequence', value=3)
    assert app.settings.led_sequence == 3
    assert app.led_sends == 1


def test_demo_mode_setting_reinitialises_the_data_sources():
    app, _, _, session = build()
    hello(session)
    ask(session, id=14, op='setting', name='demo_mode', value='1')
    assert app.settings.demo_mode is True
    assert app.data_source_inits == 1


def test_settings_are_synced_to_the_esp32():
    app, _, _, session = build()
    hello(session)
    ask(session, id=15, op='setting', name='redline_rpm', value=7500)
    assert app.esp32_syncs == 1


def test_unknown_setting_is_refused_without_crashing():
    _, _, _, session = build()
    hello(session)
    reply = ask(session, id=16, op='setting', name='nonsense', value=1)
    assert reply['data']['success'] is False
    assert 'Unknown setting' in reply['data']['error']


def test_missing_setting_name_is_refused():
    _, _, _, session = build()
    hello(session)
    assert ask(session, id=17, op='setting', value=1)['data']['success'] is False


def test_wake_clears_sleep_and_stamps_activity():
    app, _, _, session = build()
    hello(session)
    app.sleeping = True
    ask(session, id=18, op='wake')
    assert app.sleeping is False
    assert app.last_activity > 0


def test_sleep_sets_the_flag():
    app, _, _, session = build()
    hello(session)
    ask(session, id=19, op='sleep')
    assert app.sleeping is True


def test_calibrate_imu_reaches_the_esp32():
    app, _, _, session = build()
    hello(session)
    reply = ask(session, id=20, op='calibrate_imu')
    assert reply['data']['success'] is True
    assert app.esp32_handler.calibrated == 1


def test_calibrate_imu_reports_a_missing_esp32():
    app, _, _, session = build()
    hello(session)
    app.esp32_handler = None
    reply = ask(session, id=21, op='calibrate_imu')
    assert reply['data']['success'] is False
    assert 'ESP32' in reply['data']['message']


# -- roof controller ---------------------------------------------------------

def test_roof_status_is_reported():
    _, _, _, session = build()
    hello(session)
    data = ask(session, id=22, op='roof.status')['data']
    assert data['connected'] is True
    assert data['mode'] == 1


def test_roof_mode_command_reaches_the_controller():
    _, service, _, session = build()
    hello(session)
    reply = ask(session, id=23, op='roof.mode', value=2)
    assert reply['data']['success'] is True
    assert ('mode', 2) in service.roof.calls
    assert reply['data']['roof']['mode'] == 2


def test_roof_disconnect_is_reported_not_raised():
    _, service, _, session = build()
    hello(session)
    service.roof.fail_with = 'No roof controller on /dev/ttyACM0'
    data = ask(session, id=24, op='roof.status')['data']
    assert data['connected'] is False
    assert 'ttyACM0' in data['error']


def test_roof_disconnect_hands_the_module_back():
    _, service, _, session = build()
    hello(session)
    reply = ask(session, id=25, op='roof.disconnect')
    assert reply['data']['success'] is True
    assert service.roof.released is True
    assert reply['data']['roof']['connected'] is False
    assert reply['data']['roof']['released'] is True


def test_roof_connect_claims_the_module_again():
    _, service, _, session = build()
    hello(session)
    ask(session, id=26, op='roof.disconnect')
    reply = ask(session, id=27, op='roof.connect')
    assert reply['data']['success'] is True
    assert service.roof.released is False
    assert reply['data']['roof']['connected'] is True
    assert reply['data']['roof']['mode'] == 1


def test_released_roof_refuses_commands_without_touching_it():
    _, service, _, session = build()
    hello(session)
    ask(session, id=28, op='roof.disconnect')
    before = list(service.roof.calls)
    reply = ask(session, id=29, op='roof.mode', value=0)
    assert reply['data']['success'] is False
    assert service.roof.calls == before


# -- framing and robustness --------------------------------------------------

def test_two_requests_in_one_chunk_both_get_replies():
    _, _, _, session = build()
    hello(session)
    chunk = (json.dumps({'id': 30, 'op': 'ping'}) + '\n'
             + json.dumps({'id': 31, 'op': 'ping'}) + '\n')
    replies = [json.loads(r) for r in session.feed(chunk.encode())]
    assert [r['id'] for r in replies] == [30, 31]


def test_a_request_split_across_chunks_is_reassembled():
    """This is the case BLE depends on: one line arriving as several writes."""
    _, _, _, session = build()
    hello(session)
    line = json.dumps({'id': 32, 'op': 'telemetry'}) + '\n'

    # Dribble it in one byte at a time, the way a chunked characteristic would.
    replies = []
    for i in range(len(line)):
        replies.extend(session.feed(line[i:i + 1].encode()))

    assert len(replies) == 1, "expected one reply after the newline, got %r" % (replies,)
    assert json.loads(replies[0])['id'] == 32


def test_crlf_line_endings_are_tolerated():
    _, _, _, session = build()
    hello(session)
    replies = session.feed(b'{"id":33,"op":"ping"}\r\n')
    assert json.loads(replies[0])['id'] == 33


def test_malformed_json_gets_an_error_not_a_dropped_link():
    _, _, _, session = build()
    hello(session)
    replies = session.feed(b'this is not json\n')
    reply = json.loads(replies[0])
    assert reply['ok'] is False
    assert 'JSON' in reply['error']
    assert session.closed is False
    # and the link still works afterwards
    assert ask(session, id=34, op='ping')['ok'] is True


def test_an_oversized_line_is_rejected_without_closing_the_link():
    _, _, _, session = build()
    hello(session)
    session.feed(b'x' * 20000 + b'\n')
    assert session.closed is False
    assert ask(session, id=35, op='ping')['ok'] is True


def test_unknown_op_is_reported():
    _, _, _, session = build()
    hello(session)
    reply = ask(session, id=36, op='does.not.exist')
    assert reply['ok'] is False
    assert 'Unknown op' in reply['error']


def test_missing_op_is_reported():
    _, _, _, session = build()
    hello(session)
    assert ask(session, id=37)['ok'] is False


def test_blank_lines_are_ignored():
    _, _, _, session = build()
    hello(session)
    assert session.feed(b'\n') == []


def test_a_service_level_failure_comes_back_readable():
    """A command that blows up must be reportable, not fatal.

    LinkService already catches this class of failure and turns it into
    {'success': False}, so the failure shows up inside an ok reply rather than as a
    transport error. Either shape is fine; what matters is that the client can read it
    and the session survives it.
    """
    app, _, _, session = build()
    hello(session)

    def boom(*_a, **_k):
        raise RuntimeError('exploded')

    app._sync_settings_to_esp32 = boom
    reply = ask(session, id=38, op='setting', name='brightness', value=50)
    assert reply['ok'] is True
    assert reply['data']['success'] is False
    assert 'Internal error' in reply['data']['error']
    assert session.closed is False
    assert ask(session, id=39, op='ping')['ok'] is True


def test_an_exception_escaping_the_service_still_replies():
    """The protocol's own handler is the backstop for anything the service does not catch."""
    app, _, _, session = build()
    hello(session)

    def boom(_n):
        raise RuntimeError('screen change exploded')

    # set_screen has no try/except of its own, so this escapes into the protocol's
    # handler rather than being folded into {'success': False} like a rejected setting.
    app.change_screen = boom
    reply = ask(session, id=40, op='screen', value=2)
    assert reply['ok'] is False
    assert 'exploded' in reply['error']
    assert reply['id'] == 40      # the id still comes back, so the client can match it
    assert session.closed is False
    assert ask(session, id=41, op='ping')['ok'] is True


def test_token_can_be_required_or_not():
    """require_token=False is for a bench test over a trusted pipe."""
    app = FakeDisplayApp()
    protocol = LinkProtocol(LinkService(app), token=None, require_token=False)
    session = LinkSession(protocol)
    assert json.loads(session.feed(b'{"id":1,"op":"ping"}\n')[0])['ok'] is True


# -- the SPP server, over an injected TCP listener ---------------------------

def _spp_over_tcp(**kwargs):
    """Start an SppServer on a local TCP socket. Returns (server, app, service, port).

    SppServer takes an injectable listener precisely so this is possible: the accept,
    serve and pump loop is the same code the Pi runs, but the socket is TCP rather than
    RFCOMM, so it can be exercised with no Bluetooth stack anywhere.
    """
    import socket as _socket
    from bt_spp_server import SppServer

    app = FakeDisplayApp()
    service = LinkService(app)

    listener = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    listener.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
    listener.bind(('127.0.0.1', 0))
    listener.listen(2)
    port = listener.getsockname()[1]

    server = SppServer(service, token=TOKEN, listener=listener, publish_sdp=False, **kwargs)
    server.start()
    return server, app, service, port


def _connect(port):
    import socket as _socket
    conn = _socket.create_connection(('127.0.0.1', port), timeout=5)
    conn.settimeout(5)
    return conn, conn.makefile('rwb')


def _close_peer(conn, f):
    """Release a peer completely.

    socket.makefile() holds its own reference to the socket, so conn.close() alone does
    NOT close the underlying fd and the server never sees EOF: it sits in recv() forever
    and never comes back round to accept() the next peer. Closing the file object first
    is what actually drops the connection.
    """
    try:
        f.close()
    except OSError:
        pass
    try:
        conn.close()
    except OSError:
        pass


def _rpc(f, **request):
    f.write(json.dumps(request).encode() + b'\n')
    f.flush()
    line = f.readline()
    assert line, "no reply for %r" % (request,)
    return json.loads(line.decode())


def test_spp_server_serves_a_client_end_to_end():
    server, app, _, port = _spp_over_tcp()
    try:
        conn, f = _connect(port)
        try:
            assert _rpc(f, id=1, op='hello', token=TOKEN)['ok'] is True

            app.telemetry.rpm = 4321
            assert _rpc(f, id=2, op='telemetry')['data']['rpm'] == 4321

            assert _rpc(f, id=3, op='screen', value=4)['data']['screen'] == 4
            assert app.current_screen == 4

            # A rejected command still round-trips rather than dropping the link.
            reply = _rpc(f, id=4, op='setting', name='nonsense', value=1)
            assert reply['data']['success'] is False
            assert _rpc(f, id=5, op='ping')['ok'] is True
        finally:
            _close_peer(conn, f)
    finally:
        server.stop()


def test_spp_server_refuses_commands_before_hello():
    server, app, _, port = _spp_over_tcp()
    try:
        conn, f = _connect(port)
        try:
            reply = _rpc(f, id=1, op='telemetry')
            assert reply['ok'] is False
            assert 'authenticated' in reply['error'].lower()
        finally:
            _close_peer(conn, f)
    finally:
        server.stop()


def test_spp_server_resets_the_session_between_peers():
    """A second phone must not inherit the first one's login."""
    server, app, _, port = _spp_over_tcp()
    try:
        conn1, f1 = _connect(port)
        assert _rpc(f1, id=1, op='hello', token=TOKEN)['ok'] is True
        assert _rpc(f1, id=2, op='ping')['ok'] is True
        # Released properly, or the server sits in recv() on peer 1 for ever.
        _close_peer(conn1, f1)

        conn2, f2 = _connect(port)
        try:
            reply = _rpc(f2, id=3, op='ping')
            assert reply['ok'] is False, "peer 2 inherited peer 1's session"
            assert _rpc(f2, id=4, op='hello', token=TOKEN)['ok'] is True
            assert _rpc(f2, id=5, op='ping')['ok'] is True
        finally:
            _close_peer(conn2, f2)
    finally:
        server.stop()


def test_spp_server_rejects_a_bad_token_and_drops_the_peer():
    server, app, _, port = _spp_over_tcp()
    try:
        conn, f = _connect(port)
        try:
            for i in range(MAX_AUTH_FAILURES):
                reply = _rpc(f, id=i, op='hello', token='wrong')
                assert reply['ok'] is False
            # The server closes the link; the next read returns EOF rather than a reply.
            assert f.readline() == b''
        finally:
            _close_peer(conn, f)
    finally:
        server.stop()


def test_spp_describe_reports_what_is_missing():
    """The diagnostics have to name the missing piece, not just fail to connect."""
    from bt_spp_server import SppServer
    server = SppServer(LinkService(FakeDisplayApp()), token=TOKEN, publish_sdp=False)
    info = server.describe()
    assert info['transport'] == 'spp'
    assert info['uuid'] == '00001101-0000-1000-8000-00805F9B34FB'
    assert 'sdptool' in info and 'af_bluetooth' in info


# -- the manager, and what it does when Bluetooth is missing -----------------

def test_bt_link_reports_missing_transports_without_raising():
    """The whole point of BtLink: a missing transport is reported, not fatal.

    This machine has no Bluetooth stack at all, which is the worst case, so this also
    checks the two failures that are most likely on a real Pi: no AF_BLUETOOTH, and bless
    not installed.
    """
    from bt_link import BtLink

    link = BtLink(LinkService(FakeDisplayApp()), mode='both', token=TOKEN)
    assert link.enabled is True

    started = link.start()          # must not raise, whatever is missing
    if not started:
        assert link.errors, "failed to start but reported no reason"
        for name, message in link.errors.items():
            assert message, "transport %r failed with an empty message" % name

    status = link.status()
    assert status['mode'] == 'both'
    assert status['token_required'] is True
    link.stop()


def test_bt_link_can_be_turned_off():
    from bt_link import BtLink

    link = BtLink(LinkService(FakeDisplayApp()), mode='off')
    assert link.enabled is False
    assert link.start() is False
    assert link.errors == {}


def test_bt_link_falls_back_on_an_unknown_mode():
    from bt_link import BtLink

    link = BtLink(LinkService(FakeDisplayApp()), mode='nonsense')
    assert link.mode == 'both'
    link.stop()


def test_bt_link_takes_the_web_token_when_none_is_given(monkeypatch=None):
    """One secret for both transports: the BT link defaults to MX5_WEB_TOKEN."""
    import os
    from bt_link import BtLink

    saved = os.environ.get('MX5_WEB_TOKEN')
    saved_bt = os.environ.get('MX5_BT_TOKEN')
    try:
        os.environ['MX5_WEB_TOKEN'] = 'shared-secret'
        os.environ.pop('MX5_BT_TOKEN', None)
        link = BtLink(LinkService(FakeDisplayApp()))
        assert link.token == 'shared-secret'
        assert link.require_token is True
    finally:
        if saved is None:
            os.environ.pop('MX5_WEB_TOKEN', None)
        else:
            os.environ['MX5_WEB_TOKEN'] = saved
        if saved_bt is not None:
            os.environ['MX5_BT_TOKEN'] = saved_bt


def test_bt_link_refuses_to_start_without_a_token():
    """With no token the link would take commands from any paired device, so it stays shut.

    The web server's fail-safe cannot be reused here: it binds loopback-only, and a radio
    has no loopback. This pins both halves, because either alone would pass against a
    broken implementation: the refusal must fire with no token, AND the documented opt-out
    must still be able to switch it off on purpose.
    """
    import os
    from bt_link import BtLink

    keys = ('MX5_WEB_TOKEN', 'MX5_BT_TOKEN', 'MX5_BT_ALLOW_NO_TOKEN')
    saved = {k: os.environ.get(k) for k in keys}
    try:
        for k in keys:
            os.environ.pop(k, None)

        link = BtLink(LinkService(FakeDisplayApp()), mode='both')
        assert link.require_token is False
        assert link.refused_reason, "opened the link with no token and no complaint"
        assert link.start() is False
        assert link.status()['refused'] == link.refused_reason
        link.stop()

        # The opt-out has to work, or a bench test could never exercise the link.
        os.environ['MX5_BT_ALLOW_NO_TOKEN'] = '1'
        allowed = BtLink(LinkService(FakeDisplayApp()), mode='both')
        assert allowed.refused_reason is None
        assert allowed.require_token is False
        allowed.stop()

        # With no transports enabled there is nothing to guard, so it must not refuse.
        off = BtLink(LinkService(FakeDisplayApp()), mode='off')
        assert off.refused_reason is None
        off.stop()

        # And a token clears it with no opt-out needed.
        os.environ['MX5_WEB_TOKEN'] = 'shared-secret'
        tokened = BtLink(LinkService(FakeDisplayApp()), mode='both')
        assert tokened.refused_reason is None
        assert tokened.require_token is True
        tokened.stop()
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# -- runner ------------------------------------------------------------------

def main():
    # Deliberate-failure tests log tracebacks through logging; keep the output readable.
    logging.disable(logging.CRITICAL)
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith('test_') and callable(f)]
    failures = []
    for name, fn in tests:
        try:
            fn()
            print("  PASS  %s" % name)
        except Exception as e:
            failures.append((name, e))
            print("  FAIL  %s: %s: %s" % (name, type(e).__name__, e))

    print("\n%d/%d passed" % (len(tests) - len(failures), len(tests)))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
