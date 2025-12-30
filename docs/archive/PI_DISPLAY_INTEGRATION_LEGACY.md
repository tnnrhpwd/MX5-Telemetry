# MX5 Raspberry Pi + ESP32-S3 Display Integration

## Project Overview

Integrate a Raspberry Pi 4B (HDMI output to Pioneer AVH-W4500NEX) and ESP32-S3 Round Display (mounted in stock oil gauge location) into the 2008 MX5 NC GT, controlled via stock steering wheel buttons through CAN bus.

### Goals ✅ IMPLEMENTED
- Display telemetry data on ESP32-S3 round LCD (gauges, RPM, speed) - **replaces stock oil gauge**
- Display telemetry data on Raspberry Pi via HDMI to Pioneer aftermarket head unit
- Display tire pressure from BLE TPMS sensors on both displays
- Display G-force data from ESP32-S3's onboard IMU on both displays
- Control both devices using stock MX5 steering wheel buttons (no touch needed)
- Read vehicle data from HS-CAN and MS-CAN buses
- Arduino LED strip around gauge cluster for RPM visualization (direct CAN for <1ms latency)
- Pi caches all settings and syncs to ESP32 and Arduino on startup

### Physical Mounting

| Device | Location | Notes |
|--------|----------|-------|
| **Raspberry Pi 4B** | Hidden (center console/trunk) | Central hub |
| **ESP32-S3 Round Display** | **Stock oil gauge hole** | 1.85" fits perfectly |
| **Arduino Nano + LEDs** | Gauge cluster bezel | LED strip surrounds instruments |
| **Pioneer Head Unit** | Stock head unit location | Aftermarket with HDMI input |

### UI Implementation Summary

Both displays share a synchronized **8-screen interface**:

| Screen | Name | Key Data |
|--------|------|----------|
| 0 | **Overview** | Gear, speed, mini TPMS, alerts |
| 1 | **RPM/Speed** | RPM gauge, gear, shift light, lap time |
| 2 | **TPMS** | 4-corner tire pressure & temperature |
| 3 | **Engine** | Coolant, oil, fuel, voltage |
| 4 | **G-Force** | IMU-based lateral/longitudinal G |
| 5 | **Diagnostics** | CEL, ABS, DTC codes, wheel slip |
| 6 | **System** | CPU, memory, network, CAN status |
| 7 | **Settings** | Brightness, shift RPM, warnings, units, LED pattern |

**Navigation**: RES+/SET- (↑/↓) to cycle screens, VOL+/VOL- (→/←) also navigates, ON/OFF to select, CANCEL to back, MUTE for sleep mode. **RPM/Speed screen**: ON/OFF starts/stops lap timer, CANCEL resets.

---

## Hardware Components

