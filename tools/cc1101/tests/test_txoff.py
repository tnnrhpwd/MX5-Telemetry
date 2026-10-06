import serial
import time
from collections import Counter

def read_rssi(s, seconds):
    vals = []
    end = time.time() + seconds
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
    return vals

s = serial.Serial("COM3", 115200, timeout=0.2)
time.sleep(2)
vals = read_rssi(s, 2)
print("boot rssi:", dict(sorted(Counter(vals).items())[:5]))
print("sending TXOFF (SRES -> guaranteed off)")
s.write(b"TXOFF\n")
time.sleep(1)
vals = read_rssi(s, 2)
print("after TXOFF rssi:", dict(sorted(Counter(vals).items())[:5]))
s.close()
