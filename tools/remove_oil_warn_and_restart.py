#!/usr/bin/env python3
"""Remove oil_warn_f and restart service"""

import paramiko
import time

PI_IP = "192.168.1.23"
PI_USER = "pi"
PI_PASSWORD = "Hopwood12"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_IP, username=PI_USER, password=PI_PASSWORD, timeout=10)

print("Removing oil_warn_f from telemetry_data.py...")
stdin, stdout, stderr = ssh.exec_command("sed -i '/oil_warn_f.*=.*250/d' /home/pi/MX5-Telemetry/pi/ui/src/telemetry_data.py")
stdout.read()
print("✓ Removed")

print("\nRestarting mx5-display service...")
stdin, stdout, stderr = ssh.exec_command("sudo systemctl restart mx5-display")
stdout.read()
print("✓ Restarted")

print("\nWaiting 8 seconds for startup...")
time.sleep(8)

print("\nChecking logs for oil_status errors...")
stdin, stdout, stderr = ssh.exec_command("journalctl -u mx5-display.service --since '10 seconds ago' --no-pager | grep -E 'oil_status|oil_warn'")
logs = stdout.read().decode()

if "oil_status" in logs or "oil_warn" in logs:
    print("✗ Errors found:")
    print(logs)
else:
    print("✓ No oil-related errors!")

ssh.close()
