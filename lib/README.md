# MX5-Telemetry Custom Libraries

This directory contains modular, reusable components for the MX5-Telemetry system.

## 🏎️ Current Architecture

The production system uses **three devices**:

| Device | Location | Role |
|--------|----------|------|
| **Raspberry Pi 4B** | Console/trunk | CAN hub, settings cache, HDMI to Pioneer head unit |
| **ESP32-S3 Round Display** | Stock oil gauge hole | Visual dashboard, BLE TPMS, G-force |
| **Arduino Nano** | Behind gauge cluster | Direct CAN→LED strip (<1ms latency) |

These libraries are primarily used by the **Arduino Nano** for LED control.

---

## 📦 Active Modules

### CANHandler
**Purpose**: CAN bus communication and vehicle data acquisition

**Used by**: Arduino Nano (direct HS-CAN at 500 kbaud)

**Features**:
- Dual-mode operation (direct CAN monitoring + OBD-II fallback)
- 100Hz high-frequency RPM polling
- Hardware interrupt on D2 for minimal latency
- Supports Mazda-specific CAN ID 0x201 (RPM) and 0x420 (Speed)
- Shares HS-CAN bus with Raspberry Pi (both can read simultaneously)

**Files**:
- `CANHandler/CANHandler.h` - Interface definition
- `CANHandler/CANHandler.cpp` - Implementation

**Key Methods**:
- `begin()` - Initialize CAN controller (MCP2515)
- `update()` - Read and parse CAN data (call at 100Hz)
- `getRPM()`, `getSpeed()`, `getThrottle()`, `getCoolantTemp()` - Data accessors

---

### LEDController
**Purpose**: Visual RPM feedback via WS2812B LED strip

**Used by**: Arduino Nano (around gauge cluster)

**Features**:
- 7-state LED system (see [LED_STATE_SYSTEM.md](../docs/features/LED_STATE_SYSTEM.md))
- Color gradient: Green → Yellow → Red based on RPM
- Shift light activation at configurable RPM threshold
- Settings received from Pi via serial (brightness, thresholds)
- <1ms CAN→LED update latency

**Files**:
- `LEDController/LEDController.h` - Interface definition
- `LEDController/LEDController.cpp` - Implementation

**Key Methods**:
- `begin()` - Initialize LED strip
- `updateRPM(rpm)` - Update display based on current RPM
- `startupAnimation()`, `errorAnimation()`, `readyAnimation()` - Visual feedback
- `clear()` - Turn off all LEDs
- `setRPM(rpm)` - Set RPM for simulator control

---

### CommandHandler
**Purpose**: Serial command processing from Pi or simulator

**Used by**: Arduino Nano (receives settings from Pi)

**Features**:
- Parses commands from Raspberry Pi via serial
- Handles `RPM:xxxx` commands from LED Simulator
- Updates LED controller settings in real-time

**Files**:
- `CommandHandler/CommandHandler.h` - Interface definition
- `CommandHandler/CommandHandler.cpp` - Implementation

**Key Methods**:
- `begin()` - Initialize command parser
- `process()` - Check for and handle incoming commands
- `setLEDController()` - Link to LED controller for RPM commands

---

### Config
**Purpose**: Centralized configuration constants

**Features**:
- Pin assignments (CAN, LED, etc.)
- RPM thresholds and timing constants
- Feature enable/disable flags

**Files**:
- `Config/config.h` - All configuration in one place

---

## 🗄️ Archived Modules

> **Note**: The following modules were part of the dual-arduino architecture and are no longer used in production. They remain in `archive/dual-arduino/` for reference.

| Module | Original Purpose | Replaced By |
|--------|-----------------|-------------|
| **GPSHandler** | GPS data acquisition (Neo-6M) | Pi handles GPS via USB dongle if needed |
| **DataLogger** | SD card CSV logging | Pi handles all data logging |
| **PowerManager** | GoPro power control | Pi manages accessory power |

---

## 🔧 Usage Example

```cpp
#include "CANHandler.h"
#include "LEDController.h"
#include "CommandHandler.h"

// Create instances
CANHandler canBus(CAN_CS_PIN);
LEDController ledStrip(LED_DATA_PIN, LED_COUNT);
CommandHandler cmdHandler;

void setup() {
    Serial.begin(115200);  // For Pi serial communication
    canBus.begin();
    ledStrip.begin();
    cmdHandler.setLEDController(&ledStrip);
}

void loop() {
    // Check for commands from Pi
    cmdHandler.process();
    
    // Update CAN data at 100Hz
    static unsigned long lastUpdate = 0;
    if (millis() - lastUpdate >= 10) {
        lastUpdate = millis();
        canBus.update();
    }
    
    // Update LED display
    ledStrip.updateRPM(canBus.getRPM());
}
```

## 🎯 Design Benefits

### Modularity
Each component is self-contained with clear interfaces, making the code easier to understand and maintain.

### Minimal Latency
Direct CAN→LED path achieves <1ms latency, 170x faster than the old serial-based dual-arduino setup.

### Testability
Use the LED Simulator (`tools/simulators/led_simulator/`) to test LED behavior without the car.

### Scalability
New features can be added as new modules without affecting existing code.

---

## 📁 File Organization

Each module follows the PlatformIO library structure:
```
lib/
├── CANHandler/
│   ├── CANHandler.h
│   └── CANHandler.cpp
├── LEDController/
│   ├── LEDController.h
│   └── LEDController.cpp
├── CommandHandler/
│   ├── CommandHandler.h
│   └── CommandHandler.cpp
├── Config/
│   └── config.h
└── README.md
```

## 🔍 Dependencies

### External Libraries (Arduino Nano)
- `mcp_can.h` - CAN bus communication (MCP2515)
- `Adafruit_NeoPixel.h` - WS2812B LED control
- `SPI.h` - SPI communication for CAN module

### Internal Dependencies
- All modules depend on `Config/config.h` for configuration constants

---

## 📝 Adding New Modules

To add a new custom module:

1. Create folder: `lib/NewModule/`
2. Create header: `lib/NewModule/NewModule.h`
3. Create implementation: `lib/NewModule/NewModule.cpp`
4. Include in `arduino/src/main.cpp`: `#include "NewModule.h"`
5. PlatformIO will automatically detect and compile it

---

## 🔗 Related Documentation

- [Single Arduino Wiring Guide](../docs/hardware/WIRING_GUIDE_SINGLE_ARDUINO.md)
- [LED State System](../docs/features/LED_STATE_SYSTEM.md)
- [LED Timing & Performance](../docs/features/LED_TIMING_AND_PERFORMANCE.md)
- [PI Display Integration](../docs/PI_DISPLAY_INTEGRATION.md)
