#!/usr/bin/env python3
"""
Force CAN interfaces out of BUS-OFF state
Performs hard reset cycle
"""

import paramiko
import time
import sys

PI_IP = "192.168.1.23"
PI_USER = "pi"
PI_PASSWORD = "Hopwood12"

print("=" * 70)
print("FORCE RECOVERY FROM BUS-OFF STATE")
print("=" * 70)

try:
    print(f"\nConnecting to {PI_IP}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(PI_IP, username=PI_USER, password=PI_PASSWORD, timeout=10)
    print("✓ Connected\n")
    
    print("[1/7] Checking current state...")
    stdin, stdout, stderr = ssh.exec_command("ip -s link show can0 | head -5")
    can0_state = stdout.read().decode()
    stdin, stdout, stderr = ssh.exec_command("ip -s link show can1 | head -5")
    can1_state = stdout.read().decode()
    
    print("can0:", "BUS-OFF" if "BUS-OFF" in can0_state else "OK")
    print("can1:", "BUS-OFF" if "BUS-OFF" in can1_state else "OK")
    
    print("\n[2/7] Bringing down both interfaces...")
    ssh.exec_command("sudo ip link set can0 down")
    ssh.exec_command("sudo ip link set can1 down")
    time.sleep(3)
    print("  ✓ Down\n")
    
    print("[3/7] Reloading MCP2515 kernel modules...")
    ssh.exec_command("sudo modprobe -r mcp251x")
    time.sleep(2)
    ssh.exec_command("sudo modprobe mcp251x")
    time.sleep(3)
    print("  ✓ Modules reloaded\n")
    
    print("[4/7] Checking if interfaces exist...")
    stdin, stdout, stderr = ssh.exec_command("ip link show | grep can")
    interfaces = stdout.read().decode()
    print(f"  {interfaces}")
    
    if "can0" not in interfaces or "can1" not in interfaces:
        print("\n⚠️  Interfaces missing, trying to reload device tree overlays...")
        ssh.exec_command("sudo dtoverlay mcp2515-can0,oscillator=8000000,interrupt=25")
        time.sleep(2)
        ssh.exec_command("sudo dtoverlay mcp2515-can1,oscillator=8000000,interrupt=24")
        time.sleep(2)
        stdin, stdout, stderr = ssh.exec_command("ip link show | grep can")
        interfaces = stdout.read().decode()
        print(f"  {interfaces}")
    
    print("\n[5/7] Bringing up can0 with restart-ms...")
    stdin, stdout, stderr = ssh.exec_command(
        "sudo ip link set can0 type can bitrate 500000 restart-ms 100 && sudo ip link set can0 up"
    )
    time.sleep(2)
    error = stderr.read().decode()
    if error and "Cannot" in error:
        print(f"  ✗ Error: {error}")
    else:
        print("  ✓ can0 up")
    
    print("\n[6/7] Bringing up can1 with restart-ms...")
    stdin, stdout, stderr = ssh.exec_command(
        "sudo ip link set can1 type can bitrate 125000 restart-ms 100 && sudo ip link set can1 up"
    )
    time.sleep(2)
    error = stderr.read().decode()
    if error and "Cannot" in error:
        print(f"  ✗ Error: {error}")
    else:
        print("  ✓ can1 up")
    
    print("\n[7/7] Checking final state...")
    stdin, stdout, stderr = ssh.exec_command("ip link show can0")
    can0_final = stdout.read().decode()
    stdin, stdout, stderr = ssh.exec_command("ip link show can1")
    can1_final = stdout.read().decode()
    
    print("\ncan0 state:")
    for line in can0_final.split('\n')[:3]:
        if line.strip():
            print(f"  {line.strip()}")
    
    print("\ncan1 state:")
    for line in can1_final.split('\n')[:3]:
        if line.strip():
            print(f"  {line.strip()}")
    
    # Check error counters
    print("\n" + "=" * 70)
    stdin, stdout, stderr = ssh.exec_command("ip -s link show can0")
    stats = stdout.read().decode()
    
    print("can0 error counters:")
    for line in stats.split('\n'):
        if 're-started' in line or 'bus-errors' in line or 'RX:' in line or 'TX:' in line:
            print(f"  {line.strip()}")
    
    stdin, stdout, stderr = ssh.exec_command("ip -s link show can1")
    stats = stdout.read().decode()
    
    print("\ncan1 error counters:")
    for line in stats.split('\n'):
        if 're-started' in line or 'bus-errors' in line or 'RX:' in line or 'TX:' in line:
            print(f"  {line.strip()}")
    
    print("\n" + "=" * 70)
    print("DIAGNOSIS")
    print("=" * 70)
    
    if "BUS-OFF" in can0_final or "BUS-OFF" in can1_final:
        print("\n⚠️  STILL IN BUS-OFF STATE")
        print("\nThis means:")
        print("  • The CAN bus is seeing errors/no traffic")
        print("  • Car ignition must be ON for traffic to appear")
        print("  • Once car is ON, restart-ms will auto-recover")
        print("\nActions:")
        print("  1. Make sure car ignition is in ACC or ON")
        print("  2. Wait a few seconds - auto-restart should recover")
        print("  3. If still BUS-OFF: Check CAN wiring (CAN-H, CAN-L)")
    else:
        print("\n✓ Interfaces recovered from BUS-OFF!")
        print("\nTesting for CAN traffic...")
        stdin, stdout, stderr = ssh.exec_command("timeout 3 candump can0 -n 3 2>&1", get_pty=True)
        messages = stdout.read().decode()
        if "can0" in messages:
            print("✓✓✓ CAN traffic detected!")
            print(messages[:200])
        else:
            print("⚠️  No CAN traffic yet (car may not be ready)")
    
    print("\n" + "=" * 70 + "\n")
    
    ssh.close()
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    sys.exit(1)
