#!/usr/bin/env python3
"""
CC1101 capture analyzer
=======================
Reads raw capture lines from the CC1101 capture sketch:

    CAP <numSamples> <microsTaken> <hexbytes...>

and attempts to find, clock, and Manchester-decode TPMS-like frames so we can
read the sensor ID (and later pressure / temperature).

Usage:
    python analyze_capture.py --selftest          # verify the decoder on synthetic data
    python analyze_capture.py capture.txt         # analyze a saved capture log
    echo 'CAP 4800 19200 0f3c81...' | python analyze_capture.py
"""
import sys
from collections import Counter

# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_cap_line(line):
    line = line.strip()
    if not line or not line.upper().startswith("CAP"):
        return None
    parts = line.split()
    if len(parts) < 4:
        return None
    try:
        num_samples = int(parts[1])
        micros = int(parts[2])
    except ValueError:
        return None
    hexstr = "".join(parts[3:])
    return num_samples, micros, hexstr


def unpack_samples(hexstr):
    """Unpack 8-samples-per-byte (LSB = oldest) into a list of 0/1 levels."""
    bits = []
    try:
        data = bytes.fromhex(hexstr)
    except ValueError:
        return []
    for byte in data:
        for i in range(8):
            bits.append((byte >> i) & 1)
    return bits


def sample_rate_hz(num_samples, micros):
    if micros <= 0:
        return 0.0
    return num_samples / (micros * 1e-6)


# ---------------------------------------------------------------------------
# Clock recovery
# ---------------------------------------------------------------------------

def edges(bits):
    return [i for i in range(1, len(bits)) if bits[i] != bits[i - 1]]


def edge_intervals(bits):
    e = edges(bits)
    return [e[i + 1] - e[i] for i in range(len(e) - 1)]


def estimate_half_bit(bits):
    """Estimate the Manchester half-bit period (samples) from edge spacing.

    A Manchester signal has edges at the half-bit period T and at the bit
    period 2T. Noise contributes scattered intervals. We find the dominant
    edge spacing (with +-1 jitter tolerance); if half of it is also strongly
    present, the dominant spacing is 2T and the half-bit is T, otherwise the
    dominant spacing is already T.
    """
    iv = edge_intervals(bits)
    if not iv:
        return None
    hist = Counter(d for d in iv if 4 <= d <= 120)
    if not hist:
        return None

    def local(d):
        return sum(c for x, c in hist.items() if d - 1 <= x <= d + 1)

    keys = sorted(hist)
    best_d, best_c = keys[0], local(keys[0])
    for d in keys:
        c = local(d)
        if c > best_c:
            best_d, best_c = d, c
    if best_c < 8:
        return None

    half = best_d // 2
    if local(half) >= best_c // 3:
        return half
    return best_d


