#!/usr/bin/env python3
"""
Fix CAN BUS-OFF state by resetting interfaces with proper restart settings
"""

import paramiko
import time

PI_IP = "192.168.1.23"
PI_USER = "pi"
PI_PASSWORD = "Hopwood12"

print("=" * 70)
print("FIX CAN BUS-OFF STATE")
print("=" * 70)

try:
    print(f"\nConnecting to {PI_IP}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(PI_IP, username=PI_USER, password=PI_PASSWORD, timeout=10)
    print("✓ Connected\n")
    
    print("[1/6] Bringing down both CAN interfaces...")
    ssh.exec_command("sudo ip link set can0 down")
    ssh.exec_command("sudo ip link set can1 down")
    time.sleep(2)
    print("  ✓ Interfaces down\n")
    
    print("[2/6] Setting up can0 (HS-CAN) with auto-restart...")
    stdin, stdout, stderr = ssh.exec_command(
        "sudo ip link set can0 up type can bitrate 500000 restart-ms 100 listen-only on"
    )
    time.sleep(1)
    error = stderr.read().decode()
    if error and "Cannot" in error:
        print(f"  ✗ Error: {error}")
    else:
        print("  ✓ can0 up (500kbps, auto-restart enabled)")
    
    print("\n[3/6] Setting up can1 (MS-CAN) with auto-restart...")
    stdin, stdout, stderr = ssh.exec_command(
        "sudo ip link set can1 up type can bitrate 125000 restart-ms 100 listen-only on"
    )
    time.sleep(1)
    error = stderr.read().decode()
    if error and "Cannot" in error:
        print(f"  ✗ Error: {error}")
    else:
        print("  ✓ can1 up (125kbps, auto-restart enabled)")
    
    print("\n[4/6] Checking interface states...")
    stdin, stdout, stderr = ssh.exec_command("ip link show can0 | grep -E 'state|can '")
    can0_state = stdout.read().decode()
    print(f"can0: {can0_state.strip()}")
    
    stdin, stdout, stderr = ssh.exec_command("ip link show can1 | grep -E 'state|can '")
    can1_state = stdout.read().decode()
    print(f"can1: {can1_state.strip()}")
    
    print("\n[5/6] Resetting error counters...")
    # Sometimes need to restart to clear BUS-OFF
    if "BUS-OFF" in can0_state or "BUS-OFF" in can1_state:
        print("  Detected BUS-OFF, performing hard reset...")
        ssh.exec_command("sudo ip link set can0 down")
        ssh.exec_command("sudo ip link set can1 down")
        time.sleep(3)
        ssh.exec_command("sudo ip link set can0 up type can bitrate 500000 restart-ms 100 listen-only on")
        ssh.exec_command("sudo ip link set can1 up type can bitrate 125000 restart-ms 100 listen-only on")
        time.sleep(2)
        print("  ✓ Hard reset completed")
    else:
        print("  ✓ No BUS-OFF state")
    
    print("\n[6/6] Testing for CAN traffic...")
    stdin, stdout, stderr = ssh.exec_command("timeout 3 candump can0 -n 5 2>&1", get_pty=True)
    messages = []
    for line in stdout:
        line = line.strip()
        if line and "can0" in line:
            messages.append(line)
            print(f"  📡 {line}")
    
    print("\n" + "=" * 70)
    print("RESULT")
    print("=" * 70)
    
    if messages:
        print("\n✓✓✓ CAN interfaces restored!")
        print("CAN data is now flowing correctly.")
        print("\nThe bad data issue should be resolved.")
    else:
        print("\n⚠️  Still no CAN traffic")
        print("\nPossible issues:")
        print("  • Car ignition not in ACC/ON")
        print("  • Incorrect bitrate for your vehicle")
        print("  • CAN-H/CAN-L wiring issue")
        print("\nTry:")
        print("  1. Turn off car, wait 10 seconds, turn to ACC")
        print("  2. Check CAN wiring connections")
        print("  3. Run full diagnostic: python tools/reset_mcp_modules.py")
    
    print("=" * 70 + "\n")
    
    ssh.close()
    
except Exception as e:
    print(f"\n✗ Error: {e}")