| Component | Purpose | Location | Docs |
|-----------|---------|----------|------|
| Raspberry Pi 4B | CAN hub + settings cache + HDMI output | Hidden (console/trunk) | - |
| ESP32-S3 Round Display | 1.85" gauge display + BLE TPMS + IMU | **Stock oil gauge hole** | - |
| Arduino Nano | RPM LED strip controller (direct CAN) | Gauge cluster bezel | [WIRING_GUIDE.md](hardware/WIRING_GUIDE.md) |
| MCP2515 Module x3 | Pi (HS + MS), Arduino (HS) - **HS-CAN shared** | - | [WIRING_GUIDE.md](hardware/WIRING_GUIDE.md) |
| Pioneer AVH-W4500NEX | Aftermarket head unit with HDMI input | Stock head unit location | - |
| WS2812B LED Strip | RPM shift light (20 LEDs) | Around gauge cluster | [WIRING_GUIDE.md](hardware/WIRING_GUIDE.md) |
| OBD-II Breakout/Splitter | Access CAN bus pins | Under dash | [WIRING_GUIDE.md](hardware/WIRING_GUIDE.md) |
| LM2596 Buck Converter | 12V → 5V power | - | [WIRING_GUIDE.md](hardware/WIRING_GUIDE.md) |
| BLE TPMS Sensors (4x) | Tire pressure + temp → ESP32 BLE | On each tire valve | ✅ Ordered |

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
│           (Pi as Hub + Settings Cache, Arduino Direct CAN for RPM)          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                         OBD-II PORT                                  │   │
│   │   Pin 6 ───┬─── HS-CAN High (500kbps) ─── SHARED: Pi + Arduino      │   │
│   │   Pin 14 ──┼─── HS-CAN Low                                          │   │
│   │   Pin 3 ───┼─── MS-CAN High (125kbps) ─── Pi only                   │   │
│   │   Pin 11 ──┴─── MS-CAN Low                                          │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                 │                              │                             │
│                 ▼                              ▼                             │
│   ════════════════════════        ════════════════════════                  │
│      HS-CAN BUS (500k)               MS-CAN BUS (125k)                      │
│       (SHARED by Pi + Arduino)           (Pi only)                          │
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
│   │             RASPBERRY PI 4B (CENTRAL HUB + SETTINGS CACHE)           │   │
│   │                        [Hidden in console/trunk]                     │   │
│   │                                                                      │   │
│   │  • Reads HS-CAN (RPM, Speed, Throttle, Temps, Gear)                 │   │
│   │  • Reads MS-CAN (Steering Wheel Buttons, Cruise, Body)              │   │
│   │  • Receives BLE TPMS data from ESP32-S3                             │   │
│   │  • Receives G-Force IMU data from ESP32-S3                          │   │
│   │  • Sends all telemetry + SWC to ESP32-S3 via Serial                 │   │
│   │  • Sends LED sequence selection to Arduino via Serial               │   │
│   │  • CACHES ALL SETTINGS - syncs to devices on startup                │   │
│   │  • Displays telemetry on HDMI → Pioneer AVH-W4500NEX                │   │
│   │                                                                      │   │
│   └────────┬─────────────────────────┬────────────────┬─────────────────┘   │
│            │                         │                │                      │
│            │ Serial/UART             │ HDMI           │ Serial/UART          │
│            │ (GPIO 14/15)            │                │ (to Arduino)         │
│            │ ~20cm shielded          │                │                      │
│            ▼                         ▼                ▼                      │
│   ┌─────────────────────┐   ┌─────────────────┐   ┌─────────────────────┐   │
│   │     ESP32-S3        │   │  Pioneer AVH    │   │    Arduino Nano     │   │
│   │   Round Display     │   │    -W4500NEX    │   │     RPM LEDs        │   │
│   │                     │   │   (800x480)     │   │                     │   │
│   │ [Oil gauge hole]    │   └─────────────────┘   │ [Gauge cluster      │   │
│   │                     │                         │  bezel]             │   │
│   │  • Receives data    │                         │                     │   │
│   │    from Pi (Serial) │                         │  • Reads RPM direct │   │
│   │  • Receives SWC     │                         │    from HS-CAN      │   │
│   │    button events    │                         │  • Receives LED     │   │
│   │  • BLE TPMS Rx ─────│◄──── BLE TPMS Sensors   │    sequence from Pi │   │
│   │  • Round LCD gauge  │      (x4 cap-mount)     │  • Drives WS2812B   │   │
│   │  • Forwards TPMS    │                         │    LED strip        │   │
│   │    to Pi (Serial)   │                         │  • Works offline    │   │
│   │  • QMI8658 IMU ─────│──── G-Force data to Pi  │    (defaults)       │   │
│   │  • NO CAN MODULE    │                         │                     │   │
│   └─────────────────────┘                         └─────────────────────┘   │
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
│   │               RASPBERRY PI 4B (CAN HUB + SETTINGS CACHE)             │   │
│   │                                                                      │   │
│   │  INPUTS:                          OUTPUTS:                           │   │
│   │  ├─ MCP2515 #1 (HS-CAN 500k)      ├─► ESP32-S3 (Serial TX)          │   │
│   │  │  • RPM, Speed, Throttle        │   • All CAN telemetry            │   │
│   │  │  • Temps, Gear, Brake          │   • SWC button events            │   │
│   │  │  • Wheel Speeds, Steering      │   • Settings sync on startup     │   │
│   │  │                                │   (short cable, low EMI)         │   │
│   │  ├─ MCP2515 #2 (MS-CAN 125k)      │                                  │   │
│   │  │  • SWC Buttons (screen nav) ───┼─► ESP32 + Pi UI control         │   │
│   │  │  • Cruise Control              │                                  │   │
│   │  │  • Lights, Doors, Climate      ├─► Arduino (Serial TX)           │   │
│   │  │  • Fuel Level/Consumption      │   • LED sequence selection       │   │
│   │  │                                │   • Settings sync on startup     │   │
│   │  └─ ESP32-S3 (Serial RX) ◄────────│                                  │   │
│   │     • Tire Pressure (x4)          ├─► Pioneer (HDMI)                │   │
│   │     • Tire Temp (x4)              │   • Full UI display              │   │
│   │     • TPMS Battery %              │                                  │   │
│   │     • G-Force (lateral/long)      │◄── QMI8658 IMU on ESP32          │   │
│   │                                   │                                  │   │
│   │  SETTINGS CACHE:                  │                                  │   │
│   │  • Brightness levels              │                                  │   │
│   │  • Shift RPM threshold            │                                  │   │
│   │  • LED pattern/sequence           │ ← Sends to Arduino on startup   │   │
│   │  • Warning thresholds             │                                  │   │
│   │  • Units (mph/kph, °F/°C)         │                                  │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                   ESP32-S3 ROUND DISPLAY                             │   │
│   │             (Mounted in stock oil gauge hole)                        │   │
│   │                    (NO CAN - Serial Only)                            │   │
│   │                                                                      │   │
│   │  INPUTS:                          OUTPUTS:                           │   │
│   │  ├─ Pi (Serial RX)                ├─► Pi (Serial TX)                │   │
│   │  │  • All CAN telemetry           │   • TPMS data (BLE sensors)     │   │
│   │  │  • SWC button events ──────────┼─► Round LCD Display             │   │
│   │  │    (to control ESP UI)         │   • Gauges, TPMS, Alerts        │   │
│   │  │  • Settings sync on startup    │   • G-Force data (QMI8658 IMU)  │   │
│   │  │                                │                                  │   │
│   │  ├─ BLE (built-in)                │                                  │   │
│   │  │  • TPMS cap sensors (x4)       │                                  │   │
│   │  │                                │                                  │   │
│   │  └─ QMI8658 IMU (built-in)        │                                  │   │
│   │     • Accelerometer (±16g)        │                                  │   │
│   │     • Gyroscope (±2048°/s)        │                                  │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    ARDUINO NANO (DIRECT HS-CAN)                      │   │
│   │              (LED strip around gauge cluster bezel)                  │   │
│   │                                                                      │   │
│   │  INPUTS:                          OUTPUTS:                           │   │
│   │  ├─ MCP2515 #3 (HS-CAN 500k)      └─► WS2812B LED Strip             │   │
│   │  │  • RPM (0x201)                     • 20 LEDs, shift light         │   │
│   │  │  • Direct from OBD-II              • <1ms CAN-to-LED latency      │   │
│   │  │  • SHARED bus with Pi MCP2515#1    • Works even if Pi offline     │   │
│   │  │                                                                   │   │
│   │  └─ Pi (Serial RX)                                                   │   │
│   │     • LED sequence/pattern selection                                 │   │
│   │     • Settings sync on startup (which LED animation to use)         │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   SUMMARY:                                                                   │
│   ═══════                                                                    │
│   Pi → ESP32:  CAN data + SWC buttons + settings sync (serial)              │
│   ESP32 → Pi:  TPMS data + G-Force IMU data                                 │
│   Pi → Arduino: LED sequence selection + settings sync (serial)             │
│   Arduino CAN: DIRECT HS-CAN via MCP2515 #3 (shared bus with Pi)            │
│                                                                              │
│   WHY ARDUINO USES DIRECT CAN FOR RPM:                                       │
│   • RPM timing critical (<50ms for shift light)                             │
│   • Long wire run through high-EMI engine bay                               │
│   • CAN differential signaling resists noise                                │
│   • Already working and proven reliable                                      │
│   • Serial from Pi only for LED pattern selection (not time-critical)       │
│                                                                              │
│   SETTINGS CACHE (Pi manages all settings):                                  │
│   • Pi stores all user preferences in config file                           │
│   • On startup, Pi sends settings to ESP32 and Arduino                      │
│   • Settings changed via SWC navigation → saved to Pi → synced to devices   │
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
| **D3** | Serial RX | Pi GPIO 14 (TXD) - LED sequence commands (SoftwareSerial) |
| **D4** | Serial TX | Pi GPIO 15 (RXD) - LED sequence responses (SoftwareSerial) |
| **D5** | LED Data | WS2812B Data In (330Ω resistor recommended) |
| **D10** | CAN CS | MCP2515 CS (SPI chip select) |
| **D11** | SPI MOSI | MCP2515 SI |
| **D12** | SPI MISO | MCP2515 SO |
| **D13** | SPI SCK | MCP2515 SCK |
| **5V** | Power | VCC from LM2596 buck converter |
| **GND** | Ground | Common ground (shared with Pi) |

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

### Pi → Arduino Serial (LED Sequence Settings)

While RPM data comes from direct CAN for time-critical performance, **LED sequence settings** are sent via serial from the Pi. This is acceptable because:

1. **Not time-critical**: Sequence changes happen once at startup or on user input
2. **Short, infrequent messages**: `SEQ:1\n` to `SEQ:4\n` commands only
3. **Arduino caches in EEPROM**: Setting persists across power cycles

#### Serial Connection

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PI → ARDUINO SERIAL (LED SEQUENCE)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Raspberry Pi 4B                    Arduino Nano                            │
│   ═══════════════                    ═══════════════                         │
│                                                                              │
│   GPIO 14 (TXD0) ─────────────────→ D3 (SoftwareSerial RX)                  │
│   GND ────────────────────────────→ GND (shared)                            │
│                                                                              │
│   ⚠️  Optional: GPIO 15 (RXD0) ←── D4 (SoftwareSerial TX) for responses    │
│   ⚠️  3.3V/5V level: Arduino input is 3.3V tolerant, TX divider optional   │
│   ⚠️  Baud rate: 9600 bps (low speed for reliability)                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### LED Sequence Serial Protocol

| Command | Description | Arduino Response |
|---------|-------------|------------------|
| `SEQ:1\n` | Center-Out (default) | `OK:1\n` |
| `SEQ:2\n` | Left-to-Right (2x resolution) | `OK:2\n` |
| `SEQ:3\n` | Right-to-Left | `OK:3\n` |
| `SEQ:4\n` | Center-In | `OK:4\n` |
| `SEQ?\n` | Query current sequence | `SEQ:n\n` |
| `PING\n` | Connection test | `PONG\n` |

#### LED Sequence Modes

