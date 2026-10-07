#!/usr/bin/env python3
"""Regression test: a brief periodic pulse must still become a table row.

The bug this guards: the event detector required EVENT_MIN_ABOVE (= 3) RSSI
samples above the noise floor before it would record a transmission. The probe
watches a 24 ms window every ~50 ms, so a fob that pulses for a few ms about
once a second - a 2008 MX-5 fob does exactly this - lands in ONE sample at best,
and usually in none at all. The result was that the fob spiked the live chart
plainly but never appeared in the Detected Transmissions table: no signal row,
no fob row, nothing.

The fix accepts a single above-threshold sample when the deviation is
unambiguous (>= 1.5x EVENT_RISE_DB) while keeping the three-sample rule for
marginal deviations, so ordinary noise still cannot open an event. This test
pins both halves of that behaviour - a test that only checked the first half
would pass just as happily against a detector with no noise rejection at all.

Usage:  python tests/test_event_detector.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import live_readout as L      # noqa: E402

FLOOR = -110
STRONG = -95          # 15 dB above the floor: unambiguous
MARGINAL = FLOOR + 9  # 9 dB: above EVENT_RISE_DB (8) but below the strong bar
FREQ = 315.0
STEP = 0.2            # seconds between RSSI samples


def reset():
    """Put the module back to a cold, idle state."""
    L.events.clear()
    L._floor = None
    L._in_event = False
    L._below_count = 0
    L._ev_above = 0
    L._ev_peak = -200
    L._ev_codes.clear()
    L.last_decode = None
    L.fobburst_at = None


def feed(levels):
    """Run the detector over a level sequence; return the rows it produced."""
    t = 0.0
    for lv in levels:
        L._update_events(lv, FREQ, t)
        t += STEP
    return list(L.events)


def check(name, cond, detail=""):
    print("  %-46s %s%s" % (name, "PASS" if cond else "FAIL",
                            "" if cond else "   " + detail))
    return cond


def main():
    ok = True

    reset()
    rows = feed([FLOOR] * 6 + [STRONG] + [FLOOR] * 6)
    ok &= check("single-sample pulse is recorded", len(rows) == 1,
                "got %d rows" % len(rows))

    reset()
    rows = feed([FLOOR] * 6 + [STRONG] + [FLOOR] * 6)
    ok &= check("short strong pulse is typed 'signal'",
                rows and rows[0]["type"] == "signal",
                "got %r" % (rows[0]["type"] if rows else None))

    reset()
    rows = feed([FLOOR] * 6 + [MARGINAL] + [FLOOR] * 6)
    ok &= check("marginal single blip is still rejected", len(rows) == 0,
                "got %d rows" % len(rows))

    reset()
    rows = feed([FLOOR] * 6 + [STRONG] * 4 + [FLOOR] * 6)
    ok &= check("sustained burst still recorded", len(rows) == 1,
                "got %d rows" % len(rows))

    # A 1 Hz pulse train should give one row per pulse, each with a ~1 s repeat
    # interval - the device fingerprint the user described. The spacing has to
    # be right for that to mean anything: 5 samples at STEP = 1.0 s between
    # pulses, with enough quiet either side for the event to close (it needs 3
    # below-threshold samples).
    reset()
    # The trailing quiet matters: the detector closes an event only after 3
    # below-threshold samples, so a sequence that ends on the last pulse leaves
    # that row unrecorded.
    rows = feed(([FLOOR] * 2 + [STRONG] + [FLOOR] * 2) * 4 + [FLOOR] * 3)
    good = [r for r in rows if r.get("repeat_s") and 0.8 <= r["repeat_s"] <= 1.2]
    ok &= check("1 Hz pulse train -> one row per pulse, ~1 s repeat",
                len(rows) == 4 and len(good) == 3,
                "rows=%d repeating=%d" % (len(rows), len(good)))

    print("\n%s" % ("all checks passed" if ok else "FAILURES above"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
