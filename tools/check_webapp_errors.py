#!/usr/bin/env python3
"""Check webapp error logs"""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.1.23", username="pi", password="Hopwood12", timeout=10)

print("=" * 70)
print("WEBAPP ERROR LOGS")
print("=" * 70)

stdin, stdout, stderr = ssh.exec_command("journalctl -u mx5-display.service --since '10 minutes ago' --no-pager | grep -A 5 -B 5 -E 'flask|socketio|Traceback|Error|web_server' | tail -50")
logs = stdout.read().decode()
print(logs)

ssh.close()
