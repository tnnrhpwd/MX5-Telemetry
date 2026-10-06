import serial
import time
from collections import Counter

s = serial.Serial("COM3", 115200, timeout=0.2)
time.sleep(5)
s.write(b"FREQ 315.000\n")
time.sleep(0.05)
s.write(b"MOD 2\n")
time.sleep(3)
vals = []
end = time.time() + 6
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
print("webapp-mimic (FREQ+MOD at 5s): n=%d" % len(vals))
for v, c in sorted(Counter(vals).items()):
    print("%d:%d" % (v, c))
