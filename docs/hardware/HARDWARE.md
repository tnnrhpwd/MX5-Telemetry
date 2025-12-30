# 🔧 MX5-Telemetry Hardware Guide

Complete hardware documentation: parts list, wiring diagrams, TPMS setup, and steering wheel control programming.

---

## 📋 Table of Contents

1. [Parts List & Budget](#parts-list--budget)
2. [System Architecture](#system-architecture)
3. [Wiring Guide](#wiring-guide)
4. [BLE TPMS Sensors](#ble-tpms-sensors)
5. [Steering Wheel Controls](#steering-wheel-controls-axxess-swc)
6. [Shopping Guide](#shopping-guide)

---

## Parts List & Budget

### 💰 Budget Overview

| Category | Estimated Cost (USD) |
|----------|---------------------|
| Raspberry Pi 4B + Accessories | $60-80 |
| ESP32-S3 Round Display | $25-35 |
| Arduino Nano | $5-10 |
| MCP2515 Modules (x3 total) | $9-21 |
| LED Strip + Power | $15-25 |
| BLE TPMS Sensors (x4) | $25-40 |
| Wiring & Connectors | $15-25 |
| **Total** | **$165-255** |

---

### 🖥️ Raspberry Pi 4B (Central Hub + Settings Cache)

| Item | Specifications | Qty | Price | Notes |
|------|---------------|-----|-------|-------|
| Raspberry Pi 4B | 2GB+ RAM | 1 | $35-55 | 4GB recommended |
| MicroSD Card | 32GB Class 10 | 1 | $8-15 | SanDisk recommended |
| Pi Power Supply | 5V 3A USB-C | 1 | $10-15 | Official Pi PSU recommended |
| MCP2515 CAN Module | 8MHz crystal | 2 | $6-14 | For Pi: HS-CAN + MS-CAN |
| Heatsink/Cooling | Passive or fan | 1 | $5-10 | Recommended for Pi 4 |
| Micro HDMI Cable | 1-2m | 1 | $5-10 | To Pioneer head unit |

**Pi GPIO Connections:**
- **SPI Bus** (shared): GPIO 10 (MOSI), GPIO 9 (MISO), GPIO 11 (SCLK)
- **MCP2515 #1 CS**: GPIO 8 (CE0) - HS-CAN
- **MCP2515 #2 CS**: GPIO 7 (CE1) - MS-CAN
- **Interrupts**: GPIO 25 (HS), GPIO 24 (MS)
- **Serial to Arduino**: GPIO 14/15 (TX/RX)
- **USB**: ESP32-S3 display connection

---

### 📺 ESP32-S3 Round Display

| Item | Specifications | Qty | Price | Notes |
|------|---------------|-----|-------|-------|
| Waveshare ESP32-S3-Touch-LCD-1.85 | 360x360 IPS, Touch | 1 | $25-35 | **Mounts in stock oil gauge hole** |
| USB-C Cable | Data capable | 1 | $5-10 | For Pi connection |

**Built-in Features:**
- 1.85" Round IPS LCD (360×360) - fits oil gauge hole perfectly
- Capacitive touch (CST816) - backup navigation
- QMI8658 IMU → **G-force data sent to Pi**
- ESP32-S3 BLE 5.0 → **TPMS sensor data sent to Pi**

---

### 🎯 Arduino Nano (LED Controller)

| Item | Specifications | Qty | Price | Notes |
|------|---------------|-----|-------|-------|
| Arduino Nano V3.0 | ATmega328P, 16MHz, 5V | 1 | $3-8 | Clone or official |
| MCP2515 CAN Module | 8MHz crystal | 1 | $3-7 | Arduino's dedicated HS-CAN module |

**Location**: Gauge cluster bezel (LED strip surrounds instruments)

---

### 💡 LED Strip

| Item | Specifications | Qty | Price | Notes |
|------|---------------|-----|-------|-------|
| WS2812B LED Strip | 20 LEDs, 5V, addressable RGB | 1 | $5-12 | IP65 waterproof recommended |

**Location**: Mounted around gauge cluster bezel

---

### 📡 BLE TPMS Sensors

| Item | Specifications | Qty | Price | Notes |
|------|---------------|-----|-------|-------|
| BLE TPMS Cap Sensors | Bluetooth 4.0, cap-mount | 4 | $25-40 | One per tire |

**Features to look for:**
- BLE broadcast (not proprietary app only)
- Pressure range: 0-80 PSI
- Temperature sensing
- Service UUID: 0xFBB0 (Chinese TPMS standard)

---

### 🔌 CAN Bus & Power

| Item | Specifications | Qty | Price | Notes |
|------|---------------|-----|-------|-------|
| OBD-II Extension Cable | Male-to-female, 1m | 1 | $8-15 | For easier access |
| LM2596 Buck Converter | 12V → 5V, 3A output | 1 | $2-5 | Adjustable voltage |
| 2A Blade Fuse + Holder | 12V automotive | 1 | $2-5 | Protection |
| Breadboard | 400 tie-points | 1 | $2-5 | Central power distribution |

---

### 🔌 Wiring & Connectors

| Item | Specifications | Qty | Price |
|------|---------------|-----|-------|
| 22 AWG Stranded Wire | Various colors | 5m | $5-10 |
| Heat Shrink Tubing Kit | Assorted sizes | 1 set | $5-10 |
| Dupont Jumper Wires | Female-to-female | 20pcs | $3-5 |
| JST Connectors | 3-pin, for LED strip | 2pcs | $1-3 |
| Zip Ties | 100mm | 20pcs | $2-5 |

---

## System Architecture

### Device Overview

| Device | Purpose | Location | CAN Connection |
|--------|---------|----------|----------------|
| **Raspberry Pi 4B** | CAN hub + settings cache + HDMI | Hidden (console/trunk) | MCP2515 #1 (HS) + #2 (MS) |
| **ESP32-S3 Round Display** | Gauge display + BLE TPMS + G-force | **Stock oil gauge hole** | None (serial from Pi) |
| **Arduino Nano** | RPM LED strip controller | Gauge cluster bezel | MCP2515 #3 (HS, dedicated) |

### MCP2515 Module Distribution (3 Total)

| Module | CAN Bus | Speed | OBD Pins | Controller |
|--------|---------|-------|----------|------------|
| MCP2515 #1 | HS-CAN | 500 kbps | 6/14 | Raspberry Pi |
| MCP2515 #2 | MS-CAN | 125 kbps | 3/11 | Raspberry Pi |
| MCP2515 #3 | HS-CAN | 500 kbps | 6/14 | Arduino Nano |

> **Why separate modules?** Using dedicated MCP2515 modules eliminates SPI bus contention and improves signal integrity. The CAN bus side (CANH/CANL) connects in parallel, which is safe since CAN is designed for multiple nodes.

### Data Flow Summary

```
OBD-II Port
    │
    ├─── HS-CAN (500k) ──┬──► Pi MCP2515 #1 ──► Pi processes all data
    │                    │
    │                    └──► Arduino MCP2515 ──► RPM → LED strip (direct, <1ms)
    │
    └─── MS-CAN (125k) ──────► Pi MCP2515 #2 ──► Steering wheel buttons
    
Pi (Central Hub)
    │
    ├──► ESP32-S3 (Serial) ──► Telemetry + SWC buttons + settings sync
    │    ◄─── ESP32-S3 ◄───── TPMS + G-force data
    │
    ├──► Arduino (Serial) ───► LED sequence selection + settings sync
    │
    └──► Pioneer (HDMI) ─────► Full dashboard display
```

---

## Wiring Guide

### 🏎️ System Overview

```
                    ┌─────────────────────────────────────────┐
                    │         BREADBOARD (Central Power)       │
                    │  5V Rail ◄── LM2596 ◄── OBD Pin 16 (12V)│
                    │  GND Rail ◄───────────── OBD Pin 5       │
                    └──┬────────┬────────┬────────┬───────────┘
                       │        │        │        │
                       ▼        ▼        ▼        ▼
                    Pi 5V    MCP2515  MCP2515  MCP2515   Arduino  LEDs
                            (HS Pi)  (MS Pi)  (HS Ard)   5V      5V
```

### ⚠️ Safety

- Disconnect vehicle battery for permanent connections
- Use 2A fuse on 12V lines
- Test voltages with multimeter before connecting devices
- Use heat shrink on all solder joints

---

### 🔌 OBD-II Pinout

```
   OBD-II Female (looking at pins)
   ┌─────────────────────┐
   │  8  7  6  5  4  3  2  1 │
   │    16 15 14 13 12 11 10 9│
   └─────────────────────┘
```

| Pin | Signal | Connects To |
|-----|--------|-------------|
| 3 | MS-CAN High (125k) | MCP2515 (MS-CAN Pi) CANH |
| 5 | Ground | Breadboard GND rail → All devices |
| 6 | HS-CAN High (500k) | MCP2515 (HS-CAN Pi) + (HS-CAN Ard) CANH |
| 11 | MS-CAN Low (125k) | MCP2515 (MS-CAN Pi) CANL |
| 14 | HS-CAN Low (500k) | MCP2515 (HS-CAN Pi) + (HS-CAN Ard) CANL |
| 16 | 12V DC | LM2596 → Breadboard 5V rail |

---

### 🥧 Raspberry Pi Wiring

> **Note**: Uses **BCM GPIO numbering** (Linux/Python standard)

**Wired Pins Summary:**

| Pin | GPIO | Connects To | Purpose |
|-----|------|-------------|---------|
| 6 | GND | Breadboard GND | Common ground |
| 8 | BCM14 (TXD) | Arduino D3 | Serial to Arduino |
| 10 | BCM15 (RXD) | Arduino D4 | Serial from Arduino |
| 18 | BCM24 | MCP2515 (MS-CAN Pi) INT | Interrupt (125k) |
| 19 | BCM10 (MOSI) | Both MCP2515 MOSI | SPI data out |
| 21 | BCM9 (MISO) | Both MCP2515 MISO | SPI data in |
| 22 | BCM25 | MCP2515 (HS-CAN Pi) INT | Interrupt (500k) |
| 23 | BCM11 (SCLK) | Both MCP2515 SCK | SPI clock |
| 24 | BCM8 (CE0) | MCP2515 (HS-CAN Pi) CS | Chip select |
| 26 | BCM7 (CE1) | MCP2515 (MS-CAN Pi) CS | Chip select |

**Total: 10 wires from Pi** (1×GND, 2×Serial, 3×SPI shared, 2×INT, 2×CS)

**MCP2515 → Pi Connections:**

| MCP2515 Pin | HS-CAN Pi | MS-CAN Pi |
|-------------|-----------|-----------|
| VCC | Breadboard 5V | Breadboard 5V |
| GND | Breadboard GND | Breadboard GND |
| CS | GPIO 8 (Pin 24) | GPIO 7 (Pin 26) |
| MOSI | GPIO 10 (Pin 19) | (shared) |
| MISO | GPIO 9 (Pin 21) | (shared) |
| SCK | GPIO 11 (Pin 23) | (shared) |
| INT | GPIO 25 (Pin 22) | GPIO 24 (Pin 18) |
| CANH | OBD Pin 6 | OBD Pin 3 |
| CANL | OBD Pin 14 | OBD Pin 11 |

**Other Pi Connections:**

| Connection | Pi | Device |
|------------|-----|--------|
| USB-A #1 | Any USB port | ESP32-S3 USB-C |
| HDMI | Micro HDMI | Pioneer head unit |

---

### 🔵 Arduino Nano Wiring

**MCP2515 (HS-CAN Arduino) Connections:**

| MCP2515 Pin | Arduino Pin | Notes |
|-------------|-------------|-------|
| VCC | Breadboard 5V | NOT from Arduino |
| GND | Breadboard GND | Common ground |
| CS | D10 | |
| MOSI | D11 | |
| MISO | D12 | |
| SCK | D13 | |
| **INT** | **D2** | ⚠️ REQUIRED for interrupts |
| CANH | OBD Pin 6 | Parallel with Pi |
| CANL | OBD Pin 14 | Parallel with Pi |

**Other Arduino Connections:**

| Connection | Arduino Pin | Notes |
|------------|-------------|-------|
| USB | Mini-B / Micro-B | → Pi USB-A (primary serial) |
| LED Data | D5 | WS2812B DIN |
| Pi Serial RX | D3 | ← Pi GPIO 14 (backup serial) |
| Pi Serial TX | D4 | → Pi GPIO 15 (backup serial) |

**WS2812B LED Strip:**

| LED Pin | Connection |
|---------|------------|
| 5V | Breadboard 5V rail |
| GND | Breadboard GND rail |
| DIN | Arduino D5 |

---

### 📺 ESP32-S3 Display

Single USB-C cable to Pi USB-A provides both power and serial (`/dev/ttyACM0`).

---

### ⚡ Power Distribution (Centralized Breadboard)

```
OBD Pin 16 (12V) ──[2A Fuse]──► LM2596 ──► BREADBOARD 5V RAIL
                                                  │
                  ┌───────────────┬───────────────┼───────────────┬───────────────┐
                  ▼               ▼               ▼               ▼               ▼
             Raspberry Pi    MCP2515         MCP2515         MCP2515          WS2812B
               (5V pin)     (HS-CAN Pi)     (MS-CAN Pi)    (HS-CAN Ard)      LED Strip
                  │               │               │               │               │
                  ▼               ▼               ▼               ▼               ▼
             Arduino Nano
               (5V pin)

OBD Pin 5 (GND) ──────────────► BREADBOARD GND RAIL ──► All devices
```

**LM2596 Setup:**
1. Connect 12V input, measure output with multimeter
2. Adjust to exactly **5.0V** before connecting anything
3. Connect output to breadboard 5V/GND rails
4. All devices draw power from breadboard rails

---

### ✅ Quick Checklist

**Breadboard Power:**
- [ ] Buck converter adjusted to 5.0V
- [ ] 2A fuse on 12V line
- [ ] All devices powered from breadboard (not from Pi/Arduino)

**Pi MCP2515s:**
- [ ] VCC from breadboard 5V (not Pi 3.3V)
- [ ] INT pins connected (GPIO 25, 24)
- [ ] SPI shared, CS separate

**Arduino:**
- [ ] Arduino 5V from breadboard
- [ ] MCP2515 INT → D2 (critical!)
- [ ] LED strip from breadboard 5V

**CAN Bus:**
- [ ] HS-CAN (pins 6/14) spliced to both HS-CAN modules
- [ ] MS-CAN (pins 3/11) to MS-CAN Pi module only

---

### 🧪 Testing

**Pi CAN Bus:**
```bash
ip link show can0 can1
sudo ip link set can0 up type can bitrate 500000
sudo ip link set can1 up type can bitrate 125000
candump can0  # Should see traffic with ignition ON
```

**ESP32 Serial:**
```bash
ls /dev/ttyACM*  # Should show device
```

**Arduino Serial:**
```bash
echo "SEQ:1" > /dev/serial0
```

---

## BLE TPMS Sensors

### Identified TPMS Sensors

All four sensors show as **Non Connectable** BLE devices (TPMS sensors broadcast advertising data without requiring connection).

| Tire Position | MAC Address | Distance |
|--------------|-------------|----------|
| Unknown | `14:27:4B:11:11:11` | ~25m |
| Unknown | `14:26:6D:11:11:11` | ~28m |
| Unknown | `14:10:50:11:11:11` | ~40m |
| Unknown | `14:13:1F:11:11:11` | ~28m |

**Note:** All MACs share pattern `14:XX:XX:11:11:11` suggesting same manufacturer.

### Service UUID

- **UUID:** `0xFBB0`
- **Type:** 16-bit BLE Service UUID
- **Standard:** Common Chinese/generic BLE TPMS (SYSGRATION compatible)

### Data Format

**Raw advertising packet:**
```
0x0201060303B0FB12FFAC00853D3C000A2500D0281111111F1314
```

**Manufacturer Data (18 bytes):**
```
Offset  Hex   Purpose
------  ----  -------
0-1     AC00  Manufacturer ID
2       85    PRESSURE (raw)
3       3D    TEMPERATURE (raw)
4-10    ...   Status/padding
11-16   ...   Sensor ID (matches MAC)
```

### Decoding Functions

```cpp
// Pressure decoding (returns PSI)
// Calibrated 2025-12-15
float decodePressure(uint8_t raw) {
    float kPa = raw + 56.0f;  // Calibrated offset
    return kPa / 6.895f;
}

// Temperature decoding (returns Fahrenheit)
// Calibrated 2025-12-15
float decodeTemperature(uint8_t raw) {
    float celsius = raw - 40.0f;  // Calibrated offset
    return celsius * 9.0f / 5.0f + 32.0f;
}
```

### Implementation Status ✅

**ESP32-S3 BLE TPMS Scanner:**
- Location: `display/src/main.cpp`
- Uses NimBLE-Arduino library
- Scans every 5 seconds
- Sends data to Pi: `TPMS_PSI:FL,FR,RL,RR` and `TPMS_TEMP:FL,FR,RL,RR`

**Raspberry Pi Integration:**
- Location: `pi/ui/src/esp32_serial_handler.py`
- Receives TPMS messages from ESP32
- Updates telemetry object

### Tire Position Mapping

To update which sensor is on which tire, edit `display/src/main.cpp`:
```cpp
// Tire positions: 0=FL, 1=FR, 2=RL, 3=RR
int tpmsTireMapping[4] = {0, 1, 2, 3};
```

---

## Steering Wheel Controls (Axxess SWC)

### Module Information

**Module:** Axxess ASWC-1 (or Metra SWC interface)  
**Head Unit:** Pioneer AVH-W4500NEX  
**Vehicle:** Mazda MX-5 NC (2006-2015)

### LED Indicators

| LED State | Meaning |
|-----------|---------|
| **Green Solid** | Ready / Normal operation |
| **Green Blinking** | Programming mode active |
| **Red Solid** | Error / Not recognized |
| **Red Blinking** | Waiting for button press |

---

### Initial Setup (Auto-Detect)

1. **Power off** the head unit
2. **Disconnect** SWC module from head unit's remote wire
3. **Reconnect** everything
4. **Turn ignition ON** (ACC or RUN position)
5. **Wait 30 seconds** - module will attempt auto-detection
6. **Green LED** should illuminate when successful

---

### Manual Programming Mode

**Enter Programming:**
1. **Turn ignition ON**
2. **Press and HOLD** program button for **5+ seconds**
3. **Release** when **Green LED starts blinking**

**Program Each Button:**
1. **Wait for Red LED to blink**
2. **Press steering wheel button** you want to assign
3. **Green LED flashes** to confirm
4. Module advances to next function

**Button Functions (in order):**
1. Volume Up
2. Volume Down
3. Seek Up / Next
4. Seek Down / Previous
5. Source
6. Mute
7. Phone / Bluetooth
8. Voice

**Skip a Function:**
- Press program button briefly (1 sec) OR wait 10 seconds

**Exit Programming:**
- Hold program button 3 seconds OR wait 30 seconds timeout
- Green LED goes solid = complete

---

### Factory Reset

1. **Disconnect** module from power
2. **Press and hold** program button
3. **While holding**, reconnect power
4. **Continue holding** for 10 seconds
5. Both LEDs flash = reset complete

---

### Troubleshooting SWC

| Problem | Solution |
|---------|----------|
| Red LED stays on | Check SWC harness, verify ground |
| Green LED never comes on | Check 12V ACC and ground connections |
| Buttons don't work | Re-enter programming, check head unit settings |
| Module won't program | Hold button longer, disconnect/reconnect power |

**After CAN Bus Interference:**
1. Disconnect telemetry system
2. Disconnect vehicle battery for 30 seconds
3. Reconnect battery
4. Perform factory reset on ASWC module
5. Reprogram all buttons
6. Test before reconnecting telemetry

---

## Shopping Guide

### 🛍️ Where to Buy

**Fast Shipping (1-3 days):**
- **Amazon** - Prime shipping, easy returns
- **Adafruit** - Quality components, US-based
- **SparkFun** - Quality electronics, tutorials

**Budget Options (2-4 weeks):**
- **AliExpress** - Very cheap, long shipping
- **eBay** - Mix of domestic/international
- **Banggood** - Similar to AliExpress

**Local Options:**
- **Micro Center** - Excellent prices if near store
- **RadioShack** - Limited locations remaining

---

### 🔧 Tools Required

| Tool | Purpose | Approx. Cost |
|------|---------|--------------|
| Soldering Iron + Solder | Wire connections | $15-40 |
| Wire Strippers | Strip insulation | $5-15 |
| Multimeter | Voltage testing | $10-25 |
| Heat Gun or Lighter | Shrink tubing | $10-30 |
| Crimping Tool | Crimp connectors | $10-25 |

---

### 💾 Save Money Tips

1. **Buy in bulk** - 5-packs often cheaper per unit
2. **Use coupon codes** - Check RetailMeNot, Honey
3. **Wait for sales** - Prime Day, Black Friday, 11.11 (AliExpress)
4. **Bundle shipping** - Order multiple items from same seller
5. **Reuse what you have** - Old USB cables, wire from other projects

---

### ⏱️ Lead Time Planning

| Supplier | Typical Shipping | Total Time |
|----------|-----------------|------------|
| Amazon (Prime) | 1-2 days | 1-2 days |
| Adafruit/SparkFun | 3-7 days | 3-7 days |
| AliExpress | 15-45 days | 4-6 weeks |
| eBay | 1-30 days | Varies |

---

## Related Documentation

- [../DEPLOYMENT_GUIDE.md](../DEPLOYMENT_GUIDE.md) - Build and deployment procedures
- [../ARCHITECTURE.md](../ARCHITECTURE.md) - System architecture and design
- [../LED_SYSTEM.md](../LED_SYSTEM.md) - LED strip system documentation

---

**Last Updated:** December 29, 2025
