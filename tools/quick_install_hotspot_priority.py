#!/usr/bin/env python3
"""Quick install hotspot priority"""
import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.1.23", username="pi", password="Hopwood12", timeout=10)

script = r"""#!/bin/bash
sleep 10
HOTSPOT_SSID="Tanner's Galaxy S25"
CURRENT_SSID=$(iwgetid -r)
echo "[WiFi Priority] Current: $CURRENT_SSID"
if iwlist wlan0 scan 2>/dev/null | grep -q "$HOTSPOT_SSID"; then
    echo "[WiFi Priority] Hotspot available"
    if [ "$CURRENT_SSID" != "$HOTSPOT_SSID" ]; then
        echo "[WiFi Priority] Switching to hotspot..."
        HOTSPOT_ID=$(wpa_cli -i wlan0 list_networks | grep "$HOTSPOT_SSID" | awk '{print $1}')
        if [ ! -z "$HOTSPOT_ID" ]; then
            wpa_cli -i wlan0 select_network $HOTSPOT_ID
            echo "[WiFi Priority] Switched to hotspot"
        fi
    fi
else
    echo "[WiFi Priority] Hotspot not available"
fi
"""

service = """[Unit]
Description=WiFi Hotspot Priority
After=network.target wpa_supplicant.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/prefer-hotspot.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
"""

print("Installing hotspot priority service...")

print("\n[1] Creating script...")
stdin, stdout, stderr = ssh.exec_command(f"echo '{script}' | sudo tee /usr/local/bin/prefer-hotspot.sh > /dev/null")
stdout.read()
stdin, stdout, stderr = ssh.exec_command("sudo chmod +x /usr/local/bin/prefer-hotspot.sh")
stdout.read()
print("✓ Script created")

print("\n[2] Creating service...")
stdin, stdout, stderr = ssh.exec_command(f"echo '{service}' | sudo tee /etc/systemd/system/wifi-priority.service > /dev/null")
stdout.read()
print("✓ Service created")

print("\n[3] Enabling service...")
stdin, stdout, stderr = ssh.exec_command("sudo systemctl daemon-reload")
stdout.read()
stdin, stdout, stderr = ssh.exec_command("sudo systemctl enable wifi-priority.service")
enable_out = stdout.read().decode()
print(enable_out)
print("✓ Service enabled")

print("\n✓ Hotspot priority service installed!")
print("\nNow on every boot, the Pi will automatically switch to your hotspot if it's available.")

ssh.close()
