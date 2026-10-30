#!/usr/bin/env python3
"""Desk test for average MPG, fuel accounting and range.

The average and the range are the two numbers a driver actually trusts, and both
are derived rather than measured, which is where assumptions hide. This pins the
arithmetic and - more importantly - the accounting rules:

* fuel summed from air flow is the primary source, and covers idle;
* distance is only counted over intervals whose fuel flow is known;
* on the sender fallback, burned fuel still counts even when the resulting MPG is
  implausible (that used to bias the average upward);
* a small top-up rebases the segment instead of stranding the milestone;
* range is tank contents x average, and 0 without a tank reading.

    python3 test_mpg_calculator.py
    pytest test_mpg_calculator.py
"""

import json
import math
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from instant_mpg import GALLONS_PER_HOUR_PER_GPS                      # noqa: E402
from mpg_calculator import MPGCalculator                             # noqa: E402


# -- helpers ----------------------------------------------------------------

def make_calc(**kwargs):
    """A calculator over a throwaway data directory, already started."""
    tmpdir = tempfile.mkdtemp(prefix='mx5_mpg_test_')
    calc = MPGCalculator(data_dir=tmpdir, verbose=False)
    calc.start()
    for key, value in kwargs.items():
        setattr(calc, key, value)
    return calc


def fuel_gallons(maf_gps, seconds):
    """What the air-flow integration should have accumulated."""
    return GALLONS_PER_HOUR_PER_GPS * maf_gps * (seconds / 3600.0)


class Clock:
    """Deterministic time for `update()`: one 0.1 s tick per step."""

    def __init__(self, calc, start=1000.0):
        self.calc = calc
        self.now = start
        calc._last_update_time = start

    def run(self, seconds, maf=None, speed_mph=0.0, fuel=50.0, engine=True,
            maf_fresh=True, dt=0.1):
        """Drive `update()` for `seconds`, returning the last reported average."""
        steps = max(1, int(round(seconds / dt)))
        for _ in range(steps):
            self.now += dt
            self.calc._last_update_time = self.now - dt
            self.calc.update(
                speed_mph=speed_mph,
                raw_fuel_pct=fuel,
                engine_running=engine,
                dt_seconds=dt,
                maf_gps=maf if maf is not None else 0.0,
                maf_fresh=maf_fresh and maf is not None,
            )
        return self.calc.average_mpg


# -- air-flow accounting ----------------------------------------------------

def test_fuel_comes_from_air_flow():
    """60 mph burning 20 g/s is 34.3 mpg, and it needs no tank reading at all."""
    calc = make_calc()
    Clock(calc).run(180.0, maf=20.0, speed_mph=60.0, fuel=0.0)

    assert calc.average_mpg_source == 'maf'
    assert math.isclose(calc.average_mpg, 34.3, abs_tol=0.3)


def test_air_flow_matches_the_integration_by_hand():
    calc = make_calc()
    Clock(calc).run(180.0, maf=15.0, speed_mph=50.0)

    expected = (50.0 / 3600.0) * 180.0 / fuel_gallons(15.0, 180.0)
    assert math.isclose(calc.average_mpg, expected, rel_tol=1e-6)


def test_idling_counts_as_fuel_without_distance():
    """Fuel burned standing still is real fuel. It must drag the average down."""
    calc = make_calc()
    Clock(calc).run(300.0, maf=20.0, speed_mph=60.0)     # 5 miles at 34.3 mpg
    cruise = calc.average_mpg

    Clock(calc).run(600.0, maf=3.0, speed_mph=0.0)       # ten minutes idling
    assert calc.average_mpg_source == 'maf'
    assert calc.average_mpg < cruise, "idling has to cost something"


def test_distance_without_fuel_is_not_counted():
    """A MAF drop-out must not turn miles into mpg: no fuel figure, no miles."""
    calc = make_calc()
    Clock(calc).run(180.0, maf=20.0, speed_mph=60.0)
    before = calc.average_mpg

    # Same speed, stale sample: distance accrues on the gauge path, but the
    # air-flow average must not see either side of it.
    Clock(calc).run(180.0, maf=20.0, speed_mph=60.0, maf_fresh=False)
    assert calc.average_mpg == before


def test_a_short_burst_of_data_is_not_quoted():
    """Ten seconds of samples cannot define a tank average."""
    calc = make_calc()
    Clock(calc).run(10.0, maf=20.0, speed_mph=60.0)
    assert calc.average_mpg_source == 'estimated', \
        "too little air-flow data yet: report the EPA figure, not a measurement"


