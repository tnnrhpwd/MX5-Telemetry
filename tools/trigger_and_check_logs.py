#!/usr/bin/env python3
"""Trigger setting change and immediately check logs"""
import paramiko
import requests
import time

# Send request
print("Sending LED sequence change...")
try:
    resp = requests.post('http://192.168.1.23:5000/api/settings/update',
                         json={'name': 'led_sequence', 'value': 2},
                         timeout=2)
    print(f"Response: {resp.status_code}")
    if resp.status_code != 200:
        print(f"Body: {resp.text}")
except Exception as e:
    print(f"Error: {e}")

time.sleep(1)

# Check logs
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.1.23", username="pi", password="Hopwood12", timeout=10)

print("\nChecking logs...")
stdin, stdout, stderr = ssh.exec_command("journalctl -u mx5-display.service --since '10 seconds ago' --no-pager | tail -30")
print(stdout.read().decode())

ssh.close()
