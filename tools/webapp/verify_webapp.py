#!/usr/bin/env python3
"""
Verify webapp is now running
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.lib.pi_ssh import connect as pi_connect


import time

PI_IP = "192.168.1.23"
PI_USER = "pi"

ssh = pi_connect(host=PI_IP, user=PI_USER, timeout=10)
print("Waiting for service to start...")
time.sleep(5)

print("\nChecking webapp status...")
stdin, stdout, stderr = ssh.exec_command("netstat -tlnp 2>/dev/null | grep :5000 || ss -tlnp 2>/dev/null | grep :5000")
port_check = stdout.read().decode()

if port_check:
    print("✓ Webapp is RUNNING!")
    print(f"\nAccess URLs:")
    print(f"  WiFi mode: http://192.168.1.23:5000")
    print(f"  Hotspot mode: http://192.168.4.1:5000")
else:
    print("✗ Still not running. Checking logs...")
    stdin, stdout, stderr = ssh.exec_command("journalctl -u mx5-display.service -n 20 --no-pager | grep -i web")
    print(stdout.read().decode())

ssh.close()
