# 🔌 MX5-Telemetry Wiring Guide

Complete wiring reference for the MX5-Telemetry system.

---

## 🏎️ System Overview

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

┌────────────────────────────────────────────────────────────────────────────┐
│                           RASPBERRY PI 4B (Central Hub)                     │
│  GPIO 8/7 (CS) ─────► MCP2515 (HS/MS)   GPIO 14/15 ──► Arduino Serial      │
│  GPIO 10/9/11 (SPI) ─► Shared Bus       USB-A ───────► ESP32-S3 Display    │
│  GPIO 25/24 (INT) ──► Interrupts        (Power from breadboard, not Pi)    │
└──────────────┬─────────────────┬────────────────────────────────────────────┘
               │                 │
    ┌──────────▼──────┐  ┌───────▼───────┐
    │ MCP2515 (HS Pi) │  │ MCP2515 (MS Pi)│
    │  500k, Pin 6/14 │  │  125k, Pin 3/11│
    │  VCC ◄─ Bread 5V│  │  VCC ◄─ Bread 5V│
    └────────┬────────┘  └────────────────┘
             │ (parallel CAN)
    ┌────────▼─────────┐
    │ MCP2515 (HS Ard) │       ┌─────────────────────────────┐
    │  500k, Pin 6/14  │       │        ARDUINO NANO         │
    │  VCC ◄─ Bread 5V │◄─────►│  D10-13 (SPI), D2 (INT)     │
    └──────────────────┘       │  D3/D4 ◄──► Pi Serial       │
                               │  D5 ──────► LED Strip       │
                               │  5V ◄────── Breadboard      │
                               └─────────────────────────────┘
```

### Why 3 MCP2515 Modules?

SPI requires single-master operation. Each controller (Pi, Arduino) needs its own MCP2515 module with independent SPI. The CAN bus side (CANH/CANL) connects in parallel—CAN natively supports multiple listeners.

---

## ⚠️ Safety

- Disconnect vehicle battery for permanent connections
- Use 2A fuse on 12V lines
- Test voltages with multimeter before connecting devices
- Use heat shrink on all solder joints

---

## 📦 Components

| Component | Qty | Notes |
|-----------|-----|-------|
| Raspberry Pi 4B | 1 | 2GB+ RAM |
| ESP32-S3 Round Display | 1 | Waveshare 1.85" LCD |
| Arduino Nano V3.0 | 1 | ATmega328P |
| MCP2515 CAN Module | 3 | 8MHz crystal |
| WS2812B LED Strip | 1 | 20 LEDs |
| LM2596 Buck Converter | 1 | 12V→5V, 3A |
| **Breadboard** | 1 | Central power distribution |
| OBD-II Extension Cable | 1 | For easy access |
| 2A Blade Fuse | 1 | 12V protection |

---

## 🔌 OBD-II Pinout

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

## 🥧 Raspberry Pi Wiring

> **Note**: This guide uses **BCM GPIO numbering** (Linux/Python standard), not WiringPi numbers.

![Raspberry Pi 4B Pinout Reference](pi4b_pinout.jpg)

### GPIO Reference (Physical Pin Layout)

**Legend**: ■ = Wired, ○ = Unused

> **Power Note**: Pi does NOT power MCP2515 modules. All power comes from breadboard.

```
          3.3V  (1) ○                  ○ (2)  5V
     BCM2/SDA1  (3) ○                  ○ (4)  5V
     BCM3/SCL1  (5) ○                  ■ (6)  GND ───► Breadboard GND
          BCM4  (7) ○                  ■ (8)  BCM14/TXD ──► Arduino D3 (RX)
           GND  (9) ○                  ■ (10) BCM15/RXD ◄── Arduino D4 (TX)
         BCM17 (11) ○                  ○ (12) BCM18
         BCM27 (13) ○                  ○ (14) GND
         BCM22 (15) ○                  ○ (16) BCM23
          3.3V (17) ○                  ■ (18) BCM24 ◄── MCP2515 (MS-CAN Pi) INT
    BCM10/MOSI (19) ■──► MCP MOSI      ○ (20) GND
     BCM9/MISO (21) ■◄── MCP MISO      ■ (22) BCM25 ◄── MCP2515 (HS-CAN Pi) INT
    BCM11/SCLK (23) ■──► MCP SCK       ■ (24) BCM8/CE0 ◄─ MCP2515 (HS-CAN Pi) CS
           GND (25) ○                  ■ (26) BCM7/CE1 ◄─ MCP2515 (MS-CAN Pi) CS
         BCM0  (27) ○                  ○ (28) BCM1
         BCM5  (29) ○                  ○ (30) GND
         BCM6  (31) ○                  ○ (32) BCM12
        BCM13  (33) ○                  ○ (34) GND
        BCM19  (35) ○                  ○ (36) BCM16
        BCM26  (37) ○                  ○ (38) BCM20
           GND (39) ○                  ○ (40) BCM21
