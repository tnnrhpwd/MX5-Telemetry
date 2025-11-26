# MX5-Telemetry Tools

This folder contains development tools for the MX5-Telemetry project.

## 🆕 Auto-Sync Feature (Latest Update)

**The simulator now automatically reads LED configuration from Arduino code!**

- ✅ Edit only `lib/Config/LEDStates.h` - Python syncs automatically
- ✅ No manual copying of constants
- ✅ Impossible to get out of sync
- ✅ Speed-aware State 1: Only shows stall warning when vehicle is moving

**See** `parse_arduino_led_config.py` for the parser that makes this possible.

**Documentation**: `docs/LED_AUTO_SYNC.md` for full details.

## LED Simulator v2.1

Interactive GUI simulator for testing LED strip logic before uploading to Arduino.

### New in v2.1 🎉

- **🔊 Engine Sound Synthesis**: Real-time audio that changes pitch with RPM (optional, requires pyaudio)
- **⚠️ Engine Stalling**: Realistic stall when RPM drops too low without clutch
- **🌊 Realistic Speed Decay**: Natural deceleration from drag and rolling resistance
- **📊 Enhanced Physics**: Accurate stall detection and warnings

### Features from v2.0

- **🚗 Car Configuration Files**: Load custom JSON files with vehicle specs
- **🔑 Engine Start/Stop**: Toggle engine on/off with button control
- **📂 Multiple Car Support**: Switch between different vehicle configurations
- **📊 Accurate Physics**: Each car uses its own gear ratios, RPM limits, and performance data

### Features

- **Real-time LED visualization**: See exactly how your LED strip will look
- **Realistic physics**: Simulates actual transmission with accurate gear ratios
- **Interactive controls**: Keyboard-based gas, brake, clutch, and shifting
- **Dual gauges**: RPM and speed displayed as analog gauges
- **Live gear indicator**: Shows current gear selection (N when engine off)
- **30-LED strip simulation**: Matches your WS2812B strip configuration
- **Custom car profiles**: Load any vehicle configuration from JSON files

### Quick Start

#### First Time Setup

Create a Python virtual environment in the project root:

```powershell
# From MX5-Telemetry root directory
py -m venv venv
```

This creates an isolated Python environment (already excluded in `.gitignore`).

#### Windows

**Option 1: Using virtual environment (recommended)**
```powershell
.\venv\Scripts\Activate.ps1
python tools\led_simulator_v2.1.py
```

**Option 2: Batch launcher**
```batch
tools\run_simulator.bat
```

**With Audio Support (optional):**
```powershell
.\venv\Scripts\Activate.ps1
pip install pyaudio
python tools\led_simulator_v2.1.py
```

#### Manual Launch (all platforms)

```bash
python tools/LED_Simulator/led_simulator_v2.1.py
```

**Note**: All versions available:
- `led_simulator_v2.1.py` - **Recommended** (sounds, stalling, realistic physics)
- `led_simulator_v2.py` - Basic car config support
- `led_simulator.py` - Original version (v1)

### Requirements

- Python 3.7 or higher (comes with Windows 11)
- tkinter (included with Python)
- Virtual environment (optional but recommended)

### Controls

| Key | Action |
|-----|--------|
| ↑ Up Arrow | Gas Pedal (increase RPM) |
| ↓ Down Arrow | Brake (decrease RPM) |
| → Right Arrow | Shift Up (1st → 6th) |
| ← Left Arrow | Shift Down (6th → 1st) |
| Shift | Clutch (hold while shifting or revving) |
| ESC | Quit (with confirmation) |

### How to Use

1. **Launch the simulator** using `run_simulator.bat` or directly with Python
2. **Click "START ENGINE"** button (engine starts at idle, gear shows "1")
3. **Optional: Load different car** using "Load Car File" button
4. **Hold Shift (clutch)** and press Up Arrow to rev the engine
5. **Release clutch** and continue holding Up Arrow to accelerate
6. **Shift up** with Right Arrow (use clutch for smooth shifts)
7. **Watch the LEDs** change color and count as RPM increases:
   - 🟢 Green: Low RPM (1000-3000)
   - 🟡 Yellow: Mid RPM (3000-5000)
   - 🟠 Orange: High RPM (5000-6500)
   - 🔴 Red Flash: Shift light (6500+)
8. **Click "STOP ENGINE"** to turn off the engine

### Car Configuration Files

The simulator supports loading custom car configurations from JSON files in the `cars/` directory.

**Default Car**: 2008 Mazda MX-5 NC (auto-loaded on startup)

**Creating Custom Cars**:
1. See `cars/README.md` for complete file format documentation
2. Copy an existing car file (e.g., `cars/2008_miata_nc.json`)
3. Modify values to match your vehicle
4. Load in simulator using "Load Car File" button

**Included Cars**:
- `2008_miata_nc.json` - 2008 Mazda MX-5 NC (170hp, 6-speed manual)
- `example_sports_car.json` - Generic performance car (400hp, turbocharged)

### Customizing LED Logic

The LED color algorithm is in `led_simulator.py`:

```python
def get_rpm_color(rpm):
    """Calculate LED color based on RPM."""
    # Modify this function to change LED colors
    # Returns RGB tuple (0-255, 0-255, 0-255)
```

**To test your changes:**
1. Edit `led_simulator.py`
2. Run the simulator
3. Test the LED behavior
4. When satisfied, apply the same logic to Arduino code in `lib/LEDController/LEDController.cpp`

### Configuration

Match these values with your `lib/Config/config.h`:

```python
LED_COUNT = 20              # Number of LEDs in strip
RPM_IDLE = 800             # Idle RPM
RPM_MIN_DISPLAY = 1000     # Minimum RPM to light LEDs
RPM_MAX_DISPLAY = 7000     # Maximum RPM for gradient
RPM_SHIFT_LIGHT = 6500     # Shift light activation RPM
RPM_REDLINE = 7200         # Absolute redline
```

### Physics Simulation

The simulator includes realistic MX-5 NC physics:

- **Gear Ratios**: Authentic 6-speed manual ratios
- **Final Drive**: 4.100:1
- **Tire Size**: 205/45R17
- **Acceleration**: Realistic RPM climb rate
- **Engine Braking**: RPM follows speed in gear

### Troubleshooting

#### Python Not Found

Install Python from [python.org](https://www.python.org/downloads/):
- ✅ Check "Add Python to PATH" during installation
- Restart terminal after installation

#### tkinter Not Found

Tkinter should come with Python. If missing:

**Windows:**
```batch
python -m pip install tk
```

**Linux:**
```bash
sudo apt-get install python3-tk
```

**macOS:**
```bash
brew install python-tk
```

#### Window Not Responding

- Make sure to click on the window after launch
- Keyboard focus must be on the simulator window

### Tips

1. **Realistic shifting**: Hold clutch (Shift key) while changing gears
2. **Rev matching**: Blip throttle (Up Arrow) while downshifting with clutch held
3. **Test shift light**: Accelerate in 1st gear with clutch held to quickly reach redline
4. **Test all gears**: Each gear has different RPM characteristics
5. **Color testing**: Focus on 3000-7000 RPM range for most driving

### Files

- `led_simulator.py` - Main simulator application
- `run_simulator.bat` - Windows launcher script
- `README.md` - This file

### Development Notes

The simulator matches the Arduino implementation in:
- `lib/LEDController/LEDController.cpp` - LED update logic
- `lib/Config/config.h` - Configuration constants

Any changes to LED logic should be tested here first before uploading to Arduino.
