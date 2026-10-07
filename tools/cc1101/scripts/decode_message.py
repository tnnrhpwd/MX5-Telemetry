"""Read the fob's MESSAGE by finding the period that repeats inside one capture.

Cross-capture alignment (find_frame.py) is the wrong tool here: the captures
vary from 12 to 281 runs, so most pairs cannot overlap meaningfully and the
median match is dominated by short ones. A repeating remote repeats its frame
WITHIN a burst, though - so the period can be found from a single capture by
autocorrelation, with no alignment at all.

Why the period matters more than the bits:
  a LARGE period that matches near 100 %  -> the whole frame repeats, so the
      code is FIXED and can be used to identify one specific fob.
  only a SMALL period matching           -> just the alternating preamble
      repeats, i.e. the payload changes every repeat = ROLLING code, and no
      amount of decoding will let one fob be told from another.

Autocorrelation caveat handled below: an alternating preamble is periodic with
L=2, 4, 6 ... so small lags score well on the preamble alone. Every candidate is
therefore reported with its match fraction, and the frame has to beat that by
being long AND complete.
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
    runs, cur = [], 1
    for i in range(1, len(x)):
        if x[i] == x[i - 1]:
            cur += 1
        else:
            runs.append(cur)
            cur = 1
    runs.append(cur)
    return runs


def stretch(rr, gap=500):
    """Longest stretch of runs not broken by a real inter-frame gap."""
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


def to_symbols(runs):
    """Runs -> short/long symbols, split at the geometric mean of the two modes."""
    if len(runs) < 4:                  # nothing to split; a stretch can be empty
        return None, None, None
    s = sorted(runs)
    half = len(s) // 2
    lo = statistics.median(s[:half])
    hi = statistics.median(s[half:])
    if lo <= 0 or hi <= 0:
        return None, None, None
    thr = (lo * hi) ** 0.5
    return "".join("0" if r < thr else "1" for r in runs), lo, hi


def period_scores(sym, lo=16, hi=400):
    """Match fraction for every candidate lag."""
    out = []
    for L in range(lo, hi + 1):
        n = len(sym) - L
        if n < 40:                     # need real overlap to mean anything
            break
        m = sum(1 for i in range(n) if sym[i] == sym[i + L]) / float(n)
        out.append((L, m))
    return out


def slide_match(stream, template):
    """Best match of `template` anywhere in `stream`, plus its offset.

    Sliding a fixed-length template is the real question: a bare majority vote
    across captures counts a 2-of-4 split as agreement, which is almost
    automatic and hid the fact that the extracted periods did not actually
    agree. A template either matches in the stream or it does not.
    """
    if len(stream) < len(template):
        return None, None
    best, boff = 0.0, 0
    for off in range(len(stream) - len(template) + 1):
        m = sum(1 for j in range(len(template))
                if stream[off + j] == template[j]) / float(len(template))
        if m > best:
            best, boff = m, off
    return best, boff


def shuffled(seq, seed=20261007):
    import random
    s = list(seq)
    random.Random(seed).shuffle(s)
    return "".join(s)


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
    print("=" * 74)
    print("%s -- %d captures" % (tag, len(seqs)))
    strong = []
    for idx, st in enumerate(seqs[:8]):
        sym, lo, hi = to_symbols(st)
        if sym is None or len(sym) < 80:
            continue
        sc = period_scores(sym)
        if not sc:
            continue
        L, m = max(sc, key=lambda t: t[1])
        # How much better than the best SMALL lag, i.e. than the preamble alone?
        small = max((mm for ll, mm in sc if ll <= 12), default=0.0)
        print("\n  capture %d: %d symbols, short~%.0f long~%.0f runs"
              % (idx + 1, len(sym), lo, hi))
        print("    best lag %3d matches %.0f%%   (preamble-only lag <=12: %.0f%%)"
              % (L, 100 * m, 100 * small))
        if m >= 0.8 and L >= 30:
            base = 0
            best_off = 0
            for off in range(min(L, len(sym) - L)):
                seg = sym[off:off + L]
                mm = sum(1 for i in range(L) if sym[i + off] == sym[i]) / float(L)
                if mm > base:
                    base, best_off = mm, off
            period = sym[best_off:best_off + L]
            print("    PERIOD (%d symbols, %.0f%% self-consistent):" % (L, 100 * base))
            for i in range(0, len(period), 60):
                print("      %s" % period[i:i + 60])
            strong.append(period)

    if strong:
        ref = strong[0]
        print("\n  TEMPLATE MATCH - is the SAME message in every capture?")
        print("  template: the %d-symbol period from the longest capture" % len(ref))
        print("  %-8s %9s %9s   %s" % ("capture", "match", "shuffled", "verdict"))
        hits = 0
        for i, st in enumerate(seqs):
            sym, lo, hi = to_symbols(st)
            if sym is None or len(sym) < len(ref):
                continue
            m, off = slide_match(sym, ref)
            ctl, _ = slide_match(sym, shuffled(ref))
            if m is None:
                continue
            verdict = "SAME message" if (m >= 0.85 and m - ctl > 0.15) else \
                      "different" if m - ctl <= 0.15 else "partial"
            if verdict == "SAME message":
                hits += 1
            print("  %-8d %8.0f%% %8.0f%%   %s" % (i + 1, 100 * m, 100 * ctl,
                                                   verdict))
        print("\n  %d of %d captures carry the SAME message." % (hits, len(seqs)))
        if hits >= 2:
            print("  -> the fob sends a FIXED code: it can identify this exact")
            print("     fob, and a different Mazda fob will not match it.")
            print("\n  MESSAGE (%d symbols, short=0 long=1):" % len(ref))
            for i in range(0, len(ref), 60):
                print("    %s" % ref[i:i + 60])
        else:
            print("  -> the payload CHANGES between captures: ROLLING code, so")
            print("     no stored message can recognise one fob from another.")
    else:
        print("\n  no period repeated near-identically -> no fixed message here")
