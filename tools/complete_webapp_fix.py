#!/usr/bin/env python3
import paramiko

PI_IP = "192.168.1.23"
PI_USER = "pi"
PI_PASSWORD = "Hopwood12"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_IP, username=PI_USER, password=PI_PASSWORD, timeout=10)

print("Checking flask-socketio installation...")
stdin, stdout, stderr = ssh.exec_command("python3 -c 'import flask_socketio; print(\"OK\")'")
result = stdout.read().decode().strip()

if result == "OK":
    print("✓ flask-socketio is installed\n")
    print("Restarting display service...")
    stdin, stdout, stderr = ssh.exec_command("sudo systemctl restart mx5-display")
    stdout.read()
    
    import time
    time.sleep(5)
    
    print("Checking webapp...")
    stdin, stdout, stderr = ssh.exec_command("netstat -tlnp 2>/dev/null | grep :5000 || ss -tlnp | grep :5000")
    port = stdout.read().decode()
    
    if port:
        print("\n✓✓✓ WEBAPP IS RUNNING!")
        print(f"\n📱 Access at:")
        print(f"   WiFi: http://192.168.1.23:5000")
        print(f"   Hotspot: http://192.168.4.1:5000")
    else:
        print("\n✗ Still not running")
        stdin, stdout, stderr = ssh.exec_command("journalctl -u mx5-display.service --since '1 min ago' --no-pager | tail -20")
        print(stdout.read().decode())
else:
    print("✗ flask-socketio still not installed")
    print("Installing manually...")
    stdin, stdout, stderr = ssh.exec_command("sudo pip3 install flask-socketio python-socketio")
    print(stdout.read().decode())

ssh.close()
