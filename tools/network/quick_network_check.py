#!/usr/bin/env python3
"""Quick check current network"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.lib.pi_ssh import connect as pi_connect


try:

    ssh = pi_connect(host="192.168.1.23", user="pi", timeout=5)
    stdin, stdout, stderr = ssh.exec_command("iwgetid -r")
    ssid = stdout.read().decode().strip()
    
    stdin, stdout, stderr = ssh.exec_command("hostname -I")
    ip = stdout.read().decode().strip().split()[0]
    
    print(f"Connected to: {ssid or 'None'}")
    print(f"IP address: {ip}")
    
    if "Galaxy" in ssid:
        print("\n✓ Connected to HOTSPOT")
    else:
        print(f"\n✗ Connected to {ssid} (not hotspot)")
    
    ssh.close()
except Exception as e:
    print(f"Connection failed (Pi may have switched networks): {e}")
    print("\nTry connecting to hotspot IP:")
    print("ssh pi@192.168.1.1")
