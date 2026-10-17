#!/usr/bin/env python3
"""Desk test for the RCNC-2 driver, against a fake serial port.

The driver's whole promise is that it never leaves the port open, because a host
left attached to the module is what puts it into its USB state and stops the roof
working. That promise is a claim about open and close calls, so it is exactly the
thing a fake port can check and a car in a driveway cannot.

    python3 test_roof_controller.py
    pytest test_roof_controller.py

pyserial is not required: the port is stubbed below.
"""

import importlib.util
import os
import sys
import types

_HERE = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, _HERE)


class SerialException(Exception):
    """What serial.SerialException looks like to the driver."""


class FakeSerial:
    """Records every open and close, and answers one console reply per exchange."""

    handles = []
    reply = (b"=\r\nRCNC2 Software Version 44\r\nOne touch mode\r\n"
             b"Speed Limit(mph): 30, Auto: 1\r\n\r\n>")
    write_error = None
    open_error = None

    def __init__(self, port, baud, timeout=None):
        if FakeSerial.open_error:
            raise FakeSerial.open_error
        self.port = port
        self.baud = baud
        self.is_open = True
        self.written = []
        self._sent = False
        FakeSerial.handles.append(self)

    # -- the parts of serial.Serial the driver actually uses

    def reset_input_buffer(self):
        pass

    def write(self, data):
        if FakeSerial.write_error:
            raise FakeSerial.write_error
        self.written.append(data)

    def flush(self):
        pass

    def read(self, size):
        if self._sent:
            return b""
        self._sent = True
        return FakeSerial.reply

    def close(self):
        self.is_open = False


def _install_serial_stub():
    """Make ``import serial`` resolve to the fake, whatever is on this machine."""
    serial_module = types.ModuleType('serial')
    serial_module.Serial = FakeSerial
    serial_module.SerialException = SerialException

    list_ports = types.ModuleType('serial.tools.list_ports')
    list_ports.comports = lambda: []
    tools = types.ModuleType('serial.tools')
    tools.list_ports = list_ports

    sys.modules['serial'] = serial_module
    sys.modules['serial.tools'] = tools
    sys.modules['serial.tools.list_ports'] = list_ports


def _load_driver():
    """Load roof_controller from its file rather than by name.

    test_link_protocol stubs a module called ``roof_controller`` into sys.modules,
    so a plain import here would hand back that stub whenever the two run in one
    pytest process.
    """
    spec = importlib.util.spec_from_file_location(
        'roof_controller_under_test', os.path.join(_HERE, 'roof_controller.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_install_serial_stub()
driver = _load_driver()

PORT = '/dev/ttyACM0'


def reset():
    FakeSerial.handles = []
    FakeSerial.write_error = None
    FakeSerial.open_error = None


def controller():
    return driver.RoofController(port=PORT)


def refuses(roof, call):
    """Return the message from a control that was expected to be refused."""
    try:
        call()
    except driver.RoofControllerError as e:
        return str(e)
    raise AssertionError("expected RoofControllerError, got a result")


# -- the promise: no handle survives an exchange ------------------------------

def test_a_read_closes_the_port_before_returning():
    reset()
    info = controller().status()
    assert info['speed_limit'] == 30
    assert len(FakeSerial.handles) == 1
    assert FakeSerial.handles[0].is_open is False


def test_polling_never_leaves_a_port_open():
    """The regression this guards.

    The driver used to keep the first handle it opened, so the status poll from
    the phone held the module for as long as the Pi was powered. That is the
    state the vendor's guide says must not exist while the car is in use.
    """
    reset()
    roof = controller()
    for _ in range(4):
        roof.status()
    assert len(FakeSerial.handles) == 4
    assert all(h.is_open is False for h in FakeSerial.handles)


def test_setting_changes_close_the_port_too():
    reset()
    roof = controller()
    roof.set_speed(20)
    roof.set_mode(2)
    roof.set_auto(1)
    assert len(FakeSerial.handles) == 3
    assert all(h.is_open is False for h in FakeSerial.handles)
    assert FakeSerial.handles[0].written == [b's 20\n']


def test_a_write_failure_still_closes_the_port():
    reset()
    FakeSerial.write_error = SerialException('cable pulled')
    roof = controller()
    message = refuses(roof, roof.status)
    assert 'write failed' in message
    assert len(FakeSerial.handles) == 1
    assert FakeSerial.handles[0].is_open is False


# -- releasing the module -----------------------------------------------------

def test_disconnect_stops_touching_the_module_entirely():
    reset()
    roof = controller()
    roof.status()
    opened = len(FakeSerial.handles)

    roof.disconnect()
    assert roof.released is True

    assert 'released' in refuses(roof, roof.status)
    assert len(FakeSerial.handles) == opened, "a released controller opened the port"


def test_connect_proves_the_module_without_holding_it():
    reset()
    roof = controller()
    roof.disconnect()

    info = roof.connect()
    assert roof.released is False
    assert info['released'] is False
    assert info['mode_name'] == 'One Touch'
    assert len(FakeSerial.handles) == 1
    assert FakeSerial.handles[0].is_open is False


def test_close_is_still_accepted_as_letting_go():
    reset()
    roof = controller()
    roof.close()
    assert roof.released is True


def test_a_released_controller_reports_itself_as_released():
    reset()
    roof = controller()
    assert roof.status()['released'] is False


# -- failures that must not open anything -------------------------------------

def test_connect_reports_a_module_that_is_not_there():
    reset()
    FakeSerial.open_error = SerialException('no such device')
    assert 'cannot open' in refuses(controller(), controller().connect)
    assert FakeSerial.handles == []


def test_an_out_of_range_speed_never_opens_the_port():
    reset()
    roof = controller()
    refuses(roof, lambda: roof.set_speed(31))
    assert FakeSerial.handles == []


def test_an_unknown_mode_never_opens_the_port():
    reset()
    roof = controller()
    refuses(roof, lambda: roof.set_mode(9))
    assert FakeSerial.handles == []


# -- runner -------------------------------------------------------------------

def main():
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
