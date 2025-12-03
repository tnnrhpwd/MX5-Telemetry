# 📚 MX5-Telemetry Documentation

Complete documentation for the MX5-Telemetry system.

---

## 🔄 Choose Your Setup

| Setup | Best For | Guide |
|-------|----------|-------|
| **🎯 Single Arduino** | RPM display only, fastest response | [WIRING_GUIDE_SINGLE_ARDUINO.md](hardware/WIRING_GUIDE_SINGLE_ARDUINO.md) |
| **📊 Dual Arduino** | Full logging with GPS & SD card | [WIRING_GUIDE_DUAL_ARDUINO.md](hardware/WIRING_GUIDE_DUAL_ARDUINO.md) |

> 💡 **Recommendation:** Use Single Arduino unless you need GPS/SD logging.

---

## 🚀 Getting Started

| Document | Description |
|----------|-------------|
| [**BUILD_AND_UPLOAD.md**](BUILD_AND_UPLOAD.md) | ⭐ **Start here!** Build and flash Arduinos |
| [setup/DUAL_ARDUINO_SETUP.md](setup/DUAL_ARDUINO_SETUP.md) | Dual-Arduino configuration |
| [setup/OUTDOOR_TEST_QUICKSTART.md](setup/OUTDOOR_TEST_QUICKSTART.md) | Field testing checklist |

---

## 🔧 Hardware

| Document | Description |
|----------|-------------|
| [hardware/WIRING_GUIDE_SINGLE_ARDUINO.md](hardware/WIRING_GUIDE_SINGLE_ARDUINO.md) | **Recommended** - Simple single Arduino wiring |
| [hardware/WIRING_GUIDE_DUAL_ARDUINO.md](hardware/WIRING_GUIDE_DUAL_ARDUINO.md) | Dual Arduino wiring for full logging |
| [hardware/WIRING_GUIDE.md](hardware/WIRING_GUIDE.md) | Legacy detailed pin assignments |
| [hardware/PARTS_LIST.md](hardware/PARTS_LIST.md) | Bill of materials (~$80-140) |
| [hardware/MASTER_SLAVE_ARCHITECTURE.md](hardware/MASTER_SLAVE_ARCHITECTURE.md) | Dual Arduino architecture |

---

## ✨ Features

### LED System
| Document | Description |
|----------|-------------|
| [features/LED_STATE_SYSTEM.md](features/LED_STATE_SYSTEM.md) | Complete LED state documentation |
| [features/LED_TIMING_AND_PERFORMANCE.md](features/LED_TIMING_AND_PERFORMANCE.md) | Update rate and latency analysis |
| [features/LED_SIMULATOR_ARDUINO_CONNECTION.md](features/LED_SIMULATOR_ARDUINO_CONNECTION.md) | Python simulator setup |
| [features/LED_SIMULATOR_TROUBLESHOOTING.md](features/LED_SIMULATOR_TROUBLESHOOTING.md) | Simulator debugging |

### GPS & Logging
| Document | Description |
|----------|-------------|
| [features/GPS_TROUBLESHOOTING.md](features/GPS_TROUBLESHOOTING.md) | GPS fix issues |
| [features/COMPREHENSIVE_DATA_LOGGING.md](features/COMPREHENSIVE_DATA_LOGGING.md) | Data logging system |
| [features/LOG_ROTATION_FEATURE.md](features/LOG_ROTATION_FEATURE.md) | Log file management |
| [features/AUTO_START_FEATURE.md](features/AUTO_START_FEATURE.md) | Automatic logging startup |

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

Old/superseded documentation kept for historical reference:

| Document | Superseded By |
|----------|---------------|
| archive/FLASH_ARDUINOS.md | BUILD_AND_UPLOAD.md |
| archive/UPLOAD_GUIDE.md | BUILD_AND_UPLOAD.md |
| archive/BUILD_GUIDE.md | BUILD_AND_UPLOAD.md |
| archive/QUICK_START.md | BUILD_AND_UPLOAD.md |
| archive/QUICK_REFERENCE.md | BUILD_AND_UPLOAD.md |
| archive/LED_QUICKREF.md | LED_STATE_SYSTEM.md |
| archive/LED_AUTO_SYNC.md | (outdated) |
| archive/STRUCTURE.md | (one-time setup) |
| archive/PLATFORMIO_VERIFICATION.md | (one-time setup) |
| archive/REORGANIZATION_SUMMARY.md | (one-time setup) |

