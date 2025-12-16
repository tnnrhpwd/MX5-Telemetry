# Auto-Start Feature for Standalone GPS Testing

## Overview

The MX5-Telemetry system now automatically starts logging when powered on **without a USB connection**. This enables standalone outdoor GPS testing without requiring a laptop.

## How It Works

### Boot Behavior

**With USB Connected (Normal Operation):**
```
1. Arduino boots
2. Waits 3 seconds for USB serial connection
3. Detects USB is connected
4. Prints startup messages (MX5v3, CAN: OK, GPS: Ready, SD: OK, etc.)
5. Waits for commands (S, P, X, T, etc.) from Python tool or serial monitor
6. System remains in IDLE state until START command received
```

**Without USB Connected (Auto-Start Mode):**
```
1. Arduino boots
2. Waits 3 seconds for USB serial connection
3. Detects NO USB connected
4. Skips all Serial.println() calls (saves time)
5. Automatically calls handleStart() to begin logging
6. GPS enabled immediately
7. LED strip brightness set to medium (visual confirmation)
8. System enters RUNNING state
9. Begins logging to SD card immediately
```

## Testing GPS Outdoors Without Laptop

### Equipment Needed
- Arduino Nano with MX5-Telemetry firmware uploaded
- Portable power source:
  - USB power bank (5V, 1A minimum)
  - 12V battery with buck converter
  - Car cigarette lighter USB adapter
- SD card (FAT32 formatted)
- Neo-6M GPS module connected

### Step-by-Step Outdoor Test

#### 1. Prepare Device
```bash
# While connected to laptop:
1. Upload latest firmware with auto-start feature
2. Verify SD card is inserted and formatted (FAT32)
3. Use Python tool to send STOP command (X) to ensure clean state
4. Disconnect USB cable from Arduino
```

#### 2. Go Outdoors
```bash
1. Take Arduino + power bank outside
2. Find location with clear sky view:
   ✓ Open field, parking lot, or roof
   ✓ Minimal tree cover
   ✓ Away from tall buildings
   ✗ NOT under porch/overhang
   ✗ NOT near metal structures

3. Connect power bank to Arduino USB port
4. Arduino will:
   - Boot in ~5 seconds
   - Auto-start logging (no commands needed)
   - Enable GPS immediately
   - Start writing to SD card

5. Visual confirmation:
   - LED strip shows medium brightness (if enabled)
   - GPS module LED blinks fast (searching for satellites)
```

#### 3. Wait for GPS Lock
```bash
1. Keep device stationary for 30-60 seconds
2. GPS module LED will change blink rate when locked:
   - Fast blink (1Hz) = searching
   - Slow blink (15 seconds) = GPS fix acquired

3. After GPS locks, walk or drive around for 2-3 minutes:
   - Walk 100+ meters to generate position changes
   - Drive slowly around parking lot
   - This verifies speed and position tracking work
```

#### 4. Stop Logging
```bash
1. Disconnect power from Arduino (just unplug USB power bank)
2. Logging stops automatically on power loss
3. SD card will have new LOG_XXXX.CSV file with GPS data
```

#### 5. Download and Verify Data
```bash
# Back indoors with laptop:
1. Connect Arduino to laptop via USB
2. Arduino will boot normally (not auto-start because USB detected)
3. Open Arduino Actions Python tool
4. Click "LIST" (I) to see log files
5. Click "DUMP" (D) and select the newest LOG_XXXX.CSV file
6. Open downloaded CSV in Excel or text editor
7. Verify GPS columns show valid data:
   ✓ Lat: Real coordinates (e.g., 33.123456)
   ✓ Lon: Real coordinates (e.g., -117.654321)
   ✓ Date: 20251125 format
   ✓ GPSTime: HHMMSSCC format (e.g., 15304523)
   ✓ Sat: 4-12 satellites
   ✓ Speed: Changes as you moved
   ✓ Alt: Reasonable altitude for location
```

## Expected Results

### Sample Valid GPS Data
```csv
Time,Date,GPSTime,Lat,Lon,Speed,Alt,Sat,RPM
5430,20251125,15304512,33.123456,-117.654321,0.00,125.3,8,800
5630,20251125,15304712,33.123458,-117.654318,0.52,125.5,9,850
5830,20251125,15304912,33.123461,-117.654315,1.23,125.7,9,950
6030,20251125,15305112,33.123465,-117.654310,2.45,126.0,10,1200
```

**Column Meanings:**
- **Time**: 5430ms = 5.43 seconds from boot
- **Date**: 20251125 = November 25, 2025
- **GPSTime**: 15304512 = 15:30:45.12 (3:30 PM and 45.12 seconds)
- **Lat**: 33.123456° North
- **Lon**: -117.654321° West (Southern California example)
- **Speed**: 1.23 knots ≈ 1.4 mph ≈ 2.3 km/h (walking pace)
- **Alt**: 126.0 meters above sea level
- **Sat**: 10 satellites locked
- **RPM**: 1200 (from CAN bus, if engine running)

### Validation Checklist

