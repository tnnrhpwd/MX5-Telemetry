#!/usr/bin/env python3
"""
Check why webapp isn't starting and fix it
"""

import paramiko

PI_IP = "192.168.1.23"
PI_USER = "pi"
PI_PASSWORD = "Hopwood12"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_IP, username=PI_USER, password=PI_PASSWORD, timeout=10)

print("=" * 70)
print("WEBAPP STARTUP DIAGNOSIS")
print("=" * 70)

# Check if Flask is installed
print("\n[1/4] Checking Flask installation...")
stdin, stdout, stderr = ssh.exec_command("python3 -c 'import flask; print(flask.__version__)'")
output = stdout.read().decode().strip()
error = stderr.read().decode()
if output and not error:
    print(f"  ✓ Flask installed: {output}")
else:
    print(f"  ✗ Flask NOT installed")

# Check if flask-socketio is installed
print("\n[2/4] Checking flask-socketio installation...")
stdin, stdout, stderr = ssh.exec_command("python3 -c 'import flask_socketio; print(flask_socketio.__version__)'")
output = stdout.read().decode().strip()
error = stderr.read().decode()
if output and not error:
    print(f"  ✓ flask-socketio installed: {output}")
else:
    print(f"  ✗ flask-socketio NOT installed")

# Check display app logs for web server messages
print("\n[3/4] Checking display app logs for web server...")
stdin, stdout, stderr = ssh.exec_command("journalctl -u mx5-display.service -n 50 --no-pager | grep -i 'web'")
logs = stdout.read().decode()
if logs:
    print("  Web server related logs:")
    for line in logs.split('\n')[:10]:
        if line.strip():
            print(f"    {line}")
else:
    print("  No web server messages in logs")

# Check if port 5000 is in use
print("\n[4/4] Checking if port 5000 is listening...")
stdin, stdout, stderr = ssh.exec_command("netstat -tlnp 2>/dev/null | grep :5000 || ss -tlnp 2>/dev/null | grep :5000")
port_check = stdout.read().decode()
if port_check:
    print(f"  ✓ Port 5000 is listening:")
    print(f"    {port_check.strip()}")
else:
    print("  ✗ Port 5000 is NOT listening")

print("\n" + "=" * 70)
print("SOLUTION")
print("=" * 70)

if not output or error:
    print("\nFlask or flask-socketio is missing!")
    print("\nInstalling now...")
    stdin, stdout, stderr = ssh.exec_command("sudo pip3 install flask flask-socketio")
    print(stdout.read().decode())
    print("\nRestarting display service...")
    stdin, stdout, stderr = ssh.exec_command("sudo systemctl restart mx5-display")
    stdout.read()
    print("✓ Service restarted - webapp should now be running")
    print(f"\nAccess at: http://{PI_IP}:5000")
else:
    print("\nFlask is installed but webapp not starting")
    print("Check the display app logs for errors")
    
print("=" * 70 + "\n")

ssh.close()
