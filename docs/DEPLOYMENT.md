# MX5 Telemetry Deployment Guide

## System Overview

The MX5 Telemetry system uses three devices:

| Device | Purpose | Location |
|--------|---------|----------|
| **Raspberry Pi 4B** | CAN hub + settings cache + HDMI display | Hidden (console/trunk) |
| **ESP32-S3 Round Display** | Gauge display + BLE TPMS + G-force | **Stock oil gauge hole** |
| **Arduino Nano** | RPM LED strip (direct CAN) | Gauge cluster bezel |

### Data Flow

- **Pi → ESP32**: All CAN telemetry + SWC buttons + settings sync (serial)
- **ESP32 → Pi**: TPMS data (BLE) + G-force data (IMU)
- **Pi → Arduino**: LED sequence/pattern selection + settings sync (serial)
- **Arduino**: Reads RPM directly from shared HS-CAN bus

### Settings Cache

The Pi caches all user settings and syncs them to ESP32 and Arduino on startup:
- Brightness levels
- Shift RPM threshold
- LED pattern/sequence
- Warning thresholds
- Units (mph/kph, °F/°C)

---

## Hardware Setup & Upload Methods

### Raspberry Pi 4B (Remote Access)
- **IP Address**: `192.168.1.28`
- **User**: `pi`
- **SSH**: `ssh pi@192.168.1.28`
- **Project Path**: `~/MX5-Telemetry`
- **Display Service**: `mx5-display.service` (systemd)
- **Upload Method**: `git pull` + `systemctl restart` via SSH

### ESP32-S3 Round Display (Remote Upload via Pi)
- **Location**: Mounted in stock oil gauge hole (1.85" display fits perfectly)
- **Connection**: USB-C to Raspberry Pi (`/dev/ttyACM0`)
- **Baud Rate**: 115200
- **Upload Method**: **Remote** - Flash via Pi using PlatformIO over SSH
- **Command**: `ssh pi@192.168.1.28 '~/.local/bin/pio run -d display --target upload'`

### Arduino Nano (Local Upload Required)
- **Location**: Gauge cluster bezel (LED strip surrounds instruments)
- **Connection**: USB to PC (disconnect from vehicle, plug into dev machine)
- **Upload Method**: **Local** - Must plug into PC to flash
- **Command**: `pio run -d arduino --target upload`
- **Purpose**: RPM LED strip control (direct CAN) + receives LED pattern from Pi

---

## VS Code Tasks (Ctrl+Shift+P → "Run Task")

### Quick Deploy Tasks
| Task | Description |
|------|-------------|
| `Deploy All: Build, Push, Flash ESP32, Restart Pi` | Full deployment - builds locally, pushes, flashes ESP32 via Pi, restarts Pi display |
| `Pi: Flash ESP32 (Remote)` | Git pull on Pi + flash ESP32 via USB |
| `Pi: Git Pull & Restart UI` | Update Pi code and restart display service |

### Pi Management
| Task | Description |
|------|-------------|
| `Pi: SSH Connect` | Open SSH session to Pi |
| `Pi: View Display Logs` | Stream display service logs |

### Local Build
| Task | Description |
|------|-------------|
| `PlatformIO: Build Display (ESP32-S3)` | Build ESP32 firmware locally |
| `PlatformIO: Build Arduino` | Build Arduino LED controller |

---

## Manual Commands

### SSH to Pi
```bash
ssh pi@192.168.1.28
```

### Update Pi & Restart Display
```bash
ssh pi@192.168.1.28 'cd ~/MX5-Telemetry && git pull && sudo systemctl restart mx5-display'
```

### Flash ESP32 via Pi
```bash
ssh pi@192.168.1.28 'cd ~/MX5-Telemetry && git pull && ~/.local/bin/pio run -d display --target upload'
```

### View Pi Display Logs
```bash
ssh pi@192.168.1.28 'journalctl -u mx5-display -f'
```

### Restart Display Service
```bash
ssh pi@192.168.1.28 'sudo systemctl restart mx5-display'
```

### Stop Display (for debugging)
```bash
ssh pi@192.168.1.28 'sudo systemctl stop mx5-display'
```

### Run Display Manually (with output)
```bash
ssh pi@192.168.1.28 'cd ~/MX5-Telemetry && python pi/ui/src/main.py'
```

---

## Typical Workflow

### 1. Make code changes locally

### 2. Deploy everything (one command):
Run VS Code task: `Deploy All: Build, Push, Flash ESP32, Restart Pi`

Or manually:
```bash
# Build locally
pio run -d display

# Commit and push
git add -A && git commit -m "Your message" && git push

# Flash ESP32 and restart Pi
ssh pi@192.168.1.28 'cd ~/MX5-Telemetry && git pull && ~/.local/bin/pio run -d display --target upload && sudo systemctl restart mx5-display'
```

### 3. If only Pi code changed (no ESP32):
Run VS Code task: `Pi: Git Pull & Restart UI`

---

## Troubleshooting

### ESP32 not flashing
- Check USB connection: `ssh pi@192.168.1.28 'ls /dev/ttyACM*'`
- Should show `/dev/ttyACM0`

### Display not starting
- Check logs: `ssh pi@192.168.1.28 'journalctl -u mx5-display -n 50'`
- Check service status: `ssh pi@192.168.1.28 'systemctl status mx5-display'`

### Network issues
- Pi static IP: `192.168.1.28`
- Make sure you're on the same network
