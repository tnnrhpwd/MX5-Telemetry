# 🚗 MX5-Telemetry System

A real-time telemetry and visual feedback system for the 2008 Mazda Miata NC (MX-5).

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Raspberry Pi](https://img.shields.io/badge/Raspberry_Pi-4B-C51A4A.svg)
![Arduino](https://img.shields.io/badge/Arduino-Nano-00979D.svg)
![ESP32-S3](https://img.shields.io/badge/ESP32--S3-Display-blue.svg)
![Build System](https://img.shields.io/badge/Build-PlatformIO-orange.svg)

## 🔗 Quick Access

**Pi Network IPs:**
- Home WiFi: `192.168.1.23` or `mx5pi.local`
- Phone Hotspot: `10.62.26.67`

**Web Interface:** `http://<pi-ip>:5000`

## 🎯 Architecture

| Module | Hardware | Purpose | Location |
|--------|----------|---------|----------|
| **Pi Hub** | Raspberry Pi 4B | CAN bus hub, settings cache, HDMI to head unit | Hidden (center console/trunk) |
| **Round Display** | ESP32-S3 1.85" Round LCD | Gauge display, BLE TPMS + G-force sensor | Replaces stock oil gauge |
| **LED Controller** | Arduino Nano | Direct CAN → LED strip for RPM | Gauge cluster bezel |

### System Overview

```
                           ┌──────────────────────────────────────────┐
                           │            RASPBERRY PI 4B               │
                           │         (Central Hub + Settings Cache)   │
                           │                                          │
┌────────────────┐         │  ┌──────────────┐    ┌──────────────┐   │
│   OBD-II Port  │         │  │   MCP2515    │    │   MCP2515    │   │
│                │         │  │   HS-CAN     │    │   MS-CAN     │   │
│  HS-CAN ───────┼────┬───►│  │   (500k)     │    │   (125k)     │   │
│  (Pin 6/14)    │    │    │  └──────────────┘    └──────────────┘   │
│                │    │    │         │                   │           │
│  MS-CAN ───────┼────┼───►│         └───────┬───────────┘           │
│  (Pin 3/11)    │    │    │                 ▼                       │
│                │    │    │  • Reads engine data (RPM, speed, etc)  │
│  12V (Pin 16)  │    │    │  • Reads steering wheel buttons         │
│  GND (Pin 5)   │    │    │  • Caches & distributes settings        │
└────────────────┘    │    │  • Sends telemetry to ESP32             │
                      │    │  • Sends LED sequence to Arduino        │
                      │    │                                          │
                      │    │    HDMI ─────► Pioneer AVH-W4500NEX     │
                      │    │    Serial ───► ESP32-S3 (telemetry)     │
                      │    │    Serial ───► Arduino (LED settings)   │
                      │    └──────────────────────────────────────────┘
                      │
                      │    ┌──────────────────────────────────────────┐
                      │    │          ESP32-S3 ROUND DISPLAY          │
                      │    │     (Mounted in stock oil gauge hole)    │
                      │    │                                          │
                      │    │  • Receives telemetry from Pi (Serial)   │
                      │    │  • Receives steering wheel buttons       │
                      │    │  • BLE TPMS receiver → sends to Pi       │
                      │    │  • QMI8658 IMU G-force → sends to Pi     │
                      │    │  • Displays gauges, TPMS, G-force, etc   │
                      │    └──────────────────────────────────────────┘
                      │
                      │    ┌──────────────────────────────────────────┐
                      │    │            ARDUINO NANO                  │
                      ├───►│        (Direct HS-CAN for RPM)           │
                      │    │      (LED strip around gauge cluster)    │
                      │    │                                          │
                      │    │  • MCP2515 reads RPM directly (<1ms)     │
 BLE TPMS Sensors ────┼──► │  • Receives LED sequence from Pi         │
   (4x cap-mount)     │    │  • Drives WS2812B LED strip              │
                      │    │  • Independent operation if Pi offline   │
                      │    └──────────────────────────────────────────┘
                      │
                      └─── Note: HS-CAN is SHARED between Pi and Arduino
                           (via OBD-II Y-splitter or parallel tap)
```

## ✨ Features

### Raspberry Pi (Central Hub)
- **📊 Dual CAN Bus** - Reads HS-CAN (500k) + MS-CAN (125k) via MCP2515 modules
- **🖥️ HDMI Dashboard** - Full telemetry display on Pioneer head unit
- **🎮 Steering Wheel Controls** - Navigate UI using stock buttons (via MS-CAN)
- **📡 Data Distribution** - Sends telemetry to ESP32-S3 via serial
- **💾 Settings Cache** - Stores all settings and syncs to devices on startup
- **🔄 LED Control** - Sends selected LED sequence/pattern to Arduino via serial

### ESP32-S3 Round Display (Oil Gauge Replacement)
- **📺 1.85" Round IPS LCD** - 360×360 pixel display
- **🎨 Visual Gauges** - RPM, speed, temps with color-coded arc display
- **📱 8 Synchronized Screens** - Overview, RPM, TPMS, Engine, G-Force, Diagnostics, System, Settings
- **📡 BLE TPMS Receiver** - Receives tire pressure/temp from Bluetooth sensors → forward to Pi
- **🎛️ QMI8658 IMU** - G-force & tilt display (see [G-Force Display Behavior](display/README.md#g-force-display-behavior))
- **🎮 SWC Navigation** - Receives steering wheel button events from Pi

### Arduino Nano (LED Controller)
- **⚡ Sub-millisecond latency** - Direct CAN bus to LED update
- **🎯 100Hz LED refresh** - Smooth, responsive RPM visualization
- **✨ Smooth LED Transitions** - Fractional brightness + color gradients for buttery-smooth display
- **🔌 Independent operation** - Works even if Pi is offline
- **📊 Direct HS-CAN** - Own MCP2515 module (shared bus with Pi)
- **🎨 Configurable Patterns** - Receives LED sequence selection from Pi via serial

## 📁 Project Structure

```
MX5-Telemetry/
├── arduino/                    # 🎯 Arduino Nano (RPM LED Controller)
│   ├── src/main.cpp            # LED controller firmware
│   └── platformio.ini          # Direct CAN + LED strip + serial for settings
│
├── display/                    # 📺 ESP32-S3 Round Display (Oil Gauge)
│   ├── src/main.cpp            # Display firmware
│   ├── ui/                     # UI components & screens
│   ├── scripts/                # Firmware backup/flash tools
│   ├── README.md
│   └── WORKFLOW.md             # Firmware cloning guide
│
├── pi/                         # 🖥️ Raspberry Pi 4B (Central Hub)
│   ├── ui/src/                 # Python display application
│   │   ├── main.py             # Main UI application
│   │   ├── can_handler.py      # Dual CAN bus reader
│   │   ├── esp32_serial_handler.py  # ESP32 communication
│   │   ├── arduino_serial_handler.py # Arduino LED settings
│   │   ├── settings_manager.py # Settings cache + sync
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

### 🔌 Deployment Overview

| Device | Upload Method | Connection |
|--------|---------------|------------|
| **Arduino Nano** | **Local** (plug into PC) | USB to PC |
| **ESP32-S3** | **Remote** via Pi SSH | USB to Pi (192.168.1.23) |
| **Pi Application** | **Remote** via SSH | Git pull + systemctl |

### Arduino Nano (Requires Local Connection)

The Arduino Nano must be plugged directly into your PC:

```powershell
# Build and upload (Arduino plugged into PC)
pio run -d arduino --target upload

# Monitor serial output
pio device monitor -b 115200
```

### ESP32-S3 Display (Remote Upload via Pi)

The ESP32-S3 is permanently connected to the Pi's USB (192.168.1.23). Upload remotely using VS Code task:

**`Ctrl+Shift+P` → "Tasks: Run Task" → "Pi: Flash ESP32 (Remote)"**

This pulls the latest code on the Pi and flashes the ESP32 in one step (~68 seconds).

<details>
<summary>Task runs this command:</summary>

```bash
ssh pi@192.168.1.23 'cd ~/MX5-Telemetry && git pull && ~/.local/bin/pio run -d display --target upload'
```
</details>

### Pi Display Application (Remote Update)

```powershell
# Push code to GitHub, then update Pi
git push
ssh pi@192.168.1.23 'cd ~/MX5-Telemetry && git pull && sudo systemctl restart mx5-display'
```

Or use VS Code task: **Pi: Git Pull & Restart UI**

## 🔌 Hardware Requirements

### Raspberry Pi 4B (Central Hub)

| Component | Model | Interface | Notes |
|-----------|-------|-----------|-------|
| Raspberry Pi | 4B (2GB+) | - | Central hub, settings cache |
| MCP2515 Module | x2 | SPI | HS-CAN (GPIO8) + MS-CAN (GPIO7) |
| HDMI Cable | Micro HDMI | HDMI | To Pioneer head unit |

### ESP32-S3 Round Display (Replaces Oil Gauge)

| Component | Model | Notes |
|-----------|-------|-------|
| Display | Waveshare ESP32-S3-Touch-LCD-1.85 | 360×360 IPS, mounts in oil gauge hole |
| TPMS Sensors | BLE Cap-mount | x4, data forwarded to Pi |
| IMU | QMI8658 (built-in) | G-force data forwarded to Pi |

### Arduino Nano (LED Controller)

| Component | Model | Interface | Notes |
|-----------|-------|-----------|-------|
| Microcontroller | Arduino Nano V3.0 | USB | ATmega328P, 16MHz |
| CAN Controller | MCP2515 + TJA1050 | SPI | Shares HS-CAN bus with Pi |
| LED Strip | WS2812B | Digital | 20 LEDs, mounted around gauge cluster |
| Power Supply | LM2596 | - | 12V → 5V buck converter |

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [docs/PI_DISPLAY_INTEGRATION.md](docs/PI_DISPLAY_INTEGRATION.md) | **⭐ Main architecture guide** |
| [docs/hardware/WIRING_GUIDE.md](docs/hardware/WIRING_GUIDE.md) | Complete wiring guide |
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
