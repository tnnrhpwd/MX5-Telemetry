#!/usr/bin/env python3
"""
Check CAN bus for errors and monitor data quality
"""

import paramiko
import sys

PI_IP = "192.168.1.23"
PI_USER = "pi"
PI_PASSWORD = "Hopwood12"

print("=" * 70)
print("CAN BUS ERROR & DATA QUALITY CHECK")
print("=" * 70)

try:
    print(f"\nConnecting to {PI_IP}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(PI_IP, username=PI_USER, password=PI_PASSWORD, timeout=10)
    print("✓ Connected\n")
    
    # Check interface status and error counters
    print("=" * 70)
    print("CAN0 (HS-CAN) - Interface Status & Error Counters")
    print("=" * 70)
    stdin, stdout, stderr = ssh.exec_command("ip -s -d link show can0")
    output = stdout.read().decode()
    print(output)
    
    # Check for specific error indicators
    if "bus-off" in output.lower():
        print("⚠️  WARNING: can0 is in BUS-OFF state!")
    if "error-warning" in output.lower():
        print("⚠️  WARNING: can0 has error-warning state!")
    
    print("\n" + "=" * 70)
    print("CAN1 (MS-CAN) - Interface Status & Error Counters")
    print("=" * 70)
    stdin, stdout, stderr = ssh.exec_command("ip -s -d link show can1")
    output = stdout.read().decode()
    print(output)
    
    if "bus-off" in output.lower():
        print("⚠️  WARNING: can1 is in BUS-OFF state!")
    if "error-warning" in output.lower():
        print("⚠️  WARNING: can1 has error-warning state!")
    
    # Check for CAN error frames
    print("\n" + "=" * 70)
    print("Checking for CAN Error Frames on can0 (5 second test)")
    print("=" * 70)
    print("Listening for errors...")
    stdin, stdout, stderr = ssh.exec_command("timeout 5 candump can0,0~0:e 2>&1", get_pty=True)
    error_frames = []
    for line in stdout:
        line = line.strip()
        if line:
            error_frames.append(line)
            print(f"  {line}")
    
    if not error_frames:
        print("  ✓ No error frames detected")
    else:
        print(f"\n⚠️  {len(error_frames)} error frames detected!")
    
    # Sample actual CAN data on can0
    print("\n" + "=" * 70)
    print("Sampling CAN0 (HS-CAN) Data - First 20 messages")
    print("=" * 70)
    stdin, stdout, stderr = ssh.exec_command("timeout 5 candump can0 -n 20 2>&1", get_pty=True)
    messages = []
    for line in stdout:
        line = line.strip()
        if line and "can0" in line:
            messages.append(line)
            print(f"  {line}")
    
    if not messages:
        print("  ⚠️  NO DATA on can0!")
        print("  Check: Is car ignition ON? Are CAN-H/CAN-L connected?")
    else:
        print(f"\n  ✓ Received {len(messages)} messages on can0")
    
    # Sample actual CAN data on can1
    print("\n" + "=" * 70)
    print("Sampling CAN1 (MS-CAN) Data - First 20 messages")
    print("=" * 70)
    stdin, stdout, stderr = ssh.exec_command("timeout 5 candump can1 -n 20 2>&1", get_pty=True)
    messages1 = []
    for line in stdout:
        line = line.strip()
        if line and "can1" in line:
            messages1.append(line)
            print(f"  {line}")
    
    if not messages1:
        print("  ⚠️  NO DATA on can1!")
    else:
        print(f"\n  ✓ Received {len(messages1)} messages on can1")
    
    # Check for bus timing/bitrate issues
    print("\n" + "=" * 70)
    print("Checking Bus Configuration")
    print("=" * 70)
    stdin, stdout, stderr = ssh.exec_command("ip -d link show can0 | grep -E 'bitrate|sample-point'")
    can0_config = stdout.read().decode()
    print("can0 (HS-CAN):")
    print(f"  {can0_config.strip()}")
    
    stdin, stdout, stderr = ssh.exec_command("ip -d link show can1 | grep -E 'bitrate|sample-point'")
    can1_config = stdout.read().decode()
    print("can1 (MS-CAN):")
    print(f"  {can1_config.strip()}")
    
    # Summary
    print("\n" + "=" * 70)
    print("DIAGNOSIS")
    print("=" * 70)
    
    if error_frames:
        print("\n⚠️  CAN ERROR FRAMES DETECTED")
        print("This indicates:")
        print("  • Incorrect bitrate (should be 500k for HS-CAN, 125k for MS-CAN)")
        print("  • Bus termination issues")
        print("  • Electrical noise or poor connections")
        print("  • Incorrect CAN-H/CAN-L wiring")
        print("\nRecommended actions:")
        print("  1. Verify bitrates: can0=500000, can1=125000")
        print("  2. Check CAN termination resistors (120Ω)")
        print("  3. Inspect CAN-H and CAN-L wiring for shorts or swaps")
    
    if not messages and not messages1:
        print("\n⚠️  NO CAN DATA RECEIVED")
        print("Possible causes:")
        print("  • Car ignition not in ACC or ON")
        print("  • CAN-H/CAN-L not connected to OBD-II port")
        print("  • Wrong CAN bus selected (check which is HS vs MS)")
    elif messages or messages1:
        print("\n✓ CAN data is being received")
        if not error_frames:
            print("✓ No error frames detected")
            print("\nIf seeing bad data (wrong coolant/oil/fuel values):")
            print("  • The CAN hardware is working correctly")
            print("  • Issue is likely in data parsing/decoding")
            print("  • Check the Python code that interprets CAN messages")
            print("  • Verify CAN ID mappings for coolant/oil/fuel")
            print("\nNext step: Check which CAN IDs contain sensor data")
            print("  Run: python tools/monitor_can_data.py")
    
    print("\n" + "=" * 70 + "\n")
    
    ssh.close()
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    sys.exit(1)
