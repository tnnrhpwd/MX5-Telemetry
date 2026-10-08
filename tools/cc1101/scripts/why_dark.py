#!/usr/bin/env python3
"""Why is no chip lighting up?

Shows the live signature scored against every enrolled device, FIELD BY FIELD,
and names the reason nothing is lit: the best score is too low, two devices are
within the ambiguity margin, or the device was skipped because its enrolment came
from too few pulse runs.

This exists because "the indicator is dark" has four different causes that look
identical from the outside, and three of them have already been mistaken for one
another in this project.

Usage:  python scripts/why_dark.py
"""
import json
import pathlib
import sys
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import live_readout as L      # noqa: E402

# Must mirror _sig_score(): a field either side does not know is skipped.
FIELDS = (("short_us", 0.30), ("long_us", 0.30),
          ("ratio", 0.25), ("period_syms", 0.20))


def main():
    # SUPERSEDED: this explained why a TIMING match failed, and identification is
    # by the decoded MESSAGE now (see _match_code). The page's meta line already
    # does this job - it shows the last message received and whether it is
    # enrolled - so leaving this printing timing scores would actively mislead.
    print("superseded: identification is by the decoded message now.")
    print("The page's meta line shows the last message and the device it matched;")
    print("a message that is not enrolled appears there as '(not enrolled)'.")
    return 0


def _superseded_main():
    try:
        raw = urllib.request.urlopen("http://127.0.0.1:8765/data", timeout=5).read()
    except Exception as exc:                       # noqa: BLE001
        print("cannot reach the readout server: %s" % exc)
        return 1
    d = json.loads(raw.decode("utf-8", "ignore"))

    sig = d.get("last_signature")
    live = d.get("last_device")
    print("live signature : %s" % (sig,))
    print("lit now        : %s"
          % ("nothing" if not live
             else "%s (%.2f)" % (live.get("name"), live.get("score", 0))))
    print("rules          : score >= 0.75, winner must beat the runner-up by %.2f,"
          % L.MATCH_MARGIN)
    print("                 enrolment needs >= %d runs" % L.ENROL_MIN_RUNS)
    print("hold           : a lit chip expires after %.1f s" % L.DEVICE_HOLD_S)
    print()

    if not sig:
        print("VERDICT: no signature has been computed at all - press a fob.")
        return 0

    scored = []
    for name, dev in (d.get("devices") or {}).items():
        ref = (dev or {}).get("sig") or {}
        runs = ref.get("n_runs") or 0
        if runs < L.ENROL_MIN_RUNS:
            print("%-14s SKIPPED - enrolled from %d runs (< %d)"
                  % (name, runs, L.ENROL_MIN_RUNS))
            continue
        parts = []
        for key, tol in FIELDS:
            x, y = sig.get(key), ref.get(key)
            if x is None or y is None:
                parts.append("%s -" % key)
                continue
            denom = max(abs(x), abs(y)) or 1
            gap = abs(x - y) / float(denom)
            parts.append("%s %s vs %s (%.0f%% off, tol %.0f%%)%s"
                         % (key, x, y, gap * 100, tol * 100,
                            "" if gap <= tol else "   <-- MISS"))
        score = L._sig_score(sig, ref)
        print("%-14s score=%s" % (name, "n/a" if score is None else "%.2f" % score))
        for p in parts:
            print("                 %s" % p)
        if score is not None:
            scored.append((score, name))

    print()
    if not scored:
        print("VERDICT: no device is eligible at all -> nothing can light.")
    elif scored[0][0] < 0.75:
        print("VERDICT: best is %s at %.2f, under the 0.75 bar -> nothing lights."
              % (scored[0][1], scored[0][0]))
    elif len(scored) > 1 and scored[0][0] - scored[1][0] < L.MATCH_MARGIN:
        print("VERDICT: %s (%.2f) and %s (%.2f) are inside the %.2f margin -> "
              "ambiguous, so nothing lights."
              % (scored[0][1], scored[0][0], scored[1][1], scored[1][0],
                 L.MATCH_MARGIN))
    else:
        print("VERDICT: %s should be lit at %.2f."
              % (scored[0][1], scored[0][0]))
        print("If it is dark, the light had already expired when you looked "
              "(hold is only %.1f s)." % L.DEVICE_HOLD_S)
    return 0


if __name__ == "__main__":
    sys.exit(main())