| Mode | Name | Description | Use Case |
|------|------|-------------|----------|
| 1 | **Center-Out** | LEDs fill from center toward edges | Default, symmetric look |
| 2 | **Left-to-Right** | LEDs fill from left to right | 2x resolution (no center split) |
| 3 | **Right-to-Left** | LEDs fill from right to left | Mirror of L→R |
| 4 | **Center-In** | LEDs fill from edges toward center | Inverse of default |

#### EEPROM Storage

Arduino saves LED sequence to EEPROM (survives power loss):
- **Address 0**: Magic byte (0xA5) to detect valid data
- **Address 1**: LED sequence (1-4)

```cpp
// On startup, load from EEPROM
if (EEPROM.read(0) == 0xA5) {
    currentSequence = EEPROM.read(1);
}

// On serial command, save to EEPROM
EEPROM.write(0, 0xA5);
EEPROM.write(1, currentSequence);
```

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

## Button Navigation System (Implemented)

### Steering Wheel Button Mapping

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    IMPLEMENTED BUTTON MAPPING                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   LEFT SIDE (Audio Controls)           RIGHT SIDE (Cruise Controls)         │
│   ══════════════════════════           ════════════════════════════         │
│                                                                              │
│   ┌───────┐                            ┌────────┐  ┌────────┐               │
│   │  VOL+ │ = RIGHT / Next Screen      │ ON/OFF │  │ CANCEL │               │
│   │   →   │   Increase (settings)      │ SELECT │  │  BACK  │               │
│   └───────┘                            │ ENTER  │  │  EXIT  │               │
│                                        └────────┘  └────────┘               │
│   ┌───────┐                                                                  │
│   │  VOL- │ = LEFT / Previous Screen   ┌────────┐  ┌────────┐               │
│   │   ←   │   Decrease (settings)      │  RES+  │  │  SET-  │               │
│   └───────┘                            │   UP   │  │  DOWN  │               │
│                                        │  PREV  │  │  NEXT  │               │
│   ┌───────┐  ┌───────┐  ┌──────┐       └────────┘  └────────┘               │
│   │ SEEK▲ │  │ SEEK▼ │  │ MODE │                                            │
│   │(track)│  │(track)│  │(src) │ ◄── Not used in current implementation     │
│   └───────┘  └───────┘  └──────┘                                            │
│                                                                              │
│   ┌──────┐                                                                   │
│   │ MUTE │ = Toggle Sleep Mode                                              │
│   └──────┘   (minimal UI / screen dim)                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Keyboard Mapping (Development/Testing)

For testing without CAN bus hardware:

| Key | SWC Equivalent | Action |
|-----|----------------|--------|
| **↑ / W** | RES+ | Previous screen / Navigate up |
| **↓ / S** | SET- | Next screen / Navigate down |
| **→ / D** | VOL+ | Next screen / Increase value |
| **← / A** | VOL- | Previous screen / Decrease value |
| **Enter** | ON/OFF | Select / Confirm / Start-Stop |
| **B** | CANCEL | Back / Exit / Reset |
| **ESC** | - | Exit application |

### Button Actions by Context

| Button | Normal Screens | Settings Screen | RPM/Speed Screen |
|--------|----------------|-----------------|------------------|
| **RES+ (↑)** | Previous screen | Navigate up in menu | Previous screen |
| **SET- (↓)** | Next screen | Navigate down in menu | Next screen |
| **VOL+ (→)** | Next screen | Increase selected value | Next screen |
| **VOL- (←)** | Previous screen | Decrease selected value | Previous screen |
| **ON/OFF** | - | Select/Edit setting | **Start/Stop Lap Timer** |
| **CANCEL** | - | Exit edit / Back | **Reset Lap Timer** |
| **MUTE** | Toggle sleep mode | Toggle sleep mode | Toggle sleep mode |

### RPM/Speed Screen - Lap Timer Controls

The RPM/Speed screen (Screen 1) has special lap timer functionality:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        LAP TIMER CONTROLS                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ON/OFF (Enter)  = Start / Stop lap timer                                  │
│                     • Starting resets timer to 0:00.00                      │
│                     • Stopping records best lap if faster                   │
│                                                                              │
│   CANCEL (B key)  = Reset lap timer                                         │
│                     • Resets timer to 0:00.00                               │
│                     • Stops timer if running                                │
│                                                                              │
│   Visual Indicators:                                                        │
│   • "● RUN" (green) = Timer is running                                      │
│   • "○ STOP" (gray) = Timer is stopped                                      │
│   • Button hints shown at bottom: "ENTER: Start/Stop   B: Reset"           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Navigation Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        SCREEN NAVIGATION FLOW                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   NORMAL MODE (viewing screens):                                            │
│   ══════════════════════════════                                            │
│                                                                              │
│       ┌─────────────────────────────────────────────────────────────┐       │
│       │                                                             │       │
│       ▼                                                             │       │
│   ┌───────┐  SET-/→  ┌───────┐  SET-/→  ┌───────┐        ┌───────┐        │
│   │Screen │ ────────► │Screen │ ────────► │Screen │  ...   │Screen │        │
│   │   0   │ ◄──────── │   1   │ ◄──────── │   2   │  ...   │   7   │        │
│   └───────┘  RES+/←  └───────┘  RES+/←  └───────┘        └───────┘        │
│       ▲                                                             │       │
│       │                       (wraps around)                        │       │
│       └─────────────────────────────────────────────────────────────┘       │
│                                                                              │
│                                                                              │
│   SETTINGS MODE (Screen 7):                                                 │
│   ═════════════════════════                                                 │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  SETTINGS SCREEN (scrollable list)                                  │   │
│   │                                                                     │   │
│   │  [Back]          ◄── Select with ON/OFF to return to Overview      │   │
│   │  Brightness      ◄── RES+/SET- to navigate, ON/OFF to edit         │   │
│   │  Shift RPM           VOL+/VOL- to adjust value when editing        │   │
│   │  Redline RPM                                                        │   │
│   │  Units (MPH/KPH)                                                    │   │
│   │  Low Tire PSI                                                       │   │
│   │  Coolant Warning                                                    │   │
│   │  Demo Mode                                                          │   │
│   │                                                                     │   │
│   │  CANCEL          = Exit edit mode / Return to screens              │   │
│   │                                                                     │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### CAN Bus Button Detection

Buttons are read from MS-CAN bus (125 kbps):

| Button | CAN ID | Byte 0 Value | Detected Event |
|--------|--------|--------------|----------------|
| Volume Up | `0x240` | `0x01` | `SWC_VOL_UP` |
| Volume Down | `0x240` | `0x02` | `SWC_VOL_DOWN` |
| Mode/Source | `0x240` | `0x04` | `SWC_MODE` |
| Seek/Track Up | `0x240` | `0x08` | `SWC_SEEK_UP` |
| Seek/Track Down | `0x240` | `0x10` | `SWC_SEEK_DOWN` |
| Mute | `0x240` | `0x20` | `SWC_MUTE` |
| Cruise ON/OFF | `0x250` | `0x01` | `SWC_CRUISE_ON` |
| Cruise Cancel | `0x250` | `0x02` | `SWC_CRUISE_CANCEL` |
| Cruise RES+ | `0x250` | `0x04` | `SWC_CRUISE_RES` |
| Cruise SET- | `0x250` | `0x08` | `SWC_CRUISE_SET` |

> ⚠️ **Note**: Exact CAN IDs verified by sniffing actual bus traffic

---

## ESP32-S3 Display UI (Implemented)

### Screen Overview (8 Screens)

