# LED Mirrored Progress Bar System

## Overview

The MX5-Telemetry project uses a sophisticated **mirrored progress bar** LED system that provides intuitive visual feedback for different driving conditions. The progress bar grows from both edges **inward toward the center**, creating a symmetric visual that's easy to read peripherally while driving.

The system features a **smooth color gradient** in the normal driving zone (2000-4500 RPM) that transitions through three efficiency zones: Blue (best MPG) → Green (best thermal efficiency) → Yellow (approaching high RPM).

## 🎨 The Seven States

### 🔴 Standby State (Speed = 0, RPM = 0) - NEW!
**Purpose:** Indicates system is waiting for data - CAN bus not connected OR engine off.

**Visual Pattern (Cylon Scanner Effect):**
```
Frame 1: 🔴 ● ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ 🔴
Frame 2: 🔴 🔴 ● ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ 🔴 🔴
  ...    (scanner sweeps across strip)
```
*Note: 🔴 = dim breathing red background, ● = bright white-red scanner head*

**Characteristics:**
- **Scanner effect**: Single bright dot sweeps back and forth across the strip
- **Breathing background**: Dim red glow pulses slowly (3-second cycle)
- **Scanner head**: Bright white-red (RGB: 255, 60, 30)
- **Scanner trail**: Red gradient fading 3 LEDs behind the head
- **Speed**: 50ms per position update (smooth motion)
- **Triggers when**: Speed = 0 km/h AND RPM = 0

**When It Activates:**
- System powered on but CAN bus not yet connected
- Engine is off (ignition on but not started)
- CAN communication lost (reverts to this state)
- Futuristic "standby/sleep" visual while waiting

---

### ⚪ Idle State (Speed = 0, RPM 1-1999)
**Purpose:** Visual indication of RPM while stationary - shows engine breathing/revving.

**Visual Pattern (Progressive Inward Bar):**
```
RPM 100:  ⚪ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚪ (1 LED per side)
RPM 500:  ⚪ ⚪ ⚪ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚪ ⚪ ⚪ (~3 LEDs)
RPM 1000: ⚪ ⚪ ⚪ ⚪ ⚪ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚪ ⚪ ⚪ ⚪ ⚪ (~5 LEDs)
RPM 1500: ⚪ ⚪ ⚪ ⚪ ⚪ ⚪ ⚪ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚪ ⚪ ⚪ ⚪ ⚪ ⚪ ⚪ (~7 LEDs)
RPM 2000: ⚪ ⚪ ⚪ ⚪ ⚪ ⚪ ⚪ ⚪ ⚪ ⚪ ⚪ ⚪ ⚪ ⚪ ⚪ ⚪ ⚪ ⚪ ⚪ ⚪ (FULL - 10 per side)
```

**Characteristics:**
- **Progressive bar**: White LEDs grow inward from edges as RPM increases
- **Direction**: Outer edges → Center (mirrored on both sides)
- **Linear scale**: LEDs scale from 1 (RPM=1) to full (RPM=2000)
- **Gradient brightness**: Brighter at edges, dims toward center for depth effect
- **Color**: Pure white (RGB: 255, 255, 255)
- **Brightness**: 180 (out of 255) at edges, fades to ~40% at innermost lit LED
- **Triggers when**: Speed = 0 km/h AND RPM 1-1999

**When It Activates:**
- Vehicle parked/stopped at traffic light with engine running
- Engine idling (~750 RPM) or being revved while stationary
- Shows "breathing" visual feedback as RPM fluctuates at idle
- Provides instant feedback when blipping throttle while stopped

---

### 🟠 Stall Danger (Speed > 0, RPM 0-1999)
**Purpose:** Warning that engine is operating below optimal torque range while moving.

