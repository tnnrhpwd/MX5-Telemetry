#!/usr/bin/env python3
"""
Debug CAN data parsing - shows raw CAN messages and parsed values
"""

import paramiko
import sys

PI_IP = "192.168.1.23"
PI_USER = "pi"
PI_PASSWORD = "Hopwood12"

def parse_coolant_temp(data_hex):
    """Parse coolant temperature from hex string"""
    data = bytes.fromhex(data_hex.replace(' ', ''))
    if len(data) >= 1:
        temp_c = data[0] - 40
        temp_f = int(temp_c * 9 / 5 + 32)
        return temp_c, temp_f
    return None, None

def parse_fuel_level(data_hex):
    """Parse fuel level from hex string"""
    data = bytes.fromhex(data_hex.replace(' ', ''))
    if len(data) >= 1:
        percent = data[0] * 100 / 255
        return percent
    return None

def parse_oil_pressure(data_hex):
    """Parse oil pressure from hex string"""
    data = bytes.fromhex(data_hex.replace(' ', ''))
    if len(data) >= 5:
        oil_ok = bool(data[4] & 0x01)
        return oil_ok
    return None

print("=" * 70)
print("CAN DATA PARSER DEBUG")
print("=" * 70)
print("\nMonitoring CAN IDs: 0x420 (coolant), 0x430 (fuel), 0x212 (oil)")
print("Showing raw data and how it's being parsed\n")

try:
    print(f"Connecting to {PI_IP}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(PI_IP, username=PI_USER, password=PI_PASSWORD, timeout=10)
    print("✓ Connected\n")
    
    # Monitor CAN traffic for these specific IDs
    print("Capturing CAN messages (10 seconds)...")
    print("-" * 70)
    
    cmd = "timeout 10 candump can0 | grep -E '420|430|212'"
    stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True)
    
    coolant_msgs = []
    fuel_msgs = []
    oil_msgs = []
    
    for line in stdout:
        line = line.strip()
        if not line or "can0" not in line:
            continue
            
        parts = line.split()
        if len(parts) >= 2:
            can_id_part = parts[1]
            if '#' in can_id_part:
                can_id, data_hex = can_id_part.split('#')
                
                # Coolant temp (0x420)
                if '420' in can_id:
                    temp_c, temp_f = parse_coolant_temp(data_hex)
                    coolant_msgs.append((data_hex, temp_c, temp_f))
                    if len(coolant_msgs) <= 5:
                        print(f"0x420 COOLANT: {data_hex}")
                        print(f"  → Byte 0: 0x{data_hex[:2]} = {int(data_hex[:2], 16)}")
                        print(f"  → Parsed: {temp_c}°C = {temp_f}°F\n")
                
                # Fuel level (0x430)
                elif '430' in can_id:
                    percent = parse_fuel_level(data_hex)
                    fuel_msgs.append((data_hex, percent))
                    if len(fuel_msgs) <= 5:
                        print(f"0x430 FUEL: {data_hex}")
                        print(f"  → Byte 0: 0x{data_hex[:2]} = {int(data_hex[:2], 16)}")
                        print(f"  → Parsed: {percent:.1f}%\n")
                
                # Oil pressure (0x212)
                elif '212' in can_id:
                    oil_ok = parse_oil_pressure(data_hex)
                    oil_msgs.append((data_hex, oil_ok))
                    if len(oil_msgs) <= 5:
                        print(f"0x212 OIL: {data_hex}")
                        if len(data_hex) >= 10:
                            print(f"  → Byte 4: 0x{data_hex[8:10]} = {int(data_hex[8:10], 16)}")
                        print(f"  → Oil OK: {oil_ok}\n")
    
    print("-" * 70)
    print(f"\nCaptured:")
    print(f"  Coolant messages: {len(coolant_msgs)}")
    print(f"  Fuel messages: {len(fuel_msgs)}")
    print(f"  Oil messages: {len(oil_msgs)}")
    
    # Summary
    print("\n" + "=" * 70)
    print("ANALYSIS")
    print("=" * 70)
    
    if coolant_msgs:
        unique_temps = set((c, f) for _, c, f in coolant_msgs if c is not None)
        print(f"\nCoolant temperatures seen:")
        for temp_c, temp_f in sorted(unique_temps):
            print(f"  {temp_c}°C = {temp_f}°F")
        
        if len(unique_temps) == 1 and list(unique_temps)[0][1] < 50:
            print("\n⚠️  Coolant shows very low temp - likely incorrect!")
            print("  Check: Byte offset, scaling factor, or CAN ID")
    else:
        print("\n⚠️  NO COOLANT DATA (0x420) received")
        print("  Is the car engine running/warm?")
    
    if fuel_msgs:
        unique_fuel = set(f for _, f in fuel_msgs if f is not None)
        print(f"\nFuel levels seen:")
        for pct in sorted(unique_fuel):
            print(f"  {pct:.1f}%")
        
        if len(unique_fuel) == 1 and (list(unique_fuel)[0] < 5 or list(unique_fuel)[0] > 95):
            print("\n⚠️  Fuel level seems extreme (very low or high)")
            print("  Check: Byte offset or scaling factor")
    else:
        print("\n⚠️  NO FUEL DATA (0x430) received")
    
    if oil_msgs:
        oil_states = [ok for _, ok in oil_msgs if ok is not None]
        true_count = sum(oil_states)
        false_count = len(oil_states) - true_count
        print(f"\nOil pressure states:")
        print(f"  OK (True): {true_count}")
        print(f"  BAD (False): {false_count}")
    else:
        print("\n⚠️  NO OIL DATA (0x212) received")
    
    print("\n" + "=" * 70)
    print("RECOMMENDATIONS")
    print("=" * 70)
    
    if not coolant_msgs and not fuel_msgs and not oil_msgs:
        print("\n⚠️  NO SENSOR DATA RECEIVED")
        print("  • Verify car is in ACC or ON (not just accessory)")
        print("  • Check if engine needs to be running for these messages")
        print("  • Try: python tools/monitor_can_data.py to see all IDs")
    else:
        print("\nIf values look wrong:")
        print("  1. Check CAN ID mappings (may vary by year/model)")
        print("  2. Verify byte offsets in parsing functions")
        print("  3. Check scaling factors and offset constants")
        print("  4. Consider endianness (big-endian vs little-endian)")
        print("\nNext: Edit pi/ui/src/can_handler.py parsing functions")
    
    print("=" * 70 + "\n")
    
    ssh.close()
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    sys.exit(1)
