# LED Timing and Performance Analysis

**Last Updated:** December 2, 2025  
**Status:** ✅ Performance issues identified and fixed

---

## Overview

This document explains the LED update timing, the 3-second delay bug that was discovered during real car testing, and the fixes applied to achieve responsive LED feedback.

---

## The Problem: 3-Second LED Update Delay

During the first real car test (December 1, 2025), the LEDs were observed to update only approximately **once every 3 seconds**. This made the RPM display feel sluggish and unresponsive.

### Root Causes Identified

| Issue | Impact | Status |
|-------|--------|--------|
| RPM caching in LEDSlave.cpp | Only sent updates when RPM changed, with 3-second keep-alive | ✅ Fixed |
| LED_UPDATE_INTERVAL = 250ms | Limited updates to 4Hz maximum | ✅ Fixed |
| Debug Serial.print statements | Added ~10-20ms overhead per update | ✅ Fixed |
| 1200 baud bit-bang serial | ~50ms per message transmission | By design (see below) |

---

## Fix 1: Remove RPM Caching

### Before (LEDSlave.cpp)
```cpp
void LEDSlave::updateRPM(uint16_t rpm, uint16_t speed_kmh) {
    unsigned long now = millis();
    bool needsKeepalive = (now - lastKeepalive) >= 3000;  // Keep-alive every 3 seconds
    
    // Only sent if RPM changed OR 3 seconds passed!
    if (rpm != lastRPM || needsKeepalive) {
        sendCommand(cmd);
        lastRPM = rpm;
        lastKeepalive = now;
    }
}
```

### After (Always send RPM)
```cpp
void LEDSlave::updateRPM(uint16_t rpm, uint16_t speed_kmh) {
    // Always send RPM for responsive LEDs (removed caching)
    char cmd[8];
    cmd[0] = 'R';
    itoa(rpm, cmd + 1, 10);
    sendCommand(cmd);
    lastRPM = rpm;
}
```

**Why the caching was a problem:** When RPM stays constant (idling at 800 RPM, cruising at steady speed), no updates were sent. The LEDs only updated on the 3-second keep-alive timer.

---

## Fix 2: Increase LED Update Rate

### Before (config.h)
```cpp
#define LED_UPDATE_INTERVAL  250   // 4Hz - heavily rate-limited
```

### After
```cpp
#define LED_UPDATE_INTERVAL  100   // 10Hz - responsive to RPM changes
```

---

## Fix 3: Conditional Debug Output

Debug `Serial.print()` statements were executing on every byte received, adding significant overhead. Now they only run when USB is actively connected.

### Implementation (slave main.cpp)
```cpp
bool debugMode = false;  // Only true when USB command received recently
#define DEBUG_MODE_TIMEOUT_MS 10000  // Auto-disable after 10 seconds

// Debug prints now conditional:
if (debugMode) {
    Serial.print("RX: ");
    Serial.println(c);
}
```

**Behavior:**
- Send any USB command → Debug mode enabled for 10 seconds
- No USB activity → Debug mode auto-disables
- Running in car (no USB) → Zero debug overhead

---

## Why 1200 Baud Serial?

The Master→Slave serial communication uses **1200 baud**, which is intentionally slow.

### The Tradeoff

| Baud Rate | Transmission Time (6 bytes) | Reliability |
|-----------|----------------------------|-------------|
| 9600 baud | ~6ms | Occasional corruption |
| 4800 baud | ~12ms | Better reliability |
| **1200 baud** | **~50ms** | **Most reliable** |

### Why We Chose 1200 Baud

1. **Bit-bang serial from Master:** The Master uses software bit-banging (not hardware UART) on pin D6, which is timing-sensitive
2. **Interrupt conflicts:** The Master runs CAN bus (SPI), GPS (SoftwareSerial), and SD card (SPI) - all generate interrupts that can corrupt serial timing
3. **SoftwareSerial on Slave:** The Slave uses SoftwareSerial on D2, which can also miss bits during interrupts
4. **Proven reliability:** At 1200 baud, we observed zero corruption during testing

### Message Format
```
!R6500\n    (8 bytes total)
│││   │
││└───┴── RPM value (up to 5 digits)
│└─────── 'R' = RPM command
└──────── '!' = Start marker (helps resync after corruption)
```

**Transmission time at 1200 baud:**
- 8 bytes × 10 bits/byte = 80 bits
- 80 bits ÷ 1200 baud = **~67ms** per message

---

## Current Performance (After Fixes)

### Timing Breakdown

| Stage | Time | Notes |
|-------|------|-------|
| CAN Bus Read | 20ms interval | 50Hz polling |
| LED_UPDATE_INTERVAL | 100ms | Rate-limits Master→Slave |
| Bit-bang transmission | ~67ms | 8 bytes at 1200 baud |
| Bit-bang delays | ~5ms | Settling time, gaps |
| Debug prints | 0ms | Disabled in car |
| **Total worst-case** | **~170ms** | |

### Effective Update Rate

| Metric | Before Fixes | After Fixes |
|--------|--------------|-------------|
| **Update Rate** | ~0.3 Hz (3s delays) | **~6-10 Hz** |
| **Perceived Latency** | ~3 seconds | **~100-170ms** |
| **Responsiveness** | Very sluggish | **Near-instant** |

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         TIMING FLOW                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Car ECU                                                       │
│      │                                                          │
│      │ CAN Bus (500 kbps)                                       │
│      ▼                                                          │
│   ┌─────────────┐     Bit-bang Serial      ┌─────────────┐     │
│   │   MASTER    │      (1200 baud)         │    SLAVE    │     │
│   │  Arduino    │ ──────────────────────▶  │   Arduino   │     │
│   │             │     D6 → D2               │             │     │
│   │ CAN + GPS   │     ~67ms/msg            │  LED Strip  │     │
│   │ + SD Card   │                          │  20 LEDs    │     │
│   └─────────────┘                          └─────────────┘     │
│                                                                 │
│   Timing:                                                       │
│   ├── CAN read every 20ms (50 Hz)                              │
│   ├── LED update every 100ms (10 Hz)                           │
│   └── Serial TX takes ~67ms (1200 baud)                        │
│                                                                 │
│   Result: ~6-10 Hz effective LED update rate                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Future Improvements

If even faster updates are needed (20Hz+), consider:

1. **Increase baud rate to 9600** (if reliability permits)
   - Would reduce transmission to ~8ms
   - Risk: potential corruption from interrupt conflicts

2. **Reduce LED_UPDATE_INTERVAL to 50ms**
   - Would allow 20Hz theoretical max
   - Trade-off: more CPU load on Master

3. **Single-Arduino architecture**
   - Eliminate serial bottleneck entirely
   - CAN + LEDs on same Arduino Nano
   - Challenge: SD card + LED interrupt conflicts

4. **ESP32 upgrade**
   - Hardware CAN controller (no MCP2515 needed)
   - Dual-core: one for CAN, one for LEDs
   - Much faster processor (240 MHz vs 16 MHz)

---

## Related Documentation

- [Master/Slave Architecture](../hardware/MASTER_SLAVE_ARCHITECTURE.md)
- [LED State System](LED_STATE_SYSTEM.md)
- [Config Reference](../../lib/Config/config.h)
