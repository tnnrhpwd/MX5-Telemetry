import serial
import time

s = serial.Serial("COM3", 115200, timeout=0.2)
time.sleep(2)
# Drain boot lines
time.sleep(0.5)
try:
    while s.in_waiting:
        s.readline()
except Exception:
    pass
s.write(b"DUMP\n")
time.sleep(0.5)
print("--- DUMP after boot (OOK+BW100) ---")
end = time.time() + 1.5
while time.time() < end:
    try:
        line = s.readline().decode("ascii", "replace").strip()
        if line:
            print(line)
    except Exception:
        pass
# now send MOD 2 and dump again
s.write(b"MOD 2\n")
time.sleep(1)
s.write(b"DUMP\n")
time.sleep(0.5)
print("--- DUMP after MOD 2 ---")
end = time.time() + 1.5
while time.time() < end:
    try:
        line = s.readline().decode("ascii", "replace").strip()
        if line:
            print(line)
    except Exception:
        pass
s.close()
