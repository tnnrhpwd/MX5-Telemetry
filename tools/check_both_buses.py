#!/usr/bin/env python3
"""Check BOTH CAN buses for 0x250"""
import can
import time
import threading

results = {"can0": {"total": 0, "0x250": 0, "ids": set()}, 
           "can1": {"total": 0, "0x250": 0, "ids": set()}}

def monitor_bus(channel):
    try:
        bus = can.interface.Bus(channel=channel, bustype='socketcan')
        start = time.time()
        
        while (time.time() - start) < 10:
            msg = bus.recv(timeout=0.1)
            if msg:
                results[channel]["total"] += 1
                results[channel]["ids"].add(msg.arbitration_id)
                
                if msg.arbitration_id == 0x250:
                    results[channel]["0x250"] += 1
                    data_hex = ' '.join(f'{b:02X}' for b in msg.data)
                    byte0 = msg.data[0] if len(msg.data) > 0 else 0x00
                    print(f"[{channel}] 0x250: {data_hex}  Byte0=0x{byte0:02X}")
        
        bus.shutdown()
    except Exception as e:
        print(f"Error on {channel}: {e}")

print("=== Checking BOTH CAN buses for 0x250 ===")
print("Hold CANCEL button NOW!")
print("Monitoring for 10 seconds...\n")

t0 = threading.Thread(target=monitor_bus, args=("can0",), daemon=True)
t1 = threading.Thread(target=monitor_bus, args=("can1",), daemon=True)

t0.start()
t1.start()

t0.join()
t1.join()

print("\n=== RESULTS ===")
for bus in ["can0", "can1"]:
    print(f"\n{bus} (HS-CAN if can0, MS-CAN if can1):")
    print(f"  Total messages: {results[bus]['total']}")
    print(f"  Messages with 0x250: {results[bus]['0x250']}")
    print(f"  Unique IDs: {len(results[bus]['ids'])}")
    if results[bus]['ids']:
        print(f"  IDs: {', '.join(f'0x{id:03X}' for id in sorted(list(results[bus]['ids'])[:20]))}")

if results["can0"]["0x250"] == 0 and results["can1"]["0x250"] == 0:
    print("\n*** PROBLEM: No 0x250 messages on EITHER bus! ***")
    print("\nPossible reasons:")
    print("1. Car ignition needs to be ON (not just ACC)")
    print("2. Some MX5 NC models may not broadcast cruise buttons on CAN")
    print("3. Your specific trim (2008 NC GT) may use different CAN ID")
    print("4. Cruise control module may be disabled/disconnected")
    print("\nTry: Check if you have cruise control stalk/buttons working normally")