**Visual Pattern (INVERTED - more LEDs = lower RPM = more danger):**
```
RPM 0:    🟠 🟠 🟠 🟠 🟠 🟠 🟠 🟠 🟠 🟠 🟠 🟠 🟠 🟠 🟠 🟠 (FULL - maximum danger!)
RPM 1000: 🟠 🟠 🟠 🟠 🟠 ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ 🟠 🟠 🟠 🟠 🟠 (half)
RPM 1999: 🟠 ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ 🟠 (minimal - almost safe)
```

**Characteristics:**
- **Progressive bar (INVERTED)**: More LEDs lit = lower RPM = more danger
- **Direction**: Bars shrink as RPM increases toward safe zone
- **Color**: Orange (RGB: 255, 80, 0)
- **Brightness**: Full intensity (255)
- **Only activates when moving**: Speed > 0 prevents false alarms at idle

**When It Activates:**
- Engine lugging (too low RPM for current gear) while driving
- Risk of stalling while moving
- Inefficient operation below torque curve

---

### 🔵🟢🟡 Normal Driving Zone (2000-4500 RPM) - Efficiency Gradient
**Purpose:** Main driving zone with smooth color gradient showing efficiency zones.

The bar grows from edges inward, with color indicating which efficiency zone you're in:

#### 🔵 Blue Zone (2000-2500 RPM) - Best MPG
**Purpose:** Optimal fuel economy for highway cruising.
```
🔵 🔵 ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ 🔵 🔵
```
- **Color**: Blue (RGB: 0, 100, 255)
- **Best for**: Highway cruising, maximum miles per gallon
- **Smooth transition**: Blends into green as RPM increases

#### 🟢 Green Zone (2500-4000 RPM) - Best Thermal Efficiency
**Purpose:** Optimal power-to-fuel ratio, best thermal efficiency.
```
🟢 🟢 🟢 🟢 🟢 🟢 ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ 🟢 🟢 🟢 🟢 🟢 🟢
```
- **Color**: Green (RGB: 0, 255, 0)
- **Best for**: Spirited driving, optimal engine performance
- **Smooth transition**: Blends from blue, blends into yellow

#### 🟡 Yellow Zone (4000-4500 RPM) - Approaching High RPM
**Purpose:** Nearing the shift danger zone.
```
🟡 🟡 🟡 🟡 🟡 🟡 🟡 🟡 🟡 🟡 🟡 🟡 🟡 🟡 🟡 🟡 🟡 🟡 🟡 🟡
```
- **Color**: Yellow (RGB: 255, 255, 0)
- **Indication**: Approaching high RPM, prepare to shift soon

**Visual Progression with Color Gradient:**
```
RPM 2000 (0%):   ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫   (empty)
RPM 2250 (10%):  🔵 ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ 🔵   (blue - best MPG)
RPM 2500 (20%):  🔵 🟢 ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ 🟢 🔵   (blue→green transition)
RPM 3000 (40%):  🟢 🟢 🟢 🟢 ⚫ ⚫ 🟢 🟢 🟢 🟢   (green - thermal efficiency)
RPM 3500 (60%):  🟢 🟢 🟢 🟢 🟢 🟢 🟢 🟢 🟢 🟢   (green - power band)
RPM 4000 (80%):  � 🟡 🟡 🟡 🟡 🟡 🟡 🟡 🟡 �   (green→yellow transition)
RPM 4500 (100%): 🟡 🟡 🟡 🟡 🟡 🟡 🟡 🟡 🟡 🟡   (yellow - full bar)
```

**Characteristics:**
- **Smooth interpolation**: Colors blend seamlessly between zones
- **Mirrored progress bar**: Symmetric growth from both edges
- **Brightness**: Full intensity (255)
- **Non-linear mapping**: Efficiency zones get more visual emphasis (3-4-3 LED distribution)
- **Color calculation**: Linear interpolation between zone colors

---

### 🔴 Shift Danger (4501-7199 RPM)
**Purpose:** Urgent visual signal demanding immediate upshift.

