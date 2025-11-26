# LED Mirrored Progress Bar System

## Overview

The MX5-Telemetry project uses a sophisticated **mirrored progress bar** LED system that provides intuitive visual feedback for different driving conditions. The progress bar grows from both edges **inward toward the center**, creating a symmetric visual that's easy to read peripherally while driving.

This system is implemented consistently across both the Arduino hardware and the Python simulator, with 7 distinct states.

## 🎨 The Seven States

### ⚪ State 0: Idle/Neutral (Speed = 0)
**Purpose:** Visual confirmation that vehicle is stationary (not moving).

**Visual Pattern:**
```
⚪ → ⚪ ⚪ → ⚪ ⚪ ⚪ → ⚪ ⚪ ⚪ ⚪ → ... → ALL ⚪ (center)
```

**Characteristics:**
- **Sequential pepper animation**: White LEDs light up one-by-one from edges inward
- **Direction**: Outer edges → Center
- **Timing**: 80ms delay between each LED
- **Hold**: 300ms at full center illumination
- **Color**: Pure white (RGB: 255, 255, 255)
- **Brightness**: 180 (out of 255)
- **Speed threshold**: Activates when speed < 1 km/h

**When It Activates:**
- Vehicle parked/stopped at traffic light
- Clutch fully engaged (neutral)
- Engine idling with no movement

---

### 🟢 State 1: Gas Efficiency Zone (2000-2500 RPM)
**Purpose:** Subtle confirmation of optimal cruising range.

**Visual Pattern (20 LEDs):**
```
🟢 🟢 ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ 🟢 🟢
```

**Characteristics:**
- **Minimal display**: Only outermost 2 LEDs per side illuminate
- **Static**: No animation, steady glow
- **Color**: Pure green (RGB: 0, 255, 0)
- **Brightness**: 180 (comfortable for cruising)
- **Mirrored**: 2 LEDs left edge + 2 LEDs right edge

**When It Activates:**
- Efficient highway cruising
- Optimal torque range (2000-2500 RPM)
- Best fuel economy zone

---

### 🟠 State 2: Stall Danger (750-1999 RPM)
**Purpose:** Warning that engine is operating below optimal torque range.

**Visual Pattern:**
```
Start: ⚫ ⚫ ⚫ 🟠 🟠 ⚫ ⚫ 🟠 🟠 ⚫ ⚫ ⚫
  ↓ (pulse outward)
Peak:  🟠 🟠 🟠 🟠 🟠 🟠 🟠 🟠 🟠 🟠 🟠 🟠
  ↓ (fade back)
Start: ⚫ ⚫ ⚫ 🟠 🟠 ⚫ ⚫ 🟠 🟠 ⚫ ⚫ ⚫
```

**Characteristics:**
- **Outward pulse**: Orange bars expand from center outward to edges
- **Animation**: Smooth pulse using sine wave
- **Period**: 600ms complete cycle
- **Color**: Orange (RGB: 255, 80, 0)
- **Brightness range**: 20 (dim) to 200 (bright)
- **Direction**: Center → Edges (opposite of normal progress bar)

**When It Activates:**
- Engine lugging (too low RPM for current gear)
- Risk of stalling
- Inefficient operation below torque curve

---

### 🟡 State 3: Normal Driving / Power Band (2501-4500 RPM)
**Purpose:** Main mirrored progress bar showing RPM progression.

**Visual Pattern (at ~4000 RPM, mid-range):**
```
🟡 🟡 🟡 🟡 🟡 ⚫ ⚫ ⚫ ⚫ 🟡 🟡 🟡 🟡 🟡
```

**Characteristics:**
- **Mirrored progress bar**: Bars grow inward from both edges toward center
- **Symmetric**: Left side mirrors right side exactly
- **Color**: Solid yellow (RGB: 255, 255, 0)
- **Brightness**: Full intensity (255)
- **Progressive**: More LEDs light up as RPM increases
- **Calculation**: Each side shows (RPM - 2501) / (4500 - 2501) percentage of LEDs

