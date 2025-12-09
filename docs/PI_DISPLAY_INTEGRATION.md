# MX5 Raspberry Pi + ESP32-S3 Display Integration

## Project Overview

Integrate a Raspberry Pi 4 (HDMI output to Pioneer AVH-W4500NEX) and ESP32-S3 Round Display into the 2008 MX5 NC GT, controlled via stock steering wheel buttons through CAN bus.

### Goals
- Display telemetry data on ESP32-S3 round LCD (gauges, RPM, speed)
- Display telemetry data on Raspberry Pi via HDMI to Pioneer head unit
- Display tire pressure from BLE TPMS sensors on both displays
- Control both devices using stock MX5 steering wheel buttons (no touch needed)
- Read vehicle data from HS-CAN and MS-CAN buses

---

## Hardware Components

| Component | Purpose | Docs |
|-----------|---------|------|
| Raspberry Pi 4B | CAN hub + HDMI output to Pioneer AVH-W4500NEX | - |
| ESP32-S3 Round Display | 1.85" gauge display + BLE TPMS receiver | - |
| Arduino Nano | RPM LED strip controller (direct CAN) | [WIRING_GUIDE.md](hardware/WIRING_GUIDE.md) |
| MCP2515 Module x3 | Pi (HS + MS), Arduino (HS) - hardwired for reliability | [WIRING_GUIDE.md](hardware/WIRING_GUIDE.md) |
| Pioneer AVH-W4500NEX | Head unit with HDMI input | - |
| WS2812B LED Strip | RPM shift light (20 LEDs) | [WIRING_GUIDE.md](hardware/WIRING_GUIDE.md) |
| OBD-II Breakout | Access CAN bus pins | [WIRING_GUIDE.md](hardware/WIRING_GUIDE.md) |
| LM2596 Buck Converter | 12V → 5V power | [WIRING_GUIDE.md](hardware/WIRING_GUIDE.md) |
| BLE TPMS Sensors (4x) | Tire pressure + temp | Cap-mounted, BLE broadcast ✅ Ordered |

---

## MX5 NC CAN Bus Architecture

### Bus Specifications

| Bus | Speed | OBD Pins | Data Available |
|-----|-------|----------|----------------|
| **HS-CAN** | 500 kbps | 6 (H), 14 (L) | Engine RPM, Speed, Throttle, Temps, Gear |
| **MS-CAN** | 125 kbps | 3 (H), 11 (L) | Steering Wheel Buttons, Cruise Control, Body |

### Steering Wheel Button CAN Messages

#### Audio Controls (Left Side)
| Button | CAN ID | Byte 0 Value |
|--------|--------|--------------|
| Volume Up | `0x240` | `0x01` |
| Volume Down | `0x240` | `0x02` |
| Mode/Source | `0x240` | `0x04` |
| Seek/Track Up | `0x240` | `0x08` |
| Seek/Track Down | `0x240` | `0x10` |
| Mute | `0x240` | `0x20` |

#### Cruise Control (Right Side)
| Button | CAN ID | Byte Value |
|--------|--------|------------|
| ON/OFF | `0x250` | `0x01` |
| Cancel | `0x250` | `0x02` |
| RES+ (Resume/Accel) | `0x250` | `0x04` |
| SET- (Set/Decel) | `0x250` | `0x08` |

> ⚠️ **Note**: CAN IDs need verification by sniffing actual bus traffic

---

## Available Diagnostic Data

All data below can be displayed on **both** the ESP32-S3 round display and the Pi/Pioneer screen.

### HS-CAN Data (500 kbps) - Engine/Drivetrain

| CAN ID | Data | Bytes | Scale/Formula | Display Ideas |
|--------|------|-------|---------------|---------------|
| `0x201` | **RPM** | 0,1 | Direct value | Tachometer, shift light |
| `0x201` | **Vehicle Speed** | 4,5 | X/100 km/h | Speedometer |
| `0x201` | **Accelerator Position** | 6 | 0-200 (200=100%) | Throttle bar |
| `0x228` | **Gear Position** | 0 | Bit flags (see below) | Gear indicator |
| `0x231` | **Gear (Alt)** | 0 | Bits 4-7 = gear | Gear indicator |
| `0x190` | **Brake Active** | 2, bit 6 | 0x40 = braking | Brake indicator |
| `0x205` | **Brake Active (Alt)** | 2, bit 6 | 0x40 = braking | Brake light |
| `0x4B0` | **Wheel Speed FL** | 0,1 | (X-10000)/100 km/h | Individual wheel speeds |
| `0x4B0` | **Wheel Speed FR** | 2,3 | (X-10000)/100 km/h | Traction display |
| `0x4B0` | **Wheel Speed RL** | 4,5 | (X-10000)/100 km/h | Slip detection |
| `0x4B0` | **Wheel Speed RR** | 6,7 | (X-10000)/100 km/h | |
| `0x4DA` | **Steering Angle** | 0,1 | (X-32768)/10 degrees | Steering indicator |
| `0x420` | **Coolant Temp** | 0 | Temperature | Temp gauge |
| `0x4F2` | **Odometer** | 1,2 | Total km/miles | Trip computer |

#### Gear Position Decoding (0x228 Byte 0)

| Bit | Value | Meaning |
|-----|-------|--------|
| 0 | 0x01 | Park/Off |
| 1 | 0x02 | Reverse |
| 2 | 0x04 | Forward/Drive |
| 4 | 0x10 | 1st Gear |
| 5 | 0x20 | 2nd Gear |
| 6 | 0x40 | 3rd Gear |
| 7 | 0x80 | 4th Gear |

*Note: 5th and 6th gear likely in Byte 1*

### MS-CAN Data (125 kbps) - Body/Accessories

