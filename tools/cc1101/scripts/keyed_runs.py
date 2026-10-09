"""Show the run structure of captures that are actually carrying a signal.

A capture is either a rail (no signal - high fraction near 0 % or 100 %) or it is
keyed by a real transmission. Only the keyed ones contain an encoding, and the
existing scripts disagree about them because each was written against an assumed
encoding (PWM, a symbol grid, an autocorrelation period).

This one assumes nothing. It selects captures by high fraction - the property
that actually distinguishes "the receiver was moving" from "the receiver was
stuck" - and prints their measured runs in MICROSECONDS, in order, so the
encoding can be read directly.

Usage:
  python keyed_runs.py [log-path] [max-runs-to-print]

Defaults: the standard capture log, 80 runs.
"""
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LOG = os.path.join(HERE, "..", "captures", "capture_live.txt")

LO, HI = 0.15, 0.85        # a keyed capture is nowhere near a rail


def expand(hexstr):
    """Hex -> one bit per captured sample (4 bits per hex char)."""
    bits = []
    for ch in hexstr:
        if ch not in "0123456789abcdefABCDEF":
            continue
        v = int(ch, 16)
        for k in (3, 2, 1, 0):
            bits.append((v >> k) & 1)
    return bits


def runs_of(bits):
    out = []
    prev, run = bits[0], 1
    for b in bits[1:]:
        if b == prev:
            run += 1
        else:
            out.append((prev, run))
            prev, run = b, 1
    out.append((prev, run))
    return out


def load(path):
    """[(index, samples, micros, hex, drate)] - the tag matters for a sweep."""
    caps = []
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = re.search(r"\bCAP\s+(\d+)\s+(\d+)\s+([0-9A-Fa-f]+)", line)
            if m:
                d = re.search(r"DRATE=(\d+)", line)
                caps.append((int(m.group(1)), int(m.group(2)), m.group(3),
                             int(d.group(1)) if d else None))
    return caps


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_LOG
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 80
    hi = float(sys.argv[3]) if len(sys.argv) > 3 else HI

    caps = load(path)
    print("read %d captures from %s" % (len(caps), path))

    keyed = []
    for i, (n, us, hexs, drate) in enumerate(caps):
        bits = expand(hexs)[:n]
        if len(bits) < 8:
            continue
        frac = sum(bits) / float(len(bits))
        if LO < frac < hi:
            keyed.append((i, n, us, hexs, bits, frac, drate))

    print("%d of %d are keyed (high fraction between %d%% and %d%%)\n"
          % (len(keyed), len(caps), LO * 100, hi * 100))
    if not keyed:
        print("none - the receiver was railed for every capture in this log")
        return

    # Roll-up per data rate - the whole point of a rate sweep. If the dominant
    # width pair (and so the period) moves with DRATE it is the receiver's
    # slicer time constant; if it holds at every rate it is the fob's bit
    # period, and can be framed.
    print("dominant run widths per data rate (us)")
    print("%8s %6s %9s %9s %9s" % ("DRATE", "n", "short", "long", "period"))
    by_rate = {}
    for i, n, us, hexs, bits, frac, drate in keyed:
        sample_us = us / float(n)
        by_rate.setdefault(drate, []).extend(r * sample_us for _, r in runs_of(bits))
    for d in sorted(x for x in by_rate if x):
        w = by_rate[d]
        top = Counter(int(round(x / 10.0) * 10) for x in w).most_common(2)
        top.sort()
        if len(top) == 2:
            print("%8d %6d %9d %9d %9d"
                  % (d, len(w), top[0][0], top[1][0], top[0][0] + top[1][0]))
        else:
            print("%8d %6d   (single width cluster)" % (d, len(w)))
    print()

    for i, n, us, hexs, bits, frac, drate in keyed:
        sample_us = us / float(n)
        runs = runs_of(bits)
        widths = sorted(r * sample_us for _, r in runs)
        print("=" * 78)
        print("capture #%d   high %.1f%%   runs %d   sample %.2f us   DRATE=%s"
              % (i, 100 * frac, len(runs), sample_us, drate))
        print("  shortest %.0f us   median %.0f us   longest %.0f us"
              % (widths[0], widths[len(widths) // 2], widths[-1]))
        top = Counter(int(round(w / 10.0) * 10) for w in widths).most_common(8)
        print("  run widths (us): " +
              "  ".join("%dus x%d" % (w, c) for w, c in sorted(top)))
        print("  first %d runs as (level,us):" % min(limit, len(runs)))
        seq = []
        for lvl, r in runs[:limit]:
            w = int(round(r * sample_us))
            if w > 5000:
                seq.append("[RAIL %d%s]" % (w, "H" if lvl else "L"))
            else:
                seq.append("%d%s" % (w, "H" if lvl else "L"))
        for k in range(0, len(seq), 12):
            print("     " + " ".join(seq[k:k + 12]))
        print()


if __name__ == "__main__":
    main()
