# LED Simulator v2.0 - Upgrade Summary

## Changes Made

### New Files Created

1. **tools/LED_Simulator/led_simulator_v2.py**
   - Complete rewrite with car configuration support
   - Engine start/stop toggle functionality
   - Car file selection dialog
   - Enhanced UI with car name display

2. **tools/cars/2008_miata_nc.json**
   - Complete 2008 Mazda MX-5 NC specification
   - Accurate gear ratios, RPM limits, tire size
   - Performance data and physics parameters

3. **tools/cars/example_sports_car.json**
   - Generic sports car example (400hp turbocharged)
   - Template for creating custom car files

4. **tools/cars/README.md**
   - Complete documentation for car configuration files
   - Field descriptions and formulas
   - Instructions for creating custom cars

5. **tools/LED_Simulator/led_simulator_v1_backup.py**
   - Backup of original simulator (auto-created)

### Modified Files

1. **tools/README.md**
   - Added v2.0 feature descriptions
   - Updated quick start instructions
   - Added car configuration documentation section

2. **README.md** (main)
   - Updated LED Simulator section for v2.0
   - Added car configuration files description
   - Enhanced feature list

## New Features

### 🔑 Engine Start/Stop
- Button toggle in UI
- Engine starts at idle RPM
- Gear indicator shows "N" when engine is off
- All LEDs off when engine is stopped
- Keyboard controls disabled until engine started

### 🚗 Car Configuration Files
- JSON-based vehicle specifications
- Load custom cars via file dialog
- Default car: 2008 Mazda MX-5 NC
- Supports unlimited custom vehicles

### 📊 Per-Vehicle Physics
Each car file includes:
- Engine specs (displacement, cylinders, RPM limits)
- Transmission (gear ratios, final drive, clutch engagement)
- Tires (size, rolling circumference)
- Performance (top speed, power, weight)
- Physics tuning (acceleration/deceleration rates)

### 🎨 Enhanced UI
- Car name display at top
- "Load Car File" button
- "START ENGINE" / "STOP ENGINE" toggle button
- Status messages for engine state
- Neutral gear display when stopped

## How It Works

### Car Configuration Loading

1. On startup, looks for `tools/cars/2008_miata_nc.json`
2. Falls back to hardcoded defaults if file not found
3. User can load different cars via "Load Car File" button
4. Engine automatically stops when switching cars

### JSON File Structure

```json
{
  "name": "Display Name",
  "engine": {
    "redline_rpm": 7200,
    "idle_rpm": 800,
    "shift_light_rpm": 6500,
    ...
  },
  "transmission": {
    "gear_ratios": {"1": 3.760, ...},
    "final_drive": 4.100,
    ...
  },
  "tires": {
    "circumference_meters": 1.937
  },
  ...
}
```

### Engine State Management

- **Engine OFF (default)**:
  - RPM = 0
  - Gear = N (neutral)
  - All LEDs off (dark gray)
  - Keyboard controls disabled
  - Gauges dimmed (gray needles)

- **Engine ON**:
  - RPM = idle_rpm (from car config)
  - Gear = 1
  - LEDs active based on RPM
  - Keyboard controls enabled
  - Gauges active (colored needles)

### Physics Simulation

RPM calculation uses actual vehicle data:
```python
wheel_rpm = (speed_m/s * 60) / tire_circumference
engine_rpm = wheel_rpm * gear_ratio * final_drive
```

Each car has unique:
- Acceleration rates
- Deceleration rates
- Gear ratios
- Top speed limits
- RPM thresholds

## Backwards Compatibility

- Original `led_simulator.py` preserved as v1
- New `led_simulator_v2.py` is standalone
- Both versions work independently
- v2 recommended for new users

## Testing

Tested successfully with:
- ✅ Engine start/stop functionality
- ✅ Car file loading (2008 Miata NC)
- ✅ Keyboard controls (when engine running)
- ✅ Neutral gear display (engine off)
- ✅ LED strip visualization (on/off states)
- ✅ Gauge rendering (active/dimmed states)

## Usage

### Start the Simulator

```powershell
.\venv\Scripts\Activate.ps1
python tools\LED_Simulator\led_simulator_v2.py
```

### Basic Workflow

1. Click "START ENGINE" button
2. Hold Shift (clutch) and press Up (gas) to rev
3. Release clutch, continue holding Up to accelerate
4. Press Right Arrow to shift up (hold Shift for smooth)
5. Watch LEDs change color as RPM increases
6. Click "STOP ENGINE" to shut down

### Load Custom Car

1. Click "Load Car File" button
2. Navigate to `tools/cars/` directory
3. Select a JSON file (e.g., `example_sports_car.json`)
4. Engine stops automatically during switch
5. Click "START ENGINE" to test new car

## Creating Custom Cars

See `tools/cars/README.md` for:
- Complete JSON schema
- Field descriptions
- Tire circumference calculation
- Gear ratio sources
- Physics tuning tips

## Future Enhancements

Potential additions for v3.0:
- [ ] Save/load simulator state
- [ ] Recording and playback of sessions
- [ ] Multiple LED color schemes
- [ ] Automatic car detection from Arduino
- [ ] Data export for analysis
- [ ] Sound effects for engine/shifts
- [ ] Force feedback support

## Notes

- All car files in `tools/cars/` directory
- JSON format for easy editing
- Infinite car configurations supported
- Physics rates tunable per vehicle
- Original v1 simulator still available
