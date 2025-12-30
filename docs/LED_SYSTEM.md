# Arduino LED System - Complete Guide

This document covers the complete LED RPM visualization system running on the Arduino Nano.

---

## System Overview

The Arduino Nano controls a WS2812B LED strip (20 LEDs) around the gauge cluster, providing real-time RPM visualization with **<1ms latency** from CAN bus to LED update.

**Architecture:**
- **Arduino Nano** - Mounted behind gauge cluster, reads HS-CAN directly
- **MCP2515 Module** - CAN interface (shared HS-CAN bus with Pi)
- **WS2812B Strip** - 20 RGB LEDs forming mirrored progress bar
- **Serial Link** - Receives settings/commands from Raspberry Pi

---

## LED States & Visual Patterns

### 🔴 Standby State (CAN Disconnected)
**Triggers:** Speed = 0, RPM = 0 (engine off or CAN not connected)

**Visual:** Cylon scanner effect with breathing background
- Bright dot sweeps back and forth
- Dim red background pulses (3-second cycle)
- Scanner head: bright white-red (255, 60, 30)
- Update rate: 50ms per position

### ⚪ Idle State (Stationary, RPM 1-1999)
**Triggers:** Speed = 0, RPM 1-1999 (engine running, not moving)

**Visual:** Mirrored progress bar from edges → center
- Shows engine "breathing" while stationary
- White LEDs filling toward center based on RPM %
- Useful for rev-matching, launch control

### 🔵 Blue Zone (2000-2999 RPM)
**Purpose:** Best fuel economy zone

**Visual:** Blue LEDs, mirrored center-out fill
- Optimal for cruising
- Encourages eco-friendly driving

### 🟢 Green Zone (3000-4499 RPM)
**Purpose:** Best thermal efficiency zone

**Visual:** Green LEDs with smooth gradient from blue
- Peak torque range for MX-5
- Balance of power and efficiency

### 🟡 Yellow Zone (4500-5499 RPM)
**Purpose:** Spirited driving zone

**Visual:** Yellow LEDs with smooth gradient from green
- High performance range
- Warning that redline is approaching

### 🟠 Orange Zone (5500-6199 RPM)
**Purpose:** High RPM warning

**Visual:** Orange LEDs with smooth gradient from yellow
- Approaching redline
- Prepare to shift

### 🔴 Red Zone (6200+ RPM)
**Purpose:** Redline / shift light

**Visual:** Solid red, all LEDs lit
- Full strip flashes red
- Time to shift!
- Optional haptic feedback

---

## Visual Behavior Modes

The LED strip supports 4 different fill patterns (selectable via Pi):

### Mode 1: Center-Out (Default)
LEDs fill from **edges toward center** (mirrored progress bar)
```
0%:   ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫
50%:  ▓ ▓ ▓ ▓ ▓ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ▓ ▓ ▓ ▓ ▓
100%: ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓
```
- Symmetric, easy to read peripherally
- Default pattern

### Mode 2: Left-to-Right
LEDs fill from **left to right** (traditional progress bar)
```
0%:   ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫
50%:  ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫
100%: ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓
```
- 2x effective resolution (no center split)
- Familiar progress bar style

### Mode 3: Right-to-Left
LEDs fill from **right to left** (reversed progress bar)
```
0%:   ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫
50%:  ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓
100%: ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓
```
- Mirror of left-to-right
- Alternative visualization

### Mode 4: Center-In
LEDs fill from **center toward edges** (inverse mirrored)
```
0%:   ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫
50%:  ⚫ ⚫ ⚫ ⚫ ⚫ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ⚫ ⚫ ⚫ ⚫ ⚫
100%: ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓ ▓
```
- Inverse of default
- Unique visual style

**Switching Modes:**
Send `SEQ:n\n` command via serial from Pi (n = 1-4)

---

## Smoothing Features (Implemented ✅)

### Fractional LED Brightness
Instead of discrete on/off steps, LEDs use sub-LED resolution:
- At 2000 RPM → 8.0 LEDs (8 full brightness)
- At 2155 RPM → 8.5 LEDs (8 full + 1 at 50%)
- At 2310 RPM → 9.0 LEDs (9 full brightness)

**Result:** 2x effective resolution (~40 visual steps from 20 LEDs)

### Smooth Color Gradients
Colors interpolate continuously between RPM zones:
- No sudden color jumps
- Smooth transitions: Blue → Green → Yellow → Orange → Red
- Infinite color resolution

**Anti-Flicker Threshold:** 5% minimum brightness prevents LED flickering

---

## Performance Specifications

### Single Arduino Performance (Current Implementation)

| Metric | Value | Notes |
|--------|-------|-------|
| **CAN→LED Latency** | <1ms | Hardware interrupt-driven |
| **LED Update Rate** | 100 Hz | 10ms update interval |
| **Data Corruption** | None | Direct CAN, no serial link |
| **RPM Accuracy** | Perfect | Direct CAN read |
| **CPU Usage** | ~35% | Plenty of headroom |
| **Flash Usage** | ~45% | 20-30KB of 32KB |

### Why Direct CAN is Critical

Arduino reads RPM directly from HS-CAN instead of via serial from Pi:

| Factor | Direct CAN ✅ | Serial from Pi |
|--------|-------------|----------------|
| **Latency** | <1ms | ~170ms |
| **Update Rate** | 100 Hz | 6-10 Hz |
| **EMI Resistance** | Excellent (differential) | Poor (single-ended) |
| **Reliability** | Proven in engine bay | Corruption risk |
| **Independence** | Works if Pi offline | Requires Pi |

**Decision:** Arduino keeps its own MCP2515 on shared HS-CAN bus for time-critical RPM display.

