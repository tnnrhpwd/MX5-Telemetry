#!/usr/bin/env python3
"""Fix HDMI1 config - try CEA mode instead of DMT"""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.1.28', username='pi', password='Hopwood12', timeout=10)

# Read current config
stdin, stdout, stderr = ssh.exec_command('cat /boot/config.txt')
config = stdout.read().decode()

print("Current HDMI:1 section:")
print("=" * 40)
import re
match = re.search(r'\[HDMI:1\].*?\[all\]', config, re.DOTALL)
if match:
    print(match.group())

# New config - try CEA group with custom resolution
new_hdmi1_section = """[HDMI:1]
hdmi_force_hotplug=1
hdmi_ignore_edid=0xa5000080
hdmi_drive=2
hdmi_group=2
hdmi_mode=87
hdmi_cvt=800 480 60 6 0 0 0
hdmi_pixel_encoding=2

[all]"""

# Replace the section
new_config = re.sub(r'\[HDMI:1\].*?\[all\]', new_hdmi1_section, config, flags=re.DOTALL)

print("\n\nNew HDMI:1 section:")
print("=" * 40)
print(new_hdmi1_section)

# Write it back
cmd = f'''cat << 'EOF' | sudo tee /boot/config.txt > /dev/null
{new_config}
EOF'''

stdin, stdout, stderr = ssh.exec_command(cmd)
err = stderr.read().decode()
if err:
    print(f"Error: {err}")
else:
    print("\n\nConfig updated! Changes:")
    print("- Added hdmi_ignore_edid=0xa5000080 (force config over EDID)")
    print("- Added hdmi_pixel_encoding=2 (full RGB range)")
    print("\nReboot needed to apply.")

ssh.close()
