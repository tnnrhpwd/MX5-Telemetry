#!/usr/bin/env python3
"""Clear Python cache and restart"""
import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.1.23", username="pi", password="Hopwood12", timeout=10)

print("Clearing Python cache...")
stdin, stdout, stderr = ssh.exec_command("find /home/pi/MX5-Telemetry/pi/ui -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null; echo 'Done'")
print(stdout.read().decode())

print("Removing .pyc files...")
stdin, stdout, stderr = ssh.exec_command("find /home/pi/MX5-Telemetry/pi/ui -name '*.pyc' -delete; echo 'Done'")
print(stdout.read().decode())

print("\nRestarting mx5-display service...")
stdin, stdout, stderr = ssh.exec_command("sudo systemctl restart mx5-display")
stdout.read()
print("✓ Restarted")

print("\nWaiting 10 seconds for startup...")
time.sleep(10)

print("\nChecking logs...")
stdin, stdout, stderr = ssh.exec_command("journalctl -u mx5-display.service --since '12 seconds ago' --no-pager | grep -E 'oil_status|Started|Traceback' | tail -20")
logs = stdout.read().decode()
print(logs)

if "oil_status" not in logs:
    print("\n✓ No more oil_status errors!")
else:
    print("\n✗ Still getting oil_status errors")

ssh.close()
