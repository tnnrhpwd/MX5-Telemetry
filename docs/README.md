# 📚 MX5-Telemetry Documentation

Complete documentation for the MX5-Telemetry system.

## 📖 Documentation Files

### Getting Started

- **[QUICK_START.md](QUICK_START.md)** - 30-minute setup guide for rapid deployment
- **[WIRING_GUIDE.md](WIRING_GUIDE.md)** - Step-by-step hardware assembly instructions
- **[PARTS_LIST.md](PARTS_LIST.md)** - Complete bill of materials with suppliers and pricing (~$80-140)

### Development & Installation

- **[PLATFORMIO_GUIDE.md](PLATFORMIO_GUIDE.md)** - Complete PlatformIO setup, testing, and simulation guide
- **[LIBRARY_INSTALL_GUIDE.md](LIBRARY_INSTALL_GUIDE.md)** - Arduino IDE library installation troubleshooting
- **[libraries_needed.txt](libraries_needed.txt)** - Quick reference list of required libraries

### LED System

- **[LED_STATE_SYSTEM.md](LED_STATE_SYSTEM.md)** - Complete documentation of mirrored progress bar LED states
- **[LED_QUICKREF.md](LED_QUICKREF.md)** - Quick reference for LED state modifications
- **[LED_AUTO_SYNC.md](LED_AUTO_SYNC.md)** - Automatic synchronization between Arduino and Python simulator

### Data & Analysis

- **[DATA_ANALYSIS.md](DATA_ANALYSIS.md)** - Python scripts for CSV data visualization and track analysis

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
