#!/usr/bin/env python3
"""Redeploy esp32_serial_handler.py"""
import paramiko
import time

PI_IP = "192.168.1.23"
PI_USER = "pi"
PI_PASSWORD = "Hopwood12"

# Read local file
with open(r"c:\Users\tanne\Documents\Github\MX5-Telemetry\pi\ui\src\esp32_serial_handler.py", 'r') as f:
    local_content = f.read()

# Connect and upload
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_IP, username=PI_USER, password=PI_PASSWORD, timeout=10)

sftp = ssh.open_sftp()
print("Uploading esp32_serial_handler.py...")
with sftp.open('/home/pi/MX5-Telemetry/pi/ui/src/esp32_serial_handler.py', 'w') as f:
    f.write(local_content)
sftp.close()
print("✓ Uploaded")

print("\nClearingPython cache...")
stdin, stdout, stderr = ssh.exec_command("find /home/pi/MX5-Telemetry/pi/ui/src -name '__pycache__' -exec rm -rf {} + 2>/dev/null; find /home/pi/MX5-Telemetry/pi/ui/src -name '*.pyc' -delete")
stdout.read()
print("✓ Cleared")

print("\nRestarting service...")
stdin, stdout, stderr = ssh.exec_command("sudo systemctl restart mx5-display")
stdout.read()
print("✓ Restarted")

print("\nWaiting 10 seconds...")
time.sleep(10)

print("\nChecking logs for oil_status errors...")
stdin, stdout, stderr = ssh.exec_command("journalctl -u mx5-display.service --since '12 seconds ago' --no-pager | grep 'oil_status' | head -5")
errors = stdout.read().decode()

if errors.strip():
    print("✗ Still errors:")
    print(errors)
else:
    print("✓ No oil_status errors!")
    
    # Show recent telemetry
    print("\nRecent ESP32 TX messages:")
    stdin, stdout, stderr = ssh.exec_command("journalctl -u mx5-display.service --since '12 seconds ago' --no-pager | grep 'ESP32 TX' | tail -3")
    print(stdout.read().decode())

ssh.close()
