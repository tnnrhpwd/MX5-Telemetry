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
| Raspberry Pi 4B | HDMI output to Pioneer AVH-W4500NEX | - |
| ESP32-S3 Round Display | 1.85" gauge display (new CAN hub) | - |
| Arduino Nano | RPM LED strip controller | [WIRING_GUIDE.md](hardware/WIRING_GUIDE.md) |
| MCP2515 Module x2 | CAN bus readers (HS + MS) for ESP32-S3 | [WIRING_GUIDE.md](hardware/WIRING_GUIDE.md) |
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

> **Decision**: Pi reads CAN buses and distributes data via wired serial to ESP32-S3 and Arduino.
> ESP32-S3 handles BLE TPMS (built-in Bluetooth) and forwards to Pi.

### Block Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MX5 NC TELEMETRY ARCHITECTURE                             │
│                      (Raspberry Pi as Main Hub)                              │
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
│         │                                │                                   │
│         ▼                                ▼                                   │
│   ┌──────────┐                    ┌──────────┐                              │
│   │ MCP2515  │                    │ MCP2515  │                              │
│   │ #1 (HS)  │                    │ #2 (MS)  │                              │
│   └────┬─────┘                    └────┬─────┘                              │
│        │ SPI (shared bus)              │ SPI (shared bus)                   │
│        └───────────┬───────────────────┘                                     │
│                    │                                                         │
│                    ▼                                                         │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    RASPBERRY PI 4B (MAIN HUB)                        │   │
│   │                                                                      │   │
│   │  • Reads HS-CAN (RPM, Speed, Throttle, Temps, Gear)                 │   │
│   │  • Reads MS-CAN (Steering Wheel Buttons, Cruise, Body)              │   │
│   │  • Receives BLE TPMS data from ESP32-S3                             │   │
│   │  • Distributes data to ESP32-S3 and Arduino via Serial              │   │
│   │  • Displays telemetry on HDMI → Pioneer AVH-W4500NEX                │   │
│   │  • Handles button commands for Pi apps                              │   │
│   │                                                                      │   │
│   └────────┬────────────────────────────────┬───────────────────────────┘   │
│            │                                │                                │
│            │ Serial/UART                    │ HDMI                           │
│            │ (GPIO 14/15)                   │                                │
│            ▼                                ▼                                │
│   ┌─────────────────────┐         ┌─────────────────────┐                   │
│   │     ESP32-S3        │         │  Pioneer AVH-W4500  │                   │
│   │   Round Display     │         │    (800x480)        │                   │
│   │                     │         └─────────────────────┘                   │
│   │  • Receives data    │                                                    │
│   │    from Pi (Serial) │                                                    │
│   │  • BLE TPMS Rx      │◄──────── BLE TPMS Cap Sensors (x4)                │
│   │  • Round LCD gauge  │                                                    │
│   │  • Forwards TPMS    │                                                    │
│   │    to Pi (Serial)   │                                                    │
│   └──────────┬──────────┘                                                    │
│              │ Serial (pass-through or separate)                             │
│              ▼                                                               │
│   ┌─────────────────────┐                                                    │
│   │    Arduino Nano     │                                                    │
│   │     RPM LEDs        │                                                    │
│   │                     │                                                    │
│   │  • Receives RPM     │                                                    │
│   │    from Pi/ESP      │                                                    │
│   │  • Drives WS2812B   │                                                    │
│   └─────────────────────┘                                                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA FLOW                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   HS-CAN (500kbps)              MS-CAN (125kbps)         BLE (2.4GHz)       │
│   ════════════════              ════════════════         ═══════════        │
│   • RPM                         • Steering Buttons       • Tire Pressure    │
│   • Vehicle Speed               • Cruise Buttons         • Tire Temp        │
│   • Throttle Position           • Door Status            • Battery Level    │
│   • Engine Temp                 • Lights Status                             │
│   • Gear Position               • Climate Control                           │
│           │                            │                        │           │
│           │                            │                        │           │
│           ▼                            ▼                        ▼           │
│   ┌──────────────────────────────────────────┐    ┌─────────────────────┐  │
│   │           RASPBERRY PI 4B                │    │     ESP32-S3        │  │
│   │              (CAN HUB)                   │◄───│   (BLE TPMS Rx)     │  │
│   │                                          │    │                     │  │
│   │  MCP2515 #1 ─── SPI ───┐                │    │  Built-in BLE scans │  │
│   │  MCP2515 #2 ─── SPI ───┴─► CAN Parser   │    │  for TPMS sensors   │  │
│   │                             │            │    │                     │  │
│   │                             ▼            │    │  Sends TPMS data    │  │
│   │                    ┌────────────────┐   │    │  to Pi via Serial   │  │
│   │                    │  Data Manager  │   │    └──────────┬──────────┘  │
│   │                    │  + Button Mgr  │   │               │             │
│   │                    └───────┬────────┘   │               │ Serial      │
│   │                            │            │◄──────────────┘ (TPMS)      │
│   └────────────┬───────────────┼────────────┘                             │
│                │               │                                           │
│        HDMI    │    Serial     │   Serial                                  │
│                │   (telemetry) │   (RPM)                                   │
│                ▼               ▼               ▼                           │
│   ┌────────────────┐  ┌─────────────────┐  ┌─────────────────┐            │
│   │    Pioneer     │  │    ESP32-S3     │  │  Arduino Nano   │            │
│   │   AVH-W4500    │  │  Round Display  │  │   RPM LEDs      │            │
│   │   (800x480)    │  │                 │  │                 │            │
│   ├────────────────┤  ├─────────────────┤  ├─────────────────┤            │
│   │ • Full UI      │  │ • RPM Gauge     │  │ • WS2812B LEDs  │            │
│   │ • Maps         │  │ • Speed         │  │ • Shift light   │            │
│   │ • Music        │  │ • TPMS          │  │ • Color sweep   │            │
│   │ • Telemetry    │  │ • Temps         │  │                 │            │
│   │ • Settings     │  │                 │  │                 │            │
│   └────────────────┘  └─────────────────┘  └─────────────────┘            │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
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

