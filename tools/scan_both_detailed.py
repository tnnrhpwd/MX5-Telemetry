#!/usr/bin/env python3
"""Scan both buses with extended ID support"""
import can

for bus_name in ['can0', 'can1']:
    print(f"\n=== {bus_name} ===")
    try:
        bus = can.interface.Bus(channel=bus_name, bustype='socketcan')
        ids = set()
        for _ in range(100):
            msg = bus.recv(timeout=0.05)
            if msg:
                ids.add((msg.arbitration_id, msg.is_extended_id))
        
        print(f"Total unique IDs: {len(ids)}")
        for can_id, is_ext in sorted(ids):
            id_str = f"0x{can_id:08X}" if is_ext else f"0x{can_id:03X}"
            id_type = "extended" if is_ext else "standard"
            print(f"  {id_str} ({id_type})")
        
        # Check for 0x250
        has_250 = any(can_id == 0x250 and not is_ext for can_id, is_ext in ids)
        print(f"\n0x250 (SWC cruise) present: {has_250}")
        
        bus.shutdown()
    except Exception as e:
        print(f"Error: {e}")

print("\n=== While you're holding CANCEL button ===")
