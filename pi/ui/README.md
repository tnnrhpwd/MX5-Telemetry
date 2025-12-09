# Raspberry Pi Display UI

## Overview
UI code for the Pioneer AVH-W4500NEX display (800x480 pixels via HDMI).

## Screens/Apps
1. **Home** - App launcher grid
2. **Maps** - Navigation display (placeholder)
3. **Music** - Media player interface
4. **Telemetry** - Full dashboard with all sensor data
5. **TPMS** - Detailed tire pressure display
6. **Settings** - System configuration

## Navigation
- **MODE** - Switch focus between Pi and ESP32
- **MUTE** - Sleep/dim display
- **SEEK▲/▼** - Navigate left/right
- **RES+/SET-** - Navigate up/down
- **VOL+/VOL-** - Adjust values
- **ON/OFF** - Select/confirm
- **CANCEL** - Back/exit

## Simulation
Run the Python simulator for desktop testing:
```bash
cd simulator
python pi_ui_simulator.py
```

## Files
- `src/main_ui.py` - Main application entry
- `src/screens/` - Screen implementations
- `src/swc_handler.py` - Steering wheel control handler
- `simulator/` - Desktop simulator with SWC button panel

## Serial Communication
The Pi receives telemetry data from serial and SWC button events.
Protocol: JSON messages over UART at 115200 baud.
