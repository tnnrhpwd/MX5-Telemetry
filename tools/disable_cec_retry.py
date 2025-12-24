#!/usr/bin/env python3
"""Disable CEC and try HDMI again - CEC can cause handshake issues"""
import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.1.28', username='pi', password='Hopwood12', timeout=10)

# Check if CEC is even enabled
stdin, stdout, stderr = ssh.exec_command('grep -i cec /boot/config.txt')
cec_config = stdout.read().decode()
print(f"CEC in config: {cec_config if cec_config else 'Not mentioned'}")

# Add CEC disable if not present
stdin, stdout, stderr = ssh.exec_command('cat /boot/config.txt')
config = stdout.read().decode()

if 'hdmi_ignore_cec_init=1' not in config:
    # Add CEC disable before [all] section
    new_config = config.replace('[HDMI:1]', 'hdmi_ignore_cec_init=1\nhdmi_ignore_cec=1\n\n[HDMI:1]')
    
    cmd = f'''cat << 'CONFIGEOF' | sudo tee /boot/config.txt > /dev/null
{new_config}
CONFIGEOF'''
    stdin, stdout, stderr = ssh.exec_command(cmd)
    print("Added CEC disable options to config.txt")
    print("This will take effect after reboot.")
else:
    print("CEC already disabled in config")

# For now, try cycling HDMI again with explicit audio setting
print("\nPower cycling HDMI1 with audio enabled...")
commands = [
    'tvservice -o -v 7',
    'sleep 2',
    'tvservice -e "DMT 87 HDMI" -v 7',  # HDMI mode ensures audio path
    'sleep 1',
    'vcgencmd display_power 1 7',  # Ensure display power is on
]

for cmd in commands:
    stdin, stdout, stderr = ssh.exec_command(cmd)
    time.sleep(0.5)

# Final status
stdin, stdout, stderr = ssh.exec_command('tvservice -s -v 7')
print(f"\nFinal HDMI1 status: {stdout.read().decode()}")

ssh.close()
print("\nCheck Pioneer now!")