**Visual Pattern (at ~6000 RPM):**
```
🟥 🟥 🟥 🟥 🟥 🟥 ✨ ✨ ✨ ✨ 🟥 🟥 🟥 🟥 🟥 🟥
(✨ = rapid red/white flashing)
```

**Characteristics:**
- **Dual behavior**: 
  1. **Filled segments**: Solid red, continue growing inward
  2. **Unfilled center gap**: Flashes rapidly red/white
- **Flash speed**: Accelerates as RPM increases
  - 4501 RPM: 150ms per flash
  - 7199 RPM: 40ms per flash (extremely fast)
- **Flash colors**: Alternates between red (255,0,0) and white (255,255,255)
- **Brightness**: Maximum (255)
- **Progressive**: Gap shrinks as RPM approaches redline

**Visual Progression:**
```
4501 RPM: 🟥 🟥 ✨ ✨ ✨ ✨ ✨ ✨ ✨ ✨ ✨ ✨ ✨ ✨ 🟥 🟥 (large gap)
5500 RPM: 🟥 🟥 🟥 🟥 ✨ ✨ ✨ ✨ ✨ ✨ ✨ ✨ 🟥 🟥 🟥 🟥 (medium gap)
6500 RPM: 🟥 🟥 🟥 🟥 🟥 🟥 ✨ ✨ ✨ ✨ 🟥 🟥 🟥 🟥 🟥 🟥 (small gap)
7000 RPM: 🟥 🟥 🟥 🟥 🟥 🟥 🟥 ✨ ✨ 🟥 🟥 🟥 🟥 🟥 🟥 🟥 (tiny gap)
```

---

### 🛑 Rev Limit (7200+ RPM)
**Purpose:** Absolute maximum - engine at fuel cut limiter.

**Visual Pattern (Full Strip):**
```
🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥 🟥
```

**Characteristics:**
- **Complete fill**: All LEDs solid red
- **No animation**: Static display for maximum urgency
- **Color**: Pure red (RGB: 255, 0, 0)
- **Brightness**: Maximum (255)

---

### ❌ Error State: Communication/Master Timeout
**Purpose:** Visual indication of communication failure - triggered by master timeout or explicit error command.

**Visual Pattern (Dual Scanner with Urgent Pulse):**
```
Frame 1: ● 🔴 🔴 ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ 🔴 🔴 ● 
Frame 2: 🔴 ● 🔴 🔴 ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ ⚫ 🔴 🔴 ● 🔴
  ...    (scanners sweep inward then outward from both edges)
```
*Note: ● = bright white scanner head, 🔴 = red gradient trail, ⚫ = pulsing dim red*

**Characteristics:**
- **Dual scanner**: White scanner heads sweep inward/outward from both edges (mirrored)
- **Fast urgent pulse**: Background pulses rapidly (500ms cycle) for urgency
- **Scanner cycle**: 1.2 seconds per full in-out sweep
- **Scanner head**: Bright white flash (RGB: 255, 255, 255)
- **Scanner trail**: Red gradient fading 2 LEDs behind head
- **Background**: Pulsing dim red (~20-60 brightness)

**When It Activates:**
- Master Arduino stops sending updates for 5+ seconds
- Explicit error command (`E`) received from master
- Indicates something needs attention

---

## 📊 Complete State Summary

| State | Condition | Color | Animation | Purpose |
|-------|-----------|-------|-----------|---------|
| 🔴 Standby | Speed=0, RPM=0 | Dim Red | Scanner sweep | Waiting for CAN/engine |
| ⚪ Idle | Speed=0, RPM 1-1999 | White | Progress bar | Engine running, stationary |
| 🟠 Stall | Speed>0, RPM 0-1999 | Orange | Inverted bar | Stall warning while moving |
| 🔵 MPG | RPM 2000-2500 | Blue | Progress bar | Best fuel efficiency |
| 🟢 Thermal | RPM 2500-4000 | Green | Progress bar | Best thermal efficiency |
| 🟡 High | RPM 4000-4500 | Yellow | Progress bar | Approaching shift zone |
| 🔴 Shift | RPM 4501-7199 | Red+Flash | Flash gap | Urgent shift warning |
| 🛑 Limit | RPM 7200+ | Solid Red | Static | Rev limiter engaged |
| ❌ Error | Master timeout | Red | Dual scanner | Communication error |
---

