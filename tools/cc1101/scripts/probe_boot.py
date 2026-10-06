"""Open COM3, report the boot GDO_EDGES count and the idle RSSI/CAP behaviour."""
import serial
import time
from collections import Counter

s = serial.Serial('COM3', 115200, timeout=0.5)
time.sleep(3.0)          # boot settle
s.reset_input_buffer()

edges_line = None
rssi_vals = []
caps = 0
t0 = time.time()
while time.time() - t0 < 10:
    l = s.readline().decode('utf-8', 'ignore').strip()
    if not l:
        continue
    if l.startswith('GDO_EDGES'):
        edges_line = l
    elif l.startswith('CAP '):
        caps += 1
    elif 'RSSI=' in l:
        try:
            rssi_vals.append(int(l.split('RSSI=')[1].split()[0]))
        except ValueError:
            pass
s.close()

print("boot:", edges_line)
print("idle RSSI: min=%s max=%s  (mode=%s)  in %d samples"
      % (min(rssi_vals) if rssi_vals else None,
         max(rssi_vals) if rssi_vals else None,
         Counter(rssi_vals).most_common(3),
         len(rssi_vals)))
print("CAP lines in 10 s with NO fob:", caps)
