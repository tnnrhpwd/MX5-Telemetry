#!/usr/bin/env python3
"""Check webapp error logs"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.lib.pi_ssh import connect as pi_connect


ssh = pi_connect(host="192.168.1.23", user="pi", timeout=10)
print("=" * 70)
print("WEBAPP ERROR LOGS")
print("=" * 70)

stdin, stdout, stderr = ssh.exec_command("journalctl -u mx5-display.service --since '10 minutes ago' --no-pager | grep -A 5 -B 5 -E 'flask|socketio|Traceback|Error|web_server' | tail -50")
logs = stdout.read().decode()
print(logs)

ssh.close()
