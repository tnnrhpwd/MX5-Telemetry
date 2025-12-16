# MX5 Telemetry - Next Session To-Do List

**Date Created:** December 1, 2025  
**Last Updated:** December 16, 2025  
**Status:** ✅ Pi + Arduino + ESP32-S3 architecture complete!

---

## 🎯 Current Architecture

| Device | Purpose | Status |
|--------|---------|--------|
| **Raspberry Pi 4B** | CAN hub + HDMI display | ✅ Implemented |
| **ESP32-S3 Round Display** | Gauge display + BLE TPMS | ✅ Implemented |
| **Arduino Nano** | Direct CAN → LED strip | ✅ Implemented |

See [PI_DISPLAY_INTEGRATION.md](PI_DISPLAY_INTEGRATION.md) for full architecture.

---

## 🎉 COMPLETED - December 16, 2025: Documentation Cleanup

### What Was Done

1. **Archived Dual-Arduino Documentation**
   - Moved to `archive/dual-arduino/docs/`:
     - `MASTER_SLAVE_ARCHITECTURE.md`
     - `WIRING_GUIDE_DUAL_ARDUINO.md`
     - `DUAL_ARDUINO_SETUP.md`
     - `GPS_TROUBLESHOOTING.md`
     - `COMPREHENSIVE_DATA_LOGGING.md`
     - `LOG_ROTATION_FEATURE.md`
     - `AUTO_START_FEATURE.md`

2. **Updated Documentation**
   - `docs/README.md` - Reflects Pi + ESP32 + Arduino architecture
   - `README.md` - Updated project overview
   - `docs/BUILD_AND_UPLOAD.md` - Updated for current build targets
   - `docs/hardware/PARTS_LIST.md` - Added Pi, ESP32, TPMS components
   - `archive/dual-arduino/README.md` - Updated archive description

---

## 🎉 COMPLETED - December 3, 2025: Single Arduino Setup

### What Was Done

1. **Created Single Arduino Optimized Build** (`arduino/`)
   - Direct CAN→LED path with <1ms latency
   - 100Hz LED update rate
   - Hardware interrupt on D2 for CAN messages
   - No serial communication = no data corruption

2. **Created ESP32-S3 Display** (`display/`)
   - 360x360 round LCD with modern UI
   - 8 screens: Overview, RPM, TPMS, Engine, G-Force, Diagnostics, System, Settings
   - BLE TPMS scanner for tire pressure sensors
   - QMI8658 IMU for G-force display

3. **Created Raspberry Pi UI** (`pi/ui/src/`)
   - Python/Pygame application
   - Dual CAN bus reading (HS + MS)
   - Serial communication with ESP32-S3
   - HDMI output to Pioneer head unit

---

## 📋 Remaining Tasks

### Hardware
- [ ] Test Pi with actual MCP2515 modules in car
- [ ] Verify BLE TPMS sensor pairing
- [ ] Mount ESP32-S3 round display in dash
- [ ] Run shielded cable from Pi to ESP32

### Software
- [ ] Fine-tune Pi CAN bus timing
- [ ] Add data logging to Pi (SD card or USB)
- [ ] Implement lap timer on RPM/Speed screen
- [ ] Add TPMS low-pressure alerts with audio

### Testing
- [ ] Full car test with all components
- [ ] Verify steering wheel button mapping
- [ ] Test G-force calibration during driving

### ✅ COMPLETED - Single Arduino code

- [x] Combined CAN reading and LED control in one loop
- [x] Removed serial communication code
- [x] Inline functions for speed
- [x] Integer-only math (no floats)
- [x] Direct port manipulation macros

### Code Cleanup
- [ ] Remove unused features and dead code
- [ ] Simplify LED state machine (too many states currently)
- [ ] Remove or disable features not needed for core RPM display:
  - [ ] Stall warning animation
  - [ ] Idle breathing animation  
  - [ ] Complex efficiency gradient (simplify to basic RPM bar?)
  - [ ] Pepper animation
  - [ ] Haptic feedback code

### Streamlined Mode
- [ ] Create a "SIMPLE_MODE" compile flag
- [ ] Simple mode: RPM in → LED bar out (minimal processing)
- [ ] Keep advanced features available but optional

### Serial Protocol Simplification
- [ ] Reduce Master→Slave message to just: `R<rpm>\n`
- [ ] Remove acknowledgments and status messages during operation
- [ ] Consider binary protocol for speed (2 bytes for RPM vs 6+ chars)

---

## 🗑️ Priority 4: Feature Removal Candidates

### Consider Removing/Disabling
- [ ] **SD Card Logging** - Major source of delays
  - Blocking writes can take 10-100ms+
  - Not needed for real-time RPM display
  - Can add back later as optional feature
  
- [ ] **GPS Logging** - Adds complexity, not needed for RPM LEDs
  - GPS parsing takes time each loop
  - SoftwareSerial can interfere with timing
  
- [ ] **Comprehensive Data Logging** - Overkill for RPM display
  
- [ ] **Log Rotation** - Only needed if keeping SD logging

- [ ] **Status LED states** - Simplify to just: Running / Error

### Keep These Features
- [ ] CAN Bus reading (core functionality)
- [ ] RPM to LED mapping (core functionality)
- [ ] Potentiometer brightness control (hardware feature, minimal overhead)
- [ ] Basic startup animation (good UX, runs once)

---

## 📊 Priority 5: Performance Optimizations

### Timing Analysis
- [ ] Add performance profiling code to measure loop time
- [ ] Target: LED update within 50ms of CAN message (20Hz minimum)
- [ ] Ideal: LED update within 16ms (60Hz, smooth animation)

### Code Optimizations
- [ ] Use `FastLED` library instead of Adafruit NeoPixel? (reportedly faster)
- [ ] Pre-calculate LED colors in lookup table
- [ ] Avoid floating-point math in hot paths
- [ ] Use `constexpr` for compile-time calculations
- [ ] Minimize `map()` calls - use bit shifting where possible

### Hardware Optimizations
- [ ] Ensure CAN bus is running at correct speed (500kbps for OBD-II)
- [ ] Check if MCP2515 interrupt pin could speed up CAN reads
- [ ] Consider ESP32 for future (faster processor, built-in CAN on some)

---

## Quick Reference: Current Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  OBD-II Port    │     │  Raspberry Pi 4B │     │ Pioneer AVH     │
│  HS-CAN (500k)  │────►│  (CAN Hub)       │────►│ W4500NEX        │
│  MS-CAN (125k)  │     │  + Python UI     │     │ (HDMI Display)  │
└─────────────────┘     └────────┬─────────┘     └─────────────────┘
                                 │ Serial
        ┌────────────────────────┼────────────────────────┐
        │                        ▼                        │
        │                ┌──────────────────┐             │
        │                │ ESP32-S3 Round   │◄── BLE TPMS │
        │                │ Display (1.85")  │    Sensors  │
        │                └──────────────────┘             │
        │                                                 │
┌───────┴───────┐                                         │
│ Arduino Nano  │◄── MCP2515 (Direct HS-CAN)             │
│ + WS2812B LED │    <1ms latency for shift light        │
└───────────────┘                                         │
```

### Build Commands

```powershell
# Arduino LED Controller
pio run -d arduino --target upload

# ESP32-S3 Display  
pio run -d display --target upload

# Pi Display (run on Pi)
python3 pi/ui/src/main.py --fullscreen
```

---

## Session Notes

_Add notes here during next session:_

- 
- 
- 


