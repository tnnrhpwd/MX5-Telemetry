#!/usr/bin/env python3
"""Check PlatformIO installation on Pi"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.lib.pi_ssh import connect as pi_connect


PI_HOST = "192.168.1.23"
PI_USER = "pi"

ssh = pi_connect(host=PI_HOST, user=PI_USER)
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
