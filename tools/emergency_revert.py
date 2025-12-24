#!/usr/bin/env python3
"""
Emergency revert - boot text disappeared, need to fix quickly
Let's revert to a simpler working config
"""
import paramiko
import time

print("Waiting for Pi to be accessible...")
time.sleep(5)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

for attempt in range(5):
    try:
        ssh.connect('192.168.1.28', username='pi', password='Hopwood12', timeout=10)
        print("✓ Connected to Pi")
        break
    except Exception as e:
        if attempt < 4:
            print(f"Attempt {attempt+1} failed, waiting...")
            time.sleep(5)
        else:
            print(f"Cannot connect: {e}")
            print("Pi might need manual intervention via VNC")
            exit(1)

print("\n" + "="*70)
print("EMERGENCY REVERT TO WORKING CONFIGURATION")
print("="*70)

# Simple working config for HDMI 1 (second port)
# Remove the HDMI:0 disable section and use minimal settings
new_config = """# For more options and information see
# http://rpf.io/configtxt
# Some settings may impact device functionality. See link above for details

disable_overscan=1
hdmi_force_hotplug=1

# Enable audio (loads snd_bcm2835)
dtparam=audio=on
dtparam=i2c_arm=on

# Enable DRM VC4 V3D driver
dtoverlay=dwc2
max_framebuffers=2
arm_64bit=1
start_x=1
gpu_mem=128
dtoverlay=vc4-fkms-v3d,audio=on

# =============================================================================
# MX5-Telemetry CAN Bus Configuration
# =============================================================================
dtparam=spi=on
dtoverlay=mcp2515-can0,oscillator=8000000,interrupt=25
dtoverlay=mcp2515-can1,oscillator=8000000,interrupt=24
enable_uart=1

# =============================================================================
# HDMI Configuration - Pioneer AVH-W4500NEX on HDMI 1 (second port)
# =============================================================================
[HDMI:1]
hdmi_group=2
hdmi_mode=87
hdmi_cvt=800 480 60 6 0 0 0
hdmi_drive=2
config_hdmi_boost=7
hdmi_pixel_encoding=2

[all]
"""

# Simple cmdline without framebuffer overrides
simple_cmdline = "console=serial0,115200 console=tty1 root=PARTUUID=eee3aba0-02 rootfstype=ext4 elevator=deadline fsck.repair=yes rootwait modules-load=dwc2,g_ether quiet splash usbhid.mousepoll=1"

print("\n1. Reverting to simple config.txt...")
cmd = f"""sudo tee /boot/config.txt > /dev/null << 'EOFCFG'
{new_config}
EOFCFG"""
stdin, stdout, stderr = ssh.exec_command(cmd)
err = stderr.read().decode()
if err:
    print(f"  Error: {err}")
else:
    print("  ✓ Simple config.txt written")

print("\n2. Reverting to simple cmdline.txt...")
stdin, stdout, stderr = ssh.exec_command(f"""sudo bash -c 'echo "{simple_cmdline}" > /boot/cmdline.txt'""")
err = stderr.read().decode()
if err and 'warning' not in err.lower():
    print(f"  Warning: {err}")
else:
    print("  ✓ Simple cmdline.txt written")

# Verify
print("\n" + "="*70)
print("VERIFYING CONFIGURATION")
print("="*70)

print("\n>>> config.txt HDMI sections:")
stdin, stdout, stderr = ssh.exec_command("grep -E '\\[HDMI|hdmi_' /boot/config.txt")
print(stdout.read().decode())

print("\n>>> cmdline.txt:")
stdin, stdout, stderr = ssh.exec_command("cat /boot/cmdline.txt")
print(stdout.read().decode())

print("\n" + "="*70)
print("Configuration reverted to simple working setup")
print("="*70)
print("\nThis configuration:")
print("- Uses only [HDMI:1] section for second port")
print("- Does NOT disable HDMI:0")
print("- Uses minimal cmdline without framebuffer overrides")
print("- Should show boot text on the Pioneer")
print("\nRebooting now...")

ssh.exec_command('sudo reboot')
ssh.close()

print("\n✓ Reboot initiated")
print("Boot text should now appear on Pioneer HDMI 2 (second port)")
