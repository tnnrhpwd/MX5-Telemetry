"""Does the TX carrier actually reach the RX? Measured with NO SPI in the window.

Why the previous test could not answer this: GDO0 picks up SPI crosstalk, and
that crosstalk is LARGER than anything the radio produced (keyed 88 vs spi-only
136 edges over 300 ms). An edge counter that strobes SPI while counting measures
its own SPI traffic. So `TXKEY` was measuring crosstalk.

`RXDIFF <ms>` fixes that:
  DIFF_OFF - TX initialised, carrier OFF, then a capture with NO SPI at all
  DIFF_ON  - carrier ON via ONE strobe, then a capture with NO SPI at all
  DIFF_KEY - carrier keyed slowly (ms per state) while capturing

DIFF_OFF vs DIFF_ON is the clean RF test: nothing but PIND sampling happens in
either window, so any difference is the radio.

DIFF_KEY is judged by RUN LENGTH, not edge count. A carrier the RX actually
demodulates shows up as LONG runs (~ms * 1000 / 11 samples each); crosstalk
shows up as isolated short edges. A capture full of short runs with no long ones
means the RX never saw a carrier, however many edges it contains.

Run with the webapp STOPPED - it owns COM3.
"""
import statistics
import sys
import time

import serial

PORT = "COM3"
BAUD = 115200
MS_PER_STATE = 4          # ms per carrier state, so a ~53 ms capture holds ~13
RUNS = 3
# One captured sample costs ~11 us, so a ms_per_state carrier state should span
# about this many samples if the RX is truly following it.
SAMPLE_US = 11.0


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


def summarize(cap_line):
    f = cap_line.split()
    n, us, hexs = int(f[1]), int(f[2]), f[3]
    samples = nibbles_to_bits(hexs, n)
    if len(samples) < 8:
        return None
    runs = runs_of(samples)
    ones = sum(samples)
    rail = max(ones, n - ones) / float(n)
    longest = max(runs)
    long_runs = [r for r in runs if r * SAMPLE_US > 1000]     # > 1 ms
    return {
        "n": n, "us": us, "rail": rail, "trans": len(runs) - 1,
        "longest": longest, "longest_us": longest * SAMPLE_US,
        "long_runs": sorted(long_runs, reverse=True)[:8],
        "bucket": "%d short, %d mid, %d >1ms" % (
            sum(1 for r in runs if r * SAMPLE_US < 100),
            sum(1 for r in runs if 100 <= r * SAMPLE_US <= 1000),
            len(long_runs)),
        "runs": runs,
        "first": "".join(str(b) for b in samples[:48]),
    }


def run_once(ser, mps):
    ser.reset_input_buffer()
    ser.write(("RXDIFF %d\n" % mps).encode())
    found, want = {}, None
    end = time.time() + 20
    while time.time() < end:
        line = ser.readline().decode("ascii", "ignore").strip()
        if line in ("DIFF_PRE", "DIFF_OFF", "DIFF_ON", "DIFF_KEY"):
            want = line
        elif line.startswith("CAP ") and want:
            found[want] = line
            want = None
        elif line == "DIFF_DONE":
            break
    return found


