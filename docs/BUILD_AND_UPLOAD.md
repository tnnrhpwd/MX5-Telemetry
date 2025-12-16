# 🚀 Build and Upload Guide

**One-stop guide for building and uploading firmware to all devices.**

---

## Quick Reference

| Device | Purpose | Build Command | Upload Command |
|--------|---------|---------------|----------------|
| **Arduino Nano** | LED Controller | `pio run -d arduino` | `pio run -d arduino --target upload` |
| **ESP32-S3** | Round Display | `pio run -d display` | `pio run -d display --target upload` |

---

## 🔧 Prerequisites

- **VS Code** with PlatformIO extension installed
- **Arduino Nano** (CH340 or FTDI) with USB cable
- **ESP32-S3** (Waveshare 1.85" Round Display) with USB-C cable

---

## Method 1: VS Code Tasks (Easiest)

Press `Ctrl+Shift+B` and select:
- **PlatformIO: Build Arduino** - Build Arduino firmware
- **PlatformIO: Upload Arduino** - Upload to Arduino Nano
- **PlatformIO: Build Display (ESP32-S3)** - Build ESP32 firmware
- **PlatformIO: Upload Display (ESP32-S3)** - Upload to ESP32-S3

---

## Method 2: Command Line

### Find Your COM Ports

```powershell
# Windows - List COM ports
Get-WmiObject Win32_SerialPort | Select-Object DeviceID, Description
```

### Arduino Nano (LED Controller)

```powershell
cd C:\Users\tanne\Documents\Github\MX5-Telemetry

# Build
pio run -d arduino

# Upload
pio run -d arduino --target upload

# Upload with specific port
pio run -d arduino --target upload --upload-port COM3

# Monitor serial
pio device monitor -b 115200
```

### ESP32-S3 Display

```powershell
# Build
pio run -d display

# Upload
pio run -d display --target upload

# Upload with specific port
pio run -d display --target upload --upload-port COM4

# Monitor serial
pio device monitor -b 115200
```

---

## 🧪 Verify Upload

### Arduino Nano

1. LEDs should show startup animation (rainbow scan)
2. Open Serial Monitor at **115200 baud** (if ENABLE_SERIAL_DEBUG is true)
3. Without CAN bus connected, LEDs will show error animation after 3 seconds
4. With CAN bus connected, LEDs display RPM-based colors

### ESP32-S3 Display

1. Display shows boot logo on startup
2. Screen cycles through Overview, RPM, TPMS, Engine screens
3. Touch to change screens (or use steering wheel buttons via Pi)
4. Serial monitor shows BLE TPMS scanning status

---

## 🔌 Hardware Setup

### Arduino Nano Wiring

```
┌──────────────────────────────────────────────────────────────┐
│                        ARDUINO NANO                          │
│                                                              │
│   D2 ←──── INT (MCP2515 Interrupt - CRITICAL!)              │
│   D5 ────→ WS2812B Data                                      │
│   D10 ───→ MCP2515 CS                                        │
│   D11 ───→ MCP2515 MOSI                                      │
│   D12 ←─── MCP2515 MISO                                      │
│   D13 ───→ MCP2515 SCK                                       │
│   A6 ←──── Brightness Pot (optional)                         │
│   D3 ────→ Haptic Motor (optional)                           │
│   5V ────→ MCP2515 VCC, LED Strip VCC                        │
│   GND ───→ MCP2515 GND, LED Strip GND                        │
└──────────────────────────────────────────────────────────────┘

MCP2515 → OBD-II Port:
  CANH → Pin 6 (HS-CAN High)
  CANL → Pin 14 (HS-CAN Low)
```

### ESP32-S3 Round Display

The Waveshare ESP32-S3-Touch-LCD-1.85 is pre-wired. Connect via USB-C to Pi for serial data.

**Serial Connection (USB preferred):**
- Pi USB-A port → ESP32-S3 USB-C port
- Shows as `/dev/ttyACM0` on Pi

### Raspberry Pi 4B

See [PI_DISPLAY_INTEGRATION.md](PI_DISPLAY_INTEGRATION.md) for full Pi wiring with dual MCP2515 modules.

---

## 🔧 Troubleshooting

### "avrdude: stk500_recv(): programmer is not responding"

1. **Close Serial Monitor** - can't upload while monitoring
2. **Try different USB port**
3. **Press reset button** while upload starts
4. **Check USB cable** - must be data cable, not charge-only

### "Access denied" on COM port

1. Close any other program using the port
2. Close Serial Monitor in VS Code
3. Restart VS Code

### Arduino: LEDs stuck on error animation

1. Check MCP2515 wiring (especially INT → D2)
2. Verify CAN bus is connected and active
3. Check OBD-II CANH/CANL connections

### ESP32-S3: Upload fails

1. Hold BOOT button while clicking upload
2. Release BOOT when upload starts
3. Try different USB-C cable (some are charge-only)

### Old bootloader (clone Nanos)

Some clone Nanos use the old bootloader:
```powershell
# Edit arduino/platformio.ini and add:
# board_upload.speed = 57600
```

---

## 📊 Expected Memory Usage

| Device | RAM | Flash |
|--------|-----|-------|
| Arduino Nano | ~35% | ~45% |
| ESP32-S3 | ~25% | ~60% |

---

## See Also

- [hardware/WIRING_GUIDE_SINGLE_ARDUINO.md](hardware/WIRING_GUIDE_SINGLE_ARDUINO.md) - Detailed Arduino wiring
- [PI_DISPLAY_INTEGRATION.md](PI_DISPLAY_INTEGRATION.md) - Full system architecture
- [features/LED_STATE_SYSTEM.md](features/LED_STATE_SYSTEM.md) - LED behavior documentation
- [DISPLAY_DEPLOYMENT.md](DISPLAY_DEPLOYMENT.md) - ESP32-S3 display deployment