**Visual Examples:**
- **2501 RPM (0%)**: `⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫`
- **3500 RPM (50%)**: `🟡 🟡 🟡 🟡 ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ 🟡 🟡 🟡 🟡`
- **4500 RPM (100%)**: `🟡 🟡 🟡 🟡 🟡 🟡 🟡 🟡 🟡 🟡 🟡 🟡 🟡 🟡 🟡 🟡`

**When It Activates:**
- Normal acceleration
- Active driving in power band
- Most common state during spirited driving

---

### 🔴 State 4: High RPM / Shift Danger (4501-7199 RPM)
**Purpose:** Urgent visual signal demanding immediate upshift.

**Visual Pattern (at ~6000 RPM):**
```
🟥 🟥 🟥 🟥 🟥 🟥 ✨ ✨ ✨ ✨ 🟥 🟥 🟥 🟥 🟥 🟥
(✨ = rapid red/white/cyan flashing)
```

**Characteristics:**
- **Dual behavior**: 
  1. **Filled segments**: Turn solid red and continue growing inward
  2. **Unfilled center gap**: Flashes violently red/white/cyan
- **Flash speed**: Accelerates as RPM increases
  - 4501 RPM: 150ms per flash
  - 7199 RPM: 40ms per flash (extremely fast)
- **Flash colors**: Alternates between red (255,0,0), white (255,255,255), and cyan (0,255,255)
- **Brightness**: Maximum (255)
- **Progressive**: Gap shrinks as RPM approaches redline

**Visual Progression:**
- **4501 RPM**: `🟥 🟥 ✨ ✨ ✨ ✨ ✨ ✨ ✨ ✨ ✨ ✨ ✨ ✨ 🟥 🟥`
- **5500 RPM**: `🟥 🟥 🟥 🟥 ✨ ✨ ✨ ✨ ✨ ✨ ✨ ✨ 🟥 🟥 🟥 🟥`
- **6500 RPM**: `🟥 🟥 🟥 🟥 🟥 🟥 ✨ ✨ ✨ ✨ 🟥 🟥 🟥 🟥 🟥 🟥`
- **7000 RPM**: `🟥 🟥 🟥 🟥 🟥 🟥 🟥 ✨ ✨ 🟥 🟥 🟥 🟥 🟥 🟥 🟥`

**When It Activates:**
- High-RPM acceleration
- Approaching optimal shift point
- Prevents over-revving and engine damage

---

### 🛑 State 5: Rev Limit Cut (7200+ RPM)
**Purpose:** Absolute maximum - engine at fuel cut limiter.

**Visual Pattern (Full Strip):**
```
🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥
```

**Characteristics:**
- **Complete fill**: Mirrored bars have met at center
- **Solid red**: All LEDs illuminated, no flashing
- **Color**: Pure red (RGB: 255, 0, 0)
- **Brightness**: Maximum (255)
- **No animation**: Static display (urgency is in the solid red)

**When It Activates:**
- Engine at fuel cut (7200+ RPM)
- ECU limiting RPM to prevent damage
- Immediate shift required

---

### ❌ Error State: CAN Bus Read Error
**Purpose:** Visual indication of communication failure with vehicle.

**Visual Pattern:**
```
🔴 → 🔴 🔴 → 🔴 🔴 🔴 → 🔴 🔴 🔴 🔴 → ... → ALL 🔴 (center)
```

**Characteristics:**
- **Sequential pepper animation**: Red LEDs light up one-by-one from edges inward
- **Direction**: Outer edges → Center (same as State 0, but red)
- **Timing**: 80ms delay between each LED
- **Hold**: 300ms at full center illumination
- **Color**: Pure red (RGB: 255, 0, 0)
- **Brightness**: 200 (out of 255)
- **Trigger**: No valid CAN data received

**When It Activates:**
- CAN bus disconnected
- MCP2515 module failure
- Vehicle communication error
- Loose wiring to OBD-II port

---

## 📁 Implementation Files

