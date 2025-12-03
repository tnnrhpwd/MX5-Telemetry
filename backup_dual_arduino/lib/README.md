# MX5-Telemetry Custom Libraries

This directory contains modular, reusable components for the MX5-Telemetry system.

## 📦 Module Overview

### CANHandler
**Purpose**: CAN bus communication and vehicle data acquisition

**Features**:
- Dual-mode operation (direct CAN monitoring + OBD-II fallback)
- 50Hz high-frequency RPM polling
- Automatic error recovery
- Supports Mazda-specific CAN ID 0x201 and standard OBD-II PIDs

**Files**:
- `CANHandler.h` - Interface definition
- `CANHandler.cpp` - Implementation

**Key Methods**:
- `begin()` - Initialize CAN controller
- `update()` - Read and parse CAN data (call at 50Hz)
- `getRPM()`, `getSpeed()`, `getThrottle()`, `getCoolantTemp()` - Data accessors

---

### LEDController
**Purpose**: Visual RPM feedback via WS2812B LED strip

**Features**:
- Color gradient: Green → Yellow → Red based on RPM
- Shift light activation at configurable RPM threshold
- Smooth transitions and animations
- Startup, error, and ready animations

**Files**:
- `LEDController.h` - Interface definition
- `LEDController.cpp` - Implementation

**Key Methods**:
- `begin()` - Initialize LED strip
- `updateRPM(rpm)` - Update display based on current RPM
- `startupAnimation()`, `errorAnimation()`, `readyAnimation()` - Visual feedback
- `clear()` - Turn off all LEDs

---

### GPSHandler
**Purpose**: GPS data acquisition and parsing

**Features**:
- Neo-6M GPS module support
- 10Hz update rate
- TinyGPS++ NMEA sentence parsing
- Position, altitude, time, and satellite data

**Files**:
- `GPSHandler.h` - Interface definition
- `GPSHandler.cpp` - Implementation

**Key Methods**:
- `begin()` - Initialize GPS serial
- `update()` - Feed GPS data to parser (call frequently)
- `getLatitude()`, `getLongitude()`, `getAltitude()`, `getSatellites()` - Data accessors
- `isValid()` - Check if GPS has a fix

---

### DataLogger
**Purpose**: SD card CSV data logging

**Features**:
- Unique timestamped filenames (LOG_YYMMDD_HHMM.CSV)
- CSV format with 11 columns
- 5Hz logging rate
- Automatic error recovery with SD card reinitialization
- Proper file closing for data integrity

**Files**:
- `DataLogger.h` - Interface definition
- `DataLogger.cpp` - Implementation

**Key Methods**:
- `begin()` - Initialize SD card
- `createLogFile(date, time)` - Create new log file with unique name
- `logData(...)` - Write CSV row with all telemetry data

---

### PowerManager
**Purpose**: GoPro power control and system standby management

**Features**:
- MOSFET-controlled GoPro USB power switching
- Automatic ON when RPM > 0
- 10-second delay before OFF when RPM = 0
- Low-power standby mode detection
- LED strip auto-off in standby

**Files**:
- `PowerManager.h` - Interface definition
- `PowerManager.cpp` - Implementation

**Key Methods**:
- `begin()` - Initialize power control GPIO
- `update(rpm)` - Update power state based on RPM
- `checkStandbyMode(rpm, goProOn)` - Detect and enter standby
- `isGoProOn()`, `isInStandbyMode()` - Status accessors

---

## 🔧 Usage Example

```cpp
#include "CANHandler.h"
#include "LEDController.h"

// Create instances
CANHandler canBus(CAN_CS_PIN);
LEDController ledStrip(LED_DATA_PIN, LED_COUNT);

void setup() {
    canBus.begin();
    ledStrip.begin();
}

void loop() {
    // Update CAN data at 50Hz
    static unsigned long lastUpdate = 0;
    if (millis() - lastUpdate >= 20) {
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

### Reusability
Components can be used independently or combined as needed. Easy to adapt for similar projects.

### Testability
Individual modules can be tested in isolation with mock hardware or simulators.

### Scalability
New features can be added as new modules without affecting existing code.

### Memory Efficiency
No global variables polluting the namespace. Clear ownership and lifetime management.

## 📁 File Organization

Each module follows the PlatformIO library structure:
```
lib/
└── ModuleName/
    ├── ModuleName.h    # Interface (public API)
    └── ModuleName.cpp  # Implementation (private logic)
```

## 🔍 Dependencies

### External Libraries
- `mcp_can.h` - CAN bus communication (CANHandler)
- `Adafruit_NeoPixel.h` - LED control (LEDController)
- `TinyGPS++.h` - GPS parsing (GPSHandler)
- `SD.h` - SD card operations (DataLogger)
- `SPI.h` - SPI communication (CANHandler, DataLogger)
- `SoftwareSerial.h` - GPS serial (GPSHandler)

### Internal Dependencies
- All modules depend on `src/config.h` for configuration constants
- DataLogger depends on GPSHandler for timestamp data

## 📝 Adding New Modules

To add a new custom module:

1. Create folder: `lib/NewModule/`
2. Create header: `lib/NewModule/NewModule.h`
3. Create implementation: `lib/NewModule/NewModule.cpp`
4. Include in `src/main.cpp`: `#include "NewModule.h"`
5. PlatformIO will automatically detect and compile it

## 🚀 Performance Notes

- **CANHandler**: Optimized for 50Hz polling (20ms intervals)
- **LEDController**: Fast pixel updates with minimal flicker
- **GPSHandler**: Efficient NMEA parsing with TinyGPS++
- **DataLogger**: Buffered writes, file properly closed after each log
- **PowerManager**: Lightweight state machine with minimal overhead

---

**Note**: All modules use Arduino's built-in `millis()` for timing to avoid blocking operations.
