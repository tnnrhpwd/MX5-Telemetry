# MX5 Telemetry System Architecture

Complete system architecture and design documentation for the MX5-Telemetry system.

---

## System Overview

The MX5 Telemetry system uses a **three-device architecture** with centralized data processing:

```
┌─────────────────────────────────────────────────────────────┐
│                    SYSTEM ARCHITECTURE                      │
│              Raspberry Pi as Central Hub                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  OBD-II Port                                                │
│      │                                                      │
│      ├─── HS-CAN (500k) ──┬──► Pi MCP2515 #1 (HS)          │
│      │                    │                                 │
│      │                    └──► Arduino MCP2515 (HS shared)  │
│      │                                                      │
│      └─── MS-CAN (125k) ──────► Pi MCP2515 #2 (MS)         │
│                                                             │
│  Raspberry Pi 4B (Hub)                                      │
│      ├──► ESP32-S3 (Serial) ──► Display + TPMS + IMU       │
│      ├──► Arduino (Serial) ────► LED sequence commands      │
│      └──► Pioneer (HDMI) ──────► Full dashboard            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Device Roles

| Device | Primary Role | Secondary Role | Location |
|--------|-------------|----------------|----------|
| **Raspberry Pi 4B** | CAN hub & data processor | Settings cache & HDMI output | Hidden (console/trunk) |
| **ESP32-S3 Display** | Gauge display | BLE TPMS & G-force IMU | Stock oil gauge hole |
| **Arduino Nano** | RPM LED controller | Direct CAN for low latency | Gauge cluster bezel |

---

## Design Decisions

### Why Raspberry Pi as Hub?

| Factor | Pi as Hub ✅ | ESP32 as Hub |
|--------|-------------|--------------|
| GPIO pins available | 26+ pins | ~6-10 pins |
| CAN processing power | Plenty | Limited |
| Display connections | Wired serial (fast) | WiFi (laggy) |
| Complexity | Distributed, simpler | Everything on ESP32 |
| BLE TPMS | Need USB dongle | Built-in ✅ |

**Decision:** Pi reads both CAN buses and distributes data. ESP32 handles BLE TPMS with built-in radio.

### Why Arduino Keeps Direct CAN?

Arduino reads RPM directly from CAN instead of via serial from Pi:

| Factor | Direct CAN ✅ | Serial from Pi |
|--------|-------------|----------------|
| Latency | <1ms with interrupt | Variable, buffered |
| EMI resistance | Excellent (differential) | Poor (single-ended) |
| Distance | 1-2m through engine bay | Same, but EMI-prone |
| Independence | Works if Pi offline | Needs Pi running |
| Reliability | Proven in-car | Corruption risk |

**Decision:** Arduino keeps its own MCP2515 on shared HS-CAN bus for time-critical RPM display.

---

## Data Flow Architecture

### CAN Bus Reading

```
OBD-II Connector
│
├─── HS-CAN (500kbps) ─────────┬─► Pi MCP2515 #1 (GPIO 8)
│    Pins 6(H) & 14(L)         │   • RPM, Speed, Throttle
│    SHARED BUS                │   • Temps, Gear, Brake
│                              │   • Wheel speeds
│                              │
│                              └─► Arduino MCP2515 (D10)
│                                  • RPM only (direct)
│
└─── MS-CAN (125kbps) ────────────► Pi MCP2515 #2 (GPIO 7)
     Pins 3(H) & 11(L)              • Steering wheel buttons
                                    • Body/accessory data
