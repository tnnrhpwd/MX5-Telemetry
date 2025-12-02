# LED Mirrored Progress Bar System - Quick Reference

## 🎨 Visual States (6 Total)

```
┌─────────────────────────────────────────────────────────────────┐
│  ⚪ IDLE STATE (Speed = 0, RPM 0-800)                           │
├─────────────────────────────────────────────────────────────────┤
│  Pattern: ⚪ → ⚪⚪ → ⚪⚪⚪ → ... → center                         │
│  Animation: Pepper inward (edges to center)                     │
│  Color: White (255, 255, 255)                                   │
│  Brightness: 180                                                │
│  Purpose: Vehicle stationary with engine idling                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  🟠 STALL DANGER (Speed > 0, RPM 0-1999)                        │
├─────────────────────────────────────────────────────────────────┤
│  Pattern: 🟠🟠🟠🟠🟠🟠🟠🟠 → 🟠🟠🟠🟠 → 🟠🟠 → 🟠                 │
│  Animation: Progressive bar (INVERTED - more LEDs = lower RPM) │
│  Color: Orange (255, 80, 0)                                     │
│  Brightness: 255                                                │
│  Purpose: Warn of potential stall while moving                  │
│  Note: RPM 0 = full bar, RPM 1999 = minimal bar                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  🔵🟢🟡 NORMAL DRIVING (2000-4500 RPM) - Efficiency Gradient    │
├─────────────────────────────────────────────────────────────────┤
│  Pattern: Smooth color gradient as bar grows inward             │
│  Animation: Mirrored progress bar (inward growth)               │
│  LED Distribution: Non-linear emphasis on efficiency zones      │
│                                                                 │
│  🔵 BLUE (2000-2500 RPM): Best MPG - LEDs 1-3 per side (30%)    │
│     → 500 RPM range gets 3 LEDs (emphasized)                    │
│  🟢 GREEN (2500-4000 RPM): Thermal Eff - LEDs 4-7 per side (40%)│
│     → 1500 RPM range gets 4 LEDs (emphasized)                   │
│  🟡 YELLOW (4000-4500 RPM): High RPM - LEDs 8-10 per side (30%) │
│     → 500 RPM range gets 3 LEDs (compressed)                    │
│                                                                 │
│  Colors: Blue (0,100,255) → Green (0,255,0) → Yellow (255,255,0)│
│  Purpose: Emphasize efficient driving zones visually            │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  🔴 SHIFT DANGER (4501-7199 RPM)                                │
├─────────────────────────────────────────────────────────────────┤
│  Pattern: 🟥🟥🟥🟥🟥🟥 ✨✨✨✨ 🟥🟥🟥🟥🟥🟥                         │
│  Animation: Solid red bar + flashing gap (red/white)            │
│  Color: Red (255,0,0) + Flash (255,255,255)                     │
│  Brightness: 255 (maximum urgency)                              │
│  Flash Speed: 150ms→40ms (faster as RPM increases)              │
│  Purpose: Urgent shift signal, gap closes as RPM rises          │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  🛑 REV LIMIT (7200+ RPM)                                       │
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

## 🌈 Efficiency Gradient Visual Examples (2000-4500 RPM)

**Non-linear LED mapping emphasizes MPG and thermal zones:**
- 🔵 Blue zone (2000-2500): 30% of LEDs for 20% of RPM range
- 🟢 Green zone (2500-4000): 40% of LEDs for 60% of RPM range  
- 🟡 Yellow zone (4000-4500): 30% of LEDs for 20% of RPM range

```
RPM 2000 (start): ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫
                                    (empty - just entered zone)

RPM 2250 (MPG):   🔵 🔵 ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ 🔵 🔵
                                    (blue - best MPG zone)

RPM 2500 (MPG→):  🔵 🔵 🟢 ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ 🟢 🔵 🔵
                                    (3 LEDs, transitioning to green)

RPM 3000 (therm): 🔵 🔵 🟢 🟢 🟢 ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ 🟢 🟢 🟢 🔵 🔵
                                    (green - thermal efficiency zone)

RPM 3500 (therm): 🔵 🔵 🟢 🟢 🟢 🟢 ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ 🟢 🟢 🟢 🟢 🔵 🔵
                                    (green - mid thermal zone)

RPM 4000 (→yel):  🔵 🔵 🟢 🟢 🟢 🟢 🟡 ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ 🟡 🟢 🟢 🟢 🟢 🔵 🔵
                                    (7 LEDs, transitioning to yellow)

RPM 4500 (high):  🔵 🔵 🟢 🟢 🟢 🟢 🟡 🟡 🟡 🟡 🟡 🟡 🟡 🟡 🟢 🟢 🟢 🟢 🔵 🔵
                                    (full bar - approaching shift zone)
