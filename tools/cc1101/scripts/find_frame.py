"""Is there a repeating frame? Compare raw pulse sequences, not decoder output.

decode_cap's payload start depends on where the capture happened to cut, so
comparing its OUTPUT cannot answer "fixed or rolling code" - every window would
look different even for a fixed code.

Instead: take each capture's raw run-length sequence (in samples) and find the
best alignment between every pair. If the fob repeats one frame, the true
alignment matches strongly and stands out from the median alignment, which is
what chance produces. If nothing stands out, there is no repeating frame in what
we captured.
"""
import pathlib
import random
import statistics
import sys
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


def longest_stretch(rr):
    best, cur = [], []
    for r in rr:
        if r > 60:
            if len(cur) > len(best):
                best = cur
            cur = []
        else:
            cur.append(r)
    if len(cur) > len(best):
        best = cur
    return best


def alignment_scores(a, b, tol_frac=0.25):
    """Match ratio for every offset, plus the offset that scored best."""
    scores = []
    for off in range(-len(b) + 1, len(a)):
        matches = overlap = 0
        for k in range(len(a)):
            j = k - off
            if 0 <= j < len(b):
                overlap += 1
                if abs(a[k] - b[j]) <= max(2, tol_frac * a[k]):
                    matches += 1
        if overlap >= 8:
            scores.append((matches / overlap, off))
    return scores


def best_over_offsets(a, b):
    """Best match ratio over all alignments, or None."""
    sc = alignment_scores(a, b)
    return max((s for s, _ in sc), default=None)


groups = defaultdict(list)
for line in open(LOG, encoding="utf-8", errors="ignore"):
    line = line.strip()
    if not line.startswith("CAP "):
        continue
    f = line.split()
    if len(f) < 5:            # index from the RIGHT: tolerant of a leading ts
        continue
    tag = " ".join(f[-2:])
    st = longest_stretch(runs_of(bits(f[-3])))
    if len(st) >= 12:
        groups[tag].append(st)

for tag in sorted(groups):
    seqs = groups[tag]
    print("=== %s: %d captures, run-count %s ===" % (
        tag, len(seqs), sorted(len(s) for s in seqs)))
    if len(seqs) < 2:
        continue
    real, control = [], []
    rng = random.Random(12345)          # fixed seed: the control is repeatable
    for i in range(len(seqs)):
        for j in range(i + 1, len(seqs)):
            a, b = seqs[i], seqs[j]
            r = best_over_offsets(a, b)
            if r is None:
                continue
            real.append(r)
            # Control: same search against a SHUFFLED copy. Taking the best of
            # ~100 offsets is a maximum statistic, so it sits well above the
            # median of the same search even when there is nothing to align.
            # Only a real pair beating its own shuffled control means anything.
            shuffled = b[:]
            rng.shuffle(shuffled)
            c = best_over_offsets(a, shuffled)
            if c is not None:
                control.append(c)
    if not real or not control:
        print("  (no comparable pairs)\n")
        continue
    print("  best alignment, REAL pairs    : median %.2f  max %.2f" % (
        statistics.median(real), max(real)))
    print("  best alignment, SHUFFLED ctrl : median %.2f  max %.2f" % (
        statistics.median(control), max(control)))
    margin = statistics.median(real) - statistics.median(control)
    print("  margin %.2f -> %s" % (margin, (
        "real captures align better than chance" if margin > 0.08
        else "INDISTINGUISHABLE from shuffled: no repeating frame extracted")))
    print()