✓ **Coordinates change over time** (not stuck at 0.000000)
✓ **Date in YYYYMMDD format** (not garbage like 100663703)
✓ **Time in HHMMSSCC format** (not garbage like 123342683)
✓ **4+ satellites** (not 0 or 15)
✓ **Speed increases when moving** (not stuck at 0.00)
✓ **Altitude reasonable** (e.g., 0-500m for most locations)

## Reverting to Manual Start

If you want to disable auto-start and require manual START command:

### Option 1: Modify Code
```cpp
// In src/main.cpp, find the auto-start section and comment it out:

if (usbConnected) {
    Serial.println(F("OK"));
    Serial.flush();
} else {
    // No USB connected - auto-start logging for standalone operation
    // This allows outdoor GPS testing without laptop
    // cmdHandler.handleStart();  // <-- Comment this line
    
    #if ENABLE_LED_STRIP
        // Visual indication that logging started automatically
        ledStrip.setBrightness(128);  // Medium brightness to show activity
    #endif
}
```

### Option 2: Always Use USB Power
- If Arduino is powered via USB (laptop or power bank), it will NOT auto-start
- Wait for boot messages to appear
- Send START command manually via Python tool

### Option 3: Use Debug Build
```bash
# platformio.ini already has a debug configuration
pio run -e nano_debug --target upload
# Debug builds could be configured to skip auto-start
```

## Power Consumption

**Auto-Start Mode Power Usage:**
- Arduino Nano: ~50mA idle, ~100mA active
- GPS Module: ~45mA (searching) → ~25mA (locked)
- SD Card: ~80mA (writing) → ~20mA (idle)
- **Total**: ~150-200mA continuous

**Battery Life Estimates:**
| Power Bank | Runtime |
|------------|---------|
| 5,000 mAh | 25-33 hours |
| 10,000 mAh | 50-66 hours |
| 20,000 mAh | 100-133 hours |

*Note: CAN bus and LED strip disabled for these estimates. Add ~100mA if LEDs active.*

## Troubleshooting

### Arduino Doesn't Auto-Start
**Symptoms:** No data logged when powered without USB
**Causes:**
1. USB power bank provides data lines (Arduino thinks USB connected)
2. SD card missing or not formatted (FAT32)
3. Firmware not uploaded correctly

**Solutions:**
1. Use "charging only" USB cable (no data lines)
2. Verify SD card inserted and readable
3. Re-upload firmware and verify flash size ~30,682 bytes

### GPS Still Shows Zeros Outdoors
**Symptoms:** CSV shows 0.000000 for Lat/Lon even outdoors
**Causes:**
1. Didn't wait long enough (need 30-60s minimum)
2. GPS antenna blocked or damaged
3. Poor sky view (trees, buildings nearby)

**Solutions:**
1. Wait 2-5 minutes for first fix
2. Check GPS module LED is blinking
3. Move to more open location
4. Verify GPS wiring: TX→pin8, RX→pin9, VCC→5V, GND→GND

### SD Card Full
**Symptoms:** No new files created
**Solutions:**
1. Delete old LOG_XXXX.CSV files via Python tool DUMP then manual delete
2. Reformat SD card as FAT32
3. Use larger capacity SD card (up to 32GB for FAT32)

### Can't Download Logs After Outdoor Test
**Symptoms:** LIST command shows files but DUMP fails
**Solutions:**
1. Ensure Arduino is powered via USB (not battery) when dumping
2. Close any programs that might access SD card
3. Try LIST command again to verify SD card readable
4. Worst case: Remove SD card and read directly with PC card reader

## Advanced Configuration

### Customize Auto-Start Delay

Change GPS warm-up time before logging:
```cpp
// In src/main.cpp, after handleStart() call:
if (!usbConnected) {
    delay(5000);  // Wait 5 seconds before starting to log
    cmdHandler.handleStart();
}
```

### Auto-Stop After Duration

Add timer to stop logging after set time:
```cpp
// In config.h:
#define AUTO_STOP_DURATION 600000  // 10 minutes in milliseconds

// In main loop:
if (!usbConnected && cmdHandler.isRunning()) {
    if (millis() > AUTO_STOP_DURATION) {
        cmdHandler.handleStop();
    }
}
```

### LED Indication Patterns

Current behavior:
- USB connected: LEDs off until START command
- Auto-start mode: LEDs medium brightness (128/255)

Customize in `src/main.cpp` after `handleStart()` call.

## Safety Notes

⚠️ **Do not test while driving** - Have a passenger operate the device or pull over
⚠️ **Secure device properly** - Don't let Arduino/GPS slide around in vehicle
⚠️ **Check power source** - Ensure power bank is charged before outdoor test
⚠️ **Weather protection** - GPS works in rain, but protect Arduino from water
⚠️ **Heat sensitivity** - Don't leave in direct sunlight (internal temps can exceed 85°C)

## Summary

The auto-start feature enables true standalone GPS testing:
- ✅ No laptop required outdoors
- ✅ Automatic logging begins on power-up
- ✅ GPS enabled immediately for maximum satellite acquisition time
- ✅ Works with any USB power source (battery bank, car adapter, etc.)
- ✅ Safe data logging even if device loses power suddenly
- ✅ Download logs later when convenient via Python tool

Perfect for outdoor GPS validation! 🛰️
