# 📁 Repository Structure Guide

This document explains the organization of the MX5-Telemetry repository, which has been structured to clearly separate the **dual Arduino architecture** (Master/Slave) and organize documentation, tools, and build automation.

## 🏗️ High-Level Structure

```
MX5-Telemetry/
├── src/                        # 🎯 Master Arduino source code
├── src_slave/                  # 🎯 Slave Arduino source code
├── lib/                        # 📦 Master Arduino libraries
├── test/                       # ✅ Unit tests
│
├── docs/                       # 📚 Documentation (organized by category)
│   ├── setup/                  # Quick start and installation guides
│   ├── hardware/               # Wiring, parts, architecture
│   ├── development/            # Build, PlatformIO, testing guides
│   └── features/               # Feature-specific documentation
│
├── tools/                      # 🛠️ Development tools
│   ├── simulators/             # LED simulator and testing tools
│   └── utilities/              # Arduino helper scripts
│
├── build-automation/           # 🔧 Build scripts and automation
├── hardware/                   # 🔌 Wokwi simulation files
│
├── platformio.ini              # PlatformIO configuration
└── README.md                   # Main project documentation
```

> **Note:** This file is located at `docs/STRUCTURE.md`

---

## 🎯 Source Code Organization

### Master Arduino (`src/`)

**Purpose:** Main telemetry logger with full sensor suite

**Location:** `src/`

**Contains:**
- `main.cpp` - Main application entry point
- Master-specific initialization and control logic

**Dependencies in `lib/`:**
- `CANHandler/` - CAN bus communication (MCP2515)
- `GPSHandler/` - GPS data acquisition (Neo-6M)
- `DataLogger/` - SD card CSV logging
- `CommandHandler/` - USB serial command interface
- `LEDSlave/` - Serial communication with slave Arduino
- `Config/` - Shared configuration constants

**PlatformIO Environment:** `nano_atmega328`

**Upload Command:**
```bash
platformio run -e nano_atmega328 --target upload --upload-port COM3
```

---

### Slave Arduino (`src_slave/`)

**Purpose:** Dedicated LED strip controller

**Location:** `src_slave/`

**Contains:**
- `main.cpp` - LED controller application
- Serial command parsing
- WS2812B LED control logic

**Dependencies:**
- Only `Adafruit NeoPixel` library (no custom libs)

**PlatformIO Environment:** `led_slave`

**Upload Command:**
```bash
platformio run -e led_slave --target upload --upload-port COM4
```

---

### Shared Libraries (`lib/`)

**Location:** `lib/`

**Used by:** Master Arduino only

**Structure:**
```
lib/
├── CANHandler/         # CAN bus communication
│   ├── CANHandler.h
│   └── CANHandler.cpp
├── GPSHandler/         # GPS module interface
│   ├── GPSHandler.h
│   └── GPSHandler.cpp
├── DataLogger/         # SD card logging
│   ├── DataLogger.h
│   └── DataLogger.cpp
├── CommandHandler/     # USB command interface
│   ├── CommandHandler.h
│   └── CommandHandler.cpp
├── LEDSlave/          # Master→Slave Serial protocol
│   ├── LEDSlave.h
│   └── LEDSlave.cpp
├── LEDController/     # (Legacy) Local LED control
│   ├── LEDController.h
│   └── LEDController.cpp
└── Config/            # Global configuration
    ├── config.h
    └── LEDStates.h
```

**Note:** Slave Arduino ignores all custom libraries via `lib_ignore` in `platformio.ini`.

---

## 📚 Documentation Organization

Documentation has been reorganized into **four main categories** for easier navigation:

### 1. Setup Guides (`docs/setup/`)

**For:** First-time users and quick setup

**Files:**
- `QUICK_START.md` - 30-minute setup guide
- `QUICK_REFERENCE.md` - Command reference
- `DUAL_ARDUINO_SETUP.md` - Complete dual Arduino configuration
- `LIBRARY_INSTALL_GUIDE.md` - Troubleshooting library installation
- `OUTDOOR_TEST_QUICKSTART.md` - Field testing guide

### 2. Hardware Documentation (`docs/hardware/`)

**For:** Physical assembly and wiring

**Files:**
- `WIRING_GUIDE.md` - Complete wiring instructions
- `PARTS_LIST.md` - Bill of materials with links
- `MASTER_SLAVE_ARCHITECTURE.md` - Dual Arduino design rationale

### 3. Development Guides (`docs/development/`)

**For:** Developers and advanced users

