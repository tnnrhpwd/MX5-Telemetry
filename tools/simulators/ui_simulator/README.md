# MX5 Telemetry UI Simulators

This folder contains tools to simulate and debug the ESP32-S3 round display and Raspberry Pi dashboard UIs.

## Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run both simulators:
```bash
python launch_simulators.py
```

Or run individually:
```bash
python launch_simulators.py --esp32    # ESP32-S3 only
python launch_simulators.py --pi       # Raspberry Pi only
```

## Simulator Locations

| Simulator | Path | Display Size |
|-----------|------|--------------|
| ESP32-S3 | `display/ui/simulator/esp32_ui_simulator.py` | 360x360 (round) |
| Raspberry Pi | `pi/ui/simulator/pi_ui_simulator.py` | 800x480 |

## Keyboard Controls (SWC Button Mapping)

Both simulators use the same keyboard mappings to simulate steering wheel buttons:

| Key | SWC Button | Action |
|-----|------------|--------|
| M / Tab | MODE | Switch screens (ESP32) / Switch device focus (Pi) |
| Enter | ON/OFF | Select / Confirm |
| Esc / B | CANCEL | Back / Exit |
| ↑ / W | RES+ | Navigate Up |
| ↓ / S | SET- | Navigate Down |
| → / D | SEEK▲ | Navigate Right / Next |
| ← / A | SEEK▼ | Navigate Left / Previous |
| + / = | VOL+ | Increase value |
| - | VOL- | Decrease value |
| Space | MUTE | Toggle sleep mode |
| D / T | - | Toggle demo mode (auto-animate values) |

## Features

### ESP32-S3 Simulator
- 360x360 circular display
- RPM gauge with color zones
- Speedometer with gear indicator
- TPMS 4-corner tire pressure view
- Engine temperature display
- G-force meter
- Settings menu

### Raspberry Pi Simulator
- 800x480 dashboard display
- Home screen with app launcher
- Maps placeholder
- Music player interface
- Full telemetry dashboard
- Detailed TPMS display
- Settings menu
- Device focus indicator (Pi/ESP32)

## Demo Mode

Both simulators include a demo mode that automatically animates telemetry values:
- RPM oscillates through all zones
- Gear changes based on RPM
- Speed correlates with RPM/gear
- G-forces vary randomly

Toggle demo mode with **D** (ESP32) or **T** (Pi) keys.

## Architecture Notes

In the real system:
- **Pi** is the CAN hub, reading HS-CAN and MS-CAN
- **Pi** sends telemetry data to ESP32-S3 via serial
- **ESP32-S3** handles BLE TPMS and sends data back to Pi
- **MODE button** switches which device responds to buttons
- Both displays can show data simultaneously
