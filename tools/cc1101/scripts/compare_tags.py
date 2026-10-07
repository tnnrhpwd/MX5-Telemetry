"""Compare captures grouped by their MOD= tag: which modulation reproduces the
fob's pulse structure most cleanly?

A cleanly demodulated 2-level signal shows up as:
  - a large, CONSISTENT short/long separation within each capture
  - SIMILAR pulse widths from one capture to the next (low spread)
That is the thing to compare, not signal strength.
"""
import math
import pathlib
import statistics
import sys
from collections import Counter, defaultdict

HERE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
from live_readout import decode_cap      # noqa: E402

LOG = HERE / "captures" / "capture_live.txt"
lines = [l.strip() for l in open(LOG, encoding="utf-8", errors="ignore")
         if l.startswith("CAP ")]
print("CAP lines: %d" % len(lines))


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


def kmeans2(vals):
    a, b = float(min(vals)), float(max(vals))
    for _ in range(50):
        g1 = [v for v in vals if abs(v - a) <= abs(v - b)]
        g2 = [v for v in vals if abs(v - a) > abs(v - b)]
        if not g1 or not g2:
            break
        a, b = sum(g1) / len(g1), sum(g2) / len(g2)
    return a, b


groups = defaultdict(lambda: {"n": 0, "short": [], "long": [], "sep": [],
                              "bursts": [], "decoded": [], "pulses": []})
untagged = 0

for l in lines:
    f = l.split()
    if len(f) < 6:
        untagged += 1
        continue
    # Group by the WHOLE tag, not just MOD: a 10k and a 38.4k run are
    # different experiments and must not be averaged together.
    tag = " ".join(f[-2:])
    if not tag:
        untagged += 1
        continue

    per = float(f[-4]) / float(f[-5])
    samples = bits(f[-3])
    rr = runs_of(samples)

    bursts, cur = [], []
    for r in rr:
        if r > 60:
            if cur:
                bursts.append(cur)
            cur = []
        else:
            cur.append(r)
    if cur:
        bursts.append(cur)
    bursts = [b for b in bursts if len(b) >= 8]

    g = groups[tag]
    g["n"] += 1
    d = decode_cap(f[-3], per)
    g["decoded"].append(1 if d else 0)
    if not bursts:
        continue
    b = max(bursts, key=len)
    a, bb = kmeans2(b)
    if a <= 0:
        continue
    g["short"].append(a * per)
    g["long"].append(bb * per)
    g["sep"].append(bb / a)
    g["bursts"].append(len(bursts))
    g["pulses"].append(len(b))

print("untagged/legacy captures: %d\n" % untagged)
print("%-24s %4s %8s %8s %7s %8s %6s %6s %8s" % (
    "tag", "n", "short", "long", "sep", "shortSD", "pulses", "bursts", "decoded"))
for tag in sorted(groups):
    g = groups[tag]
    if not g["short"]:
        print("%-24s %4d  (no usable bursts)" % (tag, g["n"]))
        continue
    print("%-24s %4d %7.0fus %7.0fus %6.2fx %7.0fus %6.0f %6.1f %5d/%d" % (
        tag, g["n"],
        statistics.median(g["short"]), statistics.median(g["long"]),
        statistics.median(g["sep"]),
        statistics.pstdev(g["short"]),
        statistics.median(g["pulses"]), statistics.median(g["bursts"]),
        sum(g["decoded"]), g["n"]))

print()
print("payloads seen (by full tag):")
for tag in sorted(groups):
    codes = Counter()
    for l in lines:
        f = l.split()
        if len(f) < 6:
            continue
        if " ".join(f[-2:]) != tag:
            continue
        d = decode_cap(f[-3], float(f[-4]) / float(f[-5]))
        if d:
            codes[d[0]] += 1
    print("  %-24s %s" % (tag, dict(codes) if codes else "(none decoded)"))
