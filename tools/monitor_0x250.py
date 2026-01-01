#!/usr/bin/env python3
"""Monitor specifically for 0x250 with detailed stats"""
import can
import time

print("=== Monitoring for CAN ID 0x250 (Cruise Control Buttons) ===")
print("Hold the CANCEL button now!")
print("Monitoring for 15 seconds...\n")

try:
    bus = can.interface.Bus(channel='can1', bustype='socketcan')
    
    msg_250_count = 0
    total_count = 0
    unique_ids = set()
    start = time.time()
    
    while (time.time() - start) < 15:
        msg = bus.recv(timeout=0.1)
        if msg:
            total_count += 1
            unique_ids.add(msg.arbitration_id)
            
            if msg.arbitration_id == 0x250:
                msg_250_count += 1
                data_hex = ' '.join(f'{b:02X}' for b in msg.data)
                byte0 = msg.data[0] if len(msg.data) > 0 else 0x00
                
                button = "NONE"
                if byte0 == 0x01:
                    button = "ON/OFF"
                elif byte0 == 0x02:
                    button = "CANCEL *** THIS IS THE ONE YOU'RE HOLDING ***"
                elif byte0 == 0x04:
                    button = "RES+"
                elif byte0 == 0x08:
                    button = "SET-"
                
                print(f"[{time.strftime('%H:%M:%S')}] 0x250: {data_hex}  -> {button}")
    
    print(f"\n=== RESULTS ===")
    print(f"Total CAN messages: {total_count}")
    print(f"Messages with ID 0x250: {msg_250_count}")
    print(f"Unique CAN IDs seen: {len(unique_ids)}")
    print(f"IDs: {', '.join(f'0x{id:03X}' for id in sorted(unique_ids))}")
    
    if msg_250_count == 0:
        print("\n*** NO 0x250 MESSAGES DETECTED! ***")
        print("Possible issues:")
        print("1. Car may need to be in different mode (ignition ON, engine running)")
        print("2. Cruise control system may not be active")
        print("3. 2008 MX5 NC GT may not broadcast cruise buttons on accessible MS-CAN")
        print("4. Wiring may be connected to wrong CAN bus")
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
