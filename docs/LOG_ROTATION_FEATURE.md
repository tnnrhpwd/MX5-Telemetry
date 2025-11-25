# Log Rotation Feature - Automatic File Creation

## What's New

Your Arduino now **automatically creates a new log file every 10 minutes** instead of continuously logging to one gigabyte file! This prevents the runaway logging issue you experienced.

## How It Works

### Automatic Log Rotation

**During logging:**
1. Arduino creates first log file on START: `LOG_0001.CSV`
2. Logs data normally for 10 minutes
3. After 10 minutes elapsed:
   - Closes current log file
   - Creates new log file: `LOG_0002.CSV`
   - Continues logging seamlessly
4. Process repeats every 10 minutes

**Result:** Multiple manageable files instead of one giant corrupted file!

### Example Session

```
Outdoor test - 35 minutes total:

00:00 - START → Creates LOG_0001.CSV
00:00 - 10:00 → Logging to LOG_0001.CSV (~240 KB)
10:00 → Rotation! Creates LOG_0002.CSV
10:00 - 20:00 → Logging to LOG_0002.CSV (~240 KB)
20:00 → Rotation! Creates LOG_0003.CSV
20:00 - 30:00 → Logging to LOG_0003.CSV (~240 KB)
30:00 → Rotation! Creates LOG_0004.CSV
30:00 - 35:00 → Logging to LOG_0004.CSV (~120 KB)
35:00 - STOP → All files saved

Result: 4 manageable CSV files, ~840 KB total
```

## Configuration

### Change Rotation Interval

Edit `lib/Config/config.h`:

```cpp
#define LOG_ROTATION_INTERVAL 600000  // Current: 10 minutes

// Common values:
#define LOG_ROTATION_INTERVAL 300000   // 5 minutes
#define LOG_ROTATION_INTERVAL 600000   // 10 minutes (default)
#define LOG_ROTATION_INTERVAL 900000   // 15 minutes
#define LOG_ROTATION_INTERVAL 1800000  // 30 minutes
#define LOG_ROTATION_INTERVAL 3600000  // 1 hour
```

### Disable Log Rotation

If you want single continuous file (not recommended for long sessions):

```cpp
#define LOG_ROTATION_ENABLED false
```

## GPS-Based Filenames (Optional)

Currently disabled due to memory constraints (costs 340 bytes). To enable:

**Step 1: Free memory by disabling LED strip**
```cpp
// In config.h:
#define ENABLE_LED_STRIP false  // Frees ~500 bytes
```

**Step 2: Enable GPS filenames**
```cpp
#define GPS_FILENAMES_ENABLED true
```

**Step 3: Rebuild and upload**
```bash
pio run --target upload
```

**Result:** Files named with GPS datetime!
- `1125_1530.CSV` = November 25, 3:30 PM
- `1125_1540.CSV` = November 25, 3:40 PM (after rotation)
- `1125_1550.CSV` = November 25, 3:50 PM (after rotation)

**Without GPS fix (indoors):** Falls back to `LOG_XXXX.CSV`

## File Size Expectations

With 10-minute rotation:
- **Per file:** ~240 KB (3,000 lines @ 5Hz × 80 bytes/line)
- **1 hour session:** 6 files, ~1.4 MB total
- **Track day (2 hours):** 12 files, ~2.9 MB total
- **All day (8 hours):** 48 files, ~11.5 MB total

All easily manageable!

## Downloading Logs

### Via Arduino Actions Python Tool

**List all files:**
```
Click "LIST" → Shows all LOG_XXXX.CSV files
```

**Download each file:**
```
Click "DUMP"
Enter: LOG_0001.CSV
Wait for download
Repeat for LOG_0002.CSV, LOG_0003.CSV, etc.
```

**Combine files in Excel/Python:**
```python
# Python script to merge all logs:
import pandas as pd
import glob

files = sorted(glob.glob('arduino_dump_*.csv'))
dfs = [pd.read_csv(f) for f in files]
combined = pd.concat(dfs, ignore_index=True)
combined.to_csv('combined_session.csv', index=False)
```

### Via SD Card Reader

