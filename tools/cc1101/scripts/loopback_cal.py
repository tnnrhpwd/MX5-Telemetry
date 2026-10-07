"""Loopback calibration: can the RX reproduce a bitstream we generated ourselves?

`TXLOOP` has the TX module transmit a KNOWN 16-byte OOK frame while sampling the
RX's GDO0, exercising the whole chain (TX -> air -> RX -> demod -> sampler) with
no real fob involved:

    AA AA AA AA AA AA AA AA   2D D4   01 02 04 08 10 20
    \\_______ 64-bit ________/  sync   \\____ 48 bits _____/
             alternating                 known payload

That shape is deliberate - a long alternating preamble then a payload - because
it is what a real fob sends. If the receiver chain is faithful the capture MUST
reproduce those 128 bits per repetition. If it does not, no amount of decoder
work will ever read a real fob, and the fault is the radio, not the algorithm.

The TX bit period is ~110 us (~9 kbps, close to the fob's ~10 kbps) and the
capture samples at ~11 us, so one transmitted bit is ~10 captured samples.

Sweeps the TX power index because two modules on one desk SATURATE the RX at
full power - the slicer rails high (all-0xFF captures) and the test is
meaningless. The clean operating point this finds is also the level to replay a
real fob at.

Run with the webapp STOPPED - it owns COM3.
"""
import random
import statistics
import sys
import time
from collections import Counter

import serial

PORT = "COM3"
BAUD = 115200
# (captured samples per transmitted bit, matching RX data rate). Each sample is
# ~11 us, so spb=10 is a ~110 us bit (~9 kbps) and spb=45 is ~495 us (~2 kbps).
# txFobBurst, which is known to make the RX spike, uses ~480 us bits - so if the
# carrier can only be keyed at those speeds, a 10 kbps fob can never be mirrored.
BIT_SWEEP = [(10, 10000), (25, 3600), (45, 2000), (70, 1300)]

FRAME = bytes([0xAA] * 8 + [0x2D, 0xD4, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20])
EXPECTED = [(b >> k) & 1 for b in FRAME for k in range(7, -1, -1)]

# A fixed shuffle of the pattern, used as the shape-null control.
_rng = random.Random(20261006)
SHUFFLED = EXPECTED[:]
_rng.shuffle(SHUFFLED)


def nibbles_to_bits(hexs, n):
    out = []
    for ch in hexs:
        v = int(ch, 16)
        for k in (3, 2, 1, 0):
            out.append((v >> k) & 1)
    return out[:n]


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


