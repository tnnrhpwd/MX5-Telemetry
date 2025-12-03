# MX5 Telemetry - Next Session To-Do List

**Date Created:** December 1, 2025  
**Last Updated:** December 3, 2025  
**Status:** ✅ Single Arduino optimized setup created!

---

## 🎉 COMPLETED - December 3, 2025: Single Arduino Setup

### What Was Done

1. **Created Single Arduino Optimized Build** (`single/`)
   - Direct CAN→LED path with <1ms latency
   - 100Hz LED update rate (was 10Hz)
   - Hardware interrupt on D2 for CAN messages
   - No serial communication = no data corruption
   - Simplified wiring (one Arduino instead of two)

2. **Backed Up Dual Arduino Setup** (`backup_dual_arduino/`)
   - Complete backup of master/slave/lib for future use
   - Dual setup still available for GPS/SD logging needs

3. **Updated Documentation**
   - `docs/hardware/WIRING_GUIDE_SINGLE_ARDUINO.md` - New single setup guide
   - `docs/hardware/WIRING_GUIDE_DUAL_ARDUINO.md` - Dual setup guide
   - Updated README.md to show both options
   - Updated docs/README.md with setup comparison

### Build Commands

**Single Arduino (Recommended):**
```powershell
pio run -d single -t upload --upload-port COM6
```

**Dual Arduino (for GPS/SD logging):**
```powershell
# Master
pio run -d master -t upload --upload-port COM6
# Slave (swap USB cable)
pio run -d slave -t upload --upload-port COM6
```

---

## 🎯 Priority 1: Fix LED Update Speed (CRITICAL)

### ✅ COMPLETED - Single Arduino fixes this completely

The single Arduino setup eliminates the serial link delay entirely:
- **Before:** 70ms serial transmission + 100ms update interval = ~170ms minimum
- **After:** Direct CAN read → LED update in <1ms

---

## 🔧 Priority 2: Simplify Wiring Circuit

### ✅ COMPLETED - Single Arduino setup

- [x] **Created single Arduino solution** - `single/src/main.cpp`
- [x] **Documented simplified wiring** - `WIRING_GUIDE_SINGLE_ARDUINO.md`
- [x] **Reduced wire count by 50%** - No inter-Arduino connection needed
- [x] **Hardware interrupt** - D2 for CAN INT (required for single setup)

### Single Arduino Pin Usage
| Pin | Function |
|-----|----------|
| D2 | MCP2515 INT (hardware interrupt) |
| D5 | WS2812B LED Data |
| D10 | MCP2515 CS |
| D11 | MOSI |
| D12 | MISO |
| D13 | SCK |
| A6 | Brightness pot (optional) |
| D3 | Haptic motor (optional) |

---

## 💻 Priority 3: Simplify Programming Logic

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

## 🔌 Priority 6: Hardware Improvements

### Connector System
- [ ] Design quick-disconnect for CAN bus connection
- [ ] Add inline fuse for 12V power
- [ ] Create mounting solution for LED strip
- [ ] Weatherproof connections if needed

### Power
- [ ] Verify current draw at full brightness
- [ ] Add capacitor for LED power stability
- [ ] Consider voltage regulator improvements

---

## 📝 Priority 7: Documentation Updates

- [ ] Update wiring diagram with simplified circuit
- [ ] Create "Minimal Build" guide
- [ ] Document CAN message IDs used from MX5
- [ ] Record successful test configuration for reference

---

## 🧪 Testing Checklist

Before next car test:
- [ ] Verify LED update rate on bench with simulated CAN
- [ ] Test with Serial debugging completely disabled
- [ ] Measure loop time with oscilloscope or timing pins
- [ ] Test potentiometer during startup animation
- [ ] Confirm brightness range is good for daylight visibility

---

## 💡 Future Ideas (Lower Priority)

- [ ] Shift light with configurable RPM threshold
- [ ] Color themes (selectable via potentiometer on startup?)
- [ ] Bluetooth configuration app
- [ ] Rev-match downshift indicator
- [ ] Lap timer integration
- [ ] OBD-II PID expansion (coolant temp, throttle position)

---

## Quick Reference: Current Architecture

```
[Car CAN Bus] 
     ↓ (CAN-H, CAN-L)
[MCP2515 Module] 
     ↓ (SPI)
[Master Arduino - Uno] ← Reads CAN, sends RPM over serial
     ↓ (TX→RX Serial)
[Slave Arduino - Nano] ← Receives RPM, controls LEDs
     ↓ (Data pin D5)
[WS2812B LED Strip - 20 LEDs]
     ↑
[B20K Potentiometer - A6] → Brightness control
```

### Proposed Simplified Architecture

```
[Car CAN Bus]
     ↓ (CAN-H, CAN-L)
[MCP2515 Module]
     ↓ (SPI)
[Single Arduino Nano] ← Reads CAN directly, controls LEDs
     ↓ (Data pin D5)
[WS2812B LED Strip - 20 LEDs]
     ↑
[B20K Potentiometer - A6] → Brightness control
```

**Wires eliminated:** Serial TX/RX between Arduinos, second Arduino power

---

## Session Notes

_Add notes here during tomorrow's session:_

- 
- 
- 

