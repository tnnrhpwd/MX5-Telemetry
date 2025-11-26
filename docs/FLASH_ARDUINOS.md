# 🚀 FLASH YOUR ARDUINOS - Quick Start

## ✅ What You Need

- [ ] **Master Arduino Nano** (Arduino #1 - Logger)
- [ ] **Slave Arduino Nano** (Arduino #2 - LED Controller)  
- [ ] **2 USB cables** (data cables, not charging-only)
- [ ] **VS Code** with PlatformIO extension installed

---

## 📋 Step-by-Step Upload Process

### Step 1: Connect Master Arduino

1. **Plug Master Arduino** into USB port
2. **Wait 5 seconds** for drivers to load
3. **Check Device Manager** (optional):
   - Press `Win + X` → Device Manager
   - Look under "Ports (COM & LPT)"
   - Note the COM port (e.g., COM3)

### Step 2: Open Project in VS Code

1. **Open VS Code**
2. **File** → **Open Folder**
3. Select: `C:\Users\tanne\Documents\Github\MX5-Telemetry`
4. Wait for PlatformIO to initialize (bottom toolbar appears)

### Step 3: Upload Master Firmware

**Option A: Use PlatformIO Toolbar (Easiest)**

1. Look at **bottom toolbar** in VS Code
2. Find the **PlatformIO icon** (looks like alien head 👽)
3. Click **"Project Environments"** dropdown
4. Select **`nano_atmega328` (Master)**
5. Click the **Upload button** (→ arrow icon)
6. Wait for "SUCCESS" message

**Option B: Use PowerShell Script**

```powershell
.\upload_master.ps1
```

**Option C: Use Command Palette**

1. Press `Ctrl + Shift + P`
2. Type: `PlatformIO: Upload`
3. Select: `nano_atmega328`

### Step 4: Verify Master Upload

1. **Open Serial Monitor**:
   - Click "Serial Monitor" button in bottom toolbar
   - Set baud rate to **115200**
2. **Press Reset** button on Arduino
3. **Look for startup messages**:
   ```
   MX5-Telemetry Master v1.0.0
   Initializing CAN bus...
   Initializing GPS...
   Initializing SD card...
   System ready!
   ```

### Step 5: Upload Slave Firmware

1. **Disconnect Master Arduino** (unplug USB)
2. **Connect Slave Arduino** (Arduino #2)
3. **Switch environment** in VS Code:
   - Click "Project Environments" dropdown
   - Select **`led_slave` (Slave)**
4. **Upload** (click → arrow or press `Ctrl + Alt + U`)
5. **Look for startup flash**:
   - LED strip should flash **GREEN 3 times**

### Step 6: Test Slave

**Option A: Serial Monitor Test**

1. Open Serial Monitor at **9600 baud**
2. Type these commands:
   ```
   RPM:3000    (should show yellow bar)
   SPD:0       (should show white idle animation)
   ERR         (should show red error)
   CLR         (should clear LEDs)
   ```

**Option B: Connect to Master**

1. Power both Arduinos from 5V supply
2. Connect serial link: Master TX (D1) → Slave RX (D0)
3. LEDs should respond to master's RPM data automatically

---

## 🎯 Future Uploads (Game Plan)

### Daily Workflow

**Editing Master Code:**
1. Make changes in `src/` or `lib/`
2. Press `Ctrl + Alt + B` (build)
3. Connect Master Arduino
4. Press `Ctrl + Alt + U` (upload)

**Editing Slave Code:**
1. Make changes in `src_slave/main.cpp`
2. Switch to `led_slave` environment
3. Connect Slave Arduino
4. Press `Ctrl + Alt + U` (upload)

### Quick Reference

| Task | Keyboard Shortcut | Menu Location |
|------|------------------|---------------|
| Build | `Ctrl + Alt + B` | PlatformIO → Build |
| Upload | `Ctrl + Alt + U` | PlatformIO → Upload |
| Serial Monitor | `Ctrl + Alt + S` | PlatformIO → Serial Monitor |
| Clean | `Ctrl + Alt + C` | PlatformIO → Clean |

---

## 🔧 Troubleshooting

### "Upload failed" Error

**Try these in order:**

1. **Close Serial Monitor** first
2. **Press Reset** button right before upload
3. **Try different USB port**
4. **Check USB cable** (must be data cable)
5. **Install CH340 drivers** (for clone Nanos):
   - Download: https://sparks.gogo.co.nz/ch340.html

### "Port not found" Error

**Solution:**
```powershell
# Find your COM ports
Get-WmiObject Win32_SerialPort | Select-Object Name, DeviceID
```

Then update `platformio.ini`:
```ini
[env:nano_atmega328]
upload_port = COM3    # Your actual port

[env:led_slave]  
upload_port = COM4    # Your actual port
```

### "Out of memory" Error

**Solution:** Disable unused features in `lib/Config/config.h`:
```cpp
#define ENABLE_GPS          false    // Disable GPS if not needed
#define ENABLE_LOGGING      false    // Disable SD logging if testing
```

### LEDs Not Working After Upload

**Checklist:**
- [ ] LED strip connected to Slave D5 pin
- [ ] LED strip has 5V power (not from Arduino pin)
- [ ] LED strip GND connected to Arduino GND
- [ ] LED_COUNT set to 20 in `src_slave/main.cpp`
- [ ] Serial baud matches (9600 for slave)

---

## 📦 What Gets Flashed

### Master Arduino (nano_atmega328)
```
Source: src/main.cpp
Size: ~26KB flash, ~1.4KB RAM
Libraries:
  ✓ CANHandler (MCP2515 CAN bus)
  ✓ GPSHandler (Neo-6M GPS)
  ✓ DataLogger (SD card)
  ✓ LEDSlave (Serial commands to slave)
  ✓ CommandHandler (USB commands)
Serial: 115200 baud
```

### Slave Arduino (led_slave)
```
Source: src_slave/main.cpp
Size: ~8KB flash, ~450 bytes RAM
Libraries:
  ✓ Adafruit NeoPixel only
Serial: 9600 baud (RX from master)
LEDs: 20 LEDs on pin D5
```

---

## 💡 Pro Tips

1. **Label your Arduinos** with masking tape:
   - "MASTER - COM3"
   - "SLAVE - COM4"

2. **Use dedicated USB cables** - keep them plugged in

3. **Serial Monitor shortcuts**:
   - Master: 115200 baud for debugging
   - Slave: 9600 baud for LED commands

4. **Test before installing** in vehicle:
   - Master: Connect to USB, verify CAN/GPS/SD init
   - Slave: Send RPM commands, verify LED response

5. **Backup your configuration**:
   - `lib/Config/config.h` (master settings)
   - `src_slave/main.cpp` (slave LED_COUNT)

---

## 🆘 Need Help?

- **Full upload guide**: `UPLOAD_GUIDE.md`
- **Wiring guide**: `docs/hardware/WIRING_GUIDE.md`
- **Build troubleshooting**: `docs/development/BUILD_GUIDE.md`
- **PlatformIO setup**: `docs/development/PLATFORMIO_GUIDE.md`

---

## ✅ Success Checklist

After uploading both Arduinos:

- [ ] Master shows startup messages at 115200 baud
- [ ] Slave LEDs flash green 3 times on power-up
- [ ] Master sends "RPM:xxxx" commands to slave
- [ ] Slave LEDs respond to RPM values
- [ ] No compile errors in either build
- [ ] Serial monitors work at correct baud rates

**You're ready to install in your vehicle!** 🚗