### Arduino (C++)

1. **`lib/Config/LEDStates.h`**
   - Central definition of all state constants (53 constants total)
   - Single source of truth for ranges and colors
   - Includes all 7 states: State 0-5 + Error state
   - Helper macros for state detection

2. **`lib/LEDController/LEDController.h`**
   - Class declarations for LED control
   - State methods: `idleNeutralState()`, `gasEfficiencyState()`, `stallDangerState()`, `normalDrivingState()`, `highRPMShiftState()`, `revLimitState()`, `canErrorState()`
   - Helper methods: `drawMirroredBar()`, `pepperInward()`, `pulseOutward()`

3. **`lib/LEDController/LEDController.cpp`**
   - Full implementation of all seven states
   - `updateRPM()` method determines state and calls appropriate function
   - Animation timing and mirrored progress bar calculations

### Python Simulator

1. **`tools/LED_Simulator/led_simulator_v2.1.py`**
   - Mirrors Arduino logic exactly
   - State constants loaded from Arduino header via parser
   - Pattern functions: `get_state_0_pattern()` through `get_state_5_pattern()`, `get_error_pattern()`
   - State detection: Checks speed and RPM thresholds to determine active state

2. **`tools/LED_Simulator/parse_arduino_led_config.py`**
   - Automatic synchronization tool
   - Parses `LEDStates.h` and loads all 53 constants into Python
   - Ensures Arduino and simulator always match

---

## 🔧 How to Modify the LED Logic

### Changing RPM Thresholds

**Step 1: Edit `LEDStates.h` (Arduino)**
```cpp
// Example: Adjust State 3 upper limit
#define STATE_3_RPM_MAX         5000     // Was 4500
```

**Step 2: Run Parser to Auto-Sync Simulator**
```powershell
python tools\LED_Simulator\parse_arduino_led_config.py
```
The simulator automatically loads the new values from the Arduino header file!

### Changing Colors

**State 2 Orange → Different Color:**

Arduino (`LEDStates.h`):
```cpp
#define STATE_2_COLOR_R         200    // Less red
#define STATE_2_COLOR_G         120    // More green
#define STATE_2_COLOR_B         0      // No blue
```

Run parser again to sync:
```powershell
python tools\LED_Simulator\parse_arduino_led_config.py
```

### Changing Animation Speed

**State 1 Pulse Speed:**

Arduino (`LEDStates.h`):
```cpp
#define STATE_1_PULSE_PERIOD    1200   // Slower (was 800ms)
```

Python (`led_simulator_v2.1.py`):
```python
STATE_1_PULSE_PERIOD = 1200  # Match Arduino
```

**State 3 Chase Speed:**

Arduino (`LEDStates.h`):
```cpp
#define STATE_3_CHASE_SPEED_MIN 200    // Slower start (was 120)
#define STATE_3_CHASE_SPEED_MAX 60     // Slower peak (was 40)
```

Python (`led_simulator_v2.1.py`):
```python
STATE_3_CHASE_SPEED_MIN = 200  # Match Arduino
STATE_3_CHASE_SPEED_MAX = 60   # Match Arduino
```

---

## 🔄 Workflow for Making Changes

1. **Test in Simulator First**
   ```powershell
   cd tools
   python led_simulator_v2.1.py
   ```
   - Load your car configuration
   - Start the engine
   - Test RPM ranges with throttle controls
   - Verify visual appearance

2. **Update Arduino Code**
   - Make changes to `LEDStates.h` first
   - Rebuild the project
   - Upload to Arduino

3. **Sync Simulator**
   - Update matching constants in `led_simulator_v2.1.py`
   - Retest to ensure they match

4. **Document Changes**
   - Update this file if you add new states or major changes
   - Update version numbers if appropriate

---

## 🎯 Design Philosophy

### Why Three States?

1. **State 1 (Stall Danger)**: Prevents accidental engine stall, especially important for manual transmission
2. **State 2 (Good Efficiency)**: Encourages efficient driving and provides clear RPM feedback
3. **State 3 (High RPM/Shift)**: Urgent visual signal prevents engine damage and optimizes shift points

