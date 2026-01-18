#!/usr/bin/env python3
"""Check if webapp is running"""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.1.23", username="pi", password="Hopwood12", timeout=10)

print("=" * 70)
print("WEBAPP STATUS CHECK")
print("=" * 70)

print("\n[1] Checking if port 5000 is listening...")
stdin, stdout, stderr = ssh.exec_command("ss -tlnp | grep :5000")
port_status = stdout.read().decode().strip()
if port_status:
    print("✓ Port 5000 is LISTENING")
    print(port_status)
else:
    print("✗ Port 5000 is NOT listening")

print("\n[2] Checking flask-socketio installation...")
stdin, stdout, stderr = ssh.exec_command("pip3 list | grep -E 'flask-socketio|python-socketio'")
packages = stdout.read().decode().strip()
if packages:
    print("✓ Packages installed:")
    print(packages)
else:
    print("✗ flask-socketio not installed")

print("\n[3] Checking for webapp errors in logs...")
stdin, stdout, stderr = ssh.exec_command("journalctl -u mx5-display.service --since '5 minutes ago' --no-pager | grep -E 'flask|socketio|WebRemote|5000' | tail -10")
logs = stdout.read().decode().strip()
if logs:
    print("Recent webapp-related log entries:")
    print(logs)
else:
    print("No recent webapp logs found")

print("\n[4] Checking if WebRemoteServer is initialized...")
stdin, stdout, stderr = ssh.exec_command("journalctl -u mx5-display.service --since '5 minutes ago' --no-pager | grep 'Web remote'")
web_logs = stdout.read().decode().strip()
if web_logs:
    print(web_logs)
else:
    print("No 'Web remote' initialization messages found")

print("\n" + "=" * 70)
if port_status:
    print("✓✓✓ WEBAPP IS RUNNING ✓✓✓")
    print(f"\nAccess at: http://192.168.1.23:5000")
else:
    print("✗ WEBAPP IS NOT RUNNING")
    print("\nPossible reasons:")
    print("  - flask-socketio not installed or wrong version")
    print("  - Import error in main.py")
    print("  - Service started before packages were installed")
print("=" * 70)

ssh.close()
