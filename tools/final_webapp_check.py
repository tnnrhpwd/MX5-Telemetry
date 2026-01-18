#!/usr/bin/env python3
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.1.23", username='pi', password='Hopwood12')

# Check flask-socketio
stdin, stdout, stderr = ssh.exec_command("python3 -c 'import flask_socketio; print(flask_socketio.__version__)'")
version = stdout.read().decode().strip()
error = stderr.read().decode()

print(f"flask-socketio: {version if version else 'NOT INSTALLED'}")
if error:
    print(f"Error: {error}")

# Check logs for web server
stdin, stdout, stderr = ssh.exec_command("journalctl -u mx5-display.service --since '1 min ago' --no-pager | grep -i 'web\\|flask\\|initializing'")
logs = stdout.read().decode()
if logs:
    print("\nWeb server logs:")
    print(logs)
else:
    print("\nNo web server messages in logs")

# Check if port 5000 is open
stdin, stdout, stderr = ssh.exec_command("ss -tlnp | grep :5000")
port = stdout.read().decode()

print("\nPort 5000 status:")
if port:
    print(f"✓ LISTENING: {port.strip()}")
    print("\n" + "=" * 60)
    print("WEBAPP URL:")
    print("=" * 60)
    print("\n  http://192.168.1.23:5000")
    print("\n  (Open on your phone)")
    print("=" * 60)
else:
    print("✗ NOT listening")

ssh.close()
