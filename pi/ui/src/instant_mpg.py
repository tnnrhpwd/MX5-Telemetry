"""Instantaneous fuel economy from mass air flow (OBD-II PID 0x10).

Both displays show the same INST MPG number, fed from `TelemetryData.instant_mpg`:
the round ESP32 panel draws it on its Overview card, and the Android Engine page
prints it to one decimal. It is derived from the air the engine actually metered,
which is the one fuel-consumption signal the NC gives away for free once the Pi is
allowed to transmit an OBD-II request:

    fuel (gal/h) = MAF (g/s) * 3600 / (AFR * lb/gal * g/lb)
                 = MAF * 3600 / (14.7 * 6.17 * 454)
                 = MAF / 11.438

    MPG = mph / (gal/h) = 11.438 * mph / MAF

The arithmetic is one line. Deciding whether a reading means anything is not: a
stopped car, a missing MAF reply, a bus that went quiet and a genuine fuel-cut
coast all arrive as ordinary numbers, and the UIs draw `--` for "unknown" but a
number for everything else. A wrong guard shows `--` forever (this has already
happened once on the car); a missing guard shows a confident 300 mpg.

So the decision lives here, away from the render loop, where it can be tested
without a car, a Pi or a CAN adapter. See test_instant_mpg.py.
"""

import time

# -- the formula ------------------------------------------------------------
#
# Stoichiometric values for gasoline. Closed-loop cruise runs at 14.7:1, which is
# where this reading is most accurate; under load the PCM richens to ~12.5:1, so
# the number reads slightly optimistic at wide-open throttle. That bias is shared
# with every MAF-based trip computer and is accepted rather than corrected.

AFR_STOICHIOMETRIC = 14.7        # air:fuel mass ratio, gasoline, closed loop
GASOLINE_LB_PER_GALLON = 6.17    # 60 F; summer blend is ~6.25, about 1% apart
GRAMS_PER_POUND = 454.0

# Gallons per hour for one gram/second of air, and the reciprocal the MPG
# calculation actually uses. Derived, not typed: 3600 / (14.7 * 6.17 * 454).
GALLONS_PER_HOUR_PER_GPS = 3600.0 / (
    AFR_STOICHIOMETRIC * GASOLINE_LB_PER_GALLON * GRAMS_PER_POUND)
MPG_PER_GPS_AIR = 1.0 / GALLONS_PER_HOUR_PER_GPS        # 11.4379

# -- what counts as a real reading ------------------------------------------

# Below this the quotient says more about speed-sensor rounding than about fuel,
# and a parked car has no distance to divide by. Reported as unknown, not 0.
MIN_SPEED_MPH = 1.0

# Zero air mass means no reply or an engine that is not running, never real flow.
MIN_MAF_GPS = 0.5

# MAF is polled in one slot shared with intake air, so a healthy reply every
# 0.5 s. Four missed replies in a row is a dead link, not jitter.
MAX_MAF_AGE_SEC = 2.0

# Fuel cut on overrun (and a bad MAF divisor) can push the quotient arbitrarily
# high. 99 is past anything the car can do and still reads as a number.
MAX_MPG = 99.0

# Only worth a journal line when the car is actually moving: at a red light
# "no reading" is the expected answer.
LOG_MIN_SPEED_MPH = 5.0


def mpg_from_maf(speed_mph: float, maf_gps: float) -> float:
    """MPG for one sample, with no guards and no clamp.

    The sign of the speed is ignored: reversing covers distance and burns fuel
    the same way forward motion does, and `speed_kmh` is negative in reverse.
    """
    if not (maf_gps > 0.0):      # also rejects NaN
        return 0.0
    return MPG_PER_GPS_AIR * abs(speed_mph) / maf_gps


class InstantMPG:
    """MAF samples in, the value both displays show out.

    `update()` is called from the render loop at the loop's own rate with
    whatever the CAN reader last stored, so the same MAF sample is seen many
    times. Validity is therefore decided from the age of the sample, not from a
    per-call delta: repeating a stale number must never make it look fresh.
    """

    def __init__(self, log_interval_sec: float = 30.0):
        self._value = 0.0
        self._valid = False
        self._log_interval = log_interval_sec
        self._last_log = 0.0

    @property
    def value(self) -> float:
        """Last computed MPG, or 0.0 when the reading is not valid."""
        return self._value

    @property
    def valid(self) -> bool:
        """True when `value` is a real reading rather than a placeholder."""
        return self._valid

    def update(self, speed_mph: float, maf_gps: float,
               maf_age_sec: float) -> float:
        """Recompute from the current telemetry and return the MPG value.

        Args:
            speed_mph: Road speed; sign ignored.
            maf_gps: Latest MAF sample in grams/second (0 if never received).
            maf_age_sec: Age of that sample. Large when the bus has gone quiet.

        Returns:
            The MPG value, or 0.0 when the reading is not valid. Read `valid`
            (or `telemetry.instant_mpg_valid`) to tell "unknown" from "0 mpg".
        """
        speed = abs(speed_mph)

        # Each test is written as `not (x in range)` rather than `x out of range`
        # so a NaN fails it: a NaN compares false against everything, and letting
        # one through would put "nan" on the wire and a blank card on the dash.
        if not (speed >= MIN_SPEED_MPH):
            # Parked or crawling. There is no distance being covered, so this is
            # "not applicable" rather than an infinite or zero figure.
            return self._invalidate()

        if not (maf_gps >= MIN_MAF_GPS):
            return self._invalidate('no MAF reply', speed)

        if not (maf_age_sec <= MAX_MAF_AGE_SEC):
            return self._invalidate(f'MAF {maf_age_sec:.1f}s old', speed)

        self._value = min(mpg_from_maf(speed, maf_gps), MAX_MPG)
        self._valid = True
        return self._value

    # -- internals ---------------------------------------------------------

    def _invalidate(self, reason: str = '', speed_mph: float = 0.0) -> float:
        self._value = 0.0
        self._valid = False
        if reason and speed_mph >= LOG_MIN_SPEED_MPH:
            # One line per half minute is enough to tell "the car never answered
            # the PID" from "the reply stopped", which is the difference between
            # a wiring problem and a bus problem.
            now = time.time()
            if now - self._last_log >= self._log_interval:
                self._last_log = now
                print(f"MPG INST: -- while moving at {speed_mph:.0f} mph ({reason})")
        return 0.0
