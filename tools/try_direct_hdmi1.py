#!/usr/bin/env python3
"""
Try simpler fix - add video parameter to cmdline.txt for HDMI second port
With FKMS, the second HDMI may need explicit kernel parameter
"""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.1.28', username='pi', password='Hopwood12', timeout=10)

# Check current cmdline
stdin, stdout, stderr = ssh.exec_command('cat /boot/cmdline.txt')
cmdline = stdout.read().decode().strip()

print("Current cmdline.txt:")
print(cmdline)

# Check if video= parameter exists
if 'video=' in cmdline:
    print("\n\nNote: video= parameter already exists in cmdline")
    # The current kernel has: video=HDMI-A-1:800x480M@59
    # This should be coming from config.txt, not cmdline.txt
    
# Actually let's check if we need to use the OLD firmware approach
# instead of KMS for the second HDMI port

print("\n\nLet me check the tvservice mappings...")
stdin, stdout, stderr = ssh.exec_command('tvservice -l')
print(stdout.read().decode())

# Display 7 = HDMI1 in firmware terms
# Let's try setting the mode directly and then powering on
print("\nTrying direct mode set on HDMI1 (display ID 7)...")
commands = [
    'tvservice -o -v 7',  # off
    'sleep 1',
    'tvservice -e "DMT 87 HDMI" -v 7',  # explicit mode with HDMI (not DVI)
    'sleep 2',
    'tvservice -s -v 7',  # status
    'fbset -fb /dev/fb0',  # check framebuffer
]

for cmd in commands:
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out:
        print(out)
    if err:
        print(f"ERR: {err}")

ssh.close()
print("\nDone - check Pioneer display!")
