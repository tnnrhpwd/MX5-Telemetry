#!/usr/bin/env python3
"""Try to fix HDMI1 output without reboot - various methods"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.lib.pi_ssh import connect as pi_connect


import time

ssh = pi_connect(host='192.168.1.23', user='pi', timeout=10)
print("Attempting to fix HDMI1 output without reboot...\n")

# Method 1: Turn HDMI off and back on
print("Method 1: Power cycling HDMI1...")
ssh.exec_command('tvservice -o -v 7')
time.sleep(2)
stdin, stdout, stderr = ssh.exec_command('tvservice -p -v 7')
print(stdout.read().decode())
time.sleep(1)

# Method 2: Force explicit mode
print("\nMethod 2: Force explicit mode on HDMI1...")
stdin, stdout, stderr = ssh.exec_command('tvservice -e "DMT 87" -v 7')
out = stdout.read().decode()
err = stderr.read().decode()
print(f"Out: {out}")
print(f"Err: {err}")

# Method 3: Use fbset to reconfigure framebuffer
print("\nMethod 3: Reconfiguring framebuffer...")
stdin, stdout, stderr = ssh.exec_command('sudo fbset -xres 800 -yres 480 -depth 32')
print(stdout.read().decode())

# Check current status
print("\nCurrent HDMI1 status:")
stdin, stdout, stderr = ssh.exec_command('tvservice -s -v 7')
print(stdout.read().decode())

# Check xrandr
print("\nxrandr status:")
stdin, stdout, stderr = ssh.exec_command('DISPLAY=:0 xrandr')
print(stdout.read().decode())

ssh.close()
print("\nDone! Check if Pioneer now shows the display.")
