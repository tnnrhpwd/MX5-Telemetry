# ESP32-S3 Display Module Workflow

## 🏎️ Architecture Context

The ESP32-S3 1.85" round display is part of the MX5-Telemetry system:

| Device | Location | Role |
|--------|----------|------|
| **Raspberry Pi 4B** | Console/trunk | CAN hub, settings cache, HDMI to head unit |
| **ESP32-S3 Round Display** | **Stock oil gauge hole** | Visual dashboard, BLE TPMS, G-force |
| **Arduino Nano** | Behind gauge cluster | LED strip controller |

The ESP32-S3 displays:
- RPM gauge, speedometer
- TPMS (tire pressure from BLE sensors)
- G-force meter (from onboard QMI8658 IMU)
- Settings menu (navigated via steering wheel controls sent from Pi)

---

## 🔧 Development Workflow

This guide covers the firmware development and deployment workflow for the ESP32-S3 display module.

### Quick Start (Normal Development)

```powershell
# Build firmware
pio run -d display

# Upload to ESP32-S3
pio run -d display --target upload

# Monitor serial output
pio device monitor -b 115200
```

### Build + Upload + Monitor (Combined)

```powershell
pio run -d display --target upload; pio device monitor -b 115200
```

---

## 📦 Firmware Backup & Recovery

This section is for users who need to:
1. **Backup** firmware from a working device
2. **Clone** firmware to a new device
3. **Recover** a bricked device

### Step 1: Backup Firmware

Connect the ESP32-S3 to your computer:

```powershell
cd display
.\scripts\backup_firmware.ps1
```

This creates a complete backup in `display/firmware_backup/<timestamp>/` containing:
- `flash_backup_full.bin` - Complete 16MB flash image
- `bootloader.bin` - Bootloader partition
- `partition_table.bin` - Partition layout
- `application.bin` - Main application
- `device_info.txt` - Chip ID and MAC address
- `flash_info.txt` - Flash manufacturer info

### Step 2: Reverse Engineer & Redevelop the Source Code

Since you're working with a binary backup and likely don't have the original source code, you'll need to reverse engineer the firmware to understand how it works, then rebuild equivalent source code that you can modify and maintain.

#### 2.1 Analyze the Binary Structure

First, examine what's in the firmware:

```powershell
# View the partition table
python -m esptool --port COM5 read_flash 0x8000 0x1000 partition_table.bin
python -m gen_esp32part partition_table.bin

# Or use ESP-IDF's partition tool
partitiontool.py partition_table.bin
```

#### 2.2 Extract and Identify Components

```powershell
# The application binary starts at 0x10000
# Use a hex editor to look for strings
strings firmware_backup/*/application.bin > strings_dump.txt
```

Look for clues in the strings dump:
- Library names (e.g., "LovyanGFX", "LVGL", "TFT_eSPI")
- Error messages and debug prints
- WiFi SSIDs, URLs, or configuration values
- Version strings

#### 2.3 Identify the Display Driver & Libraries

Common ESP32-S3 round display libraries leave signatures:

| Library | String Signatures |
|---------|-------------------|
| LovyanGFX | `LGFX`, `Panel_GC9A01`, `lgfx::` |
| TFT_eSPI | `TFT_eSPI`, `TFT_WIDTH` |
| LVGL | `lv_`, `LVGL`, `lv_obj` |
| Arduino_GFX | `Arduino_GFX`, `GFX_` |
| Adafruit_GFX | `Adafruit_GFX` |

#### 2.4 Use Ghidra or IDA for Deeper Analysis

For serious reverse engineering:

