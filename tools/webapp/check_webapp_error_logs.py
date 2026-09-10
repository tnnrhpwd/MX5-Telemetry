#!/usr/bin/env python3
"""Check webapp errors"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.lib.pi_ssh import connect as pi_connect


ssh = pi_connect(host="192.168.1.23", user="pi", timeout=10)
print("Checking webapp errors from last minute...")
stdin, stdout, stderr = ssh.exec_command("journalctl -u mx5-display.service --since '1 minute ago' --no-pager | grep -A 10 -E 'Error|Traceback|Exception'")
print(stdout.read().decode())

ssh.close()
