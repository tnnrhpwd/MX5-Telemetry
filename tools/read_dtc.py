#!/usr/bin/env python3
"""
Read Diagnostic Trouble Codes (DTCs) from vehicle ECU via CAN bus
Uses OBD-II protocol over CAN (ISO 15765-4)
"""

import can
import time

# OBD-II CAN IDs
OBD_REQUEST = 0x7DF  # Broadcast request
ECU_RESPONSE = 0x7E8  # ECU response

# OBD-II Service 03: Request emission-related DTCs
REQUEST_DTC = [0x03]

def read_dtcs():
    """Read DTCs from the ECU"""
    try:
        # Connect to CAN bus
        bus = can.interface.Bus(channel='can0', bustype='socketcan')
        print("Connected to CAN bus (can0)")
        
        # Send DTC request
        msg = can.Message(arbitration_id=OBD_REQUEST, data=REQUEST_DTC, is_extended_id=False)
        bus.send(msg)
        print(f"Sent DTC request: {msg}")
        
        # Wait for response
        print("Waiting for ECU response...")
        timeout = time.time() + 2.0
        dtcs = []
        
        while time.time() < timeout:
            response = bus.recv(timeout=0.5)
            if response and response.arbitration_id == ECU_RESPONSE:
                print(f"Received: {response}")
                data = response.data
                
                # Parse DTC response (Service 03 response = 0x43)
                if len(data) >= 2 and data[0] == 0x43:
                    num_codes = data[1]
                    print(f"Number of DTCs: {num_codes}")
                    
                    # Parse DTCs (2 bytes each, starting at byte 2)
                    for i in range(num_codes):
                        if len(data) >= (2 + (i+1)*2):
                            dtc_high = data[2 + i*2]
                            dtc_low = data[3 + i*2]
                            
                            # Decode DTC
                            dtc_str = decode_dtc(dtc_high, dtc_low)
                            dtcs.append(dtc_str)
                            print(f"DTC #{i+1}: {dtc_str}")
                    
                    break
        
        bus.shutdown()
        
        if dtcs:
            print(f"\nFound {len(dtcs)} DTC(s):")
            for dtc in dtcs:
                print(f"  - {dtc}")
        else:
            print("\nNo DTCs found or ECU did not respond")
            print("Note: Check engine light may be on for a different reason")
            
    except Exception as e:
        print(f"Error reading DTCs: {e}")

def decode_dtc(high_byte, low_byte):
    """Decode DTC from two bytes"""
    # First 2 bits determine DTC type
    dtc_type = (high_byte >> 6) & 0x03
    type_map = {0: 'P', 1: 'C', 2: 'B', 3: 'U'}  # Powertrain, Chassis, Body, Network
    
    # Remaining bits form the code
    digit1 = (high_byte >> 4) & 0x03
    digit2 = high_byte & 0x0F
    digit3 = (low_byte >> 4) & 0x0F
    digit4 = low_byte & 0x0F
    
    return f"{type_map[dtc_type]}{digit1}{digit2:X}{digit3:X}{digit4:X}"

if __name__ == "__main__":
    print("=== OBD-II DTC Reader ===")
    print("Reading diagnostic trouble codes from ECU...\n")
    read_dtcs()
