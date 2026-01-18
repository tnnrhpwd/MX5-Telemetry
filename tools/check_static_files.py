#!/usr/bin/env python3
"""Check if static files exist on Pi"""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.1.23", username="pi", password="Hopwood12", timeout=10)

print("Checking for static files on Pi...")
stdin, stdout, stderr = ssh.exec_command("ls -lh /home/pi/MX5-Telemetry/pi/ui/static/")
result = stdout.read().decode()
error = stderr.read().decode()

if error and "No such file" in error:
    print("✗ Static directory does NOT exist!")
else:
    print("Static files:")
    print(result)

ssh.close()
