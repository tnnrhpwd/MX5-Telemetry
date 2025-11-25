# GPS Data Troubleshooting Guide

## Understanding GPS Data in Logs

### Expected Behavior Without Satellite Fix

When the GPS module doesn't have a satellite lock (indoors, blocked view, cold start), you'll see:

```csv
Time,Date,GPSTime,Lat,Lon,Speed,Alt,Sat,RPM
53214,100663703,123342683,0.000000,0.000000,0.00,0.0,15,8192
```

**What each value means:**

- **Time**: `53214` ✓ CORRECT - Milliseconds from `millis()`, always works
- **Date**: `100663703` ✗ INVALID - Should be YYYYMMDD format (e.g., 20251125)
- **GPSTime**: `123342683` ✗ INVALID - Should be HHMMSSCC format (e.g., 15253042 = 15:25:30.42)
- **Lat/Lon**: `0.000000` ✗ NO FIX - Actual coordinates will be -90 to +90 / -180 to +180
- **Speed**: `0.00` ✗ NO FIX - Speed in knots (will show movement when tracking)
- **Alt**: `0.0` ✗ NO FIX - Altitude in meters
- **Sat**: `15` ⚠️ SUSPICIOUS - Should be 0-12 satellites; 15 suggests garbage data
- **RPM**: `8192` ✓ CORRECT - From CAN bus (depends on engine state)

### Getting Valid GPS Data

**Requirements:**
1. **Outdoor location** - GPS needs clear view of sky
2. **Cold start time** - Allow 30-60 seconds for first satellite lock
3. **Minimum satellites** - Need 4+ for full 3D fix with altitude
4. **Movement** - Speed/heading require motion (walking or driving)

**How to verify GPS is working:**

1. Upload firmware and connect to Arduino
2. Take device **outdoors** with clear sky view
3. Send `S` (START) command via Python tool
4. Wait 30-60 seconds for satellite acquisition
5. Send `X` (STOP) command
6. Dump the log file with `D` command
7. Check for valid coordinates:
   - Valid latitude: -90.0 to +90.0 (e.g., 33.123456)
   - Valid longitude: -180.0 to +180.0 (e.g., -117.654321)
   - Valid date: 20251125 format
   - Valid time: 15253042 format (15:25:30.42)
   - Satellites: 3-12 (4+ for good fix)

### Common GPS Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| All zeros | No satellite fix | Move outdoors, wait longer |
| Garbage numbers (15 sats) | Invalid TinyGPS data | Normal without fix |
| Coordinates never change | Stationary | Move/drive to see updates |
| Date shows 100663703 | No GPS time sync | Wait for satellite lock |
| Speed always 0.00 | Not moving or no fix | Drive and retest |

## Single-Letter Command Protocol

**Why single letters?**

The Arduino uses SoftwareSerial for GPS which shares interrupts with hardware Serial (USB). Longer commands can be corrupted during GPS updates.

**Correct Usage:**

✅ **Use Python Tool Buttons** - Always use the Arduino Actions tool
- Buttons send single letters (`S`, `P`, `X`, `T`, etc.)
- Most reliable method

✅ **Manual Single Letters** - If typing in serial monitor:
- `S` = START
- `P` = PAUSE  
- `X` = STOP
- `L` = LIVE
- `T` = STATUS
- `I` = LIST
- `D` = DUMP
- `?` = HELP

❌ **Avoid Full Words** - Don't type these manually:
- `STATUS` → corrupts to `? STATU` or `STAT`
- `START` → corrupts to `? STA` or `TART`
- `PAUSE` → corrupts to `PAUS` or `? PA`

### Example from Your Log

```
[15:09:48] → STATUS        ← User typed full word
[15:09:48] ? STATU         ← GPS interference corrupted it
[15:09:54] ⚠️ TIMEOUT      ← Arduino didn't recognize command
```

**Solution:** Use the Python tool's "📊 STATUS" button which sends just `T`

## Testing Checklist

### Indoor Testing (No GPS Fix Expected)
- [x] CAN bus RPM data logs correctly
- [x] Single-letter commands work reliably
- [x] SD card writes without corruption
- [x] CSV format includes GPS columns
- [ ] GPS shows zeros (expected - no satellites indoors)

### Outdoor Testing (GPS Fix Required)
- [ ] Take device outdoors with clear sky view
- [ ] Start logging with `S` command
- [ ] Wait 60 seconds minimum
- [ ] Walk or drive 100+ meters
- [ ] Stop logging with `X` command
- [ ] Verify GPS data shows:
  - [ ] Valid coordinates (not 0.000000)
  - [ ] Valid date (YYYYMMDD format)
  - [ ] Valid time (HHMMSSCC format)
  - [ ] 4+ satellites locked
  - [ ] Speed changes with movement
  - [ ] Altitude shows reasonable value

## Debugging GPS Hardware

If GPS never gets a fix outdoors:

1. **Check wiring:**
   - GPS RX → Arduino pin 9
   - GPS TX → Arduino pin 8
   - GPS VCC → 3.3V or 5V (check module specs)
   - GPS GND → Arduino GND

2. **Check GPS LED:**
   - Blinking every 1-2 seconds = searching for satellites
   - Blinking every 15 seconds = GPS fix acquired

3. **Test with U-Center software:**
   - Connect GPS directly to PC via USB-Serial adapter
   - Use u-blox U-Center to verify satellite acquisition
   - Confirms hardware is functional

4. **Check antenna:**
   - Module needs ceramic patch antenna
   - Metal case/enclosure can block signal
   - Try moving to different outdoor location

## Expected Performance

**Satellite Acquisition:**
- Cold start (no prior data): 30-60 seconds
- Warm start (recent data): 10-30 seconds  
- Hot start (current data): 1-10 seconds

**Accuracy:**
- Horizontal: 2.5m CEP (circular error probable)
- Altitude: 3-5m typical
- Speed: 0.1 knots typical
- Time: 30ns RMS (extremely accurate)

**Update Rate:**
- Default: 1Hz (once per second)
- Can configure up to 5Hz (requires more processing)
- Current logging: 200ms interval captures 5 GPS readings per log entry
