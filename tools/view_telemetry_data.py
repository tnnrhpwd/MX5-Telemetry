#!/usr/bin/env python3
"""View actual file content"""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.1.23", username="pi", password="Hopwood12", timeout=10)

print("Full telemetry_data.py content:")
print("=" * 70)
stdin, stdout, stderr = ssh.exec_command("cat /home/pi/MX5-Telemetry/pi/ui/src/telemetry_data.py")
print(stdout.read().decode())

ssh.close()
