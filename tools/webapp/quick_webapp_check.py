#!/usr/bin/env python3
"""Quick webapp check"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.lib.pi_ssh import connect as pi_connect


ssh = pi_connect(host="192.168.1.23", user="pi", timeout=10)
stdin, stdout, stderr = ssh.exec_command("ss -tlnp 2>/dev/null | grep :5000")
port_check = stdout.read().decode()

stdin, stdout, stderr = ssh.exec_command("pip3 list 2>/dev/null | grep flask-socketio")
flask_check = stdout.read().decode()

print("Port 5000 status:")
print(port_check if port_check.strip() else "NOT listening")

print("\nFlask-socketio installed:")
print(flask_check if flask_check.strip() else "NOT installed")

if port_check.strip():
    print("\n✓ Webapp IS running at http://192.168.1.23:5000")
else:
    print("\n✗ Webapp is NOT running")
    if not flask_check.strip():
        print("   Reason: flask-socketio not installed")

ssh.close()