| CAN ID | Data | Bytes | Description | Display Ideas |
|--------|------|-------|-------------|---------------|
| `0x240` | **SWC Audio Buttons** | 0 | See button table above | UI navigation |
| `0x250` | **SWC Cruise Buttons** | 0 | See button table above | UI navigation |
| `0x265` | **Turn Signals** | 0, bits 5-6 | L=0x20, R=0x40 | Blinker indicators |
| `0x400` | **Average Speed** | 0,1 | km/h | Trip computer |
| `0x400` | **Instant Fuel Consumption** | 2,3 | X/10 L/100km | Economy gauge |
| `0x400` | **Average Fuel Consumption** | 3,4 | X/10 L/100km | Economy display |
| `0x400` | **Distance Remaining** | 5,6 | km to empty | Range indicator |
| `0x430` | **Fuel Level** | 0 | X/2.55 = % | Fuel gauge |
| `0x433` | **Outside Temp** | 2 | X/4 °C | Temp display |
| `0x433` | **Headlights On** | 4 | Bit flags | Light indicators |
| `0x433` | **High Beams** | 3, bit 6 | 0x40 = on | Light indicators |
| `0x433` | **A/C Running** | 3, bit 3 | 0x08 = on | Climate display |

### BLE TPMS Data (via ESP32-S3)

| Data | Source | Display Ideas |
|------|--------|---------------|
| **Tire Pressure FL** | BLE sensor | 4-corner TPMS display |
| **Tire Pressure FR** | BLE sensor | Low pressure warning |
| **Tire Pressure RL** | BLE sensor | Color-coded pressures |
| **Tire Pressure RR** | BLE sensor | |
| **Tire Temp FL-RR** | BLE sensor | Temp warnings |
| **TPMS Battery %** | BLE sensor | Low battery alert |

### Display Screen Ideas

#### ESP32-S3 Round Display (360x360)

| Screen | Data Shown |
|--------|------------|
| **RPM Gauge** | RPM (large), Gear, Shift indicator |
| **Speedometer** | Speed, Gear, Turn signals |
| **TPMS View** | 4-corner tire pressures + temps |
| **Temps** | Coolant, Outside temp, Oil (if available) |
| **G-Force** | Calculated from wheel speed deltas |
| **Economy** | Instant MPG, Average MPG, Range |

#### Pioneer AVH-W4500 (800x480)

| Screen | Data Shown |
|--------|------------|
| **Dashboard** | RPM bar, Speed, Gear, Temps |
| **TPMS Full** | 4 tires with PSI, temp, battery |
| **Trip Computer** | Avg speed, fuel economy, range, odometer |
| **Performance** | 0-60 timer, G-force, lap timer |
| **Diagnostics** | All raw CAN values, error codes |
| **Settings** | Shift light RPM, units, brightness |

---

## System Architecture

### Why Raspberry Pi as Hub (Not ESP32-S3)

The ESP32-S3 round display modules have **limited exposed GPIO pins** (6-10 usable), while the Pi has **26+ GPIO pins**. This makes the Pi the better choice for CAN bus hub:

| Factor | ESP32-S3 as Hub | Pi as Hub ✅ |
|--------|-----------------|-------------|
| Available GPIO | ~6-10 pins | 26+ pins |
| CAN Processing | Limited CPU | Plenty of power |
| Connection to displays | WiFi (laggy) | Wired UART (fast) |
| Complexity | ESP does everything | Distributed, simpler |
| BLE TPMS | Built-in BLE ✅ | Need USB dongle |

> **Decision**: Pi reads both CAN buses (HS + MS) and distributes data via wired serial to ESP32-S3.
> Arduino Nano **keeps its own MCP2515** connected directly to HS-CAN for reliable RPM reading.
> ESP32-S3 handles BLE TPMS (built-in Bluetooth) and forwards TPMS to Pi.
> **Both displays receive SWC button events** so both can respond to steering wheel controls.

### Why Arduino Keeps Direct CAN (Not Serial)

Serial communication is prone to **EMI corruption** in automotive environments:

| Connection | Distance | Environment | Risk |
|------------|----------|-------------|------|
| **Pi ↔ ESP32** | ~10-30cm (same enclosure) | Low EMI, cabin | **LOW** ✅ |
| **Pi → Arduino** | ~1-2m (dash to engine bay) | High EMI (ignition, alternator) | **HIGH** ⚠️ |

**Arduino stays on direct CAN because:**
1. **RPM is time-critical** - Shift light needs <50ms latency
2. **Long wire run** - Through firewall, near spark plug wires
3. **High EMI zone** - Ignition coils, alternator, injectors
4. **Already working** - Current setup is proven reliable
5. **CAN is differential** - Inherently noise-resistant vs single-ended serial

