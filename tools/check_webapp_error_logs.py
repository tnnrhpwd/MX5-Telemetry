#!/usr/bin/env python3
"""Check webapp errors"""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.1.23", username="pi", password="Hopwood12", timeout=10)

print("Checking webapp errors from last minute...")
stdin, stdout, stderr = ssh.exec_command("journalctl -u mx5-display.service --since '1 minute ago' --no-pager | grep -A 10 -E 'Error|Traceback|Exception'")
print(stdout.read().decode())

ssh.close()
