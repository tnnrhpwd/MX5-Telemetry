# ESP32-S3 Round Display Module

## Overview

This module provides a visual dashboard for the MX5 Telemetry system using the **Waveshare ESP32-S3-Touch-LCD-1.85** round touch screen display.

### Hardware: Waveshare ESP32-S3-Touch-LCD-1.85

| Component | Specification |
|-----------|---------------|
| **MCU** | ESP32-S3 (Dual-core Xtensa LX7, 240MHz) |
| **Display** | 1.85" Round IPS LCD, 360×360 pixels, ST77916 controller (QSPI) |
| **Touch** | CST816 Capacitive touch controller |
| **IMU** | QMI8658 (Accelerometer + Gyroscope) |
| **IO Expander** | TCA9554PWR |
| **Flash** | 16MB |
| **PSRAM** | 8MB (OPI) |
| **Connectivity** | WiFi, BLE, USB-C |

### I2C Device Addresses
- `0x15` - CST816 Touch Controller  
- `0x20` - TCA9554PWR IO Expander
- `0x51` - QMI8658 IMU

## Quick Start

### Build and Upload Firmware

```powershell
cd display

# Build the firmware
pio run

# Upload to device (auto-detect COM port)
pio run --target upload

# Or specify COM port manually
pio run --target upload --upload-port COM8
```

### Serial Monitor

```powershell
pio device monitor -b 115200
```

### Boot Mode (if upload fails)

1. **Hold BOOT button** on the device
2. **Press RESET button** (or reconnect USB)
3. **Release BOOT button**
4. Device is now in download mode - upload should work

## PlatformIO Configuration

This project requires **Arduino-ESP32 3.x** (based on ESP-IDF 5.1+) for the Waveshare ST77916 display driver APIs.

Key `platformio.ini` settings:
```ini
; pioarduino platform provides Arduino-ESP32 3.x with ESP-IDF 5.x APIs
platform = https://github.com/pioarduino/platform-espressif32/releases/download/53.03.10/platform-espressif32.zip
board = esp32-s3-devkitc-1
framework = arduino

; 16MB flash with OPI PSRAM
board_build.flash_size = 16MB
board_build.psram_type = opi

; USB CDC for serial output
build_flags = 
    -DARDUINO_USB_MODE=1
    -DARDUINO_USB_CDC_ON_BOOT=1
```

> **Important**: The standard `espressif32` platform uses Arduino-ESP32 2.x (ESP-IDF 4.x) which lacks the LCD APIs needed for the ST77916 driver. The `pioarduino` platform provides Arduino-ESP32 3.x with full ESP-IDF 5.x support.

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
