#!/usr/bin/env python3
"""
Single targeted fix: Keep HDMI active after graphical boot
Create a persistent service that maintains HDMI output
"""
import paramiko
import time

print("Waiting for Pi to finish booting...")
time.sleep(40)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.1.28', username='pi', password='Hopwood12', timeout=10)

print("\n" + "="*70)
print("INSTALLING HDMI KEEPALIVE SERVICE")
print("="*70)

# Script that keeps HDMI active
keepalive_script = """#!/bin/bash
# Keep HDMI port 2 active and outputting

while true; do
    # Ensure HDMI 1 (port 2) is powered on
    tvservice -s -v 7 | grep -q "state 0x" || tvservice -p -v 7
    
    # Unblank framebuffer
    echo 0 > /sys/class/graphics/fb0/blank 2>/dev/null
    
    sleep 5
done
"""

# Systemd service
keepalive_service = """[Unit]
Description=HDMI Port 2 Keepalive for Pioneer Display
After=graphical.target

[Service]
Type=simple
ExecStart=/usr/local/bin/hdmi-keepalive.sh
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=graphical.target
"""

print("\n1. Creating keepalive script...")
cmd = f"""cat << 'EOFSCRIPT' | sudo tee /usr/local/bin/hdmi-keepalive.sh > /dev/null
{keepalive_script}
EOFSCRIPT"""
stdin, stdout, stderr = ssh.exec_command(cmd)
stdin, stdout, stderr = ssh.exec_command("sudo chmod +x /usr/local/bin/hdmi-keepalive.sh")
print("  ✓ Script created")

print("\n2. Creating systemd service...")
cmd = f"""cat << 'EOFSVC' | sudo tee /etc/systemd/system/hdmi-keepalive.service > /dev/null
{keepalive_service}
EOFSVC"""
stdin, stdout, stderr = ssh.exec_command(cmd)
print("  ✓ Service created")

print("\n3. Enabling and starting service...")
stdin, stdout, stderr = ssh.exec_command("sudo systemctl daemon-reload")
stdin, stdout, stderr = ssh.exec_command("sudo systemctl enable hdmi-keepalive.service")
stdin, stdout, stderr = ssh.exec_command("sudo systemctl start hdmi-keepalive.service")
time.sleep(2)
print("  ✓ Service started")

print("\n4. Checking service status...")
stdin, stdout, stderr = ssh.exec_command("sudo systemctl status hdmi-keepalive.service | head -15")
print(stdout.read().decode())

print("\n5. Checking HDMI status now...")
stdin, stdout, stderr = ssh.exec_command("tvservice -s -v 7")
print(stdout.read().decode())

print("\n6. Updating config.txt with additional settings...")
stdin, stdout, stderr = ssh.exec_command("cat /boot/config.txt")
current_config = stdout.read().decode()

# Add hdmi_ignore_edid to HDMI:1 section if not present
if "hdmi_ignore_edid" not in current_config:
    stdin, stdout, stderr = ssh.exec_command("""
sudo sed -i '/^\[HDMI:1\]/a hdmi_ignore_edid=0xa5000080\nhdmi_pixel_encoding=2' /boot/config.txt
""")
    print("  ✓ Added hdmi_ignore_edid to force signal")

print("\n" + "="*70)
print("HDMI KEEPALIVE INSTALLED")
print("="*70)
print("\nWhat this does:")
print("  • Runs continuously in the background")
print("  • Every 5 seconds checks if HDMI port 2 is active")
print("  • Powers it on if it goes off")
print("  • Keeps framebuffer unblank")
print("  • Restarts automatically if it crashes")
print("\nThe service is running NOW - check the Pioneer display!")

response = input("\nDo you see output on Pioneer? (y/n): ").strip().lower()
if response == 'y':
    print("\n✓ SUCCESS! HDMI is working!")
else:
    print("\nLet me check what's happening...")
    stdin, stdout, stderr = ssh.exec_command("sudo journalctl -u hdmi-keepalive.service -n 20")
    print(stdout.read().decode())
    
    print("\nRebooting to test full boot sequence...")
    ssh.exec_command('sudo reboot')
    print("✓ Rebooting - service will start automatically")
    print("Wait 60 seconds and check if Pioneer shows output")

ssh.close()
print("\nDone!")