Both ESP32-S3 and Raspberry Pi share a synchronized 8-screen structure for consistency.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ESP32-S3 SCREEN HIERARCHY                             │
│                         (RES+/SET- cycles screens)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Screen 0      Screen 1      Screen 2      Screen 3                        │
│  ┌────────┐    ┌────────┐    ┌────────┐    ┌────────┐                       │
│  │OVERVIEW│────│RPM/SPEED────│  TPMS  │────│ ENGINE │                       │
│  │        │    │        │    │        │    │        │                       │
│  └────────┘    └────────┘    └────────┘    └────────┘                       │
│       │                                          │                           │
│       └──────────────────────────────────────────┘                           │
│                          │                                                   │
│   Screen 4      Screen 5 │    Screen 6      Screen 7                        │
│  ┌────────┐    ┌────────┐│   ┌────────┐    ┌────────┐                       │
│  │G-FORCE │────│DIAGNOS-│────│ SYSTEM │────│SETTINGS│                       │
│  │        │    │  TICS  │    │        │    │        │                       │
│  └────────┘    └────────┘    └────────┘    └────────┘                       │
│                                                                              │
│   Navigation: RES+ = Previous Screen | SET- = Next Screen                   │
│               Touch zones also work (top/bottom swipe)                       │
│               Dot indicators at bottom show current position                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Screen Details

| # | Screen | Purpose | Data Displayed |
|---|--------|---------|----------------|
| 0 | **Overview** | At-a-glance dashboard | Gear, speed, mini TPMS with car silhouette, alert summary |
| 1 | **RPM/Speed** | Primary driving data | RPM arc gauge, gear indicator, speed, shift light |
| 2 | **TPMS** | Tire monitoring | 4-corner pressure/temperature with car silhouette |
| 3 | **Engine** | Engine vitals | Coolant temp, oil temp, fuel gauge, voltage |
| 4 | **G-Force** | Acceleration display | 2D G-ball visualization from QMI8658 IMU |
| 5 | **Diagnostics** | Vehicle warnings | CEL, ABS, TC warnings, DTC codes, wheel slip |
| 6 | **System** | ESP32 diagnostics | CPU temp, frequency, heap memory, PSRAM, uptime |
| 7 | **Settings** | Configuration | Brightness, shift RPM, redline, units, warnings |

### Screen Designs (360×360 Round Display)

#### Screen 0: Overview
```
        ┌────────────────────────┐
        │      ╭───────────╮     │
        │    ╭─│  65 MPH   │─╮   │
        │   │  │    ⚡3     │  │  │
        │   │  ├───────────┤  │  │
        │   │  │  32│  │32 │  │  │  ← Mini TPMS
        │   │  │   [🚗]    │  │  │    with car
        │   │  │  32│  │32 │  │  │    silhouette
        │   │  ├───────────┤  │  │
        │   │  │ ⚠️ 2 ALERTS│  │  │
        │    ╰─│           │─╯   │
        │      ╰───────────╯     │
        │      ● ○ ○ ○ ○ ○ ○ ○   │  ← Screen indicator dots
        └────────────────────────┘
```

#### Screen 1: RPM/Speed
```
        ┌────────────────────────┐
        │     ╭─────────────╮    │
        │   ╭─┤ 3   5   7  ├─╮  │
        │  ╱  │    ╲│╱      │  ╲ │  ← RPM arc gauge
        │ │ 1 │  ▓▓▓▓▓░░░░  │ R │ │    (color-coded zones)
        │  ╲  │    ╱│╲      │  ╱ │
        │   ╰─┤             ├─╯  │
        │     │    3500     │    │
        │     │     ⚡3      │    │  ← Gear indicator
        │     │   65 MPH    │    │
        │     ╰─────────────╯    │
        │      ○ ● ○ ○ ○ ○ ○ ○   │
        └────────────────────────┘
```

#### Screen 2: TPMS
```
        ┌────────────────────────┐
        │         TPMS           │
        │  ┌──────┐  ┌──────┐    │
        │  │32 PSI│  │32 PSI│    │  ← Front tires
        │  │ 75°F │  │ 76°F │    │
        │  └──────┘  └──────┘    │
        │       [  🚗  ]         │  ← Car silhouette
        │  ┌──────┐  ┌──────┐    │
        │  │32 PSI│  │32 PSI│    │  ← Rear tires
        │  │ 74°F │  │ 75°F │    │
        │  └──────┘  └──────┘    │
        │      ○ ○ ● ○ ○ ○ ○ ○   │
        └────────────────────────┘
```

#### Screen 3: Engine
```
        ┌────────────────────────┐
        │        ENGINE          │
        │   ┌─────────────────┐  │
        │   │  COOLANT  195°F │  │  ← Circular gauge
        │   │    ╭───╮        │  │
        │   │   │▓▓▓░│        │  │
        │   │    ╰───╯        │  │
        │   ├─────────────────┤  │
        │   │  OIL TEMP 210°F │  │
        │   │  FUEL      65%  │  │
        │   │  VOLTAGE  14.2V │  │
        │   └─────────────────┘  │
        │      ○ ○ ○ ● ○ ○ ○ ○   │
        └────────────────────────┘
```

#### Screen 4: G-Force
```
        ┌────────────────────────┐
        │       G-FORCE          │
        │   ┌─────────────────┐  │
        │   │    ╭─────╮      │  │
        │   │   ╱   ●   ╲     │  │  ← G-ball position
        │   │  │    │    │    │  │    from IMU
        │   │   ╲       ╱     │  │
        │   │    ╰─────╯      │  │
        │   ├─────────────────┤  │
        │   │ LAT: +0.25G     │  │
        │   │ LON: -0.15G     │  │
        │   └─────────────────┘  │
        │      ○ ○ ○ ○ ● ○ ○ ○   │
        └────────────────────────┘
```

#### Screen 7: Settings
```
        ┌────────────────────────┐
        │       SETTINGS         │
        ├────────────────────────┤
        │ ▶ Brightness      80%  │
        │   Shift RPM     6500   │
        │   Redline RPM   7200   │
        │   Units          MPH   │
        │   Low Tire PSI  28.0   │
        │   Coolant Warn  220°F  │
        └────────────────────────┘
        
        RES+/SET- = Navigate settings
        ON/OFF = Select/Enter edit mode
        VOL+/- = Adjust selected value
        CANCEL = Back / Exit settings
```

### ESP32 Touch Navigation

The round display supports touch input with 5 zones (matching SWC buttons):

```
              ┌─────────────┐
              │     TOP     │ ← Tap: RES+ (Previous screen)
              │   (y<120)   │
        ┌─────┼─────────────┼─────┐
        │LEFT │   CENTER    │RIGHT│
        │VOL- │  ON/OFF     │VOL+ │ ← Tap: Select/Enter
        │(x<120)           (x>240)│
        └─────┼─────────────┼─────┘
              │   BOTTOM    │ ← Tap: SET- (Next screen)
              │   (y>240)   │
              └─────────────┘
              
        Swipe Up   = RES+ (Previous screen)
        Swipe Down = SET- (Next screen)
```

---

## Raspberry Pi UI (Implemented)

### Screen Overview (8 Screens - Mirrored from ESP32)

