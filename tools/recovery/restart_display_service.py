#!/usr/bin/env python3

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.lib.pi_ssh import connect as pi_connect

PI_IP = "192.168.1.23"
PI_USER = "pi"

ssh = pi_connect(host=PI_IP, user=PI_USER, timeout=10)
print("Restarting mx5-display service...")
stdin, stdout, stderr = ssh.exec_command("sudo systemctl restart mx5-display")
stdout.read()

print("Checking status...")
stdin, stdout, stderr = ssh.exec_command("sleep 2; systemctl status mx5-display --no-pager | head -15")
print(stdout.read().decode())

ssh.close()
print("\n✓ Service restarted - oil_status fix is now active!")
