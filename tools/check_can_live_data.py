#!/usr/bin/env python3
"""
Check live CAN data on both buses to see which has HS-CAN data
"""
import paramiko

PI_IP = "192.168.1.23"
PI_USER = "pi"
PI_PASSWORD = "Hopwood12"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_IP, username=PI_USER, password=PI_PASSWORD, timeout=10)

print("Checking which CAN interface has OEM HS-CAN data...")
print("=" * 70)

print("\n[can0 - Checking for HS-CAN IDs like 0x201 (RPM), 0x420 (coolant)]")
stdin, stdout, stderr = ssh.exec_command("timeout 3 candump can0 2>&1 | head -20")
can0_output = stdout.read().decode()
print(can0_output if can0_output else "  No data on can0")

print("\n[can1 - Checking for HS-CAN IDs like 0x201 (RPM), 0x420 (coolant)]")
stdin, stdout, stderr = ssh.exec_command("timeout 3 candump can1 2>&1 | head -20")
can1_output = stdout.read().decode()
print(can1_output if can1_output else "  No data on can1")

# Check which has the right IDs
if '201' in can1_output or '420' in can1_output:
    print("\n✓ HS-CAN data (0x201/0x420) found on can1")
elif '201' in can0_output or '420' in can0_output:
    print("\n✓ HS-CAN data (0x201/0x420) found on can0")
else:
    print("\n⚠ No HS-CAN data found - car may need key turned to ACC")

ssh.close()
