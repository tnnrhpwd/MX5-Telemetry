# 📚 MX5-Telemetry Documentation Index

Complete documentation for the MX5-Telemetry dual Arduino system, organized by category for easy navigation.

---

## 📖 Essential Documentation

### Repository Organization
- **[STRUCTURE.md](STRUCTURE.md)** - Complete repository structure guide and navigation
- **[PLATFORMIO_VERIFICATION.md](PLATFORMIO_VERIFICATION.md)** - PlatformIO dual Arduino setup verification
- **[REORGANIZATION_SUMMARY.md](REORGANIZATION_SUMMARY.md)** - Recent structural changes and migration guide

---

## 🚀 Getting Started

### Quick Setup (Start Here!)
1. **[QUICK_START.md](setup/QUICK_START.md)** - 30-minute rapid deployment guide
2. **[DUAL_ARDUINO_SETUP.md](setup/DUAL_ARDUINO_SETUP.md)** - Master/slave Arduino configuration
3. **[WIRING_GUIDE.md](hardware/WIRING_GUIDE.md)** - Hardware assembly instructions

### Setup Guides ([setup/](setup/))
- **[QUICK_REFERENCE.md](setup/QUICK_REFERENCE.md)** - Command reference card
- **[LIBRARY_INSTALL_GUIDE.md](setup/LIBRARY_INSTALL_GUIDE.md)** - Library installation troubleshooting
- **[OUTDOOR_TEST_QUICKSTART.md](setup/OUTDOOR_TEST_QUICKSTART.md)** - Field testing guide

---

## 🔧 Hardware

### Physical Assembly ([hardware/](hardware/))
- **[WIRING_GUIDE.md](hardware/WIRING_GUIDE.md)** - Step-by-step wiring instructions
- **[PARTS_LIST.md](hardware/PARTS_LIST.md)** - Bill of materials (~$80-140)
- **[MASTER_SLAVE_ARCHITECTURE.md](hardware/MASTER_SLAVE_ARCHITECTURE.md)** - Dual Arduino design rationale

---

## 💻 Development

### Build & Test ([development/](development/))
- **[PLATFORMIO_GUIDE.md](development/PLATFORMIO_GUIDE.md)** - PlatformIO setup and testing
- **[BUILD_GUIDE.md](development/BUILD_GUIDE.md)** - Building and uploading firmware
- **[BUILD_ARCHITECTURE.md](development/BUILD_ARCHITECTURE.md)** - Code architecture overview
- **[DATA_ANALYSIS.md](development/DATA_ANALYSIS.md)** - CSV data visualization tools
- **[REQUIREMENTS_COMPLIANCE.md](development/REQUIREMENTS_COMPLIANCE.md)** - Requirements verification
- **[CLEANUP_GUIDE.md](development/CLEANUP_GUIDE.md)** - Code cleanup history

---

## ✨ Features & Troubleshooting

### LED System ([features/](features/))
- **[LED_STATE_SYSTEM.md](features/LED_STATE_SYSTEM.md)** - Complete LED animation documentation
- **[LED_TIMING_AND_PERFORMANCE.md](features/LED_TIMING_AND_PERFORMANCE.md)** - ⚡ Update rate, latency, and performance tuning
- **[LED_QUICKREF.md](features/LED_QUICKREF.md)** - Quick reference for LED states
- **[LED_AUTO_SYNC.md](features/LED_AUTO_SYNC.md)** - Arduino/Python simulator sync
- **[LED_SIMULATOR_ARDUINO_CONNECTION.md](features/LED_SIMULATOR_ARDUINO_CONNECTION.md)** - Simulator integration
- **[LED_SIMULATOR_TROUBLESHOOTING.md](features/LED_SIMULATOR_TROUBLESHOOTING.md)** - Simulator debugging

### GPS System ([features/](features/))
- **[GPS_TROUBLESHOOTING.md](features/GPS_TROUBLESHOOTING.md)** - GPS fix issues
- **[STATUS_AND_GPS_EXPLAINED.md](features/STATUS_AND_GPS_EXPLAINED.md)** - GPS status indicators

### Data Logging ([features/](features/))
- **[COMPREHENSIVE_DATA_LOGGING.md](features/COMPREHENSIVE_DATA_LOGGING.md)** - Logging system details
- **[LOG_ROTATION_FEATURE.md](features/LOG_ROTATION_FEATURE.md)** - Log file management
- **[AUTO_START_FEATURE.md](features/AUTO_START_FEATURE.md)** - Automatic startup
- **[RUNAWAY_LOGGING_PREVENTION.md](features/RUNAWAY_LOGGING_PREVENTION.md)** - Safety features

---

## 📦 Archive

Historical documentation (for reference only):

- **[archive/](archive/)** - Legacy documentation including changelogs, bug fix summaries, and historical notes
  - `CHANGELOG_V3.md` - Version 3 changelog
  - `UPDATE_SUMMARY.md` - Update history
  - `HANG_FIX_SUMMARY.md`, `TIMEOUT_FIX_SUMMARY.md` - Historical bug fixes
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
