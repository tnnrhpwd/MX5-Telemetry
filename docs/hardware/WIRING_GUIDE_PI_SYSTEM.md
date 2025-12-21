# 🔌 Raspberry Pi CAN Bus Wiring Guide

Complete wiring guide for the Raspberry Pi 4B CAN hub with 2 MCP2515 modules (HS-CAN spliced to Arduino), ESP32-S3 display, and Arduino LED controller.

## 🏎️ System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MX5-Telemetry System (2 MCP2515 Modules)                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                     RASPBERRY PI 4B                                 │    │
│  │                  (Central Hub + Settings Cache)                     │    │
│  │                                                                     │    │
│  │  GPIO 8 (CE0)     → MCP2515 #1 CS (HS-CAN, spliced to Arduino)     │    │
│  │  GPIO 7 (CE1)     → MCP2515 #2 CS (MS-CAN, Pi only)                │    │
│  │  GPIO 10/9/11     → MCP2515 #1 SPI (spliced to Arduino)            │    │
│  │  GPIO 25          → MCP2515 #1 INT (spliced to Arduino D2)         │    │
│  │  GPIO 24          → MCP2515 #2 INT                                 │    │
│  │  GPIO 14/15       → Arduino Nano RX/TX (serial)                    │    │
│  │  USB-A            → ESP32-S3 USB-C                                 │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│           │                        │                      │                 │
│           │                        │                      │                 │
│  ┌────────▼────────┐    ┌──────────▼─────┐    ┌────────────────────────┐   │
│  │   MCP2515 #1    │    │   MCP2515 #2   │    │   ESP32-S3 Display     │   │
│  │   (HS-CAN)      │    │   (MS-CAN)     │    │   (Oil Gauge Hole)     │   │
│  │   500 kbps      │    │   125 kbps     │    │                        │   │
│  │   Pin 6/14      │    │   Pin 3/11     │    │   • Receives telemetry │   │
│  │                 │    │                │    │   • BLE TPMS → Pi      │   │
│  │  SPI wires are  │    │   Pi only      │    │   • G-Force IMU → Pi   │   │
│  │  SPLICED to:    │    │                │    └────────────────────────┘   │
│  │  • Pi GPIO      │    └───────┬────────┘                                 │
│  │  • Arduino SPI  │            │                                          │
│  └────────┬────────┘            │                                          │
│           │                     │                                          │
│   ════════╪═════════════════════╪══════════════════════════════════════    │
│           │    SPI SPLICE       │                                          │
│           │    ───────────      │                                          │
│           │                     │                                          │
│  ┌────────▼────────────────────────────────────────────────────────────┐   │
│  │                      ARDUINO NANO                                    │   │
│  │                  (Gauge Cluster Bezel)                               │   │
│  │                                                                      │   │
│  │  D2 (INT)        ← SPLICED from MCP2515 #1 INT                      │   │
│  │  D3 (RX)         ← Pi GPIO 14 (TX) - LED sequence commands          │   │
│  │  D4 (TX)         → Pi GPIO 15 (RX) - optional responses             │   │
│  │  D5              → WS2812B LED Strip Data                           │   │
│  │  D10 (CS)        ← SPLICED from MCP2515 #1 CS                       │   │
│  │  D11 (MOSI)      ← SPLICED from MCP2515 #1 SI                       │   │
│  │  D12 (MISO)      ← SPLICED from MCP2515 #1 SO                       │   │
│  │  D13 (SCK)       ← SPLICED from MCP2515 #1 SCK                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                           OBD-II Port                                 │   │
│  │   Pin 6/14: HS-CAN (500k) → MCP2515 #1 (spliced to Pi + Arduino)     │   │
│  │   Pin 3/11: MS-CAN (125k) → MCP2515 #2 (Pi only)                     │   │
│  │   Pin 5: Ground                                                       │   │
│  │   Pin 16: 12V Battery                                                 │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 📊 MCP2515 Module Summary (2 Total)

| Module | CAN Bus | Speed | OBD Pins | SPI Wiring |
|--------|---------|-------|----------|------------|
| MCP2515 #1 | HS-CAN | 500 kbps | 6/14 | **Spliced** to Pi GPIO AND Arduino SPI |
| MCP2515 #2 | MS-CAN | 125 kbps | 3/11 | Pi only (GPIO 7, 24) |

---

## ⚠️ Safety First

- **Disconnect vehicle battery** when making permanent connections
- **Use proper fusing** (2A recommended) on 12V power lines
- **Test with multimeter** before connecting to devices
- **Ensure proper grounding** to vehicle chassis
- **Keep wires away** from heat sources and moving parts
- **Use heat shrink tubing** on all solder joints

