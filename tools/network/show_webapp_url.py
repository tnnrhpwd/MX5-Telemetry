#!/usr/bin/env python3
"""Show current webapp URL based on active network"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.lib.pi_ssh import connect as pi_connect


try:
    # Try home WiFi IP first
    ssh = pi_connect(host="192.168.1.23", user="pi", timeout=5)
    connected_via = "192.168.1.23"
except:
    # Try common hotspot IP ranges
    for ip in ["192.168.43.1", "192.168.42.1", "192.168.4.1"]:
        try:
            ssh = pi_connect(host=ip, user="pi", timeout=3)
            connected_via = ip
            break
        except:
            continue

if ssh.get_transport() and ssh.get_transport().is_active():
    print("=" * 70)
    print("WEBAPP ACCESS INFO")
    print("=" * 70)
    
    # Get current SSID
    stdin, stdout, stderr = ssh.exec_command("iwgetid -r")
    ssid = stdout.read().decode().strip()
    
    # Get all IPs
    stdin, stdout, stderr = ssh.exec_command("hostname -I")
    all_ips = stdout.read().decode().strip().split()
    
    print(f"\nConnected to: {ssid if ssid else 'Unknown'}")
    print(f"Accessible via SSH at: {connected_via}")
    print(f"\nAll Pi IP addresses: {' '.join(all_ips)}")
    
    print("\n" + "=" * 70)
    print("WEBAPP URLs:")
    print("=" * 70)
    for ip in all_ips:
        if ':' not in ip:  # Skip IPv6
            print(f"  http://{ip}:5000")
    
    print("\n💡 Save one of these URLs to your phone's home screen!")
    
    ssh.close()
else:
    print("Could not connect to Pi on any known IP address")