### Block Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MX5 NC TELEMETRY ARCHITECTURE                             │
│                  (Pi as Hub, Arduino Direct CAN for RPM)                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                         OBD-II PORT                                  │   │
│   │   Pin 6 ───┬─── HS-CAN High (500kbps)                               │   │
│   │   Pin 14 ──┼─── HS-CAN Low                                          │   │
│   │   Pin 3 ───┼─── MS-CAN High (125kbps)                               │   │
│   │   Pin 11 ──┴─── MS-CAN Low                                          │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                 │                              │                             │
│                 ▼                              ▼                             │
│   ════════════════════════        ════════════════════════                  │
│      HS-CAN BUS (500k)               MS-CAN BUS (125k)                      │
│   ════════════════════════        ════════════════════════                  │
│         │         │                      │                                   │
│         │         │                      ▼                                   │
│         │         │               ┌──────────┐                              │
│         │         │               │ MCP2515  │                              │
│         │         │               │ #2 (MS)  │──── Pi GPIO 7 (CE1)          │
│         │         │               └────┬─────┘                              │
│         │         │                    │ SPI                                │
│         ▼         ▼                    │                                    │
│   ┌──────────┐  ┌──────────┐           │                                    │
│   │ MCP2515  │  │ MCP2515  │           │                                    │
│   │ #1 (HS)  │  │ #3 (HS)  │           │                                    │
│   │ for Pi   │  │ Arduino  │           │                                    │
│   └────┬─────┘  └────┬─────┘           │                                    │
│        │ SPI         │ SPI             │                                    │
│        │ Pi GPIO 8   │ Nano D10        │                                    │
│        │             │                 │                                    │
│        ▼             ▼                 ▼                                    │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    RASPBERRY PI 4B (MAIN HUB)                        │   │
│   │                                                                      │   │
│   │  • Reads HS-CAN (RPM, Speed, Throttle, Temps, Gear)                 │   │
│   │  • Reads MS-CAN (Steering Wheel Buttons, Cruise, Body)              │   │
│   │  • Receives BLE TPMS data from ESP32-S3                             │   │
│   │  • Sends all data to ESP32-S3 via Serial (short, shielded cable)    │   │
│   │  • Displays telemetry on HDMI → Pioneer AVH-W4500NEX                │   │
│   │  • Handles button commands for Pi apps                              │   │
│   │                                                                      │   │
│   └────────┬────────────────────────────┬───────────────────────────────┘   │
│            │                            │                                    │
│            │ Serial/UART                │ HDMI                               │
│            │ (GPIO 14/15)               │                                    │
│            │ ~20cm shielded             │                                    │
│            ▼                            ▼                                    │
│   ┌─────────────────────┐     ┌─────────────────────┐                       │
│   │     ESP32-S3        │     │  Pioneer AVH-W4500  │                       │
│   │   Round Display     │     │    (800x480)        │                       │
│   │                     │     └─────────────────────┘                       │
│   │  • Receives data    │                                                    │
│   │    from Pi (Serial) │                                                    │
│   │  • BLE TPMS Rx      │◄──────── BLE TPMS Cap Sensors (x4)                │
│   │  • Round LCD gauge  │                                                    │
│   │  • Forwards TPMS    │                                                    │
│   │    to Pi (Serial)   │                                                    │
│   │  • NO CAN MODULE    │                                                    │
│   └─────────────────────┘                                                    │
│                                                                              │
│   ┌─────────────────────┐                                                    │
│   │    Arduino Nano     │◄──────── MCP2515 #3 (DIRECT HS-CAN)               │
│   │     RPM LEDs        │          (separate from Pi, EMI-resistant)        │
│   │                     │                                                    │
│   │  • Reads RPM direct │                                                    │
│   │    from HS-CAN      │                                                    │
│   │  • Drives WS2812B   │                                                    │
│   │  • NO SERIAL needed │                                                    │
│   └─────────────────────┘                                                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow (Hybrid: CAN + Serial)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    HYBRID DATA FLOW (CAN + Serial)                           │
│              Arduino: Direct CAN | ESP32: Serial from Pi                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                     RASPBERRY PI 4B (CAN HUB)                        │   │
│   │                                                                      │   │
│   │  INPUTS:                          OUTPUTS:                           │   │
│   │  ├─ MCP2515 #1 (HS-CAN 500k)      ├─► ESP32-S3 (Serial TX)          │   │
│   │  │  • RPM, Speed, Throttle        │   • All CAN telemetry            │   │
│   │  │  • Temps, Gear, Brake          │   • SWC button events ◄──────┐  │   │
│   │  │  • Wheel Speeds, Steering      │   (short cable, low EMI)     │  │   │
│   │  │                                │                              │  │   │
│   │  ├─ MCP2515 #2 (MS-CAN 125k)      │                              │  │   │
│   │  │  • SWC Buttons ────────────────┼──────────────────────────────┘  │   │
│   │  │  • Cruise Control              │                                  │   │
│   │  │  • Lights, Doors, Climate      ├─► Pioneer (HDMI)                │   │
│   │  │  • Fuel Level/Consumption      │   • Full UI display              │   │
│   │  │                                │                                  │   │
│   │  └─ ESP32-S3 (Serial RX) ◄────────┼─── TPMS data from ESP32         │   │
│   │     • Tire Pressure (x4)          │                                  │   │
│   │     • Tire Temp (x4)              │                                  │   │
│   │     • TPMS Battery %              │                                  │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                        ESP32-S3 ROUND DISPLAY                        │   │
│   │                         (NO CAN - Serial Only)                       │   │
│   │                                                                      │   │
│   │  INPUTS:                          OUTPUTS:                           │   │
│   │  ├─ Pi (Serial RX)                ├─► Pi (Serial TX)                │   │
│   │  │  • All CAN telemetry           │   • TPMS data only              │   │
│   │  │  • SWC button events ──────────┼─► Round LCD Display             │   │
│   │  │    (to control ESP UI)         │   • Gauges, TPMS, Alerts        │   │
│   │  │                                │                                  │   │
│   │  └─ BLE (built-in)                │                                  │   │
│   │     • TPMS cap sensors (x4)       │                                  │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    ARDUINO NANO (DIRECT HS-CAN)                      │   │
│   │                     (Independent, EMI-Resistant)                     │   │
│   │                                                                      │   │
│   │  INPUTS:                          OUTPUTS:                           │   │
│   │  └─ MCP2515 #3 (HS-CAN 500k)      └─► WS2812B LED Strip             │   │
│   │     • RPM (0x201)                     • 20 LEDs, shift light         │   │
│   │     • Direct from OBD-II              • <1ms CAN-to-LED latency      │   │
│   │     • No serial dependency            • Works even if Pi offline     │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   SUMMARY:                                                                   │
│   ═══════                                                                    │
│   Pi → ESP32:  All CAN data + SWC buttons (short serial, ~20cm)             │
│   ESP32 → Pi:  TPMS data only (BLE reception)                               │
│   Arduino:     DIRECT HS-CAN via MCP2515 #3 (no serial, no corruption)      │
│                                                                              │
│   WHY ARDUINO USES DIRECT CAN:                                               │
│   • RPM timing critical (<50ms for shift light)                             │
│   • Long wire run through high-EMI engine bay                               │
│   • CAN differential signaling resists noise                                │
│   • Already working and proven reliable                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Wiring Diagrams

