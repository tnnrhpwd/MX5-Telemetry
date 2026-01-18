#!/usr/bin/env python3
"""Quick check current network"""
import paramiko

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect("192.168.1.23", username="pi", password="Hopwood12", timeout=5)
    
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
