#!/usr/bin/env python3
"""Desk test for instantaneous MPG: MAF frame -> MPG -> `TEL:` line.

INST MPG has shipped broken twice (once because the CAN interface was
listen-only, once because the Android page never copied the validity flag), and
both times the symptom was the same empty placeholder. This pins the parts that
can be checked without a car:

* the arithmetic against the standard MAF/lambda derivation;
* every reason the value is "unknown" rather than a number, since `--` on the
  dash is produced by any one of them failing;
* the MAF frame decode and the smoothing that feeds it;
* the two `TEL:` fields both displays read.

    python3 test_instant_mpg.py
    pytest test_instant_mpg.py
"""

import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from instant_mpg import (                                   # noqa: E402
    InstantMPG,
    MAX_MPG,
    MPG_PER_GPS_AIR,
    mpg_from_maf,
)
from can_handler import CANHandler, CANParser                # noqa: E402
from esp32_serial_handler import format_telemetry_line       # noqa: E402


# -- helpers ----------------------------------------------------------------

class FakeTelemetry:
    """Just the attributes the MAF path and `format_telemetry_line` touch."""

    def __init__(self, **kwargs):
        self.rpm = 2500
        self.speed_kmh = 60
        self.gear = 3
        self.gear_estimated = False
        self.clutch_engaged = False
        self.gear_color = 'green'
        self.is_in_neutral = False
        self.is_in_reverse = False
        self.throttle_percent = 20
        self.brake_percent = 0
        self.coolant_temp_f = 190
        self.oil_status = True
        self.fuel_level_percent = 60.0
        self.voltage = 13.8
        self.instant_mpg = 0.0
        self.instant_mpg_valid = False
        self.average_mpg = 26.0
        self.range_miles = 250
        self.intake_temp_f = 0
        self.maf = 0.0
        self.maf_timestamp = 0.0
        for key, value in kwargs.items():
            setattr(self, key, value)


class FakeMsg:
    def __init__(self, arbitration_id, data):
        self.arbitration_id = arbitration_id
        self.data = data


def maf_frame(gps):
    """An OBD-II Mode 01 PID 0x10 reply carrying `gps` grams/second."""
    raw = int(round(gps * 100))
    return FakeMsg(0x7E8, bytes([0x04, 0x41, 0x10, (raw >> 8) & 0xFF, raw & 0xFF, 0, 0, 0]))


def iat_frame(deg_c):
    """An OBD-II Mode 01 PID 0x0F reply carrying `deg_c`."""
    return FakeMsg(0x7E8, bytes([0x03, 0x41, 0x0F, deg_c + 40, 0, 0, 0, 0]))


def make_handler():
    """A real CANHandler over a fake telemetry object; no bus is opened."""
    return CANHandler(FakeTelemetry())


# -- the arithmetic ---------------------------------------------------------

def test_constant_matches_the_standard_derivation():
    """gal/h = MAF * 3600 / (14.7 * 6.17 * 454); MPG = mph / (gal/h)."""
    assert math.isclose(MPG_PER_GPS_AIR, 11.4379, abs_tol=1e-3)
    # The number quoted in docs and comments has to be the one the code uses.
    assert math.isclose(MPG_PER_GPS_AIR, 11.438, abs_tol=5e-4)


def test_steady_cruise():
    # 60 mph burning 20 g/s of air: 20 / 11.4379 = 1.749 gal/h -> 34.3 mpg
    assert math.isclose(mpg_from_maf(60.0, 20.0), 34.31, abs_tol=0.01)


def test_load_drops_the_number_and_lift_off_raises_it():
    """The behaviour the issue asked for: rises on lift-off, drops under load."""
    light = mpg_from_maf(50.0, 12.0)
    heavy = mpg_from_maf(50.0, 30.0)
    coast = mpg_from_maf(50.0, 2.0)
    assert coast > light > heavy


def test_reverse_counts_like_forward():
    """speed_kmh is negative in reverse; fuel is burnt over distance either way."""
    assert math.isclose(mpg_from_maf(-40.0, 15.0), mpg_from_maf(40.0, 15.0))