### Raspberry Pi 4B Pin Assignments (CAN Hub)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    RASPBERRY PI 4B WIRING DIAGRAM                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Pi GPIO Pin       │  Connection                                           │
│   ══════════════════│══════════════════════════════════════                 │
│                     │                                                        │
│   --- Power ---                                                              │
│   5V (Pin 2,4)      │  From LM2596 Buck Converter                           │
│   GND (Pin 6,9,etc) │  Common Ground                                        │
│                     │                                                        │
│   --- MCP2515 CAN Modules (Shared SPI Bus) ---                              │
│   GPIO 10 (MOSI)    │  MCP2515 #1 SI + MCP2515 #2 SI                        │
│   GPIO 9  (MISO)    │  MCP2515 #1 SO + MCP2515 #2 SO                        │
│   GPIO 11 (SCLK)    │  MCP2515 #1 SCK + MCP2515 #2 SCK                      │
│   GPIO 8  (CE0)     │  MCP2515 #1 CS (HS-CAN)                               │
│   GPIO 7  (CE1)     │  MCP2515 #2 CS (MS-CAN)                               │
│   GPIO 25           │  MCP2515 #1 INT (HS-CAN)                              │
│   GPIO 24           │  MCP2515 #2 INT (MS-CAN)                              │
│                     │                                                        │
│   --- Serial to ESP32-S3 (Telemetry + TPMS) ---                             │
│   GPIO 14 (TXD)     │  ESP32-S3 RX (receive telemetry from Pi)              │
│   GPIO 15 (RXD)     │  ESP32-S3 TX (send TPMS data to Pi)                   │
│                     │                                                        │
│   --- Serial to Arduino (RPM only) --- [Optional: via ESP32]                │
│   GPIO 0  (TXD1)*   │  Arduino D2 (SoftwareSerial RX)                       │
│   GPIO 1  (RXD1)*   │  Arduino D3 (optional feedback)                       │
│   * Or route through ESP32-S3                                                │
│                     │                                                        │
│   --- HDMI ---                                                               │
│   HDMI Port         │  Pioneer AVH-W4500NEX (800x480)                       │
│                     │                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### ESP32-S3 Round Display Pin Assignments (Simplified)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                 ESP32-S3 ROUND DISPLAY WIRING (SIMPLIFIED)                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   The ESP32-S3 round display module has LIMITED exposed GPIOs.              │
│   In this architecture, it only needs:                                       │
│                                                                              │
│   ESP32-S3 Pin      │  Connection                                           │
│   ══════════════════│══════════════════════════════════════                 │
│                     │                                                        │
│   --- Power ---                                                              │
│   5V / VIN          │  From LM2596 Buck Converter (shared with Pi)          │
│   GND               │  Common Ground                                        │
│                     │                                                        │
│   --- Serial to Raspberry Pi ---                                            │
│   TX (GPIO 43)      │  Pi GPIO 15 (RXD) - Send TPMS data to Pi              │
│   RX (GPIO 44)      │  Pi GPIO 14 (TXD) - Receive telemetry from Pi         │
│                     │                                                        │
│   --- Built-in (no external wiring) ---                                     │
│   Internal SPI      │  GC9A01 1.85" Round LCD (360x360)                     │
│   Internal I2C      │  Touch Controller (FT5x06)                            │
│   Internal BLE      │  BLE TPMS Sensor Reception (no wiring needed!)        │
│                     │                                                        │
│   ✅ Total external connections: Power (2) + Serial (2) = 4 wires only!    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### MCP2515 Module Connections (to Raspberry Pi)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MCP2515 MODULE CONNECTIONS                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   MCP2515 #1 (HS-CAN)          MCP2515 #2 (MS-CAN)                          │
│   ═══════════════════          ═══════════════════                          │
│                                                                              │
│   VCC ──── Pi 3.3V (Pin 1)     VCC ──── Pi 3.3V (Pin 1)                     │
│   GND ──── Pi GND (Pin 6)      GND ──── Pi GND (Pin 6)                      │
│   CS  ──── Pi GPIO 8 (CE0)     CS  ──── Pi GPIO 7 (CE1)                     │
│   SO  ──── Pi GPIO 9 (MISO)    SO  ──── Pi GPIO 9 (MISO)  [shared]          │
│   SI  ──── Pi GPIO 10 (MOSI)   SI  ──── Pi GPIO 10 (MOSI) [shared]          │
│   SCK ──── Pi GPIO 11 (SCLK)   SCK ──── Pi GPIO 11 (SCLK) [shared]          │
│   INT ──── Pi GPIO 25          INT ──── Pi GPIO 24                          │
│                                                                              │
│   CANH ─── OBD Pin 6           CANH ─── OBD Pin 3                           │
│   CANL ─── OBD Pin 14          CANL ─── OBD Pin 11                          │
│                                                                              │
│   ⚠️  120Ω terminator usually not needed when tapping OBD port              │
│   ⚠️  Both MCP2515 share SPI bus (MISO, MOSI, SCLK) but have separate CS    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Existing Arduino LED RPM System

> ✅ **This system already exists and is working!** See `docs/hardware/WIRING_GUIDE.md` and `arduino/src/main.cpp` for full implementation.

The Arduino Nano RPM LED controller reads directly from HS-CAN via its own MCP2515 module. **This design is kept unchanged** because serial communication over long distances in automotive environments is prone to EMI corruption.

### Arduino Nano Pin Configuration

From `arduino/src/main.cpp` (current working setup):

| Pin | Function | Connection |
|-----|----------|------------|
| **D2** | CAN INT | MCP2515 INT (hardware interrupt for fast response) |
| **D5** | LED Data | WS2812B Data In (330Ω resistor recommended) |
| **D10** | CAN CS | MCP2515 CS (SPI chip select) |
| **D11** | SPI MOSI | MCP2515 SI |
| **D12** | SPI MISO | MCP2515 SO |
| **D13** | SPI SCK | MCP2515 SCK |
| **5V** | Power | VCC from LM2596 buck converter |
| **GND** | Ground | Common ground |

### LED Configuration

From `arduino/src/main.cpp`:

```cpp
#define LED_COUNT           20      // Number of LEDs in strip
#define LED_DATA_PIN        5       // WS2812B Data Pin
#define ENABLE_BRIGHTNESS   true    // Potentiometer brightness control
```

### RPM Thresholds (Color Zones)

From `arduino/src/main.cpp`:

```cpp
// RPM thresholds for LED color zones
#define RPM_ZONE_BLUE       2000    // 0-1999: Blue (idle/low)
#define RPM_ZONE_GREEN      3000    // 2000-2999: Green (eco)
#define RPM_ZONE_YELLOW     4500    // 3000-4499: Yellow (normal)
#define RPM_ZONE_ORANGE     5500    // 4500-5499: Orange (spirited)
#define RPM_MAX             6200    // 5500+: Red (high RPM)
#define RPM_REDLINE         6800    // Trigger haptic pulse (optional)
```

### CAN Configuration

From `arduino/src/main.cpp`:

