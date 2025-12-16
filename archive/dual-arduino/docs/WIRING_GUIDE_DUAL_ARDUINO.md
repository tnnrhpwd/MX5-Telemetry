# 🔌 Dual Arduino Wiring Guide

This guide covers the **dual Arduino setup** - using a Master Arduino for data logging and a Slave Arduino for LED control.

## ℹ️ When to Use Dual Arduino

Choose the dual Arduino setup when you need:
- **SD card data logging** (GPS, RPM, speed logs)
- **GPS tracking** with waypoint recording
- **USB command interface** for laptop control
- **Isolation** between logging and display functions

> 💡 **For simple RPM-to-LED display only**, see `WIRING_GUIDE_SINGLE_ARDUINO.md`

## ⚠️ Safety First

- **Disconnect vehicle battery** when making permanent connections
- **Use proper fusing** (2A recommended) on 12V power line
- **Test with multimeter** before connecting to Arduino
- **Ensure proper grounding** to vehicle chassis

## 📦 Required Components

### Core Components
| Component | Quantity | Notes |
|-----------|----------|-------|
| Arduino Nano V3.0 | 2 | ATmega328P, 16MHz |
| MCP2515 + TJA1050 Module | 1 | 8MHz crystal version |
| WS2812B LED Strip | 1 | 20 LEDs recommended |
| MicroSD Card Module | 1 | SPI interface |
| Neo-6M GPS Module | 1 | 9600 baud |
| LM2596 Buck Converter | 1 | 12V → 5V, 3A capacity |
| OBD-II Male Connector | 1 | Or Y-splitter cable |

### Optional Components
| Component | Purpose |
|-----------|---------|
| 10K-100K Potentiometer | Brightness control |
| Vibration Motor | Haptic feedback at redline |
| 2A Fuse | Protection for 12V line |

## 🔧 System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           MASTER ARDUINO (Logger)                                │
│                                                                                  │
│   ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐                   │
│   │ MCP2515 │     │ SD Card │     │ Neo-6M  │     │  USB    │                   │
│   │ CAN Bus │     │ Module  │     │  GPS    │     │ Serial  │                   │
│   └────┬────┘     └────┬────┘     └────┬────┘     └────┬────┘                   │
│        │               │               │               │                         │
│   SPI (D10,11,12,13)   SPI (D4)    D8,D9 (SW Serial)  D0,D1                     │
│        │               │               │               │                         │
│        └───────────────┴───────────────┴───────────────┘                         │
│                                    │                                             │
│                            D6 (Bit-bang TX)                                      │
│                                    │                                             │
└────────────────────────────────────┼─────────────────────────────────────────────┘
                                     │
                                     │ 1200 baud serial
                                     │ Commands: !R3500\n
                                     ▼
┌────────────────────────────────────┼─────────────────────────────────────────────┐
│                            D2 (SoftwareSerial RX)                                │
│                                    │                                             │
│                           SLAVE ARDUINO (LED)                                    │
│                                                                                  │
│   ┌───────────────┐     ┌─────────────┐     ┌───────────────┐                   │
│   │ WS2812B Strip │     │ Brightness  │     │ Haptic Motor  │                   │
│   │   (20 LEDs)   │     │ Pot (A6)    │     │   (D3)        │                   │
│   └───────────────┘     └─────────────┘     └───────────────┘                   │
│         D5                   A6                   D3                             │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## 📍 Master Arduino Pinout