## 📁 Implementation Files

### Arduino (C++) - Slave Controller

1. **`slave/src/LEDStates.h`**
   - LED state constants and thresholds
   - Efficiency zone definitions (blue/green/yellow ranges)
   - Color values for each state

2. **`slave/src/main.cpp`**
   - Full LED state machine implementation
   - Key functions:
     - `updateLEDDisplay()`: Main state detection and dispatch
     - `idleState()`: White pepper animation when stationary
     - `stallDangerState()`: Inverted orange bar when moving at low RPM
     - `normalDrivingState()`: Efficiency gradient (blue→green→yellow)
     - `shiftDangerState()`: Red bar with flashing center
     - `revLimitState()`: Solid red strip
     - `canErrorState()`: Red pepper animation
   - Helper functions:
     - `getInterpolatedColor()`: Linear color blending
     - `getEfficiencyColor()`: Calculate gradient color from RPM

### Configuration

1. **`lib/Config/config.h`**
   - Master Arduino configuration
   - CAN bus settings and OBD-II PIDs
   - Commented Mazda NC CAN IDs for future use

---

## 🔧 How to Modify the LED Logic

### Changing RPM Thresholds

**Edit `slave/src/LEDStates.h`:**
```cpp
// Efficiency zone thresholds
#define EFFICIENCY_BLUE_END     2500     // Blue→Green transition
#define EFFICIENCY_GREEN_END    4000     // Green→Yellow transition
#define NORMAL_RPM_MAX          4500     // Yellow→Red transition
```

### Changing Colors

**Edit `slave/src/LEDStates.h`:**
```cpp
// Efficiency zone colors
#define BLUE_COLOR_R            0
#define BLUE_COLOR_G            100
#define BLUE_COLOR_B            255

#define GREEN_COLOR_R           0
#define GREEN_COLOR_G           255
#define GREEN_COLOR_B           0

#define YELLOW_COLOR_R          255
#define YELLOW_COLOR_G          255
#define YELLOW_COLOR_B          0
```

### Building and Uploading

```powershell
# Build the slave firmware
pio run -d slave

# Upload to slave Arduino (adjust COM port as needed)
pio run -d slave --target upload --upload-port COM4
```

---

## 🔄 Workflow for Making Changes

1. **Edit Constants**
   - Modify `slave/src/LEDStates.h` for thresholds/colors
   - Modify `slave/src/main.cpp` for logic changes

2. **Build and Test**
   ```powershell
   pio run -d slave --target upload --upload-port COM4
   ```

3. **Verify Behavior**
   - Connect to vehicle or use simulator
   - Test each state transition
   - Verify color gradients are smooth

---

## 🎯 Design Philosophy

### Why These States?

1. **⚪ Idle**: Clear visual that system is working while stationary
2. **🟠 Stall Danger**: Prevents accidental engine stall while moving (manual transmission)
3. **🔵 MPG Zone**: Encourages fuel-efficient driving (2000-2500 RPM)
4. **🟢 Thermal Efficiency**: Optimal engine power-to-fuel ratio (2500-4000 RPM)
5. **🟡 High RPM**: Visual feedback approaching shift zone (4000-4500 RPM)
6. **🔴 Shift Danger**: Urgent signal to upshift before damage (4501-7199 RPM)
7. **🛑 Rev Limit**: Engine at fuel cut - immediate shift needed (7200+ RPM)

### Visual Design Principles

