 the# 🚗 MX5-Telemetry System

A comprehensive embedded telemetry and data logging system for the 2008 Mazda Miata NC (MX-5). This system reads real-time engine data from the vehicle's CAN bus, provides visual RPM feedback via an LED strip, logs GPS-enhanced telemetry data, and automatically controls external camera recording.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Arduino](https://img.shields.io/badge/Arduino-Nano-00979D.svg)
![Platform](https://img.shields.io/badge/Platform-ATmega328P-orange.svg)

## ✨ Features

- **Real-time CAN Bus Communication**: Reads engine data at 500 kbaud directly from the Miata's OBD-II port
- **Visual RPM Indicator**: WS2812B LED strip displays RPM with color gradient and shift light
- **GPS Data Logging**: Records position, speed, altitude, and timestamps
- **CSV Data Export**: Logs all telemetry data to MicroSD card for easy analysis
- **Error Handling**: Graceful recovery from communication failures
- **Low-Power Standby**: Reduces power consumption when vehicle is off

## 📋 Table of Contents

- [Project Structure](#project-structure)
- [Hardware Requirements](#hardware-requirements)
- [Wiring Diagram](#wiring-diagram)
- [Software Dependencies](#software-dependencies)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Data Format](#data-format)
- [Troubleshooting](#troubleshooting)
- [Performance Notes](#performance-notes)
- [Documentation](#documentation)
- [License](#license)

## 📁 Project Structure

```
MX5-Telemetry/
├── platformio.ini              # PlatformIO configuration
├── README.md                   # This file
│
├── src/                        # 🎯 Main application code
│   ├── main.cpp                # Main application entry point
│   └── config.h                # Central configuration
│
├── lib/                        # 📦 Custom libraries (modular architecture)
│   ├── CANHandler/             # CAN bus communication
│   │   ├── CANHandler.h
│   │   └── CANHandler.cpp
│   ├── LEDController/          # LED strip visual feedback
│   │   ├── LEDController.h
│   │   └── LEDController.cpp
│   ├── GPSHandler/             # GPS data acquisition
│   │   ├── GPSHandler.h
│   │   └── GPSHandler.cpp
│   ├── DataLogger/             # SD card CSV logging
│   │   ├── DataLogger.h
│   │   └── DataLogger.cpp
│
├── docs/                       # 📚 All documentation
│   ├── QUICK_START.md          # 30-min setup guide
│   ├── WIRING_GUIDE.md         # Hardware assembly
│   ├── PARTS_LIST.md           # Bill of materials
│   ├── PLATFORMIO_GUIDE.md     # Development setup
│   ├── LIBRARY_INSTALL_GUIDE.md # Library troubleshooting
│   ├── DATA_ANALYSIS.md        # Data visualization
│   └── REQUIREMENTS_COMPLIANCE.md # ✅ Requirements verification
│
├── scripts/                    # 🔧 Helper scripts
│   ├── pio_quick_start.bat     # PlatformIO menu (Windows)
│   ├── pio_quick_start.sh      # PlatformIO menu (Linux/Mac)
│   ├── verify_build.bat        # Build verification (Windows)
│   ├── verify_build.sh         # Build verification (Linux/Mac)
│   ├── install_libraries.bat   # Arduino library installer
│   └── install_libraries.sh    # Arduino library installer
│
├── tools/                      # 🎮 Development tools
│   ├── led_simulator.py        # Interactive LED simulator (GUI)
│   ├── run_simulator.bat       # Simulator launcher (Windows)
│   └── README.md               # Tool documentation
│
├── hardware/                   # 🔌 Hardware files
│   ├── diagram.json            # Wokwi circuit diagram
│   └── wokwi.toml              # Simulator config
│
├── test/                       # ✅ Unit tests
│   └── test_telemetry.cpp      # 15 test cases
│
└── .vscode/                    # VS Code settings
    └── tasks.json              # Build/upload tasks
```

## 🔧 Hardware Requirements

### Core Components

| Component | Model/Type | Interface | Notes |
|-----------|------------|-----------|-------|
| Microcontroller | Arduino Nano V3.0 | - | ATmega328P, 16MHz, 5V logic |
| CAN Controller | MCP2515 + TJA1050 | SPI | 500 kbaud CAN transceiver |
| LED Strip | WS2812B | Single-wire | 30 LEDs recommended |
| GPS Module | Neo-6M | Software Serial | UART, 9600 baud |
| SD Card Module | MicroSD | SPI | Shares SPI bus with CAN |
| Buck Converter | LM2596 | - | 12V automotive → 5V regulated |

### Wiring Connections

#### Arduino Nano Pin Assignments

```
Digital Pins:
  D2  → GPS Module TX (via SoftwareSerial RX)
  D3  → GPS Module RX (via SoftwareSerial TX)
  D4  → SD Card CS (Chip Select)
  D6  → WS2812B Data In
  D10 → MCP2515 CS (Chip Select)
  D11 → MOSI (shared SPI)
  D12 → MISO (shared SPI)
  D13 → SCK (shared SPI)

Power:
  5V  → All module VCC pins (via buck converter)
  GND → Common ground (all modules + vehicle ground)
```

## 🔌 Wiring Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Vehicle 12V System                           │
│                        (OBD-II Port Pin 16)                         │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                        ┌────▼────┐
                        │ LM2596  │ Buck Converter (12V → 5V)
                        │  5V 3A  │
                        └────┬────┘
                             │ 5V Regulated
              ┌──────────────┼──────────────┐
              │              │              │
         ┌────▼────┐    ┌────▼────┐   ┌────▼────┐
         │ Arduino │    │ WS2812B │   │  Neo-6M │
         │  Nano   │    │ LED(30) │   │   GPS   │
         │         │    └─────────┘   └────┬────┘
         │   D2◄───┼───────────────────────┘ TX
         │   D3►───┼──────────────────────────► RX
         │   D4───►┼────► SD Card (CS)
         │   D6───►┼────► WS2812B Data
         │   D10──►┼────► MCP2515 (CS)
         │   D11──►┼────► MOSI (shared)
         │   D12◄──┼────► MISO (shared)
         │   D13──►┼────► SCK (shared)
         └────┬────┘
              │
         ┌────▼────┐          ┌──────────┐
         │ MCP2515 │          │   SD     │
         │ + TJA   ◄──────────┤  Card    │
         │  1050   │   SPI    │  Module  │
         └────┬────┘          └──────────┘
              │
    ┌─────────▼─────────┐
    │   OBD-II Port     │
    │  CAN-H (Pin 6)    │
    │  CAN-L (Pin 14)   │
    │  GND   (Pin 5)    │
    └───────────────────┘
```

## 📚 Software Dependencies

### Development Environment Options

**Option 1: Arduino IDE** (Traditional)
- Download: https://www.arduino.cc/en/software
- See [Library Installation](#library-installation-commands) below

**Option 2: PlatformIO** (Recommended for Advanced Users)
- VS Code extension with better tooling
- Automatic dependency management
- Built-in testing and simulation
- See `docs/PLATFORMIO_GUIDE.md` for complete setup
- Quick start: Run `scripts/pio_quick_start.bat` (Windows) or `scripts/pio_quick_start.sh` (Linux/Mac)

### Required Arduino Libraries

Install these libraries via Arduino IDE Library Manager or PlatformIO will auto-install:

```cpp
// Core Libraries (built-in)
#include <SPI.h>              // SPI communication

// Third-party Libraries (install via Library Manager)
#include <mcp_can.h>          // MCP2515 CAN Controller
                              // by Cory J. Fowler
                              
#include <SD.h>               // SD Card file operations
                              // (built-in)
                              
#include <Adafruit_NeoPixel.h> // WS2812B LED control
                               // by Adafruit
                               
#include <TinyGPS++.h>        // GPS NMEA sentence parser
                              // by Mikal Hart
                              
#include <SoftwareSerial.h>   // Software UART for GPS
                              // (built-in)
```

### Library Installation Commands

Via Arduino IDE:
1. Open Arduino IDE
2. Go to **Sketch** → **Include Library** → **Manage Libraries**
3. Search and install:
   - `MCP_CAN` by Cory J. Fowler
   - `Adafruit NeoPixel` by Adafruit
   - `TinyGPSPlus` by Mikal Hart

Via Command Line (using arduino-cli):
```bash
arduino-cli lib install "MCP_CAN"
arduino-cli lib install "Adafruit NeoPixel"
arduino-cli lib install "TinyGPSPlus"
```

## 🚀 Installation

### 1. Hardware Assembly

1. **Mount the Arduino Nano** in a protective enclosure
2. **Connect the buck converter** to vehicle 12V (fused recommended: 2A)
3. **Wire the MCP2515** to the OBD-II port:
   - CAN-H → Pin 6
   - CAN-L → Pin 14
   - GND → Pin 5
4. **Connect all modules** according to the wiring diagram above
5. **Mount the LED strip** in your desired location (dashboard, windshield, etc.)

### 2. Software Setup

1. **Clone this repository**:
   ```bash
   git clone https://github.com/tnnrhpwd/MX5-Telemetry.git
   cd MX5-Telemetry
   ```

2. **Open the sketch** in Arduino IDE:
   ```bash
   arduino MX5_Telemetry.ino
   ```

3. **Install required libraries** (see [Software Dependencies](#software-dependencies))

4. **Configure settings** (optional, see [Configuration](#configuration))

5. **Select board and port**:
   - Board: `Arduino Nano`
   - Processor: `ATmega328P`
   - Port: Select your COM port

6. **Upload the sketch** to your Arduino Nano

### 3. First-Time Setup

1. **Insert a formatted MicroSD card** (FAT32, 32GB max recommended)
2. **Connect to vehicle OBD-II port**
3. **Turn on vehicle ignition** (engine doesn't need to be running initially)
4. **Observe LED startup animation**:
   - Rainbow chase → System initializing
   - Green fill → System ready
   - Red flash → Error detected

5. **Monitor Serial output** (115200 baud) for diagnostic messages

## ⚙️ Configuration

### Adjustable Parameters

Edit these constants in `MX5_Telemetry.ino` to customize behavior:

```cpp
// LED Strip Configuration
#define LED_COUNT       30    // Number of LEDs in your strip

// RPM Thresholds (adjust for your engine)
#define RPM_IDLE        800   // Idle RPM
#define RPM_MIN_DISPLAY 1000  // Minimum RPM to show on LEDs
#define RPM_MAX_DISPLAY 7000  // Maximum RPM for gradient
#define RPM_SHIFT_LIGHT 6500  // RPM to activate shift light
#define RPM_REDLINE     7200  // Absolute redline

// Timing Configuration
#define CAN_READ_INTERVAL    20    // CAN polling rate (ms)
#define GPS_READ_INTERVAL    100   // GPS update rate (ms)
#define LOG_INTERVAL         200   // Data logging rate (ms)

// Pin Configuration (if you need different pins)
#define CAN_CS_PIN      10
#define SD_CS_PIN       4
#define LED_DATA_PIN    6
#define GPS_RX_PIN      2
#define GPS_TX_PIN      3
```

### CAN Bus Configuration

The system supports two methods of reading RPM:

1. **Direct CAN monitoring** (faster, preferred):
   - Listens for CAN ID `0x201` (Mazda-specific)
   - Parses RPM from raw CAN frames

2. **OBD-II PID requests** (fallback):
   - Requests PID `0x0C` (Engine RPM)
   - Standard OBD-II protocol

If your vehicle uses different CAN IDs, modify the `readCANData()` function.

## 📖 Usage

### Normal Operation

1. **Start your vehicle** - System automatically activates
2. **LED strip shows RPM** with color gradient:
   - 🟢 **Green** → Low RPM (1000-3000)
   - 🟡 **Yellow** → Mid RPM (3000-5000)
   - 🟠 **Orange** → High RPM (5000-6500)
   - 🔴 **Red Flash** → Shift light (6500+)

3. **Data logs continuously** to SD card in CSV format

### LED Patterns - Mirrored Progress Bar System

The LED strip uses a sophisticated mirrored progress bar that grows from both edges toward the center, with different states for various driving conditions:

#### ⚪ State 0: Idle/Neutral (Speed = 0)
**Visual:** White LEDs sequentially pepper **inward** from edges to center  
**Pattern:** `⚪ → ⚪ ⚪ → ⚪ ⚪ ⚪ → ... → full strip (hold 2s) → reset`  
**Purpose:** Indicates vehicle is stationary (neutral/clutch engaged)  
**Animation:** 150ms delay between LEDs, holds 2000ms at full brightness before repeating

#### 🟢 State 1: Gas Efficiency Zone (2000-2500 RPM)
**Visual:** Gentle green glow on outermost 2 LEDs per side  
**Pattern (16 LEDs):** `🟢 🟢 ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ 🟢 🟢`  
**Purpose:** Quiet confirmation of optimal cruising range

#### 🟠 State 2: Stall Danger (750-1999 RPM)
**Visual:** Orange bars pulse **outward** from center to edges  
**Pattern:** `⚫ ⚫ ⚫ 🟠 🟠 ⚫ ⚫ 🟠 🟠 ⚫ ⚫ ⚫ → 🟠 🟠 🟠 🟠 🟠 🟠 🟠 🟠 🟠 🟠 🟠 🟠`  
**Purpose:** Warn of potential engine stall (below torque range)  
**Animation:** 600ms pulse period, brightness 20-200

#### 🟡 State 3: Normal Driving / Power Band (2501-4500 RPM)
**Visual:** Solid yellow bars grow **inward** from edges toward center  
**Pattern (at ~4000 RPM):** `🟡 🟡 🟡 🟡 🟡 ⚫ ⚫ ⚫ ⚫ 🟡 🟡 🟡 🟡 🟡`  
**Purpose:** Mirrored progress bar showing current RPM percentage

#### 🔴 State 4: High RPM / Shift Danger (4501-7199 RPM)
**Visual:** Filled segments turn **solid red**, unfilled center gap **flashes violently**  
**Pattern (at ~6000 RPM):** `🟥 🟥 🟥 🟥 🟥 🟥 ✨ ✨ ✨ ✨ 🟥 🟥 🟥 🟥 🟥 🟥`  
*(✨ = rapid red/white/cyan flashing)*  
**Purpose:** Urgent shift signal - gauge nearly full, flash speed 150ms→40ms  
**Behavior:** Bar continues growing inward while gap flashes faster as RPM rises

#### 🛑 State 5: Rev Limit Cut (7200+ RPM)
**Visual:** Bars meet completely, entire strip **solid red**  
**Pattern (Full Strip):** `🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥`  
**Purpose:** Maximum limit reached (fuel cut), immediate action required

#### ❌ Error State: CAN Bus Read Error
**Visual:** Red LEDs sequentially pepper **inward** from edges to center  
**Pattern:** `🔴 → 🔴 🔴 → 🔴 🔴 🔴 → ... → center`  
**Purpose:** Indicates communication failure with vehicle CAN bus  
**Animation:** 80ms delay between LEDs, holds 300ms at center, brightness 200

---

**Startup Patterns:**
| Pattern | Meaning |
|---------|------|
| Rainbow chase | System starting up |
| Green fill | Initialization successful |
| Red flash (3x) | Error detected |

### Data Retrieval

You have **two options** for retrieving logged data:

#### Option A: Direct SD Card Access (Traditional)

1. **Power off the vehicle**
2. **Remove the MicroSD card**
3. **Insert into computer**
4. **Open CSV file** in Excel, Google Sheets, or data analysis software

#### Option B: USB Serial Data Dump (No Card Removal)

This method allows data retrieval without removing the SD card:

**Prerequisites:**
- USB-C extension cable accessible from cabin
- Terminal program (PuTTY, Tera Term, or Arduino Serial Monitor)

**Step-by-Step Procedure:**

1. **Park and Turn OFF**: Turn the key to OFF position
   - This isolates USB data lines for direct computer access
3. **Connect Laptop**: Plug laptop into USB-C extension port

4. **Choose Your Method**:

   **Method 1 - Built-in Commands (Main Firmware):**
   - Main firmware includes data dump commands
   - Open Serial Monitor at 115200 baud
   - Type commands:
     - `LIST` - Show all files on SD card
     - `DUMP` - Dump current log file
     - `DUMP filename` - Dump specific file (e.g., `DUMP LOG_251120_1430.CSV`)
     - `HELP` - Show available commands
   
   **Method 2 - Dedicated Dump Sketch (Most Reliable):**
   - Upload the standalone `examples/DataDump/DataDump.ino` sketch
   - Open Serial Monitor at 115200 baud
   - Use same commands as above
   - This sketch is optimized ONLY for data retrieval

5. **Capture Serial Data**:
   - **IMPORTANT**: Configure your terminal to LOG all incoming data to a file
   - **PuTTY**: Session → Logging → "All session output" → Select file
   - **Tera Term**: File → Log → Choose filename
   - **Arduino IDE**: Copy from Serial Monitor (not ideal for large files)
   
6. **Execute Dump**:
   - Start logging in terminal
   - Send `DUMP` command
   - Wait for "=== END FILE DUMP ===" message
   - Stop logging

7. **Convert to CSV**:
   - Rename captured `.txt` file to `.csv`
   - Open in Excel or data analysis software

8. **Finalize**:
   - Disconnect laptop
   - If you uploaded DataDump sketch, re-upload main firmware

**File Naming:** `LOG_YYMMDD_HHMM.CSV` (GPS-based) or `LOG_0.CSV` (counter-based)

## 📊 Data Format

### CSV Column Structure

```csv
Timestamp,Date,Time,Latitude,Longitude,Altitude,Satellites,RPM,Speed,Throttle,CoolantTemp
```

| Column | Description | Unit | Example |
|--------|-------------|------|---------|
| Timestamp | Milliseconds since startup | ms | 125430 |
| Date | GPS date | YYYYMMDD | 20251120 |
| Time | GPS time | HHMMSS | 143052 |
| Latitude | GPS latitude | decimal degrees | 34.052235 |
| Longitude | GPS longitude | decimal degrees | -118.243683 |
| Altitude | GPS altitude | meters | 125.4 |
| Satellites | Number of GPS satellites | count | 8 |
| RPM | Engine RPM | revolutions/min | 3450 |
| Speed | Vehicle speed | km/h | 65 |
| Throttle | Throttle position | percent | 45 |
| CoolantTemp | Coolant temperature | °C | 88 |

### Sample Data

```csv
Timestamp,Date,Time,Latitude,Longitude,Altitude,Satellites,RPM,Speed,Throttle,CoolantTemp
12543,20251120,143052,34.052235,-118.243683,125.4,8,850,0,0,88
12743,20251120,143052,34.052236,-118.243684,125.5,8,1200,5,15,88
12943,20251120,143053,34.052238,-118.243686,125.6,9,2500,25,35,89
```

## 🔧 Troubleshooting

### Common Issues

#### ❌ CAN Bus Not Responding

**Symptoms**: RPM stays at 0, Serial shows "CAN Bus initialization FAILED"

**Solutions**:
1. Check MCP2515 wiring (especially CS pin to D10)
2. Verify CAN-H and CAN-L are connected to correct OBD-II pins
3. Ensure 120Ω termination resistor is present (usually built into MCP2515 module)
4. Check vehicle is in ignition or running (CAN bus may be inactive when off)
5. Try a different CAN speed: `CAN_250KBPS` (some vehicles use 250 kbaud)

#### ❌ SD Card Not Detected

**Symptoms**: Serial shows "SD Card initialization FAILED"

**Solutions**:
1. Ensure SD card is formatted as FAT32
2. Check SD module wiring (CS pin to D4, shared SPI pins)
3. Try a different SD card (32GB or smaller, Class 10 recommended)
4. Verify 5V power supply is stable (low voltage can cause SD failures)

#### ❌ GPS Not Getting Fix

**Symptoms**: Latitude/Longitude empty in CSV, satellite count is 0

**Solutions**:
1. Place GPS module near window or outside (needs clear sky view)
2. Wait 2-5 minutes for initial GPS lock (cold start)
3. Check GPS module wiring (TX→D2, RX→D3, power)
4. Verify baud rate matches GPS module (9600 is standard)

#### ❌ LEDs Not Lighting

**Symptoms**: LED strip stays dark or shows random colors

**Solutions**:
1. Check WS2812B data pin connection (D6)
2. Ensure LED strip is powered from 5V supply (not Arduino pin)
3. Verify `LED_COUNT` matches your actual LED count
4. Add a 470Ω resistor between D6 and LED data line (reduces signal noise)
5. Add a 1000µF capacitor across LED power supply

### Debug Mode

Enable verbose Serial output by uncommenting debug lines:

```cpp
// In loop() function, add:
Serial.print("RPM: ");
Serial.print(currentRPM);
Serial.print(" | GPS Fix: ");
Serial.print(gpsValid);
Serial.print(" | Satellites: ");
Serial.println(satellites);
```

Monitor at **115200 baud** in Serial Monitor.

## ⚡ Performance Notes

### Timing Specifications

- **CAN Bus Read Rate**: 50Hz (every 20ms)
  - High-frequency polling for responsive LED display
  
- **GPS Update Rate**: 10Hz (every 100ms)
  - Standard GPS refresh rate
  
- **Data Logging Rate**: 5Hz (every 200ms)
  - Balances data density with SD card write speed
  
- **LED Refresh Rate**: ~50Hz (every 20ms)
  - Flicker-free visual feedback

### Memory Usage

Approximate flash and RAM usage on ATmega328P:

```
Sketch uses 24,568 bytes (79%) of program storage space
Global variables use 1,124 bytes (54%) of dynamic memory
```

**Note**: Tight on memory. Reduce `LED_COUNT` or optimize strings if running out of RAM.

### Power Consumption

Typical current draw at 5V:

- Arduino Nano: ~50mA
- MCP2515 module: ~30mA
- GPS module: ~40mA
- SD card (active): ~100mA
- WS2812B LEDs: ~60mA per LED at full brightness (30 LEDs = 1.8A max)

**Total system**: ~250mA (LEDs off) to 2.1A (all LEDs full brightness)

**Recommendation**: Use 3A or higher buck converter for reliable operation.

## 🎯 Advanced Customization

### Custom CAN IDs

If your vehicle broadcasts RPM on a different CAN ID, modify:

```cpp
// In readCANData() function:
if (rxId == 0xYOUR_CAN_ID && len >= 2) {
  uint16_t rawRPM = (rxBuf[0] << 8) | rxBuf[1];
  currentRPM = rawRPM / 4;  // Adjust divisor if needed
}
```

### LED Animation Customization

Modify `getRPMColor()` for different color schemes:

```cpp
// Example: Blue to Red gradient
uint32_t getRPMColor(int ledIndex, int totalLEDs) {
  float position = (float)ledIndex / (float)totalLEDs;
  uint8_t red = (uint8_t)(position * 255);
  uint8_t blue = (uint8_t)((1.0 - position) * 255);
  return strip.Color(red, 0, blue);
}
```

### Additional OBD-II PIDs

Add more PIDs to log additional data:

```cpp
// In readCANData(), add case statements:
case 0x05:  // Engine Coolant Temp
  coolantTemp = rxBuf[3] - 40;
  break;
case 0x0D:  // Vehicle Speed
  vehicleSpeed = rxBuf[3];
  break;
case 0x11:  // Throttle Position
  throttlePosition = (rxBuf[3] * 100) / 255;
  break;
```

## 🎮 LED Simulator Tool v2.0

Before uploading code to your Arduino, you can test LED logic changes using the interactive simulator!

### ✨ What's New in v2.0

- **🚗 Car Configuration Files** - Load custom vehicle specs from JSON files
- **🔑 Engine Start/Stop** - Toggle engine with button control
- **📂 Multiple Car Support** - Switch between different vehicles on the fly
- **📊 Realistic Physics** - Each car uses its own gear ratios and performance data

### Setup (First Time)

**Create Python virtual environment:**
```powershell
# In project root
py -m venv venv
```

This creates an isolated Python environment in the `venv/` folder (already excluded in `.gitignore`).

### Quick Start

**Windows (with virtual environment):**
```powershell
.\venv\Scripts\Activate.ps1
python tools\LED_Simulator\led_simulator_v2.1.py
```

**Windows (batch launcher):**
```batch
tools\LED_Simulator\run_simulator.bat
```

**All Platforms:**
```bash
python tools/LED_Simulator/led_simulator_v2.1.py
```

### Features

- 🎨 **Real-time LED visualization** - See your LED strip in action
- 🏎️ **Realistic physics** - Accurate transmission simulation per vehicle
- ⌨️ **Keyboard controls** - Gas, brake, clutch, shifting
- 📊 **Dual gauges** - RPM and speed displays
- ⚙️ **Gear indicator** - Current gear selection (N when engine off)
- 🔴 **Shift light testing** - Test your RPM thresholds
- 📁 **Custom car files** - Load any vehicle configuration from JSON

### Controls

- **START ENGINE Button**: Turn engine on/off
- **Load Car File Button**: Switch vehicle configurations
- ↑ **Up Arrow**: Gas pedal (increase RPM)
- ↓ **Down Arrow**: Brake (decrease RPM)
- → **Right Arrow**: Shift up
- ← **Left Arrow**: Shift down
- **Shift Key**: Clutch (hold while shifting)
- **ESC**: Quit

### Car Configuration Files

Create custom car profiles in `tools/cars/` directory:

**Included Cars:**
- `2008_miata_nc.json` - 2008 Mazda MX-5 NC (default)
- `example_sports_car.json` - Generic performance car

**Create Your Own:**
1. Copy an existing car file
2. Modify specs (gear ratios, RPM limits, top speed, etc.)
3. Load in simulator using "Load Car File" button

See `tools/cars/README.md` for complete file format documentation.

**Perfect for:**
- Testing LED color changes before upload
- Adjusting RPM thresholds visually
- Experimenting with shift light behavior
- Testing different vehicle configurations
- Demonstrating the system to others

See [tools/README.md](tools/README.md) for detailed usage and customization guide.

## 📚 Documentation

Complete documentation is available in the `docs/` folder:

- **[Quick Start Guide](docs/QUICK_START.md)** - Get up and running in 30 minutes
- **[Wiring Guide](docs/WIRING_GUIDE.md)** - Step-by-step hardware assembly
- **[Parts List](docs/PARTS_LIST.md)** - Complete bill of materials with prices
- **[PlatformIO Guide](docs/PLATFORMIO_GUIDE.md)** - Development environment setup and testing
- **[Library Install Guide](docs/LIBRARY_INSTALL_GUIDE.md)** - Troubleshooting library installation
- **[Data Analysis](docs/DATA_ANALYSIS.md)** - Python scripts for track data visualization
- **[Requirements Compliance](docs/REQUIREMENTS_COMPLIANCE.md)** - ✅ Verification of all project requirements

See [docs/README.md](docs/README.md) for a complete documentation index.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Mazda** for the excellent NC Miata platform
- **Arduino Community** for extensive libraries and support
- **Cory J. Fowler** for the MCP_CAN library
- **Adafruit** for the NeoPixel library
- **Mikal Hart** for the TinyGPS++ library

## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for:

- Bug fixes
- Performance improvements
- Additional features
- Documentation improvements
- Support for other vehicle models

## 📧 Support

For questions, issues, or suggestions:

- Open an issue on GitHub
- Check existing issues for solutions
- Review the [Troubleshooting](#troubleshooting) section

---

**⚠️ Disclaimer**: This system interfaces with your vehicle's CAN bus. Improper installation or use may affect vehicle operation. Install at your own risk. Always test thoroughly in a safe environment before track use.
Arduino-based OBD2 CAN Bus data logger and WS2812B RPM visualizer for the Miata NC.
