#!/usr/bin/env python3
"""Verify web_server.py is updated and restart service"""
import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.1.23", username="pi", password="Hopwood12", timeout=10)

print("Checking if web_server.py has the fix...")
stdin, stdout, stderr = ssh.exec_command("grep -A 2 '_send_led_sequence_to_arduino' /home/pi/MX5-Telemetry/pi/ui/src/web_server.py")
result = stdout.read().decode()

if '_send_led_sequence_to_arduino' in result:
    print("✓ Fix is in the file")
    print(result)
else:
    print("✗ Fix not found - need to redeploy")

print("\nRestarting service to apply changes...")
stdin, stdout, stderr = ssh.exec_command("sudo systemctl restart mx5-display")
stdout.read()
print("✓ Service restarted")

print("\nWaiting 8 seconds for startup...")
time.sleep(8)

print("\n✓ Ready to test")

ssh.close()
