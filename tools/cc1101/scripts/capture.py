#!/usr/bin/env python3
"""
Record serial output from the CC1101 capture sketch to a file.

Usage:
    python capture.py [PORT] [OUTFILE] [seconds]

Defaults: COM3 -> capture.txt, run until stopped (Ctrl+C or kill).
"""
import sys
import time

import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM3"
OUT = sys.argv[2] if len(sys.argv) > 2 else "capture.txt"
DURATION = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0  # 0 = until stopped

ser = serial.Serial(PORT, 115200, timeout=1)
start = time.time()
with open(OUT, "w", encoding="utf-8") as f:
    while True:
        if DURATION and (time.time() - start) > DURATION:
            break
        line = ser.readline()
        if line:
            s = line.decode("utf-8", "ignore").rstrip()
            print(s)
            f.write(s + "\n")
            f.flush()
ser.close()
print("captured to %s" % OUT)
