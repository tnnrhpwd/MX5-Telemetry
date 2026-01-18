#!/usr/bin/env python3
"""
Check if display app is running and reading CAN data
"""

import paramiko

PI_IP = "192.168.1.23"
PI_USER = "pi"
PI_PASSWORD = "Hopwood12"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_IP, username=PI_USER, password=PI_PASSWORD, timeout=10)

print("=" * 70)
print("DISPLAY APP & CAN DATA CHECK")
print("=" * 70)

# Check if display app is running
print("\n[Display application status]")
stdin, stdout, stderr = ssh.exec_command("ps aux | grep '[m]ain.py'")
output = stdout.read().decode()
if output:
    print("  ✓ Display app is RUNNING")
    print(f"  {output.strip()}")
else:
    print("  ✗ Display app is NOT running")

# Check systemd service
print("\n[mx5-display service status]")
stdin, stdout, stderr = ssh.exec_command("systemctl is-active mx5-display")
status = stdout.read().decode().strip()
print(f"  Status: {status}")

# Check when services started
print("\n[Service start times]")
stdin, stdout, stderr = ssh.exec_command("systemctl show mx5-can.service -p ActiveEnterTimestamp")
can_start = stdout.read().decode().strip()
stdin, stdout, stderr = ssh.exec_command("systemctl show mx5-display.service -p ActiveEnterTimestamp")
display_start = stdout.read().decode().strip()
print(f"  CAN service: {can_start}")
print(f"  Display service: {display_start}")

# Check current CAN packet counts
print("\n[Current CAN statistics]")
stdin, stdout, stderr = ssh.exec_command("ip -s link show can0 | grep -A1 'RX:'")
print("can0:", stdout.read().decode().strip())

stdin, stdout, stderr = ssh.exec_command("ip -s link show can1 | grep -A1 'RX:'")
print("can1:", stdout.read().decode().strip())

# Try to capture some CAN traffic NOW
print("\n[Capturing CAN traffic NOW - 3 seconds]")
stdin, stdout, stderr = ssh.exec_command("timeout 3 candump can0 -n 5 2>&1", get_pty=True)
messages = []
for line in stdout:
    line = line.strip()
    if line and "can0" in line:
        messages.append(line)
        print(f"  {line}")

print("\n" + "=" * 70)
print("DIAGNOSIS")
print("=" * 70)

if messages:
    print("\n✓ CAN traffic IS flowing on can0 right now!")
    print("\nIf display shows bad data, the issue is in:")
    print("  → How the Python app parses CAN messages")
    print("  → Check: pi/ui/src/can_handler.py")
    print("\nPossible parsing bugs:")
    print("  • Wrong byte offset for temperature/fuel/oil")
    print("  • Incorrect scaling factor")
    print("  • Wrong CAN ID mapping")
else:
    print("\n✗ NO CAN traffic on can0 right now")
    print("\nPossible causes:")
    print("  • Car just went to sleep (turn key to ACC again)")
    print("  • CAN bus disconnected")
    print("  • Wrong OBD-II pins")

# Check application logs for errors
print("\n[Recent application logs]")
stdin, stdout, stderr = ssh.exec_command("journalctl -u mx5-display.service -n 20 --no-pager")
logs = stdout.read().decode()
if "error" in logs.lower() or "fail" in logs.lower():
    print("  ⚠️  Errors in logs:")
    for line in logs.split('\n'):
        if 'error' in line.lower() or 'fail' in line.lower():
            print(f"    {line}")
else:
    print("  ✓ No errors in recent logs")

print("\n" + "=" * 70)

ssh.close()
