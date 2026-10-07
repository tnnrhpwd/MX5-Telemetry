"""Print the symbol stream of the longest captures, so the framing is visible.

Scoring scripts tell you *whether* two captures match; this shows you what one
capture actually contains. If the fob repeats a frame every ~20-40 ms, a 45 ms
window should hold the SAME pattern two or three times, visible by eye without
any alignment machinery.
"""
import pathlib
import statistics
from collections import defaultdict

HERE = pathlib.Path(__file__).resolve().parent.parent
LOG = HERE / "captures" / "capture_live.txt"


def bits(hexs):
    out = []
    for ch in hexs:
        v = int(ch, 16)
        for k in (3, 2, 1, 0):
            out.append((v >> k) & 1)
    return out


def runs_of(x):
    r, prev, res = 1, x[0], []
    for v in x[1:]:
        if v == prev:
            r += 1
        else:
            res.append(r)
            prev, r = v, 1
    res.append(r)
    return res


def stretch(rr, gap=500):
    best, cur = [], []
    for r in rr:
        if r > gap:
            if len(cur) > len(best):
                best = cur
            cur = []
        else:
            cur.append(r)
    if len(cur) > len(best):
        best = cur
    return best


groups = defaultdict(list)
for line in open(LOG, encoding="utf-8", errors="ignore"):
    line = line.strip()
    if not line.startswith("CAP "):
        continue
    f = line.split()
    if len(f) < 5:            # index from the RIGHT: tolerant of a leading ts
        continue
    groups[" ".join(f[-2:])].append(stretch(runs_of(bits(f[-3]))))

for tag in sorted(groups):
    seqs = sorted(groups[tag], key=len, reverse=True)
    print("=" * 72)
    print("%s -- longest %d of %d captures" % (tag, min(2, len(seqs)), len(seqs)))
    for st in seqs[:2]:
        lo = statistics.median(sorted(st)[: max(1, len(st) // 2)])
        hi = statistics.median(sorted(st)[len(st) // 2:])
        thr = (lo * hi) ** 0.5
        sym = "".join("0" if r < thr else "1" for r in st)
        print("\n  %d runs, short~%.0f long~%.0f samples (%.0fus / %.0fus)"
              % (len(st), lo, hi, lo * 9.33, hi * 9.33))
        for i in range(0, len(sym), 60):
            print("    %s" % sym[i:i + 60])
