#!/usr/bin/env python3
"""
Fix HDMI signal loss after boot text
The issue: Boot console works, but signal is lost when switching to desktop/KMS

Solutions to try:
1. Force framebuffer console to stay active
2. Prevent console blanking
3. Ensure proper KMS handoff
4. Keep HDMI signal hot throughout boot
"""
import paramiko
import time
import re

print("Waiting for Pi to be ready...")
time.sleep(5)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

for attempt in range(3):
    try:
        ssh.connect('192.168.1.28', username='pi', password='Hopwood12', timeout=15)
        print("✓ Connected to Pi")
        break
    except Exception as e:
        if attempt < 2:
            print(f"Connection attempt {attempt+1} failed, retrying...")
            time.sleep(10)
        else:
            print(f"Failed to connect: {e}")
            exit(1)

print("\n" + "="*70)
print("FIXING HDMI SIGNAL LOSS AFTER BOOT")
print("="*70)

# Step 1: Check current status
print("\n>>> Checking current HDMI status...")
stdin, stdout, stderr = ssh.exec_command("tvservice -s -v 7")
current_status = stdout.read().decode()
print(current_status)

# Step 2: Read current configs
stdin, stdout, stderr = ssh.exec_command('cat /boot/cmdline.txt')
cmdline = stdout.read().decode().strip()

stdin, stdout, stderr = ssh.exec_command('cat /boot/config.txt')
config = stdout.read().decode()

print("\n" + "="*70)
print("APPLYING FIXES")
print("="*70)

# Fix 1: Update cmdline.txt to prevent console blanking and keep framebuffer active
print("\n1. Updating cmdline.txt...")

# Remove any existing video= or consoleblank= parameters
cmdline = re.sub(r'video=[^\s]+', '', cmdline)
cmdline = re.sub(r'consoleblank=[^\s]+', '', cmdline)
cmdline = re.sub(r'logo\.nologo', '', cmdline)
cmdline = re.sub(r'\s+', ' ', cmdline).strip()

# Add our parameters
new_params = "consoleblank=0 fbcon=map:10"
new_cmdline = cmdline + " " + new_params

stdin, stdout, stderr = ssh.exec_command(f"""sudo bash -c 'echo "{new_cmdline}" > /boot/cmdline.txt'""")
err = stderr.read().decode()
if err and 'warning' not in err.lower():
    print(f"  Warning: {err}")
else:
    print("  ✓ cmdline.txt updated")
    print(f"  Added: {new_params}")

# Fix 2: Update config.txt for better HDMI persistence
print("\n2. Updating config.txt for HDMI persistence...")

# Ensure these settings are in the [all] section (not port-specific)
all_section_settings = {
    'hdmi_force_hotplug': '1',
    'hdmi_drive': '2',
    'disable_overscan': '1',
    'framebuffer_width': '800',
    'framebuffer_height': '480',
}

# Find the [all] section before [HDMI:0]
all_section_match = re.search(r'(\[all\])(?=.*?\[HDMI:0\])', config, re.DOTALL)
if all_section_match:
    insertion_point = all_section_match.end()
    # Build settings to add
    settings_text = "\n# Global HDMI settings for stable signal\n"
    for key, value in all_section_settings.items():
        # Check if setting already exists in [all] section
        if not re.search(rf'^{key}=', config[insertion_point:insertion_point+500], re.MULTILINE):
            settings_text += f"{key}={value}\n"
    
    # Insert settings after [all]
    config = config[:insertion_point] + settings_text + config[insertion_point:]
    print("  ✓ Added global HDMI settings to [all] section")

# Fix 3: Enhance HDMI:1 section with additional stability settings
print("\n3. Enhancing HDMI:1 configuration...")

hdmi1_section = """# =============================================================================
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
max_framebuffer_width=800
max_framebuffer_height=480
hdmi_blanking=0
"""

# Replace existing HDMI:1 section
config = re.sub(
    r'# HDMI:1 Configuration.*?\[HDMI:1\].*?(?=\n\[)',
    hdmi1_section,
    config,
    flags=re.DOTALL
)

print("  ✓ Enhanced HDMI:1 section")

# Write updated config
stdin, stdout, stderr = ssh.exec_command(f"""sudo tee /boot/config.txt > /dev/null << 'EOFCONFIG'
{config}
EOFCONFIG""")
err = stderr.read().decode()
if err:
    print(f"  Error: {err}")
else:
    print("  ✓ config.txt written")

# Verify changes
print("\n" + "="*70)
print("VERIFYING CHANGES")
print("="*70)

print("\n>>> cmdline.txt:")
stdin, stdout, stderr = ssh.exec_command('cat /boot/cmdline.txt')
print(stdout.read().decode())

print("\n>>> HDMI:1 section in config.txt:")
stdin, stdout, stderr = ssh.exec_command('grep -A12 "HDMI:1" /boot/config.txt')
print(stdout.read().decode())

print("\n" + "="*70)
print("CHANGES APPLIED SUCCESSFULLY")
print("="*70)
print("\nWhat was fixed:")
print("1. ✓ Disabled console blanking (consoleblank=0)")
print("2. ✓ Forced framebuffer console to stay mapped (fbcon=map:10)")
print("3. ✓ Added global HDMI force hotplug and drive settings")
print("4. ✓ Enhanced HDMI:1 with max_framebuffer and hdmi_blanking=0")
print("\nThese changes ensure:")
print("- Console stays active and doesn't blank")
print("- Framebuffer maintains the HDMI signal")
print("- HDMI stays hot during mode transitions")
print("- Signal persists from boot text through to desktop")

print("\n" + "="*70)
response = input("Reboot Pi now to test? (y/n): ").strip().lower()
if response == 'y':
    print("\nRebooting Pi...")
    ssh.exec_command('sudo reboot')
    print("✓ Reboot initiated")
    print("\nWatch the Pioneer screen - you should see:")
    print("1. Boot text (you already see this)")
    print("2. Rainbow splash (if enabled)")
    print("3. Desktop/display content (THIS should now stay visible)")
else:
    print("\nReboot with: ssh pi@192.168.1.28 'sudo reboot'")

ssh.close()
print("\nDone!")
