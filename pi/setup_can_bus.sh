#!/bin/bash
# =============================================================================
# MX5 Telemetry - Raspberry Pi CAN Bus Setup Script
# =============================================================================
# This script configures the Raspberry Pi 4B for dual MCP2515 CAN bus modules
# and enables UART for Arduino serial communication.
#
# Run with: sudo bash setup_can_bus.sh
# =============================================================================

set -e  # Exit on error

echo "=============================================="
echo "MX5 Telemetry - Pi CAN Bus Setup"
echo "=============================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Please run as root (sudo bash setup_can_bus.sh)"
    exit 1
fi

# Backup existing config
BOOT_CONFIG="/boot/config.txt"
BACKUP_FILE="/boot/config.txt.backup.$(date +%Y%m%d_%H%M%S)"

echo ""
echo "[1/5] Backing up $BOOT_CONFIG to $BACKUP_FILE..."
cp "$BOOT_CONFIG" "$BACKUP_FILE"
echo "      ✓ Backup created"

# Check if our config already exists
if grep -q "MX5-Telemetry CAN Bus Configuration" "$BOOT_CONFIG"; then
    echo ""
    echo "[!] MX5 CAN configuration already exists in $BOOT_CONFIG"
    echo "    Skipping config.txt modification."
else
    echo ""
    echo "[2/5] Adding CAN bus configuration to $BOOT_CONFIG..."
    
    # Append our configuration
    cat >> "$BOOT_CONFIG" << 'EOF'

# =============================================================================
# MX5-Telemetry CAN Bus Configuration
# Added by setup_can_bus.sh
# =============================================================================

# Enable SPI for CAN bus
dtparam=spi=on

# MCP2515 CAN Module #1 (HS-CAN on CE0, INT on GPIO 25)
# Wiring: CS=GPIO8, INT=GPIO25, SI=GPIO10, SO=GPIO9, SCK=GPIO11
dtoverlay=mcp2515-can0,oscillator=8000000,interrupt=25

# MCP2515 CAN Module #2 (MS-CAN on CE1, INT on GPIO 24)
# Wiring: CS=GPIO7, INT=GPIO24, SI=GPIO10, SO=GPIO9, SCK=GPIO11
dtoverlay=mcp2515-can1,oscillator=8000000,interrupt=24

# Enable GPIO UART for Arduino serial communication
# Pi TX (GPIO14) -> Arduino RX (D3)
# Pi RX (GPIO15) -> Arduino TX (D4)
enable_uart=1

# Disable Bluetooth to free up UART (optional but recommended)
# dtoverlay=disable-bt
EOF
    
    echo "      ✓ Configuration added to $BOOT_CONFIG"
fi

# Create CAN interface startup script
echo ""
echo "[3/5] Creating CAN interface startup script..."

CAN_SCRIPT="/usr/local/bin/mx5-can-setup.sh"
cat > "$CAN_SCRIPT" << 'EOF'
#!/bin/bash
# MX5 Telemetry - Bring up CAN interfaces
# Called by systemd service on boot

# Wait for interfaces to be ready
sleep 2

# Bring up HS-CAN (500kbps) - Engine data, RPM, Speed
if ip link show can0 > /dev/null 2>&1; then
    ip link set can0 up type can bitrate 500000
    echo "can0 (HS-CAN) up at 500kbps"
else
    echo "can0 not found - check MCP2515 wiring"
fi

# Bring up MS-CAN (125kbps) - Steering wheel buttons, body data
if ip link show can1 > /dev/null 2>&1; then
    ip link set can1 up type can bitrate 125000
    echo "can1 (MS-CAN) up at 125kbps"
else
    echo "can1 not found - check MCP2515 wiring"
fi
EOF

chmod +x "$CAN_SCRIPT"
echo "      ✓ Created $CAN_SCRIPT"

# Create systemd service for CAN startup
echo ""
echo "[4/5] Creating systemd service for CAN startup..."

SERVICE_FILE="/etc/systemd/system/mx5-can.service"
cat > "$SERVICE_FILE" << 'EOF'
[Unit]
Description=MX5 Telemetry CAN Bus Setup
After=network.target
Before=mx5-display.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/mx5-can-setup.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

# Enable the service
systemctl daemon-reload
systemctl enable mx5-can.service
echo "      ✓ Created and enabled mx5-can.service"

# Install can-utils if not present
echo ""
echo "[5/5] Checking for can-utils..."
if ! command -v candump &> /dev/null; then
    echo "      Installing can-utils..."
    apt-get update -qq
    apt-get install -y can-utils
    echo "      ✓ can-utils installed"
else
    echo "      ✓ can-utils already installed"
fi

# Summary
echo ""
echo "=============================================="
echo "Setup Complete!"
echo "=============================================="
echo ""
echo "Configuration added to $BOOT_CONFIG:"
echo "  - SPI enabled (dtparam=spi=on)"
echo "  - MCP2515 #1: can0 (HS-CAN, GPIO8/CE0, INT=GPIO25)"
echo "  - MCP2515 #2: can1 (MS-CAN, GPIO7/CE1, INT=GPIO24)"
echo "  - UART enabled for Arduino serial"
echo ""
echo "Systemd service: mx5-can.service"
echo "  - Automatically brings up CAN interfaces on boot"
echo ""
echo "NEXT STEPS:"
echo "  1. Reboot the Pi: sudo reboot"
echo "  2. After reboot, verify CAN interfaces:"
echo "     ip link show can0"
echo "     ip link show can1"
echo "  3. Test with car (ignition on):"
echo "     candump can0  # Should see HS-CAN traffic"
echo "     candump can1  # Should see MS-CAN traffic"
echo ""
echo "To manually bring up CAN interfaces:"
echo "  sudo /usr/local/bin/mx5-can-setup.sh"
echo ""
