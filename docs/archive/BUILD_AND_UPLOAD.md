# 🚀 Build and Upload Guide

**One-stop guide for building and uploading firmware to all devices.**

---

## Quick Reference

| Device | Upload Method | Connection | Command |
|--------|---------------|------------|----------|
| **Arduino Nano** | **Local** (plug into PC) | USB-C to PC | `pio run -d arduino --target upload` |
| **ESP32-S3** | **Remote** (via Pi SSH) | USB-C to Pi | `ssh pi@192.168.1.28 '... pio run -d display --target upload'` |
| **Pi App** | **Remote** (SSH) | Network | `ssh pi@192.168.1.28 '... systemctl restart mx5-display'` |

### Physical Setup
- **Arduino Nano**: Disconnected from vehicle, plug into PC for upload
- **ESP32-S3**: Permanently connected to Pi USB (`/dev/ttyACM0`) - upload remotely
- **Pi (192.168.1.28)**: Always on network, git pull + restart service

---

## 🔧 Prerequisites

- **VS Code** with PlatformIO extension installed
- **Arduino Nano** (CH340 or FTDI) with USB cable
- **ESP32-S3** (Waveshare 1.85" Round Display) with USB-C cable

---

## Method 1: VS Code Tasks (Recommended)

Press `Ctrl+Shift+P` → "Tasks: Run Task":

### Remote Deployment (Default - ESP32 & Pi)
- **Deploy All: Build, Push, Flash ESP32, Restart Pi** - Full deployment
- **Pi: Flash ESP32 (Remote)** - Git pull on Pi + flash ESP32 via USB
- **Pi: Git Pull & Restart UI** - Update Pi code only

### Local Upload (Arduino Only)
- **PlatformIO: Upload Arduino** - Upload to Arduino Nano (must be plugged into PC)
- **PlatformIO: Upload and Monitor Arduino** - Upload + serial monitor

---

## Method 2: Command Line

### Arduino Nano (Local - Plug into PC)

The Arduino must be physically connected to your PC:

```powershell
# Find COM port (Windows)
Get-WmiObject Win32_SerialPort | Select-Object DeviceID, Description

# Build and upload
pio run -d arduino --target upload

# Or specify COM port
pio run -d arduino --target upload --upload-port COM3

# Monitor serial
pio device monitor -b 115200
```

### ESP32-S3 Display (Remote via Pi SSH)

The ESP32 is permanently connected to the Pi. Upload remotely:

```powershell
# First, push your changes to GitHub
git add -A && git commit -m "Your message" && git push

# Then SSH to Pi and flash
ssh pi@192.168.1.28 'cd ~/MX5-Telemetry && git pull && ~/.local/bin/pio run -d display --target upload'
```

### Pi Application (Remote Update)

```powershell
# Push changes, then update and restart
git push
ssh pi@192.168.1.28 'cd ~/MX5-Telemetry && git pull && sudo systemctl restart mx5-display'
```

### Full Deploy (All in One)

```powershell
# Build locally, push, flash ESP32, restart Pi
pio run -d display; git add -A; git commit -m 'Deploy update' --allow-empty; git push; ssh pi@192.168.1.28 'cd ~/MX5-Telemetry && git pull && ~/.local/bin/pio run -d display --target upload && sudo systemctl restart mx5-display'
```

---

## 🧪 Verify Upload

### Arduino Nano

1. LEDs should show startup animation (rainbow scan)
2. Open Serial Monitor at **115200 baud** (if ENABLE_SERIAL_DEBUG is true)
3. Without CAN bus connected, LEDs will show error animation after 3 seconds
4. With CAN bus connected, LEDs display RPM-based colors
5. **When connected to Pi**: Arduino receives LED sequence/pattern selection via serial

### ESP32-S3 Display

1. Display shows boot logo on startup
2. Screen cycles through Overview, RPM, TPMS, Engine screens
3. Touch to change screens (or use steering wheel buttons via Pi)
4. Serial monitor shows BLE TPMS scanning status
5. **When connected to Pi**: Receives all CAN telemetry + SWC buttons, sends TPMS + G-force data back

---

## 🔌 Hardware Setup

### System Overview

| Device | Location | CAN | Serial |
|--------|----------|-----|--------|
| **Pi 4B** | Hidden (console/trunk) | MCP2515 x2 (HS + MS) | To ESP32 + Arduino |
| **ESP32-S3** | **Stock oil gauge hole** | None | From Pi (telemetry in, TPMS/G-force out) |
| **Arduino Nano** | Gauge cluster bezel | MCP2515 (shared HS-CAN) | From Pi (LED settings) |

### Arduino Nano Wiring

```
┌──────────────────────────────────────────────────────────────┐
│                        ARDUINO NANO                          │
│              (Located in gauge cluster bezel)                │
│                                                              │
│   D2 ←──── INT (MCP2515 Interrupt - CRITICAL!)              │
│   D5 ────→ WS2812B Data (LED strip around gauges)           │
│   D10 ───→ MCP2515 CS                                        │
│   D11 ───→ MCP2515 MOSI                                      │
│   D12 ←─── MCP2515 MISO                                      │
│   D13 ───→ MCP2515 SCK                                       │
│   D0 ←──── Pi Serial TX (for LED sequence selection)        │
│   A6 ←──── Brightness Pot (optional)                         │
│   D3 ────→ Haptic Motor (optional)                           │
│   5V ────→ MCP2515 VCC, LED Strip VCC                        │
│   GND ───→ MCP2515 GND, LED Strip GND                        │
└──────────────────────────────────────────────────────────────┘

MCP2515 → OBD-II Port (SHARED with Pi MCP2515 #1):
  CANH → Pin 6 (HS-CAN High)
  CANL → Pin 14 (HS-CAN Low)
```

### ESP32-S3 Round Display

- **Location**: Mounted in stock oil gauge hole (1.85" fits perfectly)
- **Connection**: USB-C to Pi for serial data
- **Shows as**: `/dev/ttyACM0` on Pi

The Waveshare ESP32-S3-Touch-LCD-1.85 is pre-wired internally.

**Data Flow**:
- Receives from Pi: CAN telemetry, SWC buttons, settings sync
- Sends to Pi: BLE TPMS data, G-force IMU data

### Raspberry Pi 4B

- **Location**: Hidden in center console or trunk
- **CAN**: Dual MCP2515 (HS-CAN shared with Arduino, MS-CAN exclusive)
- **Output**: HDMI to Pioneer head unit
- **Serial**: To ESP32-S3 and Arduino

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

- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture & design
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - Deployment & testing guide
- [LED_SYSTEM.md](LED_SYSTEM.md) - Complete LED system guide
- [hardware/WIRING_GUIDE.md](hardware/WIRING_GUIDE.md) - Complete wiring diagrams
- [development/DEVELOPMENT_GUIDE.md](development/DEVELOPMENT_GUIDE.md) - Analysis & debugging
