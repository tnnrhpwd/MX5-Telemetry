# 🔌 Dual Arduino Setup Guide

This project supports **two separate Arduino configurations**:

1. **Master Arduino (nano_atmega328)** - Main telemetry logger with CAN, GPS, SD card
2. **Slave Arduino (led_slave)** - Dedicated LED controller receiving commands via Serial

## 📁 Project Structure

```
MX5-Telemetry/
├── platformio.ini           # Both environments configured here
├── src/                     # Master Arduino source code
│   └── main.cpp             # Main telemetry application
├── src_led_slave/           # Slave Arduino source code
│   └── main.cpp             # LED controller application
└── lib/                     # Shared libraries (only used by master)
```

## 🎯 Build Environments

### Master Arduino (Default)

**Environment name:** `nano_atmega328`

**Purpose:** Main telemetry system with full features:
- CAN bus communication (MCP2515)
- GPS logging (Neo-6M)
- SD card data logging
- USB command interface
- Sends LED commands to slave via TX pin

**Build command:**
```bash
platformio run -e nano_atmega328
```

**Upload command:**
```bash
platformio run -e nano_atmega328 --target upload
```

### Slave Arduino (LED Controller)

**Environment name:** `led_slave`

**Purpose:** Dedicated LED strip controller:
- Receives Serial commands on RX (Pin 0)
- Controls WS2812B LED strip (Pin D5)
- No CAN, GPS, or SD card dependencies
- Minimal memory footprint

**Build command:**
```bash
platformio run -e led_slave
```

**Upload command:**
```bash
platformio run -e led_slave --target upload --upload-port COM4
```

**Note:** Change `COM4` to your actual slave Arduino COM port.

## 🔧 Hardware Connections

### Master Arduino #1 (nano_atmega328)

```
Pin Assignments:
  D0  (RX) → USB Serial (computer communication)
  D1  (TX) → Arduino #2 RX (LED commands out)
  D2       → GPS Module TX
  D3       → GPS Module RX
  D4       → SD Card CS
  D10      → MCP2515 CS
  D11      → MOSI (shared SPI)
  D12      → MISO (shared SPI)
  D13      → SCK (shared SPI)
  
  5V/GND   → Power to all modules
```

**Note:** Master Arduino does **NOT** connect to LED strip directly.

### Slave Arduino #2 (led_slave)

```
Pin Assignments:
  D0  (RX) → Arduino #1 TX (receives commands)
  D5       → WS2812B LED Strip Data In
  
  5V/GND   → Shared ground with Arduino #1
```

**Note:** Slave Arduino **ONLY** connects to LED strip and master TX pin.

### Wiring Diagram

```
┌──────────────────┐
│   Arduino #1     │ Master (Telemetry Logger)
│  (Master)        │
│                  │
│  RX (D0) ◄───────┼──── USB to Computer
│  TX (D1) ────────┼──┐
│                  │  │
│  D2-D3  ◄────────┼──┼── GPS Module
│  D4     ─────────┼──┼── SD Card
│  D10-D13 ────────┼──┼── MCP2515 CAN
│                  │  │
│  5V/GND ─────────┼──┼── Power Bus
└──────────────────┘  │
                      │
                      │ Serial Commands (9600 baud)
                      │ Format: "RPM:3500\n"
                      │
                      ▼
┌──────────────────┐  │
│   Arduino #2     │  │
│  (Slave)         │  │
│                  │  │
│  RX (D0) ◄───────┼──┘
│  D5     ─────────┼──── WS2812B LED Strip
│                  │
│  5V/GND ─────────┼──── Shared Ground with Master
└──────────────────┘
```

## 📡 Serial Communication Protocol

### Commands (Master → Slave)

| Command | Format | Example | Description |
|---------|--------|---------|-------------|
| RPM | `RPM:xxxx\n` | `RPM:3500\n` | Update RPM display |
| Speed | `SPD:xxx\n` | `SPD:65\n` | Update speed (affects idle state) |
| Error | `ERR\n` | `ERR\n` | Show error animation |
| Clear | `CLR\n` | `CLR\n` | Clear all LEDs |
| Brightness | `BRT:xxx\n` | `BRT:128\n` | Set brightness (0-255) |

