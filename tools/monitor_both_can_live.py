#!/usr/bin/env python3
"""
Live monitor both CAN buses simultaneously
"""
import paramiko
import time

PI_IP = "192.168.1.23"
PI_USER = "pi"
PI_PASSWORD = "Hopwood12"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_IP, username=PI_USER, password=PI_PASSWORD, timeout=10)

print("LIVE CAN MONITOR - Both Buses")
print("=" * 70)
print("Turn the car key to ACC now!\n")

# Start monitoring both buses
print("[Monitoring can0 @ 500kbps and can1 @ 125kbps for 5 seconds]\n")

command = """
echo "=== can0 (500kbps) ===" & timeout 5 candump can0 2>&1 | head -15 &
echo "=== can1 (125kbps) ===" & timeout 5 candump can1 2>&1 | head -15 &
wait
"""

stdin, stdout, stderr = ssh.exec_command(command)
output = stdout.read().decode()
error = stderr.read().decode()

print(output)
if error:
    print("Errors:", error)

# Check packet counts
print("\n[Packet counts after monitoring]")
stdin, stdout, stderr = ssh.exec_command("ip -s link show can0 | grep 'RX:' -A1")
print("can0:", stdout.read().decode().strip())

stdin, stdout, stderr = ssh.exec_command("ip -s link show can1 | grep 'RX:' -A1")
print("can1:", stdout.read().decode().strip())

ssh.close()
