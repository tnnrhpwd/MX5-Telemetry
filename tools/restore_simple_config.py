#!/usr/bin/env python3
"""
RESTORE SIMPLE WORKING CONFIG FOR HDMI PORT 2
Back to basics - minimal config that outputs to the correct physical port
"""
import paramiko
import time

print("Connecting to Pi...")
for attempt in range(5):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect('192.168.1.28', username='pi', password='Hopwood12', timeout=10)
        print("✓ Connected")
        break
    except Exception as e:
        if attempt < 4:
            print(f"Attempt {attempt+1} failed, retrying...")
            time.sleep(5)
        else:
            print(f"Cannot connect. Please reboot Pi manually and run this again.")
            exit(1)

print("\n" + "="*70)
print("RESTORING SIMPLE HDMI PORT 2 CONFIGURATION")
print("="*70)

# Simple working config - output to HDMI 1 (physical port 2, farthest from USB-C)
simple_config = """# For more options and information see
# http://rpf.io/configtxt

disable_overscan=1

# Enable audio
dtparam=audio=on
dtparam=i2c_arm=on

# GPU and display settings
dtoverlay=dwc2
max_framebuffers=2
arm_64bit=1
start_x=1
gpu_mem=128
dtoverlay=vc4-fkms-v3d

# =============================================================================
# MX5-Telemetry CAN Bus Configuration
# =============================================================================
dtparam=spi=on
dtoverlay=mcp2515-can0,oscillator=8000000,interrupt=25
dtoverlay=mcp2515-can1,oscillator=8000000,interrupt=24
enable_uart=1

# =============================================================================
# HDMI Port 2 Configuration (farthest from USB-C) for Pioneer AVH-W4500NEX
# =============================================================================
[HDMI:1]
hdmi_group=2
hdmi_mode=87
hdmi_cvt=800 480 60 6 0 0 0
hdmi_drive=2
config_hdmi_boost=7
hdmi_force_hotplug=1

[all]
"""

# Clean cmdline - no framebuffer overrides
clean_cmdline = "console=serial0,115200 console=tty1 root=PARTUUID=eee3aba0-02 rootfstype=ext4 fsck.repair=yes rootwait modules-load=dwc2,g_ether usbhid.mousepoll=1"

print("\n1. Writing clean config.txt...")
cmd = f"""sudo tee /boot/config.txt > /dev/null << 'EOFCFG'
{simple_config}
EOFCFG"""
stdin, stdout, stderr = ssh.exec_command(cmd)
err = stderr.read().decode()
if err:
    print(f"  Error: {err}")
else:
    print("  ✓ Config written")

print("\n2. Writing clean cmdline.txt...")
stdin, stdout, stderr = ssh.exec_command(f"""sudo bash -c 'echo "{clean_cmdline}" > /boot/cmdline.txt'""")
print("  ✓ Cmdline written")

# Remove the force-hdmi service if it exists (might be causing issues)
print("\n3. Removing force-hdmi service if it exists...")
stdin, stdout, stderr = ssh.exec_command("sudo systemctl stop force-hdmi.service 2>/dev/null; sudo systemctl disable force-hdmi.service 2>/dev/null")
print("  ✓ Cleaned up")

print("\n" + "="*70)
print("VERIFICATION")
print("="*70)

print("\n>>> Config for HDMI:1 (port 2):")
stdin, stdout, stderr = ssh.exec_command("grep -A7 'HDMI:1' /boot/config.txt")
print(stdout.read().decode())

print("\n>>> Cmdline:")
stdin, stdout, stderr = ssh.exec_command("cat /boot/cmdline.txt")
print(stdout.read().decode())

print("\n" + "="*70)
print("CONFIGURATION RESTORED")
print("="*70)
print("\nThis is a MINIMAL config that:")
print("  • Outputs to HDMI port 2 (HDMI:1, farthest from USB-C)")
print("  • Uses standard Pioneer settings (800x480)")
print("  • Has vc4-fkms-v3d enabled")
print("  • No complex framebuffer or blanking overrides")
print("\nRebooting now...")

ssh.exec_command('sudo reboot')
ssh.close()

print("\n✓ Pi rebooting")
print("\nBoot text should appear on Pioneer in 30 seconds.")
print("After that we'll tackle keeping signal active through desktop.")