**Baud Rate:** 9600 (configured in slave's `SERIAL_BAUD`)

**Line Ending:** `\n` (newline)

### Implementation in Master

The master Arduino can send commands using the `LEDSlave` class:

```cpp
#include "LEDSlave.h"

LEDSlave ledStrip;  // Uses Serial for communication

void setup() {
    ledStrip.begin();
}

void loop() {
    // Send RPM to slave
    ledStrip.updateRPM(canBus.getRPM());
    
    // Send error state
    ledStrip.updateRPMError();
}
```

The `LEDSlave` class (in `lib/LEDSlave/`) handles Serial communication automatically.

## 🔨 Building & Uploading

### Option 1: PlatformIO CLI

**Build both environments:**
```bash
platformio run -e nano_atmega328
platformio run -e led_slave
```

**Upload to specific ports:**
```bash
# Upload master to COM3
platformio run -e nano_atmega328 --target upload --upload-port COM3

# Upload slave to COM4
platformio run -e led_slave --target upload --upload-port COM4
```

### Option 2: VS Code Tasks

Open Command Palette (`Ctrl+Shift+P`) and run:
- `Tasks: Run Task`
- Select `PlatformIO: Upload (nano_atmega328)` or `PlatformIO: Upload (led_slave)`

### Option 3: PlatformIO IDE

1. Open PlatformIO sidebar
2. Expand `Project Tasks`
3. Choose environment:
   - `nano_atmega328` → `General` → `Upload`
   - `led_slave` → `General` → `Upload`

## 🧪 Testing

### Test Master Arduino

1. Upload `nano_atmega328` environment
2. Open Serial Monitor at **115200 baud**
3. Type commands: `START`, `STATUS`, `HELP`
4. Check for CAN, GPS, SD initialization messages

### Test Slave Arduino

1. Upload `led_slave` environment
2. Open Serial Monitor at **9600 baud**
3. Manually send test commands:
   ```
   RPM:1000
   RPM:3000
   RPM:5000
   RPM:7000
   ERR
   CLR
   ```
4. Observe LED patterns changing

### Test Master → Slave Communication

1. Upload both Arduinos
2. Connect TX (Master D1) to RX (Slave D0)
3. Connect shared ground
4. Power on master Arduino
5. Start logging with `START` command
6. Rev engine and watch LED strip respond

**Troubleshooting:**
- If LEDs don't respond, check TX→RX wiring
- Verify both Arduinos share common ground
- Check baud rate is 9600 for slave Serial
- Monitor slave Serial output for debugging

## ⚙️ Configuration

### Master Configuration

Edit `lib/Config/config.h`:

```cpp
// Enable/disable features
#define ENABLE_LED_STRIP    0    // Set to 0 (using slave instead)
#define ENABLE_LED_SLAVE    1    // Set to 1 (using Serial to slave)
#define ENABLE_CAN_BUS      1
#define ENABLE_GPS          1
#define ENABLE_LOGGING      1
```

### Slave Configuration

Edit `src_slave/main.cpp`:

```cpp
#define LED_DATA_PIN        5       // D5 on Arduino #2
#define LED_COUNT           20      // Adjust to your strip length
#define SERIAL_BAUD         9600    // Match master TX baud rate

// Adjust RPM thresholds and colors
#define STATE_3_RPM_MIN         2501
#define STATE_3_RPM_MAX         4500
#define STATE_3_COLOR_R         255
#define STATE_3_COLOR_G         255
#define STATE_3_COLOR_B         0
```

## 📊 Memory Usage

### Master Arduino (nano_atmega328)

```
Sketch uses ~24,568 bytes (79%) of program storage
Global variables use ~1,124 bytes (54%) of dynamic memory
```

**Features:** CAN, GPS, SD, Serial commands, LED slave control

### Slave Arduino (led_slave)

```
Sketch uses ~8,420 bytes (27%) of program storage
Global variables use ~512 bytes (25%) of dynamic memory
```

**Features:** LED control, Serial command parsing

**Benefits of Separation:**
- Master has more memory for logging features
- Slave provides dedicated LED processing
- No interrupt conflicts between GPS SoftwareSerial and LED updates
- Cleaner USB communication on master

## 🎨 LED States

Both configurations use the same LED state logic:

| State | RPM Range | Visual | Description |
|-------|-----------|--------|-------------|
| 0 | Speed = 0 | ⚪ White pepper inward | Idle/Neutral |
| 1 | 2000-2500 | 🟢 Green edges | Gas efficiency zone |
| 2 | 750-1999 | 🟠 Orange pulse | Stall danger |
| 3 | 2501-4500 | 🟡 Yellow mirrored bar | Normal driving |
| 4 | 4501-7199 | 🔴 Red with flashing gap | Shift warning |
| 5 | 7200+ | 🔴 Solid red | Rev limit |
| Error | - | 🔴 Red pepper inward | CAN error |

See `docs/LED_STATE_SYSTEM.md` for detailed animation descriptions.

## 🔄 Migration from Single Arduino

If you previously used a single Arduino with local LED control:

1. **Backup your configuration** (note your LED_COUNT, pin assignments, RPM thresholds)

2. **Update config.h:**
   ```cpp
   #define ENABLE_LED_STRIP    0    // Disable local control
   #define ENABLE_LED_SLAVE    1    // Enable slave control
   ```

3. **Upload master firmware** to Arduino #1

4. **Configure slave:**
   - Copy your LED_COUNT to `src_led_slave/main.cpp`
   - Copy any custom RPM thresholds
   - Set LED_DATA_PIN to 5 (or your pin on slave)

5. **Upload slave firmware** to Arduino #2

6. **Wire connections:**
   - Move LED strip data wire from Master to Slave D5
   - Connect Master TX (D1) to Slave RX (D0)
   - Connect shared ground

## 🆘 Troubleshooting

### LEDs not responding to RPM changes

**Check:**
- [ ] Master TX (D1) connected to Slave RX (D0)
- [ ] Shared ground between both Arduinos
- [ ] `ENABLE_LED_SLAVE` set to 1 in master config
- [ ] Slave Serial baud rate is 9600
- [ ] Upload both firmwares successfully

**Debug:**
```cpp
// Add to master loop() to verify commands sent:
Serial.print("Sending RPM: ");
Serial.println(canBus.getRPM());
```

### Build errors for led_slave

**Common issues:**
- Missing Adafruit NeoPixel library → Install via Library Manager
- Wrong build environment → Use `-e led_slave` flag
- Source conflicts → Check `build_src_filter` in platformio.ini

### Upload to wrong Arduino

**Solution:**
Always specify upload port explicitly:
```bash
platformio run -e nano_atmega328 --target upload --upload-port COM3
platformio run -e led_slave --target upload --upload-port COM4
```

Use Windows Device Manager to identify which COM port is which Arduino.

## 📚 Related Documentation

- [LED State System](LED_STATE_SYSTEM.md) - Detailed LED animation descriptions
- [Quick Start Guide](QUICK_START.md) - Initial setup for both Arduinos
- [Wiring Guide](WIRING_GUIDE.md) - Complete hardware assembly
- [Master/Slave Architecture](../MASTER_SLAVE_ARCHITECTURE.md) - Design rationale

---

**Questions?** Open an issue on GitHub or check existing documentation in `docs/`.