### Visual Design Principles

- **Distinct patterns**: Each state uses a unique animation style
- **Progressive urgency**: Calm → Active → Urgent
- **Color psychology**: Orange (warning) → Green/Yellow (optimal) → Red (danger)
- **Speed indicates intensity**: Faster animations at higher RPM in State 3

### Technical Considerations

- **Timing precision**: Both Arduino and Python use millisecond timing
- **Brightness control**: Prevents eye strain at low RPM, maximum visibility at high RPM
- **Smooth transitions**: Animations use sine waves and gradients for smooth visual flow
- **CPU efficiency**: State checks use simple range comparisons, minimal overhead

---

## 🐛 Troubleshooting

### LEDs Not Matching Between Arduino and Simulator

**Problem**: Colors or timing are different
**Solution**: 
- Check that constants in `LEDStates.h` match those in `led_simulator_v2.1.py`
- Verify both are using the same LED_COUNT (30)
- Ensure no custom modifications in one but not the other

### State 3 Chase Not Moving

**Problem**: White LEDs appear stuck
**Solution**:
- Arduino: Check `millis()` is incrementing properly
- Python: Verify `self.current_time_ms` is being updated in `update_simulation()`
- Check chase speed constants aren't too high

### Pulse Animation Not Smooth

**Problem**: State 1 flickers or jumps
**Solution**:
- Verify `STATE_1_PULSE_PERIOD` is reasonable (500-1500ms)
- Check sine wave calculation in `getPulseBrightness()`
- Ensure brightness range (min/max) allows visible variation

---

## 📊 State Comparison Table

| State | RPM/Speed Range | Animation | Color | Brightness | Purpose |
|-------|-----------------|-----------|-------|------------|---------|
| 0 | Speed = 0 | Pepper Inward | White | 180 | Idle/Neutral |
| 1 | 2000-2500 RPM | Static 2 LEDs/side | Green | 180 | Gas Efficiency |
| 2 | 750-1999 RPM | Pulse Outward | Orange | 20-200 | Stall Warning |
| 3 | 2501-4500 RPM | Mirrored Progress Bar | Yellow | 255 | Normal Driving |
| 4 | 4501-7199 RPM | Bar + Flash Gap | Red + White/Cyan | 255 | Shift Danger |
| 5 | 7200+ RPM | Full Solid | Red | 255 | Rev Limit |
| Error | CAN Failure | Pepper Inward | Red | 200 | Communication Error |

---

## 🚀 Future Enhancements

Potential improvements to consider:

1. **Configurable Patterns**: Allow users to select from multiple animation presets
2. **RPM-based Brightness**: Auto-adjust brightness based on ambient light or time of day
3. **Custom Colors**: User-defined color schemes via configuration file
4. **Multi-car Profiles**: Different state ranges for different engines (turbo vs NA)
5. **State Transition Effects**: Smooth crossfade between states

---

## 📝 Version History

- **v3.0**: Complete mirrored progress bar system (7 states)
  - State 0: Idle/Neutral (white pepper inward)
  - State 1: Gas Efficiency (green static 2 LEDs/side)
  - State 2: Stall Danger (orange pulse outward)
  - State 3: Normal Driving (yellow mirrored bar)
  - State 4: Shift Danger (red bar + flashing gap)
  - State 5: Rev Limit (solid red full strip)
  - Error State: CAN Error (red pepper inward)
- **v2.1**: Three-state system
- **v2.0**: Two-state system (gradient + flash)
- **v1.0**: Original single gradient implementation

---

## 📧 Support

If you modify the LED system and encounter issues:

1. Check this documentation first
2. Test in simulator before uploading to Arduino
3. Verify all constants match between Arduino and Python
4. Review the example code in `LEDController.cpp` and `led_simulator_v2.1.py`

Remember: **The simulator should always mirror the Arduino behavior exactly!**
