#!/usr/bin/env python3
"""Does cleaning up the capture make the signature converge?

The live signature is short=71 us / long=379 us / ratio 5.35 while the encrolled
devices are ~120-145 / ~293-441 / ratio 2.5-3.1 : the LONG cluster agrees and the
SHORT one is nearly half. That is what a second, much faster population of runs
looks like when k-means is asked to split a mixture into two levels.

Every capture profiled so far contains runs at 9 us and 19 us - one and two
samples at the capture's 9.44 us/sample. A run of one sample is at the sampling
limit; it cannot be a symbol of a device whose symbols are 120 us long. Two
candidate explanations, and they need different fixes:

  (a) SETTLING - the capture starts the moment the probe sees 6 edges, so its
      first part is the receiver's AGC/slicer waking up rather than data.
      Fix: trim the start (or delay the capture).
  (b) NOISE - runs at the sampling limit are interleaved throughout.
      Fix: discard runs too short to be symbols.

This applies both to the logged captures and prints whether either cleanup makes
DIFFERENT captures of the same device agree with each other and with what is
enrolled - which is the only thing that matters.

Usage:  python scripts/capture_hygiene.py [capture-log] [max-captures]
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import live_readout as L      # noqa: E402

path = sys.argv[1] if len(sys.argv) > 1 else L.CAPTURE_PATH
maxn = int(sys.argv[2]) if len(sys.argv) > 2 else 60
CAP_RE = re.compile(r"CAP\s+(\d+)\s+(\d+)\s+([0-9A-Fa-f]+)")


def stretch_of(runs):
    best, cur = [], []
    for r in runs:
        if r > L.FRAME_GAP:
            if len(cur) > len(best):
                best = cur
            cur = []
        else:
            cur.append(r)
    if len(cur) > len(best):
        best = cur
    return best


def brief(sig):
    if not sig:
        return "-"
    return "%s/%-6s x%-5s" % (sig["short_us"], sig["long_us"], sig["ratio"])


def trim_head(runs, frac):
    """Drop whole runs from the front until `frac` of the samples are gone."""
    total = sum(runs)
    if total <= 0:
        return runs
    want = total * frac
    gone, i = 0, 0
    while i < len(runs) - 20 and gone < want:
        gone += runs[i]
        i += 1
    return runs[i:]


def drop_short(runs, min_samples):
    return [r for r in runs if r >= min_samples]


def cap_split(runs, sample_us, max_us):
    """Treat any run longer than max_us as SILENCE, not as a symbol.

    _signature() splits the stretch only on runs over FRAME_GAP, which is 500
    SAMPLES - about 4.7 ms at this capture rate. A silent gap of two or three
    milliseconds therefore stays inside the "gap-free stretch" and gets clustered
    as if it were a symbol, where it dominates the long cluster. Every capture
    here reports a long of 379-1996 us while the enrolled devices are 293-441,
    which is exactly what that would look like.
    """
    lim = max_us / sample_us
    best, cur = [], []
    for r in runs:
        if r > lim:
            if len(cur) > len(best):
                best = cur
            cur = []
        else:
            cur.append(r)
    if len(cur) > len(best):
        best = cur
    return best


def main():
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            lines = [ln for ln in f if "CAP" in ln]
    except OSError as exc:
        print("cannot read %s: %s" % (path, exc))
        return 1
    lines = lines[-maxn:]

    caps = []
    for ln in lines:
        m = CAP_RE.search(ln)
        if not m:
            continue
        try:
            sample_us = float(m.group(2)) / float(m.group(1))
        except (ValueError, ZeroDivisionError):
            continue
        runs = stretch_of(L._cap_runs(m.group(3)))
        if len(runs) >= 16:
            caps.append((runs, sample_us))

    print("capture log : %s" % path)
    print("usable      : %d captures (of %d lines)" % (len(caps), len(lines)))
    print()
    if not caps:
        print("Nothing usable to analyse.")
        return 0

    print("enrolled    : %s"
          % "  ".join("%s %s/%s x%s" % (n, (d.get("sig") or {}).get("short_us"),
                                        (d.get("sig") or {}).get("long_us"),
                                        (d.get("sig") or {}).get("ratio"))
                      for n, d in (L._devices or {}).items()))
    print()
    header = "%-5s %-8s" % ("runs", "as-is")
    variants = [("gap>300us", lambda r, s: cap_split(r, s, 300)),
                ("gap>500us", lambda r, s: cap_split(r, s, 500)),
                ("g300+d3", lambda r, s: drop_short(cap_split(r, s, 300), 3)),
                ("g500+d3", lambda r, s: drop_short(cap_split(r, s, 500), 3)),
                ("g300+d5", lambda r, s: drop_short(cap_split(r, s, 300), 5)),
                ("g500+d5", lambda r, s: drop_short(cap_split(r, s, 500), 5))]
    for name, _ in variants:
        header += " %-15s" % name
    print(header)
    print("-" * len(header))

    for runs, sus in caps:
        row = "%-5d %-8s" % (len(runs), brief(L._signature(runs, sus)))
        for _, fn in variants:
            v = fn(runs, sus)
            row += " %-15s" % (brief(L._signature(v, sus)) if len(v) >= 16 else "-")
        print(row)

    print()
    print("Read it as: the cleanup that makes the columns AGREE with each other")
    print("across captures - and with the enrolled values above - is the one that")
    print("is removing something real.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
