#!/usr/bin/env python3
"""Check what process has Arduino serial port open"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.lib.pi_ssh import connect as pi_connect


ssh = pi_connect(host="192.168.1.23", user="pi", timeout=10)
print("Checking what has /dev/ttyUSB0 open...")
stdin, stdout, stderr = ssh.exec_command("sudo lsof /dev/ttyUSB0 2>/dev/null")
result = stdout.read().decode()

if result.strip():
    print("Processes using /dev/ttyUSB0:")
    print(result)
else:
    print("No process has /dev/ttyUSB0 open")

print("\nChecking if mx5-display service has arduino_serial active...")
stdin, stdout, stderr = ssh.exec_command("journalctl -u mx5-display.service --since '5 minutes ago' --no-pager | grep 'Arduino serial'")
log = stdout.read().decode()
if log.strip():
    print(log)
else:
    print("No Arduino serial connection in recent logs")

ssh.close()