> ⚠️ **This system already exists and is working!** See `docs/hardware/WIRING_GUIDE.md` for detailed setup instructions.

The Arduino Nano RPM LED controller is already implemented in this repo. In the new integrated system, instead of reading CAN directly, it will receive RPM data via Serial from the ESP32-S3 hub.

### Arduino Nano Pin Configuration

From `lib/Config/config.h`:

| Pin | Function | Connection |
|-----|----------|------------|
| **D5** | LED Data | WS2812B Data In |
| **D10** | CAN CS | MCP2515 CS (current) → **Not needed in new design** |
| **D7** | CAN INT | MCP2515 INT (current) → **Not needed in new design** |
| **D11** | SPI MOSI | MCP2515 SI (current) → **Not needed in new design** |
| **D12** | SPI MISO | MCP2515 SO (current) → **Not needed in new design** |
| **D13** | SPI SCK | MCP2515 SCK (current) → **Not needed in new design** |
| **D2** | Serial RX | **NEW: ESP32-S3 GPIO 43 (TX)** |
| **5V** | Power | VCC from buck converter |
| **GND** | Ground | Common ground |

### LED Configuration

From `lib/Config/config.h`:

```cpp
#define LED_COUNT 20           // 20x WS2812B LEDs
#define LED_BRIGHTNESS 50      // 0-255 default brightness
#define LED_FADE_SPEED 15      // Fade animation speed
```

### RPM Thresholds

From `lib/Config/config.h`:

```cpp
#define RPM_IDLE        800    // Below this = idle
#define RPM_MIN_DISPLAY 1000   // Start lighting LEDs
#define RPM_MAX         7000   // Full LED bar
#define RPM_SHIFT       6500   // Shift light flash
#define RPM_REDLINE     7200   // Redline warning
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

### Arduino Integration: Current vs New Design

**CURRENT DESIGN** (standalone, reads CAN directly):
```
                     MCP2515
                   ┌─────────┐
    OBD-II HS-CAN ─┤ CAN H/L │
                   └────┬────┘
                        │ SPI (D10-D13)
                        ▼
                  ┌───────────┐
                  │  Arduino  │
                  │   Nano    │
                  └─────┬─────┘
                        │ D5
                        ▼
                  ┌───────────┐
                  │ WS2812B   │
                  │ LED Strip │
                  └───────────┘
