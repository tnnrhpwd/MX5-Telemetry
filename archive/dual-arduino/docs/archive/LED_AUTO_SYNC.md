# LED Configuration Synchronization System

## Overview

The Python simulator now **automatically reads** the LED configuration from the Arduino code, ensuring perfect synchronization. When you modify `LEDStates.h`, the simulator automatically picks up those changes.

## 🔄 How It Works

### Arduino → Python Synchronization

1. **Single Source of Truth**: `lib/Config/LEDStates.h` defines all LED constants
2. **Python Parser**: `tools/parse_arduino_led_config.py` reads the header file
3. **Automatic Loading**: Simulator loads constants on startup
4. **Always in Sync**: No manual copying needed - changes propagate automatically

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  lib/Config/LEDStates.h                                     │
│  ────────────────────────                                   │
│  #define STATE_1_RPM_MIN  750                               │
│  #define STATE_1_RPM_MAX  1500                              │
│  #define STATE_1_COLOR_R  255                               │
│  ...                                                         │
└────────────────┬────────────────────────────────────────────┘
                 │
                 │ Parsed by
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  tools/parse_arduino_led_config.py                          │
│  ──────────────────────────────────                         │
│  load_led_config() → Dictionary of constants                │
└────────────────┬────────────────────────────────────────────┘
                 │
                 │ Imported by
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  tools/LED_Simulator/led_simulator_v2.1.py                  │
│  ────────────────────────────                               │
│  STATE_1_RPM_MIN = _led_config['STATE_1_RPM_MIN']           │
│  STATE_1_RPM_MAX = _led_config['STATE_1_RPM_MAX']           │
│  ...                                                         │
│                                                              │
│  ✓ LED visualization uses Arduino constants                 │
│  ✓ State logic matches Arduino exactly                      │
└─────────────────────────────────────────────────────────────┘
```

## 🆕 New Feature: Speed-Aware State 1

### The Problem

Previously, State 1 (Stall Danger) would activate whenever RPM was 750-1500, even if the car was in neutral or the clutch was pressed. This was misleading because there's no stall danger in neutral.

### The Solution

State 1 now checks **vehicle speed**:

- **Speed > 0 km/h**: Show stall danger warning (car is moving, could stall)
- **Speed = 0 km/h**: LEDs off (car in neutral/clutch, no danger)

### Arduino Implementation

**`LEDStates.h`** - New constant:
```cpp
#define STATE_1_MIN_SPEED_KMH   1    // Minimum speed to show stall danger
```

**`LEDController.h`** - New overloaded method:
```cpp
// Original (assumes vehicle is moving)
void updateRPM(uint16_t rpm);

// New (checks vehicle speed)
void updateRPM(uint16_t rpm, uint16_t speed_kmh);
```

**`LEDController.cpp`** - Smart State 1 logic:
```cpp
if (IS_STATE_1(rpm)) {
    if (speed_kmh > 0) {
        stallDangerState(rpm);  // Show warning
    } else {
        strip.clear();  // In neutral - no warning
        strip.show();
    }
}
```

### Python Implementation

**State detection with speed check**:
```python
def is_state_1(rpm, speed_kmh=None):
    """Check if State 1 should activate."""
    if not (STATE_1_RPM_MIN <= rpm <= STATE_1_RPM_MAX):
        return False
    
    # If speed is 0, don't show stall danger
    if speed_kmh is not None and speed_kmh < STATE_1_MIN_SPEED_KMH:
        return False
    
    return True
```

**Usage in simulator**:
```python
# Pass speed to state detection
if is_state_1(self.rpm, self.speed):
    led_pattern = get_state_1_pattern(...)  # Show stall warning
else:
    led_pattern = [(0, 0, 0)] * LED_COUNT   # LEDs off
```

## 📝 Workflow: Making Changes

### 1. Edit Arduino Configuration

Edit only **one file**: `lib/Config/LEDStates.h`

```cpp
// Example: Change State 1 upper RPM limit
#define STATE_1_RPM_MAX    1800    // Was 1500

// Example: Change State 1 color to red
#define STATE_1_COLOR_R    255
#define STATE_1_COLOR_G    0       // Was 80
#define STATE_1_COLOR_B    0

// Example: Change minimum speed threshold
#define STATE_1_MIN_SPEED_KMH    5  // Was 1
```

### 2. Test in Simulator

The simulator automatically picks up your changes:

```powershell
cd tools
python led_simulator_v2.1.py
```

**On startup, you'll see**:
```
Loading LED configuration from Arduino LEDStates.h...
✓ Loaded 27 constants from Arduino
✓ State 1 RPM: 750-1800
✓ State 2 RPM: 1501-4500
✓ State 3 RPM: 4501-7200
```

### 3. Test Speed-Aware Behavior

In the simulator:
1. Start engine (hold SHIFT + SPACE)
2. Let RPM drop to ~1000 (State 1 range)
3. **With clutch pressed** (speed = 0): LEDs should be OFF
4. **Release clutch** (speed > 0): Orange pulsing should appear

### 4. Upload to Arduino

```powershell
pio run
pio run --target upload
```

That's it! No manual synchronization needed.

## 🔍 Verification

### Check Parser Works

Run the parser standalone:

```powershell
cd tools
python parse_arduino_led_config.py
```

**Expected output**:
```
======================================================================
LED CONFIGURATION (from LEDStates.h)
======================================================================

