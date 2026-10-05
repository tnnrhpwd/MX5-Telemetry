import serial
import time
from collections import Counter

def bucket(vals, n=5):
    out = []
    for i in range(n):
        chunk = vals[i::n]
        out.append(chunk)
    return out

s = serial.Serial("COM3", 115200, timeout=0.2)
time.sleep(5)          # FSK soak
s.write(b"MOD 2\n")
time.sleep(3)          # OOK settle
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
print("FSK soak=5s, OOK settle=3s, read=6s  n=%d" % len(vals))
for v, c in sorted(Counter(vals).items()):
    print("%d:%d" % (v, c))
# time sequence: split into 3 halves
n = len(vals)
if n > 9:
    third = n // 3
    for i, (a, b) in enumerate([(0, third), (third, 2*third), (2*third, n)]):
        seg = vals[a:b]
        c = Counter(seg)
        print("  seg%d: %s" % (i, sorted(c.items())[:4]))
