"""Decode the captured OOK waveform into bits, and look for a frame structure.

This reads the waveform for what the measurement says it is rather than what a
protocol datasheet says it should be:

  * One bit occupies a fixed cell of ~63 samples (596 us at 9.44 us/sample),
    measured from the captures themselves with a ~2% spread.
  * Inside each cell the carrier is ON for either a SHORT time (~25 samples,
    236 us) or a LONG time (~38 samples, 359 us), and the cell is made up the
    difference. So the bit is carried by the duty cycle of the cell - the width
    of the mark - and the cell length stays constant.

Pairing marks with the space that follows them is what makes this work. Judging
single run lengths against a symbol grid finds nothing, because neither 25 nor
38 samples is a multiple of the 63-sample cell.

Usage:
  python pwm_decode.py [log]              all clean captures, bits + hex
  python pwm_decode.py [log] --quiet       one line per capture
"""

import collections
import os
import pathlib
import re
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import run_shape as R      # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LOG = os.path.join(HERE, "..", "captures", "capture_live.txt")

IDLE_RUN_US = 600.0
CLEAN_CV = 0.15          # pair-period spread below this = a real data stream
MIN_CELLS = 24


def cells(burst):
    """[(mark, space)] pairs, aligned so every cell starts on a mark.

    A capture that begins mid-cell leaves a leading partial space; skipping to
    the first mark is what keeps the bit order stable from capture to capture.
    The final cell is dropped unless it is complete, because the window ends
    wherever it ends rather than at a bit boundary.
    """
    out = []
    i = 0
    while i < len(burst):
        if burst[i][0] == 1:
            if i + 1 < len(burst):
                out.append((burst[i][1], burst[i + 1][1]))
            i += 2
        else:
            i += 1
    return out


