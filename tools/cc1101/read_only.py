import serial
import time
from collections import Counter

s = serial.Serial("COM3", 115200, timeout=0.2)
time.sleep(2)
vals = []
end = time.time() + 10
while time.time() < end:
    try:
        line = s.readline().decode("ascii", "replace")
    except Exception:
        continue
    if "RSSI=" in line:
        i = line.index("RSSI=")
        rest = line[i + 5:].split()[0]
        try:
            vals.append(int(rest))
        except ValueError:
            pass
s.close()
print("FSK-only (no MOD cmd), n=%d" % len(vals))
for v, c in sorted(Counter(vals).items()):
    print("%d:%d" % (v, c))
