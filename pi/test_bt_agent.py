#!/usr/bin/env python3
"""Desk test for mx5-bt-agent, with no D-Bus and no Bluetooth.

The agent is the thing that keeps a phone *able* to reconnect: it holds the adapter class,
auto-accepts pairing, republishes the SPP record when bluetoothd forgets it, and restarts
the display app only when the BLE advertisement it should be running has gone. Every one of
those decisions is a judgement about state it can only partly see, so the judgements are
worth pinning down: getting one wrong either leaves the link dead or drops a link that was
working.

Runs as a plain script and under pytest:

    python3 test_bt_agent.py
    pytest test_bt_agent.py
"""

import importlib.util
import os
import subprocess
import sys
import types

PI_DIR = os.path.dirname(os.path.abspath(__file__))
AGENT_PATH = os.path.join(PI_DIR, 'mx5-bt-agent.py')


# -- load the agent with dbus stubbed out -------------------------------------

def _load_agent():
    """Import mx5-bt-agent.py from its path, with the D-Bus imports faked.

    The module is a script rather than a package module, so it has no importable name, and
    `dbus` is a Pi-only dependency that is not part of what this test is about.
    """

    class _DBusException(Exception):
        """Its own type on purpose: the real one is not Exception, and code that catches
        it must not swallow unrelated AttributeErrors."""

    dbus = types.ModuleType('dbus')
    dbus.exceptions = types.SimpleNamespace(DBusException=_DBusException)
    dbus.String = str          # real dbus-python marshals str as 's'; this is its name
    dbus.service = types.ModuleType('dbus.service')
    dbus.service.Object = type('Object', (), {'__init__': lambda self, *a, **k: None})
    dbus.service.method = lambda *a, **k: (lambda fn: fn)
    dbus.Interface = lambda *a, **k: None
    glib = types.ModuleType('dbus.mainloop.glib')
    glib.DBusGMainLoop = lambda **k: None
    mainloop = types.ModuleType('dbus.mainloop')

    saved = {name: sys.modules.get(name)
             for name in ('dbus', 'dbus.service', 'dbus.mainloop',
                          'dbus.mainloop.glib')}
    sys.modules['dbus'] = dbus
    sys.modules['dbus.service'] = dbus.service
    sys.modules['dbus.mainloop'] = mainloop
    sys.modules['dbus.mainloop.glib'] = glib
    try:
        spec = importlib.util.spec_from_file_location('mx5_bt_agent', AGENT_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, original in saved.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


class _Result:
    """Stands in for subprocess.CompletedProcess."""

    def __init__(self, stdout='', stderr='', returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class _Subprocess:
    """A stand-in for the subprocess module.

    Swapped in wholesale rather than patching subprocess.run on the real module, because
    that would leak into every other test in the process - and this file has six of them.
    """

    DEVNULL = subprocess.DEVNULL
    PIPE = subprocess.PIPE
    SubprocessError = subprocess.SubprocessError

    def __init__(self, run=None, call=None, result=None):
        self._run = run
        self._call = call
        self._result = result if result is not None else _Result()
        self.calls = []

    def run(self, args, *a, **k):
        self.calls.append(args)
        if self._run is not None:
            return self._run(args, *a, **k)
        return self._result

    def call(self, args, *a, **k):
        self.calls.append(args)
        if self._call is not None:
            return self._call(args, *a, **k)
        return 0

    def check_output(self, args, *a, **k):
        self.calls.append(args)
        return b''

    def Popen(self, *a, **k):
        return None


def _agent(run=None, call=None, **result):
    """A fresh agent module with subprocess replaced, and the app 'running'."""
    agent = _load_agent()
    agent.subprocess = _Subprocess(run=run, call=call, result=_Result(**result))
    agent.display_is_active = lambda: True
    agent._calls = agent.subprocess.calls
    return agent


# -- what the running app was configured to do -------------------------------

def test_transport_mode_defaults_to_both():
    agent = _load_agent()
    assert agent.transport_mode({}) == 'both'


def test_transport_mode_is_read_from_the_running_process():
    agent = _load_agent()
    assert agent.transport_mode({'MX5_BT': 'SPP'}) == 'spp'
    assert agent.transport_mode({'MX5_BT': 'ble'}) == 'ble'


def test_an_unknown_transport_mode_is_treated_as_both():
    agent = _load_agent()
    assert agent.transport_mode({'MX5_BT': 'nonsense'}) == 'both'


def test_spp_channel_defaults_and_survives_a_bad_value():
    agent = _load_agent()
    assert agent.spp_channel({}) == 3
    assert agent.spp_channel({'MX5_BT_SPP_CHANNEL': '7'}) == 7
    assert agent.spp_channel({'MX5_BT_SPP_CHANNEL': 'x'}) == 3


# -- reading the SDP server: three answers, not two ---------------------------

def test_a_published_record_is_present():
    agent = _agent(stdout='Service Name: Serial Port\n'
                          '  Service Class ID List:\n    Serial Port\n'
                          '  00001101-0000-1000-8000-00805f9b34fb\n')
    assert agent.sdp_record_present() is True


def test_a_reachable_server_with_no_record_is_missing():
    agent = _agent(stdout='Service Name: Something Else\n')
    assert agent.sdp_record_present() is False


def test_an_unreachable_server_is_unknown_rather_than_missing():
    agent = _agent(stderr='Failed to connect to SDP server on FF:FF:FF:FF:FF:FF: '
                          'No such file or directory')
    assert agent.sdp_record_present() is None


def test_a_missing_sdptool_is_unknown_rather_than_missing():
    def boom(*_a, **_k):
        raise OSError('no sdptool')

    agent = _agent(run=boom)
    assert agent.sdp_record_present() is None


# -- republishing the record --------------------------------------------------

def test_nothing_is_published_with_no_display_app():
    """A record with no listener behind it is worse than no record: it accepts and hangs."""
    agent = _agent()
    assert agent.ensure_sdp({}) is True
    assert agent._calls == []


def test_nothing_is_published_when_only_ble_is_configured():
    agent = _agent()
    assert agent.ensure_sdp({'MX5_BT': 'ble'}) is True
    assert agent._calls == []


def test_an_unreachable_sdp_server_is_reported_once_and_then_left_alone():
    """On an install with no SDP server, SPP cannot work at all and retrying is spam."""
    agent = _agent(stderr='Failed to connect to SDP server on FF:FF:FF:FF:FF:FF')
    env = {'MX5_BT': 'both'}
    assert agent.ensure_sdp(env) is False
    failed = agent._sdp['failed']
    assert failed == 1
    assert agent._sdp['retry_at'] > 0, 'no backoff was set'
    assert agent.ensure_sdp(env) is False
    assert agent._sdp['failed'] == failed, 'the backed-off check still ran'


def test_a_missing_record_is_republished_on_the_configured_channel():
    agent = _agent(stdout='Service Name: Something Else\n')
    env = {'MX5_BT': 'both', 'MX5_BT_SPP_CHANNEL': '5'}

    def adds():
        return [c for c in agent._calls if len(c) > 1 and c[1] == 'add']

    # One miss only schedules a recheck: `sdptool add` is asynchronous inside bluetoothd.
    assert agent.ensure_sdp(env) is False
    assert adds() == []

    assert agent.ensure_sdp(env) is True
    assert adds()[-1] == ['sdptool', 'add', '--channel=5', 'SP']
    assert agent._sdp['republished'] == 1


def test_a_failed_republish_backs_off_instead_of_shouting_every_minute():
    agent = _agent(run=lambda *_a, **_k: _Result(returncode=255, stderr='oops'))
    agent._sdp['missing'] = 1
    env = {'MX5_BT': 'both'}
    assert agent.ensure_sdp(env) is False
    assert agent._sdp['failed'] == 1
    assert agent._sdp['retry_at'] > 0


def test_a_restored_record_clears_the_backoff():
    agent = _agent(stdout='00001101-0000-1000-8000-00805f9b34fb\n')
    agent._sdp.update(missing=3, failed=2, retry_at=0.0)
    assert agent.ensure_sdp({'MX5_BT': 'both'}) is True
    assert agent._sdp['failed'] == 0
    assert agent._sdp['missing'] == 0


# -- the adapter class --------------------------------------------------------

class _Bus:
    """Enough of a system bus to get hold_class/hold_name to their property reads."""

    def __init__(self, current_class, current_alias=None):
        self.current_class = current_class
        self.current_alias = current_alias
        self.sets = []

    def get_object(self, *args):
        return object()

    def props(self):
        def get(_iface, prop):
            return self.current_alias if prop == 'Alias' else self.current_class

        def set_(_iface, prop, value):
            self.sets.append((prop, value))
            if prop == 'Alias':
                self.current_alias = value

        return types.SimpleNamespace(Get=get, Set=set_)


def _class_agent(current_class, alias=None, **kwargs):
    agent = _agent(**kwargs)
    bus = _Bus(current_class, alias)
    agent.dbus.Interface = lambda *_a, **_k: bus.props()
    return agent, bus


def test_a_missing_hciconfig_does_not_kill_the_watchdogs():
    """A timer callback that raises is removed for the life of the process.

    bluez-tools is not installed on every Pi, so hciconfig may be absent. Letting that
    propagate would silently stop the advertisement watchdog and the SDP republish too,
    and the link would then be unrecoverable without a service restart.
    """
    def missing(*_a, **_k):
        raise OSError('No such file or directory: hciconfig')

    agent, bus = _class_agent(0, call=missing)
    assert agent.hold_class(bus) is True, 'the tick would have died here'
    assert agent._calls and agent._calls[-1][0] == 'hciconfig'


def test_the_class_is_set_when_it_differs():
    agent, bus = _class_agent(0)
    agent.hold_class(bus)
    assert agent._calls[-1] == ['hciconfig', 'hci0', 'class', '0x%06x' % agent.WANT_CLASS]


def test_the_class_is_left_alone_when_it_is_already_right():
    wanted = _agent().WANT_CLASS
    agent, bus = _class_agent(wanted)
    agent.hold_class(bus)
    assert agent._calls == []


# -- the adapter name ---------------------------------------------------------

def _refusing_bus(agent, bus):
    """Make the bus refuse the alias write, as PolicyKit does for a non-root writer."""
    def refuse(_iface, _prop, _value):
        raise agent.dbus.exceptions.DBusException('PolicyKit says no')

    bus.props = lambda: types.SimpleNamespace(
        Get=lambda _i, prop: bus.current_alias if prop == 'Alias' else bus.current_class,
        Set=refuse)
    agent.dbus.Interface = lambda *_a, **_k: bus.props()


def test_the_name_is_set_when_it_has_reverted_to_the_hostname():
    """bluetoothd resets the alias to the hostname, and the phone then lists the Pi as
    "raspberrypi" - or with no name at all when the scan misses the response."""
    agent, bus = _class_agent(0x120103, alias='raspberrypi')
    agent.hold_name(bus)
    assert bus.sets == [('Alias', agent.WANT_NAME)]


def test_the_name_is_left_alone_when_it_is_already_right():
    wanted = _agent().WANT_NAME
    agent, bus = _class_agent(0x120103, alias=wanted)
    agent.hold_name(bus)
    assert bus.sets == []
    assert agent._calls == []


def test_a_failed_dbus_set_falls_back_to_bluetoothctl():
    agent, bus = _class_agent(0x120103, alias='raspberrypi')
    _refusing_bus(agent, bus)

    assert agent.hold_name(bus) is True, 'the tick would have died here'
    assert agent._calls[-1] == ['bluetoothctl', 'system-alias', agent.WANT_NAME]


def test_a_missing_bluetoothctl_does_not_kill_the_watchdogs():
    agent, bus = _class_agent(0x120103, alias='raspberrypi')
    _refusing_bus(agent, bus)

    def missing(*_a, **_k):
        raise OSError('No such file or directory: bluetoothctl')

    agent.subprocess.call = missing
    assert agent.hold_name(bus) is True, 'the tick would have died here'


# -- runner -------------------------------------------------------------------

def main():
    tests = [(name, fn) for name, fn in sorted(globals().items())
             if name.startswith('test_') and callable(fn)]
    failures = []
    for name, fn in tests:
        try:
            fn()
            print("  PASS  %s" % name)
        except Exception as e:
            failures.append(name)
            print("  FAIL  %s: %s: %s" % (name, type(e).__name__, e))
    print("\n%d/%d passed" % (len(tests) - len(failures), len(tests)))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.exit(main())
