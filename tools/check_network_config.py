#!/usr/bin/env python3
"""Check Pi network configuration"""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.1.23", username="pi", password="Hopwood12", timeout=10)

print("=" * 70)
print("NETWORK CONFIGURATION")
print("=" * 70)

print("\n[1] Checking wpa_supplicant.conf...")
stdin, stdout, stderr = ssh.exec_command("sudo cat /etc/wpa_supplicant/wpa_supplicant.conf")
wpa_config = stdout.read().decode()
print(wpa_config)

print("\n[2] Current WiFi connection...")
stdin, stdout, stderr = ssh.exec_command("iwgetid -r")
current_ssid = stdout.read().decode().strip()
print(f"Connected to: {current_ssid}")

print("\n[3] Available networks...")
stdin, stdout, stderr = ssh.exec_command("sudo iwlist wlan0 scan | grep -E 'ESSID|Quality'")
available = stdout.read().decode()
print(available[:1000] if len(available) > 1000 else available)

ssh.close()
