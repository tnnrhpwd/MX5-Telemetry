# 🚀 Quick Build Guide

This guide shows how to build and upload firmware to both Arduino boards.

## Prerequisites

- **PlatformIO IDE** installed in VS Code
- **Two Arduino Nano boards** connected via USB
- USB drivers installed (CH340/CH341 for clones, FTDI for official)

## Build Environments

| Environment | Purpose | Source Directory | COM Port Example |
|-------------|---------|------------------|------------------|
| `nano_atmega328` | Master (Logger) | `src/` | COM3 |
| `led_slave` | Slave (LED Controller) | `src_led_slave/` | COM4 |

## Method 1: VS Code PlatformIO Extension (Recommended)

### Step 1: Open Project
1. Open VS Code
2. File → Open Folder → Select `MX5-Telemetry`
3. Wait for PlatformIO to initialize

### Step 2: Build Master Arduino

1. Open PlatformIO sidebar (alien icon on left)
2. Expand **Project Tasks**
3. Expand **nano_atmega328**
4. Click **General → Build**

**Expected output:**
```
Building .pio\build\nano_atmega328\firmware.elf
Checking size .pio\build\nano_atmega328\firmware.elf
Advanced Memory Usage is available via "PlatformIO Home > Project Inspect"
RAM:   [====      ]  54.2% (used 1112 bytes from 2048 bytes)
Flash: [========= ]  79.8% (used 24568 bytes from 30720 bytes)
```

### Step 3: Build Slave Arduino

1. In PlatformIO sidebar
2. Expand **led_slave**
3. Click **General → Build**

**Expected output:**
```
Building .pio\build\led_slave\firmware.elf
Checking size .pio\build\led_slave\firmware.elf
RAM:   [==        ]  25.0% (used 512 bytes from 2048 bytes)
Flash: [==        ]  27.4% (used 8420 bytes from 30720 bytes)
```

### Step 4: Upload Master Arduino

1. Connect Master Arduino to USB (note COM port in Device Manager)
2. In PlatformIO sidebar → **nano_atmega328** → **General → Upload**
3. Or open `platformio.ini` and click **Upload** button

**Troubleshooting:**
- If upload fails with "port not found", manually specify in `platformio.ini`:
  ```ini
  [env:nano_atmega328]
  upload_port = COM3  ; Change to your actual port
  ```

### Step 5: Upload Slave Arduino

1. Connect Slave Arduino to different USB port
2. In PlatformIO sidebar → **led_slave** → **General → Upload**

**Troubleshooting:**
- Specify different port in `platformio.ini`:
  ```ini
  [env:led_slave]
  upload_port = COM4  ; Change to your actual port
  ```

## Method 2: Command Line (Advanced)

### Find COM Ports

**Windows:**
```powershell
Get-WmiObject Win32_SerialPort | Select-Object DeviceID, Description
```

**Output example:**
```
DeviceID Description
-------- -----------
COM3     USB-SERIAL CH340 (COM3)
COM4     USB-SERIAL CH340 (COM4)
```

### Build Commands

```powershell
# Navigate to project
cd "c:\Users\tanne\Documents\Github\MX5-Telemetry"

# Build master
platformio run -e nano_atmega328

# Build slave
platformio run -e led_slave

# Upload master to COM3
platformio run -e nano_atmega328 --target upload --upload-port COM3

# Upload slave to COM4
platformio run -e led_slave --target upload --upload-port COM4
```

## Method 3: Batch Scripts (Windows)

### Create Upload Scripts

**upload_master.bat:**
```batch
@echo off
echo Uploading Master Arduino (nano_atmega328)...
platformio run -e nano_atmega328 --target upload --upload-port COM3
pause
```

**upload_slave.bat:**
```batch
@echo off
echo Uploading Slave Arduino (led_slave)...
platformio run -e led_slave --target upload --upload-port COM4
pause
```

