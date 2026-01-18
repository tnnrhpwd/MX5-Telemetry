#!/usr/bin/env python3
"""Deploy webapp static files to Pi"""
import paramiko
import os

PI_IP = "192.168.1.23"
PI_USER = "pi"
PI_PASSWORD = "Hopwood12"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_IP, username=PI_USER, password=PI_PASSWORD, timeout=10)

# Create static directory
print("Creating static directory on Pi...")
stdin, stdout, stderr = ssh.exec_command("mkdir -p /home/pi/MX5-Telemetry/pi/ui/static")
stdout.read()
print("✓ Directory created")

# Upload app.js
print("\nUploading app.js...")
local_js = r"c:\Users\tanne\Documents\Github\MX5-Telemetry\pi\ui\static\app.js"
with open(local_js, 'r', encoding='utf-8') as f:
    js_content = f.read()

sftp = ssh.open_sftp()
with sftp.open('/home/pi/MX5-Telemetry/pi/ui/static/app.js', 'w') as f:
    f.write(js_content)
print("✓ app.js uploaded")

# Upload style.css
print("\nUploading style.css...")
local_css = r"c:\Users\tanne\Documents\Github\MX5-Telemetry\pi\ui\static\style.css"
with open(local_css, 'r', encoding='utf-8') as f:
    css_content = f.read()

with sftp.open('/home/pi/MX5-Telemetry/pi/ui/static/style.css', 'w') as f:
    f.write(css_content)
print("✓ style.css uploaded")

sftp.close()

# Verify
print("\nVerifying static files...")
stdin, stdout, stderr = ssh.exec_command("ls -lh /home/pi/MX5-Telemetry/pi/ui/static/")
result = stdout.read().decode()
print(result)

print("\n✓✓✓ Webapp static files deployed!")
print("\nRefresh the webpage in your browser and try the buttons again.")

ssh.close()
