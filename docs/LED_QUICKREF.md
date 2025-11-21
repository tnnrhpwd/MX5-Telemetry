# LED Mirrored Progress Bar System - Quick Reference

## 🎨 Visual States (7 Total)

```
┌─────────────────────────────────────────────────────────────────┐
│  ⚪ STATE 0: IDLE/NEUTRAL (Speed = 0)                           │
├─────────────────────────────────────────────────────────────────┤
│  Pattern: ⚪ → ⚪⚪ → ⚪⚪⚪ → ... → center                         │
│  Animation: Pepper inward (edges to center)                     │
│  Color: White (255, 255, 255)                                   │
│  Brightness: 180                                                │
│  Purpose: Vehicle stationary (neutral/clutch)                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  🟢 STATE 1: GAS EFFICIENCY (2000-2500 RPM)                     │
├─────────────────────────────────────────────────────────────────┤
│  Pattern: 🟢🟢 ⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫ 🟢🟢                              │
│  Animation: Static (2 LEDs per side)                            │
│  Color: Green (0, 255, 0)                                       │
│  Brightness: 180                                                │
│  Purpose: Optimal cruising range confirmation                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  🟠 STATE 2: STALL DANGER (750-1999 RPM)                        │
├─────────────────────────────────────────────────────────────────┤
│  Pattern: ⚫⚫⚫🟠🟠⚫⚫🟠🟠⚫⚫⚫ → 🟠🟠🟠🟠🟠🟠🟠🟠🟠🟠🟠🟠            │
│  Animation: Pulse outward (center to edges)                     │
│  Color: Orange (255, 80, 0)                                     │
│  Brightness: 20-200 (pulsing)                                   │
│  Purpose: Warn of potential stall                               │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  🟡 STATE 3: NORMAL DRIVING (2501-4500 RPM)                     │
├─────────────────────────────────────────────────────────────────┤
│  Pattern: 🟡🟡🟡🟡🟡 ⚫⚫⚫⚫ 🟡🟡🟡🟡🟡                              │
│  Animation: Mirrored progress bar (inward growth)               │
│  Color: Yellow (255, 255, 0)                                    │
│  Brightness: 255                                                │
│  Purpose: Show RPM progression in power band                    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  🔴 STATE 4: SHIFT DANGER (4501-7199 RPM)                       │
├─────────────────────────────────────────────────────────────────┤
│  Pattern: 🟥🟥🟥🟥🟥🟥 ✨✨✨✨ 🟥🟥🟥🟥🟥🟥                         │
│  Animation: Solid red bar + flashing gap (red/white/cyan)       │
│  Color: Red (255,0,0) + Flash (255,255,255) & (0,255,255)      │
│  Brightness: 255 (maximum urgency)                              │
│  Flash Speed: 150ms→40ms (faster as RPM increases)              │
│  Purpose: Urgent shift signal, gap closes as RPM rises          │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  🛑 STATE 5: REV LIMIT (7200+ RPM)                              │
├─────────────────────────────────────────────────────────────────┤
│  Pattern: 🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥                         │
│  Animation: Solid (no animation)                                │
│  Color: Red (255, 0, 0)                                         │
│  Brightness: 255                                                │
│  Purpose: Maximum limit (fuel cut) - immediate action required  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  ❌ ERROR STATE: CAN BUS FAILURE                                │
├─────────────────────────────────────────────────────────────────┤
│  Pattern: 🔴 → 🔴🔴 → 🔴🔴🔴 → ... → center                      │
│  Animation: Pepper inward (edges to center)                     │
│  Color: Red (255, 0, 0)                                         │
│  Brightness: 200                                                │
│  Purpose: Indicate CAN communication failure                    │
└─────────────────────────────────────────────────────────────────┘
```

## 📝 Quick Modification Guide

### Change State RPM Ranges

**Files to Edit:**
1. `lib/Config/LEDStates.h` (Arduino)
2. `tools/LED_Simulator/led_simulator_v2.1.py` (Python)

**Example - Adjust State 3 range:**

```cpp
// Arduino: LEDStates.h
#define STATE_3_RPM_MIN    2000    // Change from 2501
#define STATE_3_RPM_MAX    5000    // Change from 4500
```

Then run parser to auto-sync simulator:
```powershell
python tools\LED_Simulator\parse_arduino_led_config.py
```

### Change Colors

**State 2 (Orange) → Red:**

```cpp
// Arduino: LEDStates.h
#define STATE_2_COLOR_R    255
#define STATE_2_COLOR_G    0      // Was 80
#define STATE_2_COLOR_B    0
```

Then run parser to auto-sync simulator:
```powershell
python tools\LED_Simulator\parse_arduino_led_config.py
```

### Adjust Animation Speed

**State 1 Pulse (slower):**

```cpp
// Arduino: LEDStates.h
#define STATE_1_PULSE_PERIOD    1200    // Was 800
```

