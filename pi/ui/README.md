# Raspberry Pi Display UI

## Overview
UI code for the Pioneer AVH-W4500NEX display (800x480 pixels via HDMI).

## Screens/Apps
1. **Overview** - Dashboard with key telemetry
2. **RPM/Speed** - Racing-focused gauges with lap timer
3. **TPMS** - Tire pressure and temperatures
4. **Engine** - Coolant, oil, fuel, voltage
5. **G-Force** - Lateral and longitudinal G
6. **Diagnostics** - DTC codes and warnings
7. **System** - Connection status and info
8. **Settings** - System configuration

## Navigation (Cruise Control Buttons Only)

**IMPORTANT:** Only cruise control buttons are readable on the MS-CAN bus.
Audio/volume buttons (VOL+, VOL-, MODE, SEEK, MUTE) are NOT available on the CAN bus.

### Available Buttons

| Button | Normal Screens | Settings (Normal) | Settings (Edit Mode) |
|--------|----------------|-------------------|---------------------|
| **RES+ (UP)** | Previous page | Move selection up | Increase value |
| **SET- (DOWN)** | Next page | Move selection down | Decrease value |
| **ON/OFF** | - | Enter edit mode | Confirm & exit edit |
| **CANCEL** | Go to Overview | Go to Overview | Cancel & exit edit |

### Settings Navigation
- **UP/DOWN** moves through settings items
- At top/bottom of list, wraps to previous/next page
- Press **ON/OFF** to edit a setting
- **UP/DOWN** adjusts the value
- Press **ON/OFF** to confirm or **CANCEL** to discard

### Navigation Lock
To prevent accidental changes while driving:
- **Hold ON/OFF for 3 seconds** to toggle lock on/off
- When locked: All button presses are ignored
- Visual indicator: Orange "LCK" icon on ESP32 Overview screen
- Keyboard shortcut: **L** key (for testing)

## Files
- `src/main.py` - Main application entry
- `src/screens/` - Screen implementations
- `src/swc_handler.py` - Steering wheel control handler (cruise buttons only)
- `src/can_handler.py` - CAN bus communication

## Serial Communication
The Pi receives telemetry data from CAN and communicates with ESP32 via serial.
Protocol: Text messages over UART at 115200 baud.