def best_match(rec, pattern):
    """Best fraction of matching bits over every alignment of `pattern`.

    This is a MAXIMUM over ~128 offsets, so on its own it sits well above
    chance. It is only meaningful next to the same statistic computed on a
    shuffled pattern AND on a flat capture - see `constant_control`.
    """
    L = len(pattern)
    tiled = pattern * (len(rec) // L + 2)
    best = 0.0
    for off in range(L):
        seg = tiled[off:off + len(rec)]
        if len(seg) < len(rec):
            break
        m = sum(1 for a, b in zip(rec, seg) if a == b) / len(rec)
        if m > best:
            best = m
    return best


def constant_control(stream):
    """What a RAILED capture scores under the same statistic.

    The expected pattern is 64.8% zeros, so a capture that is one flat level
    matches it ~0.65 by construction - a number that looks like partial success
    and means nothing. Every match must beat this before it means anything.
    """
    dom = 1 if sum(stream) * 2 >= len(stream) else 0
    return best_match([dom] * len(stream), EXPECTED)


def read_pair(ser, cmd, timeout=14.0):
    """Send `cmd` and return (baseline_cap, tx_cap).

    txLoopback emits LB_BASE / a CAP / LB_TX / a CAP: the first capture is taken
    with the TX untouched, the second during transmission. The first is the
    control that tells us whether the rail is the RX's own state.
    """
    ser.reset_input_buffer()
    ser.write((cmd + "\n").encode())
    caps, seg = [], None
    end = time.time() + timeout
    while time.time() < end:
        line = ser.readline().decode("ascii", "ignore").strip()
        if line == "LB_BASE":
            seg = "base"
        elif line == "LB_TX":
            seg = "tx"
        elif line.startswith("CAP "):
            caps.append((seg, line))
            if seg == "tx":
                break
    base = next((c for s, c in caps if s == "base"), None)
    tx = next((c for s, c in caps if s == "tx"), None)
    return base, tx


def analyse(cap_line):
    f = cap_line.split()
    n, us, hexs = int(f[1]), int(f[2]), f[3]
    samples = nibbles_to_bits(hexs, n)
    runs = runs_of(samples)
    if len(runs) < 8:
        return {"railed": True, "transitions": len(runs) - 1, "us": us}

    # One transmitted bit is ~10 captured samples, so the shortest run (a
    # single bit) is the natural unit. Use the median: in this frame the 64
    # preamble bits alternate, so most runs ARE one bit.
    unit = statistics.median(runs)

    # Expand back to one bit per transmitted bit.
    rec, lvl = [], samples[0]
    for r in runs:
        rec.extend([lvl] * max(1, int(round(r / unit))))
        lvl ^= 1

    # OOK slicers may be inverted, so score BOTH polarities - and score each
    # against controls built from the SAME stream. Scoring the match on one
    # polarity and the control on the other is how a railed capture produced a
    # fake 0.28 "margin" here and read as "partly readable".
    cands = []
    for name, stream in (("normal", rec), ("inverted", [1 - b for b in rec])):
        cands.append((best_match(stream, EXPECTED), name, stream))
    match, pol, best_stream = max(cands, key=lambda c: c[0])
    return {
        "railed": False, "n": n, "us": us, "transitions": len(runs) - 1,
        "unit": unit, "unit_samples": len(rec),
        "match": match, "pol": pol,
        "shuffle": best_match(best_stream, SHUFFLED),
        "railed_ctl": constant_control(best_stream),
        "rail_frac": max(sum(samples), len(samples) - sum(samples)) / len(samples),
        "rec": best_stream,
    }


def main():
    ser = serial.Serial(PORT, BAUD, timeout=0.2)
    # Opening the port toggles DTR and RESETS the Nano; boot runs the full radio
    # init (2 x SetRx plus 500 + 1000 ms settles), so wait for the board to go
    # quiet before talking to it.
    quiet, end = time.time(), time.time() + 14
    while time.time() < end:
        if ser.readline():
            quiet = time.time()
        elif time.time() - quiet > 1.5:
            break
    print("board booted, starting sweep\n")

    print("%6s %8s %9s %9s %6s %7s %8s %7s  %s" % (
        "spb", "bit_us", "base_rail", "tx_rail", "trans", "match", "railedctl",
        "margin", "verdict"))
    results = []
    # PA is fixed at the default 10. The PA sweep (0, 2 ... 12) showed no effect
    # on fidelity - a continuously-on carrier rails the RX at EVERY power - so
    # the bit period is the variable that matters.
    ser.write(b"TXPA 10\n")
    time.sleep(0.3)
    for spb, drate in BIT_SWEEP:
        # The RX data rate must match the TX bit rate or the slicer cannot track
        # the envelope, and a mismatch would look like a TX fault.
        ser.write(("DRATE %d\n" % drate).encode())
        time.sleep(1.4)          # full re-config + double SetRx settle
        base_cap, tx_cap = read_pair(ser, "TXLOOP %d" % spb)
        if not tx_cap:
            print("%6d  no CAP line" % spb)
            continue
        base = analyse(base_cap) if base_cap else None
        r = analyse(tx_cap)
        base_txt = ("%.1f%%" % (100 * base["rail_frac"])
                    if base and not base["railed"] else "-")
        if r["railed"]:
            print("%6d  tx RAILED, only %d transitions (baseline %s)"
                  % (spb, r["transitions"], base_txt))
            continue
        margin = r["match"] - max(r["railed_ctl"], r["shuffle"])
        if r["transitions"] < 50:
            verdict = "RAILED: no payload present"
        elif margin > 0.15 and r["match"] > 0.85:
            verdict = "FAITHFUL"
        elif margin > 0.15:
            verdict = "partly readable"
        else:
            verdict = "GARBAGE: no better than a flat capture"
        print("%6d %8.0f %9s %8.1f%% %6d %7.2f %8.2f %7.2f  %s %s" % (
            spb, spb * 11.0, base_txt, 100 * r["rail_frac"], r["transitions"],
            r["match"], r["railed_ctl"], margin, verdict, "(%s)" % r["pol"]))
        r["spb"] = spb
        r["base_rail"] = base["rail_frac"] if base and not base["railed"] else None
        results.append(r)

    if results:
        best = max(results, key=lambda r: r["match"] - max(r["railed_ctl"], r["shuffle"]))
        print("\nbest: spb=%d (~%.0f us/bit)  match %.2f  railed-control %.2f  shuffled-control %.2f  polarity %s" % (
            best["spb"], best["spb"] * 11.0, best["match"], best["railed_ctl"],
            best["shuffle"], best["pol"]))
        print("\nexpected (128 bits/repeat, AA preamble then 2DD4 010204081020):")
        for i in range(0, len(EXPECTED), 64):
            print("  exp %s" % "".join(str(b) for b in EXPECTED[i:i + 64]))
        print("received (best spb, first 256 bits):")
        rec = best["rec"][:256]
        for i in range(0, len(rec), 64):
            print("  rec %s" % "".join(str(b) for b in rec[i:i + 64]))
    else:
        print("\nno usable captures at any power level")
    ser.close()


if __name__ == "__main__":
    sys.exit(main())