def decode_bits(cell_list):
    """(bitstring, long_marks, threshold, cell_len) or None.

    The mark widths fall into two tight clusters, so split them at the midpoint
    of the clusters rather than at an assumed duty ratio: the slicer shifts the
    absolute widths, but it does not merge the two levels.
    """
    marks = sorted(m for m, _ in cell_list)
    if len(marks) < MIN_CELLS:
        return None
    lo = marks[len(marks) // 4]
    hi = marks[(3 * len(marks)) // 4]
    if hi < lo * 1.30:
        return None                       # the two levels have merged: no data
    thr = (lo + hi) / 2.0
    bits = "".join("1" if m >= thr else "0" for m, _ in cell_list)
    cell = sum(m + s for m, s in cell_list) / float(len(cell_list))
    return bits, (lo, hi), thr, cell


def best_unit(runs_us, lo=30, hi=400):
    """The symbol time T: the LARGEST T that most run lengths are multiples of.

    Small T always "fits" - 37 us divides almost anything to within 15% - so the
    search takes the largest T that still explains the runs, which is the real
    symbol time. OOK remotes are built from whole multiples of one T (1T for a
    short pulse, 3T for a long one, 31T for a sync gap), and reading the runs in
    those units is what turns an opaque list of microseconds into a protocol.
    """
    n = float(len(runs_us))
    cands = []
    for T in range(int(lo), int(hi)):
        Tf = float(T)
        hits = sum(1 for r in runs_us
                   if round(r / Tf) >= 1
                   and abs(r - round(r / Tf) * Tf) <= 0.15 * Tf)
        cands.append((hits / n, T))
    if not cands:
        return None, 0.0
    top = max(f for f, _ in cands)
    # Among candidates within 2 percentage points of the best fit, take the
    # LARGEST T. Small T fits everything (a 37 us unit divides almost any run to
    # within 15%), so the largest equally-good unit is the real symbol time.
    good = [T for f, T in cands if f >= top - 0.02]
    return (max(good) if good else None), top


def frame_period(bits):
    """Smallest L where bits[i] == bits[i+L] for ~all i, or None."""
    best = (None, 0.0)
    for L in range(16, len(bits) // 2 + 1):
        n = len(bits) - L
        if n < 16:
            break
        m = sum(1 for i in range(n) if bits[i] == bits[i + L]) / float(n)
        if m > best[1]:
            best = (L, m)
    if best[0] is None or best[1] < 0.9:
        return None
    return best


def strip_preamble(bits, min_run=12):
    """(payload, preamble_len): drop a leading run of identical bits.

    A preamble is a long run of the same symbol, so the payload only starts once
    the value changes. Without this the preamble dominates the reported code -
    which is why two physically different fobs kept producing the SAME string:
    both carry the same preamble, and the decoder was reporting mostly preamble.
    """
    if not bits:
        return bits, 0
    c = bits[0]
    i = 0
    while i < len(bits) and bits[i] == c:
        i += 1
    if i >= min_run:
        return bits[i:], i
    return bits, 0


def hexof(bits):
    n = len(bits) - (len(bits) % 8)
    return "".join("%02X" % int(bits[i:i + 8], 2) for i in range(0, n, 8))


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    quiet = "--quiet" in sys.argv
    debug = "--debug" in sys.argv
    units = "--units" in sys.argv
    frame = "--frame" in sys.argv
    by_drate = "--by-drate" in sys.argv
    log = argv[0] if argv else DEFAULT_LOG
    caps = []
    with open(log, "r", errors="ignore") as f:
        for line in f:
            m = re.search(r"CAP\s+(\d+)\s+(\d+)\s+([0-9A-Fa-f]+)", line)
            if not m:
                continue
            tag = re.search(r"DRATE=(\d+)", line)
            band = re.search(r"FREQ=([\d.]+)", line)
            caps.append((int(m.group(1)), int(m.group(2)), m.group(3),
                         int(tag.group(1)) if tag else None,
                         float(band.group(1)) if band else None))

    seen = collections.Counter()
    stats = []
    clean = 0
    for idx, (total, total_us, hexstr, drate, freq) in enumerate(caps):
        sample_us = float(total_us) / float(total)
        runs = R.runs_of(R.expand(hexstr))
        burst = R.longest_burst(runs, IDLE_RUN_US, sample_us)

        if units:
            u = [r * sample_us for _, r in runs]
            if len(u) < 20:
                continue
            T, fit = best_unit(u)
            if not T:
                continue
            print("")
            print("#%-4d  T=%d us (fit %.0f%%, %d runs)   %s MHz @ %s bps"
                  % (idx, T, 100 * fit, len(u),
                     "-" if freq is None else "%.2f" % freq, drate))
            # Print EVERY run in units of T, marks as H and spaces as L, so a
            # preamble, a sync gap and the payload are visible as shapes.
            out = []
            for lv, r in runs:
                out.append("%d%s" % (max(int(round(r * sample_us / T)), 1),
                                      "H" if lv else "L"))
            for i in range(0, len(out), 14):
                print("     " + " ".join(out[i:i + 14]))
            continue

        cell_list = cells(burst) if burst else []

        if frame:
            # Deliberately NOT gated on the constant-cell PWM test: a capture
            # that carries a preamble followed by data has a mixed cell list by
            # definition, and that is exactly the capture worth decoding.
            got = decode_bits(cell_list)
            if not got:
                continue
            bits, (lo, hi), thr, cell = got
            payload, npre = strip_preamble(bits)
            print("")
            print("#%-4d short=%.0f long=%.0f cell=%.0f  preamble=%-3d bits  "
                  "payload=%-3d bits   %s MHz @ %s bps"
                  % (idx, lo, hi, cell, npre, len(payload),
                     "-" if freq is None else "%.2f" % freq, drate))
            print("     payload hex: %s" % hexof(payload))
            # A fob held down retransmits continuously, so one 45 ms window
            # normally holds SEVERAL copies of the same frame. If no period
            # shows up here, the decode is not aligned yet and a differing
            # payload between presses says nothing about rolling codes.
            fp = frame_period(bits)
            if fp:
                print("     frame repeats every %d bits (match %.0f%%)"
                      % (fp[0], 100 * fp[1]))
            else:
                print("     no repeating frame inside this window")
            seen[payload] += 1
            continue
        pmean, cv, npairs = R.pair_period(burst) if burst else (None, 0.0, 0)
        why = None
        if not burst:
            why = "no burst"
        elif cv >= CLEAN_CV:
            why = "cv %.3f" % cv
        if why is None:
            got = decode_bits(cell_list)
            if not got:
                why = "decode_bits: %d cells" % len(cell_list)
        if debug:
            print("#%-4d runs=%-4d burst=%-4d cells=%-4d cv=%.3f  %s"
                  % (idx, len(runs), len(burst or []), len(cell_list), cv,
                     why or "OK"))
            if cell_list and len(cell_list) >= 20:
                ms = collections.Counter(m for m, _ in cell_list)
                ss = collections.Counter(s for _, s in cell_list)
                print("       marks  (samples): %s"
                      % ", ".join("%d x%d" % kv for kv in sorted(ms.items())))
                print("       spaces (samples): %s"
                      % ", ".join("%d x%d" % kv for kv in sorted(ss.items())))
                print("       cells in order (mark/space us): %s"
                      % " ".join("%d/%d" % (round(m * sample_us),
                                            round(s * sample_us))
                                 for m, s in cell_list))
        stats.append(((freq, drate), len(cell_list), cv,
                      (pmean * sample_us) if pmean else 0.0, why is None))
        if why is not None:
            continue
        bits, (lo, hi), thr, cell = got
        clean += 1
        seen[bits] += 1
        if quiet:
            print("#%-4d cells=%-4d short=%-3d long=%-3d cell=%.1f  %s"
                  % (idx, len(cell_list), round(lo), round(hi), cell, hexof(bits)))
            continue
        print("")
        print("=" * 78)
        print("capture #%d   %d cells   short=%d long=%d samples   cell=%.1f"
              % (idx, len(cell_list), round(lo), round(hi), cell))
        print("=" * 78)
        for i in range(0, len(bits), 8):
            print("  %3d  %s" % (i, bits[i:i + 8]))
        print("  hex: %s" % hexof(bits))
        fp = frame_period(bits)
        if fp:
            print("  frame period: %d bits (match %.0f%%)  <-- frame is shorter "
                  "than the window" % (fp[0], 100 * fp[1]))
        else:
            print("  no repeating frame inside one window (window is ~%d bits)"
                  % len(bits))

    print("")
    print("%d of %d captures were clean PWM" % (clean, len(caps)))
    same = sum(n for n in seen.values() if n > 1)
    print("%d distinct bit patterns; %d captures share a pattern with another"
          % (len(seen), same))
    for bits, n in seen.most_common(6):
        print("  x%-3d %s" % (n, hexof(bits)))

    if by_drate:
        print("")
        print("--- grouped by band and RX data rate ---")
        print("A constant-duty square wave carries no data wherever it is seen, but")
        print("WHERE it appears is informative: following the data rate means the")
        print("receiver's slicer is oscillating, and appearing at BOTH bands means")
        print("it is leakage rather than the fob's own modulated signal.")
        groups = collections.defaultdict(list)
        for key, n, cv, pm, ok in stats:
            groups[key].append((n, cv, pm, ok))
        for key in sorted(groups, key=lambda k: (k[0] is None, k[0] or 0,
                                                 k[1] is None, k[1] or 0)):
            freq, rate = key
            rows = groups[key]
            ok_rows = [r for r in rows if r[3]]
            band = "-" if freq is None else "%.2f MHz" % freq
            bps = "-" if rate is None else "%d bps" % rate
            line = "  %-11s %-10s captures=%-3d clean=%-3d" % (
                band, bps, len(rows), len(ok_rows))
            if ok_rows:
                line += "  cells=%.0f  pair period=%.0f us  cv=%.1f%%" % (
                    statistics.mean(r[0] for r in ok_rows),
                    statistics.mean(r[2] for r in ok_rows),
                    100 * statistics.mean(r[1] for r in ok_rows))
            else:
                line += "  (nothing decodable)"
            print(line)


if __name__ == "__main__":
    main()
