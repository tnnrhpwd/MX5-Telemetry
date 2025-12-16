# 📚 MX5-Telemetry Documentation

Complete documentation for the MX5-Telemetry system.

---

## 🎯 System Architecture

The current system uses a **three-device architecture**:

| Device | Purpose | Connection |
|--------|---------|------------|
| **Raspberry Pi 4B** | CAN bus hub + HDMI display | Dual MCP2515 (HS + MS CAN) |
| **ESP32-S3 Round Display** | Gauge display + BLE TPMS receiver | Serial from Pi |
| **Arduino Nano** | RPM LED strip controller | Direct HS-CAN (MCP2515) |

See [PI_DISPLAY_INTEGRATION.md](PI_DISPLAY_INTEGRATION.md) for complete architecture details.

---

## 🚀 Getting Started

| Document | Description |
|----------|-------------|
| [**PI_DISPLAY_INTEGRATION.md**](PI_DISPLAY_INTEGRATION.md) | ⭐ **Start here!** Complete system architecture |
| [**BUILD_AND_UPLOAD.md**](BUILD_AND_UPLOAD.md) | Build and flash Arduino/ESP32 firmware |
| [setup/OUTDOOR_TEST_QUICKSTART.md](setup/OUTDOOR_TEST_QUICKSTART.md) | Field testing checklist |

---

## 🔧 Hardware

| Document | Description |
|----------|-------------|
| [PI_DISPLAY_INTEGRATION.md](PI_DISPLAY_INTEGRATION.md) | **Primary** - Pi + ESP32 + Arduino system |
| [hardware/WIRING_GUIDE_SINGLE_ARDUINO.md](hardware/WIRING_GUIDE_SINGLE_ARDUINO.md) | Arduino Nano standalone wiring |
| [hardware/WIRING_GUIDE.md](hardware/WIRING_GUIDE.md) | Detailed Arduino pin assignments |
| [hardware/PARTS_LIST.md](hardware/PARTS_LIST.md) | Bill of materials |
| [hardware/TPMS_BLUETOOTH.md](hardware/TPMS_BLUETOOTH.md) | BLE TPMS sensor setup |

---

## ✨ Features

### LED System
| Document | Description |
|----------|-------------|
| [features/LED_STATE_SYSTEM.md](features/LED_STATE_SYSTEM.md) | Complete LED state documentation |
| [features/LED_TIMING_AND_PERFORMANCE.md](features/LED_TIMING_AND_PERFORMANCE.md) | Update rate and latency analysis |
| [features/LED_SIMULATOR_ARDUINO_CONNECTION.md](features/LED_SIMULATOR_ARDUINO_CONNECTION.md) | Python simulator setup |
| [features/LED_SIMULATOR_TROUBLESHOOTING.md](features/LED_SIMULATOR_TROUBLESHOOTING.md) | Simulator debugging |

### Display System
| Document | Description |
|----------|-------------|
| [DISPLAY_DEPLOYMENT.md](DISPLAY_DEPLOYMENT.md) | ESP32-S3 display deployment |
| [PI_DISPLAY_INTEGRATION.md](PI_DISPLAY_INTEGRATION.md) | Raspberry Pi + ESP32 integration |

---

## 💻 Development

| Document | Description |
|----------|-------------|
| [development/PLATFORMIO_GUIDE.md](development/PLATFORMIO_GUIDE.md) | PlatformIO deep-dive (CLI, simulation) |
| [development/BUILD_ARCHITECTURE.md](development/BUILD_ARCHITECTURE.md) | Code architecture |
| [development/DATA_ANALYSIS.md](development/DATA_ANALYSIS.md) | CSV data visualization |
| [development/CLEANUP_GUIDE.md](development/CLEANUP_GUIDE.md) | Code cleanup notes |

---

## 📋 Session Notes

| Document | Description |
|----------|-------------|
| [TODO_NEXT_SESSION.md](TODO_NEXT_SESSION.md) | Current tasks and progress |

---

## 📦 Archive

Old/superseded documentation kept for historical reference in `archive/dual-arduino/docs/`:

