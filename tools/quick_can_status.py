#!/usr/bin/env python3
"""
Quick status check - CAN state and traffic test
"""

import paramiko

PI_IP = "192.168.1.23"
PI_USER = "pi"
PI_PASSWORD = "Hopwood12"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_IP, username=PI_USER, password=PI_PASSWORD, timeout=10)

print("=" * 70)
print("CAN STATUS CHECK")
print("=" * 70)

# Check can0 state
print("\n[can0 state]")
stdin, stdout, stderr = ssh.exec_command("ip link show can0")
output = stdout.read().decode()
for line in output.split('\n')[:2]:
    print(line)

if "BUS-OFF" in output:
    print("  ⚠️  BUS-OFF STATE DETECTED")
elif "UP" in output:
    print("  ✓ Interface is UP")

# Check can1 state
print("\n[can1 state]")
stdin, stdout, stderr = ssh.exec_command("ip link show can1")
output = stdout.read().decode()
for line in output.split('\n')[:2]:
    print(line)

if "BUS-OFF" in output:
    print("  ⚠️  BUS-OFF STATE DETECTED")
elif "UP" in output:
    print("  ✓ Interface is UP")

# Check error counters
print("\n[can0 statistics]")
stdin, stdout, stderr = ssh.exec_command("ip -s link show can0 | grep -A2 'RX:'")
print(stdout.read().decode())

print("[can1 statistics]")
stdin, stdout, stderr = ssh.exec_command("ip -s link show can1 | grep -A2 'RX:'")
print(stdout.read().decode())

# Test for actual CAN traffic
print("\n[Testing can0 traffic - 5 seconds]")
stdin, stdout, stderr = ssh.exec_command("timeout 5 candump can0 -n 10 2>&1", get_pty=True)
messages = []
for line in stdout:
    line = line.strip()
    if line and "can0" in line:
        messages.append(line)
        print(f"  {line}")

if not messages:
    print("  ✗ NO TRAFFIC on can0")
    print("\n[Checking if car is sending CAN data]")
    print("  Is car ignition in ACC or ON position?")
else:
    print(f"\n  ✓ Received {len(messages)} messages")

print("\n" + "=" * 70)

if "BUS-OFF" in output:
    print("\n⚠️  ACTION REQUIRED: Run fix script")
    print("  python tools/force_recover_busoff.py")
elif not messages:
    print("\n⚠️  Interfaces OK but no CAN traffic")
    print("  • Check car ignition is in ACC/ON")
    print("  • Verify CAN-H/CAN-L wiring to OBD-II port")
else:
    print("\n✓ CAN is working! Check display application")

ssh.close()