---

## Hardware Configuration

### Arduino Pin Assignments

| Pin | Function | Connection |
|-----|----------|------------|
| **D2** | CAN INT | MCP2515 INT (hardware interrupt) |
| **D5** | LED Data | WS2812B Data In (+ 330Ω resistor) |
| **D10** | CAN CS | MCP2515 CS (SPI chip select) |
| **D11** | SPI MOSI | MCP2515 SI |
| **D12** | SPI MISO | MCP2515 SO |
| **D13** | SPI SCK | MCP2515 SCK |
| **D0** | Serial RX | Pi GPIO 14 (settings commands) |
| **5V** | Power | VCC from 12V→5V buck converter |
| **GND** | Ground | Common ground |

### WS2812B LED Strip Wiring

```
Arduino D5 ──[ 330Ω ]──► LED Strip DIN
Arduino 5V ────────────► LED Strip VCC (+ 100µF cap)
Arduino GND ───────────► LED Strip GND
```

**Power Requirements:**
- 20 LEDs × 60mA max = 1.2A max current
- Typical usage: ~400-600mA
- Use adequate 5V power supply

### CAN Bus Connection

```
MCP2515 CANH ──► OBD-II Pin 6 (HS-CAN High)
MCP2515 CANL ──► OBD-II Pin 14 (HS-CAN Low)
```

**Shared Bus:** Pi MCP2515 #1 also connects to same pins (multi-drop OK)

---

## Serial Protocol (Pi ↔ Arduino)

### Commands (Pi → Arduino)

| Command | Format | Description | Example |
|---------|--------|-------------|---------|
| **Set Sequence** | `SEQ:n\n` | Select LED pattern (1-4) | `SEQ:2\n` |
| **Query Sequence** | `SEQ?\n` | Get current pattern | `SEQ?\n` |
| **Ping** | `PING\n` | Connection test | `PING\n` |

### Responses (Arduino → Pi)

| Response | Format | Description | Example |
|----------|--------|-------------|---------|
| **Acknowledge** | `OK:n\n` | Sequence changed | `OK:2\n` |
| **Status** | `SEQ:n\n` | Current sequence | `SEQ:1\n` |
| **Pong** | `PONG\n` | Alive response | `PONG\n` |

**Baud Rate:** 9600 bps (low speed for reliability over long wires)

---

## Configuration (arduino/src/main.cpp)

### LED Configuration

```cpp
#define LED_COUNT           20      // Number of LEDs in strip
#define LED_DATA_PIN        5       // WS2812B Data Pin
#define ENABLE_BRIGHTNESS   true    // Potentiometer control
```

### RPM Thresholds (Color Zones)

```cpp
#define RPM_ZONE_BLUE       2000    // 0-1999: Blue
#define RPM_ZONE_GREEN      3000    // 2000-2999: Green
#define RPM_ZONE_YELLOW     4500    // 3000-4499: Yellow
#define RPM_ZONE_ORANGE     5500    // 4500-5499: Orange
#define RPM_MAX             6200    // 5500+: Red
#define RPM_REDLINE         6800    // Optional haptic trigger
```

### CAN Configuration

```cpp
#define CAN_CS_PIN          10      // MCP2515 Chip Select
#define CAN_INT_PIN         2       // MCP2515 Interrupt (MUST be D2)
#define CAN_SPEED           CAN_500KBPS  // MX-5 NC HS-CAN
#define CAN_CRYSTAL         MCP_8MHZ
#define MAZDA_RPM_CAN_ID    0x201   // Engine RPM message
```

---

## LED Simulator Integration

A Python-based LED simulator allows testing without physical hardware:

**Location:** `tools/simulators/led_simulator.py`

**Features:**
- Visual LED strip simulation
- Real-time Arduino connection via serial
- RPM slider control
- Supports all 4 LED patterns
- Debug mode for development

**Usage:**
```bash
python tools/simulators/led_simulator.py
```

See [tools/simulators/README.md](../../tools/simulators/README.md) for simulator documentation.

---

## Troubleshooting

### LEDs Show Error Animation (Red Flash)
- **Cause:** CAN bus not connected or no data
- **Fix:** Check MCP2515 wiring, verify OBD-II connection
- **Verify:** Should show standby animation if wiring is correct

### LEDs Not Responding to RPM
- **Cause:** Wrong CAN message ID or formula
- **Fix:** Verify CAN ID 0x201 on HS-CAN, check RPM formula (÷4)
- **Test:** Use candump to verify CAN traffic

### LEDs Flickering
- **Cause:** Insufficient power or bad ground
- **Fix:** Check 5V power supply, add 100µF capacitor
- **Verify:** Voltage should be stable 4.8-5.2V

### Serial Commands Not Working
- **Cause:** Wrong baud rate or disconnected serial
- **Fix:** Verify 9600 baud, check TX/RX wiring
- **Test:** Send `PING\n`, should respond `PONG\n`

### Wrong Colors Displayed
- **Cause:** Incorrect RPM thresholds in code
- **Fix:** Adjust RPM_ZONE_* constants in main.cpp
- **Rebuild:** Recompile and upload firmware

---

## See Also

- [ARCHITECTURE.md](../ARCHITECTURE.md) - Complete system design
- [BUILD_AND_UPLOAD.md](../BUILD_AND_UPLOAD.md) - Build & upload guide
- [hardware/WIRING_GUIDE.md](../hardware/WIRING_GUIDE.md) - Complete wiring diagrams
- [tools/simulators/README.md](../../tools/simulators/README.md) - LED simulator documentation

---

**Last Updated:** December 29, 2025