**Note:** Update COM ports to match your system.

## Verification

### Test Master Arduino

1. Upload master firmware
2. Open Serial Monitor: PlatformIO → **nano_atmega328** → **Monitor**
3. Set baud rate: **115200**
4. Expected output:
   ```
   MX5v3
   CAN: OK
   LED: Slave on TX
   GPS: Ready (disabled until START)
   SD: OK
   OK
   ```

### Test Slave Arduino

1. Upload slave firmware
2. Open Serial Monitor: PlatformIO → **led_slave** → **Monitor**
3. Set baud rate: **9600**
4. Send test commands:
   ```
   RPM:1000
   RPM:3000
   RPM:5000
   CLR
   ```
5. LED strip should respond to each command

### Test Master → Slave Communication

1. Wire Master TX (D1) to Slave RX (D0)
2. Connect shared ground between both Arduinos
3. Power both Arduinos
4. Open Serial Monitor on Master (115200 baud)
5. Type: `START`
6. Rev engine (or use simulator)
7. LED strip should show RPM feedback

## Common Issues

### ❌ Upload Failed: "Device not found"

**Solution:**
1. Check USB cable (must be data cable, not charge-only)
2. Install CH340 drivers: https://sparks.gogo.co.nz/ch340.html
3. Check Device Manager → Ports (COM & LPT)
4. Try different USB port

### ❌ Build Error: "Library not found"

**Solution:**
```powershell
# Update PlatformIO libraries
platformio lib update

# Or install specific library
platformio lib install "Adafruit NeoPixel"
```

### ❌ Upload Error: "Permission denied"

**Solution:**
1. Close Arduino IDE (conflicts with PlatformIO)
2. Close any Serial Monitor windows
3. Unplug/replug Arduino
4. Try upload again

### ❌ Wrong Arduino Uploaded

**Solution:**
Always verify which COM port before uploading:
```powershell
# Check current connections
mode
```

Label your Arduinos physically (Master/Slave) to avoid confusion.

## Configuration Changes

### Change LED Count

**File:** `src_slave/main.cpp`

```cpp
#define LED_COUNT           20      // Change to your LED count
```

### Enable/Disable Features

**File:** `lib/Config/config.h`

```cpp
#define ENABLE_CAN_BUS      1    // 1 = enable, 0 = disable
#define ENABLE_GPS          1
#define ENABLE_LOGGING      1
#define ENABLE_LED_STRIP    0    // Use 0 for slave configuration
#define ENABLE_LED_SLAVE    1    // Use 1 for slave configuration
```

### Adjust RPM Thresholds

**Master:** `lib/Config/LEDStates.h`

**Slave:** `src_led_slave/main.cpp`

```cpp
#define STATE_3_RPM_MIN         2501
#define STATE_3_RPM_MAX         4500
#define STATE_4_RPM_MIN         4501    // Shift warning starts here
#define STATE_5_RPM_MIN         7200    // Rev limit
```

## Clean Build (Reset)

If you encounter strange build errors:

```powershell
# Clean all build artifacts
platformio run --target clean

# Clean specific environment
platformio run -e nano_atmega328 --target clean
platformio run -e led_slave --target clean

# Rebuild
platformio run
```

## Serial Monitor Shortcuts

| Task | Shortcut |
|------|----------|
| Open Serial Monitor | `Ctrl+Alt+S` |
| Close Serial Monitor | `Ctrl+C` (in terminal) |
| Clear Terminal | `Ctrl+K` |

## Next Steps

After successful uploads:

1. ✅ **Master uploaded** → Test with `START` command
2. ✅ **Slave uploaded** → Test with `RPM:3000` commands
3. ✅ **Both wired** → Test full system with engine data

See [docs/DUAL_ARDUINO_SETUP.md](DUAL_ARDUINO_SETUP.md) for complete wiring guide.

---

**Need help?** Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) or open an issue on GitHub.
