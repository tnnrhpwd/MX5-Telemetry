"""Does a keyed carrier from our TX reach our RX's demodulator?

The loopback calibration could not tell WHY it failed: a railed capture is what
you get both when the TX radiates nothing AND when the RX is desensitised. A
level cannot distinguish those, because with no signal the OOK demod output sits
at a single level anyway.

`TXKEY <bit_us> <ms> <txon>` strobes a square-wave carrier for `ms` while
counting GDO0 edges, so the question becomes *does the output TOGGLE*. The same
loop with txon=0 sends no strobes at all, giving the silent control measured in
the same instant - that is what makes a low count attributable.

Interpretation:
  keyed >> silent  -> the TX is radiation-linked to a working RX slicer; any
                      remaining failure is demod/decoding, not the radio link.
  keyed ~= silent  -> nothing arrives. Cross-check against a real fob press: if
                      a fob press makes the level chart spike while this reads
                      zero, the TX side is at fault.

Run with the webapp STOPPED - it owns COM3.
"""
import statistics
import sys
import time

import serial

PORT = "COM3"
BAUD = 115200
BIT_US = 480          # ~2 kbps, the rate txFobBurst has always used
MS = 300
REPEATS = 3
PA = 12               # maximum TX power: give the link every chance


def read_result(ser, cmd, timeout=10.0):
    ser.reset_input_buffer()
    ser.write((cmd + "\n").encode())
    end = time.time() + timeout
    while time.time() < end:
        line = ser.readline().decode("ascii", "ignore").strip()
        if line.startswith("TXKEY_EDGES "):
            f = line.split()
            return int(f[1])
    return None


def main():
    # Optional argument: test at another frequency. The radio board is a
    # 433-tuned E07-M1101D-433 running 315 MHz antennas, so comparing the two
    # bands separates "the demod is bad" from "the antenna is mismatched".
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
    if PA is not None:
        ser.write(("TXPA %d\n" % PA).encode())
        time.sleep(0.3)
    print("frequency %s, TX power index %s, keyed carrier %d us on/off for %d ms\n"
          % (("%.3f MHz" % mhz) if mhz else "(boot default)", PA, BIT_US, MS))

    silent, keyed, spi = [], [], []
    for i in range(REPEATS):
        s = read_result(ser, "TXKEY %d %d 0" % (BIT_US, MS))
        k = read_result(ser, "TXKEY %d %d 1" % (BIT_US, MS))
        p = read_result(ser, "TXKEY %d %d 2" % (BIT_US, MS))
        if s is None or k is None or p is None:
            print("run %d: no response" % (i + 1))
            continue
        silent.append(s)
        keyed.append(k)
        spi.append(p)
        print("run %d: silent %5d   keyed %5d   spi-only %5d   edges"
              % (i + 1, s, k, p))

    if not silent:
        print("\nno usable runs")
        ser.close()
        return 1

    ms, mk, mp = (statistics.median(silent), statistics.median(keyed),
                  statistics.median(spi))
    print("\nmedians: silent %.0f   keyed %.0f   spi-only %.0f" % (ms, mk, mp))
    # The loop toggles the carrier once per iteration, so a perfect link gives
    # one RX edge per BIT_US of keying - NOT two. (An earlier version of this
    # script said 2x and so under-stated the shortfall.)
    print("expected from a working link: ~%d edges for %d ms at %d us"
          % (MS * 1000 // BIT_US, MS, BIT_US))
    # THE key comparison: keyed vs the SPI-MATCHED control. Both send the same
    # SPI traffic at the same instants, and both do the same tx.Init/setMHZ/
    # setPA burst; only the keyed one changes the carrier. If they agree, the
    # edges are crosstalk onto GDO0 rather than RF - which is also what would
    # explain the count being identical at every TX power level.
    if mk > mp * 2 and mk > ms * 4:
        print("-> the edges are RF: keying the carrier adds edges that")
        print("   matched SPI traffic alone does not.")
    elif mp > ms * 2 and abs(mk - mp) < 0.4 * max(mk, mp):
        print("-> NO RF EVIDENCE: the keyed count matches the SPI control.")
        print("   The edges come from SPI crosstalk onto the GDO0 line, not")
        print("   from the radio - and any 'the link works' result from the")
        print("   silent-vs-keyed comparison alone is explained by SPI.")
    else:
        print("-> inconclusive: keyed %.0f, spi-only %.0f, silent %.0f"
              % (mk, mp, ms))

    # How fast can the pair actually key? If the count tracks 300000/bit_us the
    # link follows the instruction; if it PLATEAUS at a fixed number, that
    # plateau is the real achievable keying rate - and any bit pattern sent
    # faster than it is smeared no matter how good the decoder is.
    print("\nkeying-rate sweep (%d ms of keying; ideal = 300000/bit_us edges):" % MS)
    print("%9s %9s %8s %8s %8s" % ("bit_us", "ideal", "keyed", "silent", "captured"))
    plateau = []
    for bu in (480, 1000, 2500, 5000, 10000, 25000):
        k = read_result(ser, "TXKEY %d %d 1" % (bu, MS))
        s = read_result(ser, "TXKEY %d %d 0" % (bu, MS))
        if k is None or s is None:
            print("%9d %9s %8s" % (bu, "-", "no data"))
            continue
        ideal = MS * 1000 // bu
        frac = (k - s) / float(ideal) if ideal else 0.0
        print("%9d %9d %8d %8d %7.0f%%" % (bu, ideal, k, s, 100 * frac))
        plateau.append((bu, k, s, frac))

    if plateau:
        fast = [p for p in plateau if p[0] <= 1000]
        slow = [p for p in plateau if p[0] >= 10000]
        if slow and slow[-1][3] > 0.7:
            print("\n-> the link FOLLOWS the keying even at very slow rates, so")
            print("   the ceiling at fast rates is a TRACKING limit, not a dead link.")
        elif fast and slow and abs(fast[0][1] - slow[-1][1]) < 0.3 * fast[0][1]:
            print("\n-> the edge count PLATEAUS: the pair cannot key faster than")
            print("   ~%d transitions per %d ms (~%.2f ms per state), whatever we ask for."
                  % (fast[0][1], MS, 1000.0 * MS / max(1, fast[0][1])))

    ser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
