#!/usr/bin/env python3
"""Find all telemetry_data.py files and check service path"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.lib.pi_ssh import connect as pi_connect


ssh = pi_connect(host="192.168.1.23", user="pi", timeout=10)
print("=" * 70)
print("Finding ALL telemetry_data.py files:")
print("=" * 70)
stdin, stdout, stderr = ssh.exec_command("find /home/pi -name 'telemetry_data.py' 2>/dev/null")
files = stdout.read().decode()
print(files)

print("\n" + "=" * 70)
print("Service definition:")
print("=" * 70)
stdin, stdout, stderr = ssh.exec_command("cat /etc/systemd/system/mx5-display.service")
service = stdout.read().decode()
print(service)

print("\n" + "=" * 70)
print("Python path being used:")
print("=" * 70)
stdin, stdout, stderr = ssh.exec_command("journalctl -u mx5-display.service --since '1 minute ago' --no-pager | grep 'Starting\\|WorkingDirectory\\|python' | head -3")
print(stdout.read().decode())

ssh.close()