def test_zero_maf_never_divides_by_zero():
    assert mpg_from_maf(60.0, 0.0) == 0.0


# -- what counts as a reading ----------------------------------------------

def test_steady_cruise_is_a_valid_reading():
    calc = InstantMPG()
    value = calc.update(speed_mph=60.0, maf_gps=20.0, maf_age_sec=0.4)
    assert calc.valid is True
    assert math.isclose(value, 34.31, abs_tol=0.01)


def test_stopped_car_is_unknown_not_zero():
    """At a red light there is no distance to divide by; the card shows `--`."""
    calc = InstantMPG()
    calc.update(speed_mph=45.0, maf_gps=20.0, maf_age_sec=0.4)
    assert calc.valid is True

    value = calc.update(speed_mph=0.0, maf_gps=2.5, maf_age_sec=0.4)
    assert value == 0.0
    assert calc.valid is False, "a parked car is 'not applicable', not 0 mpg"


def test_a_missing_maf_reply_is_unknown():
    calc = InstantMPG()
    assert calc.update(speed_mph=45.0, maf_gps=0.0, maf_age_sec=0.0) == 0.0
    assert calc.valid is False


def test_a_silent_bus_invalidates_an_older_reading():
    """The last MAF sample must expire rather than freeze on the dash."""
    calc = InstantMPG()
    calc.update(speed_mph=45.0, maf_gps=20.0, maf_age_sec=0.4)
    assert calc.valid is True

    value = calc.update(speed_mph=45.0, maf_gps=20.0, maf_age_sec=5.0)
    assert value == 0.0
    assert calc.valid is False


def test_the_age_limit_is_four_missed_replies():
    """MAF is polled twice a second, so 2.0 s is four misses - a link, not jitter."""
    calc = InstantMPG()
    calc.update(speed_mph=45.0, maf_gps=20.0, maf_age_sec=1.99)
    assert calc.valid is True, "one or two missed replies must not blink the card"
    calc.update(speed_mph=45.0, maf_gps=20.0, maf_age_sec=2.01)
    assert calc.valid is False


def test_fuel_cut_is_clamped_instead_of_printing_a_nonsense():
    calc = InstantMPG()
    value = calc.update(speed_mph=70.0, maf_gps=0.6, maf_age_sec=0.2)
    assert value == MAX_MPG == 99.0
    assert calc.valid is True, "overrun is a real reading, just a clamped one"


def test_a_nan_never_reaches_the_wire():
    calc = InstantMPG()
    assert calc.update(speed_mph=float('nan'), maf_gps=20.0, maf_age_sec=0.1) == 0.0
    assert calc.update(speed_mph=45.0, maf_gps=float('nan'), maf_age_sec=0.1) == 0.0
    assert calc.update(speed_mph=45.0, maf_gps=20.0, maf_age_sec=float('nan')) == 0.0
    assert calc.valid is False


# -- the CAN side -----------------------------------------------------------

def test_a_real_maf_reply_decodes():
    """[len=4, 0x41, 0x10, A, B] -> (256*A + B) / 100 g/s."""
    assert math.isclose(CANParser.parse_maf(maf_frame(30.0).data), 30.0)
    assert math.isclose(CANParser.parse_maf(bytes([0x04, 0x41, 0x10, 0x00, 0x01, 0, 0, 0])),
                        0.01)


def test_an_intake_air_reply_is_not_read_as_air_flow():
    """PID 0x0F and 0x10 share response ID 0x7E8; they must not be confused."""
    assert CANParser.parse_maf(iat_frame(20).data) == 0.0
    assert CANParser.parse_intake_temp(maf_frame(30.0).data) is None


def test_the_handler_stamps_the_maf_sample():
    h = make_handler()
    h._process_hs_message(maf_frame(24.5))
    assert math.isclose(h.telemetry.maf, 24.5, abs_tol=1e-6)
    assert h.telemetry.maf_timestamp > 0


