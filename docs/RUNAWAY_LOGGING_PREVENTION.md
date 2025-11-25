# Preventing Gigabyte CSV Files (Runaway Logging Protection)

## What Happened

You left the Arduino logging outdoors for over an hour, which created a **gigabyte-sized corrupted CSV file**. Here's why:

### The Math
- Logging rate: **5 Hz** (5 times per second)
- Per hour: 5 × 3,600 = **18,000 lines**
- Per line: ~80 bytes
- **Per hour: ~1.44 MB**
- **Over 1 hour: Can exceed 1 GB** if something goes wrong

### Why It Got Corrupted

Large CSV files can corrupt if:
1. SD card runs out of space mid-write
2. Power disconnected during write
3. Filesystem limit exceeded (FAT32 has 4GB file limit)
4. Too many writes exhaust SD card's write endurance

## Solutions (Choose One)

### Option 1: Manual Stop (RECOMMENDED - Works Now)

**Always manually stop logging after your test:**

```bash
# Outdoor test procedure:
1. Power on Arduino with battery → auto-starts logging
2. Wait 2-3 minutes for GPS fix
3. Walk around to generate data
4. **IMPORTANT: Come back and power off within 5-10 minutes**
5. Connect to laptop and download logs
```

**Safe test durations:**
- GPS fix test: **2-5 minutes** (600-1,500 lines, ~50-120 KB)
- Track day session: **20-30 minutes** (6,000-9,000 lines, ~500-700 KB)
- Never leave unattended for **> 1 hour**

### Option 2: Enable Auto-Stop Feature (+200 bytes flash)

**Requires memory optimization** - Currently 4 bytes over limit.

To enable auto-stop protection:

```cpp
// In lib/Config/config.h:
#define AUTO_STOP_ENABLED    true   // Change from false to true
#define AUTO_STOP_DURATION   600000  // 10 minutes (adjust as needed)
#define MAX_LOG_LINES        10000   // 10,000 lines max (~800KB)
```

**But first you must free 204 bytes:**

1. **Disable LED strip** (saves ~500 bytes):
   ```cpp
   #define ENABLE_LED_STRIP    false
   ```

2. **Or remove unused features** in CommandHandler.cpp:
   - Remove `handleResume()` function (not used)
   - Shorten error messages further
   - Remove `printSystemStatus()` function in main.cpp

### Option 3: Set Shorter Auto-Start Duration

Instead of unlimited logging, limit outdoor test duration:

```cpp
// In config.h (when AUTO_STOP_ENABLED = true):
#define AUTO_STOP_DURATION   300000   // 5 minutes
#define AUTO_STOP_DURATION   600000   // 10 minutes (default)
#define AUTO_STOP_DURATION   1800000  // 30 minutes
```

### Option 4: Use Laptop for Long Tests

For sessions > 10 minutes, keep laptop connected:

```bash
1. Connect Arduino to laptop via USB
2. Arduino doesn't auto-start (USB detected)
3. Open Arduino Actions Python tool
4. Click START when ready
5. Monitor in real-time
6. Click STOP when done
7. Data saved safely
```

## Recovering from Corrupted File

Your current gigabyte CSV is likely unrecoverable, but try:

### Method 1: Delete via Arduino

```bash
1. Connect Arduino to laptop
2. Open Python tool
3. Click LIST to see files
4. Note the corrupted filename (LOG_XXXX.CSV)
5. Use DUMP to try downloading (will likely fail)
6. Manually connect SD card to PC with card reader
7. Delete the corrupted file directly
8. Reformat SD card as FAT32 if needed
```

### Method 2: Direct SD Card Access

```bash
1. Power off Arduino
2. Remove SD card
3. Insert into PC card reader
4. Delete LOG_XXXX.CSV file
5. Check SD card for errors (right-click → Properties → Tools → Check)
6. Reinsert into Arduino
```

### Method 3: Reformat SD Card

**WARNING: Deletes ALL data**

```bash
1. Backup any good log files first
2. Format SD card as FAT32
3. Ensure allocation unit size = 4096 bytes (4KB)
4. Reinsert into Arduino
```

## Prevention Checklist

For your next outdoor test:

- [ ] Set a **phone alarm** for 5 minutes
- [ ] Come back to power off Arduino before alarm
- [ ] Don't leave logging unattended > 10 minutes
- [ ] Check SD card free space before test (need > 10 MB free)
- [ ] Use smaller SD card (2-8 GB) to prevent hour-long runaway logging

## Expected File Sizes

**Normal outdoor GPS test:**
- 2 minutes: ~600 lines, ~50 KB ✓
- 5 minutes: ~1,500 lines, ~120 KB ✓
- 10 minutes: ~3,000 lines, ~240 KB ✓
- 30 minutes: ~9,000 lines, ~720 KB ✓
- 1 hour: ~18,000 lines, ~1.4 MB ⚠️
- > 1 hour: Gigabytes ✗ RUNAWAY

## Current System Status

**Auto-stop feature:** ❌ Disabled (insufficient flash memory)
**Manual stop required:** ✅ Yes - always power off within 10 minutes
**Max safe test duration:** ⏱️ 10-15 minutes recommended

**To enable auto-stop:**
1. Set `ENABLE_LED_STRIP = false` in config.h (frees 500 bytes)
2. Set `AUTO_STOP_ENABLED = true` in config.h
3. Rebuild and upload firmware
4. System will automatically stop after 10 minutes or 10,000 lines

## Summary

**Immediate action for next test:**
1. Power on Arduino outdoors
2. Wait 2-3 minutes
3. Walk around
4. **Power off within 5-10 minutes**
5. Download logs
6. Check file size < 1 MB

**Long-term solution:**
- Enable auto-stop by disabling LED strip first
- Or always use laptop for monitoring
- Or set phone timer to remind you to stop

Your system works perfectly - just needs manual monitoring until auto-stop is enabled! 🎯
