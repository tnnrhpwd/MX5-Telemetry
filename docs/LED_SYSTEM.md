# Arduino LED System - Complete Guide

This document covers the complete LED RPM visualization system running on the Arduino Nano.

> ⚠️ **Being replaced.** The behaviour below is what the firmware did before the revamp.
> The strip now takes its colour ramp at runtime from the Pi (`RAMP:`) so it can follow the
> phone's theme, reports health once a second (`STATUS:`), and can be driven without the
> engine (`DEMO:<rpm>`). The authoritative specification is
> [LED_REVAMP_PLAN.md](LED_REVAMP_PLAN.md); this page describes the states and sequences,
> which are unchanged in spirit.

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

### 🔵 Idle / Pull-Away (0-1399 RPM)
**Purpose:** Idle and just moving off

**Visual:** Blue → cyan gradient, mirrored center-out fill
- Shows engine "breathing" while stationary
- Useful for rev-matching, launch control

### 🟢 Cruise / Economical (1400-2799 RPM)
**Purpose:** Best fuel economy and thermal efficiency band

**Visual:** Cyan → green gradient
- The band normal driving lives in
- Encourages eco-friendly driving

### 🟡 Waking Up (2800-4499 RPM)
**Purpose:** Spirited driving zone

**Visual:** Green → yellow gradient
- Approaching peak torque use
- Warning that the top of the range is coming

### 🟠 Spirited (4500-5799 RPM)
**Purpose:** High RPM warning

**Visual:** Yellow → orange gradient
- Prepare to shift

### 🔴 Redline (5800-6800+ RPM)
**Purpose:** Redline / shift light

**Visual:** Orange → red gradient, fully red at 6800
- The top of the strip is the shift light
- Optional haptic feedback

> **Zones are anchored to the engine, not to round numbers.** The strip only
> reaches full red at the real redline (~6800 RPM). It used to saturate at 6200,
> which left the last 600 RPM of the range showing nothing new.

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
The strip is a **positional gradient**, not a single colour that changes hue:
each LED is assigned the colour of its own place on the RPM scale
(`scaleColorAt()` in `arduino/src/main.cpp`). As RPM rises, more of that fixed
ramp lights up instead of the whole bar recolouring at once.

- Blue → cyan → green → yellow → orange → red, continuously interpolated
- The leading edge always shows the colour of the RPM it represents
- The top of the strip is red at the redline, which is what makes it a shift light

**Anti-Flicker Threshold:** 5% minimum brightness prevents LED flickering

### Latency and frame pacing
- LEDs are painted immediately after a CAN frame is decoded, not on a separate
  10 ms timer, so there is no extra tick of delay.
- Rising RPM is unfiltered (`RPM_ALPHA_RISING = 1.0`); falling RPM keeps a light
  settle filter so the bar does not trail.
- `strip.show()` is only called when a pixel actually changed
  (`showIfChanged()`), because the transfer is the expensive, interrupt-masking
  part of every frame.

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

The full command set is specified in
[LED_REVAMP_PLAN.md §5](LED_REVAMP_PLAN.md#5-phase-2--settings-protocol-pi--nano); this
table is the quick reference. Every line is `\n`-terminated and every command replies.

### Commands (Pi → Arduino)

| Command | Format | Description | Example |
|---------|--------|-------------|---------|
| **Set Sequence** | `SEQ:n` | Select LED pattern (1-4) | `SEQ:2` |
| **Query Sequence** | `SEQ?` | Get current pattern | `SEQ?` |
| **Ping** | `PING` | Connection test and identity check | `PING` |
| **Colour ramp** | `RAMP:<rpm>:<rrggbb>,…` | 2–6 stops; the last stop is also the rpm at which the strip is full | `RAMP:0:0000ff,2800:32d782,6800:ff0000` |
| **Configuration** | `CFG:<k>=<v>,…` | `bright` 0-255, `theme` 0/1, `full` rpm, `pot` 0/1, `en` 0/1, `mode` 0/1, `shift` rpm (0 = off), `hz` 2-15, `scol` rrggbb | `CFG:en=1,mode=0,shift=6300,hz=8,scol=ff0000` |
| **Query config** | `CFG?` | Prints the live configuration as one `CFG:` line | `CFG?` |
| **Persist** | `CFG:save` | Writes the config block to EEPROM (explicit, so a slider drag cannot wear it) | `CFG:save` |
| **Reset** | `CFG:reset` | Watchdog reboot, proves a save survived a power cycle | `CFG:reset` |
| **Bench rpm** | `DEMO:<rpm>` / `DEMO:OFF` | Render this rpm without CAN; self-clears after 60 s | `DEMO:2500` |
| **Self test** | `SELFTEST` | Lights every pixel in turn, so a dead LED shows as a gap | `SELFTEST` |
| **Identify** | `IDENTIFY` | Blinks the whole strip for 3 s | `IDENTIFY` |

### Responses (Arduino → Pi)

| Response | Format | Description | Example |
|----------|--------|-------------|---------|
| **Acknowledge** | `OK:<what>` / `ERR:<what>` | Command result | `OK:CFG`, `ERR:RAMP` |
| **Sequence** | `SEQ:n` | Current sequence | `SEQ:1` |
| **Pong** | `PONG` | Alive response | `PONG` |
| **Config** | `CFG:seq=…,full=…,dim=…,bright=…,stops=…,ramp=…,en=…,mode=…,shift=…,hz=…,scol=…` | Live configuration | see `CFG?` |
| **Status** | `STATUS:CAN=1,RPM=812,SEQ=1,ERR=0,FPS=320,LAST=0x201,FULL=6800,DIM=0,EN=1,MODE=0,SHIFT=6300,HZ=8` | Once a second; the only way to tell a dead strip from a real 0 rpm | |

**Baud Rate:** 9600 bps (low speed for reliability over long wires). This carries settings
only — rpm is decoded by the Nano from CAN, so it never goes over this link.

---

## Configuration (arduino/src/main.cpp)

### LED Configuration

```cpp
#define LED_COUNT           20      // Number of LEDs in strip
#define LED_DATA_PIN        5       // WS2812B Data Pin
#define ENABLE_BRIGHTNESS   true    // Potentiometer control
```

### RPM Thresholds (Colour Scale)

The zone boundaries are **not** compile-time constants any more: they live in the runtime
ramp table (`rampStops[]`), which the Pi replaces with `RAMP:` — that is what lets the
strip follow the phone's theme, or six hand-picked colours, without a reflash.

```cpp
#define RPM_MAX             6800    // default rpm at which the strip is completely full
#define RPM_REDLINE         6800    // Optional haptic trigger
```

The defaults below are what the firmware boots with, and they are also what the app's
`LED STRIP` screen starts from:

| RPM | Default colour | Why |
|-----|----------------|-----|
| 0 | `#0000ff` | idle |
| 1400 | `#00dcff` | pulling away |
| 2800 | `#32d782` | economical cruise |
| 4500 | `#ffd23c` | waking up |
| 5800 | `#ff8000` | spirited |
| 6800 | `#ff0000` | redline |

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
