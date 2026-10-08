#!/usr/bin/env python3
"""Profile the pulse runs inside recent captures.

Why this exists: the SAME Nissan fob has produced long_us values of 264, 290,
295, 675, 850 and 1246 us across six enrolments, while the Mazda has stayed
stable (410 -> 441). The hypothesis is that a fob which keeps transmitting while
its button is held contributes a trailing run whose length IS the hold time, and
_signature() clusters ALL runs in the gap-free stretch - so that one run lands in
the "long" cluster and drags long_us and ratio along with it. The signature then
measures how long somebody pressed the button, not the device.

To test that, this prints for each capture: the run count, the LONGEST run in us,
how far it stands above the next longest, the most common run lengths, and what
_signature() reports with that longest run and without it.

Usage:  python scripts/run_profile.py [capture-log] [max-captures]
"""
import collections
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import live_readout as L      # noqa: E402

path = sys.argv[1] if len(sys.argv) > 1 else L.CAPTURE_PATH
maxn = int(sys.argv[2]) if len(sys.argv) > 2 else 40

CAP_RE = re.compile(r"CAP\s+(\d+)\s+(\d+)\s+([0-9A-Fa-f]+)")


def stretch_of(runs):
    """The longest gap-free stretch, exactly as _signature() picks it."""
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
        return "none"
    return "%s/%s us x%s (%s runs)" % (sig["short_us"], sig["long_us"],
                                       sig["ratio"], sig["n_runs"])


def main():
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            lines = [ln for ln in f if "CAP" in ln]
    except OSError as exc:
        print("cannot read %s: %s" % (path, exc))
        return 1
    lines = lines[-maxn:]
    print("capture log : %s" % path)
    print("examining   : %d captures" % len(lines))
    print()

    flagged = 0
    kept = 0
    for ln in lines:
        m = CAP_RE.search(ln)
        if not m:
            continue
        try:
            sample_us = float(m.group(2)) / float(m.group(1))
        except (ValueError, ZeroDivisionError):
            sample_us = 48.0
        runs = L._cap_runs(m.group(3))
        st = stretch_of(runs)
        if len(st) < 16:
            continue
        kept += 1
        top = sorted(st, reverse=True)[:2]
        longest = top[0]
        second = top[1] if len(top) > 1 else 1
        trimmed = list(st)
        trimmed.remove(longest)
        hist = collections.Counter(st).most_common(5)
        print("stretch=%3d runs   longest=%6.0f us   next=%6.0f us   ratio=%.1fx"
              % (len(st), longest * sample_us, second * sample_us,
                 longest / float(second or 1)))
        print("   common runs (us x count): %s"
              % ", ".join("%.0f x%d" % (v * sample_us, c) for v, c in hist))
        print("   signature with longest   : %s" % brief(L._signature(st, sample_us)))
        print("   signature without it     : %s"
              % brief(L._signature(trimmed, sample_us)))
        # A "hold run" signature: the longest run dwarfs everything else.
        if second and longest >= 3 * second:
            flagged += 1
        print()

    print("stretches examined            : %d" % kept)
    print("with a dominant trailing run  : %d  (>= 3x the next longest)" % flagged)

    # --- which captures are even the same DEVICE? -------------------------
    # The receiver is in a busy band and captures whatever burst trips its
    # probe, so a scatter of signatures may be several devices rather than one
    # unstable one - and that distinction changes the whole diagnosis. A
    # device's symbol ALPHABET (the pulse widths it uses) is the thing that
    # survives an arbitrary window, so group the captures by it.
    print()
    print("--- grouping captures by symbol alphabet ---")
    vocs = []
    for ln in lines:
        m = CAP_RE.search(ln)
        if not m:
            continue
        try:
            sample_us = float(m.group(2)) / float(m.group(1))
        except (ValueError, ZeroDivisionError):
            continue
        runs = stretch_of(L._cap_runs(m.group(3)))
        if len(runs) < 16:
            continue
        c = collections.Counter(round(r * sample_us) for r in runs)
        v = [val for val, _ in c.most_common(8)]
        v.sort()
        vocs.append((v, len(runs)))

    def overlap(a, b, tol=0.20):
        if not a or not b:
            return 0.0
        hit = sum(1 for x in a
                  if any(abs(x - y) <= tol * max(x, y) for y in b))
        return hit / float(len(a))

    groups = []          # each: {"members": [idx], "vocab": [...]}
    for i, (v, n) in enumerate(vocs):
        placed = False
        for g in groups:
            if overlap(v, g["vocab"]) >= 0.6 and overlap(g["vocab"], v) >= 0.6:
                g["members"].append(i)
                # Keep the vocabulary from the largest capture in the group.
                if n > g["best"]:
                    g["vocab"], g["best"] = v, n
                placed = True
                break
        if not placed:
            groups.append({"members": [i], "vocab": v, "best": n})

    for k, g in enumerate(groups, 1):
        runs_list = [vocs[i][1] for i in g["members"]]
        print("group %d: %d of %d captures   runs=%s"
              % (k, len(g["members"]), len(vocs), runs_list))
        print("   alphabet (us): %s"
              % ", ".join(str(x) for x in sorted(g["vocab"])))
    print()
    for name, dev in (L._devices or {}).items():
        s = (dev or {}).get("sig") or {}
        print("enrolled %-12s short=%-7s long=%-8s ratio=%-6s runs=%s"
              % (name, s.get("short_us"), s.get("long_us"), s.get("ratio"),
                 s.get("n_runs")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
