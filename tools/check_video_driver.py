#!/usr/bin/env python3
"""Check which video driver and output the Pi is using"""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.1.28', username='pi', password='Hopwood12', timeout=10)

commands = [
    # Check the full DRM card info
    'ls -la /sys/class/drm/',
    
    # Check what driver is being used
    'cat /boot/config.txt | grep -i dtoverlay | grep vc4',
    
    # Check KMS mode
    'cat /boot/config.txt | grep -i "fkms\\|kms"',
    
    # Check all video-related config
    'grep -E "^dtoverlay|^gpu_|^hdmi_|^video|^display" /boot/config.txt | head -20',
    
    # Check connected displays
    'ls /sys/class/drm/*/status 2>/dev/null | while read f; do echo "$f: $(cat $f)"; done',
    
    # Check modetest if available
    'modetest -M vc4 -c 2>/dev/null | head -40 || echo "modetest not available"',
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
