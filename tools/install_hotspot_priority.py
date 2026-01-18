#!/usr/bin/env python3
"""
Create and install a systemd service that prioritizes hotspot on boot
"""
import paramiko

PI_IP = "192.168.1.23"
PI_USER = "pi"
PI_PASSWORD = "Hopwood12"

# Script that will run on boot to prefer hotspot
prefer_hotspot_script = """#!/bin/bash
# Prefer hotspot over home WiFi

HOTSPOT_SSID="Tanner's Galaxy S25"
HOTSPOT_PRIORITY=15
HOME_WIFI_SSID="ChattaWi-Fi"
HOME_WIFI_PRIORITY=5

sleep 10  # Wait for network to stabilize

# Get current SSID
CURRENT_SSID=$(iwgetid -r)

echo "[WiFi Priority] Current network: $CURRENT_SSID"

# Check if hotspot is available
if iwlist wlan0 scan | grep -q "$HOTSPOT_SSID"; then
    echo "[WiFi Priority] Hotspot '$HOTSPOT_SSID' is available"
    
    if [ "$CURRENT_SSID" != "$HOTSPOT_SSID" ]; then
        echo "[WiFi Priority] Switching to hotspot..."
        wpa_cli -i wlan0 reconfigure
        sleep 5
        
        # Force select the hotspot network
        HOTSPOT_ID=$(wpa_cli -i wlan0 list_networks | grep "$HOTSPOT_SSID" | awk '{print $1}')
        if [ ! -z "$HOTSPOT_ID" ]; then
            wpa_cli -i wlan0 select_network $HOTSPOT_ID
            echo "[WiFi Priority] Switched to hotspot (ID: $HOTSPOT_ID)"
        fi
    else
        echo "[WiFi Priority] Already connected to hotspot"
    fi
else
    echo "[WiFi Priority] Hotspot not available, using current network"
fi
"""

# Systemd service file
service_file = """[Unit]
Description=WiFi Hotspot Priority Service
After=network.target wpa_supplicant.service
Wants=network.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/prefer-hotspot.sh
RemainAfterExit=yes
User=root

[Install]
WantedBy=multi-user.target
"""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_IP, username=PI_USER, password=PI_PASSWORD, timeout=10)

print("=" * 70)
print("INSTALLING HOTSPOT PRIORITY SERVICE")
print("=" * 70)

# Upload the script
print("\n[1] Creating prefer-hotspot script...")
stdin, stdout, stderr = ssh.exec_command(f"sudo tee /usr/local/bin/prefer-hotspot.sh > /dev/null << 'EOF'\n{prefer_hotspot_script}\nEOF")
stdout.read()
print("✓ Script created")

print("\n[2] Making script executable...")
stdin, stdout, stderr = ssh.exec_command("sudo chmod +x /usr/local/bin/prefer-hotspot.sh")
stdout.read()
print("✓ Script is executable")

# Create systemd service
print("\n[3] Creating systemd service...")
stdin, stdout, stderr = ssh.exec_command(f"sudo tee /etc/systemd/system/wifi-priority.service > /dev/null << 'EOF'\n{service_file}\nEOF")
stdout.read()
print("✓ Service file created")

print("\n[4] Enabling service...")
stdin, stdout, stderr = ssh.exec_command("sudo systemctl daemon-reload && sudo systemctl enable wifi-priority.service")
stdout.read()
print("✓ Service enabled")

print("\n[5] Testing the script manually...")
stdin, stdout, stderr = ssh.exec_command("sudo /usr/local/bin/prefer-hotspot.sh")
output = stdout.read().decode()
print(output)

print("\n" + "=" * 70)
print("✓✓✓ HOTSPOT PRIORITY SERVICE INSTALLED ✓✓✓")
print("=" * 70)
print("\nThe Pi will now automatically prefer your hotspot on every boot.")
print("If the hotspot is available, it will switch to it within 15 seconds of startup.")
print("\nTo manually trigger the switch right now:")
print("  sudo systemctl start wifi-priority.service")
print("\nTo check status:")
print("  sudo systemctl status wifi-priority.service")

ssh.close()
