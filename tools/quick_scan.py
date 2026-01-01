#!/usr/bin/env python3
"""Quick ID scan"""
import can
bus = can.interface.Bus(channel='can1', bustype='socketcan')
ids = set()
for _ in range(50):
    msg = bus.recv(timeout=0.1)
    if msg:
        ids.add(msg.arbitration_id)
print(f"CAN IDs on can1: {sorted(ids)}")
print(f"0x250 present: {0x250 in ids}")
bus.shutdown()