| Pin | Function | Connection |
|-----|----------|------------|
| D0 | RX | USB Serial (don't use) |
| D1 | TX | USB Serial (don't use) |
| D4 | CS | SD Card Module CS |
| D6 | TX | **To Slave D2** (bit-bang serial) |
| D7 | INT | MCP2515 Interrupt |
| D8 | RX | GPS TX (SoftwareSerial) |
| D9 | TX | GPS RX (SoftwareSerial) |
| D10 | CS | MCP2515 CS |
| D11 | MOSI | SPI MOSI (shared) |
| D12 | MISO | SPI MISO (shared) |
| D13 | SCK | SPI SCK (shared) |
| 5V | Power | From Buck Converter |
| GND | Ground | Common Ground |

## 📍 Slave Arduino Pinout

| Pin | Function | Connection |
|-----|----------|------------|
| D2 | RX | **From Master D6** (SoftwareSerial) |
| D3 | PWM | Haptic Motor (optional) |
| D5 | Data | WS2812B LED Strip |
| A6 | Analog | Brightness Potentiometer (optional) |
| 5V | Power | From Buck Converter |
| GND | Ground | Common Ground |

## 🔧 Wiring Diagram

### Master Arduino

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                  MASTER ARDUINO                          │
                    │                                                          │
                    │   D4 ────→ SD Card CS                                    │
                    │   D6 ────→ Slave D2 (TX to Slave)                        │
                    │   D7 ←──── MCP2515 INT                                   │
                    │   D8 ←──── GPS TX                                        │
                    │   D9 ────→ GPS RX                                        │
                    │   D10 ───→ MCP2515 CS                                    │
                    │   D11 ───→ MOSI (shared SPI)                             │
                    │   D12 ←─── MISO (shared SPI)                             │
                    │   D13 ───→ SCK (shared SPI)                              │
                    │   5V ────→ Power Rail                                    │
                    │   GND ───→ Ground Rail                                   │
                    └─────────────────────────────────────────────────────────┘
```

### Slave Arduino

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                   SLAVE ARDUINO                          │
                    │                                                          │
                    │   D2 ←──── Master D6 (RX from Master)                    │
                    │   D3 ────→ Haptic Motor (optional)                       │
                    │   D5 ────→ WS2812B Data                                  │
                    │   A6 ←──── Brightness Pot (optional)                     │
                    │   5V ────→ Power Rail                                    │
                    │   GND ───→ Ground Rail                                   │
                    └─────────────────────────────────────────────────────────┘
```

## 🔗 Inter-Arduino Communication

The Master and Slave communicate via a simple serial protocol:

```
Master D6 (TX) ────────────→ Slave D2 (RX)
Master GND ─────────────────→ Slave GND  (REQUIRED!)
```

**Protocol Details:**
- Baud rate: 1200 (slow but reliable)
- Format: `!<command>\n`
- Example: `!R3500\n` sets RPM to 3500

| Command | Example | Description |
|---------|---------|-------------|
| R | `!R3500\n` | Set RPM value |
| S | `!S60\n` | Set speed (km/h) |
| E | `!E\n` | Error animation |
| W | `!W\n` | Rainbow wave |
| C | `!C\n` | Clear LEDs |
| B | `!B128\n` | Set brightness |

## ⚡ Power System

Both Arduinos share the same 5V power supply from the buck converter:

```
OBD-II Pin 16 (12V) ──► [2A Fuse] ──► Buck IN+
OBD-II Pin 5 (GND)  ──────────────► Buck IN-

Buck OUT+ (5V) ──┬── Master 5V
                 ├── Slave 5V
                 ├── MCP2515 VCC
                 ├── SD Card VCC
                 ├── GPS VCC
                 └── WS2812B 5V

Buck OUT- (GND) ──┬── Master GND
                  ├── Slave GND
                  ├── MCP2515 GND
                  ├── SD Card GND
                  ├── GPS GND
                  └── WS2812B GND
```

## 🔧 Assembly Steps

### Step 1: Prepare Power System
1. Wire buck converter to OBD-II 12V and GND
2. **Adjust to exactly 5.0V** before connecting Arduinos
3. Create 5V and GND power rails

### Step 2: Wire Master Arduino
1. Connect MCP2515 SPI pins (D10, D11, D12, D13, D7)
2. Connect SD Card SPI (D4, shared MOSI/MISO/SCK)
3. Connect GPS to D8 (RX) and D9 (TX)
4. Connect D6 wire for Slave communication

### Step 3: Wire Slave Arduino
1. Connect D2 to Master's D6 wire
2. Connect D5 to LED strip DIN
3. **Connect GND to Master's GND** (required!)
4. Optional: Wire brightness pot to A6
5. Optional: Wire haptic motor to D3

### Step 4: Connect Peripherals
1. Wire CAN-H and CAN-L to OBD-II port
2. Connect LED strip power to buck converter
3. Connect SD card to power rail

## 🧪 Testing

### Test Master Alone
1. Upload `master/` firmware
2. Open Serial Monitor at 115200 baud
3. Type `T` for status - should show CAN/GPS/SD status
4. Type `S` to start logging

### Test Slave Alone
1. Upload `slave/` firmware
2. Open Serial Monitor at 115200 baud
3. Type test commands: `R3000`, `E`, `C`
4. LEDs should respond to commands

### Test Together
1. Connect Master D6 → Slave D2
2. Connect common GND
3. Start both - Slave should show LEDs based on CAN data

## ❓ Troubleshooting

| Problem | Solution |
|---------|----------|
| Slave shows error animation | Check D6→D2 connection, verify common GND |
| No SD logging | Check D4 CS pin, verify SD card format (FAT32) |
| GPS not working | Check D8/D9 connections, wait for satellite fix |
| RPM corruption | Verify 1200 baud, check GND connection |
| Master hangs | SD card issue - check card and formatting |

## 📁 Related Files

- **Master Firmware**: `master/src/main.cpp`
- **Slave Firmware**: `slave/src/main.cpp`
- **Master Config**: `master/platformio.ini`
- **Slave Config**: `slave/platformio.ini`
- **Single Arduino alternative**: `docs/hardware/WIRING_GUIDE_SINGLE_ARDUINO.md`

## 🔄 Backup Location

A complete backup of this dual Arduino setup is stored in:
`backup_dual_arduino/`
