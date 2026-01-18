#!/usr/bin/env python3
"""Test webapp WebSocket functionality"""
import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.1.23", username="pi", password="Hopwood12", timeout=10)

print("=" * 70)
print("WEBAPP WEBSOCKET DIAGNOSTIC")
print("=" * 70)

print("\n[1] Checking flask-socketio installation...")
stdin, stdout, stderr = ssh.exec_command("python3 -c 'import flask_socketio; print(flask_socketio.__version__)'")
version = stdout.read().decode().strip()
error = stderr.read().decode().strip()
if version:
    print(f"✓ flask-socketio version: {version}")
else:
    print(f"✗ flask-socketio not available: {error}")

print("\n[2] Checking if WebRemoteServer initialized...")
stdin, stdout, stderr = ssh.exec_command("journalctl -u mx5-display.service --since '10 minutes ago' --no-pager | grep -i 'web remote'")
web_init = stdout.read().decode().strip()
if web_init:
    print("✓ WebRemoteServer initialization:")
    print(web_init)
else:
    print("✗ No WebRemoteServer initialization found")

print("\n[3] Watching for socketio events (press a button in the webapp now)...")
print("Monitoring logs for 15 seconds...")

# Start monitoring in background
stdin, stdout, stderr = ssh.exec_command("timeout 15 journalctl -u mx5-display.service -f --no-pager 2>&1")

time.sleep(16)

# Get the output
output = stdout.read().decode()
if "socketio" in output.lower() or "button" in output.lower() or "screen" in output.lower():
    print("\n✓ Events detected:")
    for line in output.split('\n')[-30:]:
        if line.strip():
            print(line)
else:
    print("\n✗ No socketio events detected")
    print("\nThis means WebSocket connections are not working.")
    print("Recent logs:")
    for line in output.split('\n')[-10:]:
        if line.strip():
            print(line)

print("\n[4] Checking web_server.py for socketio setup...")
stdin, stdout, stderr = ssh.exec_command("grep -n 'socketio' /home/pi/MX5-Telemetry/pi/ui/src/web_server.py | head -10")
socketio_code = stdout.read().decode()
print(socketio_code if socketio_code.strip() else "No socketio references found")

ssh.close()
