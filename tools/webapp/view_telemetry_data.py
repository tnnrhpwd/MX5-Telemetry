#!/usr/bin/env python3
"""View actual file content"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.lib.pi_ssh import connect as pi_connect


ssh = pi_connect(host="192.168.1.23", user="pi", timeout=10)
print("Full telemetry_data.py content:")
print("=" * 70)
stdin, stdout, stderr = ssh.exec_command("cat /home/pi/MX5-Telemetry/pi/ui/src/telemetry_data.py")
print(stdout.read().decode())

ssh.close()
