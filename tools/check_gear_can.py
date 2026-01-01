#!/usr/bin/env python3
"""Check if gear position (0x231) is on CAN bus"""
import can
import time

print("Checking for CAN ID 0x231 (gear position) on can0...")
print("Monitoring for 5 seconds...\n")

try:
    bus = can.interface.Bus(channel='can0', bustype='socketcan')
    
    gear_msgs = []
    start = time.time()
    
    while (time.time() - start) < 5:
        msg = bus.recv(timeout=0.1)
        if msg and msg.arbitration_id == 0x231:
            data_hex = ' '.join(f'{b:02X}' for b in msg.data)
            gear_byte = msg.data[0] if len(msg.data) > 0 else 0
            gear = gear_byte & 0x0F
            if gear == 0:
                gear_str = "N"
            elif gear <= 6:
                gear_str = str(gear)
            else:
                gear_str = "R"
            
            gear_msgs.append((data_hex, gear_str))
            if len(gear_msgs) <= 3:
                print(f"0x231: {data_hex} -> Gear: {gear_str}")
    
    bus.shutdown()
    
    print(f"\n=== RESULTS ===")
    print(f"0x231 messages received: {len(gear_msgs)}")
    
    if len(gear_msgs) == 0:
        print("\n*** NO 0x231 (GEAR) MESSAGES! ***")
        print("The 2008 MX5 NC GT may not transmit gear position on CAN")
        print("Or car needs to be in a different state (transmission in gear)")
    else:
        print("\n✓ Gear position IS available on CAN bus!")
        print(f"Current gear: {gear_msgs[-1][1]}")
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
