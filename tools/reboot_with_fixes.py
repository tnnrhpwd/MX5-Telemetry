#!/usr/bin/env python3
"""Auto-reboot after fixes"""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.1.28', username='pi', password='Hopwood12', timeout=10)
print("Rebooting Pi with HDMI fixes...")
ssh.exec_command('sudo reboot')
ssh.close()
print("✓ Reboot initiated!")
print("\nWatch the Pioneer screen during boot:")
print("  1. Boot text appears (you already see this)")
print("  2. Signal should now STAY ACTIVE through boot")
print("  3. Desktop/VNC content should appear and persist")
print("\nWait 60 seconds for full boot...")
