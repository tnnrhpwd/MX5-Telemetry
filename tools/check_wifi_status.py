#!/usr/bin/env python3
"""Check current WiFi connection"""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.1.23", username="pi", password="Hopwood12", timeout=10)

print("Current WiFi status:")
stdin, stdout, stderr = ssh.exec_command("iwgetid -r")
current_ssid = stdout.read().decode().strip()
print(f"  Connected to: {current_ssid}")

stdin, stdout, stderr = ssh.exec_command("hostname -I")
ip = stdout.read().decode().strip()
print(f"  IP Address: {ip}")

ssh.close()