The Pi display (800×480 via HDMI to Pioneer AVH-W4500NEX) uses the same 8-screen structure as ESP32 for consistency.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        RASPBERRY PI SCREEN HIERARCHY                         │
│                         (RES+/SET- cycles screens)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Screen 0      Screen 1      Screen 2      Screen 3                        │
│  ┌────────┐    ┌────────┐    ┌────────┐    ┌────────┐                       │
│  │OVERVIEW│────│RPM/SPEED────│  TPMS  │────│ ENGINE │                       │
│  │Multi-  │    │Racing   │    │Full    │    │Circular│                       │
│  │panel   │    │focused  │    │tire    │    │gauges  │                       │
│  └────────┘    └────────┘    └────────┘    └────────┘                       │
│                                                                              │
│   Screen 4      Screen 5      Screen 6      Screen 7                        │
│  ┌────────┐    ┌────────┐    ┌────────┐    ┌────────┐                       │
│  │G-FORCE │────│DIAGNOS-│────│ SYSTEM │────│SETTINGS│                       │
│  │Large   │    │Warning  │    │Pi stats│    │+ Volume│                       │
│  │display │    │grid     │    │network │    │control │                       │
│  └────────┘    └────────┘    └────────┘    └────────┘                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Screen Details (Pi-Specific)

| # | Screen | Purpose | Data Displayed |
|---|--------|---------|----------------|
| 0 | **Overview** | Multi-panel dashboard | Gear card, RPM bar, key values, mini TPMS, alerts panel |
| 1 | **RPM/Speed** | Racing-focused view | Large RPM gauge, speed card, throttle/brake bars, lap times |
| 2 | **TPMS** | Full tire display | Large car silhouette, 4 tire cards with PSI/temp, status bar |
| 3 | **Engine** | Detailed engine data | Circular gauges (coolant, oil, pressure, intake), fuel bar, voltage |
| 4 | **G-Force** | G visualization | Large G-ball display, lateral/longitudinal/combined value cards |
| 5 | **Diagnostics** | Full warning grid | 2×4 warning indicator grid, DTC list, wheel slip visualization |
| 6 | **System** | Pi system info | CPU temp, memory, disk, network IP, uptime, CAN/ESP32 status |
| 7 | **Settings** | Configuration | Same as ESP32 plus volume control |

### Screen Designs (800×480)