```

### Wired Pins Summary

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

### MCP2515 → Pi Connections

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

> **Note**: MCP2515 modules with onboard voltage regulators accept 5V VCC while outputting 3.3V logic levels compatible with Pi GPIO.

### Other Pi Connections

| Connection | Pi | Device | Purpose |
|------------|-----|--------|---------|
| USB-A #1 | Any USB port | ESP32-S3 USB-C | Display serial + power |
| USB-A #2 | Any USB port | Arduino Nano USB | Flashing + serial (primary) |
| Serial TX | GPIO 14 (Pin 8) | Arduino D3 (RX) | Backup serial |
| Serial RX | GPIO 15 (Pin 10) | Arduino D4 (TX) | Backup serial |
| Serial GND | Pin 6 | Breadboard GND | Common ground |
| HDMI | Micro HDMI | Head unit | Display output |

> **Serial Options**: USB serial (`/dev/ttyUSB0`) is recommended as primary—it has error checking and enables remote flashing. GPIO serial (`/dev/serial0`) is backup.

---

## 🔵 Arduino Nano Wiring

> **Power Note**: Arduino does NOT power MCP2515. All power comes from breadboard.

### MCP2515 (HS-CAN Arduino) Connections

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

### Other Arduino Connections

| Connection | Arduino Pin | Notes |
|------------|-------------|-------|
| USB | Mini-B / Micro-B | → Pi USB-A (flashing + primary serial) |
| LED Data | D5 | WS2812B DIN |
| Pi Serial RX | D3 | ← Pi GPIO 14 (backup serial) |
| Pi Serial TX | D4 | → Pi GPIO 15 (backup serial) |
| Brightness Pot | A6 | Optional |

> **Remote Flashing**: With USB connected to Pi, flash Arduino via SSH:
> ```bash
> ssh pi@192.168.1.23 'cd ~/MX5-Telemetry && pio run -d arduino --target upload'
> ```

### WS2812B LED Strip

| LED Pin | Connection |
|---------|------------|
| 5V | Breadboard 5V rail |
| GND | Breadboard GND rail |
| DIN | Arduino D5 |

---

## 📺 ESP32-S3 Display

Single USB-C cable to Pi USB-A provides both power and serial (`/dev/ttyACM0`).

**Built-in features used**: 1.85" LCD, touch, IMU (G-force), BLE (TPMS)

---

## ⚡ Power Distribution (Centralized Breadboard)

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

### LM2596 Setup
1. Connect 12V input, measure output with multimeter
2. Adjust to exactly **5.0V** before connecting anything
3. Connect output to breadboard 5V/GND rails
4. All devices draw power from breadboard rails

---

## ✅ Quick Checklist

### Breadboard Power
- [ ] Buck converter adjusted to 5.0V
- [ ] 2A fuse on 12V line
- [ ] Breadboard 5V rail connected to LM2596 OUT+
- [ ] Breadboard GND rail connected to OBD Pin 5
- [ ] All devices powered from breadboard (not from Pi/Arduino)

### Pi MCP2515s
- [ ] VCC from breadboard 5V (not Pi 3.3V)
- [ ] GND from breadboard
- [ ] INT pins connected (GPIO 25, 24)
- [ ] SPI shared, CS separate

### Arduino
- [ ] Arduino 5V from breadboard
- [ ] MCP2515 (HS-CAN Ard) VCC from breadboard
- [ ] MCP2515 INT → D2 (critical!)
- [ ] LED strip from breadboard 5V

### CAN Bus
- [ ] HS-CAN (pins 6/14) spliced to both HS-CAN modules
- [ ] MS-CAN (pins 3/11) to MS-CAN Pi module only

---

## 🧪 Testing

### Pi CAN Bus
```bash
ip link show can0 can1
sudo ip link set can0 up type can bitrate 500000
sudo ip link set can1 up type can bitrate 125000
candump can0  # Should see traffic with ignition ON
```

### ESP32 Serial
```bash
ls /dev/ttyACM*  # Should show device
```

### Arduino Serial
```bash
echo "SEQ:1" > /dev/serial0
```

---

## ❓ Troubleshooting

| Problem | Check |
|---------|-------|
| CAN interfaces missing | /boot/config.txt dtoverlay, wiring |
| MCP2515 probe fails | Breadboard 5V, SPI wires, INT pin |
| No CAN traffic | OBD pins, bitrate (500k HS, 125k MS), ignition ON |
| LEDs not working | Breadboard 5V, D5 connection, INT→D2 |
| ESP32 not detected | Different USB port, data-capable cable |
| Arduino serial fails | GPIO 14/15 wiring, common ground on breadboard |
| Nothing powers on | Check LM2596 output is 5.0V, check fuse |

---

## 📁 Related Docs

- [PARTS_LIST.md](PARTS_LIST.md) - Full bill of materials
- [TPMS_BLUETOOTH.md](TPMS_BLUETOOTH.md) - BLE TPMS setup
- [../PI_DISPLAY_INTEGRATION.md](../PI_DISPLAY_INTEGRATION.md) - System architecture
