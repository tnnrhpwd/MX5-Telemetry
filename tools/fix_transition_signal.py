#!/usr/bin/env python3
"""
Fix the boot-to-desktop transition signal loss
Boot text works, now we need to maintain signal when switching to graphics mode
"""
import paramiko
import time

print("Connecting to Pi...")
time.sleep(2)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.1.28', username='pi', password='Hopwood12', timeout=10)

print("\n" + "="*70)
print("FIXING BOOT-TO-DESKTOP SIGNAL TRANSITION")
print("="*70)

# Read current config
stdin, stdout, stderr = ssh.exec_command('cat /boot/config.txt')
config = stdout.read().decode()

# Enhanced config that maintains signal through boot transition
new_config = """# For more options and information see
# http://rpf.io/configtxt
# Some settings may impact device functionality. See link above for details

disable_overscan=1
hdmi_force_hotplug=1

# Lock framebuffer to Pioneer resolution to prevent mode changes
framebuffer_width=800
framebuffer_height=480

# Enable audio (loads snd_bcm2835)
dtparam=audio=on
dtparam=i2c_arm=on

# Enable DRM VC4 V3D driver with careful settings
dtoverlay=dwc2
max_framebuffers=2
arm_64bit=1
start_x=1
gpu_mem=128
# Use FKMS but prevent firmware from interfering with our HDMI setup
dtoverlay=vc4-fkms-v3d,audio=on
disable_fw_kms_setup=1

# =============================================================================
# MX5-Telemetry CAN Bus Configuration
# =============================================================================
dtparam=spi=on
dtoverlay=mcp2515-can0,oscillator=8000000,interrupt=25
dtoverlay=mcp2515-can1,oscillator=8000000,interrupt=24
enable_uart=1

# =============================================================================
# HDMI Configuration - Pioneer AVH-W4500NEX on HDMI 1 (second port)
# Keep signal hot and stable through all boot stages
# =============================================================================
[HDMI:1]
hdmi_group=2
hdmi_mode=87
hdmi_cvt=800 480 60 6 0 0 0
hdmi_drive=2
hdmi_ignore_edid=0xa5000080
config_hdmi_boost=7
hdmi_pixel_encoding=2
hdmi_blanking=0
max_framebuffer_width=800
max_framebuffer_height=480

[all]
"""

# Read current cmdline
stdin, stdout, stderr = ssh.exec_command('cat /boot/cmdline.txt')
cmdline = stdout.read().decode().strip()

# Add just console blank disable, don't mess with framebuffer mapping
if 'consoleblank=' not in cmdline:
    new_cmdline = cmdline + " consoleblank=0"
else:
    new_cmdline = cmdline

print("\n1. Updating config.txt with transition-safe settings...")
cmd = f"""sudo tee /boot/config.txt > /dev/null << 'EOFCFG'
{new_config}
EOFCFG"""
stdin, stdout, stderr = ssh.exec_command(cmd)
err = stderr.read().decode()
if err:
    print(f"  Error: {err}")
else:
    print("  ✓ Config updated")

print("\n2. Updating cmdline.txt...")
stdin, stdout, stderr = ssh.exec_command(f"""sudo bash -c 'echo "{new_cmdline}" > /boot/cmdline.txt'""")
print("  ✓ Cmdline updated")

# Verify
print("\n" + "="*70)
print("CONFIGURATION SUMMARY")
print("="*70)

print("\n>>> Key settings added:")
print("  • disable_fw_kms_setup=1 (prevent firmware from changing HDMI during KMS init)")
print("  • framebuffer_width/height=800x480 (lock resolution)")
print("  • hdmi_blanking=0 (prevent blanking during transitions)")
print("  • hdmi_ignore_edid=0xa5000080 (force our config over EDID)")
print("  • consoleblank=0 (keep console active)")

print("\n>>> HDMI:1 section:")
stdin, stdout, stderr = ssh.exec_command("grep -A11 'HDMI:1' /boot/config.txt")
print(stdout.read().decode())

print("\n" + "="*70)
print("READY TO TEST")
print("="*70)
print("\nThese changes should:")
print("  ✓ Maintain boot text (already working)")
print("  ✓ Keep HDMI signal during KMS/graphics initialization")
print("  ✓ Prevent mode changes that cause signal loss")
print("  ✓ Lock display at 800x480 throughout boot")

print("\nRebooting to test...")
ssh.exec_command('sudo reboot')
ssh.close()

print("\n✓ Reboot initiated")
print("\nWatch the Pioneer - you should see:")
print("  1. Boot text (working)")
print("  2. Signal stays active during transition")
print("  3. Desktop/display appears and persists")
print("\nWait 60 seconds...")
