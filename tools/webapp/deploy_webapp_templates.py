#!/usr/bin/env python3
"""Deploy webapp templates to Pi"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.lib.pi_ssh import connect as pi_connect


import os

PI_IP = "192.168.1.23"
PI_USER = "pi"

ssh = pi_connect(host=PI_IP, user=PI_USER, timeout=10)
# Create templates directory
print("Creating templates directory on Pi...")
stdin, stdout, stderr = ssh.exec_command("mkdir -p /home/pi/MX5-Telemetry/pi/ui/templates")
stdout.read()
print("✓ Directory created")

# Upload index.html
print("\nUploading index.html...")
local_template = r"c:\Users\tanne\Documents\Github\MX5-Telemetry\pi\ui\templates\index.html"
with open(local_template, 'r', encoding='utf-8') as f:
    template_content = f.read()

sftp = ssh.open_sftp()
with sftp.open('/home/pi/MX5-Telemetry/pi/ui/templates/index.html', 'w') as f:
    f.write(template_content)
sftp.close()
print("✓ index.html uploaded")

# Verify
print("\nVerifying template exists on Pi...")
stdin, stdout, stderr = ssh.exec_command("ls -lh /home/pi/MX5-Telemetry/pi/ui/templates/")
result = stdout.read().decode()
print(result)

print("\n✓✓✓ Webapp templates deployed!")
print("\nTesting webapp now...")
stdin, stdout, stderr = ssh.exec_command("curl -s -o /dev/null -w '%{http_code}' http://localhost:5000")
status = stdout.read().decode().strip()
print(f"HTTP Status: {status}")

if status == "200":
    print("✓ Webapp is now working!")
else:
    print("✗ Still getting errors")

ssh.close()