def find_signal_region(bits, T):
    """Return (start, end) of the longest run of edges spaced ~T or ~2T."""
    e = edges(bits)
    if not e:
        return None
    best = (0, 0)
    run_start = e[0]
    prev = e[0]

    def in_clock(d):
        return (abs(d - T) <= max(2, T // 3)) or (abs(d - 2 * T) <= max(2, (2 * T) // 3))

    for pos in e[1:]:
        d = pos - prev
        if in_clock(d):
            prev = pos
            continue
        if prev - run_start > best[1] - best[0]:
            best = (run_start, prev)
        run_start = pos
        prev = pos
    if prev - run_start > best[1] - best[0]:
        best = (run_start, prev)
    return best


# ---------------------------------------------------------------------------
# Manchester decoding
# ---------------------------------------------------------------------------

def manchester_decode(bits, B, phase):
    """Decode with bit period B and a bit-boundary phase.

    Returns (decoded_bits, violation_count). Each bit is sampled at the centre
    of its first half; a missing mid-bit transition (s1 == s2) is a violation.
    The first-half level IS the bit value for IEEE Manchester; the complement
    is G.E. Thomas Manchester.
    """
    n = len(bits)
    out = []
    violations = 0
    k = 0
    q1 = B // 4
    q3 = (3 * B) // 4
    while phase + k * B + q3 < n:
        c1 = phase + k * B + q1
        c2 = phase + k * B + q3
        if bits[c1] == bits[c2]:
            violations += 1
        out.append(bits[c1])
        k += 1
    return out, violations


def best_phase(bits, B):
    """Sweep the bit-boundary phase; return (phase, decoded_bits, violations)."""
    best = None
    best_phase = 0
    for phase in range(0, B, max(1, B // 8)):
        dec, viol = manchester_decode(bits, B, phase)
        if best is None or viol < best[2]:
            best = (phase, dec, viol)
    return best


def bits_to_bytes(bits):
    out = []
    for i in range(0, len(bits) - 7, 8):
        b = 0
        for j in range(8):
            b = (b << 1) | bits[i + j]
        out.append(b)
    return out


def find_frame(bytes_list):
    """Return (preamble_len, payload) for the first 0xAA/0x55 preamble run."""
    for i in range(len(bytes_list) - 3):
        b = bytes_list[i]
        if b in (0xAA, 0x55) and bytes_list[i + 1] == b and bytes_list[i + 2] == b:
            j = i
            while j < len(bytes_list) and bytes_list[j] == b:
                j += 1
            return j - i, bytes_list[j:]
    return None


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def analyze_bits(bits, micros):
    rate = sample_rate_hz(len(bits), micros)
    if len(bits) < 16:
        return {"rate": rate, "error": "capture too short"}

    T = estimate_half_bit(bits)
    if T is None:
        return {"rate": rate, "error": "no consistent clock found"}

    B = 2 * T
    region = find_signal_region(bits, T)
    if region is None or region[1] - region[0] < 4 * B:
        return {"rate": rate, "T": T, "baud": rate / B, "error": "no signal region"}

    start, end = region
    slice_bits = bits[start:end]
    phase, dec, viol = best_phase(slice_bits, B)

    ieee = bits_to_bytes(dec)
    thomas = bits_to_bytes([1 - b for b in dec])

    result = {
        "rate": rate,
        "T": T,
        "baud": rate / B,
        "region": (start, end),
        "violations": viol,
        "ieee_bytes": ieee,
        "thomas_bytes": thomas,
    }

    for name, bytes_list in (("ieee", ieee), ("thomas", thomas)):
        frame = find_frame(bytes_list)
        if frame:
            result[name + "_preamble_len"] = frame[0]
            result[name + "_payload"] = frame[1]
    return result


def fmt_bytes(bytes_list, per_line=16):
    if not bytes_list:
        return "(none)"
    parts = ["%02X" % b for b in bytes_list]
    lines = []
    for i in range(0, len(parts), per_line):
        lines.append("  " + " ".join(parts[i:i + per_line]))
    return "\n".join(lines)


def report(analyzed):
    if "error" in analyzed:
        print("error: %s" % analyzed["error"])
        if "rate" in analyzed:
            print("  sample rate: %.0f Hz" % analyzed["rate"])
        return
    print("  sample rate : %.0f Hz" % analyzed["rate"])
    print("  half-bit T  : %d samples" % analyzed["T"])
    print("  data rate   : ~%.0f baud" % analyzed["baud"])
    print("  signal span : samples %d..%d (%d samples)"
          % (analyzed["region"][0], analyzed["region"][1],
             analyzed["region"][1] - analyzed["region"][0]))
    print("  violations  : %d" % analyzed["violations"])
    print("  decoded (IEEE Manchester, bit = first-half level):")
    print(fmt_bytes(analyzed["ieee_bytes"]))
    if "ieee_payload" in analyzed:
        print("  payload after preamble (IEEE):")
        print(fmt_bytes(analyzed["ieee_payload"]))
    print("  decoded (G.E. Thomas, bit = complement):")
    print(fmt_bytes(analyzed["thomas_bytes"]))
    if "thomas_payload" in analyzed:
        print("  payload after preamble (Thomas):")
        print(fmt_bytes(analyzed["thomas_payload"]))


# ---------------------------------------------------------------------------
# Synthetic self-test
# ---------------------------------------------------------------------------

def pack_samples(bits):
    """Pack levels into bytes, 8 samples/byte, LSB = oldest (matches firmware)."""
    out = bytearray()
    for i in range(0, len(bits) - 7, 8):
        b = 0
        for j in range(8):
            b |= bits[i + j] << j
        out.append(b)
    return out


def manchester_encode_bytes(data_bytes):
    """IEEE Manchester: 1 -> [1,0], 0 -> [0,1]. Returns list of levels."""
    levels = []
    for byte in data_bytes:
        for i in range(7, -1, -1):
            bit = (byte >> i) & 1
            if bit:
                levels += [1, 0]
            else:
                levels += [0, 1]
    return levels


def selftest():
    import random
    rate = 250000.0
    baud = 9600.0
    T = rate / (2.0 * baud)          # half-bit in samples (~13)
    payload = [0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC, 0xDE, 0xF0]
    frame_bytes = [0xAA] * 16 + payload
    levels = manchester_encode_bytes(frame_bytes)

    bits = []
    for lvl in levels:
        bits += [lvl] * int(round(T))

    noise = [random.randint(0, 1) for _ in range(300)]
    full = noise + bits + noise

    packed = pack_samples(full)
    num_samples = len(full)
    micros = int(round(num_samples / rate * 1e6))
    hexstr = packed.hex()

    res = analyze_bits(unpack_samples(hexstr), micros)
    print("SELF-TEST (synthetic 9600 baud IEEE Manchester, payload %s):"
          % " ".join("%02X" % b for b in payload))
    report(res)

    ok = ("ieee_payload" in res and
          res["ieee_payload"][:len(payload)] == payload)
    if ok:
        print("SELF-TEST: PASS (recovered payload)")
    else:
        print("SELF-TEST: FAIL (could not recover payload)")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def main():
    if "--selftest" in sys.argv:
        selftest()
        return

    lines = []
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        with open(sys.argv[1], "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    else:
        lines = sys.stdin.readlines()

    caps = []
    for ln in lines:
        parsed = parse_cap_line(ln)
        if parsed:
            caps.append(parsed)

    if not caps:
        print("no CAP lines found")
        return

    print("analyzing %d capture(s)\n" % len(caps))
    all_payloads = []
    silent = 0
    for idx, (num_samples, micros, hexstr) in enumerate(caps):
        bits = unpack_samples(hexstr)
        if not bits:
            print("CAP %d: bad hex" % idx)
            continue
        if len(set(bits)) == 1:
            # All-zero (or all-one) capture: receiver idle, no signal. Skip it.
            silent += 1
            continue
        print("CAP %d (%d samples):" % (idx, len(bits)))
        res = analyze_bits(bits, micros)
        report(res)
        print()
        for key in ("ieee_payload", "thomas_payload"):
            if key in res:
                all_payloads.append((idx, key, res[key]))
    if silent:
        print("(%d idle captures with no signal skipped)" % silent)

    # Stable-byte diff across frames (candidate sensor ID).
    if len(all_payloads) >= 2:
        print("stable bytes across %d payloads (candidate sensor ID region):"
              % len(all_payloads))
        lens = [len(p) for _, _, p in all_payloads]
        n = min(lens)
        for i in range(n):
            vals = {p[i] for _, _, p in all_payloads}
            if len(vals) == 1:
                v = all_payloads[0][2][i]
                print("  byte %2d : 0x%02X (constant)" % (i, v))
            else:
                print("  byte %2d : varies (%s)"
                      % (i, ", ".join("0x%02X" % p[i] for _, _, p in all_payloads)))


if __name__ == "__main__":
    main()