#### Screen 0: Overview (Multi-Panel Dashboard)
```
┌─────────────────────────────────────────────────────────────────────────┐
│  MX5 TELEMETRY                                            14.2V  65°F  │
├───────────────────────────────────────┬─────────────────────────────────┤
│                                       │         KEY VALUES              │
│    ┌─────────────────────────┐        │  ┌─────┐ ┌─────┐ ┌─────┐ ┌───┐ │
│    │          ⚡3             │        │  │COOL │ │ OIL │ │FUEL │ │BAT│ │
│    │         GEAR            │        │  │195°F│ │210°F│ │ 65% │ │14V│ │
│    └─────────────────────────┘        │  └─────┘ └─────┘ └─────┘ └───┘ │
│                                       ├─────────────────────────────────┤
│    ┌───────────────────────────────┐  │         TPMS SUMMARY            │
│    │▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░│ 3500 │  │    32 │  │ 32                  │
│    │              RPM BAR          │  │      [🚗]                       │
│    └───────────────────────────────┘  │    32 │  │ 32                  │
│                                       ├─────────────────────────────────┤
│    65 MPH                             │         ALERTS                  │
│                                       │  ⚠️ Low tire pressure FL        │
│                                       │  🔴 Coolant temp high           │
├───────────────────────────────────────┴─────────────────────────────────┤
│                      ● ○ ○ ○ ○ ○ ○ ○                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Screen 1: RPM/Speed (Racing View)
```
┌─────────────────────────────────────────────────────────────────────────┐
│  RPM / SPEED                                               LAP: 1:23.4 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│    ┌───────────────────────────────────────────────────────────────┐   │
│    │  1  │  2  │  3  │  4  │  5  │  6  │  7  │  R  │               │   │
│    │▓▓▓▓▓│▓▓▓▓▓│▓▓▓▓▓│▓▓▓▓▓│░░░░░│░░░░░│░░░░░│░░░░░│  3500 RPM     │   │
│    └─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴───────────────┘   │
│              BLUE    GREEN   YELLOW  ORANGE   RED                       │
│                                                                         │
│    ┌────────────────┐    ┌────────────────┐    ┌────────────────┐      │
│    │     65 MPH     │    │      ⚡3       │    │  BEST: 1:21.8  │      │
│    │     SPEED      │    │     GEAR       │    │    LAP TIME    │      │
│    └────────────────┘    └────────────────┘    └────────────────┘      │
│                                                                         │
│    THROTTLE ▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░  45%                                │
│    BRAKE    ▓▓▓▓░░░░░░░░░░░░░░░░░  12%                                │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                      ○ ● ○ ○ ○ ○ ○ ○                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Screen 2: TPMS (Full Display)
```
┌─────────────────────────────────────────────────────────────────────────┐
│  TIRE PRESSURE MONITORING                                     ALL OK ✓ │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│    ┌──────────────┐                        ┌──────────────┐             │
│    │    FRONT L   │                        │    FRONT R   │             │
│    │   32.5 PSI   │      ┌────────┐        │   32.1 PSI   │             │
│    │    75°F      │      │        │        │    76°F      │             │
│    │   ████████   │      │  [🚗]  │        │   ████████   │             │
│    └──────────────┘      │        │        └──────────────┘             │
│                          └────────┘                                     │
│    ┌──────────────┐                        ┌──────────────┐             │
│    │    REAR L    │                        │    REAR R    │             │
│    │   31.8 PSI   │                        │   32.0 PSI   │             │
│    │    74°F      │                        │    75°F      │             │
│    │   ████████   │                        │   ████████   │             │
│    └──────────────┘                        └──────────────┘             │
│                                                                         │
│    Target: 32 PSI  |  Warning: < 28 PSI  |  Battery: 95% avg           │
├─────────────────────────────────────────────────────────────────────────┤
│                      ○ ○ ● ○ ○ ○ ○ ○                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Screen 4: G-Force
```
┌─────────────────────────────────────────────────────────────────────────┐
│  G-FORCE METER                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│         ┌─────────────────────────────────────┐                        │
│         │              +1.0G                  │    ┌──────────────┐    │
│         │               │                     │    │   LATERAL    │    │
│         │               │                     │    │   +0.25 G    │    │
│         │  -1.0G ───────●─────── +1.0G       │    │  (RIGHT)     │    │
│         │               │                     │    └──────────────┘    │
│         │               │                     │                        │
│         │              -1.0G                  │    ┌──────────────┐    │
│         │           (BRAKING)                 │    │ LONGITUDINAL │    │
│         │                                     │    │   -0.15 G    │    │
│         └─────────────────────────────────────┘    │  (BRAKING)   │    │
│                                                    └──────────────┘    │
│                                                    ┌──────────────┐    │
│              Max G: 1.2 (lateral)                  │   COMBINED   │    │
│                                                    │    0.29 G    │    │
│                                                    └──────────────┘    │
├─────────────────────────────────────────────────────────────────────────┤
│                      ○ ○ ○ ○ ● ○ ○ ○                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Screen 5: Diagnostics
```
┌─────────────────────────────────────────────────────────────────────────┐
│  DIAGNOSTICS                                              2 WARNINGS   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│    WARNING INDICATORS                                                   │
│    ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐                     │
│    │  CHECK  │ │   ABS   │ │ TRACTION│ │   OIL   │                     │
│    │  ENGINE │ │         │ │ CONTROL │ │  PRESS  │                     │
│    │   🔴    │ │   ⚪    │ │   🟡    │ │   ⚪    │                     │
│    └─────────┘ └─────────┘ └─────────┘ └─────────┘                     │
│    ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐                     │
│    │ BATTERY │ │  DOOR   │ │SEATBELT │ │ AIRBAG  │                     │
│    │         │ │  AJAR   │ │         │ │         │                     │
│    │   ⚪    │ │   ⚪    │ │   ⚪    │ │   ⚪    │                     │
│    └─────────┘ └─────────┘ └─────────┘ └─────────┘                     │
│                                                                         │
│    DTC CODES                          WHEEL SLIP                        │
│    ┌──────────────────────┐           ┌──────────────────┐             │
│    │ P0301 - Cylinder 1   │           │ FL: 0%  FR: 0%   │             │
│    │ P0420 - Catalyst     │           │ RL: 2%  RR: 0%   │             │
│    └──────────────────────┘           └──────────────────┘             │
├─────────────────────────────────────────────────────────────────────────┤
│                      ○ ○ ○ ○ ○ ● ○ ○                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Screen 6: System Info
```
┌─────────────────────────────────────────────────────────────────────────┐
│  SYSTEM STATUS                                           UPTIME: 2:34  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│    RASPBERRY PI                         CONNECTIVITY                    │
│    ┌──────────────────────────┐        ┌──────────────────────────┐   │
│    │ CPU Temp:      52°C      │        │ IP: 192.168.1.28         │   │
│    │ CPU Usage:     15%       │        │ WiFi: Connected          │   │
│    │ Memory:        45%       │        │ CAN HS: ✓ Active         │   │
│    │ Disk:          32%       │        │ CAN MS: ✓ Active         │   │
│    └──────────────────────────┘        │ ESP32:  ✓ Connected      │   │
│                                        └──────────────────────────┘   │
│    ESP32-S3                                                            │
│    ┌──────────────────────────┐                                       │
│    │ CPU Temp:      45°C      │        POWER                          │
│    │ Heap Free:     120KB     │        ┌──────────────────────────┐   │
│    │ PSRAM Free:    2.1MB     │        │ Vehicle:   14.2V         │   │
│    │ Frequency:     240MHz    │        │ Status:    Engine On     │   │
│    └──────────────────────────┘        └──────────────────────────┘   │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                      ○ ○ ○ ○ ○ ○ ● ○                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Screen 7: Settings
```
┌─────────────────────────────────────────────────────────────────────────┐
│  SETTINGS                                                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│    DISPLAY                              ALERTS                          │
│    ┌──────────────────────────┐        ┌──────────────────────────┐   │
│    │ ▶ Brightness:     80%    │        │   Low Tire PSI:   28.0   │   │
│    │   Volume:         70%    │        │   High Coolant:   220°F  │   │
│    │   Units:          MPH    │        │   Low Voltage:    12.0V  │   │
│    └──────────────────────────┘        │   Low Fuel:       15%    │   │
│                                        └──────────────────────────┘   │
│    SHIFT LIGHT                                                         │
│    ┌──────────────────────────┐                                       │
│    │   Shift RPM:      6500   │                                       │
│    │   Redline RPM:    7200   │                                       │
│    └──────────────────────────┘                                       │
│                                                                         │
│    RES+/SET- = Navigate  |  ON/OFF = Edit  |  VOL+/- = Adjust         │
│    CANCEL = Back                                                        │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                      ○ ○ ○ ○ ○ ○ ○ ●                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Settings Configuration

| Setting | Range | Step | Default | Screen |
|---------|-------|------|---------|--------|
| Brightness | 10-100% | 5% | 80% | Both |
| Volume | 0-100% | 5% | 70% | Pi only |
| Shift RPM | 4000-7500 | 100 | 6500 | Both |
| Redline RPM | 5000-8000 | 100 | 7200 | Both |
| Units | MPH / KMH | Toggle | MPH | Both |
| Low Tire PSI | 20-35 | 0.5 | 28.0 | Both |
| Coolant Warning | 180-250°F | 5° | 220°F | Both |

---

## UI Color Palette

Both displays use a consistent modern dark theme:

| Color | Purpose | RGB |
|-------|---------|-----|
| BG | Background | (12, 12, 18) |
| BG_CARD | Card backgrounds | (22, 22, 32) |
| WHITE | Primary text | (245, 245, 250) |
| GRAY | Secondary text | (140, 140, 160) |
| RED | Warnings / High RPM | (255, 70, 85) |
| GREEN | Good status | (50, 215, 130) |
| BLUE | Accent / RPM zone | (65, 135, 255) |
| YELLOW | Caution | (255, 210, 60) |
| ORANGE | High RPM zone | (255, 140, 50) |
| CYAN | Coolant / Info | (50, 220, 255) |
| PURPLE | Best lap / Longitudinal | (175, 130, 255) |
| ACCENT | Primary accent | (100, 140, 255) |

---

## Alert System

The UI monitors and displays alerts for:

| Alert Type | Trigger | Display |
|------------|---------|---------|
| Low Tire Pressure | < 28.0 PSI (configurable) | Yellow warning, TPMS screen + Overview |
| High Tire Pressure | > 38.0 PSI | Yellow warning |
| High Coolant Temp | > 220°F (configurable) | Red warning, Engine screen + Overview |
| High Oil Temp | > 260°F | Red warning |
| Low Voltage | < 12.0V | Yellow warning |
| Low Fuel | < 15% | Yellow warning |
| Check Engine Light | CAN signal | Red CEL indicator, Diagnostics screen |
| ABS Warning | CAN signal | Diagnostics screen |
| Traction Control | CAN signal | Diagnostics screen |

---

## Sound Effects (Pi Only)

| Action | Sound |
|--------|-------|
| Navigate screens | Short tick |
| Select item | Confirmation beep |
| Adjust value | Value change tick |
| Back/Cancel | Descending tone |
| Error | Low buzz |

---

## State Machine

```
                              ┌──────────────┐
                              │    START     │
                              └──────┬───────┘
                                     │
                                     ▼
                    ┌─────────────────────────────────┐
                    │      SYNCHRONIZED DISPLAYS      │
                    │   ESP32 = Round gauge display   │
                    │   Pi = Full telemetry dashboard │
                    │   Both show same 8 screens      │
                    └─────────────────┬───────────────┘
                                      │
                         ┌────────────┴────────────┐
                         │                         │
               RES+/SET- │                         │ RES+/SET-
                         ▼                         ▼
              ┌──────────────────┐      ┌──────────────────┐
              │  SCREEN CYCLE    │      │  SCREEN CYCLE    │
              │  ═══════════════ │      │  ═══════════════ │
              │                  │      │                  │
              │  0 → 1 → 2 → 3   │      │  0 → 1 → 2 → 3   │
              │  ↑           ↓   │◄────▶│  ↑           ↓   │
              │  7 ← 6 ← 5 ← 4   │      │  7 ← 6 ← 5 ← 4   │
              │                  │      │                  │
              │  (wraps around)  │      │  (wraps around)  │
              └──────────────────┘      └──────────────────┘
                         │                         │
                    MUTE │                         │ MUTE
                         ▼                         ▼
              ┌──────────────────┐      ┌──────────────────┐
              │   ESP32 SLEEP    │      │    PI SLEEP      │
              │   (minimal UI)   │      │   (screen dim)   │
              └──────────────────┘      └──────────────────┘