```cpp
#define CAN_CS_PIN          10      // MCP2515 Chip Select (SPI)
#define CAN_INT_PIN         2       // MCP2515 Interrupt (MUST be D2 for INT0)
#define CAN_SPEED           CAN_500KBPS  // MX-5 NC HS-CAN bus speed
#define CAN_CRYSTAL         MCP_8MHZ     // MCP2515 crystal frequency
#define MAZDA_RPM_CAN_ID    0x201   // Engine RPM broadcast ID
```

### WS2812B LED Strip Wiring

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       WS2812B LED STRIP WIRING                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Arduino Nano             WS2812B Strip (20 LEDs)                          │
│   ═══════════════          ═══════════════════════                          │
│                                                                              │
│   D5 (LED Data) ──────────→ DIN (Data In)                                   │
│   5V ─────────────────────→ VCC (through 100µF cap)                         │
│   GND ────────────────────→ GND                                             │
│                                                                              │
│   ⚠️  Add 330Ω resistor between D5 and DIN for signal protection            │
│   ⚠️  Add 100µF capacitor across VCC/GND near first LED                      │
│   ⚠️  20 LEDs @ max brightness can draw ~1.2A - ensure adequate power        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Arduino Architecture (FINAL - Direct CAN)

**KEEPING DIRECT CAN** (proven reliable, EMI-resistant):
```
                     MCP2515 #3
                   ┌─────────┐
    OBD-II HS-CAN ─┤ CAN H/L │◄── Differential signaling resists EMI
                   └────┬────┘
                        │ SPI (D10-D13) + INT (D2)
                        ▼
                  ┌───────────┐
                  │  Arduino  │◄── Hardware interrupt for <1ms latency
                  │   Nano    │
                  └─────┬─────┘
                        │ D5
                        ▼
                  ┌───────────┐
                  │ WS2812B   │◄── 20 LEDs, color-coded by RPM zone
                  │ LED Strip │
                  └───────────┘
```

### Why NOT Serial for Arduino

| Factor | Serial from Pi/ESP | Direct CAN ✅ |
|--------|-------------------|---------------|
| Distance | 1-2m through engine bay | Same |
| EMI Resistance | Poor (single-ended) | **Excellent (differential)** |
| Latency | Variable, buffered | **<1ms with interrupt** |
| Reliability | Prone to corruption | **Proven working** |
| Independence | Needs Pi running | **Works standalone** |
| Complexity | Need checksums, retries | **Simple, direct** |

### Benefits of Keeping Direct CAN

1. **EMI Resistant**: CAN differential signaling rejects ignition noise
2. **Time Critical**: Hardware interrupt gives <1ms CAN-to-LED latency
3. **Independent**: LEDs work even if Pi/ESP32 are offline
4. **Proven**: Current code is tested and working in-car
5. **No Protocol Overhead**: Direct RPM parsing, no serial framing

### Arduino CAN Message Parsing

From `arduino/src/main.cpp`:
```cpp
// Fast inline CAN message reading - optimized for RPM extraction
inline void readCANMessages() {
    unsigned long rxId;
    uint8_t len;
    uint8_t rxBuf[8];
    
    while (canBus.checkReceive() == CAN_MSGAVAIL) {
        if (canBus.readMsgBuf(&rxId, &len, rxBuf) == CAN_OK) {
            lastCANData = millis();
            errorMode = false;
            
            // Parse Mazda RPM message (ID 0x201)
            // Format: bytes 0-1 = RPM * 4 (big endian)
            unsigned long canId = rxId & 0x7FFFFFFF;
            if (canId == MAZDA_RPM_CAN_ID && len >= 2) {
                uint16_t rawRPM = ((uint16_t)rxBuf[0] << 8) | rxBuf[1];
                currentRPM = rawRPM >> 2;  // Divide by 4 using bit shift
            }
        }
    }
}
```

### No Migration Needed!

| Component | Status | Notes |
|-----------|--------|-------|
| Arduino Nano | ✅ Keep as-is | Direct CAN, proven working |
| MCP2515 for Arduino | ✅ Keep | Already wired to HS-CAN |
| Arduino Code | ✅ Keep | `arduino/src/main.cpp` unchanged |
| WS2812B LEDs | ✅ Keep | 20 LEDs on D5 |

---

### Complete Physical Wiring

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         COMPLETE WIRING DIAGRAM                              │
│                    (3x MCP2515: Pi×2, Arduino×1)                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                              OBD-II Connector                                │
│                           ┌─────────────────┐                                │
│                           │  1  2  3  4  5  │                                │
│                           │  ●  ●  ●  ●  ●  │                                │
│                           │  6  7  8  9  ... │                                │
│                           │  ●  ●  ●  ●     │                                │
│                           │ 10 11 12 13 14  │                                │
│                           │  ●  ●  ●  ●  ●  │                                │
│                           └───┬──┬─────┬──┬─┘                                │
│                               │  │     │  │                                  │
│          MS-CAN H (Pin 3) ────┘  │     │  └──── HS-CAN L (Pin 14)           │
│          MS-CAN L (Pin 11) ──────┘     └─────── HS-CAN H (Pin 6)            │
│                    │                        │        │                       │
│                    │                        │        │                       │
│                    ▼                        │        │                       │
│            ┌──────────────┐                 │        │                       │
│            │  MCP2515 #2  │                 │        │                       │
│            │   MS-CAN     │                 │        │                       │
│            │   125kbps    │                 │        │                       │
│            │  → Pi CE1    │                 │        │                       │
│            └──────┬───────┘                 │        │                       │
│                   │                         ▼        ▼                       │
│                   │                  ┌──────────────────────┐                │
│                   │                  │      HS-CAN BUS      │                │
│                   │                  │    (multi-tap OK)    │                │
│                   │                  └───────┬────────┬─────┘                │
│                   │                          │        │                      │
│                   │                          ▼        ▼                      │
│                   │                   ┌──────────┐  ┌──────────┐            │
│                   │                   │ MCP2515  │  │ MCP2515  │            │
│                   │                   │ #1 (HS)  │  │ #3 (HS)  │            │
│                   │                   │  → Pi    │  │→ Arduino │            │
│                   │                   │   CE0    │  │   D10    │            │
│                   │                   └────┬─────┘  └────┬─────┘            │
│                   │                        │             │                   │
│                   └────────────┬───────────┘             │                   │
│                                │                         │                   │
│                                ▼                         │                   │
│                    ┌───────────────────────┐             │                   │
│                    │    RASPBERRY PI 4B    │             │                   │
│                    │      (CAN Hub)        │             │                   │
│                    │                       │             │                   │
│                    │  SPI: MCP2515 #1,#2   │             │                   │
│                    │  UART: → ESP32-S3     │             │                   │
│                    │  HDMI: → Pioneer      │             │                   │
│                    └───────────┬───────────┘             │                   │
│                                │                         │                   │
│                    ┌───────────┴───────────┐             │                   │
│                    │                       │             │                   │
│                    ▼                       ▼             ▼                   │
│         ┌─────────────────┐    ┌─────────────────┐  ┌───────────────┐       │
│         │    ESP32-S3     │    │ Pioneer AVH     │  │ Arduino Nano  │       │
│         │  Round Display  │    │   W4500NEX      │  │   RPM LEDs    │       │
│         │                 │    │   (800x480)     │  │               │       │
│         │ Serial from Pi  │    │  HDMI from Pi   │  │ Direct HS-CAN │       │
│         │ BLE TPMS Rx     │    │                 │  │ MCP2515 #3    │       │
│         │ No CAN module   │    │                 │  │ D5 → WS2812B  │       │
│         └─────────────────┘    └─────────────────┘  └───────────────┘       │
│                 ▲                                                            │
│                 │                                                            │
│         BLE TPMS Sensors (x4)                                               │
│         (cap-mounted, wireless)                                             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Button Navigation System

