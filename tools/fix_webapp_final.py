#!/usr/bin/env python3
"""
Fix flask-socketio compatibility and start webapp
"""

import paramiko
import time

PI_IP = "192.168.1.23"
PI_USER = "pi"
PI_PASSWORD = "Hopwood12"

print("=" * 70)
print("FIXING WEBAPP - INSTALLING COMPATIBLE VERSIONS")
print("=" * 70)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_IP, username=PI_USER, password=PI_PASSWORD, timeout=10)

print("\n[1/4] Uninstalling incompatible flask-socketio...")
stdin, stdout, stderr = ssh.exec_command("sudo pip3 uninstall -y flask-socketio python-socketio")
stdout.read()
print("  ✓ Removed")

print("\n[2/4] Installing compatible versions...")
print("  (This may take 30-60 seconds)")
stdin, stdout, stderr = ssh.exec_command(
    "sudo pip3 install 'python-socketio==4.6.1' 'flask-socketio==4.3.2'"
)
output = stdout.read().decode()
if "Successfully installed" in output:
    print("  ✓ Installed compatible versions")
else:
    print(f"  Output: {output[-300:]}")

print("\n[3/4] Restarting display service...")
stdin, stdout, stderr = ssh.exec_command("sudo systemctl restart mx5-display")
stdout.read()
print("  ✓ Service restarted")

print("\n[4/4] Waiting for webapp to start...")
time.sleep(8)

# Check if webapp is running
for attempt in range(3):
    stdin, stdout, stderr = ssh.exec_command("ss -tlnp | grep :5000")
    result = stdout.read().decode()
    
    if ":5000" in result:
        print("\n" + "=" * 70)
        print("✓✓✓ WEBAPP IS RUNNING!")
        print("=" * 70)
        print("\n📱 Open on your phone:\n")
        print("   http://192.168.1.23:5000")
        print("\n   (Make sure phone is on same WiFi)")
        print("\n" + "=" * 70)
        ssh.close()
        exit(0)
    
    if attempt < 2:
        print(f"  Attempt {attempt+1}/3 - waiting 3 more seconds...")
        time.sleep(3)

# Still not running - check logs
print("\n✗ Webapp not starting. Checking logs...")
stdin, stdout, stderr = ssh.exec_command("journalctl -u mx5-display.service -n 30 --no-pager | tail -20")
print(stdout.read().decode())

ssh.close()
