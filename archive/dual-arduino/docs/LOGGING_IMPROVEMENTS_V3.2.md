# Data Logging Improvements v3.2.0

## Overview
Enhanced telemetry logging system with improved data quality, diagnostics, and metadata tracking based on analysis of real-world log data.

## Implementation Date
November 26, 2025

## Key Improvements

### 1. Enhanced GPS Data Quality Indicators
**New Fields:**
- `GPS_Fix` - Fix type indicator (0=no fix, 1=GPS fix, 2=DGPS fix)
- `HDOP` - Horizontal Dilution of Precision (×100, lower is better)
  - Values < 200: Excellent
  - Values 200-500: Good
  - Values 500-1000: Moderate
  - Values > 1000: Poor
  - Value -1: Invalid/Unknown
- `Heading` - GPS course heading in degrees (0-360)

**Benefits:**
- Quickly identify GPS accuracy issues
- Filter out low-quality position data in post-processing
- Understand when GPS was acquiring vs. locked

### 2. Enhanced CSV Format
**New Column Structure:**
```
SysTime_ms,Date,GPSTime,GPS_Fix,Lat,Lon,Speed_GPS,Alt,Sat,HDOP,Heading,
RPM,Speed_CAN,Throttle,Load,Coolant,Timing,CAN_Status
```

**Added Fields:**
- `SysTime_ms` - System uptime in milliseconds (replaces "Time")
- `GPS_Fix` - GPS fix quality indicator
- `HDOP` - Horizontal dilution of precision
- `Heading` - GPS course/heading
- `Speed_CAN` - Vehicle speed from CAN bus
- `Throttle` - Throttle position (%)
- `Load` - Calculated engine load (%)
- `Coolant` - Coolant temperature (°C)
- `Timing` - Ignition timing advance (degrees)
- `CAN_Status` - CAN bus connection status (0=OK, 1=Errors, 2=Not Initialized)

### 3. Data Validation & Status Codes
**Invalid Data Indicators:**
- `-1` - Data unavailable/invalid (used for speeds, HDOP, throttle, etc.)
- `-99` - Temperature/timing data unavailable
- `0` - Valid zero value OR no GPS fix (context-dependent)

**CAN Status Codes:**
- `0` - CAN bus operating normally
- `1` - CAN bus operational but with errors
- `2` - CAN bus not initialized

**Benefits:**
- Distinguish between "sensor reads zero" vs. "sensor not working"
- Identify when hardware modules fail during logging
- Enable better data filtering in post-processing

### 4. Metadata Headers
Each log file now includes a comprehensive header:
```
# MX5-Telemetry Data Log
# Firmware Version: 3.2.0
# Build Date: Nov 26 2025 14:30:00
# Log Start Date: 2025-11-26
# Log Start Time: 17:09:35
# Log Interval: 200ms
# --- Data Start ---
```

**Benefits:**
- Identify firmware version for troubleshooting
- Know exact start time of logging session
- Understand data collection parameters
- Correlate logs with GPS timestamps

### 5. Session Summary Footer
At end of logging session:
```
# --- Log End ---
# Total Records: 1247
# Write Errors: 0
# Duration: 249 seconds
```

**Benefits:**
- Verify log completeness
- Identify SD card write issues
- Calculate actual vs. expected record count

### 6. Enhanced Diagnostic Tracking
**New Internal Metrics:**
- `writeErrorCount` - Total failed SD card writes
- `recordsWritten` - Total successful records
- `logStartTime` - Session start timestamp

**Access Methods:**
- `getWriteErrorCount()` - Retrieve write error count
- `getRecordsWritten()` - Retrieve total records written

**Benefits:**
- Monitor SD card health
- Detect buffer overflow or timing issues
- Validate data integrity

## Code Changes

### Modified Files
1. **lib/Config/config.h**
   - Added `FIRMWARE_VERSION`, `BUILD_DATE`, `BUILD_TIME` constants

2. **lib/GPSHandler/GPSHandler.h/.cpp**
   - Added `fixType`, `hdop`, `course` fields
   - Added `getFixType()`, `getHDOP()`, `getCourse()` accessors
   - Enhanced `update()` to capture GPS quality metrics

3. **lib/DataLogger/DataLogger.h/.cpp**
   - Added `writeErrorCount`, `recordsWritten`, `logStartTime` tracking
   - Added `writeMetadataHeader()` method
   - Enhanced CSV header with 18 columns (was 9)
   - Updated `logData()` with validation and status codes
   - Enhanced `finishLogging()` to write session summary
   - Added `getWriteErrorCount()` and `getRecordsWritten()` accessors

## Comparison: Old vs New Format

