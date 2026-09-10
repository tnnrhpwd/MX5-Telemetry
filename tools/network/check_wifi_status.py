#!/usr/bin/env python3
"""Check current WiFi connection"""
import os
import sys

# Add repo root so tools.lib is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.lib.pi_ssh import connect

ssh = connect()

print("Current WiFi status:")
stdin, stdout, stderr = ssh.exec_command("iwgetid -r")
current_ssid = stdout.read().decode().strip()
print(f"  Connected to: {current_ssid}")

stdin, stdout, stderr = ssh.exec_command("hostname -I")
ip = stdout.read().decode().strip()
print(f"  IP Address: {ip}")

ssh.close()
