# Arduino Actions - USB Command Interface

Interactive GUI tool for controlling the MX5-Telemetry Arduino system via USB connection.

## Overview

Arduino Actions provides an easy-to-use graphical interface for:
- **Controlling Arduino** - Send commands (START, PAUSE, RESUME, LIVE, STOP)
- **Live Data Monitoring** - View real-time telemetry data streaming
- **Data Management** - Dump log files from SD card to computer
- **System Diagnostics** - Check Arduino status, GPS, CAN bus, SD card health

No need to use terminal commands or remember syntax - everything is accessible through intuitive buttons and displays.

## Features

### 🔌 Auto-Detection
- Automatically finds Arduino devices on USB ports
- Shows port names and descriptions
- Auto-refresh every 5 seconds when disconnected

### 📡 Command Control
- **START** - Begin logging and LED display
- **PAUSE** - Stop logging and LED display  
- **RESUME** - Continue logging and LED display
- **LIVE** - Real-time data streaming (no SD logging)
- **STOP** - Exit live mode, return to pause
- **STATUS** - Show system diagnostics
- **HELP** - Show command reference

### 💾 Data Management
- **LIST FILES** - View all log files on SD card
- **DUMP CURRENT LOG** - Download the active log file
- **DUMP SELECTED** - Download a specific log file
- Saves dumps as timestamped CSV files

### 📊 Live Console
- Real-time output from Arduino
- Timestamped messages
- Auto-scroll to latest
- Clear button for cleanup

### 🚦 Visual Status
- Connection indicator (🟢 Connected / ⚫ Disconnected)
- System state display (IDLE / RUNNING / PAUSED / LIVE)
- Colored console output

## Requirements

### Hardware
- Arduino Nano V3.0 with MX5-Telemetry firmware installed
- USB-C cable for connection to computer

### Software
- Python 3.7 or higher
- Required packages:
  ```
  pyserial
  ```

## Installation