### Button Mapping Concept

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        BUTTON MAPPING CONCEPT                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   LEFT SIDE (Audio)              RIGHT SIDE (Cruise)                        │
│   ═══════════════                ══════════════════                         │
│                                                                              │
│   ┌───────┐                      ┌────────┐  ┌────────┐                     │
│   │  VOL+ │ = ADJUST UP          │ ON/OFF │  │ CANCEL │                     │
│   │   ▲   │                      │ SELECT │  │  BACK  │                     │
│   └───────┘                      └────────┘  └────────┘                     │
│                                                                              │
│   ┌───────┐                      ┌────────┐  ┌────────┐                     │
│   │  VOL- │ = ADJUST DOWN        │  RES+  │  │  SET-  │                     │
│   │   ▼   │                      │   UP   │  │  DOWN  │                     │
│   └───────┘                      └────────┘  └────────┘                     │
│                                                                              │
│   ┌───────┐  ┌───────┐  ┌──────┐                                            │
│   │ SEEK▲ │  │ SEEK▼ │  │ MODE │ ◄── Switch Device/Screen                  │
│   │ RIGHT │  │ LEFT  │  │ SWAP │                                            │
│   └───────┘  └───────┘  └──────┘                                            │
│                                                                              │
│   ┌──────┐                                                                   │
│   │ MUTE │ = TOGGLE DISPLAY/SLEEP                                           │
│   └──────┘                                                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Unified Button Actions

| Button | Global Action | Context-Aware |
|--------|---------------|---------------|
| **MODE** | Switch focus: ESP32 ↔ Pi | Always available |
| **MUTE** | Toggle active display on/off | Sleep mode |
| **CANCEL** | Back / Exit to previous | Universal back |
| **ON/OFF** | Select / Enter / Confirm | Universal select |
| **RES+** | Navigate UP | Scroll up, Zoom in |
| **SET-** | Navigate DOWN | Scroll down, Zoom out |
| **SEEK▲** | Navigate RIGHT | Next item, Pan right |
| **SEEK▼** | Navigate LEFT | Prev item, Pan left |
| **VOL+** | Increase value | Brightness, volume, threshold |
| **VOL-** | Decrease value | Brightness, volume, threshold |

---

## ESP32-S3 Display UI

### Screen Hierarchy

```
                    ┌─────────────────────────────────────┐
                    │           MAIN SCREENS               │
                    │         (MODE cycles →)              │
                    └─────────────────────────────────────┘
                                    │
    ┌───────────┬───────────┬───────┴───────┬───────────┬───────────┐
    ▼           ▼           ▼               ▼           ▼           ▼
┌───────┐  ┌───────┐  ┌───────────┐  ┌───────────┐  ┌───────┐  ┌───────┐
│  RPM  │  │ SPEED │  │  G-FORCE  │  │  ENGINE   │  │  LAP  │  │ SETUP │
│ GAUGE │  │ +GEAR │  │  METER    │  │   TEMPS   │  │ TIMER │  │ MENU  │
└───────┘  └───────┘  └───────────┘  └───────────┘  └───────┘  └───────┘
```

### Screen Designs

#### Screen 1: RPM Gauge
```
        ┌────────────────────────┐
        │     ╭─────────────╮    │
        │   ╭─┤ 3   5   7  ├─╮  │
        │  ╱  │    ╲│╱      │  ╲ │
        │ │ 1 │     │       │ R │ │
        │  ╲  │    ╱│╲      │  ╱ │
        │   ╰─┤             ├─╯  │
        │     ╰─────────────╯    │
        │         3500           │
        │          RPM           │
        └────────────────────────┘
```

#### Screen 2: Speed + Gear
```
        ┌────────────────────────┐
        │                        │
        │          65            │
        │         MPH            │
        │                        │
        │     ┌─────────────┐    │
        │     │      3      │    │
        │     │    GEAR     │    │
        │     └─────────────┘    │
        └────────────────────────┘
```

#### Screen 6: Setup Menu
```
        ┌────────────────────────┐
        │       SETTINGS         │
        ├────────────────────────┤
        │ ▶ Brightness      80%  │
        │   Shift RPM     6500   │
        │   Redline RPM   7200   │
        │   LED Colors   Rainbow │
        │   Units        MPH     │
        │   WiFi         ON      │
        │   ◀ Back               │
        └────────────────────────┘
        
        RES+/SET- = Navigate
        ON/OFF = Select/Edit
        VOL+/- = Adjust value
        CANCEL = Back
```

---

## Raspberry Pi UI