```python
# Python: led_simulator_v2.1.py
STATE_1_PULSE_PERIOD = 1200  # Was 800
```

**State 3 Chase (faster):**

```cpp
// Arduino: LEDStates.h
#define STATE_3_CHASE_SPEED_MIN    80     // Was 120
#define STATE_3_CHASE_SPEED_MAX    20     // Was 40
```

```python
# Python: led_simulator_v2.1.py
STATE_3_CHASE_SPEED_MIN = 80   # Was 120
STATE_3_CHASE_SPEED_MAX = 20   # Was 40
```

## 🔧 Implementation Files

| Component | Arduino | Python Simulator |
|-----------|---------|------------------|
| **Constants** | `lib/Config/LEDStates.h` (53 constants) | Auto-loaded via parser |
| **Parser** | - | `tools/LED_Simulator/parse_arduino_led_config.py` |
| **State Logic** | `LEDController.cpp` | Functions: `get_state_0_pattern()` to `get_error_pattern()` |
| **State Detection** | `updateRPM()` method | Speed/RPM threshold checks |
| **Main Update** | `updateRPM()` method | `draw_leds()` method |

## 📊 State Specifications

| State | Range | Pattern | Color | Animation | Brightness |
|-------|-------|---------|-------|-----------|------------|
| **0** | Speed = 0 | Pepper Inward | White | ✓ Sequential | 180 |
| **1** | 2000-2500 RPM | 2 LEDs/side | Green | ✗ Static | 180 |
| **2** | 750-1999 RPM | Pulse Outward | Orange | ✓ Pulsing | 20-200 |
| **3** | 2501-4500 RPM | Mirrored Bar | Yellow | ✗ Static | 255 |
| **4** | 4501-7199 RPM | Bar + Flash Gap | Red + W/C | ✓ Flashing | 255 |
| **5** | 7200+ RPM | Full Strip | Red | ✗ Solid | 255 |
| **Error** | CAN Fail | Pepper Inward | Red | ✓ Sequential | 200 |

## 🚀 Testing Workflow

1. **Edit Constants** in `lib/Config/LEDStates.h`
2. **Run Parser to Auto-Sync:**
   ```powershell
   python tools\LED_Simulator\parse_arduino_led_config.py
   ```
3. **Test in Simulator:**
   ```powershell
   python tools\LED_Simulator\led_simulator_v2.1.py
   ```
4. **Build Arduino:**
   ```powershell
   pio run
   ```
5. **Upload to Hardware:**
   ```powershell
   pio run --target upload
   ```

## ⚠️ Important Rules

1. **Use the Parser for Automatic Synchronization**
   - Edit `LEDStates.h` in Arduino code
   - Run `parse_arduino_led_config.py` to auto-sync simulator
   - Ensures Arduino and Python always match

2. **Test in simulator first**
   - Faster iteration
   - Visual confirmation before hardware upload
   - No hardware upload needed for testing

3. **State Priority**
   - Speed = 0 triggers State 0 (overrides RPM)
   - CAN Error triggers Error State (overrides all)
   - RPM determines states 1-5

4. **Brightness values: 0-255**
   - 0 = Off
   - 255 = Maximum
   - States 0, 1, 2, Error use lower brightness for comfort

## 🎯 Mathematical Formulas

### State 0/Error: Pepper Inward
```cpp
currentLED = (currentTime / PEPPER_DELAY) % LED_COUNT
// Light LEDs from edges toward center symmetrically
leftLED = currentLED / 2
rightLED = LED_COUNT - 1 - (currentLED / 2)
```

### State 2: Pulse Brightness
```cpp
phase = (currentTime % PULSE_PERIOD) / PULSE_PERIOD
angle = phase * 2π
sineValue = (sin(angle) + 1.0) / 2.0
brightness = MIN_BRIGHTNESS + sineValue * (MAX_BRIGHTNESS - MIN_BRIGHTNESS)
```

### State 3: Mirrored Bar Position
```cpp
position = (rpm - STATE_3_MIN) / (STATE_3_MAX - STATE_3_MIN)
activeLEDsPerSide = (position * LED_COUNT) / 2
// Light from edges inward
```

### State 4: Flash Speed
```cpp
rpmRatio = (rpm - STATE_4_MIN) / (STATE_4_MAX - STATE_4_MIN)
flashSpeed = FLASH_MIN - (rpmRatio * (FLASH_MIN - FLASH_MAX))
// Faster flashing as RPM increases
```

## 📞 Need Help?

- **Full Documentation**: `docs/LED_STATE_SYSTEM.md`
- **Arduino Code**: `lib/LEDController/LEDController.cpp`
- **Python Code**: `tools/LED_Simulator/led_simulator_v2.1.py`
- **Constants**: `lib/Config/LEDStates.h`

---

**Remember**: The simulator always mirrors the Arduino! Keep them in sync! 🔄
