"""Sweep the RX data rate and measure how cleanly each one reproduces the fob."""
import serial
import time
import math
import statistics
from collections import Counter

RATES = [10000, 19200, 38400, 76800]
SECONDS_PER_RATE = 11

s = serial.Serial('COM3', 115200, timeout=0.5)
time.sleep(2.5)
s.reset_input_buffer()


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


print("=== RX data-rate sweep ===\n")
for rate in RATES:
    s.write(("DRATE %d\n" % rate).encode())
    time.sleep(0.3)
    s.reset_input_buffer()
    caps = []
    t0 = time.time()
    while time.time() - t0 < SECONDS_PER_RATE:
        l = s.readline().decode('utf-8', 'ignore').strip()
        if l.startswith('CAP '):
            caps.append(l)

    shorts, longs, pulses, active, pre = [], [], [], [], 0
    for l in caps:
        p = l.split()
        if len(p) < 4:
            continue
        per = float(p[2]) / float(p[1])
        rr = runs_of(bits(p[3]))
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
        shorts.append(a * per)
        longs.append(bb * per)
        pulses.append(len(b))
        active.append(sum(b) * per)
        thr = math.sqrt(a * bb)
        sym = ''.join('1' if r >= thr else '0' for r in b)
        if '101010' in sym or '010101' in sym:
            pre += 1

    print("DRATE %6d: captures=%2d usable=%2d" % (rate, len(caps), len(pulses)))
    if pulses:
        print("    pulses/burst  median %3d  (range %d-%d)"
              % (statistics.median(pulses), min(pulses), max(pulses)))
        print("    short pulse   median %3.0f us  spread %3.0f us"
              % (statistics.median(shorts), statistics.pstdev(shorts)))
        print("    long pulse    median %3.0f us  spread %3.0f us"
              % (statistics.median(longs), statistics.pstdev(longs)))
        print("    active/burst  median %4.1f ms" % (statistics.median(active) / 1000.0))
        print("    had preamble  %d/%d" % (pre, len(pulses)))
        print("    pulse counts  %s" % Counter(pulses).most_common(8))
    print()
s.close()