def test_a_second_sample_is_smoothed_not_stepped():
    """The average takes the edge off a two-samples-a-second reading."""
    h = make_handler()
    h.telemetry.maf = 10.0
    h.telemetry.maf_timestamp = time.time() - 0.5     # one poll slot ago
    h._process_hs_message(maf_frame(20.0))
    assert 10.0 < h.telemetry.maf < 20.0, "a single new sample must not jump the average"
    assert h.telemetry.maf > 13.0, "...but it must move a useful distance toward it"


def test_smoothing_does_not_hide_a_long_gap():
    """A stalled reader weights the returning sample fully instead of crawling."""
    h = make_handler()
    h.telemetry.maf = 10.0
    h.telemetry.maf_timestamp = time.time() - 60.0
    h._process_hs_message(maf_frame(20.0))
    assert math.isclose(h.telemetry.maf, 20.0, abs_tol=1e-6)


def test_the_smoothing_time_constant_is_rate_independent():
    """Half of the gap to the new value lands at one time constant, whatever the rate."""
    tau = CANHandler.MAF_SMOOTHING_TAU_SEC
    h = make_handler()
    h.telemetry.maf = 10.0
    h.telemetry.maf_timestamp = time.time() - tau
    h._process_hs_message(maf_frame(20.0))
    # alpha = 1 - e^-1 = 0.632 -> 10 + 6.32
    assert math.isclose(h.telemetry.maf, 16.32, abs_tol=0.15)


def test_air_flow_that_stops_arriving_is_cleared():
    """The Engine page shows MAF; a dead link must not keep showing a live number."""
    h = make_handler()
    h.telemetry.maf = 18.0
    h.telemetry.maf_timestamp = time.time() - 1.0
    h._apply_staleness()
    assert h.telemetry.maf == 18.0, "one missed reply is not a dead link"

    h.telemetry.maf_timestamp = time.time() - (CANHandler.MAF_STALE_SEC + 1.0)
    h._apply_staleness()
    assert h.telemetry.maf == 0.0


def test_the_maf_expiry_matches_the_instant_mpg_expiry():
    """One timestamp drives both readouts, so they must not disagree."""
    from instant_mpg import MAX_MAF_AGE_SEC
    assert CANHandler.MAF_STALE_SEC == MAX_MAF_AGE_SEC


# -- the wire contract ------------------------------------------------------

def test_both_displays_get_the_value_and_the_validity_flag():
    """TEL field 15 is the value, field 18 says whether it is real.

    display/src/main.cpp indexes the same line (`values[14]`, `values[17]`), and
    the HTTP snapshot the Android page reads carries the same two keys.
    """
    t = FakeTelemetry(instant_mpg=34.3, instant_mpg_valid=True)
    fields = format_telemetry_line(t).strip().split(':')[1].split(',')
    assert len(fields) == 18
    assert fields[14] == '34.3'
    assert fields[17] == '1'

    t = FakeTelemetry(instant_mpg=0.0, instant_mpg_valid=False)
    fields = format_telemetry_line(t).strip().split(':')[1].split(',')
    assert fields[14] == '0.0'
    assert fields[17] == '0', "0 mpg and 'no reading' must stay distinguishable"


def test_a_frame_from_the_car_reaches_the_wire():
    """End to end, desk-only: 0x7E8 -> handler -> tracker -> `TEL:` line."""
    t = FakeTelemetry(speed_kmh=97)          # 60.3 mph
    h = CANHandler(t)
    h._process_hs_message(maf_frame(20.0))

    calc = InstantMPG()
    t.instant_mpg = calc.update(
        speed_mph=t.speed_kmh * 0.621371,
        maf_gps=t.maf,
        maf_age_sec=time.time() - t.maf_timestamp,
    )
    t.instant_mpg_valid = calc.valid

    fields = format_telemetry_line(t).strip().split(':')[1].split(',')
    assert t.instant_mpg_valid is True
    assert fields[17] == '1'
    assert 30.0 < float(fields[14]) < 40.0


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
