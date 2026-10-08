"""Show the actual run structure of logged captures.

This exists because the previous decoders were all written against an ASSUMED
encoding (PWM where the run width carries the bit) and never against a
measurement of what the receiver actually delivers. Two different fobs produced
the same reported code, which means the assumption was wrong somewhere - and no
amount of re-reading the decoder tells you WHERE. The runs do.

Usage:
  python run_shape.py [path-to-capture-log] [n]

Prints, for the n most recent CAP lines: the run histogram in MICROSECONDS, the
mark/space breakdown, and the full run sequence of the longest gap-free burst.
"""

import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LOG = os.path.join(HERE, "..", "captures", "capture_live.txt")

IDLE_RUN_US = 600.0     # a gap longer than this separates transmissions


def expand(hexstr):
    """Hex -> one bit per 4-bit nibble, MSB first (matches live_readout)."""
    samples = []
    for ch in hexstr:
        if ch not in "0123456789abcdefABCDEF":
            continue
        v = int(ch, 16)
        for k in (3, 2, 1, 0):
            samples.append((v >> k) & 1)
    return samples


def runs_of(samples):
    """(level, length) pairs, so mark and space runs stay distinguishable."""
    out = []
    prev = samples[0]
    run = 1
    for s in samples[1:]:
        if s == prev:
            run += 1
        else:
            out.append((prev, run))
            prev, run = s, 1
    out.append((prev, run))
    return out


def longest_burst(runs, idle_us, sample_us):
    best, cur = [], []
    for level, r in runs:
        if r * sample_us > idle_us:
            if len(cur) > len(best):
                best = cur
            cur = []
        else:
            cur.append((level, r))
    if len(cur) > len(best):
        best = cur
    return best


def best_period(runs_us, lo_us=40.0, hi_us=2500.0):
    """Best bit-period fit: (T_us, fraction of runs that are near-multiples).

    A real OOK/PWM stream has run lengths that are INTEGER MULTIPLES of one bit
    time: a short pulse is 1T, a long one 2T or 3T, and nothing in between.
    Noise has no such unit - its runs spread across every value, so a run of 3
    samples is as likely as 4 or 5. That makes this one number the difference
    between "the demodulator is producing a data stream" and "it is producing
    noise", which no amount of staring at a hex dump can tell you.

    A candidate period only counts if the runs actually USE at least three
    different multiples of it; otherwise T = (smallest run) trivially "fits".
    """
    if len(runs_us) < 8:
        return None, 0.0, 0
    best = (None, 0.0, 0)
    for T in range(int(lo_us), int(hi_us), 2):
        Tf = float(T)
        fit = 0
        mults = set()
        for r in runs_us:
            n = round(r / Tf)
            if n < 1:
                continue
            if abs(r / Tf - n) * Tf <= 0.25 * Tf:
                fit += 1
                mults.add(n)
        frac = fit / float(len(runs_us))
        if len(mults) >= 3 and frac > best[1]:
            best = (T, frac, len(mults))
    return best


def pair_period(burst):
    """(mean_us, cv) of consecutive mark+space pairs - the PWM bit period.

    In PWM the bit period is the SUM of a pulse and the gap that follows it,
    not either one on its own. Testing individual runs against a symbol grid
    therefore finds nothing even when a perfectly clean data stream is sitting
    right there, because 240us-high + 360us-low and 360us-high + 240us-low are
    the same 600us cell. This is the test that actually fits this waveform.

    cv is the coefficient of variation of those sums: a real PWM stream keeps
    every cell within a few percent of the same length, whereas noise spreads
    the sums over a wide range.
    """
    sums = []
    i = 0
    while i + 1 < len(burst):
        lv, r = burst[i]
        lv2, r2 = burst[i + 1]
        if lv == 1 and lv2 == 0:
            sums.append(r + r2)
            i += 2
        else:
            i += 1
    if len(sums) < 8:
        return None, 0.0, 0
    mean = sum(sums) / float(len(sums))
    var = sum((s - mean) ** 2 for s in sums) / float(len(sums))
    cv = (var ** 0.5) / mean if mean else 0.0
    return mean, cv, len(sums)