```

---

## Quick Reference Card

```
╔═══════════════════════════════════════════════════════════════════════╗
║                MX5 STEERING WHEEL CONTROLS (IMPLEMENTED)               ║
╠═══════════════════════════════════════════════════════════════════════╣
║                                                                        ║
║   NAVIGATION (works on both displays):                                 ║
║   ─────────────────────────────────────                                ║
║   RES+ ─────── Previous screen (Screen 7 → 6 → 5 → ... → 0)           ║
║   SET- ─────── Next screen (Screen 0 → 1 → 2 → ... → 7)               ║
║   VOL+ ─────── Next screen (alternate) / Increase value               ║
║   VOL- ─────── Previous screen (alternate) / Decrease value           ║
║                                                                        ║
║   ACTIONS:                                                             ║
║   ────────                                                             ║
║   ON/OFF ───── SELECT / ENTER edit mode (Settings screen)             ║
║   CANCEL ───── BACK / EXIT edit mode / Return to previous             ║
║   MUTE ─────── Toggle sleep mode (dim display, minimal UI)            ║
║                                                                        ║
║   SETTINGS SCREEN (Screen 7):                                          ║
║   ────────────────────────────                                         ║
║   RES+/SET- ── Navigate between settings                              ║
║   ON/OFF ───── Enter edit mode for selected setting                   ║
║   VOL+/VOL- ── Adjust value when editing                              ║
║   CANCEL ───── Exit edit mode                                         ║
║                                                                        ║
║   SCREENS:                                                             ║
║   ────────                                                             ║
║   0=Overview │ 1=RPM/Speed │ 2=TPMS │ 3=Engine                        ║
║   4=G-Force  │ 5=Diagnostics │ 6=System │ 7=Settings                  ║
║                                                                        ║
╚═══════════════════════════════════════════════════════════════════════╝
```

---

## Implementation Status

### Phase 1: CAN Bus Reading ✅ COMPLETE
- [x] Wire MCP2515 #1 to HS-CAN
- [x] Wire MCP2515 #2 to MS-CAN
- [x] Verify CAN message reading
- [x] Identify exact SWC button CAN IDs by sniffing

### Phase 2: ESP32-S3 Display ✅ COMPLETE
- [x] Set up ESP32-S3 with round display
- [x] Implement serial communication with Pi
- [x] Create 8 gauge UI screens (Overview, RPM/Speed, TPMS, Engine, G-Force, Diagnostics, System, Settings)
- [x] Implement SWC button navigation
- [x] BLE TPMS sensor integration
- [x] QMI8658 IMU integration for G-Force

### Phase 3: Raspberry Pi Integration ✅ COMPLETE
- [x] Set up Serial communication from ESP32
- [x] Create Pi telemetry application with matching 8-screen UI
- [x] Implement SWC button handling via MS-CAN
- [x] Configure HDMI output for AVH-W4500NEX (800x480)
- [x] Add sound effects for navigation feedback

### Phase 4: Integration & Polish ✅ COMPLETE
- [x] Synchronized 8-screen structure between both displays
- [x] Color-coded RPM zones and alert system
- [x] Configurable settings (brightness, shift RPM, warnings, etc.)
- [x] Sleep mode for both displays
- [x] Demo mode for testing without vehicle

### Future Enhancements (Planned)
- [ ] Lap timer with GPS integration
- [ ] Data logging to SD card
- [ ] OBD-II DTC reading and clearing
- [ ] Custom gauge themes
- [ ] WiFi configuration interface

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
| 2025-12-09 | 1.0 | Updated with implemented 8-screen UI for both ESP32 and Pi displays. Added detailed screen layouts, color palette, alert system, settings configuration, and updated button navigation to reflect actual implementation. Marked implementation phases as complete. |

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

### Serial Protocol (ESP32-S3 ↔ Pi)

**ESP32 → Pi (Data):**
```
TPMS:0,32.5,25.3,95\n    // Tire 0: 32.5 PSI, 25.3°C, 95% battery
TPMS:1,31.8,24.1,92\n    // Tire 1: 31.8 PSI, 24.1°C, 92% battery
TPMS:2,33.1,26.0,88\n    // Tire 2: 33.1 PSI, 26.0°C, 88% battery
TPMS:3,32.9,25.8,90\n    // Tire 3: 32.9 PSI, 25.8°C, 90% battery
IMU:0.25,-0.15\n         // G-Force: lateral +0.25G, longitudinal -0.15G (braking)
SCREEN_CHANGED:2\n       // ESP32 user swiped to screen 2 (TPMS)
OK:SCREEN_2\n            // Acknowledgement of screen command from Pi
```

**Pi → ESP32 (Commands):**
```
SCREEN:0\n               // Change to Overview screen
SCREEN:1\n               // Change to RPM/Speed screen
SCREEN:2\n               // Change to TPMS screen
SCREEN:3\n               // Change to Engine screen
SCREEN:4\n               // Change to G-Force screen
TEL:3500,65,3,...\n      // Telemetry: RPM, speed, gear, etc.
PING\n                   // Connection test (ESP32 responds: PONG)
```

### Bidirectional Screen Sync

Both displays stay synchronized when either device changes screens:

1. **Pi → ESP32**: When user presses keys on Pi, `ESP32SerialHandler.send_screen_change(idx)` sends `SCREEN:X`
2. **ESP32 → Pi**: When user swipes on ESP32, it sends `SCREEN_CHANGED:X` and Pi callback updates `current_screen`

This ensures both displays always show the same screen, regardless of which input method is used.

### Resources

- GitHub: `ra6070/BLE-TPMS` - ESP32 Arduino code
- GitHub: `andi38/TPMS` - Protocol documentation
- GitHub: `bkbilly/tpms_ble` - Home Assistant integration

---

## QMI8658 IMU Integration

### Overview

The ESP32-S3 round display module has a **built-in QMI8658 IMU** (Inertial Measurement Unit) that provides:
- 3-axis accelerometer (±2g to ±16g)
- 3-axis gyroscope (±16°/s to ±2048°/s)

This is used for **real G-Force measurement** on the G-Force screen, eliminating the need for calculated approximations.

### Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         QMI8658 IMU DATA FLOW                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌───────────────────────┐                                                  │
│   │   ESP32-S3 Display    │                                                  │
│   │                       │                                                  │
│   │  ┌─────────────────┐  │                                                  │
│   │  │    QMI8658 IMU  │  │                                                  │
│   │  │    (built-in)   │  │                                                  │
│   │  │                 │  │                                                  │
│   │  │  Accel X ───────┼──┼──► Lateral G (left/right turns)                 │
│   │  │  Accel Y ───────┼──┼──► Longitudinal G (accel/braking)               │
│   │  │  Accel Z ───────┼──┼──► Vertical G (bumps)                           │
│   │  │  Gyro X/Y/Z ────┼──┼──► Rotation rates (optional)                    │
│   │  └─────────────────┘  │                                                  │
│   │          │            │                                                  │
│   │          ▼            │                                                  │
│   │  ┌─────────────────┐  │                                                  │
│   │  │  ESP32 Display  │◄─┼──── Shows G-Force ball on screen                │
│   │  └────────┬────────┘  │                                                  │
│   │           │           │                                                  │
│   └───────────┼───────────┘                                                  │
│               │ Serial TX                                                    │
│               │ "IMU:0.25,-0.15\n"                                           │
│               ▼                                                              │
│   ┌───────────────────────┐                                                  │
│   │   Raspberry Pi 4B     │                                                  │
│   │                       │                                                  │
│   │  Serial RX ──► Parse IMU data                                           │
│   │                  │                                                       │
│   │                  ▼                                                       │
│   │  telemetry.g_lateral = 0.25                                             │
│   │  telemetry.g_longitudinal = -0.15                                       │
│   │                  │                                                       │
│   │                  ▼                                                       │
│   │  ┌─────────────────┐                                                    │
│   │  │  Pi G-Force     │◄── Same visualization as ESP32                     │
│   │  │  Screen         │                                                    │
│   │  └─────────────────┘                                                    │
│   │           │                                                              │
│   │           ▼                                                              │
│   │  Pioneer AVH-W4500NEX (HDMI)                                            │
│   └───────────────────────┘                                                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### QMI8658 Specifications

| Parameter | Value |
|-----------|-------|
| Accelerometer Range | ±2g, ±4g, ±8g, ±16g (configurable) |
| Gyroscope Range | ±16, ±32, ±64, ±128, ±256, ±512, ±1024, ±2048 °/s |
| Interface | I2C (built into ESP32-S3 display module) |
| Update Rate | Up to 8000 Hz |
| Operating Voltage | 1.71V - 3.6V |

### Mounting Orientation

For accurate G-force readings, the ESP32-S3 display should be mounted with:
- **X-axis** pointing left/right (lateral G)
- **Y-axis** pointing front/back (longitudinal G)
- **Z-axis** pointing up/down (vertical G)

```
        FRONT OF CAR
             ▲
             │ +Y (acceleration)
             │
    ◄────────┼────────►
   +X        │        -X
 (right     ESP32    (left
  turn)      │       turn)
             │
             ▼ -Y (braking)
