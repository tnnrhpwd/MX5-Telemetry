# Quick Start: Outdoor GPS Testing (Auto-Start Mode)

## What Changed?

Your Arduino now **automatically starts logging** when powered without USB connection. This lets you test GPS outdoors without a laptop.

## Simple 5-Step Test

### 1. Upload Firmware (One Time)
```bash
# Connect Arduino to laptop via USB
# Upload the latest firmware
pio run --target upload
```

### 2. Go Outside
```bash
# Disconnect Arduino from laptop
# Connect to USB power bank instead
# Find open area with clear sky view
```

### 3. Power On
```bash
# Plug Arduino into power bank
# Logging starts automatically in ~5 seconds
# LED strip glows (if enabled) = logging active
```

### 4. Wait & Move
```bash
# Stand still for 60 seconds (GPS acquiring satellites)
# Walk around for 2-3 minutes to generate position data
# Device logs every 200ms to SD card
```

### 5. Download Data
```bash
# Go back inside
# Connect Arduino to laptop via USB
# Open Arduino Actions Python tool
# Click LIST to see files
# Click DUMP to download newest log
# Open CSV and verify GPS coordinates are real (not zeros)
```

## What to Expect

**Good GPS Data (Outdoors):**
```csv
Time,Date,GPSTime,Lat,Lon,Speed,Alt,Sat,RPM
5430,20251125,15304512,33.123456,-117.654321,0.00,125.3,8,800
```
- Date: 20251125 ✓
- Lat/Lon: Real coordinates ✓
- Sat: 4-12 satellites ✓

**Bad GPS Data (Indoors):**
```csv
Time,Date,GPSTime,Lat,Lon,Speed,Alt,Sat,RPM
5430,100663703,123342683,0.000000,0.000000,0.00,0.0,15,800
```
- Date: 100663703 ✗ (garbage)
- Lat/Lon: 0.000000 ✗ (no fix)
- Sat: 15 ✗ (invalid)

## Key Points

✅ **Auto-start ONLY happens without USB** - If you connect to laptop, it waits for commands normally

✅ **Need clear outdoor sky view** - GPS doesn't work indoors, even upstairs

✅ **Wait 60 seconds minimum** - GPS needs time to acquire satellites on cold start

✅ **Move around to test** - Walk or drive 100+ meters to see position/speed changes

✅ **Safe data logging** - Even if power disconnected suddenly, data is saved to SD

## Troubleshooting

**Q: Arduino doesn't auto-start?**
- Check SD card is inserted and formatted (FAT32)
- Try different USB cable (some "charge only" cables work better)
- Re-upload firmware

**Q: GPS still shows zeros outdoors?**
- Wait longer (up to 5 minutes for first fix)
- Check GPS LED is blinking
- Move to more open location (away from trees/buildings)

**Q: How do I stop auto-start logging?**
- Just disconnect power (unplug from power bank)
- Or connect to laptop USB (system boots normally and waits for commands)

## Normal Operation (With Laptop)

When connected via USB, behavior is **unchanged**:
- Boot messages appear in serial monitor
- System waits for commands
- Use Python tool buttons (S, P, X, T, etc.)
- No auto-start occurs

## Battery Life

With 10,000 mAh power bank:
- ~50 hours continuous logging
- More than enough for any outdoor test

For details, see `docs/AUTO_START_FEATURE.md`
