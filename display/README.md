# ESP32-S3 Round Display Module

## Overview

This module provides a visual dashboard for the MX5 Telemetry system using the **Waveshare ESP32-S3-Touch-LCD-1.85** round touch screen display.

### Installation Location

**The ESP32-S3 round display is mounted in the stock oil gauge hole.** The 1.85" form factor fits perfectly in the original gauge opening, providing a clean OEM-like appearance.

### Gear Indicator Typography

The large gear character (`R`, `N`, `C`, `S`, `1`–`6`, `-`) is set in a real
typeface, not in the bitmap text fonts and not in hand-drawn strokes.

[`gear_font.h`](src/ui_core/gear_font.h) holds 8-bit coverage masks that were
rasterised from **Arimo** 700 — the SIL Open Font License design that is
metric-compatible with Arial. Arial itself is Monotype-proprietary and cannot be
embedded, so Arimo supplies the same letterforms and the same widths.

- One glyph is a cropped alpha map plus its position inside a 46×66 cell; there is
  no font engine, no outline data and no stroke maths on the device.
- The whole cell — ink *and* background — is composited into one buffer and pushed
  with a single panel transaction, which also erases the previous gear cleanly.
- `drawLargeGear()` looks the character up in `GEAR_GLYPHS`; anything unknown
  falls back to the dash.

Regenerating or changing the typeface:

```bash
python tools/fonts/make_gear_font.py --font Arimo-var.ttf --preview sheet.png
```

Get `Arimo[wght].ttf` from <https://github.com/google/fonts/tree/main/ofl/arimo>.
The generator re-derives the em size from the cap height, condenses horizontally
just enough for the widest letter to fit the cell, and fails loudly if any glyph
would be clipped. `Arimo-OFL.txt` must ship with the firmware — it is the
licence for the embedded letterforms.

The focused simulator (`tools/simulators/native`) renders the real code, so glyph
changes can be checked on the desktop.

## G-Force Display Behavior

The G-Force screen visualizes car dynamics using the QMI8658 IMU (gyroscope + accelerometer). The display is calibrated for the ESP32 mounted **vertically** in the oil gauge hole with the screen facing the driver and USB port pointing down.

### Mounting Orientation

```
     ┌─────────────────┐
     │    (roof/up)    │
     │                 │
     │   ┌─────────┐   │
     │   │  ESP32  │   │  ← Screen faces DRIVER
     │   │ Display │   │  ← Top points UP (towards roof)  
     │   │         │   │  ← USB port points DOWN
     │   └─────────┘   │
     │                 │
     │   (floor/down)  │
     └─────────────────┘
         (Oil Gauge)
```

**When stationary and level**, the ball should be:
- **Centered** on screen (pitch = 0°, roll = 0°)
- **Normal size** (14px radius, since forward acceleration = 0)
- **Green color** (neutral acceleration)

### Circle Position = Car Orientation (Tilt)

The ball position shows the car's orientation using **gyroscope integration** to track pitch and roll angles:

| Car Movement | Circle Movement |
|--------------|-----------------|
| Nose pitches **DOWN** (braking, downhill) | Circle moves **UP** (top of screen) |
| Nose pitches **UP** (acceleration, uphill) | Circle moves **DOWN** (bottom of screen) |
| Car rolls **LEFT** (left turn, left camber) | Circle moves **LEFT** |
| Car rolls **RIGHT** (right turn, right camber) | Circle moves **RIGHT** |

- The three reference rings represent 2.5°, 5°, and 10° of tilt
- When level, the ball stays centered

### Circle Size = Forward Acceleration

The ball size represents **forward acceleration only** (not total G magnitude), with gravity subtracted to show pure dynamics:

| Condition | Ball Size |
|-----------|-----------|
| **Zero acceleration** (coasting) | Normal size (14px radius) |
| **Acceleration** (speeding up) | Ball **GROWS** (up to 24px) |
| **Deceleration** (braking) | Ball **SHRINKS** (down to 6px) |

### Color Coding

| Color | Meaning |
|-------|---------|
| 🔴 **Red** | Hard acceleration (>0.3 G) |
| 🟠 **Orange** | Light acceleration (>0.1 G) |
| 🟢 **Green** | Neutral/coasting |
| 🟡 **Yellow** | Light braking (<-0.1 G) |
| 🔵 **Cyan** | Hard braking (<-0.3 G) |

### Info Box Display

The bottom info box shows:
- **Pitch**: Current pitch angle in degrees (positive = nose up)
- **Roll**: Current roll angle in degrees (positive = roll right)
- **Fwd**: Forward acceleration in G (positive = accelerating)

### Technical Implementation

```
Mounting & Axis Mapping:
  - ESP32 is VERTICAL: screen faces driver, USB port down, top points up
  - IMU Y-axis → Car Z-axis (both point up)
  - IMU Z-axis → Car -Y-axis (Z points back towards driver, Y forward)
  - IMU X-axis → Car X-axis (both point right towards passenger)

Orientation Tracking (Position):
  - Gyroscope data (°/sec) is integrated over time to get pitch/roll in degrees
  - Accelerometer provides drift correction when total G ≈ 1 (not accelerating)
  - Complementary filter: 98% gyro + 2% accelerometer
  - Position mapping: pitch controls Y, roll controls X

Linear Acceleration (Ball Size):
  - Gravity vector calculated from current pitch/roll orientation
  - Gravity subtracted from accelerometer to get pure linear acceleration
  - Forward axis (linearAccelY) controls ball size
  - When stationary at any tilt angle, linearAccelY ≈ 0 → normal ball size
```

---

### Data Flow

- **Receives from Pi (Serial)**: All CAN telemetry data, steering wheel button events, settings sync
- **Sends to Pi (Serial)**: BLE TPMS data (4 tire sensors), G-force data (QMI8658 IMU)
- **No CAN module** - All vehicle data comes through the Pi hub

### Hardware: Waveshare ESP32-S3-Touch-LCD-1.85

| Component | Specification |
|-----------|---------------|
| **MCU** | ESP32-S3 (Dual-core Xtensa LX7, 240MHz) |
| **Display** | 1.85" Round IPS LCD, 360×360 pixels, ST77916 controller (QSPI) |
| **Touch** | CST816 Capacitive touch controller |
| **IMU** | QMI8658 (Accelerometer + Gyroscope) → G-force data sent to Pi |
| **BLE** | Built-in Bluetooth 5.0 → TPMS sensor data sent to Pi |
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
