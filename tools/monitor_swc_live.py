#!/usr/bin/env python3
"""Quick SWC button monitor - shows button presses in real-time"""
import can
import time

print("Monitoring CAN ID 0x250 for SWC buttons...")
print("Button codes: 0x01=ON/OFF, 0x02=CANCEL, 0x04=RES+, 0x08=SET-")
print("Press Ctrl+C to exit\n")

try:
    bus = can.interface.Bus(channel='can1', bustype='socketcan')
    last_byte = 0xFF
    
    while True:
        msg = bus.recv(timeout=0.1)
        if msg and msg.arbitration_id == 0x250:
            byte0 = msg.data[0] if len(msg.data) > 0 else 0x00
            if byte0 != last_byte:
                if byte0 == 0x00:
                    print(f"{time.strftime('%H:%M:%S')} - Released")
                elif byte0 == 0x01:
                    print(f"{time.strftime('%H:%M:%S')} - ON/OFF pressed")
                elif byte0 == 0x02:
                    print(f"{time.strftime('%H:%M:%S')} - CANCEL pressed *** YOU ARE HOLDING THIS ***")
                elif byte0 == 0x04:
                    print(f"{time.strftime('%H:%M:%S')} - RES+ pressed")
                elif byte0 == 0x08:
                    print(f"{time.strftime('%H:%M:%S')} - SET- pressed")
                else:
                    print(f"{time.strftime('%H:%M:%S')} - Unknown: 0x{byte0:02X}")
                last_byte = byte0
except KeyboardInterrupt:
    print("\nMonitoring stopped")
except Exception as e:
    print(f"Error: {e}")
