#!/usr/bin/env python3
"""Check logs after restart"""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.1.23", username="pi", password="Hopwood12", timeout=10)

stdin, stdout, stderr = ssh.exec_command("journalctl -u mx5-display.service --since '20 seconds ago' --no-pager | tail -30")
print(stdout.read().decode())

ssh.close()