- **Efficiency gradient**: Smooth blue→green→yellow teaches optimal driving habits
- **Inverted stall bar**: More LEDs = more danger = lower RPM (intuitive)
- **Progressive urgency**: Calm → Active → Urgent as RPM increases
- **Color psychology**: Blue/Green (good) → Yellow (caution) → Red (danger)

### Mazda MX-5 NC Specific

These thresholds are optimized for the Mazda MX-5 NC (2006-2015):
- **2000-2500 RPM**: Best absolute MPG zone
- **2500-4000 RPM**: Best thermal efficiency (power-to-fuel ratio)
- **7200 RPM**: Factory fuel cut (rev limiter)

---

## 🐛 Troubleshooting

### LEDs Not Responding

**Problem**: No LED output
**Solution**: 
- Check wiring between Slave Arduino and WS2812B strip
- Verify 5V power supply to LED strip
- Check `LED_PIN` in `slave/src/main.cpp`

### Colors Not Correct

**Problem**: Wrong colors in efficiency zone
**Solution**:
- Verify color constants in `slave/src/LEDStates.h`
- Check `getInterpolatedColor()` function
- Ensure RGB order matches your LED strip type

### State Detection Issues

**Problem**: Wrong state displayed
**Solution**:
- Check state priority order in `updateLEDDisplay()`
- Verify RPM/Speed thresholds in `LEDStates.h`
- Use Serial Monitor to debug incoming values

---

## 📊 State Comparison Table

| State | Condition | Color | Animation | Purpose |
|-------|-----------|-------|-----------|---------|
| ⚪ Idle | Speed=0, RPM≤800 | White | Pepper inward | Stationary idle |
| 🟠 Stall | Speed>0, RPM 0-1999 | Orange | Inverted bar | Stall warning |
| 🔵 MPG | RPM 2000-2500 | Blue→Green | Progress bar | Best fuel economy |
| 🟢 Thermal | RPM 2500-4000 | Green→Yellow | Progress bar | Best efficiency |
| 🟡 High | RPM 4000-4500 | Yellow | Progress bar | Approaching shift |
| 🔴 Shift | RPM 4501-7199 | Red+Flash | Flash gap | Shift urgently |
| 🛑 Limit | RPM 7200+ | Solid Red | Static | Rev limiter |
| ❌ Error | CAN Failure | Red | Pepper inward | Comms error |

---

## 🚀 Future Enhancements

Potential improvements to consider:

1. **Night Mode**: Lower brightness for nighttime driving
2. **Custom Colors**: User-configurable efficiency zone colors
3. **Multi-car Profiles**: Different thresholds for turbo vs NA engines
4. **Ambient Light Sensor**: Auto-adjust brightness based on conditions
5. **Lap Timer Integration**: Flash patterns for personal best times

---

## 📝 Version History

- **v4.0**: Efficiency Gradient System (Current)
  - ⚪ Idle: White pepper animation (Speed=0, RPM≤800)
  - 🟠 Stall Danger: Inverted orange bar (Speed>0, RPM 0-1999)
  - 🔵🟢🟡 Efficiency Gradient: Smooth blue→green→yellow (RPM 2000-4500)
  - 🔴 Shift Danger: Red bar + flashing center (RPM 4501-7199)
  - 🛑 Rev Limit: Solid red (RPM 7200+)
  - ❌ Error: Red pepper animation (CAN failure)
- **v3.0**: Seven-state mirrored progress bar system
- **v2.1**: Three-state system
- **v2.0**: Two-state system (gradient + flash)
- **v1.0**: Original single gradient implementation

---

## 📧 Support

If you encounter issues:

1. Check this documentation first
2. Review `slave/src/main.cpp` for logic
3. Verify constants in `slave/src/LEDStates.h`
4. Use Serial Monitor to debug values

---

**🌈 Drive efficiently - keep those LEDs blue and green for best MPG!**
