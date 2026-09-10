# 📚 MX5-Telemetry Documentation

Complete documentation for the MX5-Telemetry system - a real-time automotive telemetry system for Mazda MX-5 (NC) vehicles.

---

## 🎯 System Overview

The system uses a **three-device architecture** with the Pi as central hub:

| Device | Purpose | Location | Connection |
|--------|---------|----------|------------|
| **Raspberry Pi 4B** | CAN hub + settings cache + HDMI display | Hidden (console/trunk) | MCP2515 (HS + MS CAN) |
| **ESP32-S3 Round Display** | Gauge display + BLE TPMS + G-force IMU | **Stock oil gauge hole** | Serial from Pi |
| **Arduino Nano** | RPM LED strip controller | Gauge cluster bezel | Direct HS-CAN + Serial from Pi |

### Data Flow

```
OBD-II → HS-CAN & MS-CAN → Pi (Hub) → ESP32 Display + Arduino LEDs + Pioneer HDMI
         └─ Arduino (Direct RPM for <1ms LED response)
```

---

## 🚀 Quick Start Guide

| Step | Document | Description |
|------|----------|-------------|
| 1️⃣ | [**ARCHITECTURE.md**](ARCHITECTURE.md) | ⭐ System architecture & design decisions |
| 2️⃣ | [**hardware/HARDWARE.md**](hardware/HARDWARE.md) | Complete hardware guide (parts, wiring, TPMS, SWC) |
| 3️⃣ | [**DEPLOYMENT_GUIDE.md**](DEPLOYMENT_GUIDE.md) | ⭐ Build, flash firmware & deploy in vehicle |
| 4️⃣ | [**LED_SYSTEM.md**](LED_SYSTEM.md) | Complete LED system documentation |

---

## 🔧 Hardware Documentation

| Document | Description |
|----------|-------------|
| [**hardware/HARDWARE.md**](hardware/HARDWARE.md) | ⭐ Complete hardware guide (parts, wiring, TPMS, SWC) |

---

## ✨ Feature Documentation

### LED System (Arduino)
| Document | Description |
|----------|-------------|
| [**LED_SYSTEM.md**](LED_SYSTEM.md) | ⭐ Complete LED system guide (states, modes, performance) |

---

## 💻 Development

| Document | Description |
|----------|-------------|
| [**development/DEVELOPMENT_GUIDE.md**](development/DEVELOPMENT_GUIDE.md) | ⭐ Complete development guide (analysis, debugging, testing) |

---

## 📁 Archive

Older documentation and completed features can be found in [archive/](archive/).

---

## 📞 Support & Contributing

For issues or questions:
- Check [ARCHITECTURE.md](ARCHITECTURE.md) for system architecture
- Review [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for troubleshooting
- Check [hardware/HARDWARE.md](hardware/HARDWARE.md) for wiring and parts

**Last Updated:** December 29, 2025

## 📦 Archived Documentation

Old/superseded documentation kept for historical reference in `archive/dual-arduino/docs/`:

- **Dual Arduino Architecture** - Replaced by single Arduino + Pi
- **GPS & SD Card Logging** - Now handled by Pi
- **GoPro Power Control** - Legacy feature

---

## ⚡ Quick Commands

### Remote Deployment (Default - ESP32 & Pi)
```powershell
# Flash ESP32 via Pi (ESP32 is plugged into Pi USB)
git push
ssh pi@192.168.1.23 'cd ~/MX5-Telemetry && git pull && ~/.local/bin/pio run -d display --target upload'

# Update Pi application
ssh pi@192.168.1.23 'cd ~/MX5-Telemetry && git pull && sudo systemctl restart mx5-display'

# Or use VS Code tasks: "Pi: Flash ESP32 (Remote)" / "Pi: Git Pull & Restart UI"
```

### Local Upload (Arduino Only - Must Plug into PC)
```powershell
# Arduino must be connected to PC via USB
pio run -d arduino --target upload
```

### Simulators & Monitoring
```powershell
# Run LED Simulator
python tools/simulators/led_simulator/led_simulator_v2.1.py

# Monitor serial output (local device)
pio device monitor -b 115200
```

---

## 🗂️ Project Structure

```
MX5-Telemetry/
├── arduino/                    # Arduino Nano (CAN + LED)
│   └── src/main.cpp            # LED controller firmware
├── display/                    # ESP32-S3 Round Display
│   └── src/main.cpp            # Display firmware
├── pi/                         # Raspberry Pi 4B
│   └── ui/                     # Pi display application
├── lib/                        # Shared Arduino libraries
├── docs/                       # All documentation (you are here)
├── tools/simulators/           # LED & UI simulators
├── archive/                    # Archived (dual-arduino setup)
└── build-automation/           # Build scripts
```