---

## 🔧 Part 1: Raspberry Pi 4B Wiring

### Pi GPIO Pinout (40-pin header)

```
                    ┌─────────────────────────────────┐
                    │         Raspberry Pi 4B         │
                    │          GPIO Header            │
                    │                                 │
   3.3V Power (1) ──┤●  ●├── (2) 5V Power
        SDA1 (3) ──┤●  ●├── (4) 5V Power
        SCL1 (5) ──┤●  ●├── (6) Ground ◄── MCP2515 GND
    GPIO 4   (7) ──┤●  ●├── (8) GPIO 14 (TXD) ◄── Arduino RX (D3)
      Ground (9) ──┤●  ●├── (10) GPIO 15 (RXD) ◄── Arduino TX (D4)
   GPIO 17  (11) ──┤●  ●├── (12) GPIO 18
   GPIO 27  (13) ──┤●  ●├── (14) Ground
   GPIO 22  (15) ──┤●  ●├── (16) GPIO 23
   3.3V Pwr (17) ──┤●  ●├── (18) GPIO 24 ◄── MCP2515 #2 INT (MS-CAN)
 GPIO 10/MOSI(19)──┤●  ●├── (20) Ground
 GPIO 9/MISO (21)──┤●  ●├── (22) GPIO 25 ◄── MCP2515 #1 INT (HS-CAN)
GPIO 11/SCLK (23)──┤●  ●├── (24) GPIO 8 (CE0) ◄── MCP2515 #1 CS (HS-CAN)
      Ground (25) ──┤●  ●├── (26) GPIO 7 (CE1) ◄── MCP2515 #2 CS (MS-CAN)
        ID_SD(27) ──┤●  ●├── (28) ID_SC
    GPIO 5  (29) ──┤●  ●├── (30) Ground
    GPIO 6  (31) ──┤●  ●├── (32) GPIO 12
   GPIO 13  (33) ──┤●  ●├── (34) Ground
   GPIO 19  (35) ──┤●  ●├── (36) GPIO 16
   GPIO 26  (37) ──┤●  ●├── (38) GPIO 20
      Ground (39) ──┤●  ●├── (40) GPIO 21
                    └─────────────────────────────────┘
```

### MCP2515 Module #1 (HS-CAN - 500kbps)

| MCP2515 Pin | Pi GPIO | Pi Pin # | Wire Color | Description |
|-------------|---------|----------|------------|-------------|
| VCC | 3.3V | 1 or 17 | Red | Power (3.3V ONLY!) |
| GND | GND | 6 | Black | Ground |
| CS | GPIO 8 (CE0) | 24 | Orange | SPI Chip Select |
| MOSI | GPIO 10 | 19 | Green | SPI Data In |
| MISO | GPIO 9 | 21 | Blue | SPI Data Out |
| SCK | GPIO 11 | 23 | Yellow | SPI Clock |
| **INT** | **GPIO 25** | **22** | **White** | **Interrupt (REQUIRED)** |
| CANH | OBD Pin 6 | - | Blue (CAN) | CAN High |
| CANL | OBD Pin 14 | - | White (CAN) | CAN Low |

### MCP2515 Module #2 (MS-CAN - 125kbps)

| MCP2515 Pin | Pi GPIO | Pi Pin # | Wire Color | Description |
|-------------|---------|----------|------------|-------------|
| VCC | 3.3V | 1 or 17 | Red | Power (3.3V ONLY!) |
| GND | GND | 9 | Black | Ground |
| CS | GPIO 7 (CE1) | 26 | Purple | SPI Chip Select |
| MOSI | GPIO 10 | 19 | Green | SPI Data In (shared) |
| MISO | GPIO 9 | 21 | Blue | SPI Data Out (shared) |
| SCK | GPIO 11 | 23 | Yellow | SPI Clock (shared) |
| **INT** | **GPIO 24** | **18** | **Gray** | **Interrupt (REQUIRED)** |
| CANH | OBD Pin 3 | - | Blue (CAN) | CAN High |
| CANL | OBD Pin 11 | - | White (CAN) | CAN Low |

⚠️ **IMPORTANT**: 
- Use **3.3V** for MCP2515 VCC (NOT 5V!) - Pi GPIO is 3.3V only
- Both modules SHARE the SPI bus (MOSI, MISO, SCK) but have separate CS and INT pins
- INT pins MUST be connected for the driver to work!

### Pi to Arduino Serial (LED Sequence Commands)

