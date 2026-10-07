"""For captures from ONE press, do they share a long common symbol sequence?

If the fob is fixed-code, every capture holds part of the same repeating frame,
so the captures should share a long common substring. If they share almost
nothing, either the fob is rolling-code or the framing is still wrong.
"""
import math
import pathlib
import sys
from collections import defaultdict
from difflib import SequenceMatcher

HERE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

LOG = HERE / "captures" / "capture_live.txt"
lines = [l.strip() for l in open(LOG, encoding="utf-8", errors="ignore")
         if l.startswith("CAP ")]


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


groups = defaultdict(list)
for l in lines:
    f = l.split()
    if len(f) < 5:            # index from the RIGHT: tolerant of a leading ts
        continue
    mod = next((t.split("=")[1] for t in f[-2:] if t.startswith("MOD=")), None)
    if mod is None:
        continue
    per = float(f[-4]) / float(f[-5])
    rr = runs_of(bits(f[-3]))
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
    if not bursts:
        continue
    b = max(bursts, key=len)
    a, bb = kmeans2(b)
    if a <= 0 or bb < a * 1.3:
        continue
    thr = math.sqrt(a * bb)
    groups[mod].append(''.join('1' if r >= thr else '0' for r in b))

for mod in sorted(groups):
    syms = groups[mod]
    name = {"0": "FSK", "2": "ASK/OOK"}.get(mod, mod)
    print("=== %s: %d captures, symbol lengths %s ===" % (
        name, len(syms), sorted(len(s) for s in syms)))
    if len(syms) < 2:
        continue
    base = max(syms, key=len)
    best = ""
    for other in syms:
        if other is base:
            continue
        m = SequenceMatcher(None, base, other, autojunk=False).find_longest_match(
            0, len(base), 0, len(other))
        if m.size > len(best):
            best = base[m.a:m.a + m.size]
    print("  longest common substring: %d symbols" % len(best))
    print("    %s" % best)
    print("  (a fixed-code fob repeating a frame every ~20-40 ms should share")
    print("   most of a frame here; a rolling code shares only the preamble)")
    print()
