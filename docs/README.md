# 📚 MX5-Telemetry Documentation

Complete documentation for the MX5-Telemetry system - a real-time automotive telemetry system for Mazda MX-5 (NC) vehicles.

---

## 🎯 System Architecture

The system uses a **three-device architecture** with the Pi as central hub:

| Device | Purpose | Location | Connection |
|--------|---------|----------|------------|
| **Raspberry Pi 4B** | CAN hub + settings cache + HDMI display | Hidden (console/trunk) | MCP2515 (HS + MS CAN) |
| **ESP32-S3 Round Display** | Gauge display + BLE TPMS + G-force IMU | **Stock oil gauge hole** | Serial from Pi |
| **Arduino Nano** | RPM LED strip controller | Gauge cluster bezel | Direct HS-CAN + Serial from Pi |

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

See [PI_DISPLAY_INTEGRATION.md](PI_DISPLAY_INTEGRATION.md) for complete architecture details.

---

## 🚀 Getting Started (New Users)

| Step | Document | Description |
|------|----------|-------------|
| 1️⃣ | [**PI_DISPLAY_INTEGRATION.md**](PI_DISPLAY_INTEGRATION.md) | ⭐ Understand the system architecture |
| 2️⃣ | [**hardware/PARTS_LIST.md**](hardware/PARTS_LIST.md) | Get the required hardware |
| 3️⃣ | [**hardware/WIRING_GUIDE.md**](hardware/WIRING_GUIDE.md) | Wire up all components |
| 4️⃣ | [**BUILD_AND_UPLOAD.md**](BUILD_AND_UPLOAD.md) | Build and flash firmware |
| 5️⃣ | [**DEPLOYMENT.md**](DEPLOYMENT.md) | Deploy to the car |

---

## 🔧 Hardware Documentation

| Document | Description |
|----------|-------------|
| [hardware/WIRING_GUIDE.md](hardware/WIRING_GUIDE.md) | Complete wiring for all devices |
| [hardware/WIRING_GUIDE_SINGLE_ARDUINO.md](hardware/WIRING_GUIDE_SINGLE_ARDUINO.md) | Arduino-only quick reference |
| [hardware/PARTS_LIST.md](hardware/PARTS_LIST.md) | Bill of materials |
| [hardware/TPMS_BLUETOOTH.md](hardware/TPMS_BLUETOOTH.md) | BLE TPMS sensor setup (ESP32) |

---

## ✨ Feature Documentation

### LED System (Arduino)
| Document | Description |
|----------|-------------|
| [features/LED_STATE_SYSTEM.md](features/LED_STATE_SYSTEM.md) | 7-state LED visual system |
| [features/LED_TIMING_AND_PERFORMANCE.md](features/LED_TIMING_AND_PERFORMANCE.md) | <1ms latency analysis |
| [features/LED_SIMULATOR_ARDUINO_CONNECTION.md](features/LED_SIMULATOR_ARDUINO_CONNECTION.md) | Python simulator → Arduino |
| [features/LED_SIMULATOR_TROUBLESHOOTING.md](features/LED_SIMULATOR_TROUBLESHOOTING.md) | Simulator debugging |

### Display System (ESP32 + Pi)
| Document | Description |
|----------|-------------|
| [DISPLAY_DEPLOYMENT.md](DISPLAY_DEPLOYMENT.md) | ESP32-S3 display deployment |
| [PI_DISPLAY_INTEGRATION.md](PI_DISPLAY_INTEGRATION.md) | Raspberry Pi + ESP32 integration |

---

## 💻 Development Documentation

| Document | Description |
|----------|-------------|
| [development/PLATFORMIO_GUIDE.md](development/PLATFORMIO_GUIDE.md) | PlatformIO setup and usage |
| [development/BUILD_ARCHITECTURE.md](development/BUILD_ARCHITECTURE.md) | Project structure |
| [development/DATA_ANALYSIS.md](development/DATA_ANALYSIS.md) | Telemetry data visualization |
| [development/REQUIREMENTS_COMPLIANCE.md](development/REQUIREMENTS_COMPLIANCE.md) | System requirements checklist |

---

## 📋 Project Management

| Document | Description |
|----------|-------------|
| [TODO_NEXT_SESSION.md](TODO_NEXT_SESSION.md) | Current tasks and progress |

---

## 📦 Archived Documentation

Old/superseded documentation kept for historical reference in `archive/dual-arduino/docs/`:

- **Dual Arduino Architecture** - Replaced by single Arduino + Pi
- **GPS & SD Card Logging** - Now handled by Pi
- **GoPro Power Control** - Legacy feature

---

## ⚡ Quick Commands

### Remote Deployment (Default - ESP32 & Pi)
```powershell
# Flash ESP32 via Pi (ESP32 is plugged into Pi USB)
git push
ssh pi@192.168.1.28 'cd ~/MX5-Telemetry && git pull && ~/.local/bin/pio run -d display --target upload'

# Update Pi application
ssh pi@192.168.1.28 'cd ~/MX5-Telemetry && git pull && sudo systemctl restart mx5-display'

# Or use VS Code tasks: "Pi: Flash ESP32 (Remote)" / "Pi: Git Pull & Restart UI"
```

### Local Upload (Arduino Only - Must Plug into PC)
```powershell
# Arduino must be connected to PC via USB
pio run -d arduino --target upload
```

### Simulators & Monitoring
```powershell
# Run LED Simulator
python tools/simulators/led_simulator/led_simulator_v2.1.py

# Monitor serial output (local device)
pio device monitor -b 115200
```

---

## 🗂️ Project Structure

```
MX5-Telemetry/
├── arduino/                    # Arduino Nano (CAN + LED)
│   └── src/main.cpp            # LED controller firmware
├── display/                    # ESP32-S3 Round Display
│   └── src/main.cpp            # Display firmware
├── pi/                         # Raspberry Pi 4B
│   └── ui/                     # Pi display application
├── lib/                        # Shared Arduino libraries
├── docs/                       # All documentation (you are here)
├── tools/simulators/           # LED & UI simulators
├── archive/                    # Archived (dual-arduino setup)
└── build-automation/           # Build scripts
```