| Archived Document | Notes |
|----------|-------|
| WIRING_GUIDE_DUAL_ARDUINO.md | Dual Arduino wiring (replaced by single Arduino + Pi) |
| MASTER_SLAVE_ARCHITECTURE.md | Dual Arduino architecture |
| DUAL_ARDUINO_SETUP.md | Dual Arduino configuration |

GPS & Logging features documentation (for future reference):
- features/GPS_TROUBLESHOOTING.md
- features/COMPREHENSIVE_DATA_LOGGING.md
- features/LOG_ROTATION_FEATURE.md
- features/AUTO_START_FEATURE.md

---

## Quick Commands

```powershell
# Build Arduino (LED controller)
pio run -d arduino

# Upload Arduino
pio run -d arduino --target upload

# Build ESP32-S3 Display
pio run -d display

# Upload ESP32-S3 Display
pio run -d display --target upload
```

## 🗂️ Project Structure

```
MX5-Telemetry/
├── arduino/                    # Arduino Nano (CAN + LED)
│   ├── src/main.cpp            # LED controller firmware
│   └── platformio.ini
│
├── display/                    # ESP32-S3 Round Display
│   ├── src/main.cpp            # Display firmware
│   ├── ui/                     # UI components
│   └── scripts/                # Firmware backup/flash tools
│
├── pi/                         # Raspberry Pi 4B
│   ├── ui/src/                 # Pi display application
│   └── start_display.sh        # Startup script
│
├── lib/                        # Shared libraries
│   ├── CANHandler/             # CAN bus module
│   ├── LEDController/          # LED control module
│   ├── Config/                 # Configuration
│   └── ...
│
├── archive/                    # Archived (dual-arduino setup)
│   └── dual-arduino/
│
├── docs/                       # All documentation (you are here)
├── tools/                      # Simulators & utilities
├── build-automation/           # Build scripts
└── hardware/                   # Wokwi circuit files
```

## 🚀 Quick Navigation

### I want to...

- **Understand the system** → Start with [PI_DISPLAY_INTEGRATION.md](PI_DISPLAY_INTEGRATION.md)
- **Build Arduino LED strip** → [hardware/WIRING_GUIDE_SINGLE_ARDUINO.md](hardware/WIRING_GUIDE_SINGLE_ARDUINO.md)
- **Set up ESP32-S3 display** → [DISPLAY_DEPLOYMENT.md](DISPLAY_DEPLOYMENT.md)
- **Set up Pi display** → [PI_DISPLAY_INTEGRATION.md](PI_DISPLAY_INTEGRATION.md)
- **Use PlatformIO IDE** → [development/PLATFORMIO_GUIDE.md](development/PLATFORMIO_GUIDE.md)
- **Run UI simulators** → See VS Code tasks

## 🎯 Recommended Reading Order

### For First-Time Users:
1. Main [README.md](../README.md) - Project overview
2. [PI_DISPLAY_INTEGRATION.md](PI_DISPLAY_INTEGRATION.md) - Full architecture
3. [hardware/PARTS_LIST.md](hardware/PARTS_LIST.md) - Order components
4. [BUILD_AND_UPLOAD.md](BUILD_AND_UPLOAD.md) - Flash firmware

### For Developers:
1. [development/PLATFORMIO_GUIDE.md](development/PLATFORMIO_GUIDE.md) - Set up dev environment
2. Review source code in `arduino/`, `display/`, `pi/`
3. Use simulators in VS Code tasks

## 📞 Support

If you can't find what you need in the documentation:

1. Check the main [README.md](../README.md) troubleshooting section
2. Review existing GitHub issues
3. Open a new issue with detailed information

## 🤝 Contributing to Documentation

Documentation improvements are always welcome! When contributing:

- Keep guides concise but complete
- Include code examples where helpful
- Add screenshots for complex procedures
- Test all commands before submitting
- Update this index when adding new docs

---

**💡 Tip**: All documentation files are written in Markdown. View them in any text editor, or on GitHub for formatted rendering.