### Home Screen (800x480)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  📺 PI ACTIVE                                            12:34 PM      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│      ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐            │
│      │   🗺️   │   │   🎵   │   │   📊   │   │   ⚙️   │            │
│      │  MAPS   │   │  MUSIC  │   │TELEMETRY│   │SETTINGS │            │
│      │         │   │         │   │         │   │         │            │
│      └─────────┘   └─────────┘   └─────────┘   └─────────┘            │
│          ▲                                                              │
│          └── Currently selected (highlighted)                           │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│   ◀ SEEK    ▲RES+    ●SELECT    ▼SET-    CANCEL▶                       │
└─────────────────────────────────────────────────────────────────────────┘
```

### App Screens

#### Maps App
```
┌───────────────────────────────────────────────────────┐
│   🗺️ MAPS                                   CANCEL   │
├───────────────────────────────────────────────────────┤
│                                                       │
│  ┌─────────────────────────────────────────────────┐ │
│  │                                                 │ │
│  │                   MAP VIEW                      │ │
│  │                                                 │ │
│  │                     📍                          │ │
│  │                                                 │ │
│  └─────────────────────────────────────────────────┘ │
│                                                       │
│  RES+/SET- = Zoom    SEEK = Pan    CANCEL = Back     │
└───────────────────────────────────────────────────────┘
```

#### Music App
```
┌───────────────────────────────────────────────────────┐
│   🎵 MUSIC                                  CANCEL   │
├───────────────────────────────────────────────────────┤
│                                                       │
│           Now Playing:                                │
│           ─────────────                               │
│           Song Title Here                             │
│           Artist Name                                 │
│                                                       │
│              ◀◀  ▶  ▶▶                               │
│           ◀────────●──────▶                          │
│           0:45          3:21                          │
│                                                       │
│  VOL+/- = Volume    SEEK = Track    CANCEL = Back    │
└───────────────────────────────────────────────────────┘
```

#### Telemetry App
```
┌───────────────────────────────────────────────────────┐
│   📊 TELEMETRY                              CANCEL   │
├───────────────────────────────────────────────────────┤
│                                                       │
│   ┌─────────────────┐  ┌─────────────────┐           │
│   │  RPM:    3,500  │  │  Speed:  65 mph │           │
│   │  Gear:      3   │  │  Throttle:  45% │           │
│   └─────────────────┘  └─────────────────┘           │
│                                                       │
│   ┌─────────────────┐  ┌─────────────────┐           │
│   │  ECT:    185°F  │  │  IAT:     95°F  │           │
│   │  AFR:    14.7   │  │  Oil:    210°F  │           │
│   └─────────────────┘  └─────────────────┘           │
│                                                       │
│  RES+/SET- = Scroll    CANCEL = Back                 │
└───────────────────────────────────────────────────────┘
```

---

## State Machine

```
                              ┌──────────────┐
                              │    START     │
                              └──────┬───────┘
                                     │
                                     ▼
                    ┌─────────────────────────────────┐
                    │         DUAL DEVICE MODE        │
                    │   ESP32 = Primary (Gauges)      │
                    │   Pi = Secondary (Apps)         │
                    └─────────────────┬───────────────┘
                                      │
                         ┌────────────┴────────────┐
                         │                         │
                    MODE │                         │ MODE
                         ▼                         ▼
              ┌──────────────────┐      ┌──────────────────┐
              │  ESP32 FOCUSED   │      │    PI FOCUSED    │
              │  ═══════════════ │      │  ═══════════════ │
              │                  │      │                  │
              │  All buttons     │      │  All buttons     │
              │  control ESP32   │◄────▶│  control Pi      │
              │                  │ MODE │  via WiFi/Serial │
              │  Pi shows static │      │  ESP32 shows     │
              │  or auto content │      │  gauges only     │
              └──────────────────┘      └──────────────────┘
                         │                         │
                    MUTE │                         │ MUTE
                         ▼                         ▼
              ┌──────────────────┐      ┌──────────────────┐
              │   ESP32 SLEEP    │      │    PI SLEEP      │
              │   (screen off)   │      │   (screen dim)   │
              └──────────────────┘      └──────────────────┘
