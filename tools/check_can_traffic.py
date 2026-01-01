#!/usr/bin/env python3
"""Check all CAN traffic on can1"""
import can
import time

print("Monitoring ALL CAN traffic on can1...")
print("Will show first 20 messages or timeout after 5 seconds\n")

try:
    bus = can.interface.Bus(channel='can1', bustype='socketcan')
    count = 0
    start = time.time()
    
    while count < 20 and (time.time() - start) < 5:
        msg = bus.recv(timeout=0.5)
        if msg:
            data_hex = ' '.join(f'{b:02X}' for b in msg.data)
            print(f"ID: 0x{msg.arbitration_id:03X}  Data: {data_hex}")
            count += 1
    
    if count == 0:
        print("NO CAN TRAFFIC DETECTED!")
        print("Is the car ignition ON?")
    else:
        print(f"\nReceived {count} messages")
        
except Exception as e:
    print(f"Error: {e}")