def test_engine_off_does_not_accumulate_fuel():
    calc = make_calc()
    Clock(calc).run(60.0, maf=20.0, speed_mph=0.0, engine=False)
    assert calc._maf_fuel_gal == 0.0
    assert calc._maf_distance_mi == 0.0


# -- sender fallback --------------------------------------------------------

def _gauge_calc():
    """A calculator with air flow permanently unavailable."""
    calc = make_calc()
    calc._fuel_stabilized = True
    calc._last_fuel_pct = 50.0
    calc._fuel_at_milestone = 50.0
    return calc


def test_sender_fallback_still_produces_an_average():
    calc = _gauge_calc()
    clock = Clock(calc)
    clock.run(1800.0, maf=None, speed_mph=30.0, fuel=52.0)   # 15 miles
    clock.run(1800.0, maf=None, speed_mph=30.0, fuel=48.0)   # 2% drop = 0.254 gal

    assert calc.average_mpg_source in ('fuel_gauge', 'estimated')
    # 0.254 gal at ~15 miles/segment is 59 mpg in this synthetic case; the point
    # is that the arithmetic is distance/fuel, not that the number is realistic.
    assert calc.average_mpg > 0


def test_burned_fuel_counts_even_when_the_mpg_is_implausible():
    """Idling drops the level with no distance: the gallons must still count.

    Counting them only alongside an accepted sample is how the old code kept
    dropping every warm-up and traffic jam out of the denominator.
    """
    calc = _gauge_calc()
    clock = Clock(calc)
    clock.run(60.0, maf=None, speed_mph=0.0, fuel=50.0)      # parked, no miles
    clock.run(600.0, maf=None, speed_mph=0.0, fuel=47.0)     # level fell 3%

    assert calc._lifetime_gallons > 0, "3% of a tank was burned and must be counted"
    assert math.isclose(calc._lifetime_gallons, 0.03 * 12.7, rel_tol=0.02)
def test_a_small_top_up_does_not_strand_the_milestone():
    """A 3% fill used to be invisible below the old 10% refuel test.

    The milestone then sat above the new level, every drop read as negative, and
    the average stopped moving until the tank fell below the old mark.
    """
    calc = _gauge_calc()
    clock = Clock(calc)
    clock.run(1800.0, maf=None, speed_mph=30.0, fuel=48.0)   # burn 2%, ~15 mi

    clock.run(60.0, maf=None, speed_mph=0.0, fuel=53.0)      # top up 3%
    assert math.isclose(calc._fuel_at_milestone, 53.0, abs_tol=0.6), \
        "the segment must rebase on the new level"

    # Now burn back down again; milestones must keep firing.
    before = calc._lifetime_gallons
    clock.run(1800.0, maf=None, speed_mph=30.0, fuel=50.5)
    assert calc._lifetime_gallons > before


def test_a_full_tank_still_counts_its_tail():
    """The last slice of a tank - last milestone to the pump - must be counted.

    Here the level only falls 1.5% (below the 2% milestone) before the fill, so
    the tail is the only chance to account for that fuel.
    """
    calc = _gauge_calc()
    clock = Clock(calc)
    clock.run(900.0, maf=None, speed_mph=30.0, fuel=48.5)    # 1.5% down, no milestone
    tail_before = calc._lifetime_gallons

    clock.run(60.0, maf=None, speed_mph=0.0, fuel=95.0)      # fill to near full
    assert calc._lifetime_gallons > tail_before, "the last slice of the tank counts"
    assert math.isclose(calc._lifetime_gallons - tail_before,
                        0.015 * MPGCalculator.TANK_CAPACITY_GAL, rel_tol=0.02)
    assert math.isclose(calc._fuel_at_milestone, 95.0, abs_tol=0.6)


def test_a_rising_level_with_no_prior_data_does_not_crash():
    calc = make_calc()
    calc._fuel_stabilized = True
    calc._last_fuel_pct = None
    calc._fuel_at_milestone = None
    Clock(calc).run(10.0, maf=None, speed_mph=0.0, fuel=80.0)
    assert calc.average_mpg == calc.EPA_DEFAULT_MPG


# -- range ------------------------------------------------------------------

def test_range_is_tank_contents_times_average():
    calc = make_calc()
    Clock(calc).run(120.0, maf=20.0, speed_mph=60.0, fuel=50.0)

    expected = int(0.5 * MPGCalculator.TANK_CAPACITY_GAL * calc.average_mpg)
    assert calc.range_miles == expected