1. **Install Python** (if not already installed)
   - Download from [python.org](https://www.python.org/downloads/)
   - Make sure to check "Add Python to PATH" during installation

2. **Install Required Packages**
   ```bash
   pip install pyserial
   ```

3. **Navigate to Tool Directory**
   ```bash
   cd tools/Arduino_Actions
   ```

## Usage

### Quick Start

**Windows:**
```bash
python arduino_actions.py
```

Or use the convenience script:
```bash
.\run_arduino_actions.bat
```

**PowerShell:**
```powershell
.\run_arduino_actions.ps1
```

### Step-by-Step Guide

1. **Connect Arduino**
   - Plug Arduino into computer via USB-C
   - Wait for drivers to install (first time only)

2. **Launch Application**
   - Run `arduino_actions.py` or use convenience scripts
   - Application window will open

3. **Select Port**
   - Choose Arduino port from dropdown
   - Click "🔄 Refresh" if port doesn't appear
   - Click "🔌 Connect"

4. **Send Commands**
   - Use command buttons to control Arduino
   - Watch console for responses
   - Check system state indicator

5. **Dump Data (Optional)**
   - Click "📋 LIST FILES" to see available logs
   - Click "💾 DUMP CURRENT LOG" or select file and "📥 DUMP SELECTED"
   - Choose save location
   - Data saves as timestamped CSV file

## Command Reference

| Command | Description | Button Color |
|---------|-------------|--------------|
| **START** | Begin data logging and LED display | 🟢 Green |
| **PAUSE** | Stop logging and LEDs, enter idle state | 🟠 Orange |
| **RESUME** | Resume logging and LEDs from pause | 🔵 Blue |
| **LIVE** | Stream real-time data (no SD logging) | 🟣 Purple |
| **STOP** | Exit live mode, return to paused state | 🔴 Red |
| **STATUS** | Request system diagnostics | ⚫ Gray |
| **HELP** | Show available commands | ⚫ Gray |

## Data Management

### Listing Files
Click **LIST FILES** to query all files on the SD card. Files appear in the list box below the command buttons.

### Dumping Logs
1. **Current Log**: Click **DUMP CURRENT LOG** to download the active log file
2. **Specific File**: 
   - Click **LIST FILES** first
   - Select a file from the list
   - Click **DUMP SELECTED**

Dumps are saved as CSV files with format: `arduino_dump_YYYYMMDD_HHMMSS.csv`

### CSV Format
Log files contain comma-separated values with columns:
- Timestamp (ms)
- GPS Latitude
- GPS Longitude  
- GPS Speed
- GPS Satellites
- Engine RPM
- Vehicle Speed
- CAN Error Count
- Log Status

## Troubleshooting

### Arduino Not Detected
- **Check USB Cable** - Ensure USB-C cable is data-capable (not charge-only)
- **Install Drivers** - Windows may need CH340/CH341 drivers for Arduino clones
- **Refresh Ports** - Click "🔄 Refresh" button to rescan
- **Try Different Port** - Use a different USB port on computer

### Connection Fails
- **Close Other Programs** - Arduino IDE, serial monitors must be closed
- **Reset Arduino** - Unplug and replug USB cable
- **Check Baud Rate** - Default is 115200 (matches Arduino firmware)

### Commands Not Working
- **Check Connection** - Status should show "🟢 Connected"
- **Wait for Arduino** - Give 2 seconds after connecting for Arduino to initialize
- **Request Status** - Click "📊 STATUS" to verify Arduino is responding

### Dump Fails
- **Check SD Card** - Ensure SD card is inserted in Arduino
- **Verify Files** - Click "📋 LIST FILES" first
- **Write Permissions** - Ensure save folder has write permissions

### Console Output Garbled
- **Baud Rate Mismatch** - Check Arduino Serial.begin() matches 115200
- **Cable Quality** - Try a different USB cable
- **Electrical Interference** - Move away from sources of interference

## Advanced Usage

### Live Data Streaming
The **LIVE** mode streams telemetry data in real-time without writing to SD card. Useful for:
- Testing sensors
- Debugging CAN bus communication
- Monitoring GPS acquisition
- Verifying LED patterns

Press **STOP** to exit live mode and return to paused state.

### Status Diagnostics
The **STATUS** command returns system health information:
- **St**: System state (R=Running, P=Paused, L=Live, I=Idle)
- **CAN**: CAN bus initialized (Y/N)
- **RPM**: Current engine RPM
- **GPS**: GPS valid fix (Y/N)
- **Sat**: Number of GPS satellites
- **SD**: SD card initialized (Y/N)
- **LED**: LED strip active (Y/N)

Example: `St:R CAN:Y RPM:3500 GPS:Y Sat:8 SD:Y LED:Y`

## Development Notes

### Architecture
- **Main Thread**: GUI updates and user interaction
- **Background Thread**: Serial communication and data reading
- **Thread-Safe Callbacks**: Data passed to main thread via `root.after()`

### Serial Protocol
- **Baud Rate**: 115200
- **Line Ending**: `\n` (newline)
- **Commands**: ASCII text, case-insensitive
- **Responses**: Plain text or status strings

### Extending Functionality
To add new commands:
1. Add button in `create_ui()`
2. Create command handler method
3. Call `self.send_command("YOUR_COMMAND")`
4. Handle response in `_process_data()` if needed

## See Also

- [LED Simulator](../LED_Simulator/README.md) - Test LED patterns before uploading
- [Quick Start Guide](../../docs/QUICK_START.md) - Getting started with MX5-Telemetry
- [Wiring Guide](../../docs/WIRING_GUIDE.md) - Hardware connection diagrams

## License

MIT License - See [LICENSE](../../LICENSE) for details

## Support

For issues, feature requests, or questions:
- Open an issue on GitHub
- Check existing documentation in `/docs`
- Review Arduino serial commands in `CommandHandler.cpp`
