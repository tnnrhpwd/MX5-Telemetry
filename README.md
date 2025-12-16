# 🚗 MX5-Telemetry System

A real-time telemetry and visual feedback system for the 2008 Mazda Miata NC (MX-5).

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Raspberry Pi](https://img.shields.io/badge/Raspberry_Pi-4B-C51A4A.svg)
![Arduino](https://img.shields.io/badge/Arduino-Nano-00979D.svg)
![ESP32-S3](https://img.shields.io/badge/ESP32--S3-Display-blue.svg)
![Build System](https://img.shields.io/badge/Build-PlatformIO-orange.svg)

## 🎯 Architecture

| Module | Hardware | Purpose |
|--------|----------|---------|
| **Pi Hub** | Raspberry Pi 4B | CAN bus hub + HDMI output to Pioneer head unit |
| **Round Display** | ESP32-S3 1.85" Round LCD | Gauge display + BLE TPMS receiver |
| **LED Controller** | Arduino Nano | Direct CAN bus → LED strip (sub-1ms latency) |

### System Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  OBD-II Port    │     │  Raspberry Pi 4B │     │ Pioneer AVH     │
│  HS-CAN (500k)  │────►│  (CAN Hub)       │────►│ W4500NEX        │
│  MS-CAN (125k)  │     │  + Python UI     │     │ (HDMI Display)  │
└─────────────────┘     └────────┬─────────┘     └─────────────────┘
                                 │ Serial
        ┌────────────────────────┼────────────────────────┐
        │                        ▼                        │
        │                ┌──────────────────┐             │
        │                │ ESP32-S3 Round   │◄── BLE TPMS │
        │                │ Display (1.85")  │    Sensors  │
        │                └──────────────────┘             │
        │                                                 │
┌───────┴───────┐                                         │
│ Arduino Nano  │◄── MCP2515 (Direct HS-CAN)             │
│ + WS2812B LED │    <1ms latency for shift light        │
└───────────────┘                                         │
```

## ✨ Features

### Raspberry Pi (Hub)
- **📊 Dual CAN Bus** - Reads HS-CAN (500k) + MS-CAN (125k) via MCP2515
- **🖥️ HDMI Dashboard** - Full telemetry display on Pioneer head unit
- **🎮 Steering Wheel Controls** - Navigate UI using stock buttons
- **📡 Data Distribution** - Sends telemetry to ESP32-S3 via serial

### ESP32-S3 Round Display
- **📺 1.85" Round Touch Screen** - 360×360 IPS LCD
- **🎨 Visual RPM Gauge** - Color-coded arc display with shift indicator
- **📱 8 Screens** - Overview, RPM, TPMS, Engine, G-Force, Diagnostics, System, Settings
- **📡 BLE TPMS** - Receives tire pressure/temp from Bluetooth sensors
- **🎛️ QMI8658 IMU** - Built-in accelerometer for G-force display

### Arduino Nano (LED Controller)
- **⚡ Sub-millisecond latency** - Direct CAN bus to LED update
- **🎯 100Hz LED refresh** - Smooth, responsive RPM visualization
- **🔌 Independent operation** - Works even if Pi is offline
- **📊 Direct HS-CAN** - Own MCP2515 module for reliability

## 📁 Project Structure

```
MX5-Telemetry/
├── arduino/                    # 🎯 Arduino Nano (CAN + LED)
│   ├── src/main.cpp            # LED controller firmware
│   └── platformio.ini
│
├── display/                    # 📺 ESP32-S3 Round Display
│   ├── src/main.cpp            # Display firmware
│   ├── ui/                     # UI components
│   ├── scripts/                # Firmware backup/flash tools
│   ├── README.md
│   └── WORKFLOW.md             # Firmware cloning guide
│
├── pi/                         # 🖥️ Raspberry Pi 4B
│   ├── ui/src/                 # Python display application
│   │   ├── main.py             # Main UI application
│   │   ├── can_handler.py      # Dual CAN bus reader
│   │   ├── esp32_serial_handler.py  # ESP32 communication
│   │   └── screens/            # UI screens
│   └── start_display.sh        # Startup script
│
├── lib/                        # 📦 Shared Arduino libraries
│   ├── CANHandler/
│   ├── LEDController/
│   └── Config/
│
├── archive/                    # 📦 Archived (dual-arduino setup)
│   └── dual-arduino/
│
├── docs/                       # 📚 Documentation
├── build-automation/           # 🔧 Build scripts
└── tools/                      # 🛠️ Simulators & utilities
```

## 🚀 Quick Start

### Prerequisites

1. **Install PlatformIO** (VS Code extension recommended)
2. **Hardware**: See [docs/PI_DISPLAY_INTEGRATION.md](docs/PI_DISPLAY_INTEGRATION.md) for full parts list

### Build & Upload Arduino (LED Controller)

```powershell
# Build
pio run -d arduino

# Upload
pio run -d arduino --target upload

# Monitor serial output
pio device monitor -b 115200
```

### Build & Upload ESP32-S3 Display

```powershell
# Build
pio run -d display

# Upload
pio run -d display --target upload
```

### Run Pi Display Application

```bash
# On Raspberry Pi
cd pi/ui/src
python3 main.py --fullscreen
```

## 🔌 Hardware Requirements

### Raspberry Pi 4B (Hub)

| Component | Model | Interface | Notes |
|-----------|-------|-----------|-------|
| Raspberry Pi | 4B (2GB+) | - | Main hub |
| MCP2515 Module | x2 | SPI | HS-CAN + MS-CAN |
| 7" HDMI Display | 800x480 | HDMI | Or Pioneer head unit |

### ESP32-S3 Round Display

| Component | Model | Notes |
|-----------|-------|-------|
| Display | Waveshare ESP32-S3-Touch-LCD-1.85 | 360×360 IPS |
| TPMS Sensors | BLE Cap-mount | x4 |

### Arduino Nano (LED Controller)

| Component | Model | Interface | Notes |
|-----------|-------|-----------|-------|
| Microcontroller | Arduino Nano V3.0 | USB | ATmega328P, 16MHz |
| CAN Controller | MCP2515 + TJA1050 | SPI | 500 kbaud, 8MHz crystal |
| LED Strip | WS2812B | Digital | 20 LEDs recommended |
| Power Supply | LM2596 | - | 12V → 5V buck converter |

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [docs/PI_DISPLAY_INTEGRATION.md](docs/PI_DISPLAY_INTEGRATION.md) | **⭐ Main architecture guide** |
| [docs/hardware/WIRING_GUIDE_SINGLE_ARDUINO.md](docs/hardware/WIRING_GUIDE_SINGLE_ARDUINO.md) | Arduino wiring guide |
| [display/README.md](display/README.md) | ESP32-S3 display setup |
| [display/WORKFLOW.md](display/WORKFLOW.md) | Firmware cloning workflow |
| [docs/development/PLATFORMIO_GUIDE.md](docs/development/PLATFORMIO_GUIDE.md) | PlatformIO setup |

## 🔧 VS Code Tasks

Use `Ctrl+Shift+P` → "Tasks: Run Task" to access:

**Arduino:**
- PlatformIO: Build Arduino
- PlatformIO: Upload Arduino
- PlatformIO: Upload and Monitor Arduino

**Display (ESP32-S3):**
- PlatformIO: Build Display (ESP32-S3)
- PlatformIO: Upload Display (ESP32-S3)
- ESP32-S3: Backup Firmware
- ESP32-S3: Flash Firmware

**Simulators:**
- Start ESP32-S3 UI Simulator
- Start Raspberry Pi UI Simulator
- Start Combined UI Simulator

## 📦 Archived: Dual-Arduino Setup

The previous dual-arduino configuration (master + slave) has been archived to `archive/dual-arduino/`. This setup supported GPS logging and SD card data export but had higher latency (~70ms) and serial corruption issues.

The current architecture uses the Raspberry Pi as the data hub, with Arduino dedicated only to the LED strip for maximum responsiveness.

See [archive/dual-arduino/README.md](archive/dual-arduino/README.md) for historical reference.

## 📄 License

MIT License - See [LICENSE](LICENSE) for details.