**Files:**
- `PLATFORMIO_GUIDE.md` - Development environment setup
- `BUILD_GUIDE.md` - Build system documentation
- `BUILD_ARCHITECTURE.md` - Code architecture overview
- `DATA_ANALYSIS.md` - Data visualization and analysis
- `REQUIREMENTS_COMPLIANCE.md` - Requirements verification
- `CLEANUP_GUIDE.md` - Code cleanup history

### 4. Feature Documentation (`docs/features/`)

**For:** Understanding specific system features

**Files:**
- `LED_STATE_SYSTEM.md` - LED animation details
- `LED_QUICKREF.md` - LED pattern reference
- `LED_AUTO_SYNC.md` - LED synchronization feature
- `LED_SIMULATOR_ARDUINO_CONNECTION.md` - Simulator integration
- `LED_SIMULATOR_TROUBLESHOOTING.md` - Simulator debugging
- `GPS_TROUBLESHOOTING.md` - GPS fix issues
- `STATUS_AND_GPS_EXPLAINED.md` - GPS status indicators
- `COMPREHENSIVE_DATA_LOGGING.md` - Logging system details
- `LOG_ROTATION_FEATURE.md` - Log file management
- `AUTO_START_FEATURE.md` - Automatic startup behavior
- `RUNAWAY_LOGGING_PREVENTION.md` - Safety features

### Repository Documentation (`docs/`)

**Core Documentation:**
- `README.md` - Documentation index
- `STRUCTURE.md` - This file (repository organization guide)
- `PLATFORMIO_VERIFICATION.md` - PlatformIO dual Arduino verification
- `REORGANIZATION_SUMMARY.md` - Recent structural changes
- `libraries_needed.txt` - Library reference list

**Archive (`docs/archive/`):**
Historical documentation preserved for reference:
- `CHANGELOG_V3.md` - Version 3 changelog
- `UPDATE_SUMMARY.md` - Update history
- `HANG_FIX_SUMMARY.md`, `TIMEOUT_FIX_SUMMARY.md` - Historical bug fixes
- `THREE_STATE_SUMMARY.md` - Historical feature summary
- `PROJECT_INTEGRATION_SUMMARY.md` - Integration notes

---

## 🛠️ Tools Organization

### Simulators (`tools/simulators/`)

**LED Simulator** - `tools/simulators/led_simulator/`

Interactive GUI for testing LED patterns before Arduino upload.

**Contents:**
- `led_simulator_v2.1.py` - Latest simulator version
- `README.md` - Simulator documentation
- `SIMULATOR_QUICKREF.md` - Quick reference
- `TEST_GUIDE_V2.1.md` - Testing guide
- `RELEASE_NOTES_V2.1.md` - Release notes
- `UPGRADE_V2_SUMMARY.md` - Upgrade guide
- `cars/` - Vehicle configuration files
  - `2008_miata_nc.json` - Default Miata NC config
  - Additional car profiles

**Run Command (Windows):**
```powershell
.\venv\Scripts\Activate.ps1
python tools\simulators\led_simulator\led_simulator_v2.1.py
```

### Utilities (`tools/utilities/`)

**Arduino Actions** - `tools/utilities/arduino_actions/`

Command-line utility for Arduino management tasks.

**Contents:**
- `arduino_actions.py` - Main utility script
- `Arduino_Actions.bat` - Windows launcher
- `README.md` - Usage documentation

---

## 🔧 Build Automation (`build-automation/`)

**Purpose:** Automated build scripts and installers

**Location:** `build-automation/`

**Contents:**
- `install_libraries.bat` - Windows library installer
- `install_libraries.sh` - Linux/Mac library installer
- `pio_quick_start.bat` - PlatformIO quick menu (Windows)
- `pio_quick_start.sh` - PlatformIO quick menu (Linux/Mac)
- `verify_build.bat` - Build verification (Windows)
- `verify_build.sh` - Build verification (Linux/Mac)

**Usage Examples:**

```bash
# Install all required Arduino libraries
./build-automation/install_libraries.sh

# Quick PlatformIO menu
./build-automation/pio_quick_start.sh

# Verify build without upload
./build-automation/verify_build.sh
```

---

## 🔌 Hardware Simulation (`hardware/`)

**Purpose:** Wokwi virtual hardware simulation

**Location:** `hardware/`

**Contents:**
- `diagram.json` - Virtual circuit diagram
- `wokwi.toml` - Simulator configuration

**PlatformIO Environment:** `wokwi_sim`

**Run Command:**
```bash
platformio run -e wokwi_sim
```

---

## ✅ Testing (`test/`)

**Purpose:** Unit tests for core functionality

**Location:** `test/`

**Contents:**
- `test_telemetry.cpp` - 15 test cases for telemetry system

