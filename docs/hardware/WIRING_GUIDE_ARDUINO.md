# 🔌 Arduino LED Controller Wiring Guide

This guide covers the **Arduino Nano LED controller** wiring for the gauge cluster bezel shift light.

## 📋 Overview

The Arduino Nano provides <1ms latency RPM-to-LED updates by:
1. Reading from its **dedicated** MCP2515 #3 (HS-CAN) module
2. Receiving LED sequence/pattern selection from the Pi via serial
3. Driving the WS2812B LED strip around the gauge cluster

**Note**: The Arduino has its own MCP2515 module that connects to the same HS-CAN bus wires (CANH/CANL) as the Pi's module. This parallel CAN connection is safe because CAN bus natively supports multiple listeners.

## ⚠️ Safety First

- **Disconnect vehicle battery** when making permanent connections
- **Use proper fusing** (2A recommended) on 12V power line
- **Test with multimeter** before connecting to Arduino
- **Ensure proper grounding** to vehicle chassis

## 📦 Required Components

### Core Components
| Component | Quantity | Notes |
|-----------|----------|-------|
| Arduino Nano V3.0 | 1 | ATmega328P, 16MHz |
| MCP2515 CAN Module | 1 | 8MHz crystal, Arduino's dedicated module |
| WS2812B LED Strip | 1 | 20 LEDs recommended |
| LM2596 Buck Converter | 1 | 12V → 5V, 3A capacity |

### Optional Components
| Component | Purpose |
|-----------|---------|
| 10K-100K Potentiometer | Brightness control |
| Vibration Motor | Haptic feedback at redline |
| 2A Fuse | Protection for 12V line |

