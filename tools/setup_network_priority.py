#!/usr/bin/env python3
"""Install network priority script on Pi"""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.1.23", username="pi", password="Hopwood12", timeout=10)

# Create the network priority script
priority_script = """#!/bin/bash
# Network Priority Manager for MX5 Pi
# Forces reconnection on boot to select highest priority network

sleep 10  # Wait for WiFi to stabilize

# Force wpa_supplicant to reconsider network priorities
wpa_cli -i wlan0 reconfigure

sleep 5

# Check current connection
CURRENT_SSID=$(iwgetid -r)

# Log to syslog
logger "MX5 Network Priority: Connected to $CURRENT_SSID"

# If not connected to hotspot but it's available, disconnect and reconnect
if [[ "$CURRENT_SSID" != *"Galaxy"* ]]; then
    # Check if hotspot is available
    HOTSPOT_AVAILABLE=$(iwlist wlan0 scan | grep -i "Tanner's Galaxy")
    
    if [ ! -z "$HOTSPOT_AVAILABLE" ]; then
        logger "MX5 Network Priority: Hotspot detected, switching..."
        wpa_cli -i wlan0 disconnect
        sleep 2
        wpa_cli -i wlan0 reconnect
        sleep 5
        NEW_SSID=$(iwgetid -r)
        logger "MX5 Network Priority: Now connected to $NEW_SSID"
    fi
fi
"""

print("Creating network priority script...")
sftp = ssh.open_sftp()
with sftp.open('/home/pi/network_priority.sh', 'w') as f:
    f.write(priority_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command("chmod +x /home/pi/network_priority.sh")
stdout.read()
print("✓ Script created and made executable")

# Add to rc.local for automatic startup
print("\nAdding to rc.local for automatic startup...")
stdin, stdout, stderr = ssh.exec_command("sudo grep -q 'network_priority.sh' /etc/rc.local")
rc_check = stdout.read().decode()

if not rc_check:
    stdin, stdout, stderr = ssh.exec_command("sudo sed -i '/^exit 0/i /home/pi/network_priority.sh &' /etc/rc.local")
    stdout.read()
    print("✓ Added to rc.local")
else:
    print("✓ Already in rc.local")

print("\n" + "=" * 70)
print("NETWORK PRIORITY CONFIGURED")
print("=" * 70)
print("\nThe Pi will now automatically:")
print("  1. Check for the hotspot on boot")
print("  2. Switch to it if available (priority 15)")
print("  3. Fall back to ChattaWi-Fi if hotspot unavailable")
print("\nYou can manually force a switch by running:")
print("  ssh pi@192.168.1.23 'sudo /home/pi/network_priority.sh'")

ssh.close()
