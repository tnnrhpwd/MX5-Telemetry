# Comprehensive Data Logging Implementation

## Overview
The MX5-Telemetry system has been updated to log all required telemetry data points as specified in the requirements. This document summarizes the implemented data logging capabilities.

## Data Categories

### 1. Time and Location Data (via GPS - Neo-6M)
- **Timestamp**: System milliseconds (CRITICAL for event correlation)
- **Date**: GPS date (YYYYMMDD format, UTC)
- **Time**: GPS time (HHMMSS format, UTC)
- **Latitude**: Degrees (6 decimal precision)
- **Longitude**: Degrees (6 decimal precision)
- **Altitude**: Meters (1 decimal precision)
- **GPS Speed**: km/h (2 decimal precision) - absolute ground speed
- **Satellites**: Count

### 2. Core Performance & Driver Input (via OBD-II)
- **Engine RPM**: PID 0x0C (rpm)
- **ECU Vehicle Speed**: PID 0x0D (km/h)
- **Throttle Position**: PID 0x11 (%)
- **Calculated Load**: PID 0x04 (%) - percentage of peak available torque

### 3. Engine Health & Tuning Metrics (via OBD-II)
- **Engine Coolant Temp**: PID 0x05 (°C)
- **Intake Air Temp**: PID 0x0F (°C)
- **Barometric Pressure**: PID 0x33 (kPa)
- **Ignition Timing Advance**: PID 0x0E (degrees before TDC)
- **MAF Rate**: PID 0x10 (g/s)
- **Short-Term Fuel Trim**: PID 0x06 (%)
- **Long-Term Fuel Trim**: PID 0x07 (%)
- **O2 Sensor Voltage**: PID 0x14 Bank 1 Sensor 1 (Volts)

### 4. System Status (Internal Diagnostics)
- **Log Status**: Boolean (1 = actively logging, 0 = streaming only)
- **CAN Error Count**: Count of CAN bus communication errors

## CSV File Format

### Header
```
Timestamp,Date,Time,Lat,Lon,Alt,GPS_Spd,Sats,RPM,ECU_Spd,Thr,Load,Coolant,Intake,Baro,Timing,MAF,STFT,LTFT,O2,LogStat,CANErr
```

### Column Descriptions
1. **Timestamp**: Milliseconds since Arduino startup
2. **Date**: GPS date (YYYYMMDD)
3. **Time**: GPS time (HHMMSS)
4. **Lat**: Latitude in degrees
5. **Lon**: Longitude in degrees
6. **Alt**: Altitude in meters
7. **GPS_Spd**: GPS-measured speed in km/h
8. **Sats**: Number of GPS satellites
9. **RPM**: Engine RPM
10. **ECU_Spd**: ECU-reported vehicle speed in km/h
11. **Thr**: Throttle position percentage
12. **Load**: Calculated engine load percentage
13. **Coolant**: Engine coolant temperature in °C
14. **Intake**: Intake air temperature in °C
15. **Baro**: Barometric pressure in kPa
16. **Timing**: Ignition timing advance in degrees
17. **MAF**: Mass air flow rate in g/s
18. **STFT**: Short-term fuel trim percentage
19. **LTFT**: Long-term fuel trim percentage
20. **O2**: O2 sensor voltage
21. **LogStat**: 1 if actively logging to SD, 0 if streaming only
22. **CANErr**: CAN bus error count

## Implementation Details

### PID Request Strategy
The system uses a **cyclic PID request strategy** to collect all required OBD-II data:
- Requests one PID every 100ms
- Cycles through all 12 PIDs in sequence
- Complete cycle takes 1.2 seconds
- Ensures comprehensive data collection without overwhelming the ECU

### Data Collection Rates
- **CAN Bus Reading**: 50Hz (every 20ms) - high-frequency RPM for LED display
- **GPS Updates**: 10Hz (every 100ms)
- **Data Logging**: 5Hz (every 200ms) - writes all data to SD card

### Memory Optimization
The implementation required careful memory optimization to fit within the Arduino Nano's 30KB flash limit:
- **Final flash usage**: 98.2% (30,160 / 30,720 bytes)
- **Headroom**: 560 bytes
- Optimizations included:
  - Shortened CSV header field names
  - Used `write(',')` instead of `print(F(","))` for commas
  - Reduced verbose serial output messages
  - Consolidated string literals

### Dual-Mode CAN Reading
The system maintains the dual-mode CAN strategy:
1. **Mode 1**: Direct Mazda CAN monitoring (ID 0x201) for fast RPM
2. **Mode 2**: OBD-II PID cycling for comprehensive data collection

### Excluded Data
- **Wideband A/F Ratio**: Excluded as specified (no wiring available)

## Usage

### Starting Data Logging
```
START    - Begin logging all data to SD card
```

### Live Data Streaming
```
LIVE     - Stream all data via serial (no SD logging)
```

### Viewing Logged Data
```
LIST     - List all log files on SD card
DUMP     - Transfer current log file via serial
DUMP filename.csv - Transfer specific file
```

### System Status
```
STATUS   - View system diagnostics including CAN errors
```

## Data Analysis Applications

This comprehensive dataset enables:
- **Track mapping**: GPS coordinates + altitude
- **Performance analysis**: RPM, speed, throttle, load over time
- **Tuning analysis**: Timing advance, MAF, fuel trims, O2 sensor
- **Driver behavior**: Throttle position, GPS speed vs ECU speed
- **Engine health monitoring**: Coolant temp, intake temp, barometric pressure
- **System diagnostics**: CAN error tracking, log status verification

## Notes

1. All data points are logged at 5Hz (every 200ms)
2. GPS time (UTC) is used for accurate event correlation
3. CAN error count helps diagnose physical wiring and bus issues
4. Log status field differentiates between active SD logging and live streaming
5. Empty GPS fields (,,,) indicate no GPS fix at time of logging

## Build Information

- **Compilation**: Successful
- **Flash Memory**: 30,160 bytes (98.2% of 30,720 bytes)
- **RAM Usage**: 1,416 bytes (69.1% of 2,048 bytes)
- **Platform**: Arduino Nano ATmega328P
- **Framework**: Arduino