## 🔧 Wiring Diagram

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                    ARDUINO NANO                          │
                    │                                                          │
                    │   D2 ←──── SPLICE from MCP2515 #1 INT (shared with Pi)  │
                    │   D3 ←──── Pi GPIO 14 (TX) - serial commands            │
                    │   D4 ────→ Pi GPIO 15 (RX) - optional responses         │
                    │   D5 ────→ WS2812B Data                                  │
                    │   D10 ←─── SPLICE from MCP2515 #1 CS                    │
                    │   D11 ←─── SPLICE from MCP2515 #1 MOSI                  │
                    │   D12 ←─── SPLICE from MCP2515 #1 MISO                  │
                    │   D13 ←─── SPLICE from MCP2515 #1 SCK                   │
                    │   A6 ←──── Brightness Pot (optional)                     │
                    │   5V ────→ Power Rail                                    │
                    │   GND ───→ Ground Rail                                   │
                    └─────────────────────────────────────────────────────────┘

                                        │
          ┌─────────────────────────────┼─────────────────────────────┐
          │                             │                             │
          ▼                             ▼                             ▼
    ┌───────────────┐           ┌───────────────┐             ┌─────────────┐
    │ SPLICED from  │           │ WS2812B Strip │             │ LM2596      │
    │ MCP2515 #1    │           │ (20 LEDs)     │             │ Buck Conv   │
    │ (Pi's module) │           ├───────────────┤             ├─────────────┤
    ├───────────────┤           │ 5V ─→ Buck 5V │             │ IN+ ← OBD16 │
    │ CS  → D10     │           │ GND ─→ GND    │             │ IN- ← OBD5  │
    │ MOSI→ D11     │           │ DIN ← D5      │             │ OUT+ → 5V   │
    │ MISO→ D12     │           └───────────────┘             │ OUT- → GND  │
    │ SCK → D13     │                                         └─────────────┘
    │ INT → D2      │ ◄── CRITICAL!
    └───────────────┘
    (See WIRING_GUIDE_PI_SYSTEM.md for splice details)
```

## 📍 Pin Connections

### MCP2515 #3 (Arduino's Dedicated Module) → Arduino

The Arduino has its own dedicated MCP2515 module with independent SPI connection:

| MCP2515 #3 Pin | Arduino Pin | Wire Color | Description |
|----------------|-------------|------------|-------------|
| VCC | 5V Rail | Red | Power (5V from buck converter) |
| GND | GND Rail | Black | Ground |
| CS | D10 | Yellow | SPI Chip Select |
| SO/MISO | D12 | Blue | SPI Data Out |
| SI/MOSI | D11 | Green | SPI Data In |
| SCK | D13 | White | SPI Clock |
| **INT** | **D2** | **Yellow/White** | **Interrupt (REQUIRED!)** |
| CANH | OBD Pin 6 | Blue (CAN) | CAN High (parallel with Pi's MCP2515) |
| CANL | OBD Pin 14 | White (CAN) | CAN Low (parallel with Pi's MCP2515) |

⚠️ **CRITICAL**: The INT pin MUST be connected to D2 for hardware interrupt support!

### WS2812B LED Strip → Arduino

| LED Pin | Connection | Wire Color | Notes |
|---------|------------|------------|-------|
| 5V | Buck Converter OUT+ | Red | Direct to buck converter for high current |
| GND | Common Ground | Black | Shared with Arduino |
| DIN | Arduino D5 | Green | Data signal |

### OBD-II Port Connections

The Arduino's MCP2515 #3 connects to the same HS-CAN wires as the Pi's MCP2515 #1 (in parallel):

| OBD-II Pin | Connection | Wire Color | Description |
|------------|------------|------------|-------------|
| Pin 6 | MCP2515 #3 CANH | Blue | CAN High signal (parallel with Pi) |
| Pin 14 | MCP2515 #3 CANL | White | CAN Low signal (parallel with Pi) |
| Pin 5 | Common Ground | Black | Ground reference |
| Pin 16 | Buck Converter IN+ | Red | 12V power supply |

```
       OBD-II Female Connector (looking at pins)
   ┌─────────────────────┐
   │  8  7  6  5  4  3  2  1 │  Pin 6:  CAN-H (Blue)  → MCP2515 CANH
   │    16 15 14 13 12 11 10 9│  Pin 14: CAN-L (White) → MCP2515 CANL
   └─────────────────────┘     Pin 5:  GND (Black)    → Common Ground
                               Pin 16: 12V (Red)      → Buck Converter IN+
```

### Pi Serial Connection (LED Sequence Commands)

The Arduino receives LED pattern/sequence selection from the Pi via software serial:

| Pi GPIO | Pi Pin # | Arduino Pin | Wire Color | Description |
|---------|----------|-------------|------------|-------------|
| GPIO 14 (TXD) | 8 | D3 (RX) | Green | Pi TX → Arduino RX |
| GPIO 15 (RXD) | 10 | D4 (TX) | Yellow | Arduino TX → Pi RX (optional) |
| GND | 6 | GND | Black | Common ground (REQUIRED) |

**Protocol**: Pi sends `SEQ:n` commands (n = 1-4) to select LED display mode.

### Optional: Brightness Potentiometer

| Pot Pin | Connection | Wire Color |
|---------|------------|------------|
| Left | GND | Black |
| Middle (Wiper) | Arduino A6 | Yellow |
| Right | 5V | Red |

### Optional: Haptic Motor

| Motor | Connection | Wire Color |
|-------|------------|------------|
| + | Arduino D3 (PWM) | Blue |
| - | GND | Black |

## ⚡ Power System

### LM2596 Buck Converter Setup

1. **Before connecting Arduino:**
   - Connect 12V input from OBD-II
   - Measure output with multimeter
   - Adjust potentiometer to exactly **5.0V**
   - Disconnect power

2. **Power distribution:**
   ```
   Buck 5V OUT+ ──┬── Arduino 5V      (Red)
                  ├── MCP2515 VCC     (Red)
                  └── WS2812B 5V      (Red)
   
   Buck GND OUT- ──┬── Arduino GND    (Black)
                   ├── MCP2515 GND    (Black)
                   └── WS2812B GND    (Black)
   ```

## 🔧 Assembly Steps

### Step 1: Prepare Buck Converter
1. Strip and tin wires for 12V input
2. Connect to buck converter IN+ and IN-
3. **Adjust output to 5.0V before connecting Arduino!**

### Step 2: Wire MCP2515 #3 Module (Arduino's Dedicated Module)
1. Connect SPI pins:
   - CS → D10 (Yellow)
   - MOSI → D11 (Green)
   - MISO → D12 (Blue)
   - SCK → D13 (White)
2. **Connect INT to D2** (Yellow - mark with tape to distinguish from CS)
3. Connect VCC to 5V rail (Red)
4. Connect GND to ground rail (Black)

### Step 3: Wire LED Strip
1. Connect 5V directly to buck converter (Red - not through Arduino)
2. Connect GND to ground rail (Black)
3. Connect DIN to Arduino D5 (Green)

### Step 4: Connect to OBD-II
1. Connect CAN-H (pin 6) to MCP2515 CANH (Blue)
2. Connect CAN-L (pin 14) to MCP2515 CANL (White)
3. Connect 12V (pin 16) through fuse to buck converter (Red)
4. Connect GND (pin 5) to ground rail (Black)

### Step 5: Optional Components
- Wire brightness pot to A6 (Yellow signal, Red/Black for power)
- Wire haptic motor to D3 (Blue signal, Black ground)

## 🧪 Testing

### Before Installing in Vehicle

1. **Power test**: Verify 5V on all VCC pins
2. **LED test**: LEDs should show rainbow startup animation
3. **CAN test**: Connect two MCP2515 modules for loopback test

### Bench Test with Simulated CAN

If you have two Arduino setups:
1. Connect CANH↔CANH, CANL↔CANL between modules
2. One sends test RPM, other displays on LEDs
3. Verify correct color zones

## 🚗 Vehicle Installation

1. **Locate OBD-II port** (under dashboard, driver side)
2. **Use Y-splitter** if you need OBD-II for diagnostics too
3. **Route wires safely** away from pedals and heat sources
4. **Secure all connections** with zip ties and heat shrink
5. **Mount LED strip** in visible position

## ❓ Troubleshooting

| Problem | Solution |
|---------|----------|
| LEDs show error animation | Check CAN wiring, verify INT connected to D2 |
| No LED activity | Check 5V power, verify D5 connection |
| RPM stuck at 0 | Verify CAN bus speed (500kbps for MX-5 NC) |
| LEDs flicker | Check ground connections, add capacitor to LED power |
| CAN init fails | Verify 8MHz crystal, check SPI connections |

## 📁 Related Files

- **Firmware**: `arduino/src/main.cpp`
- **Build config**: `arduino/platformio.ini`
- **Pi System Wiring**: [WIRING_GUIDE_PI_SYSTEM.md](WIRING_GUIDE_PI_SYSTEM.md)
- **Parts List**: [PARTS_LIST.md](PARTS_LIST.md)
