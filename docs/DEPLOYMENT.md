# MX5 Telemetry Deployment Guide

## Hardware Setup

### Raspberry Pi 4B
- **IP Address**: `192.168.1.28`
- **User**: `pi`
- **SSH**: `ssh pi@192.168.1.28`
- **Project Path**: `~/MX5-Telemetry`
- **Display Service**: `mx5-display.service` (systemd)

### ESP32-S3 Round Display
- **Connection**: USB to Raspberry Pi (`/dev/ttyACM0`)
- **Baud Rate**: 115200
- **Flash via Pi**: PlatformIO installed on Pi

### Arduino Nano (LED Controller)
- **Connection**: USB to Raspberry Pi
- **Purpose**: RPM LED strip control

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
