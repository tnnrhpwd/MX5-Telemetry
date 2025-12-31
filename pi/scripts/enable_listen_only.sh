#!/bin/bash
# =============================================================================
# Enable Listen-Only Mode for Production
# =============================================================================
# This script configures both CAN interfaces for listen-only mode.
# This prevents the Pi from transmitting any data to the car's CAN bus.
#
# Run with: sudo bash enable_listen_only.sh
# =============================================================================

set -e

echo "=============================================="
echo "Configuring CAN Interfaces for Listen-Only"
echo "=============================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Please run as root (sudo bash enable_listen_only.sh)"
    exit 1
fi

# Update the mx5-can-setup.sh script
CAN_SCRIPT="/usr/local/bin/mx5-can-setup.sh"

if [ ! -f "$CAN_SCRIPT" ]; then
    echo "ERROR: $CAN_SCRIPT not found"
    echo "Run setup_can_bus.sh first to create the CAN setup script"
    exit 1
fi

# Backup existing script
BACKUP_FILE="${CAN_SCRIPT}.backup.$(date +%Y%m%d_%H%M%S)"
cp "$CAN_SCRIPT" "$BACKUP_FILE"
echo "✓ Backed up existing script to $BACKUP_FILE"

# Create new script with listen-only mode
cat > "$CAN_SCRIPT" << 'EOF'
#!/bin/bash
# MX5 Telemetry - Bring up CAN interfaces in LISTEN-ONLY mode
# Called by systemd service on boot

# Wait for interfaces to be ready
sleep 2

# Bring up HS-CAN (500kbps) - Engine data, RPM, Speed
# LISTEN-ONLY mode for production (no transmission to car CAN bus)
if ip link show can0 > /dev/null 2>&1; then
    ip link set can0 down 2>/dev/null || true
    ip link set can0 up type can bitrate 500000 listen-only on
    echo "can0 (HS-CAN) up at 500kbps (listen-only)"
else
    echo "can0 not found - check MCP2515 wiring"
fi

# Bring up MS-CAN (125kbps) - Steering wheel buttons, body data
# LISTEN-ONLY mode for production (no transmission to car CAN bus)
if ip link show can1 > /dev/null 2>&1; then
    ip link set can1 down 2>/dev/null || true
    ip link set can1 up type can bitrate 125000 listen-only on
    echo "can1 (MS-CAN) up at 125kbps (listen-only)"
else
    echo "can1 not found - check MCP2515 wiring"
fi
EOF

chmod +x "$CAN_SCRIPT"
echo "✓ Updated $CAN_SCRIPT with listen-only mode"

# Restart the CAN service to apply changes
echo ""
echo "Restarting mx5-can service..."
systemctl daemon-reload
systemctl restart mx5-can.service

echo ""
echo "=============================================="
echo "Configuration Complete!"
echo "=============================================="
echo ""
echo "✓ Both CAN interfaces now in LISTEN-ONLY mode"
echo "✓ Pi will NOT transmit to car CAN bus"
echo ""
echo "Verify configuration:"
echo "  ip -details link show can0"
echo "  ip -details link show can1"
echo ""
echo "Check for 'LISTEN-ONLY' flag in output"
echo ""
