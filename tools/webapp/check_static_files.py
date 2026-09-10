#!/usr/bin/env python3
"""Check if static files exist on Pi"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.lib.pi_ssh import connect as pi_connect


ssh = pi_connect(host="192.168.1.23", user="pi", timeout=10)
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
