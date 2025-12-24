#!/usr/bin/env python3
"""
Force HDMI to stay active after boot
Create a service that keeps HDMI 1 powered on and unblank framebuffer
"""
import paramiko
import time

print("Connecting to Pi...")
time.sleep(2)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.1.28', username='pi', password='Hopwood12', timeout=10)

print("\n" + "="*70)
print("FORCING HDMI TO STAY ACTIVE")
print("="*70)

# Create a script that forces HDMI on and keeps it on
force_hdmi_script = """#!/bin/bash
# Force HDMI 1 (second port) to stay active

# Turn on HDMI 1 explicitly
tvservice -e "DMT 87 HDMI" -v 7

# Unblank the framebuffer
echo 0 > /sys/class/graphics/fb0/blank

# Set display power on
vcgencmd display_power 1 7

# Keep framebuffer console active
setterm -blank 0 -powerdown 0 -powersave off < /dev/console > /dev/console 2>&1

echo "HDMI 1 forced active at $(date)"
"""

# Create systemd service to run this at boot
hdmi_service = """[Unit]
Description=Force HDMI 1 Active for Pioneer Display
After=graphical.target
Before=mx5-display.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/force-hdmi-on.sh
RemainAfterExit=yes
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=graphical.target
"""

print("\n1. Creating force-hdmi-on.sh script...")
cmd = f"""sudo tee /usr/local/bin/force-hdmi-on.sh > /dev/null << 'EOFSCRIPT'
{force_hdmi_script}
EOFSCRIPT"""
stdin, stdout, stderr = ssh.exec_command(cmd)
stdin, stdout, stderr = ssh.exec_command("sudo chmod +x /usr/local/bin/force-hdmi-on.sh")
print("  ✓ Script created and made executable")

print("\n2. Creating systemd service...")
cmd = f"""sudo tee /etc/systemd/system/force-hdmi.service > /dev/null << 'EOFSVC'
{hdmi_service}
EOFSVC"""
stdin, stdout, stderr = ssh.exec_command(cmd)
print("  ✓ Service created")

print("\n3. Enabling service...")
stdin, stdout, stderr = ssh.exec_command("sudo systemctl daemon-reload")
stdin, stdout, stderr = ssh.exec_command("sudo systemctl enable force-hdmi.service")
print("  ✓ Service enabled")

print("\n4. Testing script immediately...")
stdin, stdout, stderr = ssh.exec_command("sudo /usr/local/bin/force-hdmi-on.sh")
time.sleep(2)
out = stdout.read().decode()
err = stderr.read().decode()
if out:
    print(f"  Output: {out}")
if err:
    print(f"  Errors: {err}")

print("\n5. Checking HDMI status now...")
stdin, stdout, stderr = ssh.exec_command("tvservice -s -v 7")
print(f"  {stdout.read().decode()}")

print("\n6. Checking framebuffer blank status...")
stdin, stdout, stderr = ssh.exec_command("cat /sys/class/graphics/fb0/blank")
blank_status = stdout.read().decode().strip()
print(f"  Blank value: {blank_status} (0=visible, 1=blanked)")

print("\n" + "="*70)
print("HDMI FORCE-ON SERVICE INSTALLED")
print("="*70)
print("\nWhat this does:")
print("  • Runs after boot completes")
print("  • Explicitly turns on HDMI 1 with tvservice")
print("  • Unblanks the framebuffer")
print("  • Sets display power on")
print("  • Disables console blanking")
print("\nThe script has been run now - check if Pioneer shows output!")
print("\nIf not showing yet, reboot to test full boot sequence:")

response = input("\nReboot to test full boot sequence? (y/n): ").strip().lower()
if response == 'y':
    print("\nRebooting...")
    ssh.exec_command('sudo reboot')
    print("✓ Rebooting - wait 60 seconds and check Pioneer display")
else:
    print("\nCheck Pioneer now. If no output, run: sudo reboot")

ssh.close()
print("\nDone!")