| Pi GPIO | Pi Pin # | Arduino Pin | Wire Color | Description |
|---------|----------|-------------|------------|-------------|
| GPIO 14 (TXD) | 8 | D3 (RX) | Green | Pi TX → Arduino RX |
| GPIO 15 (RXD) | 10 | D4 (TX) | Yellow | Arduino TX → Pi RX (optional) |
| GND | 6 | GND | Black | Common ground (REQUIRED) |

### Pi to ESP32-S3 (USB Serial)

| Pi Port | ESP32-S3 | Cable | Notes |
|---------|----------|-------|-------|
| USB-A | USB-C | USB cable | Data + Power |

The ESP32-S3 connects via USB-C cable to one of the Pi's USB-A ports. This provides:
- Serial communication (appears as `/dev/ttyACM0`)
- 5V power to the ESP32

---

## 🔧 Part 2: OBD-II Connections

### OBD-II Pinout

```
       OBD-II Female Connector (looking at pins)
   ┌─────────────────────┐
   │  8  7  6  5  4  3  2  1 │
   │    16 15 14 13 12 11 10 9│
   └─────────────────────┘
   
   Pin 3:  MS-CAN High (125k) → MCP2515 #2 CANH (Pi only)
   Pin 5:  Ground             → Common ground for all devices
   Pin 6:  HS-CAN High (500k) → MCP2515 #1 CANH (SPI spliced to Pi + Arduino)
   Pin 11: MS-CAN Low (125k)  → MCP2515 #2 CANL (Pi only)
   Pin 14: HS-CAN Low (500k)  → MCP2515 #1 CANL (SPI spliced to Pi + Arduino)
   Pin 16: 12V Battery        → Buck converters (Arduino, Pi power)
```

### MCP2515 #1 SPI Splice (Pi + Arduino Share ONE Module)

The **single** HS-CAN MCP2515 module connects to OBD-II pins 6/14. Its SPI output wires are **spliced** so both the Pi and Arduino can read CAN data simultaneously.

**Splice Diagram - MCP2515 #1 SPI Outputs:**
```
                    MCP2515 #1 (HS-CAN)
                    ┌─────────────────┐
  OBD Pin 6  ──────►│ CANH            │
  OBD Pin 14 ──────►│ CANL            │
                    │                 │
                    │ VCC ────────────┼──► Pi 3.3V (Pin 17)
                    │ GND ────────────┼──► Common Ground
                    │                 │
                    │ CS  ────────────┼──┬──► Pi GPIO 8 (CE0)
                    │                 │  └──► Arduino D10 (SPLICE)
                    │                 │
                    │ MOSI ───────────┼──┬──► Pi GPIO 10
                    │                 │  └──► Arduino D11 (SPLICE)
                    │                 │
                    │ MISO ───────────┼──┬──► Pi GPIO 9
                    │                 │  └──► Arduino D12 (SPLICE)
                    │                 │
                    │ SCK  ───────────┼──┬──► Pi GPIO 11
                    │                 │  └──► Arduino D13 (SPLICE)
                    │                 │
                    │ INT  ───────────┼──┬──► Pi GPIO 25
                    │                 │  └──► Arduino D2 (SPLICE)
                    └─────────────────┘
```

**How to Splice SPI Wires:**
1. Each SPI wire (CS, MOSI, MISO, SCK, INT) has **two destinations**
2. At each splice point, solder the MCP2515 wire to TWO wires (one to Pi, one to Arduino)
3. Cover each splice with heat shrink tubing
4. Total splices needed: **5** (CS, MOSI, MISO, SCK, INT)

---

## 🔧 Part 3: Power Distribution

### Power Requirements

| Device | Voltage | Current | Notes |
|--------|---------|---------|-------|
| Raspberry Pi 4B | 5V | 3A | USB-C PD recommended |
| ESP32-S3 | 5V | 0.5A | Powered via Pi USB |
| Arduino Nano | 5V | 0.5A | Via LM2596 buck converter |
| LED Strip (20 LEDs) | 5V | 1.2A max | Via LM2596 buck converter |
| MCP2515 #1 (HS-CAN) | 3.3V | 0.05A | From Pi 3.3V rail (shared with Arduino) |
| MCP2515 #2 (MS-CAN) | 3.3V | 0.05A | From Pi 3.3V rail |

### Power Diagram

```
OBD-II Pin 16 (12V)
        │
        ├───[2A Fuse]───► LM2596 #1 ───► Arduino + LEDs (5V 3A)
        │
        └───[3A Fuse]───► USB-C PD Adapter ───► Raspberry Pi 4B (5V 3A)
                                    │
                                    └───► ESP32-S3 (via Pi USB-A)

OBD-II Pin 5 (GND)
        │
        └───► Common Ground (all devices)
```

---

## 🔧 Part 4: Complete Connection Checklist

