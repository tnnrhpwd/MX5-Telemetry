# 🚗 MX5-Telemetry System

A comprehensive embedded telemetry and data logging system for the 2008 Mazda Miata NC (MX-5). This system reads real-time engine data from the vehicle's CAN bus, provides visual RPM feedback via an LED strip, logs GPS-enhanced telemetry data, and automatically controls external camera recording.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Arduino](https://img.shields.io/badge/Arduino-Nano-00979D.svg)
![Platform](https://img.shields.io/badge/Platform-ATmega328P-orange.svg)

## ✨ Features

- **Real-time CAN Bus Communication**: Reads engine data at 500 kbaud directly from the Miata's OBD-II port
- **Visual RPM Indicator**: WS2812B LED strip displays RPM with color gradient and shift light
- **GPS Data Logging**: Records position, speed, altitude, and timestamps
- **CSV Data Export**: Logs all telemetry data to MicroSD card for easy analysis
- **Automatic GoPro Control**: Powers camera ON/OFF based on engine state
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
├── MX5_Telemetry.ino          # Main firmware (upload this)
├── platformio.ini              # PlatformIO configuration
├── README.md                   # This file
│
├── docs/                       # 📚 All documentation
│   ├── QUICK_START.md          # 30-min setup guide
│   ├── WIRING_GUIDE.md         # Hardware assembly
│   ├── PARTS_LIST.md           # Bill of materials
│   ├── PLATFORMIO_GUIDE.md     # Development setup
│   ├── LIBRARY_INSTALL_GUIDE.md # Library troubleshooting
│   └── DATA_ANALYSIS.md        # Data visualization
│
├── scripts/                    # 🔧 Helper scripts
│   ├── pio_quick_start.bat     # PlatformIO menu (Windows)
│   ├── pio_quick_start.sh      # PlatformIO menu (Linux/Mac)
│   ├── install_libraries.bat   # Arduino library installer
│   └── install_libraries.sh    # Arduino library installer
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
| Power MOSFET | IRF540N or similar | GPIO | Controls 5V GoPro power |
| Buck Converter | LM2596 | - | 12V automotive → 5V regulated |

### Wiring Connections

#### Arduino Nano Pin Assignments

```
Digital Pins:
  D2  → GPS Module TX (via SoftwareSerial RX)
  D3  → GPS Module RX (via SoftwareSerial TX)
  D4  → SD Card CS (Chip Select)
  D5  → MOSFET Gate (GoPro Power Control)
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
│                        Vehicle 12V System                            │
│                        (OBD-II Port Pin 16)                          │
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
         │   D2◄───┼────────────────────────┘ TX
         │   D3►───┼──────────────────────────► RX
         │   D4───►┼────► SD Card (CS)
         │   D5───►┼────► MOSFET Gate
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

    ┌──────────────────┐
    │  MOSFET Circuit  │
    │                  │
    │  D5 ──┬─[10kΩ]─┐│
    │       │         ││
    │     [Gate]      ││
    │       │         ││ IRF540N
    │    [Drain]◄─────┼┤ (or similar)
    │       │         ││
    │    [Source]     ││
    │       │         │└─► GoPro USB 5V+
    │      GND        │
    └──────────────────┘
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
6. **Route the GoPro power cable** through the MOSFET circuit

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
#define GOPRO_OFF_DELAY      10000 // GoPro shutdown delay (ms)

// Pin Configuration (if you need different pins)
#define CAN_CS_PIN      10
#define SD_CS_PIN       4
#define LED_DATA_PIN    6
#define GPS_RX_PIN      2
#define GPS_TX_PIN      3
#define GOPRO_PIN       5
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

3. **GoPro automatically powers ON** when engine starts (RPM > 0)
4. **Data logs continuously** to SD card in CSV format
5. **GoPro powers OFF** 10 seconds after engine stops

### LED Patterns

| Pattern | Meaning |
|---------|---------|
| Rainbow chase | System starting up |
| Green fill | Initialization successful |
| Red flash (3x) | Error detected |
| Gradient bar | Current RPM display |
| Fast red flash | Shift light active |
| All off | Vehicle off / standby mode |

### Data Retrieval

1. **Power off the vehicle**
2. **Remove the MicroSD card**
3. **Insert into computer**
4. **Open CSV file** in Excel, Google Sheets, or data analysis software

File naming format: `LOG_YYMMDD_HHMM.CSV` (based on GPS time) or `LOG_0.CSV` (counter-based)

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

#### ❌ GoPro Not Powering

**Symptoms**: GoPro doesn't turn on when engine starts

**Solutions**:
1. Check MOSFET gate connection to D5
2. Verify MOSFET can handle current (minimum 2A)
3. Ensure GoPro USB cable is connected through MOSFET drain
4. Test MOSFET with multimeter (should switch when D5 goes HIGH)
5. Check for proper ground connection

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

## 📚 Documentation

Complete documentation is available in the `docs/` folder:

- **[Quick Start Guide](docs/QUICK_START.md)** - Get up and running in 30 minutes
- **[Wiring Guide](docs/WIRING_GUIDE.md)** - Step-by-step hardware assembly
- **[Parts List](docs/PARTS_LIST.md)** - Complete bill of materials with prices
- **[PlatformIO Guide](docs/PLATFORMIO_GUIDE.md)** - Development environment setup and testing
- **[Library Install Guide](docs/LIBRARY_INSTALL_GUIDE.md)** - Troubleshooting library installation
- **[Data Analysis](docs/DATA_ANALYSIS.md)** - Python scripts for track data visualization

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
