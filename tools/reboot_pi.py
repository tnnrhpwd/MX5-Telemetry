#!/usr/bin/env python3
"""Simple reboot script"""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.1.28', username='pi', password='Hopwood12', timeout=10)
print("Rebooting Pi...")
ssh.exec_command('sudo reboot')
ssh.close()
print("Reboot command sent! Wait 60 seconds then check the Pioneer display.")
