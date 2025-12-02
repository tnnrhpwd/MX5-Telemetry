# MX5 Telemetry - Next Session To-Do List

**Date Created:** December 1, 2025  
**Last Updated:** December 2, 2025  
**Status:** ✅ CAN Bus RPM LED circuit tested successfully on real car!  
**LED Delay Fix:** ✅ Implemented (see [LED Timing and Performance](features/LED_TIMING_AND_PERFORMANCE.md))

---

## 🎯 Priority 1: Fix LED Update Speed (CRITICAL)

### ✅ COMPLETED - December 2, 2025

The LEDs were only updating ~once every 3 seconds during real car testing. **All fixes have been implemented.**

### ✅ Root Cause Identified (Dec 2, 2025)

The 3-second delay is caused by **RPM caching in LEDSlave.cpp**:

```cpp
// In LEDSlave::updateRPM() - line 93-107
if (rpm != lastRPM || needsKeepalive) {  // Only sends if RPM changed!
    sendCommand(cmd);
    lastRPM = rpm;
}
```

**Problem:** When RPM stays the same (e.g., idling at 800 RPM, or cruising at steady RPM), the master skips sending updates. It only sends a "keep-alive" every **3 seconds**.

Contributing factors:
- `LED_UPDATE_INTERVAL = 250ms` (config.h line 72) - limits updates to 4Hz max
- RPM quantization (`rawRPM / 4`) means small fluctuations produce same integer
- Debug Serial.print statements add minor delays

### Action Items ✅ ALL COMPLETED
- [x] **FIX 1:** In `lib/LEDSlave/LEDSlave.cpp` - Always send RPM (removed caching)
- [x] **FIX 2:** In `lib/Config/config.h` - Reduced LED_UPDATE_INTERVAL from 250ms to 100ms (10Hz)
- [x] **FIX 3:** Added conditional debug mode - Serial.prints only run when USB active

### Expected Performance After Fixes
| Metric | Before | After |
|--------|--------|-------|
| Update Rate | ~0.3 Hz | **~6-10 Hz** |
| Perceived Delay | ~3 seconds | **~100-170ms** |

> **Note:** 1200 baud serial is intentionally slow for reliability. See [LED Timing and Performance](features/LED_TIMING_AND_PERFORMANCE.md) for details.

### Testing After Fix
- [ ] Verify LED updates are now 10Hz on bench with simulated CAN
- [ ] Test in car - LEDs should now respond instantly to RPM changes

---

## 🔧 Priority 2: Simplify Wiring Circuit

### Current Complexity Issues
- [ ] Document current wire count and connections
- [ ] Identify which wires/components can be eliminated
- [ ] Consider single Arduino solution (eliminate Master/Slave architecture?)

### Simplification Options
- [ ] **Option A:** Single Arduino with CAN + LEDs (no serial bridge)
  - Pros: Fewer wires, simpler code, faster updates
  - Cons: Need Arduino with enough pins (Nano may work)
  
- [ ] **Option B:** Keep dual Arduino but simplify serial protocol
  - Reduce data sent over serial to just RPM value
  - Remove status messages during operation

### Wiring Improvements
- [ ] Create cleaner connector system (JST or Molex connectors)
- [ ] Design a simple PCB or perfboard layout
- [ ] Reduce wire length where possible
- [ ] Add strain relief to critical connections

---

## 💻 Priority 3: Simplify Programming Logic

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