```

### Serial Communication

**Pi → ESP32-S3** (115200 baud):
```
TEL:3500,65,3,195,14.2,...\n    # All CAN telemetry
SCREEN:2\n                      # Screen change command
```

**ESP32-S3 → Pi** (115200 baud):
```
TPMS:0,32.5,25.3,95\n          # Tire 0: PSI, temp, battery
IMU:0.25,-0.15\n               # Lateral, longitudinal G
SCREEN_CHANGED:2\n             # User changed screen
```

**Pi → Arduino** (9600 baud):
```
SEQ:1\n                        # LED sequence selection
```

### Settings Cache

The Pi maintains all user settings and syncs to devices on startup:

```
┌──────────────────────────────────────────────────┐
│         RASPBERRY PI SETTINGS CACHE              │
│     ~/MX5-Telemetry/pi/config/settings.json      │
├──────────────────────────────────────────────────┤
│                                                  │
│  • Brightness (10-100%)                          │
│  • Shift RPM (4000-7500)                         │
│  • Redline RPM (5000-8000)                       │
│  • Units (MPH/KPH, °F/°C)                        │
│  • Warning thresholds                            │
│  • LED pattern/sequence (1-4)                    │
│                                                  │
│  On startup:                                     │
│  ├─► Sends to ESP32-S3                           │
│  └─► Sends to Arduino (LED sequence)             │
│                                                  │
│  On change (via steering wheel buttons):         │
│  ├─► Saves to file                               │
│  ├─► Updates ESP32-S3                            │
│  └─► Updates Arduino                             │
│                                                  │
└──────────────────────────────────────────────────┘
```

---

## CAN Bus Specifications

### MX5 NC CAN Architecture

| Bus | Speed | OBD Pins | Purpose | Device Access |
|-----|-------|----------|---------|---------------|
| **HS-CAN** | 500 kbps | 6 (H), 14 (L) | Engine/drivetrain data | Pi + Arduino (shared) |
| **MS-CAN** | 125 kbps | 3 (H), 11 (L) | Body/accessory data | Pi only |

### Key CAN Message IDs

#### HS-CAN Messages (500kbps)

| ID | Data | Bytes | Formula |
|----|------|-------|---------|
| `0x201` | RPM | 0-1 | Value ÷ 4 |
| `0x201` | Speed | 4-5 | Value ÷ 100 (km/h) |
| `0x201` | Throttle | 6 | 0-200 (200=100%) |
| `0x228` | Gear | 0 | Bit flags |
| `0x420` | Coolant Temp | 0 | °C + 40 offset |
| `0x430` | Fuel Level | 0 | 0-255 = 0-100% |
| `0x4B0` | Wheel Speeds | 0-7 | FL, FR, RL, RR |

#### MS-CAN Messages (125kbps)

| ID | Data | Bytes | Purpose |
|----|------|-------|---------|
| `0x240` | Audio buttons | 0 | VOL+/-, MUTE, SEEK, MODE |
| `0x250` | Cruise buttons | 0 | ON/OFF, CANCEL, RES+, SET- |

See [PI_DISPLAY_INTEGRATION.md](PI_DISPLAY_INTEGRATION.md) for complete CAN message decoding.

---

## User Interface Architecture

### 8-Screen Structure (Synchronized)

Both ESP32 and Pi displays share the same screen hierarchy:

| # | Screen | ESP32 Display | Pi Display |
|---|--------|---------------|------------|
| 0 | Overview | Compact dashboard | Multi-panel dashboard |
| 1 | RPM/Speed | Large RPM arc | Racing-focused gauges |
| 2 | TPMS | 4-corner pressures | Full tire details + car diagram |
| 3 | Engine | Circular gauges | Detailed engine data |
| 4 | G-Force | 2D G-ball | Large G visualization |
| 5 | Diagnostics | Warning grid | Full DTC codes |
| 6 | System | ESP32 stats | Pi + ESP32 + network status |
| 7 | Settings | Configurable options | Settings + volume control |

### Navigation System

**Steering Wheel Controls:**
- **RES+ / SET-** - Previous/Next screen
- **VOL+ / VOL-** - Previous/Next screen (alternate)
- **ON/OFF** - Select/Enter (Settings mode)
- **CANCEL** - Back/Exit
- **MUTE** - Toggle sleep mode

**Touch (ESP32 only):**
- Top/Bottom tap - Previous/Next screen
- Center tap - Select
- Swipe up/down - Navigate screens

---

## Sensors & Data Sources

### Built-in Sensors (ESP32-S3)

| Sensor | Data | Update Rate | Used For |
|--------|------|-------------|----------|
| **QMI8658 IMU** | 3-axis accel + gyro | Up to 8kHz | G-force display |
| **BLE Radio** | TPMS sensor data | 1 Hz | Tire pressure/temp |

### External Sensors

| Sensor | Connection | Data | Purpose |
|--------|------------|------|---------|
| **BLE TPMS Caps (x4)** | BLE → ESP32 | Pressure, temp, battery | Tire monitoring |
| **MCP2515 Modules (x3)** | SPI → Pi/Arduino | CAN bus messages | Vehicle data |

---

## Hardware Integration

### Pin Assignments Summary

**Raspberry Pi 4B:**
- GPIO 8 (CE0) - MCP2515 #1 CS (HS-CAN)
- GPIO 7 (CE1) - MCP2515 #2 CS (MS-CAN)
- GPIO 14/15 - Serial to ESP32-S3
- GPIO 9/10/11 - Shared SPI bus
- GPIO 24/25 - CAN interrupts

**Arduino Nano:**
- D2 - MCP2515 INT (hardware interrupt)
- D5 - WS2812B LED data
- D10 - MCP2515 CS
- D11/12/13 - SPI bus
- D0 - Serial RX from Pi

**ESP32-S3:**
- GPIO 43/44 - Serial to Pi
- Internal - LCD, touch, BLE, IMU (pre-wired)

See [hardware/HARDWARE.md](hardware/HARDWARE.md) for complete wiring diagrams, parts list, and hardware setup.

---

## Performance Specifications

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Arduino CAN→LED latency | <50ms | <1ms | ✅ Exceeded |
| LED update rate | 50Hz | 100Hz | ✅ Exceeded |
| Screen refresh rate | 30fps | 30fps | ✅ Met |
| Pi→ESP32 serial latency | <100ms | ~50ms | ✅ Met |
| TPMS update rate | 1 Hz | 1 Hz | ✅ Met |
| G-force update rate | 20 Hz | 20 Hz | ✅ Met |

---

## System States

```
┌────────────────────────────────────────────────┐
│              SYSTEM STATE MACHINE              │
├────────────────────────────────────────────────┤
│                                                │
│  STARTUP                                       │
│    ├─► Pi: Load settings from cache           │
│    ├─► Pi: Initialize CAN buses               │
│    ├─► ESP32: Initialize display & BLE        │
│    ├─► Arduino: Initialize LEDs & CAN         │
│    └─► Pi: Sync settings to devices           │
│                                                │
│  NORMAL OPERATION                              │
│    ├─► Continuous CAN reading                 │
│    ├─► Real-time display updates              │
│    ├─► LED RPM visualization                  │
│    └─► TPMS monitoring                         │
│                                                │
│  SLEEP MODE (MUTE pressed)                    │
│    ├─► Dim displays                           │
│    ├─► Show minimal info                      │
│    └─► Reduce update rate                     │
│                                                │
│  SETTINGS MODE (Screen 7)                     │
│    ├─► Navigate with RES+/SET-                │
│    ├─► Edit with VOL+/VOL-                    │
│    ├─► Save to Pi cache                       │
│    └─► Sync to ESP32/Arduino                  │
│                                                │
└────────────────────────────────────────────────┘
```

---

## Fault Tolerance

| Failure Scenario | System Response |
|------------------|----------------|
| **Pi crashes** | Arduino LEDs continue working (direct CAN), ESP32 shows last known data |
| **ESP32 disconnects** | Pi HDMI display continues, no TPMS/G-force data |
| **Arduino disconnects** | No LED strip, rest of system functions |
| **CAN bus error** | Error animation on LEDs, "CAN OFFLINE" on displays |
| **TPMS sensor low battery** | Warning shown on display, sensor still reports |
| **Serial corruption** | Checksum validation, request retransmit |

---

## Future Enhancements

### Planned Features
- [ ] GPS lap timer with track mapping
- [ ] Data logging to SD card
- [ ] OBD-II DTC code reading/clearing
- [ ] WiFi configuration web interface
- [ ] Android Auto integration
- [ ] Custom gauge themes

### Under Consideration
- [ ] Voice control via ESP32-S3
- [ ] Bluetooth OBD adapter support
- [ ] Multiple vehicle profiles
- [ ] Cloud data sync
- [ ] Mobile app for remote monitoring

---

## Related Documentation

- **Hardware:** [hardware/HARDWARE.md](hardware/HARDWARE.md)
- **Build:** [BUILD_AND_UPLOAD.md](BUILD_AND_UPLOAD.md)
- **Deploy:** [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
- **Features:** [LED_SYSTEM.md](LED_SYSTEM.md)
- **Development:** [development/DEVELOPMENT_GUIDE.md](development/DEVELOPMENT_GUIDE.md)

---

**Last Updated:** December 29, 2025