### Pi MCP2515 Connections
- [ ] MCP2515 #1 VCC → Pi 3.3V (Pin 1 or 17)
- [ ] MCP2515 #1 GND → Pi GND (Pin 6)
- [ ] MCP2515 #1 CS → Pi GPIO 8/CE0 (Pin 24)
- [ ] MCP2515 #1 MOSI → Pi GPIO 10 (Pin 19)
- [ ] MCP2515 #1 MISO → Pi GPIO 9 (Pin 21)
- [ ] MCP2515 #1 SCK → Pi GPIO 11 (Pin 23)
- [ ] MCP2515 #1 INT → Pi GPIO 25 (Pin 22)
- [ ] MCP2515 #1 CANH → OBD Pin 6
- [ ] MCP2515 #1 CANL → OBD Pin 14
- [ ] MCP2515 #2 VCC → Pi 3.3V (Pin 1 or 17)
- [ ] MCP2515 #2 GND → Pi GND (Pin 9)
- [ ] MCP2515 #2 CS → Pi GPIO 7/CE1 (Pin 26)
- [ ] MCP2515 #2 MOSI → Pi GPIO 10 (Pin 19, shared)
- [ ] MCP2515 #2 MISO → Pi GPIO 9 (Pin 21, shared)
- [ ] MCP2515 #2 SCK → Pi GPIO 11 (Pin 23, shared)
- [ ] MCP2515 #2 INT → Pi GPIO 24 (Pin 18)
- [ ] MCP2515 #2 CANH → OBD Pin 3
- [ ] MCP2515 #2 CANL → OBD Pin 11

### Pi Serial Connections
- [ ] Pi GPIO 14 (Pin 8) → Arduino D3 (RX)
- [ ] Pi GPIO 15 (Pin 10) → Arduino D4 (TX) - optional
- [ ] Pi GND (Pin 6) → Arduino GND

### Pi USB Connections
- [ ] Pi USB-A → ESP32-S3 USB-C (data cable)
- [ ] Pi Micro HDMI → Pioneer Head Unit

### Power Connections
- [ ] OBD Pin 16 (12V) → 2A Fuse → LM2596 IN+
- [ ] OBD Pin 5 (GND) → LM2596 IN- and common ground
- [ ] LM2596 OUT+ → Arduino 5V + LED strip 5V
- [ ] LM2596 OUT- → Arduino GND + LED strip GND

---

## 🧪 Testing Procedure

### 1. Test Pi CAN Bus (before wiring to car)

```bash
# Check if CAN interfaces exist (after boot with MCP2515 connected)
ip link show can0
ip link show can1

# If interfaces exist, bring them up
sudo ip link set can0 up type can bitrate 500000
sudo ip link set can1 up type can bitrate 125000

# Check dmesg for driver messages
dmesg | grep -i mcp
```

### 2. Test with Vehicle

```bash
# Monitor HS-CAN (ignition ON)
candump can0

# Monitor MS-CAN (ignition ON)
candump can1

# Should see messages like:
#   can0  201   [8]  00 00 00 00 00 00 00 00  (RPM)
#   can1  240   [8]  00 00 00 00 00 00 00 00  (SWC)
```

### 3. Test ESP32 Serial

```bash
# Check if ESP32 is connected
ls /dev/ttyACM*

# Test serial communication
python3 -c "import serial; s=serial.Serial('/dev/ttyACM0', 115200, timeout=1); s.write(b'PING\n'); print(s.readline())"
```

### 4. Test Arduino Serial

```bash
# Test Pi UART to Arduino
echo "SEQ:1" > /dev/serial0
```

---

## ❓ Troubleshooting

| Problem | Solution |
|---------|----------|
| CAN interfaces don't appear | Check /boot/config.txt dtoverlay settings, verify wiring |
| MCP2515 probe fails | Check 3.3V power, SPI connections, INT pin |
| No CAN traffic | Verify OBD-II pins 6/14 (HS) or 3/11 (MS), check bitrate |
| ESP32 not detected | Try different USB port, check cable is data-capable |
| Arduino serial not working | Check GPIO 14/15 wiring, verify common ground |

---

## 📁 Related Documentation

- [WIRING_GUIDE_ARDUINO.md](WIRING_GUIDE_ARDUINO.md) - Arduino Nano LED controller wiring
- [PARTS_LIST.md](PARTS_LIST.md) - Complete bill of materials
- [TPMS_BLUETOOTH.md](TPMS_BLUETOOTH.md) - BLE TPMS sensor protocol
- [../PI_DISPLAY_INTEGRATION.md](../PI_DISPLAY_INTEGRATION.md) - Full system architecture