def report(label, hexstr, total, total_us, brief=False):
    sample_us = float(total_us) / float(total)
    samples = expand(hexstr)
    runs = runs_of(samples)
    if not brief:
        print("")
        print("=" * 78)
    print("%s  (%d samples, %.2f us/sample)" % (label, len(samples), sample_us))
    if not brief:
        print("=" * 78)

    # Fraction of the capture that is high: an OOK receiver with no carrier
    # present parks at one rail, so this says whether anything was received.
    high = sum(1 for s in samples if s)
    print("high fraction: %.1f%%   runs: %d" % (100.0 * high / len(samples), len(runs)))
    # The longest runs are printed BEFORE the burst filter excludes them: in
    # PT2262/EV1527-style PWM the frame boundary is a very long LOW (a "sync"
    # of ~31T), and dropping it silently is how a capture can look like a
    # stream of identical bits with no frames in it at all.
    longest = sorted(runs, key=lambda lr: -lr[1])[:6]
    print("longest runs : %s"
          % ", ".join("%d%s" % (round(r * sample_us), "H" if lv else "L")
                      for lv, r in longest))

    marks = sorted(r * sample_us for lv, r in runs if lv == 1)
    spaces = sorted(r * sample_us for lv, r in runs if lv == 0)

    def hist(vals, name):
        c = collections.Counter(round(v / 10.0) * 10 for v in vals)
        print("%s (%d): %s" % (
            name, len(vals),
            ", ".join("%dus x%d" % (k, v) for k, v in sorted(c.items())[:14])))

    hist(marks, "mark/high runs")
    hist(spaces, "space/low runs")

    burst = longest_burst(runs, IDLE_RUN_US, sample_us)
    if not burst:
        print("no burst shorter than %.0f us" % IDLE_RUN_US)
        return
    print("longest burst: %d runs" % len(burst))
    T, frac, mults = best_period([r * sample_us for lv, r in burst])
    if T:
        print("run/bit-period fit: %d us  (%.0f%% of runs, %d multiples used)"
              % (T, 100 * frac, mults))
    else:
        print("run/bit-period fit: none (no common unit)")

    pmean, pcv, npairs = pair_period(burst)
    if pmean is None:
        print("PWM pair period: none (too few mark+space pairs)")
    else:
        print("PWM pair period: %d samples = %.0f us  (cv %.1f%%, %d pairs)  %s"
              % (round(pmean), pmean * sample_us, 100 * pcv, npairs,
                 "CLEAN DATA STREAM" if pcv < 0.15 else "not a constant cell"))
    if brief:
        return
    seq = ["%d%s" % (round(r * sample_us), "H" if lv else "L") for lv, r in burst]
    # Print wrapped, with the index every 8 runs so a periodic structure shows.
    for i in range(0, len(seq), 8):
        print("  [%3d] %s" % (i, " ".join(seq[i:i + 8])))


def main():
    brief = "--brief" in sys.argv
    rest = sys.argv[1:]
    only = None
    best = "--best" in rest
    argv = []
    for i, a in enumerate(rest):
        if a in ("--brief", "--best"):
            continue
        if a == "--only":
            only = int(rest[i + 1])
            continue
        if i and rest[i - 1] == "--only":
            continue
        argv.append(a)
    log = argv[0] if argv else DEFAULT_LOG
    n = int(argv[1]) if len(argv) > 1 else 3
    caps = []
    with open(log, "r", errors="ignore") as f:
        for line in f:
            m = re.search(r"(CAP\s+(\d+)\s+(\d+)\s+([0-9A-Fa-f]+))", line)
            if m:
                caps.append((m.group(2), m.group(3), m.group(4)))
    print("read %d CAP lines from %s" % (len(caps), log))
    if not caps:
        return
    if best:
        # The log grows while the server runs, so an index is not stable. Rank by
        # run count instead: a real burst has tens of runs, idle has one or two.
        ranked = sorted(range(len(caps)),
                        key=lambda i: len(runs_of(expand(caps[i][2]))))
        for i in ranked[-5:]:
            report("capture #%d of %d" % (i, len(caps)), caps[i][2],
                   int(caps[i][0]), int(caps[i][1]), brief)
        return
    if only is not None:
        total, total_us, hexstr = caps[only]
        report("capture #%d" % only, hexstr, int(total), int(total_us), brief)
        return
    for i, (total, total_us, hexstr) in enumerate(caps[-n:]):
        report("capture #%d of %d" % (len(caps) - n + i, len(caps)), hexstr,
               int(total), int(total_us), brief)


if __name__ == "__main__":
    main()
