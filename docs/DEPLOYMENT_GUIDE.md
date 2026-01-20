# MX5 Telemetry - Complete Deployment Guide

## � Quick Reference

**Raspberry Pi Network Access:**
- **Home WiFi:** `ssh pi@192.168.1.23` or `ssh pi@mx5pi.local`
- **Phone Hotspot:** `ssh pi@10.62.26.67`
- **Web Interface:** `http://<pi-ip>:5000` (e.g., http://192.168.1.23:5000 or http://10.62.26.67:5000)

**Quick Deploy:** Run `flash_all_updates.ps1` (auto-detects Pi network)

---

## �📋 Table of Contents

1. [System Overview](#system-overview)
2. [Hardware Setup](#hardware-setup)
3. [Building Firmware](#building-firmware)
4. [Deployment Methods](#deployment-methods)
5. [Raspberry Pi Setup](#raspberry-pi-setup)
6. [Verification & Testing](#verification--testing)
7. [Troubleshooting](#troubleshooting)

---

## System Overview

The MX5 Telemetry system uses **three devices** working together:

| Device | Purpose | Location | Connection |
|--------|---------|----------|------------|
| **Raspberry Pi 4B** | CAN hub + settings cache + HDMI display | Hidden (console/trunk) | MCP2515 (HS + MS CAN) |
| **ESP32-S3 Round Display** | Gauge display + BLE TPMS + G-force IMU | **Stock oil gauge hole** | Serial from Pi |
| **Arduino Nano** | RPM LED strip controller | Gauge cluster bezel | Direct HS-CAN + Serial from Pi |

### Data Flow Summary

```
OBD-II Port
    │
    ├─── HS-CAN (500k) ──┬──► Pi MCP2515 #1 ──► Pi processes all data
    │                    │
    │                    └──► Arduino MCP2515 ──► RPM → LED strip (direct, <1ms)
    │
    └─── MS-CAN (125k) ──────► Pi MCP2515 #2 ──► Steering wheel buttons
    
Pi (Central Hub)
    │
    ├──► ESP32-S3 (Serial) ──► Telemetry + SWC buttons + settings sync
    │    ◄─── ESP32-S3 ◄───── TPMS + G-force data
    │
    ├──► Arduino (Serial) ───► LED sequence selection + settings sync
    │
    └──► Pioneer (HDMI) ─────► Full dashboard display
```

---

## Hardware Setup

### Prerequisites

- **VS Code** with PlatformIO extension installed
- **Arduino Nano** (CH340 or FTDI) with USB cable
- **ESP32-S3** (Waveshare 1.85" Round Display) with USB-C cable
- **Raspberry Pi 4B** - Network IPs:
  - **Home WiFi:** 192.168.1.23 or mx5pi.local
  - **Phone Hotspot:** 10.62.26.67
- **MCP2515 CAN modules** (3x - two for Pi, one for Arduino)
- **OBD-II breakout or splitter** for CAN bus access

### Physical Connections

See [hardware/HARDWARE.md](hardware/HARDWARE.md) for complete wiring diagrams, parts list, TPMS setup, and steering wheel control programming.

---

## Building Firmware

### Physical Setup

| Device | Upload Method | Connection | Physical Location |
|--------|---------------|------------|-------------------|
| **Arduino Nano** | **Local** (plug into PC) | USB-C to PC | Disconnected from vehicle for upload |
| **ESP32-S3** | **Remote** (via Pi SSH) | USB-C to Pi (`/dev/ttyACM0`) | Permanently connected to Pi |
| **Pi App** | **Remote** (SSH) | Network | Home: 192.168.1.23, Hotspot: 10.62.26.67 |

### Method 1: VS Code Tasks (Recommended) ⭐

Press `Ctrl+Shift+P` → "Tasks: Run Task":

#### Remote Deployment (ESP32 & Pi)
- **Deploy All: Build, Push, Flash ESP32, Restart Pi** - Full deployment
- **Pi: Flash ESP32 (Remote)** - Git pull on Pi + flash ESP32 via USB
- **Pi: Git Pull & Restart UI** - Update Pi code only

#### Local Upload (Arduino Only)
- **PlatformIO: Upload Arduino** - Upload to Arduino Nano (must be plugged into PC)
- **PlatformIO: Upload and Monitor Arduino** - Upload + serial monitor

### Method 2: Command Line

#### Arduino Nano (Local - Plug into PC)

The Arduino must be physically connected to your PC:

```powershell
# Find COM port (Windows)
Get-WmiObject Win32_SerialPort | Select-Object DeviceID, Description

# Build and upload
pio run -d arduino --target upload

# Or specify COM port explicitly
pio run -d arduino --target upload --upload-port COM3

# Upload and monitor in one command
pio run -d arduino --target upload && pio device monitor -b 115200
```

**Troubleshooting Arduino Upload:**
- "avrdude: stk500_recv(): programmer is not responding" → Close Serial Monitor, try different USB port, or press reset button during upload
- "Access denied" on COM port → Close any program using the port (including Serial Monitor)
- Old bootloader (clone Nanos): Add `board_upload.speed = 57600` to `arduino/platformio.ini`

#### ESP32-S3 Display (Remote via Pi SSH)

The ESP32 is permanently connected to the Pi. Upload remotely:

```powershell
# First, push your changes to GitHub
git add -A && git commit -m "Your message" && git push

# Then SSH to Pi and flash (use home network IP or hotspot IP)
ssh pi@192.168.1.23 'cd ~/MX5-Telemetry && git pull && ~/.local/bin/pio run -d display --target upload'
# OR if on phone hotspot:
ssh pi@10.62.26.67 'cd ~/MX5-Telemetry && git pull && ~/.local/bin/pio run -d display --target upload'
```

**Troubleshooting ESP32 Upload:**
- Upload fails → Hold BOOT button on ESP32 while clicking upload, release when upload starts
- Still failing → Try different USB-C cable (some are charge-only)

#### Pi Application (Remote Update)

```powershell
# Push changes, then update and restart (home network)
git push
ssh pi@192.168.1.23 'cd ~/MX5-Telemetry && git pull && sudo systemctl restart mx5-display'

# Or on phone hotspot:
ssh pi@10.62.26.67 'cd ~/MX5-Telemetry && git pull && sudo systemctl restart mx5-display'
```

#### Full Deploy (All in One)

```powershell
# Build locally, push, flash ESP32, restart Pi
pio run -d display; git add -A; git commit -m 'Deploy update' --allow-empty; git push; ssh pi@192.168.1.23 'cd ~/MX5-Telemetry && git pull && ~/.local/bin/pio run -d display --target upload && sudo systemctl restart mx5-display'
```

### Expected Memory Usage

| Device | RAM Usage | Flash Usage |
|--------|-----------|-------------|
| Arduino Nano | ~35% (700 bytes) | ~45% (14KB) |
| ESP32-S3 | ~25% | ~60% |

---

## Deployment Methods

### 🚀 Quick Deploy Tasks (VS Code)

The workspace includes preconfigured tasks for rapid deployment:

| Task | What It Does | When To Use |
|------|--------------|-------------|
| `Deploy All: Build, Push, Flash ESP32, Restart Pi` | Complete system deployment | After code changes to any component |
| `Pi: Flash ESP32 (Remote)` | Updates ESP32 firmware only | ESP32 display changes only |
| `Pi: Git Pull & Restart UI` | Updates Pi display only | Pi display changes only |
| `Pi: SSH Connect` | Opens SSH session | Manual Pi debugging |
| `Pi: View Display Logs` | Streams display service logs | Troubleshooting Pi display |

### Manual Deployment Commands

#### SSH to Pi
```bash
# Home network:
ssh pi@192.168.1.23
# Or hostname: ssh pi@mx5pi.local

# Phone hotspot:
ssh pi@10.62.26.67
```

#### Update Pi & Restart Display
```bash
ssh pi@192.168.1.23 'cd ~/MX5-Telemetry && git pull && sudo systemctl restart mx5-display'
```

#### Flash ESP32 via Pi
```bash
ssh pi@192.168.1.23 'cd ~/MX5-Telemetry && git pull && ~/.local/bin/pio run -d display --target upload'
```

#### View Pi Display Logs
```bash
ssh pi@192.168.1.23 'journalctl -u mx5-display -f'
```

---

## Raspberry Pi Setup

### Remote Access Configuration

| Setting | Value |
|---------|-------|
| **IP Address (Home WiFi)** | `192.168.1.23` |
| **IP Address (S25 Hotspot)** | `10.62.26.67` |
| **User** | `pi` |
| **SSH (Home)** | `ssh pi@192.168.1.23` |
| **SSH (Hotspot)** | `ssh pi@10.62.26.67` |
| **Project Path** | `~/MX5-Telemetry` |
| **Display Service** | `mx5-display.service` (systemd) |

### Pi Display Service

The Pi runs the telemetry display as a systemd service:

```bash
# Check status
sudo systemctl status mx5-display

# Restart after code changes
sudo systemctl restart mx5-display

# View logs
journalctl -u mx5-display -f

# Enable on boot
sudo systemctl enable mx5-display
```

### Settings Cache

The Pi caches all user settings and syncs them to ESP32 and Arduino on startup:
- Brightness levels
- Shift RPM threshold
- LED pattern/sequence
- Warning thresholds
- Units (mph/kph, °F/°C)

Settings are stored in: `~/MX5-Telemetry/pi/config/settings.json`

---

## Verification & Testing

### Arduino Nano Verification

1. LEDs should show startup animation (rainbow scan)
2. Open Serial Monitor at **115200 baud** (if ENABLE_SERIAL_DEBUG is true)
3. Without CAN bus connected, LEDs will show error animation after 3 seconds
4. Connect to vehicle - LEDs should start responding to RPM

**Expected LED Behavior:**
- Blue zone: 0-1999 RPM (idle)
- Green zone: 2000-2999 RPM (cruising)
- Yellow zone: 3000-4499 RPM (normal driving)
- Orange zone: 4500-5499 RPM (spirited)
- Red zone: 5500+ RPM (high RPM)

### ESP32-S3 Display Verification

1. Power on - should show boot screen
2. Display should show telemetry data within 2 seconds
3. Touch screen to cycle through 8 screens
4. Check TPMS data is receiving (if sensors installed)

**8 Screens:**
0. Overview - Dashboard summary
1. RPM/Speed - Large gauges
2. TPMS - Tire pressure
3. Engine - Temperature/voltage
4. G-Force - IMU data
5. Diagnostics - Warnings
6. System - ESP32 status
7. Settings - Configuration

### Raspberry Pi Display Verification

1. Check HDMI output to Pioneer head unit
2. Should mirror same 8-screen layout as ESP32
3. Test steering wheel button navigation
4. Verify CAN bus status on System screen

**Check CAN Status:**
```bash
ssh pi@192.168.1.23 'candump can0'  # HS-CAN (500k)
ssh pi@192.168.1.23 'candump can1'  # MS-CAN (125k)
```

### System Integration Test

1. **Power on vehicle** - All devices should initialize
2. **Check Arduino LEDs** - Should respond to engine RPM
3. **Check ESP32 display** - Should show telemetry
4. **Check Pi display** - Should show synchronized data
5. **Test steering wheel buttons** - Should navigate screens on both displays
6. **Test TPMS** - Should show tire pressures (if sensors installed)
7. **Test G-Force** - Drive and check lateral/longitudinal forces

---

## Troubleshooting

### Arduino Issues

| Problem | Solution |
|---------|----------|
| LEDs not lighting | Check power (5V/GND), LED data pin (D5) |
| Error animation (red flash) | CAN not connected - check MCP2515 wiring |
| Wrong RPM display | Verify CAN ID 0x201 and RPM formula (÷4) |
| No serial output | Ensure `ENABLE_SERIAL_DEBUG` is true in code |

### ESP32-S3 Issues

| Problem | Solution |
|---------|----------|
| Blank display | Check USB-C power, try reflashing firmware |
| No touch response | Calibrate touch or use keyboard in demo mode |
| No TPMS data | Check BLE sensors are powered and paired |
| Serial errors | Check baud rate (115200), swap TX/RX if needed |

### Raspberry Pi Issues

| Problem | Solution |
|---------|----------|
| No HDMI output | Check `hdmi_force_hotplug=1` in `/boot/config.txt` |
| CAN not working | Run `sudo ip link set can0 up type can bitrate 500000` |
| Display service crashed | `sudo systemctl restart mx5-display` |
| Can't SSH | Check Pi is on network, verify IP address |

### CAN Bus Issues

| Problem | Solution |
|---------|----------|
| No CAN data | Check OBD-II wiring (pins 6,14=HS / 3,11=MS) |
| Intermittent data | Check termination, reduce wire length |
| Wrong data values | Verify CAN IDs match your vehicle year |

### Complete System Reset

If all else fails:

```bash
# On Arduino
# 1. Re-upload firmware via USB
pio run -d arduino --target upload

# On ESP32
# 2. Reflash ESP32 via Pi
ssh pi@192.168.1.23 'cd ~/MX5-Telemetry && ~/.local/bin/pio run -d display --target upload'

# On Pi
# 3. Restart Pi display service
ssh pi@192.168.1.23 'sudo systemctl restart mx5-display'

# 4. Check logs
ssh pi@192.168.1.23 'journalctl -u mx5-display -f'
```

---

## Next Steps

After successful deployment:

1. **Test drive** - Verify all systems work in real-world conditions
2. **Adjust settings** - Use Settings screen (Screen 7) to customize
3. **Monitor stability** - Check logs after first few drives
4. **Fine-tune** - Adjust shift RPM, warning thresholds, brightness

For detailed system architecture and feature documentation, see:
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture & design decisions
- [hardware/HARDWARE.md](hardware/HARDWARE.md) - Complete hardware guide

---

**Last Updated:** December 29, 2025