```

---

## Quick Reference Card

```
╔═══════════════════════════════════════════════════════════════════════╗
║                    MX5 STEERING WHEEL CONTROLS                         ║
╠═══════════════════════════════════════════════════════════════════════╣
║                                                                        ║
║   MODE ─────── Switch between ESP32 and Pi control                    ║
║   MUTE ─────── Toggle display sleep/wake                              ║
║                                                                        ║
║   ON/OFF ───── SELECT / ENTER / CONFIRM                               ║
║   CANCEL ───── BACK / EXIT / ESCAPE                                   ║
║                                                                        ║
║   RES+ ─────── UP / SCROLL UP / ZOOM IN                               ║
║   SET- ─────── DOWN / SCROLL DOWN / ZOOM OUT                          ║
║   SEEK▲ ────── RIGHT / NEXT                                           ║
║   SEEK▼ ────── LEFT / PREVIOUS                                        ║
║                                                                        ║
║   VOL+ ─────── INCREASE (volume, brightness, value)                   ║
║   VOL- ─────── DECREASE (volume, brightness, value)                   ║
║                                                                        ║
╚═══════════════════════════════════════════════════════════════════════╝
```

---

## Implementation Phases

### Phase 1: CAN Bus Reading ✅
- [ ] Wire MCP2515 #1 to HS-CAN
- [ ] Wire MCP2515 #2 to MS-CAN
- [ ] Verify CAN message reading
- [ ] Identify exact SWC button CAN IDs by sniffing

### Phase 2: ESP32-S3 Display
- [ ] Set up ESP32-S3 with round display
- [ ] Implement dual MCP2515 SPI reading
- [ ] Create gauge UI screens
- [ ] Implement button navigation
- [ ] Forward RPM to Arduino via Serial

### Phase 3: Raspberry Pi Integration
- [ ] Set up WiFi/Serial communication from ESP32
- [ ] Create Pi button daemon (receives commands, simulates keypresses)
- [ ] Build Pi launcher application
- [ ] Configure HDMI output for AVH-W4500NEX (800x480)

### Phase 4: Integration & Testing
- [ ] Test in-car with real CAN data
- [ ] Fine-tune button mappings
- [ ] Optimize display refresh rates
- [ ] Power management (sleep/wake)

---

## Parts List

| Item | Qty | Est. Cost | Notes |
|------|-----|-----------|-------|
| MCP2515 CAN Module | 2 | $10 | For Raspberry Pi (HS + MS CAN) |
| ESP32-S3 1.85" Round Display | 1 | $25 | Waveshare/AliExpress |
| OBD-II Breakout/Splitter | 1 | $15 | Access CAN bus pins |
| Jumper Wires (M-F, M-M) | 1 pack | $8 | Various connections |
| LM2596 Buck Converter | 1 | $8 | 12V → 5V 3A (already in use) |
| Project Enclosure | 1 | $10 | Mount electronics |
| BLE TPMS Sensors | 4 | $30 | ✅ Ordered - cap-mounted |
| **Already Owned** | | | |
| Arduino Nano | 1 | - | ✅ Existing (keeps direct CAN) |
| WS2812B LED Strip (20) | 1 | - | ✅ Existing |
| MCP2515 CAN Module | 1 | - | ✅ Existing (stays with Arduino for HS-CAN) |
| Raspberry Pi 4B | 1 | - | ✅ Existing |
| **Total New Parts** | | **~$96** | |

### MCP2515 Module Allocation

| Module | Connected To | CAN Bus | Purpose |
|--------|--------------|---------|--------|
| MCP2515 #1 | Pi GPIO 8 (CE0) | HS-CAN (500k) | RPM, Speed, Temps, Gear |
| MCP2515 #2 | Pi GPIO 7 (CE1) | MS-CAN (125k) | SWC Buttons, Body data |
| MCP2515 #3 | Arduino D10 | HS-CAN (500k) | RPM only (shift light) |

---

## Raspberry Pi Configuration

### Current Setup (192.168.1.28)
- **OS**: Debian Buster (Raspberry Pi OS)
- **HDMI**: 800x480 @ 60Hz (Pioneer native resolution)
- **Boot Config**: `hdmi_force_hotplug=1` enabled for headless operation
- **VNC**: Enabled for remote access
- **SSH**: Key-based authentication configured
- **Wallpaper**: MX5 custom image

### Installed Touch/Input Tools
- `onboard` - On-screen keyboard (auto-show enabled)
- `matchbox-keyboard` - Lightweight keyboard alternative  
- `xdotool` - Simulate mouse/keyboard input
- `unclutter` - Auto-hide cursor

---

## Revision History

| Date | Version | Changes |
|------|---------|---------|
| 2025-12-08 | 0.1 | Initial concept document |

---

## BLE TPMS Integration

### Overview

The 2008 MX5 NC uses **Direct TPMS** with 315MHz RF sensors - these only send low-pressure warnings to the gauge cluster, **not actual PSI values on CAN bus**. To get real tire pressure data, we use aftermarket **BLE TPMS cap sensors**.

### Hardware

| Item | Details |
|------|--------|
| Sensors | 4x BLE TPMS external cap sensors (ordered) |
| Receiver | ESP32-S3 built-in Bluetooth (no extra hardware!) |
| Protocol | BLE advertisement broadcast |

### BLE TPMS Protocol (Decoded)

These sensors broadcast manufacturer data in BLE advertisements:

```
Manufacturer Data: 000180EACA108A78E36D0000E60A00005B00
                   │  │  │     │       │       │  └─ Alarm (00=OK)
                   │  │  │     │       │       └──── Battery %
                   │  │  │     │       └──────────── Temperature (°C)
                   │  │  │     └──────────────────── Pressure (kPa)
                   │  │  └────────────────────────── Sensor Address
                   │  └───────────────────────────── Address Prefix  
                   └──────────────────────────────── Sensor # (80-83)
```

### Data Extraction

```cpp
// Pressure (bytes 8-11) - Little Endian
long pressureRaw = byte8 | (byte9 << 8) | (byte10 << 16) | (byte11 << 24);
float pressure_kPa = pressureRaw / 1000.0;
float pressure_psi = pressure_kPa * 0.145038;

// Temperature (bytes 12-15) - Little Endian  
long tempRaw = byte12 | (byte13 << 8) | (byte14 << 16) | (byte15 << 24);
float temp_C = tempRaw / 100.0;

// Battery (byte 16)
int battery_percent = byte16;
```

### ESP32-S3 TPMS Code (Example)

```cpp
#include <BLEDevice.h>
#include <BLEScan.h>

BLEScan* pBLEScan;

class TPMSCallback : public BLEAdvertisedDeviceCallbacks {
    void onResult(BLEAdvertisedDevice device) {
        if (device.haveName() && device.getName() == "BR") {
            // This is a TPMS sensor
            std::string mfgData = device.getManufacturerData();
            if (mfgData.length() >= 18) {
                uint8_t sensorNum = mfgData[2] - 0x80;  // 0-3
                // Extract pressure, temp, battery...
                // Send to Pi via Serial
            }
        }
    }
};

void setup() {
    Serial.begin(115200);  // To Raspberry Pi
    BLEDevice::init("");
    pBLEScan = BLEDevice::getScan();
    pBLEScan->setAdvertisedDeviceCallbacks(new TPMSCallback());
    pBLEScan->setActiveScan(true);
}

void loop() {
    pBLEScan->start(5, false);  // Scan for 5 seconds
    delay(1000);
}
```

### Serial Protocol (ESP32-S3 → Pi)

```
TPMS:0,32.5,25.3,95\n    // Tire 0: 32.5 PSI, 25.3°C, 95% battery
TPMS:1,31.8,24.1,92\n    // Tire 1: 31.8 PSI, 24.1°C, 92% battery
TPMS:2,33.1,26.0,88\n    // Tire 2: 33.1 PSI, 26.0°C, 88% battery
TPMS:3,32.9,25.8,90\n    // Tire 3: 32.9 PSI, 25.8°C, 90% battery
```

### Resources

- GitHub: `ra6070/BLE-TPMS` - ESP32 Arduino code
- GitHub: `andi38/TPMS` - Protocol documentation
- GitHub: `bkbilly/tpms_ble` - Home Assistant integration

---

## Notes & Ideas

- Consider adding voice control via ESP32-S3's speech recognition
- Could add lap timer functionality with GPS module
- Bluetooth OBD adapter as backup/alternative to wired CAN
- Android Auto via OpenAuto Pro as future enhancement
- TPMS alerts: flash LED strip or beep when tire pressure low
