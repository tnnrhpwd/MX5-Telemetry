# ESP32-S3 Round Display UI

## Overview
UI code for the 1.85" round ESP32-S3 display (360x360 pixels).

## Screens
1. **RPM Gauge** - Large tachometer with gear indicator
2. **Speedometer** - Speed display with gear
3. **TPMS View** - 4-corner tire pressure display
4. **Engine Temps** - Coolant, oil, and ambient temperatures
5. **G-Force** - Lateral/longitudinal G-force meter
6. **Settings** - Configuration menu

## Navigation
- **MODE** - Cycle through screens
- **MUTE** - Sleep/wake display
- **RES+/SET-** - Navigate up/down in menus
- **VOL+/VOL-** - Adjust values
- **ON/OFF** - Select/confirm
- **CANCEL** - Back/exit

## Simulation
Run the Python simulator for desktop testing:
```bash
cd simulator
python esp32_ui_simulator.py
```

## Files
- `src/ui_screens.h` - Screen definitions
- `src/ui_manager.cpp` - UI state machine
- `src/swc_handler.cpp` - Steering wheel control handler
- `simulator/` - Python/Pygame desktop simulator
