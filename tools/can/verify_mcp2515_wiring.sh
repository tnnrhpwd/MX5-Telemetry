#!/bin/bash
# =============================================================================
# MCP2515 Wiring Verification Script
# =============================================================================
# This script verifies the SPI wiring for both MCP2515 modules
# =============================================================================

echo "=============================================="
echo "MCP2515 Wiring Verification"
echo "=============================================="
echo ""

# Expected wiring for MCP2515 modules
echo "Expected Wiring:"
echo ""
echo "MCP2515 Module #1 (can0):"
echo "  VCC  → Pi Pin 2 or 4 (5V) or Pin 1/17 (3.3V)"
echo "  GND  → Pi Pin 6, 9, 14, 20, 25, 30, 34, 39"
echo "  CS   → Pi Pin 24 (GPIO 8 / SPI0 CE0)"
echo "  SO   → Pi Pin 21 (GPIO 9 / SPI0 MISO)"
echo "  SI   → Pi Pin 19 (GPIO 10 / SPI0 MOSI)"
echo "  SCK  → Pi Pin 23 (GPIO 11 / SPI0 SCLK)"
echo "  INT  → Pi Pin 22 (GPIO 25)"
echo ""
echo "MCP2515 Module #2 (can1):"
echo "  VCC  → Pi Pin 2 or 4 (5V) or Pin 1/17 (3.3V)"
echo "  GND  → Pi Pin 6, 9, 14, 20, 25, 30, 34, 39 (shared)"
echo "  CS   → Pi Pin 26 (GPIO 7 / SPI0 CE1)"
echo "  SO   → Pi Pin 21 (GPIO 9 / SPI0 MISO) [SHARED]"
echo "  SI   → Pi Pin 19 (GPIO 10 / SPI0 MOSI) [SHARED]"
echo "  SCK  → Pi Pin 23 (GPIO 11 / SPI0 SCLK) [SHARED]"
echo "  INT  → Pi Pin 18 (GPIO 24)"
echo ""
echo "=============================================="
echo ""

# Check if SPI is enabled
echo "[1/5] Checking if SPI is enabled..."
if lsmod | grep -q spi_bcm2835; then
    echo "  ✓ SPI kernel module loaded"
else
    echo "  ✗ SPI kernel module NOT loaded"
    echo "    Run: sudo raspi-config → Interface Options → SPI → Enable"
    exit 1
fi

if [ -d "/sys/bus/spi/devices/spi0.0" ]; then
    echo "  ✓ SPI device spi0.0 exists (for can0)"
else
    echo "  ✗ SPI device spi0.0 NOT found"
fi

if [ -d "/sys/bus/spi/devices/spi0.1" ]; then
    echo "  ✓ SPI device spi0.1 exists (for can1)"
else
    echo "  ✗ SPI device spi0.1 NOT found"
fi

echo ""

# Check kernel messages
echo "[2/5] Checking kernel initialization messages..."
dmesg | grep -i mcp251 | tail -10
echo ""

# Check GPIO usage
echo "[3/5] Checking GPIO configuration..."
if command -v gpio &> /dev/null; then
    echo "  GPIO 25 (INT for can0):"
    gpio -g mode 25 in
    gpio -g read 25
    echo "  GPIO 24 (INT for can1):"
    gpio -g mode 24 in
    gpio -g read 24
else
    echo "  gpio command not found (install wiringpi to check GPIOs)"
fi
echo ""

# Check CAN interfaces
echo "[4/5] Checking CAN interface status..."
echo ""
echo "can0 status:"
ip -details link show can0 2>/dev/null || echo "  ✗ can0 not found"
echo ""
echo "can1 status:"
ip -details link show can1 2>/dev/null || echo "  ✗ can1 not found"
echo ""

# Check for errors
echo "[5/5] Checking for errors in system log..."
if dmesg | grep -i "mcp251" | grep -i "error\|fail" > /dev/null; then
    echo "  ✗ Errors found:"
    dmesg | grep -i "mcp251" | grep -i "error\|fail"
else
    echo "  ✓ No errors found in MCP2515 initialization"
fi
echo ""

echo "=============================================="
echo "Verification Complete"
echo "=============================================="
echo ""
echo "If both modules initialized successfully but"
echo "communication still fails, check:"
echo ""
echo "1. TERMINATION: Both modules need 120Ω resistors"
echo "   between CAN-H and CAN-L (jumper or soldered)"
echo ""
echo "2. WIRING: CAN-H to CAN-H, CAN-L to CAN-L"
echo ""
echo "3. POWER: Both modules have stable 3.3V or 5V"
echo ""
echo "4. OSCILLATOR: Confirm 8MHz crystal on modules"
echo "   (check the silver component, should say 8.000)"
