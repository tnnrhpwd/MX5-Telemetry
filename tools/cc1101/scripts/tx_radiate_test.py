"""Does our own transmitter put ANY power into our own receiver?

The loopback fidelity test (`loopback_cal.py`) needs the TX to radiate before it
can say anything about the RX. It has never seen a carrier, so before drawing
any conclusion about the receiver we have to establish whether the transmitter
works at all - and, if it does, at which setting.

This is a LEVEL test, not a decoding test, so it is immune to every decode-side
unknown: it only asks whether the RX's RSSI moves when the TX is keyed. RSSI is
modulation-independent, so it also separates "the TX is silent" from "the TX
radiates but in the wrong modulation".

The `TXPKT` knob exists because the firmware's default (0x32, asynchronous
serial) keys the PA from GDO0 *input*, and the TX module's GDO0 is not wired to
anything - which is the documented reason a keyed carrier may radiate nothing.
`0x04` (infinite packet length) and `0x02` (random TX) are the alternatives the
firmware exposes for exactly this test, and they were never measured together
with maximum TX power.

Every stage is bracketed by an OFF measurement taken in the same instant, so a
reading that does not move is attributable rather than assumed.

Run with the webapp STOPPED - it owns COM3.
"""
import re
import sys
import time

import serial

PORT = "COM3"
BAUD = 115200
TXPA = "12"                 # maximum output power
PACKET_MODES = ["32", "04", "02"]
SETTLE_S = 0.5
SAMPLE_S = 1.5

RSSI_RE = re.compile(r"RSSI=(-?\d+)")


def out(*a):
    print(*a)
    sys.stdout.flush()


def boot(ser):
    """Opening the port resets the Nano; wait for it to stop talking."""
    quiet = time.time()
    end = time.time() + 14
    while time.time() < end:
        if ser.readline():
            quiet = time.time()
        elif time.time() - quiet > 1.5:
            return True
    return False


def send(ser, cmd, wait=SETTLE_S):
    ser.reset_input_buffer()
    ser.write((cmd + "\n").encode())
    time.sleep(wait)


def collect(ser, sec):
    """Sample RSSI lines for `sec`.

    Prints a heartbeat per read: a silent 1.5 s window looks like an idle
    process to a terminal harness, which will cut the run short.
    """
    vals = []
    end = time.time() + sec
    while time.time() < end:
        print(".", end="", flush=True)
        line = ser.readline().decode("ascii", "ignore").strip()
        m = RSSI_RE.search(line) if line else None
        if m:
            vals.append(int(m.group(1)))
    return vals


def med(v):
    return sorted(v)[len(v) // 2] if v else None


def peak(v):
    return max(v) if v else None


def registers(ser, label):
    """Read back the TX chip - the only status registers believed reliable."""
    send(ser, "TXV")
    _, lines = None, []
    end = time.time() + 2.0
    while time.time() < end:
        line = ser.readline().decode("ascii", "ignore").strip()
        if line:
            lines.append(line)
    out("--- TX chip registers: %s ---" % label)
    found = False
    for l in lines:
        if l.startswith("TX_"):
            out("   ", l)
            found = True
    if not found:
        out("    (no TX_ lines returned)")
    out("")


def main():
    ser = serial.Serial(PORT, BAUD, timeout=0.3)
    if not boot(ser):
        out("warning: board never went quiet after reset")
    out("board booted\n")

    try:
        registers(ser, "power-on, nothing configured")

        send(ser, "TXPA " + TXPA)
        send(ser, "TXON", 0.6)
        registers(ser, "after TXPA %s + TXON (i.e. after configureTx)" % TXPA)
        send(ser, "TXOFF")

        out("TXPA %s fixed; receiver level with TX off vs on, per packet mode" % TXPA)
        out("%8s %10s %10s %10s %10s" % ("TXPKT", "off_med", "off_peak", "on_med", "on_peak"))
        for pkt in PACKET_MODES:
            send(ser, "TXPKT " + pkt, SETTLE_S)
            send(ser, "TXOFF")
            off = collect(ser, SAMPLE_S)
            send(ser, "TXON")
            on = collect(ser, SAMPLE_S)
            send(ser, "TXOFF")
            print()
            delta = ""
            if off and on:
                delta = "   <-- MOVED %d dB" % (peak(on) - peak(off))
            out("%8s %10s %10s %10s %10s%s"
                % (pkt, med(off), peak(off), med(on), peak(on), delta))
    finally:
        try:
            send(ser, "TXPKT 32")
            send(ser, "TXOFF")
        except Exception:
            pass
        ser.close()
        out("\nrestored TXPKT 32, TX off")


if __name__ == "__main__":
    main()
