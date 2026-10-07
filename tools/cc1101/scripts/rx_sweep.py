"""Sweep RX registers against a measurable objective: does the output FOLLOW a keyed carrier?

`tx_check.py` established that the link is alive but weak: keying a 480 us carrier
produced ~98 edges where a faithful demodulator would produce ~1250 (2 transitions
per 480 us period over 300 ms). Silent was ~8. So the receiver registers the
carrier but barely tracks it - a threshold/AGC/bandwidth mismatch, not a dead radio.

Each entry here sets ONE register (via `RXREG <addr> <val>`, which applies the full
config first so every entry starts from the same baseline) and then measures the
KEYED edge count. Figure of merit is `keyed` (want ~1250); `silent` is the guard
against a setting that just makes the receiver noisier.

Suspects, in the order they were chosen:
  AGCCTRL0 (0x1C) = 0xB2 -> AGC_FREEZE = 11 (freeze after 16 gain steps). A frozen
      AGC is precisely how a slicer gets stuck at one level and stops tracking.
  MDMCFG4 (0x10)  bandwidth, keeping the low nibble (DRATE_E) at 8 so the data rate
      is unchanged: 0xD8=81 kHz, 0xE8=69 kHz, 0xF8=58 kHz are all narrower than the
      current 0xC8=101 kHz, and narrower means less noise into the slicer.
  AGCCTRL2 (0x1B) MAGN_TARGET [2:0] - the AGC's target level, i.e. the OOK decision
      point. Current 0x43 = MAGN_TARGET 3.
  AGCCTRL1 (0x1A) CARRIER_SENSE_ABS_THR [3:0] - the carrier-sense threshold.

Run with the webapp STOPPED - it owns COM3.
"""
import statistics
import sys
import time

import serial

PORT = "COM3"
BAUD = 115200
BIT_US = 480
MS = 300
PA = 12

R_AGCCTRL0, R_AGCCTRL1, R_AGCCTRL2, R_MDMCFG4 = 0x1C, 0x1A, 0x1B, 0x10

SWEEP = [
    ("baseline (current config)", R_AGCCTRL0, 0xB2),
    ("agc0 freeze NEVER", R_AGCCTRL0, 0x82),
    ("agc0 freeze after 4", R_AGCCTRL0, 0x92),
    ("agc0 freeze after 8", R_AGCCTRL0, 0xA2),
    ("agc0 ti default", R_AGCCTRL0, 0x91),
    ("agc0 no-freeze hyst3", R_AGCCTRL0, 0x83),
    ("bw 116 kHz", R_MDMCFG4, 0xB8),
    ("bw  81 kHz", R_MDMCFG4, 0xD8),
    ("bw  69 kHz", R_MDMCFG4, 0xE8),
    ("bw  58 kHz", R_MDMCFG4, 0xF8),
    ("magntgt 0", R_AGCCTRL2, 0x40),
    ("magntgt 1", R_AGCCTRL2, 0x41),
    ("magntgt 7", R_AGCCTRL2, 0x47),
    ("magntgt 7 +dvga", R_AGCCTRL2, 0x77),
    ("cs abs thr +4", R_AGCCTRL1, 0x04),
    ("cs abs thr -8", R_AGCCTRL1, 0x08),
    ("lna priority + thr -8", R_AGCCTRL1, 0x48),
]

EXPECTED = MS * 1000 // BIT_US     # one carrier transition per loop iteration


def read_edges(ser, cmd, timeout=10.0):
    ser.reset_input_buffer()
    ser.write((cmd + "\n").encode())
    end = time.time() + timeout
    while time.time() < end:
        line = ser.readline().decode("ascii", "ignore").strip()
        if line.startswith("TXKEY_EDGES "):
            return int(line.split()[1])
    return None


def main():
    ser = serial.Serial(PORT, BAUD, timeout=0.2)
    quiet, end = time.time(), time.time() + 14
    while time.time() < end:
        if ser.readline():
            quiet = time.time()
        elif time.time() - quiet > 1.5:
            break

    ser.write(("TXPA %d\n" % PA).encode())
    time.sleep(0.3)
    print("objective: keyed edges approaching %d (a faithful demod of a %d us "
          "keyed carrier over %d ms)\n" % (EXPECTED, BIT_US, MS))
    print("%-26s %7s %7s %8s" % ("config", "keyed", "silent", "keyed/1250"))

    rows = []
    for label, addr, val in SWEEP:
        ser.reset_input_buffer()
        ser.write(("RXREG %02X %02X\n" % (addr, val)).encode())
        # Wait for RXREG_OK rather than sleeping a guessed interval.
        end = time.time() + 8
        ok = False
        while time.time() < end:
            line = ser.readline().decode("ascii", "ignore").strip()
            if line.startswith("RXREG_OK"):
                ok = True
                break
        if not ok:
            print("%-26s %7s" % (label, "no ack"))
            continue
        k = read_edges(ser, "TXKEY %d %d 1" % (BIT_US, MS))
        s = read_edges(ser, "TXKEY %d %d 0" % (BIT_US, MS))
        if k is None or s is None:
            print("%-26s %7s" % (label, "no data"))
            continue
        print("%-26s %7d %7d %8.2f" % (label, k, s, k / float(EXPECTED)))
        rows.append((k, s, label, addr, val))

    if rows:
        best = max(rows)
        print("\nbest: %s -> keyed %d, silent %d" % (best[2], best[0], best[1]))
        base = next((r for r in rows if r[2].startswith("baseline")), None)
        if base and best[0] > base[0] * 1.5:
            print("IMPROVED over baseline (%d -> %d keyed)" % (base[0], best[0]))
        else:
            print("no setting beat the baseline materially - the slicer is not "
                  "the limit")

    # Leave the radio back on the shipped config rather than the last probe.
    ser.write(("RXREG %02X %02X\n" % (R_AGCCTRL0, 0xB2)).encode())
    time.sleep(1.0)
    ser.write(b"DRATE 10000\n")
    time.sleep(1.0)
    ser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
