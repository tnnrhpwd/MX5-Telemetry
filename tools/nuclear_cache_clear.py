#!/usr/bin/env python3
"""Nuclear option - completely clear all cache and force reload"""
import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.1.23", username="pi", password="Hopwood12", timeout=10)

commands = [
    ("Stop service", "sudo systemctl stop mx5-display"),
    ("Remove ALL pycache", "find /home/pi/MX5-Telemetry -type d -name '__pycache__' -exec rm -rfv {} + 2>/dev/null || true"),
    ("Remove ALL .pyc files", "find /home/pi/MX5-Telemetry -name '*.pyc' -delete -print"),
    ("Remove ALL .pyo files", "find /home/pi/MX5-Telemetry -name '*.pyo' -delete"),
    ("Verify oil_status in file", "grep 'oil_status:' /home/pi/MX5-Telemetry/pi/ui/src/telemetry_data.py"),
    ("Start service", "sudo systemctl start mx5-display"),
]

for desc, cmd in commands:
    print(f"\n[{desc}]")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip():
        print(out[:500])  # Limit output
    if err.strip() and "No such file" not in err:
        print("ERR:", err[:500])
    print("✓")
    
    if "Start service" in desc:
        print("Waiting 10 seconds for startup...")
        time.sleep(10)

print("\n" + "=" * 70)
print("Checking for oil_status errors in last 12 seconds...")
print("=" * 70)
stdin, stdout, stderr = ssh.exec_command("journalctl -u mx5-display.service --since '12 seconds ago' --no-pager | grep 'oil_status'")
errors = stdout.read().decode()

if errors.strip():
    print("✗ STILL ERRORS:")
    print(errors[:1000])
else:
    print("✓✓✓ NO OIL_STATUS ERRORS! ✓✓✓")
    
    # Show actual telemetry
    print("\nESP32 TX messages:")
    stdin, stdout, stderr = ssh.exec_command("journalctl -u mx5-display.service --since '12 seconds ago' --no-pager | grep 'ESP32 TX' | tail -3")
    print(stdout.read().decode())

ssh.close()
