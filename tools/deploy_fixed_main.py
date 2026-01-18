#!/usr/bin/env python3
"""Deploy fixed main.py to Pi"""
import paramiko
import time

PI_IP = "192.168.1.23"
PI_USER = "pi"
PI_PASSWORD = "Hopwood12"

# Read local file
with open(r"c:\Users\tanne\Documents\Github\MX5-Telemetry\pi\ui\src\main.py", 'r', encoding='utf-8') as f:
    local_content = f.read()

# Connect and upload
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_IP, username=PI_USER, password=PI_PASSWORD, timeout=10)

sftp = ssh.open_sftp()
print("Uploading main.py with fixed TelemetryData...")
with sftp.open('/home/pi/MX5-Telemetry/pi/ui/src/main.py', 'w') as f:
    f.write(local_content)
sftp.close()
print("✓ Uploaded")

print("\nClearing Python cache...")
stdin, stdout, stderr = ssh.exec_command("find /home/pi/MX5-Telemetry/pi/ui -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null; find /home/pi/MX5-Telemetry/pi/ui -name '*.pyc' -delete")
stdout.read()
print("✓ Cleared")

print("\nRestarting service...")
stdin, stdout, stderr = ssh.exec_command("sudo systemctl restart mx5-display")
stdout.read()
print("✓ Restarted")

print("\nWaiting 10 seconds for startup...")
time.sleep(10)

print("\n" + "=" * 70)
print("Checking for oil_status errors...")
print("=" * 70)
stdin, stdout, stderr = ssh.exec_command("journalctl -u mx5-display.service --since '12 seconds ago' --no-pager | grep 'oil_status' | head -3")
errors = stdout.read().decode()

if errors.strip():
    print("✗ Still errors:")
    print(errors)
else:
    print("✓✓✓ NO OIL_STATUS ERRORS! ✓✓✓")
    
    # Show ESP32 TX messages
    print("\nESP32 TX messages showing oil data:")
    stdin, stdout, stderr = ssh.exec_command("journalctl -u mx5-display.service --since '12 seconds ago' --no-pager | grep 'ESP32 TX' | tail -5")
    print(stdout.read().decode())

ssh.close()