### Old Format (9 columns)
```csv
Time,Date,GPSTime,Lat,Lon,Speed,Alt,Sat,RPM
10987,0,0,0.000000,0.000000,0.00,0.0,0,0
```

### New Format (18 columns)
```csv
SysTime_ms,Date,GPSTime,GPS_Fix,Lat,Lon,Speed_GPS,Alt,Sat,HDOP,Heading,RPM,Speed_CAN,Throttle,Load,Coolant,Timing,CAN_Status
10987,0,0,0,0.000000,0.000000,-1,-1,0,-1,-1,-1,-1,-1,-1,-99,-99,2
```

**Key Differences:**
- Status codes distinguish "no data" (-1) from "zero value" (0)
- CAN_Status=2 indicates CAN bus not initialized
- HDOP=-1 indicates GPS quality unknown
- Additional CAN bus parameters available for analysis

## Analysis Example: Original Dump Issues

### Issue: GPS Not Acquiring Position
**Old Format:** Can't determine why
```csv
Time,Date,GPSTime,Lat,Lon,Speed,Alt,Sat,RPM
11820,502,24309,0.000000,0.000000,0.00,0.0,0,0
```

**New Format:** Clear diagnosis
```csv
SysTime_ms,Date,GPSTime,GPS_Fix,Lat,Lon,Speed_GPS,Alt,Sat,HDOP,Heading,...
11820,502,24309,0,0.0,0.0,-1,-1,0,9999,-1,...
```
- `GPS_Fix=0` → No GPS fix acquired
- `Sat=0` → No satellites visible
- `HDOP=9999` → GPS quality indeterminate
- **Diagnosis:** GPS antenna not connected or indoor testing

### Issue: When Did GPS Lock?
**New Format:** Timestamp visible
```csv
14854,502,24312,0,0.0,0.0,-1,-1,3,9999,-1,...  # 3 sats, no fix
15054,502,24312,1,0.0,0.0,-1,-1,3,750,-1,...   # Fix acquired, HDOP improving
```
- Can identify exact moment GPS locked
- Track HDOP improvement over time

### Issue: No RPM Data
**Old Format:** Shows 0 (ambiguous)
**New Format:** Shows -1 with CAN_Status=2
- Clear indicator CAN bus not initialized
- Distinguish from engine actually at 0 RPM (idle)

## Backward Compatibility

### Breaking Changes
⚠️ **Column count increased from 9 to 18** - existing parsing scripts will need updates

### Migration Guide
**Old parsing code:**
```python
headers = ['Time','Date','GPSTime','Lat','Lon','Speed','Alt','Sat','RPM']
```

**New parsing code:**
```python
headers = ['SysTime_ms','Date','GPSTime','GPS_Fix','Lat','Lon','Speed_GPS',
           'Alt','Sat','HDOP','Heading','RPM','Speed_CAN','Throttle',
           'Load','Coolant','Timing','CAN_Status']
```

**Handling -1 values:**
```python
# Replace -1 with NaN for analysis
df = df.replace(-1, np.nan)

# Filter valid GPS data
valid_gps = df[df['GPS_Fix'] > 0]

# Filter valid CAN data
valid_can = df[df['CAN_Status'] == 0]
```

## Memory Impact
- Flash: ~1.2KB increase (metadata strings, additional logic)
- RAM: ~20 bytes increase (new tracking variables)
- SD Write: ~60% larger per record (9 cols → 18 cols)

## Testing Recommendations
1. **Verify GPS Quality Tracking**
   - Test indoor (should show GPS_Fix=0, HDOP=9999)
   - Test outdoor until lock (watch HDOP decrease)
   - Verify heading updates while moving

2. **Verify CAN Status Tracking**
   - Disconnect CAN bus (should show CAN_Status=2, all -1/-99)
   - Connect with errors (should show CAN_Status=1)
   - Normal operation (should show CAN_Status=0)

3. **Verify Metadata & Summary**
   - Check log headers include firmware version
   - Verify session summary appears after STOP command
   - Confirm write error count tracks SD issues

## Future Enhancements
Potential additions for next version:
- Free memory tracking
- Loop timing metrics (detect performance issues)
- Trip statistics (max RPM, max speed, distance traveled)
- Acceleration calculations (derived from speed)
- Event markers (engine start/stop detection)
- MAF rate, fuel trim, O2 voltage logging

## References
- Based on analysis of `arduino_dump_20251126_170935.csv`
- TinyGPS++ HDOP documentation: https://github.com/mikalhart/TinyGPSPlus
- OBD-II PID reference: https://en.wikipedia.org/wiki/OBD-II_PIDs