1. **Install Ghidra** (free, from NSA): https://ghidra-sre.org/
2. **Add ESP32 support**: Install the [Xtensa processor module](https://github.com/Ebiroll/ghidra-xtensa)
3. **Load the binary**:
   - Create new project
   - Import `application.bin`
   - Select "Xtensa:LE:32:default" as processor
   - Set base address to `0x40080000` (typical ESP32-S3 app location)

4. **Analyze**:
   - Look for `app_main` or `setup`/`loop` functions
   - Identify library calls by their patterns
   - Map out the display initialization sequence

#### 2.5 Reconstruct the Source Code

Based on your analysis, rebuild `display/src/main.cpp`:

```cpp
// Start with the template in this repo
// display/src/main.cpp

// Then modify based on what you found:
// 1. Match the display driver (GC9A01, ST7789, etc.)
// 2. Match the pin configuration
// 3. Match the UI layout (LVGL widgets, colors, fonts)
// 4. Match any communication protocols (WiFi, BLE, Serial)
```

#### 2.6 Iterative Comparison

After each change, compare your build to the original:

```powershell
# Build your version
pio run -d display

# Compare binaries
.\scripts\compare_firmware.ps1
```

The comparison tool will show which memory regions differ. Focus on:
- **App partition differences** = Your code logic differs
- **NVS differences** = Configuration/calibration data (expected to differ)
- **SPIFFS/LittleFS differences** = Asset files (fonts, images)

#### 2.7 Extract Assets (Fonts, Images)

If the firmware includes custom assets:

```powershell
# Dump the SPIFFS/LittleFS partition (typically at 0x610000)
python -m esptool --port COM5 read_flash 0x610000 0x1F0000 spiffs.bin

# Mount and extract (using mkspiffs or mklittlefs)
mkspiffs -u extracted_files -b 4096 -p 256 -s 0x1F0000 spiffs.bin
```

#### 2.8 Match Compiler Settings

For near-identical binaries, match the build configuration:

```ini
; In platformio.ini, experiment with:
build_flags = 
    -Os              ; or -O2, -O3
    -DNDEBUG         ; Release mode
    -DCORE_DEBUG_LEVEL=0
```

Different optimization levels produce very different binaries even from identical source.

#### 2.9 Document What You Learn

Create a file `display/docs/REVERSE_ENGINEERING_NOTES.md` to track:
- Identified functions and their addresses
- Library versions detected
- Pin mappings discovered
- UI element descriptions
- Communication protocols found

### Step 3: Flash the Rebuilt Firmware to Module B

Once you've reconstructed and customized the source code, build and flash it to your target device:

```powershell
# Connect Module B (your target device)

# Build the project
pio run -d display

# Upload to Module B
pio run -d display --target upload

# Monitor serial output to verify it works
pio device monitor -b 115200
```

#### Verify Your Build Against the Original

To confirm your source code produces equivalent functionality:

```powershell
# Backup the firmware you just uploaded
.\scripts\backup_firmware.ps1

# Compare it to the original backup
.\scripts\compare_firmware.ps1
```

If there are differences, review the analysis report and iterate on your source code.

---

## 🔧 Common Tasks

| Task | Command |
|------|---------|
| Backup from device | `.\scripts\backup_firmware.ps1` |
| Flash backup to device | `.\scripts\flash_firmware.ps1` |
| Build custom firmware | `pio run -d display` |
| Upload custom firmware | `pio run -d display --target upload` |
| Serial monitor | `pio device monitor -b 115200` |
| Interactive menu | `.\scripts\quick_actions.ps1` |

---

## 🔌 Connecting a Module

1. **USB Connection**
   - Use a data-capable USB cable (not charge-only)
   - Install drivers if needed (CP210x or CH340)

2. **Download Mode** (if upload fails)
   - Hold BOOT button
   - Press and release RESET
   - Release BOOT button
   - Device is now in download mode

3. **Finding the COM Port**
   - Windows: Device Manager → Ports (COM & LPT)
   - Or run: `pio device list`

---

## 🎨 Customizing the Display (For Developers)

### Pin Configuration
Edit `display/include/display_config.h` for your specific board's pinout.

### UI Customization
The main UI is built with LVGL in `display/src/main.cpp`. Modify:
- `createGaugeUI()` - Layout and widgets
- `updateGaugeColor()` - RPM color thresholds
- Display rotation and brightness

### Adding Features
- WiFi OTA updates
- BLE connectivity
- Audio alerts
- Touch gestures
- Multiple display modes

