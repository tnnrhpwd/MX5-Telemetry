#!/usr/bin/env python3

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.lib.pi_ssh import connect as pi_connect

PI_IP = "192.168.1.23"

ssh = pi_connect(host=PI_IP, user='pi', timeout=10)
print("Restarting display service...")
stdin, stdout, stderr = ssh.exec_command("sudo systemctl restart mx5-display")
stdout.read()

import time
time.sleep(5)

print("\nChecking webapp status...\n")

# Check if port 5000 is listening
stdin, stdout, stderr = ssh.exec_command("ss -tlnp | grep :5000")
port_output = stdout.read().decode()

if ":5000" in port_output:
    print("=" * 60)
    print("✓✓✓ WEBAPP IS RUNNING!")
    print("=" * 60)
    print(f"\n📱 Open this on your phone:")
    print(f"\n   http://192.168.1.23:5000")
    print(f"\n   (Make sure phone is on same WiFi network)")
    print("\n" + "=" * 60)
else:
    print("✗ Not running yet. Checking why...")
    stdin, stdout, stderr = ssh.exec_command("journalctl -u mx5-display.service -n 30 --no-pager")
    print(stdout.read().decode())

ssh.close()
