#!/usr/bin/env python3
"""Debug why HDMI1 isn't showing on Pioneer"""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.1.28', username='pi', password='Hopwood12', timeout=10)

commands = [
    # Check cmdline.txt for video settings
    'cat /boot/cmdline.txt',
    
    # Check if there's a display manager config issue
    'ls -la /etc/X11/xorg.conf.d/ 2>/dev/null || echo "No xorg.conf.d"',
    
    # Check lightdm config
    'grep -r "HDMI" /etc/lightdm/ 2>/dev/null || echo "No HDMI in lightdm"',
    
    # Check if both HDMI ports show in drm
    'ls -la /sys/class/drm/ | grep HDMI',
    
    # Check status of both possible HDMI connectors
    'cat /sys/class/drm/card1-HDMI-A-1/status 2>/dev/null || echo "No card1-HDMI-A-1"',
    'cat /sys/class/drm/card1-HDMI-A-2/status 2>/dev/null || echo "No card1-HDMI-A-2"',
    
    # Check video=HDMI parameter in kernel
    'cat /proc/cmdline | grep -o "video=[^ ]*"',
    
    # Try getting detailed connector info
    'cat /sys/class/drm/card1-HDMI-A-1/modes 2>/dev/null | head -5',
]

for cmd in commands:
    print(f'\n>>> {cmd}')
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out:
        print(out)
    if err and 'No such file' not in err:
        print(f'STDERR: {err}')

ssh.close()
print("\nDone!")