---

## Quick Commands

```powershell
# Build both Arduinos
pio run -d master; pio run -d slave

# Upload both (adjust COM ports)
pio run -d master --target upload --upload-port COM3
pio run -d slave --target upload --upload-port COM4
```
  - `THREE_STATE_SUMMARY.md` - Historical feature summary
  - `PROJECT_INTEGRATION_SUMMARY.md` - Integration notes

## 🗂️ Project Structure

```
MX5-Telemetry/
├── platformio.ini              # PlatformIO configuration
├── README.md                   # Main project documentation
├── LICENSE                     # MIT license
│
├── src/                        # Main application code
│   ├── main.cpp                # Application entry point
│   └── config.h                # Configuration
│
├── lib/                        # Custom libraries (modular)
│   ├── CANHandler/             # CAN bus module
│   ├── LEDController/          # LED control module
│   ├── GPSHandler/             # GPS module
│   ├── DataLogger/             # SD logging module
│   └── PowerManager/           # Power management module
│
├── docs/                       # All documentation (you are here)
│   ├── README.md               # Documentation index
│   ├── QUICK_START.md          # Quick setup guide
│   ├── WIRING_GUIDE.md         # Hardware assembly
│   ├── PARTS_LIST.md           # Bill of materials
│   ├── PLATFORMIO_GUIDE.md     # Development environment
│   ├── LIBRARY_INSTALL_GUIDE.md # Library troubleshooting
│   ├── DATA_ANALYSIS.md        # Data analysis tools
│   └── libraries_needed.txt    # Library reference
│
├── scripts/                    # Helper scripts
│   ├── pio_quick_start.bat     # Windows PlatformIO menu
│   ├── pio_quick_start.sh      # Linux/Mac PlatformIO menu
│   ├── install_libraries.bat   # Windows Arduino library installer
│   └── install_libraries.sh    # Linux/Mac Arduino library installer
│
├── hardware/                   # Hardware design files
│   ├── diagram.json            # Wokwi circuit diagram
│   └── wokwi.toml              # Wokwi simulator config
│
├── test/                       # Unit tests
│   └── test_telemetry.cpp      # 15 unit tests for core logic
│
└── .vscode/                    # VS Code workspace config
    └── tasks.json              # Build/upload/test tasks
```

## 🚀 Quick Navigation

### I want to...

- **Build the hardware** → Start with [PARTS_LIST.md](PARTS_LIST.md), then [WIRING_GUIDE.md](WIRING_GUIDE.md)
- **Set up software quickly** → [QUICK_START.md](QUICK_START.md)
- **Use PlatformIO IDE** → [PLATFORMIO_GUIDE.md](PLATFORMIO_GUIDE.md)
- **Fix library errors** → [LIBRARY_INSTALL_GUIDE.md](LIBRARY_INSTALL_GUIDE.md)
- **Analyze my track data** → [DATA_ANALYSIS.md](DATA_ANALYSIS.md)
- **Run simulation** → [PLATFORMIO_GUIDE.md](PLATFORMIO_GUIDE.md#wokwi-simulator)

## 🎯 Recommended Reading Order

### For First-Time Users:
1. Main [README.md](../README.md) - Project overview and features
2. [PARTS_LIST.md](PARTS_LIST.md) - Order components
3. [WIRING_GUIDE.md](WIRING_GUIDE.md) - Assemble hardware
4. [QUICK_START.md](QUICK_START.md) - Upload and test firmware

### For Developers:
1. [PLATFORMIO_GUIDE.md](PLATFORMIO_GUIDE.md) - Set up development environment
2. [Unit Tests](../test/test_telemetry.cpp) - Review test cases
3. [Main Firmware](../MX5_Telemetry.ino) - Study code structure

### For Data Analysis:
1. [DATA_ANALYSIS.md](DATA_ANALYSIS.md) - Python visualization tools
2. CSV output format (see main [README.md](../README.md#data-format))

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
