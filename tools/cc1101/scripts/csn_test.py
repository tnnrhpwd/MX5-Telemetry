"""Are D9 and D10 actually separate chips? A controlled, read-free test.

Why this matters: `configureTx()` STARTS with an SRES. If the TX and RX chip
selects are tied together, then every TX experiment this project has run has also
been resetting the RECEIVER - which would explain the bistable railed-or-live
behaviour, the varying payloads, and why the loopback never saw a carrier from
our own transmitter.

Why it is a controlled test: the obvious observable, "the output goes quiet
after a reset", is worthless on its own, because the output is *already* quiet
most of the time. So the RX is reset through ITS OWN chip select first. That
control must show the collapse. Only if it does does the second measurement mean
anything - the same lesson as every other metric in this project.

Why it does not read registers: every register read on this two-module bus is
unreliable (FREQ2 returned 0x0C then 0x1E for the same config), so it uses the
GDO0 edge rate instead, which needs no SPI at all.

Run with the webapp STOPPED - it owns COM3.
"""
import sys
import time

import serial

PORT = "COM3"
BAUD = 115200


def main():
    ser = serial.Serial(PORT, BAUD, timeout=0.2)
    quiet, end = time.time(), time.time() + 14
    while time.time() < end:
        if ser.readline():
            quiet = time.time()
        elif time.time() - quiet > 1.5:
            break

    ser.reset_input_buffer()
    ser.write(b"CSNTEST\n")

    vals = {}
    end = time.time() + 40
    while time.time() < end:
        line = ser.readline().decode("ascii", "ignore").strip()
        if not line.startswith("CSNTEST_"):
            continue
        key, _, v = line.partition(" ")
        if key == "CSNTEST_DONE":
            break
        if v.strip().isdigit():
            vals[key] = int(v)

    print("GDO0 edges per 200 ms (0 would be a stopped output):")
    for k in ("CSNTEST_RX_BEFORE", "CSNTEST_RX_AFTER",
              "CSNTEST_TX_BEFORE", "CSNTEST_TX_AFTER"):
        if k in vals:
            print("  %-20s %d" % (k.replace("CSNTEST_", ""), vals[k]))

    need = ("CSNTEST_RX_BEFORE", "CSNTEST_RX_AFTER",
            "CSNTEST_TX_BEFORE", "CSNTEST_TX_AFTER")
    if any(k not in vals for k in need):
        print("\nIncomplete: got %s" % sorted(vals))
        ser.close()
        return 1

    rb, ra = vals["CSNTEST_RX_BEFORE"], vals["CSNTEST_RX_AFTER"]
    tb, ta = vals["CSNTEST_TX_BEFORE"], vals["CSNTEST_TX_AFTER"]

    print("\n=== control: reset the RX through the RX's own chip select ===")
    print("before %d -> after %d" % (rb, ra))
    # The control only demonstrates itself if the output really did collapse.
    if not (rb >= 3 and ra < rb / 2):
        print("-> CONTROL FAILED. The edge rate did not respond to resetting the")
        print("   receiver, so it cannot be used as an observable and the TX")
        print("   measurement below proves nothing. Re-run before concluding.")
        ser.close()
        return 1
    print("-> control OK: resetting the RX through its own CSN stops the output.")

    print("\n=== test: reset the RX through the TX's chip select ===")
    print("before %d -> after %d" % (tb, ta))
    if ta < tb / 2:
        print("-> D9 AND D10 ARE THE SAME NODE. Resetting 'the TX' reset the")
        print("   RECEIVER, so every TX command has been disturbing the RX.")
        print("   Fix the wiring before any more TX work.")
    else:
        print("-> the chip selects are INDEPENDENT: resetting 'the TX' left the")
        print("   receiver alone. So D9 does select a separate chip, and the TX")
        print("   fault is that chip not transmitting rather than the wiring.")
    ser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
