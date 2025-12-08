# MX5 Raspberry Pi + ESP32-S3 Display Integration

## Project Overview

Integrate a Raspberry Pi 4 (HDMI output to Pioneer AVH-W4500NEX) and ESP32-S3 Round Display into the 2008 MX5 NC GT, controlled via stock steering wheel buttons through CAN bus.

### Goals
- Display telemetry data on ESP32-S3 round LCD (gauges, RPM, speed)
- Display apps/media on Raspberry Pi via HDMI to Pioneer head unit
- Control both devices using stock MX5 steering wheel buttons (no touch needed)
- Read vehicle data from HS-CAN and MS-CAN buses

---

## Hardware Components

| Component | Purpose | Status |
|-----------|---------|--------|
| Raspberry Pi 4B | HDMI output to Pioneer AVH-W4500NEX | ✅ Have |
| ESP32-S3 Round Display | 1.85" gauge display | 🔲 Need |
| Arduino Nano | RPM LED strip controller | ✅ Have |
| MCP2515 Module x2 | CAN bus readers (HS + MS) | 🔲 Need |
| Pioneer AVH-W4500NEX | Head unit with HDMI input | ✅ Have |
| WS2812B LED Strip | RPM shift light (20 LEDs) | ✅ Have |
| OBD-II Breakout | Access CAN bus pins | 🔲 Need |

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

### Block Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        MX5 NC CAN BUS ARCHITECTURE                           │
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
│        │                               │                                     │
│        └───────────┬───────────────────┘                                     │
│                    │                                                         │
│                    ▼                                                         │
│          ┌─────────────────────┐                                             │
│          │      ESP32-S3       │                                             │
│          │     MAIN HUB        │                                             │
│          │                     │                                             │
│          │  • Reads HS-CAN     │                                             │
│          │  • Reads MS-CAN     │                                             │
│          │  • Round LCD Display│                                             │
│          │  • Forwards to Pi   │                                             │
│          │  • Forwards to LED  │                                             │
│          └──────┬───────┬──────┘                                             │
│                 │       │                                                    │
│     Serial/UART │       │ WiFi/Serial                                       │
│     (RPM only)  │       │ (All data + buttons)                              │
│                 ▼       ▼                                                    │
│        ┌────────────┐  ┌────────────┐                                       │
│        │Arduino Nano│  │Raspberry Pi│                                       │
│        │  RPM LEDs  │  │   HDMI     │──────▶ Pioneer AVH-W4500NEX           │
│        └────────────┘  └────────────┘                                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
HS-CAN (500kbps)                    MS-CAN (125kbps)
════════════════                    ════════════════
• RPM                               • Steering Wheel Buttons
• Vehicle Speed                     • Cruise Control Buttons
• Throttle Position                 • Door Status
• Engine Temp                       • Lights Status
• Gear Position                     • Climate Control

        │                                  │
        └──────────────┬───────────────────┘
                       │
                       ▼
             ┌─────────────────────┐
             │      ESP32-S3       │
             │    (MAIN HUB)       │
             └─────────┬───────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
  ┌──────────┐  ┌──────────┐  ┌──────────┐
  │  LOCAL   │  │ ARDUINO  │  │    PI    │
  │ DISPLAY  │  │  (LED)   │  │  (HDMI)  │
  ├──────────┤  ├──────────┤  ├──────────┤
  │ RPM Gauge│  │ RPM only │  │ All Data │
  │ Speed    │  │ via UART │  │ + SWC    │
  │ Buttons  │  │          │  │ Commands │
  │ (React)  │  │          │  │ via WiFi │
  └──────────┘  └──────────┘  └──────────┘
```

---

## Wiring Diagrams

### ESP32-S3 Pin Assignments

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ESP32-S3 WIRING DIAGRAM                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ESP32-S3 Pin      │  Connection                                           │
│   ══════════════════│══════════════════════════════════════                 │
│                     │                                                        │
│   --- MCP2515 #1 (HS-CAN) via SPI Bus 1 ---                                 │
│   GPIO 12 (SCK)     │  MCP2515 #1 SCK                                       │
│   GPIO 11 (MOSI)    │  MCP2515 #1 SI                                        │
│   GPIO 13 (MISO)    │  MCP2515 #1 SO                                        │
│   GPIO 10 (CS1)     │  MCP2515 #1 CS                                        │
│   GPIO 9  (INT1)    │  MCP2515 #1 INT                                       │
│                     │                                                        │
│   --- MCP2515 #2 (MS-CAN) via SPI Bus 2 ---                                 │
│   GPIO 36 (SCK2)    │  MCP2515 #2 SCK                                       │
│   GPIO 35 (MOSI2)   │  MCP2515 #2 SI                                        │
│   GPIO 37 (MISO2)   │  MCP2515 #2 SO                                        │
│   GPIO 34 (CS2)     │  MCP2515 #2 CS                                        │
│   GPIO 38 (INT2)    │  MCP2515 #2 INT                                       │
│                     │                                                        │
│   --- Serial to Arduino (RPM LED) ---                                       │
│   GPIO 43 (TX)      │  Arduino D2 (RX via SoftwareSerial)                   │
│   GPIO 44 (RX)      │  Arduino D3 (TX) [optional feedback]                  │
│                     │                                                        │
│   --- Serial/WiFi to Raspberry Pi ---                                       │
│   GPIO 17 (TX2)     │  Pi GPIO 15 (RXD) [or use WiFi]                       │
│   GPIO 18 (RX2)     │  Pi GPIO 14 (TXD) [or use WiFi]                       │
│                     │                                                        │
│   --- Display (already wired on module) ---                                 │
│   Internal SPI      │  GC9A01 LCD                                           │
│   Internal I2C      │  Touch FT5x06                                         │
│                     │                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### MCP2515 Module Connections

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MCP2515 MODULE CONNECTIONS                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   MCP2515 #1 (HS-CAN)          MCP2515 #2 (MS-CAN)                          │
│   ═══════════════════          ═══════════════════                          │
│                                                                              │
│   VCC ──── 3.3V                VCC ──── 3.3V                                │
│   GND ──── GND                 GND ──── GND                                 │
│   CS  ──── GPIO 10             CS  ──── GPIO 34                             │
│   SO  ──── GPIO 13             SO  ──── GPIO 37                             │
│   SI  ──── GPIO 11             SI  ──── GPIO 35                             │
│   SCK ──── GPIO 12             SCK ──── GPIO 36                             │
│   INT ──── GPIO 9              INT ──── GPIO 38                             │
│                                                                              │
│   CANH ─── OBD Pin 6           CANH ─── OBD Pin 3                           │
│   CANL ─── OBD Pin 14          CANL ─── OBD Pin 11                          │
│                                                                              │
│   ⚠️  120Ω terminator usually not needed when tapping OBD port              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

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

| Item | Qty | Est. Cost | Link |
|------|-----|-----------|------|
| MCP2515 CAN Module | 2 | $10 | Amazon/AliExpress |
| ESP32-S3 1.85" Round Display | 1 | $25 | Waveshare/AliExpress |
| OBD-II Breakout/Splitter | 1 | $15 | Amazon |
| Jumper Wires (M-F, M-M) | 1 pack | $8 | Amazon |
| 12V to 5V 3A Buck Converter | 1 | $8 | Amazon |
| Project Enclosure | 1 | $10 | Amazon |
| **Total Estimated** | | **~$76** | |

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

## Notes & Ideas

- Consider adding voice control via ESP32-S3's speech recognition
- Could add lap timer functionality with GPS module
- Bluetooth OBD adapter as backup/alternative to wired CAN
- Android Auto via OpenAuto Pro as future enhancement
