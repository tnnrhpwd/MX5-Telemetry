import serial
import time
import sys

# Kill webapp first: it holds COM3. This script talks to the Arduino directly.
s = serial.Serial("COM3", 115200, timeout=0.2)
time.sleep(2)
# ensure OOK mode
s.write(b"MOD 2\n")
time.sleep(0.5)

print("SCAN_START 313-317 MHz step 0.1 (press and HOLD the fob)")
for mhz in [round(313.0 + i * 0.1, 1) for i in range(41)]:
    s.write(("FREQ %.1f\n" % mhz).encode())
    time.sleep(0.25)
    vals = []
    end = time.time() + 0.6
    while time.time() < end:
        try:
            line = s.readline().decode("ascii", "replace")
            if "RSSI=" in line:
                i = line.index("RSSI=")
                try:
                    vals.append(int(line[i+5:].split()[0]))
                except ValueError:
                    pass
        except Exception:
            pass
    if vals:
        mx = max(vals)
        mn = min(vals)
        avg = sum(vals) // len(vals)
        print("%.1f MHz  max=%d avg=%d min=%d  n=%d" % (mhz, mx, avg, mn, len(vals)))
    else:
        print("%.1f MHz  (no data)" % mhz)
print("SCAN_END")
s.write(b"FREQ 315.0\n")
s.close()
