#!/usr/bin/env python3
"""Desk test for the speed path: CAN frame -> TelemetryData -> `TEL:` line.

Reverse used to arrive at both displays as a *positive* speed, which then made
the gear estimator pick 1st gear. Two separate defects did that:

* the 0x201 speed field was decoded only around its +100 km/h bias, so a
  two's-complement negative was read as +228..+555 km/h; and
* `esp32_serial_handler` clamped the value to 0 before it went on the wire, so
  the ESP32 could never have shown a negative even if the decode produced one.

This pins both, plus the rounding rule, with no Pi, no car and no python-can:

    python3 test_can_speed.py
    pytest test_can_speed.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from can_handler import CANParser, GearEstimator, CANHandler  # noqa: E402
from esp32_serial_handler import format_telemetry_line  # noqa: E402


# -- helpers ----------------------------------------------------------------

def frame_201(raw):
    """An 8-byte 0x201-shaped frame with `raw` in the speed field (bytes 4-5)."""
    return bytes([0x0E, 0xA0, 0x00, 0x00, (raw >> 8) & 0xFF, raw & 0xFF, 0x00, 0x00])


class FakeTelemetry:
    """Just the attributes `format_telemetry_line` touches."""

    def __init__(self, **kwargs):
        self.rpm = 900
        self.speed_kmh = 0
        self.gear = 0
        self.gear_estimated = False
        self.clutch_engaged = False
        self.gear_color = 'green'
        self.is_in_neutral = True
        self.is_in_reverse = False
        self.throttle_percent = 0
        self.brake_percent = 0
        self.coolant_temp_f = 190
        self.oil_status = True
        self.fuel_level_percent = 60.0
        self.voltage = 13.8
        self.instant_mpg = 0.0
        self.instant_mpg_valid = False
        self.average_mpg = 26.0
        self.range_miles = 250
        self.maf = 0.0
        self.maf_timestamp = 0.0
        for key, value in kwargs.items():
            setattr(self, key, value)


BIAS = CANParser.SPEED_RAW_ZERO


# -- decode: forward --------------------------------------------------------

def test_forward_speeds_are_unchanged():
    assert CANParser.parse_speed(frame_201(BIAS)) == 0
    assert CANParser.parse_speed(frame_201(BIAS + 100)) == 1
    assert CANParser.parse_speed(frame_201(BIAS + 5000)) == 50
    assert CANParser.parse_speed(frame_201(BIAS + 10000)) == 100
    assert CANParser.parse_speed(frame_201(BIAS + 22000)) == 220


def test_short_frame_is_zero():
    assert CANParser.parse_speed(b'\x00' * 5) == 0


# -- decode: reverse --------------------------------------------------------

def test_reverse_below_the_bias_is_negative():
    # -1 km/h floors to -1, not 0; that truncation is what lost slow reverse.
    assert CANParser.parse_speed(frame_201(BIAS - 40)) == -1
    assert CANParser.parse_speed(frame_201(BIAS - 100)) == -1
    assert CANParser.parse_speed(frame_201(BIAS - 500)) == -5
    assert CANParser.parse_speed(frame_201(BIAS - 1200)) == -12


def test_twos_complement_reverse_is_negative():
    """A plain signed negative (0x8000 and up) must not read as a fast forward.

    Read as unsigned around the bias, 0xFE0C (-5 km/h) came out as +555 km/h,
    which is the "reverse shows a positive speed" report.
    """
    assert CANParser.parse_speed(frame_201(0xFE0C)) == -5      # -5.00 km/h
    assert CANParser.parse_speed(frame_201(0xFF9C)) == -1      # -1.00 km/h
    assert CANParser.parse_speed(frame_201(0xFF06)) == -3      # -2.50 -> floor -3
    assert CANParser.parse_speed(frame_201(0xFFFF)) == -1      # -0.01 -> floor -1


def test_impossible_values_are_discarded():
    # Blanked field: under the bias this is -100 km/h, which used to fake a
    # reverse every time the PCM had no wheel speed yet.
    assert CANParser.parse_speed(frame_201(0x0000)) == 0
    assert CANParser.parse_speed(frame_201(0x0001)) == 0       # -99.99 km/h
    # Bus noise: 0x8000 and up decode to -327 and -228 km/h once the sign is
    # honoured, which no MX-5 can do.
    assert CANParser.parse_speed(frame_201(0x8000)) == 0       # -327.68 signed
    assert CANParser.parse_speed(frame_201(0xA6F6)) == 0       # -227.94 signed


def test_reverse_direction_reaches_the_gear_estimator():
    """The estimator must answer -1 (reverse) for a negative speed, not 1."""
    est = GearEstimator()
    gear, _clutch, confidence, recommended, _colour = est.estimate_gear(-3.0, 900, False)
    assert gear == -1, "negative speed must be reverse"
    assert recommended == -1
    assert confidence == 1.0


def test_reverse_wins_over_a_stuck_neutral_bit():
    """The neutral switch lags; it must not turn a reversing car into 'N'."""
    est = GearEstimator()
    gear = est.estimate_gear(-2.0, 900, True)[0]
    assert gear == -1


# -- wire format ------------------------------------------------------------

def test_reverse_speed_survives_to_the_wire():
    t = FakeTelemetry(speed_kmh=-3, gear=-1, is_in_reverse=True)
    fields = format_telemetry_line(t).strip().split(':')[1].split(',')
    assert len(fields) == 18, "field count is a contract with display/src/main.cpp"
    assert fields[1] == '-3', "the ESP32 must receive the signed speed"
    assert fields[2] == '-1', "gear -1 is what draws the R"
    assert fields[15] == '1', "the explicit reverse flag still travels"


def test_forward_speed_on_the_wire():
    t = FakeTelemetry(speed_kmh=50, gear=3)
    fields = format_telemetry_line(t).strip().split(':')[1].split(',')
    assert fields[1] == '50'
    assert fields[15] == '0'


def test_negative_zero_never_goes_on_the_wire():
    """-0.0 formats as "-0", which reads as a sign while meaning nothing."""
    t = FakeTelemetry(speed_kmh=-0.0, gear=0, is_in_reverse=True)
    fields = format_telemetry_line(t).strip().split(':')[1].split(',')
    assert fields[1] == '0'


# -- live handler behavior -------------------------------------------------

class FakeMsg:
    def __init__(self, arbitration_id, data):
        self.arbitration_id = arbitration_id
        self.data = data


def make_handler(**kwargs):
    """A real CANHandler over a fake telemetry object; no bus is opened."""
    return CANHandler(FakeTelemetry(**kwargs))


def test_a_silent_bus_clears_the_reverse_state():
    """Unplugging CAN while reversing used to leave `R` and a negative speed up."""
    t = FakeTelemetry(speed_kmh=-3, gear=-1, is_in_reverse=True, clutch_engaged=True)
    h = make_handler()
    h.telemetry = t
    h.speed_timestamp = time.time() - 5.0
    h._reverse_hold_until = time.time() + 10.0

    h._apply_staleness()

    assert t.speed_kmh == 0, "a frozen reverse speed must decay"
    assert t.gear == 0
    assert t.is_in_reverse is False
    assert t.clutch_engaged is False
    assert h._reverse_hold_until == 0, "the hold timer must not outlive the data"


def test_fresh_speed_is_left_alone():
    t = FakeTelemetry(speed_kmh=-3, gear=-1, is_in_reverse=True)
    h = make_handler()
    h.telemetry = t
    h.speed_timestamp = time.time()

    h._apply_staleness()

    assert t.speed_kmh == -3
    assert t.gear == -1
    assert t.is_in_reverse is True


def test_the_range_frame_does_not_clear_reverse():
    """0x231 arrives independently of 0x201 and used to clear the reverse flag.

    Two writers at different rates is what made the phone flicker between R and N
    while the ESP kept showing R: the phone reads the flag, the ESP also reads
    `gear == -1`.
    """
    t = FakeTelemetry(speed_kmh=-3, gear=-1, is_in_reverse=True)
    h = make_handler()
    h.telemetry = t
    h._update_gear_estimation()
    assert t.is_in_reverse is True

    # 0x231 claiming neutral (byte 1 == 0x04 is the neutral/park marker)
    h._process_hs_message(FakeMsg(0x231, bytes([0x00, 0x04, 0x00, 0x00, 0, 0, 0, 0])))

    assert t.is_in_neutral is True, "the neutral bit is still taken from 0x231"
    assert t.is_in_reverse is True, "but 0x231 must not be allowed to clear reverse"
    assert t.gear == -1


# -- transmission range / the discrete reverse path -------------------------

def test_range_codes_are_reported():
    assert CANParser.parse_range(bytes([0x07, 0x00, 0, 0, 0, 0, 0, 0])) == 7
    assert CANParser.parse_range(bytes([0x0B, 0x00, 0, 0, 0, 0, 0, 0])) == 11
    # Byte 1 == 0x04 is the neutral/park marker, whatever byte 0 says
    assert CANParser.parse_range(bytes([0x03, 0x04, 0, 0, 0, 0, 0, 0])) == 0
    assert CANParser.parse_range(b'') is None


def test_range_wire_payload_is_nibble_masked():
    # Upper nibble of byte 0 carries something else; only the low nibble is range
    assert CANParser.parse_range(bytes([0xF7, 0x00, 0, 0, 0, 0, 0, 0])) == 7


def test_gear_stays_unknown_until_a_reverse_code_is_configured():
    """An unconfigured range code must never be read as reverse."""
    assert CANParser.REVERSE_RANGE_CODES == frozenset(), \
        "shipping a guess here would put a confident R on screen while driving"
    assert CANParser.parse_gear(bytes([0x07, 0x00, 0, 0, 0, 0, 0, 0])) is None
    assert CANParser.parse_gear(bytes([0x00, 0x00, 0, 0, 0, 0, 0, 0])) == 0


def test_a_configured_range_code_drives_reverse_without_a_speed_sign():
    """With the observed code filled in, reverse no longer needs the speed sign.

    This is the escape hatch for ISSUE-14 if the PCM clamps the speed field at
    its centre: one constant, and 0x231 decides.
    """
    saved = CANParser.REVERSE_RANGE_CODES
    CANParser.REVERSE_RANGE_CODES = frozenset({7})
    try:
        assert CANParser.parse_gear(bytes([0x07, 0x00, 0, 0, 0, 0, 0, 0])) == -1

        t = FakeTelemetry(speed_kmh=4, gear=1, is_in_reverse=False)
        h = make_handler()
        h.telemetry = t
        h._process_hs_message(FakeMsg(0x231, bytes([0x07, 0x00, 0, 0, 0, 0, 0, 0])))
        h._update_gear_estimation()

        assert t.transmission_range == 7
        assert t.is_in_reverse is True, "reverse must not depend on the sign of the speed"
        assert t.gear == -1
    finally:
        CANParser.REVERSE_RANGE_CODES = saved


def test_the_raw_speed_field_is_recorded():
    """The raw value is what settles ISSUE-14, so it has to reach the JSON."""
    assert CANParser.parse_speed_raw(frame_201(0x2710)) == 0x2710
    assert CANParser.parse_speed_raw(frame_201(0x251C)) == 0x251C
    assert CANParser.parse_speed_raw(b'\x00' * 4) is None


# -- runner -----------------------------------------------------------------

def _main():
    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith('test_') or not callable(fn):
            continue
        try:
            fn()
            print(f"  ok   {name}")
        except AssertionError as exc:
            failures += 1
            print(f"  FAIL {name}: {exc}")
    print(f"\n{failures} failure(s)")
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(_main())