```

**NEW DESIGN** (receives RPM from ESP32-S3):
```
                  ┌──────────────┐
    OBD-II ─────→ │   ESP32-S3   │ ←── Reads CAN directly
                  │    HUB       │
                  └──────┬───────┘
                         │ Serial (GPIO 43 TX)
                         ▼
                  ┌───────────┐
                  │  Arduino  │ ←── Simplified code (no CAN library needed)
                  │   Nano    │
                  │   D2 RX   │
                  └─────┬─────┘
                        │ D5
                        ▼
                  ┌───────────┐
                  │ WS2812B   │
                  │ LED Strip │
                  └───────────┘
```

### Benefits of New Architecture

1. **Simplified Arduino Code**: Remove MCP2515/CAN library, just read serial
2. **Freed SPI Pins**: D10-D13 available for other uses
3. **Single CAN Tap**: ESP32-S3 handles all CAN reading
4. **Reduced Wiring**: No need for Arduino's MCP2515 module
5. **Lower Cost**: One less MCP2515 module required

### Serial Protocol (ESP32-S3 → Arduino)

Simple format for RPM transmission:
```
RPM:3500\n    // Send RPM value with newline terminator
```

Arduino parsing example:
```cpp
// Simplified Arduino code (no CAN library)
void loop() {
    if (Serial.available()) {
        String data = Serial.readStringUntil('\n');
        if (data.startsWith("RPM:")) {
            currentRPM = data.substring(4).toInt();
            updateLEDs(currentRPM);
        }
    }
}
```

### Migration Path

| Step | Action | Status |
|------|--------|--------|
| 1 | Keep current Arduino code working | ✅ Working |
| 2 | Add Serial receive to Arduino | ⬜ TODO |
| 3 | Remove MCP2515 code from Arduino | ⬜ TODO |
| 4 | Program ESP32-S3 to forward RPM | ⬜ TODO |
| 5 | Disconnect Arduino's MCP2515 | ⬜ TODO |
| 6 | Connect ESP32-S3 TX → Arduino D2 | ⬜ TODO |

---

### Complete Physical Wiring

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         COMPLETE WIRING DIAGRAM                              │
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
│                    │                              │                          │
│                    ▼                              ▼                          │
│            ┌──────────────┐               ┌──────────────┐                  │
│            │  MCP2515 #2  │               │  MCP2515 #1  │                  │
│            │   MS-CAN     │               │   HS-CAN     │                  │
│            │   125kbps    │               │   500kbps    │                  │
│            └──────┬───────┘               └──────┬───────┘                  │
│                   │ SPI                          │ SPI                       │
│                   └──────────────┬───────────────┘                           │
│                                  ▼                                           │
│                    ┌─────────────────────────────┐                           │
│                    │        ESP32-S3             │                           │
│                    │      Round Display          │                           │
│                    └──────┬──────────────┬──────┘                           │
│                           │              │                                   │
│              ┌────────────┘              └────────────┐                      │
│              ▼                                        ▼                      │
│    ┌───────────────────┐                  ┌───────────────────┐             │
│    │   Arduino Nano    │                  │   Raspberry Pi    │             │
│    │   D2 ←── ESP TX   │                  │   WiFi/Serial     │             │
│    │   D5 ──→ WS2812B  │                  │   HDMI ──→ AVH    │             │
│    └───────────────────┘                  └───────────────────┘             │
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
| Arduino Nano | 1 | - | ✅ Existing |
| WS2812B LED Strip (20) | 1 | - | ✅ Existing |
| MCP2515 CAN Module | 1 | - | ✅ Existing (can repurpose) |
| Raspberry Pi 4B | 1 | - | ✅ Existing |
| **Total New Parts** | | **~$96** | |

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
