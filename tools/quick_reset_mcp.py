#!/usr/bin/env python3
"""
Quick MCP2515 Reset - Simple reset and check
"""

import paramiko
import time

PI_IP = "192.168.1.23"
PI_USER = "pi"
PI_PASSWORD = "REDACTED_WIFI_PASSWORD"

print("=" * 60)
print("QUICK MCP2515 RESET")
print("=" * 60)

try:
    print(f"\nConnecting to {PI_IP}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(PI_IP, username=PI_USER, password=PI_PASSWORD, timeout=10)
    print("✓ Connected\n")
    
    # Step 1: Check interfaces
    print("[1/5] Checking for CAN interfaces...")
    stdin, stdout, stderr = ssh.exec_command("ip link show | grep -E 'can0|can1'")
    output = stdout.read().decode()
    has_can0 = "can0" in output
    has_can1 = "can1" in output
    print(f"  can0: {'✓ Found' if has_can0 else '✗ Missing'}")
    print(f"  can1: {'✓ Found' if has_can1 else '✗ Missing'}")
    
    # Step 2: Bring down interfaces
    print("\n[2/5] Bringing down interfaces...")
    ssh.exec_command("sudo ip link set can0 down 2>/dev/null")
    ssh.exec_command("sudo ip link set can1 down 2>/dev/null")
    time.sleep(1)
    print("  ✓ Interfaces brought down")
    
    # Step 3: Bring up can0 (HS-CAN at 500kbps)
    print("\n[3/5] Bringing up can0 (HS-CAN @ 500kbps)...")
    stdin, stdout, stderr = ssh.exec_command("sudo ip link set can0 up type can bitrate 500000 listen-only on")
    time.sleep(1)
    error = stderr.read().decode()
    if error and "Cannot" in error:
        print(f"  ✗ Failed: {error}")
    else:
        print("  ✓ can0 is up")
    
    # Step 4: Bring up can1 (MS-CAN at 125kbps)
    print("\n[4/5] Bringing up can1 (MS-CAN @ 125kbps)...")
    stdin, stdout, stderr = ssh.exec_command("sudo ip link set can1 up type can bitrate 125000 listen-only on")
    time.sleep(1)
    error = stderr.read().decode()
    if error and "Cannot" in error:
        print(f"  ✗ Failed: {error}")
    else:
        print("  ✓ can1 is up")
    
    # Step 5: Quick traffic test on can0
    print("\n[5/5] Testing for CAN traffic on can0 (3 second test)...")
    print("  (Make sure car ignition is in ACC or ON)")
    stdin, stdout, stderr = ssh.exec_command("timeout 3 candump can0 -n 5 2>&1", get_pty=True)
    messages = []
    for _ in range(5):
        line = stdout.readline()
        if line:
            messages.append(line.strip())
            print(f"  📡 {line.strip()}")
    
    print("\n" + "=" * 60)
    print("RESULT:")
    print("=" * 60)
    if messages:
        print(f"✓✓✓ SUCCESS! Received {len(messages)} CAN messages")
        print("MCP modules are now working!")
    else:
        print("⚠️  No CAN traffic detected")
        print("\nPossible issues:")
        print("  • Car ignition not in ACC/ON position")
        print("  • MCP2515 wiring issue")
        print("  • Need to check dmesg logs for errors")
        print("\nTry running: python tools/reset_mcp_modules.py")
        print("            for detailed diagnostics")
    print("=" * 60 + "\n")
    
    ssh.close()
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    print("\nMake sure:")
    print("  • Pi is powered on and connected to network")
    print("  • IP address is correct (192.168.1.28)")
    print("  • SSH is enabled on Pi")
