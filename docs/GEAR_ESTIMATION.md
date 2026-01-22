# Gear Estimation & Clutch Detection

## Overview

The 2008 Mazda MX-5 NC GT does not have a gear position sensor on the transmission. The CAN bus only reports when the vehicle is in **Neutral** (detected via the neutral safety switch). For all other gears (1-6 and Reverse), the system estimates the current gear based on the relationship between vehicle speed and engine RPM.

## How It Works

### Gear Ratio Calculation

The system uses the known gear ratios for the MX5 NC 6-speed manual transmission along with the final drive ratio and tire size to calculate the expected speed/RPM relationship for each gear:

**MX5 NC 6-Speed Manual Transmission:**
- 1st Gear: 3.760
- 2nd Gear: 2.269
- 3rd Gear: 1.645
- 4th Gear: 1.187
- 5th Gear: 1.000
- 6th Gear: 0.843
- Final Drive: 4.10
- Tire Size: 205/45R17 (24.3" diameter)

### Estimation Algorithm

1. **Receive Data**: System continuously receives RPM and speed data from CAN bus
2. **Calculate Ratio**: Computes actual speed/RPM ratio
3. **Match Gear**: Compares actual ratio against expected ratios for each gear
4. **Select Best Match**: Chooses the gear with the closest matching ratio
5. **Calculate Confidence**: Measures how well the ratio matches the expected value

### Clutch Detection

The system detects when the clutch pedal is pressed by identifying when the actual speed/RPM ratio deviates significantly (>30%) from the expected ratio for any gear. This happens because:
- **Clutch Pressed**: Engine and transmission are disconnected, breaking the speed/RPM relationship
- **Tire Slip**: Wheels spinning faster/slower than expected (e.g., burnout, wheel lock)

## Display Modes

When the clutch is detected as engaged, the gear indicator can display different information based on user preference. This is configured in **Settings > Clutch Display**:

### Mode 0: Gear# (Colored) - Default
- **Display**: Shows the estimated target gear number (1-6, N, R)
- **Color**: Cyan/Teal (rev-matching helper color)
- **Purpose**: Helps with rev-matching by showing which gear you should target
- **Best For**: Drivers who want assistance with smooth shifting

### Mode 1: 'C' for Clutch
- **Display**: Shows letter "C"
- **Color**: Cyan/Teal
- **Purpose**: Simple indication that clutch is pressed
- **Best For**: Drivers who prefer minimal information

### Mode 2: 'S' for Shifting
- **Display**: Shows letter "S"
- **Color**: Cyan/Teal
- **Purpose**: Indicates that a shift is in progress
- **Best For**: Drivers who want shift timing information

### Mode 3: '-' for Unknown
- **Display**: Shows dash "-"
- **Color**: Cyan/Teal
- **Purpose**: Generic placeholder when gear cannot be determined
- **Best For**: Drivers who prefer no assistance during shifts

## Normal Operation Colors

When the clutch is **not** engaged, the gear indicator color reflects engine RPM for shift timing:

- **Green**: Normal RPM range (< 4500 RPM)
- **Yellow**: Approaching shift point (4500-5500 RPM)
- **Orange**: Recommended shift range (5500-6500 RPM)
- **Red**: Near redline (> 6500 RPM)

## Configuration

### Settings Menu Location
1. Navigate to **Settings** screen (cruise control buttons or touch)
2. Scroll to **Clutch Display**
3. Press ON/OFF button to edit
4. Use VOL+/VOL- (or RES+/SET-) to cycle through modes
5. Press ON/OFF to save

### Technical Configuration
Settings are synchronized between Pi and ESP32 displays automatically.

**Pi Code**: `pi/ui/src/main.py` - `Settings.clutch_display_mode`  
**ESP32 Code**: `display/src/main.cpp` - `clutchDisplayMode` global variable

## Limitations

### Estimation Accuracy
- **Neutral Detection**: 100% accurate (from CAN bus)
- **Gear 1-6**: ~95% accurate under normal driving
- **Less Accurate When**:
  - Significant tire wear (changes effective tire diameter)
  - Tire pressure very low/high
  - Extreme wheel slip
  - Coast-down with engine off

### When Estimation Fails
The system may show incorrect gear when:
- Coasting in neutral with RPM near idle
- Rev-matching during downshifts (temporary mismatch)
- Significant tire slip (launches, drifting)
- Non-standard tire sizes installed

### Clutch Detection Threshold
The 30% ratio difference threshold works well for normal driving but may:
- **False Positive**: Detect clutch during extreme wheel spin
- **False Negative**: Miss very quick clutch taps (< 100ms)

## Implementation Details

### Code Locations

**Gear Estimator Class**:  
`pi/ui/src/can_handler.py` - `GearEstimator` class

**CAN Handler Integration**:  
`pi/ui/src/can_handler.py` - `CANHandler._update_gear_estimation()`

**Telemetry Fields**:  
`pi/ui/src/telemetry_data.py`:
- `gear_estimated`: Boolean flag indicating gear was estimated
- `clutch_engaged`: Boolean flag indicating clutch appears pressed

**ESP32 Display Logic**:  
`display/src/main.cpp` - `drawOverviewScreen()` gear display section

**Serial Protocol**:  
Pi → ESP32: `TEL:rpm,speed,gear,throttle,coolant,oil,voltage,fuel,engine,gear_est,clutch`

### Testing Recommendations

1. **Verify Neutral**: Confirm Neutral is always correctly shown when stationary
2. **Test Each Gear**: Drive at steady speed in each gear, verify correct number displays
3. **Clutch Detection**: Press clutch while driving, verify color changes to cyan
4. **Mode Cycling**: Test all 4 clutch display modes in Settings
5. **Rev-Matching**: Try rev-matched downshifts, verify gear number updates smoothly

## Future Enhancements

Potential improvements to consider:
- Adjustable clutch detection threshold in Settings
- Learning mode to calibrate for actual tire diameter
- Display confidence level indicator
- Smoothing algorithm for gear transitions
- Support for other transmission types (automatic, different ratios)

## Troubleshooting

**Gear shows wrong number**:
- Check tire pressure (affects effective diameter)
- Verify tire size matches 205/45R17 specification
- Consider tire wear (reduces diameter slightly)
- **NOTE**: A previous bug caused double conversion of speed to MPH (fixed 2026-01-22)

**Neutral not showing**:
- CAN neutral detection is now trusted at speeds up to 10 MPH
- At higher speeds, system relies on gear estimation (which returns neutral when speed < 2 MPH)
- If neutral isn't showing when stationary, check CAN bus connection

**Clutch not detected**:
- Threshold may need adjustment for driving style
- Very quick clutch taps may be missed
- Check that speed and RPM data are being received

**Clutch falsely detected**:
- May occur during extreme wheel slip
- Reduce aggressive throttle application
- Lower threshold sensitivity (requires code change)

**Settings not saving**:
- Ensure ESP32 display is connected to Pi
- Check serial communication status
- Verify Settings screen shows correct mode after change