```
1. Power off Arduino
2. Remove SD card
3. Insert into PC card reader
4. Copy all LOG_XXXX.CSV files
5. Combine manually or with script
```

## Benefits vs. Auto-Stop

| Feature | Auto-Stop | Log Rotation |
|---------|-----------|--------------|
| Prevents giant files | ✅ Yes | ✅ Yes |
| Continues logging | ❌ No (stops completely) | ✅ Yes (seamless) |
| Multiple sessions | ❌ Single file | ✅ Multiple files |
| Memory cost | ~200 bytes | ~150 bytes |
| User action required | Power off or reconnect | None |
| Best for | Short tests (< 30 min) | Long sessions (hours) |

**Log rotation is superior** because it never stops logging!

## Testing the Feature

### Quick Test (Indoor - 2 minutes)

```bash
1. Connect Arduino to laptop
2. Open Arduino Actions Python tool
3. Click START
4. Wait 2 minutes
5. Click STOP
6. Click LIST → Should see LOG_XXXX.CSV
7. Click DUMP to download
```

### Rotation Test (Change interval for testing)

Temporarily set shorter interval:
```cpp
#define LOG_ROTATION_INTERVAL 60000  // 1 minute for testing
```

Then:
```bash
1. Upload firmware
2. Click START
3. Wait 3 minutes
4. Click STOP
5. Click LIST → Should see LOG_0001.CSV, LOG_0002.CSV, LOG_0003.CSV
6. Verify each file has ~60 seconds of data
```

Remember to change back to 600000 (10 minutes) for real use!

### Outdoor GPS Test (Full validation)

```bash
1. Power Arduino with battery bank (auto-starts)
2. Go outdoors with clear sky
3. Leave logging for 25 minutes
4. Come back, power off
5. Connect to laptop
6. LIST → Should see 3 files:
   - LOG_0001.CSV (~240 KB, 0-10 min)
   - LOG_0002.CSV (~240 KB, 10-20 min)
   - LOG_0003.CSV (~120 KB, 20-25 min)
7. DUMP each file and verify GPS coordinates valid in all
```

## Troubleshooting

### Only see one LOG file after long session?
- Check LOG_ROTATION_ENABLED = true in config.h
- Verify firmware was rebuilt and uploaded after config change
- Check SD card has free space

### Files have weird names?
- GPS filenames are disabled by default (need to disable LED strip first)
- LOGFiles named `LOG_XXXX.CSV` is expected

### How to know which file is which session?
**Option 1:** Note the TIME column (in milliseconds from boot)
- File 1: Time starts at ~0
- File 2: Time continues from where file 1 ended
- File 3: Time continues from file 2

**Option 2:** Check Date/GPSTime columns (if GPS working)
- Each file has actual datetime in each row

**Option 3:** Enable GPS filenames for automatic datetime naming

### Can I change rotation while logging?
- No, firmware must be recompiled
- Changes take effect on next START command
- Existing log files continue with old interval

## Memory Usage

**Current build:**
- Flash: 99.8% (30,656/30,720 bytes)
- RAM: 86.1% (1,764/2,048 bytes)
- Free flash: 64 bytes

**To enable GPS filenames (+340 bytes):**
- Must disable LED strip first (frees ~500 bytes)
- Then set GPS_FILENAMES_ENABLED = true

## Summary

✅ **Log rotation ENABLED** - Creates new file every 10 minutes
✅ **Auto-start WORKING** - Starts logging without USB
✅ **Prevents gigabyte files** - Max file size ~240 KB per rotation
❌ **GPS filenames DISABLED** - Uses LOG_XXXX.CSV format (enable after disabling LEDs)

**Your system now handles long outdoor sessions perfectly!** You can leave it logging for hours without worry. Each 10-minute segment is saved in a separate, manageable file. 🎯

## Quick Reference

| Duration | Files Created | Total Size | Rotation Count |
|----------|---------------|------------|----------------|
| 5 min | 1 | ~120 KB | 0 |
| 15 min | 2 | ~360 KB | 1 |
| 30 min | 3 | ~720 KB | 2 |
| 1 hour | 6 | ~1.4 MB | 5 |
| 2 hours | 12 | ~2.9 MB | 11 |

All files are small, readable, and non-corrupted! ✨
