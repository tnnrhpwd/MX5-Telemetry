# ESP32-S3 Round Display Module

## Overview

This module provides a visual dashboard for the MX5 Telemetry system using an ESP32-S3 with a 1.85" round touch screen display.

### Hardware Specifications
- **MCU**: ESP32-S3 (Dual-core Xtensa LX7, 240MHz)
- **Display**: 1.85" Round IPS LCD (360×360 pixels)
- **Touch**: Capacitive touch screen
- **Audio**: 8Ω 2W Speaker with onboard Audio Codec
- **Features**: Offline Speech Recognition, AI Speech Interaction
- **Flash**: 16MB
- **PSRAM**: 8MB (OPI)

## Quick Start

### 1. Clone Firmware Between Two Modules

If you have two ESP32-S3 modules and want to clone firmware from one to another:

```powershell
cd display

# Step 1: Connect Module A (source) and backup its firmware
.\scripts\backup_firmware.ps1

# Step 2: Disconnect Module A, connect Module B (target)
# Step 3: Flash the backup to Module B
.\scripts\flash_firmware.ps1
```

See [WORKFLOW.md](WORKFLOW.md) for detailed instructions.

### 2. Backup Firmware from a Device

Back up firmware from any connected ESP32-S3:

```powershell
# Run the backup script
.\scripts\backup_firmware.ps1

# Or specify options manually
.\scripts\backup_firmware.ps1 -ComPort COM5 -FlashSize 16MB
```

The script will:
1. Auto-detect the ESP32-S3 device
2. Read device information (chip ID, flash info)
3. Create a complete flash backup
4. Save individual partitions (bootloader, partition table, app)

Backups are saved to `display/firmware_backup/<timestamp>/`

### 3. Flash Firmware to a Device

#### Flash a Backup
```powershell
# Interactive mode - will list available backups
.\scripts\flash_firmware.ps1

# Or specify the backup file directly
.\scripts\flash_firmware.ps1 -FirmwarePath "firmware_backup\2025-12-06_10-30-00\flash_backup_full.bin"
```

#### Flash Custom Development Build
```powershell
# Build and flash in one step
pio run --target upload

# Or use the flash script
.\scripts\flash_firmware.ps1 -Development
```

#### Erase Flash (Clean Slate)
```powershell
.\scripts\flash_firmware.ps1 -EraseFlash
```

### 4. Quick Actions Menu

For an interactive menu with all common tasks:

```powershell
.\scripts\quick_actions.ps1
```

## Project Structure

```
display/
├── platformio.ini          # PlatformIO configuration
├── partitions_custom.csv   # Custom partition table
├── src/
│   └── main.cpp           # Main application code
├── lib/                   # Local libraries
├── scripts/
│   ├── backup_firmware.ps1    # Backup firmware from device
│   ├── flash_firmware.ps1     # Flash firmware to device
│   ├── compare_firmware.ps1   # Compare two firmware files
│   └── quick_actions.ps1      # Interactive menu
└── firmware_backup/       # Backed up firmware files
```

## Display Driver

The code is configured for a GC9A01-based round display with FT5x06 touch controller. Pin configuration in `main.cpp`:

| Function | Pin |
|----------|-----|
| SPI SCK  | 12  |
| SPI MOSI | 11  |
| LCD DC   | 8   |
| LCD CS   | 10  |
| LCD RST  | 14  |
| Backlight| 45  |
| Touch SDA| 4   |
| Touch SCL| 5   |
| Touch INT| 3   |

> **Note**: Adjust these pins based on your specific board variant!

## Integration with MX5 Telemetry

The display module can connect to the main telemetry system via:

1. **WiFi**: Connect to the master Arduino via ESP8266/ESP32 bridge
2. **BLE**: Bluetooth Low Energy for wireless data
3. **CAN Bus**: Direct connection to vehicle CAN (requires MCP2515 module)
4. **Serial**: UART connection to master Arduino

### Telemetry Data Display

The gauge UI shows:
- **RPM**: Color-coded arc gauge (green → yellow → red)
- **Speed**: Digital readout
- **Gear**: Current gear indicator
- **Status**: Connection status

## Development Tips

### Adjusting for Your Board

Different ESP32-S3 round display boards may have different pin configurations. To find your board's pins:

1. Check your board's documentation/schematic
2. Look for silkscreen markings on the PCB
3. Common variants:
   - Waveshare ESP32-S3-Touch-LCD-1.28
   - LilyGO T-Display-S3
   - Generic "ESP32-S3 1.85 inch Round"

### Debug Output

Enable verbose debug output in `platformio.ini`:

```ini
build_flags = 
    -DCORE_DEBUG_LEVEL=5
```

### Serial Monitor

```powershell
pio device monitor -b 115200
```

## Troubleshooting

### Device Not Detected

1. Install USB drivers:
   - CP210x: [Silicon Labs](https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers)
   - CH340: [WCH](http://www.wch-ic.com/downloads/CH341SER_ZIP.html)

2. Try different USB cables (some are charge-only)

3. Hold BOOT button while connecting

### Upload Fails

1. Put device in download mode:
   - Hold BOOT button
   - Press RESET button
   - Release RESET, then BOOT

2. Reduce upload speed in `platformio.ini`:
   ```ini
   upload_speed = 460800
   ```

### Display Not Working

1. Check pin configuration matches your board
2. Try different SPI speeds
3. Verify power supply (some displays need 3.3V, others 5V)

## Resources

- [LovyanGFX Library](https://github.com/lovyan03/LovyanGFX)
- [LVGL Documentation](https://docs.lvgl.io/8.3/)
- [ESP32-S3 Datasheet](https://www.espressif.com/sites/default/files/documentation/esp32-s3_datasheet_en.pdf)
- [esptool Documentation](https://docs.espressif.com/projects/esptool/en/latest/)
