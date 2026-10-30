#!/usr/bin/env python3
"""How closely does the drawn bar follow the engine? Measured, not asserted.

Everything else in this directory checks that the pieces are correct. This one checks that
they are *responsive*: it simulates the whole loop - the ECU broadcasting on a fixed period,
the strip sampling what arrives, the predictor drawing between samples, and the repaint
cadence - and compares the rpm the strip paints against the rpm the engine actually had at
that instant.

That is the number the owner asked about, and it is not visible in any single function.
Measured on a 20 ms (50 Hz) broadcast with a 4 ms repaint, over a run that idles, pulls to
6500, holds, lifts hard and coasts down:

    case                                    mean err   ss worst
    no prediction, interrupt working          27 rpm     114 rpm
    prediction, interrupt working              4 rpm      15 rpm   <- 1/50 of an LED step
    prediction, 10 ms late (old poll)         34 rpm      74 rpm
    prediction, 2 ms late (new poll)          10 rpm      20 rpm

Three things fall out of that:

  - prediction is what makes the bar track, and it is *not* a substitute for a working
    interrupt: a 10 ms late sample scores worse (34 rpm) than no prediction at all with a
    clean one (27), because the predictor is then running from stale evidence;
  - the repaint cadence barely matters above ~2 ms (1 ms and 10 ms both land near 4 rpm),
    so the firmware's 4 ms is inside the flat region - this asserts that rather than
    assuming it;
  - the worst case is a *corner*: a hard lift drops 4100 rpm inside one sample period, and
    nothing can know that before sampling past it. It is reported separately because it is
    information the strip does not have, not latency.

    python test_latency.py
    python test_latency.py --verbose     # per-paint trace

No hardware, no compiler: this is the port's own arithmetic, driven by a clock.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Callable, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import led_engine as engine  # noqa: E402

FULL_RPM = 6800
ONE_LED_STEP = FULL_RPM / 9.0        # ten ranks centre-out, so this is one pixel of travel


def engine_curve(ms: float) -> float:
    """A drive that exercises the cases that matter, in one 3 s run.

    0.00-0.60 s  idle 800, a little hunt
    0.60-1.40 s  pulled to 6500 at ~7100 rpm/s (a second-gear pull)
    1.40-1.60 s  held
    1.60-1.75 s  lifted to 2400 at ~27000 rpm/s (over the snap threshold: a real step)
    1.75-2.40 s  coasting down gently at ~700 rpm/s (under the threshold, so filtered)
    2.40-3.00 s  idle 800
    """
    import math
    if ms < 600:
        return 800 + 12 * math.sin(ms / 90.0)
    if ms < 1400:
        return 800 + (ms - 600) * (5700 / 800.0)
    if ms < 1600:
        return 6500
    if ms < 1750:
        return 6500 - (ms - 1600) * (4100 / 150.0)
    if ms < 2400:
        return 2400 - (ms - 1750) * (1400 / 650.0)
    return 800 + 12 * math.sin(ms / 90.0)


def simulate(period_ms: int, paint_ms: int, arrival_delay_ms: int,
             predict: bool) -> List[Tuple[float, float, float]]:
    """One run of the loop. Returns [(time, truth, drawn), ...] per paint.

    `arrival_delay_ms` is how late a sample reaches the loop, which is what a missed
    interrupt or a lost flag costs. The strip stamps the sample with the time it *read* it,
    not the time the ECU took it, so a delay shows up as the predictor running from stale
    evidence - exactly the error the receive-path fixes removed.
    """
    trace: List[Tuple[float, float, float]] = []
    filtered = 0.0
    last = prev = 0
    last_ms = prev_ms = 0
    have_history = False

    pending = []            # [(available_at, reading)] not yet read
    next_sample = 0
    next_paint = 0
    t = 0
    while t <= 3000:
        # The ECU broadcast: sample the engine now, the loop can read it `delay` ms later.
        while next_sample <= t:
            pending.append((next_sample + arrival_delay_ms,
                            int(round(engine_curve(next_sample)))))
            next_sample += period_ms

        # The loop reads whatever has arrived (top of loop, in arrival order).
        while pending and pending[0][0] <= t:
            _at, reading = pending.pop(0)
            filtered = engine.smooth_rpm(filtered, float(reading))
            sample = int(filtered + 0.5)
            prev, prev_ms = last, last_ms
            last, last_ms = sample, t
            have_history = have_history or bool(prev_ms)

        if t >= next_paint:
            if predict and have_history:
                drawn = engine.predict_rpm(t, last, prev, last_ms, prev_ms, True, FULL_RPM)
            else:
                drawn = last if have_history else 0
            trace.append((t, engine_curve(t), float(drawn)))
            next_paint += paint_ms

        t += 1
    return trace


# Times where the engine's slope changes abruptly. No predictor can know a corner before it
# has sampled past it, so these are reported separately from the steady-state behaviour.
CORNERS = ((600, 80), (1400, 80), (1600, 120), (1750, 120), (2400, 80))


def _near_corner(t: float) -> bool:
    return any(abs(t - centre) <= window for centre, window in CORNERS)


def summarise(trace: List[Tuple[float, float, float]]) -> Tuple[float, float, float]:
    """(steady-state mean, steady-state worst, corner worst) absolute error, in rpm."""
    steady = [abs(drawn - truth) for t, truth, drawn in trace[60:] if not _near_corner(t)]
    corners = [abs(drawn - truth) for t, truth, drawn in trace[60:] if _near_corner(t)]
    if not steady:
        return 0.0, 0.0, 0.0
    return (sum(steady) / len(steady), max(steady), max(corners) if corners else 0.0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    period = 20                 # 0x201 at 50 Hz, the case that makes prediction matter
    paint = engine_repaint_ms()
    print("sample period: %d ms   repaint: %d ms   one LED step: %.0f rpm"
          % (period, paint, ONE_LED_STEP))

    rows = [
        ("no prediction, interrupt working", simulate(period, paint, 0, False)),
        ("prediction, interrupt working", simulate(period, paint, 0, True)),
        ("prediction, 10 ms late (old poll)", simulate(period, paint, 10, True)),
        ("prediction, 2 ms late (new poll)", simulate(period, paint, 2, True)),
    ]

    print("\n%-36s %10s %10s %12s" % ("case", "mean err", "ss worst", "corner worst"))
    steady = {}
    for label, trace in rows:
        mean, worst, corner = summarise(trace)
        steady[label] = (mean, worst)
        print("%-36s %8.0f rpm %8.0f rpm %9.0f rpm" % (label, mean, worst, corner))

    problems = []
    plain_mean, plain_worst = steady["no prediction, interrupt working"]
    pred_mean, pred_worst = steady["prediction, interrupt working"]
    if not pred_mean < plain_mean / 2:
        problems.append("prediction barely improved the mean error (%.0f vs %.0f rpm)"
                        % (pred_mean, plain_mean))
    if pred_worst > ONE_LED_STEP / 10:
        problems.append("steady-state error of %.0f rpm is over a tenth of an LED step (%.0f)"
                        % (pred_worst, ONE_LED_STEP / 10))
    late_mean, _late_worst = steady["prediction, 10 ms late (old poll)"]
    if not late_mean > pred_mean:
        problems.append("a 10 ms sampling delay did not worsen the error (%.0f vs %.0f rpm) - "
                        "the model is not exercising arrival time" % (late_mean, pred_mean))
    polled_mean, _ = steady["prediction, 2 ms late (new poll)"]
    if not polled_mean < late_mean:
        problems.append("the 2 ms fallback poll is not better than the 10 ms one (%.0f vs "
                        "%.0f rpm)" % (polled_mean, late_mean))

    # The cadence in the firmware has to be fast enough that it is not the limiting factor.
    # Compared against a 1 ms paint, which is as good as it can get.
    fastest = summarise(simulate(period, 1, 0, True))[0]
    print("\nrepaint cadence: 1 ms -> %.1f rpm mean, %d ms -> %.1f rpm mean"
          % (fastest, paint, pred_mean))
    if pred_mean > fastest * 1.2:
        problems.append("the %d ms repaint cadence is costing accuracy: %.1f rpm mean "
                        "against %.1f at 1 ms - lower LED_UPDATE_INTERVAL"
                        % (paint, pred_mean, fastest))

    if args.verbose:
        print("\n  time   truth   drawn   err")
        for t, truth, drawn in simulate(period, paint, 0, True)[::25]:
            print("%6.0f %7.0f %7.0f %6.0f" % (t, truth, drawn, drawn - truth))

    if problems:
        for problem in problems:
            print("\nFAIL", problem)
        return 1
    print("\nLATENCY OK - the bar tracks the engine inside a fraction of one LED step")
    return 0


def engine_repaint_ms() -> int:
    """The firmware's repaint cadence, read out of the source so the two cannot drift."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "..", "..", "arduino", "src", "main.cpp")
    import re
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    match = re.search(r"#define\s+LED_UPDATE_INTERVAL\s+(\d+)", text)
    if not match:
        raise SystemExit("could not read LED_UPDATE_INTERVAL from main.cpp")
    return max(1, int(match.group(1)) // 1000)


if __name__ == "__main__":
    sys.exit(main())
