# 🔌 Single Arduino Wiring Guide

This guide covers the **single Arduino setup** - the simplest and most responsive configuration for CAN bus RPM reading and LED display.

## ✅ Advantages of Single Arduino

| Benefit | Description |
|---------|-------------|
| **Zero Latency** | Direct CAN → LED update path (<1ms) |
| **No Data Corruption** | No serial link to corrupt RPM values |
| **Simple Wiring** | 50% fewer connections than dual setup |
| **Lower Power** | One Arduino instead of two |
| **Easier Debugging** | Single point of failure |

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
| MCP2515 + TJA1050 Module | 1 | 8MHz crystal version |
| WS2812B LED Strip | 1 | 20 LEDs recommended |
| LM2596 Buck Converter | 1 | 12V → 5V, 3A capacity |
| OBD-II Male Connector | 1 | Or Y-splitter cable |

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
                    │   D2 ←──── INT (CAN Interrupt - CRITICAL!)              │
                    │   D5 ────→ WS2812B Data                                  │
                    │   D10 ───→ MCP2515 CS                                    │
                    │   D11 ───→ MCP2515 MOSI                                  │
                    │   D12 ←─── MCP2515 MISO                                  │
                    │   D13 ───→ MCP2515 SCK                                   │
                    │   A6 ←──── Brightness Pot (optional)                     │
                    │   D3 ────→ Haptic Motor (optional)                       │
                    │   5V ────→ Power Rail                                    │
                    │   GND ───→ Ground Rail                                   │
                    └─────────────────────────────────────────────────────────┘

                                        │
          ┌─────────────────────────────┼─────────────────────────────┐
          │                             │                             │
          ▼                             ▼                             ▼
    ┌───────────┐               ┌───────────────┐             ┌─────────────┐
    │ MCP2515   │               │ WS2812B Strip │             │ LM2596      │
    │ CAN Module│               │ (20 LEDs)     │             │ Buck Conv   │
    ├───────────┤               ├───────────────┤             ├─────────────┤
    │ VCC ─→ 5V │               │ 5V ─→ Buck 5V │             │ IN+ ← OBD16 │
    │ GND ─→ GND│               │ GND ─→ GND    │             │ IN- ← OBD5  │
    │ CS ─→ D10 │               │ DIN ← D5      │             │ OUT+ → 5V   │
    │ SO ─→ D12 │               └───────────────┘             │ OUT- → GND  │
    │ SI ─→ D11 │                                             └─────────────┘
    │ SCK─→ D13 │                        
    │ INT─→ D2  │  ◄── CRITICAL!                    ┌─────────────┐
    │ CANH ← ─┬─│─────────────────────────────────► │ OBD-II Port │
    │ CANL ← ─┴─│─────────────────────────────────► │ Pin 6: CANH │
    └───────────┘                                   │ Pin 14: CANL│
                                                    │ Pin 5: GND  │
                                                    │ Pin 16: 12V │
                                                    └─────────────┘
```

## 📍 Pin Connections

### MCP2515 CAN Module → Arduino

| MCP2515 Pin | Arduino Pin | Wire Color | Description |
|-------------|-------------|------------|-------------|
| VCC | 5V | Red | Power supply |
| GND | GND | Black | Ground |
| CS | D10 | Yellow | SPI Chip Select |
| SO (MISO) | D12 | Blue | SPI Data Out |
| SI (MOSI) | D11 | Green | SPI Data In |
| SCK | D13 | White | SPI Clock |
| **INT** | **D2** | **Yellow/White** | **Interrupt (REQUIRED!)** |

> 💡 **Tip**: Use striped tape or heat shrink to differentiate wires of the same color (e.g., mark the INT wire with tape to distinguish from CS).

⚠️ **CRITICAL**: The INT pin MUST be connected to D2 for hardware interrupt support!

### WS2812B LED Strip → Arduino

| LED Pin | Connection | Wire Color | Notes |
|---------|------------|------------|-------|
| 5V | Buck Converter OUT+ | Red | Direct to buck converter for high current |
| GND | Common Ground | Black | Shared with Arduino |
| DIN | Arduino D5 | Green | Data signal |

### OBD-II Port Connections

| OBD-II Pin | Connection | Wire Color | Description |
|------------|------------|------------|-------------|
| Pin 6 | MCP2515 CANH | Blue | CAN High signal |
| Pin 14 | MCP2515 CANL | White | CAN Low signal |
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

### Step 2: Wire MCP2515 Module
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

- **Firmware**: `single/src/main.cpp`
- **Build config**: `single/platformio.ini`
- **Dual Arduino alternative**: `docs/hardware/WIRING_GUIDE_DUAL_ARDUINO.md`