```

## 📊 State Summary Table

| State | Condition | Color | LEDs/side | Purpose |
|-------|-----------|-------|-----------|---------||
| ⚪ Idle | Speed=0, RPM 0-800 | White | Animated | Stationary, engine idling |
| 🟠 Stall | Speed>0, RPM 0-1999 | Orange | 0-10 (inv) | Low RPM warning while moving |
| 🔵 MPG | RPM 2000-2500 | Blue→Green | 0-3 (30%) | Best fuel efficiency |
| 🟢 Thermal | RPM 2500-4000 | Green→Yellow | 3-7 (40%) | Best thermal efficiency |
| 🟡 High | RPM 4000-4500 | Yellow | 7-10 (30%) | Approaching shift zone |
| 🔴 Shift | RPM 4501-7199 | Red+Flash | Flash gap | Urgent shift warning |
| 🛑 Limit | RPM 7200+ | Solid Red | Full | Rev limiter engaged |
| ❌ Error | CAN failure | Red | Animated | Communication error |

## 📝 Quick Modification Guide

### Change Efficiency Zone Thresholds

**Files to Edit:** `slave/src/LEDStates.h`

```cpp
// Efficiency zone RPM thresholds
#define NORMAL_RPM_MIN          2000     // Start of normal zone
#define EFFICIENCY_BLUE_END     2500     // End of best MPG zone
#define EFFICIENCY_GREEN_END    4000     // End of thermal efficiency zone  
#define NORMAL_RPM_MAX          4500     // End of normal zone
```

### Change Efficiency Zone Colors

```cpp
// Blue (Best MPG)
#define BLUE_COLOR_R            0
#define BLUE_COLOR_G            100
#define BLUE_COLOR_B            255

// Green (Best Thermal Efficiency)
#define GREEN_COLOR_R           0
#define GREEN_COLOR_G           255
#define GREEN_COLOR_B           0

// Yellow (Approaching High RPM)
#define YELLOW_COLOR_R          255
#define YELLOW_COLOR_G          255
#define YELLOW_COLOR_B          0
```

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
| **Constants** | `slave/src/LEDStates.h` | Auto-loaded via parser |
| **State Logic** | `slave/src/main.cpp` | Simulator functions |
| **State Detection** | `updateLEDDisplay()` | Speed/RPM threshold checks |

## 📊 State Specifications

| State | Condition | Pattern | Color | Animation | Brightness |
|-------|-----------|---------|-------|-----------|------------|
| ⚪ **Idle** | Speed=0, RPM≤800 | Pepper Inward | White | ✓ Sequential | 180 |
| 🟠 **Stall** | Speed>0, RPM 0-1999 | Inverted Bar | Orange | ✗ Static | 255 |
| 🔵 **MPG** | RPM 2000-2500 | Progress Bar | Blue→Green | ✗ Static | 255 |
| 🟢 **Thermal** | RPM 2500-4000 | Progress Bar | Green→Yellow | ✗ Static | 255 |
| 🟡 **High** | RPM 4000-4500 | Progress Bar | Yellow | ✗ Static | 255 |
| 🔴 **Shift** | RPM 4501-7199 | Bar + Flash | Red + White | ✓ Flashing | 255 |
| 🛑 **Limit** | RPM 7200+ | Full Strip | Red | ✗ Solid | 255 |
| ❌ **Error** | CAN Fail | Pepper Inward | Red | ✓ Sequential | 200 |

## 🚀 Testing Workflow

1. **Edit Constants** in `slave/src/LEDStates.h`
2. **Build and Upload Slave:**
   ```powershell
   pio run -d slave --target upload --upload-port COM4
   ```

## ⚠️ Important Rules

1. **State Priority (checked in this order)**
   - Error Mode → Red pepper animation
   - Speed=0 AND RPM≤800 → White idle animation
   - RPM 7200+ → Solid red (rev limit)
   - RPM 4501-7199 → Red flashing (shift danger)
   - RPM 2000-4500 → Blue/Green/Yellow gradient bar
   - RPM 0-1999 (moving) → Orange inverted bar (stall danger)

2. **Efficiency Zones in Normal Driving (2000-4500 RPM)**
   - 🔵 Blue (2000-2500): Best absolute MPG
   - 🟢 Green (2500-4000): Best thermal efficiency
   - 🟡 Yellow (4000-4500): Approaching high RPM

3. **Brightness values: 0-255**
   - 0 = Off
   - 255 = Maximum

## 🎯 Mathematical Formulas

### Idle/Error: Pepper Inward
```cpp
currentLED = (currentTime / PEPPER_DELAY) % LED_COUNT
// Light LEDs from edges toward center symmetrically
```

### Stall Danger: Inverted Bar
```cpp
// More LEDs = lower RPM = more danger
ledsPerSide = map(1999 - rpm, 0, 1999, 0, LED_COUNT / 2)
```

### Normal Driving: Efficiency Gradient
```cpp
// Calculate bar size based on RPM
ledsPerSide = map(rpm - 2000, 0, 2500, 0, LED_COUNT / 2)

// Interpolate color based on RPM zone:
if (rpm <= 2500) interpolate(BLUE, GREEN)
else if (rpm <= 4000) interpolate(GREEN, YELLOW)
else color = YELLOW
```

### Shift Danger: Flash Speed
```cpp
rpmRatio = (rpm - 4501) / (7199 - 4501)
flashSpeed = 150 - (rpmRatio * (150 - 40))  // 150ms → 40ms
```

## 📞 Need Help?

- **Full Documentation**: `docs/features/LED_STATE_SYSTEM.md`
- **Slave Arduino Code**: `slave/src/main.cpp`
- **LED Constants**: `slave/src/LEDStates.h`

---

**🌈 The efficiency gradient helps you drive smarter - stay in blue/green for best fuel economy!**
