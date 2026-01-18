#!/usr/bin/env python3
"""Force Pi to reconnect and prioritize hotspot"""
import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.1.23", username="pi", password="Hopwood12", timeout=10)

print("=" * 70)
print("SWITCHING TO HOTSPOT")
print("=" * 70)

print("\n[1] Current connection...")
stdin, stdout, stderr = ssh.exec_command("iwgetid -r")
current = stdout.read().decode().strip()
print(f"Currently connected to: {current or 'None'}")

print("\n[2] Checking if hotspot is available...")
stdin, stdout, stderr = ssh.exec_command("sudo iwlist wlan0 scan | grep -i \"Tanner's Galaxy\"")
hotspot_found = stdout.read().decode().strip()
if hotspot_found:
    print("✓ Hotspot detected!")
else:
    print("✗ Hotspot not found in scan")
    print("Make sure your phone hotspot is turned on")

print("\n[3] Forcing network reconnection...")
stdin, stdout, stderr = ssh.exec_command("sudo wpa_cli -i wlan0 reconfigure")
stdout.read()
print("✓ Reconfigure command sent")

print("\n[4] Waiting 5 seconds for reconnection...")
time.sleep(5)

print("\n[5] Checking new connection...")
stdin, stdout, stderr = ssh.exec_command("iwgetid -r")
new_connection = stdout.read().decode().strip()
print(f"Now connected to: {new_connection or 'None'}")

if "Galaxy" in new_connection:
    print("\n✓✓✓ Successfully connected to hotspot!")
    
    # Get new IP
    stdin, stdout, stderr = ssh.exec_command("hostname -I")
    ip = stdout.read().decode().strip().split()[0]
    print(f"\nNew IP address: {ip}")
    print(f"Webapp accessible at: http://{ip}:5000")
else:
    print(f"\n✗ Still connected to {new_connection}")
    print("\nTrying disconnect and reconnect...")
    stdin, stdout, stderr = ssh.exec_command("sudo wpa_cli -i wlan0 disconnect && sleep 2 && sudo wpa_cli -i wlan0 reconnect")
    stdout.read()
    
    time.sleep(5)
    stdin, stdout, stderr = ssh.exec_command("iwgetid -r")
    final = stdout.read().decode().strip()
    print(f"Final connection: {final}")

ssh.close()
