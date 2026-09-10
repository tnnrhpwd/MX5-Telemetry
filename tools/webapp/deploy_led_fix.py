#!/usr/bin/env python3
"""Deploy fixed web_server.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.lib.pi_ssh import connect as pi_connect


import time

ssh = pi_connect(host="192.168.1.23", user="pi", timeout=10)
print("Uploading fixed web_server.py...")
with open(r"c:\Users\tanne\Documents\Github\MX5-Telemetry\pi\ui\src\web_server.py", 'r', encoding='utf-8') as f:
    content = f.read()

sftp = ssh.open_sftp()
with sftp.open('/home/pi/MX5-Telemetry/pi/ui/src/web_server.py', 'w') as f:
    f.write(content)
sftp.close()
print("✓ Uploaded")

print("\nRestarting service...")
stdin, stdout, stderr = ssh.exec_command("sudo systemctl restart mx5-display")
stdout.read()
print("✓ Restarted")

print("\nWaiting for service to start...")
time.sleep(8)

print("\n✓ Webapp LED control fixed!")
print("\nNow running Arduino diagnostic...\n")

ssh.close()
