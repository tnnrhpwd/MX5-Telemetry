"""Decode ONE capture, from the raw samples up, showing every step.

No thresholds hidden, nothing assumed about the encoding beyond the one property
every OOK remote has: it quantises its pulses to a clock. So:

  1. pick the capture with the most structured burst in the log,
  2. print the burst's raw bit string (0/1), so the waveform is visible,
  3. list its pulse widths in microseconds,
  4. histogram those widths - an encoding shows PEAKS, noise shows a smear,
  5. fit a symbol clock and emit the decoded bits and hex.

Usage: python decode_one.py [log-path] [capture-index]
"""
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LOG = os.path.join(HERE, "..", "captures", "capture_live.txt")

RAIL_US = 2000.0      # a gap this long separates transmissions


def expand(hexs):
    bits = []
    for ch in hexs:
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
    caps = []
    for line in open(path, encoding="utf-8", errors="ignore"):
        m = re.search(r"\bCAP\s+(\d+)\s+(\d+)\s+([0-9A-Fa-f]+)", line)
        if m:
            caps.append((int(m.group(1)), int(m.group(2)), m.group(3)))
    return caps


def burst_runs(runs, sample_us):
    """Runs of the longest segment containing no rail-sized gap.

    The fob transmits for a few ms and then stops, and the receiver rails HIGH
    for the rest of the window. Splitting on the rail leaves the burst.
    """
    segs, cur = [], []
    for lvl, r in runs:
        if r * sample_us > RAIL_US:
            if cur:
                segs.append(cur)
            cur = []
        else:
            cur.append((lvl, r))
    if cur:
        segs.append(cur)
    return max(segs, key=len) if segs else []


def widths_us(seg, sample_us):
    return [r * sample_us for _, r in seg]


def fit_clock(ws):
    """Best clock period: the T explaining the most widths as n*T (n>=1)."""
    scored = []
    for t10 in range(300, 4000, 2):         # 30.0 .. 400 us in 0.2 us steps
        t = t10 / 10.0
        hits = sum(1 for w in ws
                   if round(w / t) >= 1
                   and abs(w - round(w / t) * t) <= 0.15 * t + 1.0)
        scored.append((hits / float(len(ws)), t))
    scored.sort(key=lambda s: (-s[0], -s[1]))
    return scored[:6]


def autocorr(bits, min_lag=20):
    """Model-free frame finder: at which lag does the waveform repeat?

    A repeating remote repeats its frame within a burst, so SOME lag must show a
    high match. This assumes no encoding at all - it works on the raw samples.
    """
    n = len(bits)
    out = []
    for lag in range(min_lag, n // 2):
        same = 0
        for i in range(n - lag):
            if bits[i] == bits[i + lag]:
                same += 1
        out.append((same / float(n - lag), lag))
    out.sort(key=lambda x: (-x[0], -x[1]))
    return out


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_LOG
    want = int(sys.argv[2]) if len(sys.argv) > 2 else None

    caps = load(path)
    print("read %d captures from %s" % (len(caps), path))
    if not caps:
        return

    scored = []
    for i, (n, us, hexs) in enumerate(caps):
        sample_us = us / float(n)
        bits = expand(hexs)[:n]
        seg = burst_runs(runs_of(bits), sample_us)
        if seg:
            scored.append((len(seg), i, n, us, hexs, sample_us, seg))
    if not scored:
        print("no capture contains a burst")
        return

    scored.sort(reverse=True, key=lambda s: s[0])
    if want is not None:
        pick = [s for s in scored if s[1] == want]
        if not pick:
            print("capture %d has no burst" % want)
            return
        chosen = pick[0]
    else:
        chosen = scored[0]
    _, idx, n, us, hexs, sample_us, seg = chosen

    print("chosen: capture #%d   burst %d runs   sample %.2f us"
          % (idx, len(seg), sample_us))
    print()

    # 3) raw bit string of the burst, so nothing is hidden behind a decoder
    print("--- raw burst samples (1 = GDO0 high), 64 per line ---")
    bits = "".join("1" if lvl else "0" for lvl, r in seg for _ in range(r))
    for k in range(0, len(bits), 64):
        print("  " + bits[k:k + 64])
    print()

    ws = widths_us(seg, sample_us)

    # 2) the pulse widths themselves
    print("--- pulse widths (us), in order ---")
    cells = ["%d%s" % (int(round(w)), "H" if seg[j][0] else "L")
             for j, w in enumerate(ws)]
    for k in range(0, len(cells), 12):
        print("  " + " ".join(cells[k:k + 12]))
    print()

    # 4) histogram - peaks mean an encoding, a smear means noise
    print("--- width histogram, 10 us bins ---")
    hist = Counter(int(w // 10) * 10 for w in ws)
    top = max(hist.values())
    for b in sorted(hist):
        if hist[b] >= max(2, top // 12):
            print("  %4d us | %-40s %d" % (b, "#" * hist[b], hist[b]))
    print()

    # 5) does the burst repeat? This is model-free, so it is the honest test.
    #
    # CAVEAT that caught this script out once already: a stream that is 95% ones
    # matches ITSELF about 90% at ANY lag by chance, so a high raw match proves
    # nothing on a railed capture. The chance floor for this duty cycle is
    # p^2 + (1-p)^2, and a real frame repeat has to clear it by a margin.
    print("--- does the burst REPEAT? (autocorrelation, no encoding assumed) ---")
    raw = [lvl for lvl, r in seg for _ in range(r)]
    p = sum(raw) / float(len(raw))
    floor = p * p + (1 - p) * (1 - p)
    ac = autocorr(raw)
    for frac, lag in ac[:6]:
        print("   lag %5d samples = %7.1f us   match %5.1f%%"
              % (lag, lag * sample_us, 100 * frac))
    print("   chance floor for this duty cycle (%.0f%% high) = %.1f%%"
          % (100 * p, 100 * floor))
    print()
    if ac[0][0] > floor + 0.15 and ac[0][1] > 40:
        print("   ==> the waveform repeats every %.1f us (match %.1f%%, floor %.1f%%)"
              % (ac[0][1] * sample_us, 100 * ac[0][0], 100 * floor))
        print("       - well above chance, so this is a real frame repeat")
    else:
        print("   ==> NO repeat above chance (best %.1f%% at %.1f us, floor %.1f%%)."
              % (100 * ac[0][0], ac[0][1] * sample_us, 100 * floor))
        print("       This burst holds no repeating frame.")

    # 6) clock fit, excluding the degenerate 'every sample is a multiple of one
    #    sample' answer by starting the search at three samples.
    print()
    print("--- clock fit (T, fraction of pulses that are n*T) ---")
    print("   (search starts at 30 us; below that every width trivially fits)")
    for frac, t in fit_clock([w for w in ws if w >= 30]):
        print("   T = %7.1f us   %5.1f%%" % (t, 100 * frac))


if __name__ == "__main__":
    main()
