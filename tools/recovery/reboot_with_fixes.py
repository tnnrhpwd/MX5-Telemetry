#!/usr/bin/env python3
"""Auto-reboot after fixes"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.lib.pi_ssh import connect as pi_connect


ssh = pi_connect(host='192.168.1.23', user='pi', timeout=10)
print("Rebooting Pi with HDMI fixes...")
ssh.exec_command('sudo reboot')
ssh.close()
print("✓ Reboot initiated!")
print("\nWatch the Pioneer screen during boot:")
print("  1. Boot text appears (you already see this)")
print("  2. Signal should now STAY ACTIVE through boot")
print("  3. Desktop/VNC content should appear and persist")
print("\nWait 60 seconds for full boot...")
