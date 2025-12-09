# MX5 Telemetry - Display Deployment Guide

This guide covers deploying the telemetry UI to both the ESP32-S3 and Raspberry Pi displays.

## Overview

The MX5 Telemetry system uses two displays:
1. **ESP32-S3** (360×360 round display) - In-dash gauge cluster
2. **Raspberry Pi 4B** (800×480 LCD) - Center console information display

Both displays show the same 6 screens, synchronized:
1. **Overview** - Gear, speed, TPMS summary, alerts
2. **RPM/Speed** - Primary driving data with large gauge
3. **TPMS** - Tire pressure and temperature details
4. **Engine** - Coolant, oil, fuel, voltage gauges
5. **G-Force** - Lateral and longitudinal acceleration
6. **Settings** - Configuration options

---

## ESP32-S3 Deployment

### Hardware
- Waveshare ESP32-S3 Round Display (1.85" 360×360)
- GC9A01 LCD driver
- QMI8658 IMU for G-force data
- Touch screen for navigation

### Prerequisites
1. Install [PlatformIO](https://platformio.org/install/ide?install=vscode) VS Code extension
2. Connect ESP32-S3 via USB

### Deployment Steps

1. **Prepare the source files:**
   ```powershell
   cd display/src
   
   # Backup original main.cpp
   Rename-Item main.cpp main_lvgl.cpp
   
   # Use new UI renderer as main
   Rename-Item main_ui.cpp main.cpp
   ```

2. **Build the firmware:**
   ```powershell
   # From workspace root
   pio run -d display
   ```
   
   Or use VS Code task: `PlatformIO: Build Display (ESP32-S3)`

3. **Upload to device:**
   ```powershell
   pio run -d display --target upload
   ```
   
   Or use VS Code task: `PlatformIO: Upload Display (ESP32-S3)`

4. **Monitor output:**
   ```powershell
   pio device monitor -b 115200
   ```

### File Structure
```
display/
├── platformio.ini          # PlatformIO configuration
├── partitions_custom.csv   # Flash partition table
├── src/
│   ├── main.cpp           # Main entry point (use main_ui.cpp)
│   ├── main_ui.cpp        # New UI renderer main
│   ├── ui_config.h        # Colors, data structures
│   └── ui_renderer.h      # Screen rendering class
└── include/
    ├── display_config.h   # Hardware configuration
    └── telemetry_data.h   # Data structures
```

### Navigation
- **Touch zones:**
  - Top quarter: Previous screen
  - Bottom quarter: Next screen
  - Left quarter: Decrease value (settings)
  - Right quarter: Increase value (settings)
  - Center: Select/Enter

- **On Settings screen:**
  - Navigate items with top/bottom touch
  - Touch center to edit
  - Touch left/right to adjust values

---

## Raspberry Pi Deployment

### Hardware
- Raspberry Pi 4B (2GB+ recommended)
- 7" 800×480 HDMI touchscreen display
- USB connection to Arduino for telemetry data

### Prerequisites

1. **Install Python 3 and pygame:**
   ```bash
   sudo apt update
   sudo apt install python3 python3-pip
   pip3 install pygame
   ```

2. **Enable auto-start (optional):**
   Create `/etc/xdg/autostart/mx5-display.desktop`:
   ```desktop
   [Desktop Entry]
   Type=Application
   Name=MX5 Telemetry Display
   Exec=python3 /home/pi/MX5-Telemetry/pi/ui/src/main.py --fullscreen
   ```

### Deployment Steps

1. **Copy files to Pi:**
   ```bash
   # From development machine
   scp -r pi/ui/src/main.py pi@<PI_IP>:/home/pi/MX5-Telemetry/pi/ui/src/
   ```

   Or use git:
   ```bash
   # On Pi
   cd /home/pi/MX5-Telemetry
   git pull
   ```

2. **Run the application:**
   ```bash
   # Demo mode (default)
   python3 /home/pi/MX5-Telemetry/pi/ui/src/main.py
   
   # Fullscreen mode for production
   python3 /home/pi/MX5-Telemetry/pi/ui/src/main.py --fullscreen
   
   # Without demo animation
   python3 /home/pi/MX5-Telemetry/pi/ui/src/main.py --no-demo
   ```

3. **Test on development machine:**
   ```powershell
   # Windows (demo mode)
   python pi/ui/src/main.py
   ```

### File Structure
```
pi/
└── ui/
    └── src/
        └── main.py    # Complete display application
```

### Controls

**Keyboard:**
| Key | Action | SWC Button |
|-----|--------|------------|
| ↑ / W | Previous screen | RES+ |
| ↓ / S | Next screen | SET- |
| → / D | Increase value | VOL+ |
| ← / A | Decrease value | VOL- |
| Enter | Select/Edit | ON/OFF |
| Esc / B | Back | CANCEL |
| Space | Toggle sleep | - |
| Q | Quit | - |

**Touch (when implemented):**
- Same zones as ESP32-S3

---

## Screen Details

### 1. Overview
- Large gear indicator with RPM-based color glow
- Speed display (MPH/KMH switchable)
- RPM progress bar
- Key values: Coolant, Oil, Fuel, Voltage
- TPMS mini-diagram with car outline
- Alerts panel (shows issues or "All OK" checklist)

### 2. RPM/Speed
- Large circular RPM gauge with shift light
- Gear indicator in center
- Speed card with large numerals
- Throttle and brake percentage bars
- Current lap and best lap times

### 3. TPMS
- Full-screen tire diagram
- Pressure and temperature for each tire
- Color-coded: Green (OK), Yellow (High), Red (Low)

### 4. Engine
- Coolant temperature gauge
- Oil temperature gauge
- Oil pressure gauge
- Fuel level bar
- Voltage gauge
- Intake temperature gauge

### 5. G-Force
- Circular g-ball indicator
- Lateral G card (left/right)
- Longitudinal G card (accel/decel)
- Combined G magnitude

### 6. Settings
- Brightness (10-100%)
- Shift RPM warning point
- Redline RPM
- Units (MPH/KMH)
- Low tire PSI threshold
- Coolant warning temperature
- Back button

---

## Customization

### Colors
All colors are defined in:
- ESP32: `display/src/ui_config.h` (RGB565 format)
- Pi: `pi/ui/src/main.py` (RGB tuples)

### Alert Thresholds
Modify in the Settings structure:
- `tire_low_psi` / `tire_high_psi`
- `coolant_warn_f` / `oil_warn_f`
- Default voltage warning: < 12.0V

### Data Integration
Currently runs in demo mode. To integrate real telemetry:

**ESP32:**
1. Implement serial/CAN handler to receive data
2. Update `TelemetryData` struct in main loop

**Pi:**
1. Add serial connection to Arduino
2. Parse incoming telemetry packets
3. Update `self.telemetry` in main loop

---

## Troubleshooting

### ESP32 Issues

**Build fails with LovyanGFX errors:**
- Ensure library is installed: `pio lib install "lovyan03/LovyanGFX"`
- Check `lib_deps` in `platformio.ini`

**Display shows nothing:**
- Check SPI pin configuration in `main_ui.cpp`
- Verify display power connection
- Try adjusting brightness in setup()

**Touch not working:**
- Verify I2C address (0x38 for FT6X36)
- Check SCL/SDA pin configuration

### Pi Issues

**pygame not found:**
```bash
pip3 install pygame
```

**Display resolution wrong:**
- Check Pi display configuration in `/boot/config.txt`
- Set `hdmi_cvt=800 480 60 6`

**Fullscreen mode issues:**
- Try: `export SDL_VIDEODRIVER=x11`
- Or: `export SDL_VIDEODRIVER=directfb`

---

## Development

### Running the Simulator
The original simulator provides reference for both displays:
```powershell
python tools/simulators/ui_simulator/combined_simulator.py
```

### Testing Changes
1. Update simulator first
2. Port changes to ESP32 (`ui_renderer.h`)
3. Port changes to Pi (`main.py`)
4. Test both in demo mode before deploying