def main():
    # Optional argument: run at another frequency. The RX is configured by
    # configRadio(), which applies the 315 MHz special-casing (FSCTRL0/TEST0 for
    # VCO selection below 322.88 MHz); the TX is configured by the LIBRARY's
    # setMHZ(), which does not. If the link works at 433.92 MHz and not at
    # 315 MHz, that asymmetry is the bug.
    mhz = float(sys.argv[1]) if len(sys.argv) > 1 else None
    ser = serial.Serial(PORT, BAUD, timeout=0.2)
    quiet, end = time.time(), time.time() + 14
    while time.time() < end:
        if ser.readline():
            quiet = time.time()
        elif time.time() - quiet > 1.5:
            break

    if mhz:
        ser.write(("FREQ %.3f\n" % mhz).encode())
        time.sleep(3.0)          # full retune + VCO recalibration

    # Optional second argument: the TX PKTCTRL0 value. 0x32 is async serial,
    # where the CC1101 keys the carrier from its GDO0 INPUT pin - which on this
    # build is not wired, so nothing is radiated. Values that transmit without a
    # data pin are the point of the test: 0x02 = random TX, 0x04 = infinite.
    if len(sys.argv) > 2:
        ser.write(("TXPKT %s\n" % sys.argv[2]).encode())
        time.sleep(0.6)
        print("TX PKTCTRL0 set to %s" % sys.argv[2])

    if len(sys.argv) > 3 and sys.argv[3] == "state":
        ser.reset_input_buffer()
        ser.write(b"TXSTATE\n")
        print("\nMARCSTATE probe (IDLE=1, TX=13):")
        end = time.time() + 6
        while time.time() < end:
            line = ser.readline().decode("ascii", "ignore").strip()
            if line.startswith("TXSTATE_"):
                print("  " + line)
                if line == "TXSTATE_DONE":
                    break
        ser.close()
        return 0

    # Ask the TX chip to identify itself BEFORE trusting any RF conclusion. If
    # it does not answer, the fault is wiring/power and no register code helps.
    ser.reset_input_buffer()
    ser.write(b"TXV\n")
    print("TX chip identification:")
    end = time.time() + 5
    while time.time() < end:
        line = ser.readline().decode("ascii", "ignore").strip()
        if line.startswith("TX_"):
            print("  " + line)
            if "FREND0" in line:
                break

    print("\nfrequency %s, carrier states of %d ms (~%d samples each if the RX "
          "follows them)" % (("%.3f MHz" % mhz) if mhz else "(boot default)",
                             MS_PER_STATE, MS_PER_STATE * 1000 / SAMPLE_US))

    offs, ons, keys, pres = [], [], [], []
    for i in range(RUNS):
        found = run_once(ser, MS_PER_STATE)
        if len(found) < 4:
            print("run %d: got %s" % (i + 1, sorted(found)))
            continue
        o = summarize(found["DIFF_OFF"])
        n = summarize(found["DIFF_ON"])
        k = summarize(found["DIFF_KEY"])
        p = summarize(found["DIFF_PRE"])
        offs.append(o)
        ons.append(n)
        keys.append(k)
        pres.append(p)
        print("\nrun %d" % (i + 1))
        for tag, r in (("PRE", p), ("OFF", o), ("ON ", n), ("KEY", k)):
            print("  %s  rail %5.1f%%  trans %4d  longest %7.1f us  runs: %s"
                  % (tag, 100 * r["rail"], r["trans"], r["longest_us"],
                     r["bucket"]))

    if not offs:
        print("\nno usable runs")
        ser.close()
        return 1

    # Did touching the TX break the receiver? PRE is captured before tx.Init()
    # runs at all, so a PRE/OFF difference is the TX init upsetting the RX.
    pre_rail = statistics.median(p["rail"] for p in pres)
    pre_trans = statistics.median(p["trans"] for p in pres)
    off_rail = statistics.median(o["rail"] for o in offs)
    off_trans = statistics.median(o["trans"] for o in offs)
    print("\n=== did tx.Init() disturb the RX? ===")
    print("before TX init : rail %.1f%%  transitions %.0f" % (100 * pre_rail, pre_trans))
    print("after  TX init : rail %.1f%%  transitions %.0f" % (100 * off_rail, off_trans))
    if abs(pre_rail - off_rail) > 0.05 and pre_trans > 5:
        print("-> YES: the receiver is quiet before the TX init and railed after.")
        print("   applyAsyncConfig() after tx.Init() is still needed, or the TX")
        print("   init has to happen before the RX is configured.")
    else:
        print("-> no evidence that tx.Init() changed the RX state.")

    r_off = statistics.median(o["rail"] for o in offs)
    r_on = statistics.median(n["rail"] for n in ons)
    t_off = statistics.median(o["trans"] for o in offs)
    t_on = statistics.median(n["trans"] for n in ons)
    print("\n=== RF test (no SPI in either window) ===")
    print("carrier OFF: rail %.1f%%  transitions %.0f" % (100 * r_off, t_off))
    print("carrier ON : rail %.1f%%  transitions %.0f" % (100 * r_on, t_on))
    if abs(r_on - r_off) > 0.05 or (t_off > 0 and t_on > 2 * t_off):
        print("-> the RX DOES notice the carrier. The RF path works.")
    else:
        print("-> NO DIFFERENCE between carrier on and carrier off.")
        print("   With no SPI in either window, that means the TX carrier is not")
        print("   reaching the RX's demodulator at all.")

    exp = MS_PER_STATE * 1000 / SAMPLE_US
    # A long run only counts if it is ABOUT the expected carrier-state length AND
    # there are several of them. A flat capture contains ONE enormous run, which
    # is how the previous version of this check returned "the RX FOLLOWS the
    # modulation" for a capture that was 100 % rail - the same degenerate-input
    # trap as the earlier metrics.
    per_capture = int(52800 / exp)
    counts = [sum(1 for r in k["runs"] if 0.4 * exp <= r <= 2.5 * exp)
              for k in keys]
    best = max(counts) if counts else 0
    print("\n=== modulation test (run LENGTH, not edge count) ===")
    print("runs near the expected carrier-state length: %d (expected ~%d per "
          "capture)" % (best, per_capture))
    if best >= 4:
        print("-> the RX FOLLOWS the modulation: carrier states of the right")
        print("   length appear as runs, which crosstalk cannot produce.")
    else:
        print("-> the RX does NOT follow the modulation - no runs of the right")
        print("   length. Any edges present are SPI crosstalk, not a demodulated")
        print("   carrier; one enormous run is just a railed capture.")
    ser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