**PlatformIO Environment:** `native_sim`

**Run Command:**
```bash
platformio test -e native_sim -v
```

---

## 🚀 Quick Reference: Common Tasks

### Building & Uploading

```bash
# Build master Arduino
platformio run -e nano_atmega328

# Upload master Arduino (specify port)
platformio run -e nano_atmega328 --target upload --upload-port COM3

# Build slave Arduino
platformio run -e led_slave

# Upload slave Arduino (specify port)
platformio run -e led_slave --target upload --upload-port COM4

# Build both
platformio run -e nano_atmega328 -e led_slave
```

### Testing & Debugging

```bash
# Run unit tests
platformio test -e native_sim -v

# Build with debug symbols
platformio run -e nano_debug

# Monitor serial output (master)
platformio device monitor --baud 115200

# Monitor serial output (slave)
platformio device monitor --baud 9600 --port COM4
```

### Tools & Simulation

```bash
# Run LED simulator (Windows)
.\venv\Scripts\Activate.ps1
python tools\simulators\led_simulator\led_simulator_v2.1.py

# Run LED simulator (Linux/Mac)
source venv/bin/activate
python tools/simulators/led_simulator/led_simulator_v2.1.py

# Run Wokwi simulation
platformio run -e wokwi_sim
```

---

## 📋 VS Code Tasks

The following tasks are configured in `.vscode/tasks.json`:

| Task | Command | Description |
|------|---------|-------------|
| **PlatformIO: Build** | `pio run` | Build master Arduino |
| **PlatformIO: Upload** | `pio run --target upload` | Upload master Arduino |
| **PlatformIO: Build Wokwi Sim** | `pio run -e wokwi_sim` | Build simulator |
| **PlatformIO: Test (Unit Tests)** | `pio test -e native_sim -v` | Run unit tests |
| **PlatformIO: Clean** | `pio run --target clean` | Clean build files |
| **PlatformIO: Serial Monitor** | `pio device monitor` | Open serial monitor |
| **Start RPM LED Simulator** | `python tools\simulators\led_simulator\led_simulator_v2.1.py` | Run LED GUI |
| **Activate Python Environment** | `.\venv\Scripts\Activate.ps1` | Activate venv |

**Access:** `Ctrl+Shift+P` → `Tasks: Run Task`

---

## 🔄 Migration Notes

### From Old Structure

If you have old documentation or script references, here are the path mappings:

| Old Path | New Path |
|----------|----------|
| `src/` | `src/` (unchanged - master) |
| `src_led_slave/` | `src_slave/` |
| `lib/` | `lib/` (unchanged - master only) |
| `scripts/` | `build-automation/` |
| `tools/LED_Simulator/` | `tools/simulators/led_simulator/` |
| `tools/Arduino_Actions/` | `tools/utilities/arduino_actions/` |
| `docs/*.md` | Organized into subdirectories |

### Updating References

If you have scripts or documentation that reference old paths:

1. **Replace script paths:**
   ```bash
   scripts/install_libraries.sh → build-automation/install_libraries.sh
   ```

2. **Replace doc paths:**
   ```bash
   docs/QUICK_START.md → docs/setup/QUICK_START.md
   ```

3. **Replace tool paths:**
   ```bash
   tools/LED_Simulator/ → tools/simulators/led_simulator/
   ```

---

## 📝 Contributing

When contributing to this project, please maintain the directory structure:

### Adding New Features

- **Master firmware code:** Add to `src/` or `lib/`
- **Slave firmware code:** Add to `src_slave/`
- **Documentation:** 
  - Setup guides → `docs/setup/`
  - Hardware docs → `docs/hardware/`
  - Dev guides → `docs/development/`
  - Feature docs → `docs/features/`
- **Tools:** Add to appropriate `tools/` subdirectory
- **Build scripts:** Add to `build-automation/`

### File Naming Conventions

- **Source files:** `snake_case.cpp`, `snake_case.h`
- **Documentation:** `SCREAMING_SNAKE_CASE.md`
- **Scripts:** `snake_case.sh`, `snake_case.bat`
- **Config files:** `lowercase.ini`, `lowercase.json`

---

## 🆘 Need Help?

- **Can't find a file?** Check this guide's path mappings
- **Build errors?** See `docs/development/PLATFORMIO_GUIDE.md`
- **Wiring questions?** See `docs/hardware/WIRING_GUIDE.md`
- **Feature documentation?** See `docs/features/` directory
- **Quick setup?** See `docs/setup/QUICK_START.md`

---

**Last Updated:** November 26, 2025  
**Structure Version:** 2.0 (Dual Arduino Architecture)
