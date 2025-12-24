#!/usr/bin/env python3
"""Additional HDMI diagnostics for Pioneer connection"""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.1.28', username='pi', password='Hopwood12', timeout=10)

commands = [
    # Check if HDMI-CEC is causing issues
    'cat /boot/config.txt | grep -i cec',
    
    # Check current video mode details
    'vcgencmd get_config hdmi_group',
    'vcgencmd get_config hdmi_mode',
    
    # Force HDMI hot plug detect on HDMI1
    'tvservice -p -v 7',
    
    # Re-check status after forcing
    'sleep 1 && tvservice -s -v 7',
    
    # Check EDID data from connected display
    'tvservice -d /tmp/edid.dat -v 7 2>&1 && tvservice -d /tmp/edid.dat -v 7 && cat /tmp/edid.dat 2>/dev/null | xxd | head -5 || echo "No EDID"',
    
    # Check kernel messages for HDMI
    'dmesg | grep -i hdmi | tail -10',
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
