#!/usr/bin/env python3
"""
Monitor specific CAN IDs for coolant, oil, and fuel data
"""

import paramiko
import sys

PI_IP = "192.168.1.23"
PI_USER = "pi"
PI_PASSWORD = "Hopwood12"

print("=" * 70)
print("MONITOR CAN DATA - Coolant, Oil, Fuel")
print("=" * 70)

try:
    print(f"\nConnecting to {PI_IP}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(PI_IP, username=PI_USER, password=PI_PASSWORD, timeout=10)
    print("✓ Connected\n")
    
    print("Monitoring CAN traffic for 10 seconds...")
    print("Looking for common Mazda sensor CAN IDs:")
    print("  • Engine data (RPM, coolant, etc.)")
    print("  • Fuel level")
    print("  • Oil pressure/temp")
    print("\nPress Ctrl+C to stop early\n")
    print("-" * 70)
    
    # Monitor can0 (HS-CAN) - usually has engine data
    stdin, stdout, stderr = ssh.exec_command("timeout 10 candump can0 2>&1", get_pty=True)
    
    can_ids = {}
    count = 0
    
    for line in stdout:
        line = line.strip()
        if "can0" in line and "#" in line:
            parts = line.split()
            if len(parts) >= 2:
                can_id = parts[1].split("#")[0]
                data = parts[1].split("#")[1] if "#" in parts[1] else ""
                
                if can_id not in can_ids:
                    can_ids[can_id] = []
                can_ids[can_id].append(data)
                
                # Print first few messages of each ID
                if len(can_ids[can_id]) <= 3:
                    print(f"{line}")
                
                count += 1
                if count > 100:  # Limit output
                    break
    
    print("-" * 70)
    print(f"\nCaptured {count} messages across {len(can_ids)} unique CAN IDs\n")
    
    print("=" * 70)
    print("CAN ID SUMMARY (Frequency of messages)")
    print("=" * 70)
    
    # Sort by frequency
    sorted_ids = sorted(can_ids.items(), key=lambda x: len(x[1]), reverse=True)
    
    for can_id, data_list in sorted_ids[:20]:  # Top 20 most frequent
        frequency = len(data_list)
        sample = data_list[0] if data_list else ""
        print(f"  {can_id}: {frequency} messages  (sample: {sample})")
    
    print("\n" + "=" * 70)
    print("COMMON MAZDA CAN IDS (for reference)")
    print("=" * 70)
    print("  0x201 - Engine RPM, Speed, Throttle")
    print("  0x420 - Coolant Temp, Oil Temp")
    print("  0x430 - Fuel Level")
    print("  0x4B0 - Various sensors")
    print("\nNote: Actual IDs vary by year/model")
    print("\nIf you see unexpected data:")
    print("  1. Verify correct CAN ID mapping in your code")
    print("  2. Check byte order and scaling factors")
    print("  3. Ensure listening to correct bus (HS-CAN vs MS-CAN)")
    print("=" * 70 + "\n")
    
    ssh.close()
    
except KeyboardInterrupt:
    print("\n\nMonitoring stopped by user")
    ssh.close()
except Exception as e:
    print(f"\n✗ Error: {e}")
    sys.exit(1)
