#!/usr/bin/env python3
"""Check for webapp templates"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.lib.pi_ssh import connect as pi_connect


ssh = pi_connect(host="192.168.1.23", user="pi", timeout=10)
print("Searching for templates directory and index.html...")
stdin, stdout, stderr = ssh.exec_command("find /home/pi/MX5-Telemetry -name 'templates' -type d")
templates_dirs = stdout.read().decode()
print("Templates directories:")
print(templates_dirs if templates_dirs.strip() else "None found")

print("\nSearching for index.html...")
stdin, stdout, stderr = ssh.exec_command("find /home/pi/MX5-Telemetry -name 'index.html'")
index_files = stdout.read().decode()
print(index_files if index_files.strip() else "None found")

print("\nChecking web_server.py location and expected template path...")
stdin, stdout, stderr = ssh.exec_command("grep -n 'template' /home/pi/MX5-Telemetry/pi/ui/src/web_server.py | head -5")
print(stdout.read().decode())

ssh.close()
