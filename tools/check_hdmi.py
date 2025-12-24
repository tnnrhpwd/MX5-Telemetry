#!/usr/bin/env python3
"""Check HDMI status on Pi"""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.1.28', username='pi', password='Hopwood12', timeout=10)

commands = [
    'tvservice -l',
    'tvservice -s -v 7',
    'tvservice -s -v 2', 
    'vcgencmd display_power -1',
    'grep -A10 "HDMI:1" /boot/config.txt',
    'cat /boot/config.txt | grep -E "hdmi|HDMI" | head -30',
    'DISPLAY=:0 xrandr 2>/dev/null || echo "xrandr needs display"',
]

for cmd in commands:
    print(f'\n>>> {cmd}')
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out:
        print(out)
    if err:
        print(f'STDERR: {err}')

ssh.close()
print("\nDone!")