🛑 STATE 1: STALL DANGER
  RPM Range: 750 - 1500
  Color RGB: (255, 80, 0)
  Pulse Period: 800ms
  Brightness: 10 - 180

🟢 STATE 2: GOOD EFFICIENCY
  RPM Range: 1501 - 4500
  Green RGB: (0, 255, 0)
  Yellow RGB: (255, 255, 0)
  Yellow Threshold: 0.7

🔴 STATE 3: HIGH RPM/SHIFT
  RPM Range: 4501 - 7200
  Background RGB: (255, 0, 0)
  Chase RGB: (255, 255, 255)
  Chase Speed: 120ms - 40ms
  Chase Width: 2 LEDs

======================================================================

✓ Successfully parsed LEDStates.h
✓ Found 27 constants
```

### Test State 1 Speed Logic

**Scenario 1: In Neutral (Speed = 0)**
- RPM: 1000
- Speed: 0 km/h
- Gear: N
- **Expected**: LEDs OFF (no stall danger in neutral)

**Scenario 2: In Gear, Moving (Speed > 0)**
- RPM: 1000
- Speed: 15 km/h
- Gear: 2
- **Expected**: Orange pulsing LEDs (stall danger!)

**Scenario 3: Clutch Pressed, Coasting**
- RPM: 1200
- Speed: 0 km/h (clutch disconnects wheels)
- Clutch: PRESSED
- **Expected**: LEDs OFF (clutch pressed = no stall risk)

## 🎯 Benefits

### Before (Manual Sync)

❌ Edit `LEDStates.h`  
❌ Manually copy values to `led_simulator_v2.1.py`  
❌ Easy to forget constants  
❌ Python/Arduino could get out of sync  
❌ State 1 showed even in neutral  

### After (Automatic Sync)

✅ Edit only `LEDStates.h`  
✅ Simulator automatically reads Arduino code  
✅ Impossible to get out of sync  
✅ One source of truth  
✅ State 1 only shows when actually needed  

## 📊 Configuration Constants

All constants automatically loaded from Arduino:

| Constant | Purpose | Example |
|----------|---------|---------|
| `STATE_1_RPM_MIN` | State 1 lower threshold | 750 |
| `STATE_1_RPM_MAX` | State 1 upper threshold | 1500 |
| `STATE_1_MIN_SPEED_KMH` | Min speed to show State 1 | 1 |
| `STATE_1_PULSE_PERIOD` | Pulse animation period | 800ms |
| `STATE_1_COLOR_R/G/B` | State 1 RGB color | (255,80,0) |
| `STATE_2_RPM_MIN/MAX` | State 2 RPM range | 1501-4500 |
| `STATE_2_YELLOW_THRESHOLD` | Green→Yellow transition | 0.70 |
| `STATE_3_CHASE_SPEED_MIN/MAX` | Chase animation speed | 120-40ms |
| ... | *27 total constants* | ... |

## 🐛 Troubleshooting

### "Could not load Arduino config"

**Problem**: Parser can't find `LEDStates.h`

**Solution**:
1. Ensure you're running simulator from `tools/` directory
2. Check that `lib/Config/LEDStates.h` exists
3. Verify file path structure:
   ```
   MX5-Telemetry/
   ├── lib/
   │   └── Config/
   │       └── LEDStates.h
   └── tools/
       ├── led_simulator_v2.1.py
       └── parse_arduino_led_config.py
   ```

### State 1 Always Shows (Even in Neutral)

**Problem**: Speed checking not working

**Solution**:
1. Verify `STATE_1_MIN_SPEED_KMH` is set in `LEDStates.h`
2. Check simulator passes `self.speed` to `is_state_1()`
3. Ensure Arduino calls `updateRPM(rpm, speed_kmh)` not just `updateRPM(rpm)`

### Constants Not Updating

**Problem**: Changed `LEDStates.h` but simulator uses old values

**Solution**:
1. Completely restart the simulator (don't just reload)
2. Python caches imports - need fresh Python process
3. Check for syntax errors in `LEDStates.h` that might cause parser to fail

## 🚀 Future Enhancements

Potential improvements:

1. **Live Reload**: Detect changes to `LEDStates.h` and hot-reload
2. **Validation**: Check for invalid ranges or overlapping states
3. **UI Editor**: GUI to edit constants and generate `LEDStates.h`
4. **Multiple Profiles**: Switch between different configurations
5. **Export/Import**: Share configurations as JSON files

## 📚 Related Files

- **`lib/Config/LEDStates.h`** - Arduino LED configuration (master copy)
- **`lib/LEDController/LEDController.h`** - Arduino LED controller interface
- **`lib/LEDController/LEDController.cpp`** - Arduino LED implementation
- **`tools/parse_arduino_led_config.py`** - Configuration parser
- **`tools/LED_Simulator/led_simulator_v2.1.py`** - Python simulator
- **`docs/LED_STATE_SYSTEM.md`** - Comprehensive system documentation
- **`docs/LED_QUICKREF.md`** - Quick reference guide

---

**The simulator always mirrors the Arduino!** 🎯
