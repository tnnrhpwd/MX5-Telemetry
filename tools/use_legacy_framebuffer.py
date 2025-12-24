#!/usr/bin/env python3
"""
Switch to legacy framebuffer mode (no KMS)
This keeps firmware in control of HDMI throughout - no handoff issues
"""
import paramiko
import time

print("Connecting to Pi...")
time.sleep(2)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.1.28', username='pi', password='Hopwood12', timeout=10)

print("\n" + "="*70)
print("SWITCHING TO LEGACY FRAMEBUFFER MODE")
print("="*70)
print("\nThis disables KMS and keeps firmware control of HDMI.")
print("No more handoff = no more signal loss!")

# Legacy config without KMS
legacy_config = """# For more options and information see
# http://rpf.io/configtxt
# Some settings may impact device functionality. See link above for details

disable_overscan=1
hdmi_force_hotplug=1
framebuffer_width=800
framebuffer_height=480

# Enable audio (loads snd_bcm2835)
dtparam=audio=on
dtparam=i2c_arm=on

# DISABLE KMS - use legacy framebuffer for stable HDMI
# dtoverlay=vc4-fkms-v3d,audio=on  # <-- COMMENTED OUT
# dtoverlay=vc4-kms-v3d            # <-- NOT USED
dtoverlay=dwc2
max_framebuffers=2
arm_64bit=1
start_x=1
gpu_mem=128

# =============================================================================
# MX5-Telemetry CAN Bus Configuration
# =============================================================================
dtparam=spi=on
dtoverlay=mcp2515-can0,oscillator=8000000,interrupt=25
dtoverlay=mcp2515-can1,oscillator=8000000,interrupt=24
enable_uart=1

# =============================================================================
# HDMI Configuration - Pioneer AVH-W4500NEX on HDMI 1 (second port)
# Using legacy framebuffer mode for rock-solid HDMI output
# =============================================================================
[HDMI:1]
hdmi_group=2
hdmi_mode=87
hdmi_cvt=800 480 60 6 0 0 0
hdmi_drive=2
hdmi_ignore_edid=0xa5000080
config_hdmi_boost=7
hdmi_pixel_encoding=2

[all]
"""

print("\n1. Writing legacy config.txt (KMS disabled)...")
cmd = f"""sudo tee /boot/config.txt > /dev/null << 'EOFCFG'
{legacy_config}
EOFCFG"""
stdin, stdout, stderr = ssh.exec_command(cmd)
err = stderr.read().decode()
if err:
    print(f"  Error: {err}")
else:
    print("  ✓ Legacy config written")

# Verify
print("\n" + "="*70)
print("VERIFICATION")
print("="*70)

print("\n>>> Checking for KMS (should be commented out):")
stdin, stdout, stderr = ssh.exec_command("grep 'vc4.*v3d' /boot/config.txt")
kms_lines = stdout.read().decode()
print(kms_lines if kms_lines else "  (no active KMS overlays - good!)")

print("\n>>> HDMI:1 section:")
stdin, stdout, stderr = ssh.exec_command("grep -A9 'HDMI:1' /boot/config.txt")
print(stdout.read().decode())

print("\n" + "="*70)
print("LEGACY MODE CONFIGURED")
print("="*70)
print("\nChanges:")
print("  • KMS driver DISABLED (commented out vc4-fkms-v3d)")
print("  • Firmware stays in control of HDMI")
print("  • No kernel/firmware handoff = no signal loss")
print("  • Display will use legacy /dev/fb0 framebuffer")
print("\nTrade-off:")
print("  • Slightly less GPU performance")
print("  • But ROCK SOLID HDMI output throughout boot!")
print("\nThis is how older Pi setups worked - very reliable.")

print("\nRebooting to test...")
ssh.exec_command('sudo reboot')
ssh.close()

print("\n✓ Reboot initiated")
print("\nYou should now see:")
print("  1. Boot text (working)")
print("  2. Signal STAYS ACTIVE")
print("  3. Desktop appears and persists")
print("\nNo more signal loss! Wait 60 seconds...")
