# 🚗 MX5-Telemetry System

A real-time telemetry and visual feedback system for the 2008 Mazda Miata NC (MX-5).

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Arduino](https://img.shields.io/badge/Arduino-Nano-00979D.svg)
![ESP32-S3](https://img.shields.io/badge/ESP32--S3-Display-blue.svg)
![Build System](https://img.shields.io/badge/Build-PlatformIO-orange.svg)

## 🎯 Architecture

| Module | Hardware | Purpose |
|--------|----------|---------|
| **Arduino** | Arduino Nano | CAN bus → LED strip (sub-1ms latency) |
| **Display** | ESP32-S3 1.85" Round LCD | Visual dashboard with touch (optional) |

## ✨ Features

### Arduino Module
- **⚡ Sub-millisecond latency** - Direct CAN bus to LED update
- **🎯 100Hz LED refresh** - Smooth, responsive RPM visualization
- **🔌 Simple wiring** - Minimal components
- **📊 Real-time CAN Bus** - 500 kbaud from OBD-II port

### ESP32-S3 Display Module (Optional)
- **📺 1.85" Round Touch Screen** - 360×360 IPS LCD
- **🎨 Visual RPM Gauge** - Color-coded arc display
- **🔊 Audio Alerts** - Shift light audio cues
- **📱 Touch Interface** - Menu navigation
- **🔄 Firmware Cloning** - Backup/restore between devices

## 📁 Project Structure

```
MX5-Telemetry/
├── arduino/                    # 🎯 Arduino Nano (CAN + LED)
│   ├── src/main.cpp
│   └── platformio.ini
│
├── display/                    # 📺 ESP32-S3 Round Display
│   ├── src/main.cpp
│   ├── scripts/                # Firmware backup/flash tools
│   ├── README.md
│   └── WORKFLOW.md             # Firmware cloning guide
│
├── lib/                        # 📦 Shared libraries
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
2. **Hardware**: Arduino Nano, MCP2515 CAN module, WS2812B LED strip

### Build & Upload Arduino

```powershell
# Build
pio run -d arduino

# Upload
pio run -d arduino --target upload

# Monitor serial output
pio device monitor -b 115200
```

### Build & Upload Display (ESP32-S3)

```powershell
# Build
pio run -d display

# Upload
pio run -d display --target upload
```

### Clone Firmware Between ESP32-S3 Devices

See [display/WORKFLOW.md](display/WORKFLOW.md) for detailed instructions on:
- Backing up firmware from a working device
- Flashing firmware to a new device
- Reverse engineering and redeveloping source code

## 🔌 Hardware Requirements

### Arduino Module

| Component | Model | Interface | Qty | Notes |
|-----------|-------|-----------|-----|-------|
| Microcontroller | Arduino Nano V3.0 | USB | 1 | ATmega328P, 16MHz |
| CAN Controller | MCP2515 + TJA1050 | SPI | 1 | 500 kbaud, 16MHz crystal |
| LED Strip | WS2812B | Digital | 1 | 16 LEDs recommended |
| Power Supply | LM2596 | - | 1 | 12V → 5V buck converter |

### Display Module (Optional)

| Component | Model | Notes |
|-----------|-------|-------|
| MCU | ESP32-S3 | Dual-core 240MHz |
| Display | 1.85" Round IPS | 360×360, GC9A01 |
| Touch | Capacitive | FT5x06 |
| Audio | 8Ω 2W Speaker | Onboard codec |

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [docs/hardware/WIRING_GUIDE_SINGLE_ARDUINO.md](docs/hardware/WIRING_GUIDE_SINGLE_ARDUINO.md) | Arduino wiring guide |
| [display/README.md](display/README.md) | ESP32-S3 display setup |
| [display/WORKFLOW.md](display/WORKFLOW.md) | Firmware cloning workflow |
| [docs/development/PLATFORMIO_GUIDE.md](docs/development/PLATFORMIO_GUIDE.md) | PlatformIO setup |

## 🔧 VS Code Tasks

Use `Ctrl+Shift+P` → "Tasks: Run Task" to access:

**Arduino:**
- Build Arduino
- Upload Arduino
- Upload and Monitor Arduino

**Display (ESP32-S3):**
- Build Display
- Upload Display
- Backup Firmware
- Flash Firmware
- Analyze Firmware

## 📦 Archived: Dual-Arduino Setup

The previous dual-arduino configuration (master + slave) has been archived to `archive/dual-arduino/`. This setup supported GPS logging and SD card data export but had higher latency (~70ms).

See [archive/dual-arduino/README.md](archive/dual-arduino/README.md) for restoration instructions if needed.

## 📄 License

MIT License - See [LICENSE](LICENSE) for details.
