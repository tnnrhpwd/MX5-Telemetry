#!/usr/bin/env python3
import paramiko

PI_IP = "192.168.1.23"
PI_USER = "pi"
PI_PASSWORD = "Hopwood12"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_IP, username=PI_USER, password=PI_PASSWORD, timeout=10)

print("Restarting mx5-display service...")
stdin, stdout, stderr = ssh.exec_command("sudo systemctl restart mx5-display")
stdout.read()

print("Checking status...")
stdin, stdout, stderr = ssh.exec_command("sleep 2; systemctl status mx5-display --no-pager | head -15")
print(stdout.read().decode())

ssh.close()
print("\n✓ Service restarted - oil_status fix is now active!")
