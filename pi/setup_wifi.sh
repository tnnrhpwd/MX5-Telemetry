#!/bin/bash
# Setup WiFi networks on Raspberry Pi
# Configures home network and mobile hotspot fallback

set -e

echo "=== Pi WiFi Network Setup ==="
echo ""

# wpa_supplicant.conf is gitignored (contains real WiFi passwords) - it must exist
# locally before running this script. Either copy it from wpa_supplicant.conf.example
# and fill in your real credentials, or restore it from the encrypted backup repo
# (see ../docs/guides/ENV_BACKUP_GUIDE.md): .\scripts\restore-env.ps1
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ ! -f "$SCRIPT_DIR/wpa_supplicant.conf" ]; then
    echo "✗ $SCRIPT_DIR/wpa_supplicant.conf not found."
    echo "  Copy wpa_supplicant.conf.example to wpa_supplicant.conf and fill in your"
    echo "  real WiFi credentials, or run ../scripts/restore-env.ps1 to decrypt the backup."
    exit 1
fi

# Backup existing config
if [ -f /etc/wpa_supplicant/wpa_supplicant.conf ]; then
    sudo cp /etc/wpa_supplicant/wpa_supplicant.conf /etc/wpa_supplicant/wpa_supplicant.conf.backup
    echo "✓ Backed up existing config to wpa_supplicant.conf.backup"
fi

# Copy new config
sudo cp "$SCRIPT_DIR/wpa_supplicant.conf" /etc/wpa_supplicant/wpa_supplicant.conf

# Set proper permissions
sudo chmod 600 /etc/wpa_supplicant/wpa_supplicant.conf

echo "✓ Installed new wpa_supplicant.conf"

# Reconfigure WiFi without reboot
sudo wpa_cli -i wlan0 reconfigure

echo "✓ WiFi reconfigured"
echo ""
echo "Configured networks (priority order - see wpa_supplicant.conf for actual SSIDs):"
echo "  1. Home WiFi (5GHz)"
echo "  2. Home WiFi (2.4GHz)"
echo "  3. Mobile hotspot"
echo ""
echo "The Pi will automatically connect to the highest priority available network."
echo ""

# Show current connection
echo "Current WiFi status:"
iwgetid || echo "Not connected to any network yet"
