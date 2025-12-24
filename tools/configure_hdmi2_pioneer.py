#!/usr/bin/env python3
"""
Configure HDMI 2 (second port, farthest from USB-C) for Pioneer AVH-W4500NEX
This is HDMI:1 in config.txt terms (ports are zero-indexed)

The Pioneer AVH-W4500NEX has native resolution of 800x480
"""
import paramiko
import re

# SSH connection
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print("Connecting to Pi...")
ssh.connect('192.168.1.28', username='pi', password='Hopwood12', timeout=10)

# Step 1: Read current config
print("\n=== Reading current config ===")
stdin, stdout, stderr = ssh.exec_command('cat /boot/config.txt')
config = stdout.read().decode()

# Check if HDMI:1 section already exists
has_hdmi1_section = '[HDMI:1]' in config

print(f"Has [HDMI:1] section: {has_hdmi1_section}")

# Step 2: Create the new configuration section for HDMI:1 (second port)
# This configures the physical HDMI 2 port (farthest from USB-C)
new_hdmi1_section = """
# =============================================================================
# HDMI:1 Configuration for Pioneer AVH-W4500NEX on second port (farthest from USB-C)
# Native resolution: 800x480
# =============================================================================
[HDMI:1]
hdmi_force_hotplug=1
hdmi_ignore_edid=0xa5000080
hdmi_group=2
hdmi_mode=87
hdmi_cvt=800 480 60 6 0 0 0
hdmi_drive=2
config_hdmi_boost=7
hdmi_pixel_encoding=2
disable_overscan=1

[all]
"""

# Step 3: Update config
if has_hdmi1_section:
    # Replace existing section
    print("\n=== Replacing existing [HDMI:1] section ===")
    # Find and replace the HDMI:1 section up to the next [all] tag
    new_config = re.sub(
        r'\[HDMI:1\].*?(?=\[all\])',
        new_hdmi1_section.strip() + '\n\n',
        config,
        flags=re.DOTALL
    )
else:
    # Add new section at the end before the last line
    print("\n=== Adding new [HDMI:1] section ===")
    new_config = config.rstrip() + '\n' + new_hdmi1_section

# Step 4: Write updated config
print("\n=== Writing new config ===")
cmd = f'''sudo tee /boot/config.txt > /dev/null << 'EOF'
{new_config}
EOF'''

stdin, stdout, stderr = ssh.exec_command(cmd)
err = stderr.read().decode()
if err:
    print(f"Error writing config: {err}")
else:
    print("✓ Config written successfully")

# Step 5: Verify the changes
print("\n=== Verifying HDMI:1 section ===")
stdin, stdout, stderr = ssh.exec_command('grep -A12 "HDMI:1" /boot/config.txt')
print(stdout.read().decode())

# Step 6: Show reboot instructions
print("\n" + "=" * 70)
print("Configuration updated successfully!")
print("=" * 70)
print("\nNext steps:")
print("1. Reboot the Pi for changes to take effect:")
print("   ssh pi@192.168.1.28")
print("   sudo reboot")
print("\n2. After reboot, verify HDMI output with:")
print("   tvservice -l")
print("   tvservice -s -v 7")
print("\n3. The second HDMI port (farthest from USB-C) should now output")
print("   800x480 video to the Pioneer head unit.")
print("\nNote: HDMI:1 in config = second physical port (away from USB-C)")
print("      HDMI:0 in config = first physical port (near USB-C)")

# Prompt for reboot
print("\n" + "=" * 70)
response = input("Would you like to reboot the Pi now? (y/n): ").strip().lower()
if response == 'y':
    print("\nRebooting Pi...")
    stdin, stdout, stderr = ssh.exec_command('sudo reboot')
    print("Reboot command sent. The Pi will restart in a few seconds.")
else:
    print("\nRemember to reboot manually for changes to take effect!")

ssh.close()
print("\nDone!")
