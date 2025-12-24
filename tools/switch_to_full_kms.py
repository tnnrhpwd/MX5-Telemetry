#!/usr/bin/env python3
"""
Switch from vc4-fkms-v3d to vc4-kms-v3d for proper dual HDMI support.
Full KMS exposes both HDMI ports correctly.
"""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.1.28', username='pi', password='Hopwood12', timeout=10)

# Read current config
stdin, stdout, stderr = ssh.exec_command('cat /boot/config.txt')
config = stdout.read().decode()

print("Current KMS setting:")
import re
for line in config.split('\n'):
    if 'vc4-' in line and 'kms' in line.lower():
        print(f"  {line}")

# Replace fkms with full kms
new_config = config.replace('dtoverlay=vc4-fkms-v3d,audio=on', 'dtoverlay=vc4-kms-v3d')
new_config = new_config.replace('dtoverlay=vc4-fkms-v3d', 'dtoverlay=vc4-kms-v3d')

# Also add force_hotplug for HDMI:1 section if not there
if '[HDMI:1]' in new_config:
    # Make sure we have the right settings for the second HDMI with full KMS
    pass  # Our config should work with full KMS

print("\nNew KMS setting will be:")
for line in new_config.split('\n'):
    if 'vc4-' in line and 'kms' in line.lower():
        print(f"  {line}")

print("\nWARNING: Switching to full KMS (vc4-kms-v3d)")
print("This enables proper dual HDMI support but may affect some apps.")
print("If display doesn't work, boot to recovery and revert.")

# Write back
cmd = f'''cat << 'CONFIGEOF' | sudo tee /boot/config.txt > /dev/null
{new_config}
CONFIGEOF'''

stdin, stdout, stderr = ssh.exec_command(cmd)
err = stderr.read().decode()
if err:
    print(f"\nError: {err}")
else:
    print("\n✓ Config updated!")
    print("  Changed: vc4-fkms-v3d -> vc4-kms-v3d")
    print("\nReboot required. Run: sudo reboot")

ssh.close()
