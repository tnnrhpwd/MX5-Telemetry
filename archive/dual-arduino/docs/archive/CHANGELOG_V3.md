# MX5-Telemetry v3.0 - USB Command Interface Edition

**MAJOR ARCHITECTURAL REDESIGN** - GoPro Control Removed, Full USB Laptop Control Added

## 🎯 What Changed

### Removed Features
- ❌ GoPro power control (PowerManager module deleted)
- ❌ Standby mode detection
- ❌ MOSFET circuit requirements

### New Features
- ✅ **USB Command Interface** - Control everything from laptop via serial
- ✅ **State Machine** - IDLE, RUNNING, PAUSED, LIVE_MONITOR, DUMPING
- ✅ **Live Data Streaming** - Real-time telemetry view without SD logging
- ✅ **System Diagnostics** - STATUS command shows all module health
- ✅ **Hot-plug Support** - Connect laptop anytime during operation

## 📡 USB Commands

| Command | Function |
|---------|----------|
| `START` | Begin logging + LED display |
| `PAUSE` | Stop logging + LED display |
| `RESUME` | Continue logging + LED display |
| `LIVE` | Real-time data stream (no SD logging) |
| `STOP` | Exit live mode, return to PAUSE |
| `DUMP` | Transfer current log file |
| `DUMP filename` | Transfer specific file |
| `LIST` | Show all files on SD card |
| `STATUS` | Display system diagnostics |
| `HELP` | Show command reference |

## 🔄 Typical Workflow

### Track Day Usage
```
1. Power on system (auto-enters IDLE state)
2. Type: START
   → Logging begins, LEDs active
3. Drive session...
4. Type: PAUSE
   → Logging stops, LEDs off
5. Type: DUMP
   → Download data to laptop
6. Type: RESUME
   → Continue next session
```

### Live Monitoring
```
1. Type: LIVE
   → Real-time CSV stream to terminal
   → LEDs still active for RPM feedback
   → SD logging PAUSED
2. Monitor data in real-time...
3. Type: STOP or PAUSE
   → Exit live mode
4. Type: RESUME
   → Return to normal logging
```

## 📊 Live Data Stream Format

When in LIVE mode, data streams in CSV format:
```
Timestamp,Date,Time,Lat,Lon,Alt,Sats,RPM,Speed,Throttle,Coolant
125430,20251120,143052,34.052235,-118.243683,125.4,8,3450,65,45,88
125630,20251120,143052,34.052236,-118.243684,125.5,8,3520,66,46,88
...
```

You can capture this with terminal logging or pipe to analysis tools.

## 🔧 System States

| State | Logging | LEDs | Description |
|-------|---------|------|-------------|
| **IDLE** | ❌ | ❌ | Waiting for START command |
| **RUNNING** | ✅ | ✅ | Normal operation (5Hz SD + LEDs) |
| **PAUSED** | ❌ | ❌ | Stopped, awaiting commands |
| **LIVE_MONITOR** | ❌ | ✅ | Real-time stream (no SD) |
| **DUMPING** | ❌ | ❌ | Transferring files |

## 💾 Memory Usage

- **Flash:** 98.8% (30,356 / 30,720 bytes) - 364 bytes free
- **RAM:** 67.3% (1,379 / 2,048 bytes)

## 🏗️ Architecture Changes

### Deleted Modules
- `lib/PowerManager/` - GoPro control removed

### New Modules
- `lib/CommandHandler/` - USB command processing and state machine

### Modified Modules
- `lib/DataLogger/` - Added `streamData()` for live monitoring
- `lib/Config/config.h` - Removed GOPRO_PIN, added command constants
- `src/main.cpp` - Complete rewrite with state-based control

## 🔌 Hardware Simplification

**No longer needed:**
- IRF540N MOSFET
- GoPro power wiring

**Still required:**
- Arduino Nano V3.0
- MCP2515 CAN Controller
- WS2812B LED Strip (30 LEDs)
- Neo-6M GPS Module
- MicroSD Card Module
- LM2596 Buck Converter

## 📝 Usage Notes

1. **Connect laptop anytime** - USB connection doesn't interrupt logging
2. **Serial baud rate: 115200** - Set in your terminal
3. **Commands are case-insensitive** - `start` = `START`
4. **Default state: IDLE** - Must send START to begin logging
5. **LEDs clear on PAUSE** - Visual confirmation of state

## 🚀 Quick Start

1. Upload firmware to Arduino Nano
2. Connect to vehicle OBD-II port
3. Open Serial Monitor (115200 baud)
4. Type `HELP` to see commands
5. Type `START` to begin logging
6. Drive and collect data
7. Type `PAUSE` when finished
8. Type `DUMP` to retrieve data

## ⚠️ Breaking Changes from v2.x

- GoPro control removed entirely
- System starts in IDLE (not auto-running)
- Must send START command to begin logging
- No automatic standby mode
- PowerManager API no longer available

## 🔄 Migration from v2.x

If upgrading from v2.x:
1. Remove MOSFET circuit
2. Upload new firmware
3. Change workflow to use START/PAUSE commands
4. Remove any code that references PowerManager

---

**Version:** 3.0.0  
**Date:** 2025-11-20  
**Build:** nano_release (optimized)