```

### ESP32 IMU Reading Code (Example)

```cpp
#include <Wire.h>

// QMI8658 I2C address
#define QMI8658_ADDR 0x6B

// Accelerometer data registers
#define QMI8658_AX_L 0x35
#define QMI8658_AX_H 0x36
#define QMI8658_AY_L 0x37
#define QMI8658_AY_H 0x38
#define QMI8658_AZ_L 0x39
#define QMI8658_AZ_H 0x3A

float g_lateral = 0.0;
float g_longitudinal = 0.0;

void readIMU() {
    Wire.beginTransmission(QMI8658_ADDR);
    Wire.write(QMI8658_AX_L);
    Wire.endTransmission(false);
    Wire.requestFrom(QMI8658_ADDR, 6);
    
    int16_t ax = Wire.read() | (Wire.read() << 8);
    int16_t ay = Wire.read() | (Wire.read() << 8);
    int16_t az = Wire.read() | (Wire.read() << 8);
    
    // Convert to G (assuming ±4g range, 8192 LSB/g)
    g_lateral = ax / 8192.0;
    g_longitudinal = ay / 8192.0;
    
    // Send to Pi
    Serial.printf("IMU:%.2f,%.2f\n", g_lateral, g_longitudinal);
}

void loop() {
    readIMU();
    delay(50);  // 20Hz update rate
}
```

---

## Raspberry Pi CAN Bus Handler

### Overview

The Raspberry Pi reads vehicle data from two MCP2515 CAN modules via SPI. A Python CAN handler (`pi/ui/src/can_handler.py`) manages both buses in background threads.

### Implementation Files

| File | Purpose |
|------|---------|
| `pi/ui/src/can_handler.py` | CAN bus handler class with MCP2515 support |
| `pi/ui/src/main.py` | Main display app, integrates CAN handler |

### Pin Configuration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MCP2515 CAN MODULES - SPI WIRING                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Shared SPI Bus:                                                            │
│   ═══════════════                                                            │
│   GPIO 10 (MOSI) ──────► Both MCP2515 SI (Serial In)                        │
│   GPIO 9  (MISO) ◄────── Both MCP2515 SO (Serial Out)                       │
│   GPIO 11 (SCLK) ──────► Both MCP2515 SCK (Clock)                           │
│                                                                              │
│   Individual Chip Select:                                                    │
│   ═══════════════════════                                                    │
│   GPIO 8  (CE0)  ──────► MCP2515 #1 CS (HS-CAN, 500kbps)                    │
│   GPIO 7  (CE1)  ──────► MCP2515 #2 CS (MS-CAN, 125kbps)                    │
│                                                                              │
│   Interrupt Lines:                                                           │
│   ════════════════                                                           │
│   GPIO 25        ◄────── MCP2515 #1 INT (HS-CAN interrupt)                  │
│   GPIO 24        ◄────── MCP2515 #2 INT (MS-CAN interrupt)                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### CAN Message IDs (Mazda MX-5 NC 2006-2015)

#### HS-CAN (500kbps) - Engine/Drivetrain

| CAN ID | Description | Data Format |
|--------|-------------|-------------|
| `0x200` | Throttle Position | Byte 4: 0-255 → 0-100% |
| `0x201` | RPM + Speed | Bytes 0-1: RPM×4, Bytes 4-5: Speed km/h |
| `0x212` | Brake Status | Byte 0 bit 3: Brake pedal |
| `0x231` | Gear Position | Byte 0 bits 0-3: Gear (0=N, 1-6, 7+=R) |
| `0x420` | Engine Temps | Byte 0: Coolant, Byte 1: Oil (°C + 40 offset) |
| `0x430` | Fuel Level | Byte 0: 0-255 → 0-100% |
| `0x440` | Battery Voltage | Bytes 0-1: Voltage × 100 |
| `0x4B0` | Wheel Speeds | 2 bytes per wheel (FL, FR, RL, RR) |

#### MS-CAN (125kbps) - Body/Accessories

| CAN ID | Description | Data Format |
|--------|-------------|-------------|
| `0x240` | SWC Audio Buttons | Byte 0: Button bitmask |
| `0x250` | SWC Cruise Buttons | Byte 0: Button bitmask |
| `0x290` | Lighting Status | Byte 0 bit 1: High beam, bit 2: Fog |
| `0x430` | Door Status | Byte 0: Door ajar flags |

### Running the CAN Handler

```bash
# Demo mode (no CAN hardware required)
python3 /home/pi/MX5-Telemetry/pi/ui/src/main.py --demo

# Real CAN mode (requires MCP2515 modules)
python3 /home/pi/MX5-Telemetry/pi/ui/src/main.py --no-demo
```

### Pi Setup (One-Time)

1. **Enable SPI:**
   ```bash
   sudo raspi-config
   # Interface Options → SPI → Enable
   ```

2. **Install python-can:**
   ```bash
   pip3 install python-can
   ```

3. **Add to `/boot/config.txt`:**
   ```
   dtparam=spi=on
   dtoverlay=mcp2515-can0,oscillator=8000000,interrupt=25
   dtoverlay=mcp2515-can1,oscillator=8000000,interrupt=24,spi0-1
   ```

4. **Reboot and bring up interfaces:**
   ```bash
   sudo reboot
   sudo ip link set can0 up type can bitrate 500000
   sudo ip link set can1 up type can bitrate 125000
   ```

5. **Test CAN (optional):**
   ```bash
   candump can0  # Should show HS-CAN traffic
   candump can1  # Should show MS-CAN traffic
   ```

### System Screen - CAN Status

The Pi display's **System** screen shows real-time CAN bus status:

| Status | Meaning |
|--------|---------|
| `DEMO MODE` (orange) | Running with simulated data |
| `CONNECTED` (green) | Receiving real CAN messages |
| `WAITING...` (yellow) | CAN initialized but no data yet |
| `OFFLINE` (red) | CAN failed to initialize |

---

## Notes & Ideas


- Consider adding voice control via ESP32-S3's speech recognition
- Could add lap timer functionality with GPS module
- Bluetooth OBD adapter as backup/alternative to wired CAN
- Android Auto via OpenAuto Pro as future enhancement
- TPMS alerts: flash LED strip or beep when tire pressure low
