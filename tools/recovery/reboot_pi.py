#!/usr/bin/env python3
"""Simple reboot script"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.lib.pi_ssh import connect as pi_connect


ssh = pi_connect(host='192.168.1.23', user='pi', timeout=10)
print("Rebooting Pi...")
ssh.exec_command('sudo reboot')
ssh.close()
print("Reboot command sent! Wait 60 seconds then check the Pioneer display.")
