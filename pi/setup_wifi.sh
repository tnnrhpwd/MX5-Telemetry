#!/bin/bash
# Setup WiFi networks on Raspberry Pi
# Configures home network and mobile hotspot fallback

set -e

echo "=== Pi WiFi Network Setup ==="
echo ""

# Backup existing config
if [ -f /etc/wpa_supplicant/wpa_supplicant.conf ]; then
    sudo cp /etc/wpa_supplicant/wpa_supplicant.conf /etc/wpa_supplicant/wpa_supplicant.conf.backup
    echo "✓ Backed up existing config to wpa_supplicant.conf.backup"
fi

# Copy new config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
sudo cp "$SCRIPT_DIR/wpa_supplicant.conf" /etc/wpa_supplicant/wpa_supplicant.conf

# Set proper permissions
sudo chmod 600 /etc/wpa_supplicant/wpa_supplicant.conf

echo "✓ Installed new wpa_supplicant.conf"

# Reconfigure WiFi without reboot
sudo wpa_cli -i wlan0 reconfigure

echo "✓ WiFi reconfigured"
echo ""
echo "Configured networks (priority order):"
echo "  1. ChattaWi-Fi-5G (home 5GHz)"
echo "  2. ChattaWi-Fi (home 2.4GHz)"
echo "  3. Tanner's Galaxy S25 (mobile hotspot)"
echo ""
echo "The Pi will automatically connect to the highest priority available network."
echo ""

# Show current connection
echo "Current WiFi status:"
iwgetid || echo "Not connected to any network yet"
