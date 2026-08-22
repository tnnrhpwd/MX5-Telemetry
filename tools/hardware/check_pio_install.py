#!/usr/bin/env python3
"""Check PlatformIO installation on Pi"""
import paramiko

PI_HOST = "192.168.1.23"
PI_USER = "pi"
PI_PASSWORD = "Mototunertanner"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_HOST, username=PI_USER, password=PI_PASSWORD)

commands = [
    "which pio",
    "which platformio", 
    "ls -la ~/.platformio/",
    "find ~ -name 'pio' 2>/dev/null | head -5",
    "pio --version 2>&1 || platformio --version 2>&1"
]

for cmd in commands:
    print(f"\n$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode('utf-8')
    err = stderr.read().decode('utf-8')
    print(out if out else err)

ssh.close()