def test_range_is_zero_without_a_tank_reading():
    calc = make_calc()
    Clock(calc).run(120.0, maf=20.0, speed_mph=60.0, fuel=0.0)
    assert calc.range_miles == 0, "the range needs a tank level; MPG does not"


def test_range_shrinks_with_fuel_level():
    calc = make_calc()
    clock = Clock(calc)
    clock.run(120.0, maf=20.0, speed_mph=60.0, fuel=80.0)
    full = calc.range_miles
    clock.run(10.0, maf=20.0, speed_mph=60.0, fuel=40.0)
    assert calc.range_miles < full


# -- sanity and persistence -------------------------------------------------

def test_the_average_is_clamped_to_the_physically_possible():
    calc = make_calc()
    calc._maf_fuel_gal = 1.0
    calc._maf_distance_mi = 1000.0        # would be 1000 mpg
    calc._maf_seconds = 1000.0
    calc._update_outputs(50.0)
    assert calc.average_mpg == MPGCalculator.AVERAGE_MAX_MPG


def test_air_flow_totals_survive_a_restart():
    tmpdir = tempfile.mkdtemp(prefix='mx5_mpg_test_')
    calc = MPGCalculator(data_dir=tmpdir)
    calc.start()
    Clock(calc).run(120.0, maf=20.0, speed_mph=60.0)
    calc.stop()

    with open(os.path.join(tmpdir, 'mpg_data.json')) as f:
        saved = json.load(f)
    assert saved['maf_fuel_gal'] > 0
    assert saved['maf_distance_mi'] > 0

    revived = MPGCalculator(data_dir=tmpdir)
    revived.start()
    assert math.isclose(revived._maf_fuel_gal, calc._maf_fuel_gal, rel_tol=1e-9)
    assert math.isclose(revived.average_mpg, calc.average_mpg, rel_tol=1e-9)


def test_old_data_files_without_air_flow_totals_still_load():
    tmpdir = tempfile.mkdtemp(prefix='mx5_mpg_test_')
    with open(os.path.join(tmpdir, 'mpg_data.json'), 'w') as f:
        json.dump({'total_miles': 120.0, 'total_gallons': 5.0,
                   'recent_mpg_values': [], 'recent_distances': []}, f)

    calc = MPGCalculator(data_dir=tmpdir)
    calc.start()
    assert calc._maf_fuel_gal == 0.0
    assert calc.average_mpg_source == 'fuel_gauge'
    assert math.isclose(calc.average_mpg, 24.0, rel_tol=1e-6)


def test_the_source_name_tells_the_truth():
    calc = make_calc()
    assert calc.average_mpg_source == 'estimated'
    Clock(calc).run(120.0, maf=20.0, speed_mph=60.0)
    assert calc.average_mpg_source == 'maf'


def test_reset_actually_clears_the_file():
    """The overwrite guard must not resurrect the totals a reset just cleared.

    A reset writes less than the disk holds, which is exactly the shape of "another
    instance has more data" - so without an explicit force the guard reloaded the
    old totals and the reset silently did nothing.
    """
    tmpdir = tempfile.mkdtemp(prefix='mx5_mpg_test_')
    calc = MPGCalculator(data_dir=tmpdir, verbose=False)
    calc.start()
    Clock(calc).run(180.0, maf=20.0, speed_mph=60.0)
    calc._save_data()
    assert calc._maf_fuel_gal > 0

    calc.reset_lifetime_data()

    with open(os.path.join(tmpdir, 'mpg_data.json')) as f:
        saved = json.load(f)
    assert saved['maf_fuel_gal'] == 0.0
    assert saved['total_miles'] == 0.0
    assert calc._maf_fuel_gal == 0.0


def test_the_overwrite_guard_still_protects_a_higher_mileage_file():
    """A stale instance must not overwrite a file with more miles on it."""
    tmpdir = tempfile.mkdtemp(prefix='mx5_mpg_test_')
    with open(os.path.join(tmpdir, 'mpg_data.json'), 'w') as f:
        json.dump({'total_miles': 500.0, 'total_gallons': 20.0}, f)

    calc = MPGCalculator(data_dir=tmpdir, verbose=False)
    calc.start()
    calc._lifetime_miles = 10.0          # a stale instance
    calc._save_data()

    with open(os.path.join(tmpdir, 'mpg_data.json')) as f:
        saved = json.load(f)
    assert saved['total_miles'] == 500.0
    assert calc._lifetime_miles == 500.0, "it reloads rather than overwriting"


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
