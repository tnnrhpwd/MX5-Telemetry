#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""View file content with UTF-8 handling"""
import paramiko
import sys

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.1.23", username="pi", password="Hopwood12", timeout=10)

print("=" * 70)
print("Oil-related lines from telemetry_data.py:")
print("=" * 70)
stdin, stdout, stderr = ssh.exec_command("grep -n 'oil' /home/pi/MX5-Telemetry/pi/ui/src/telemetry_data.py")
result = stdout.read().decode('utf-8', errors='replace')
print(result)

print("\n" + "=" * 70)
print("Lines 35-50 (around oil field):")
print("=" * 70)
stdin, stdout, stderr = ssh.exec_command("sed -n '35,50p' /home/pi/MX5-Telemetry/pi/ui/src/telemetry_data.py")
result = stdout.read().decode('utf-8', errors='replace')
print(result)

ssh.close()
