# 🚀 Dual Arduino Upload Guide

## Quick Reference

| Arduino | Firmware | Environment | COM Port | Build | Upload |
|---------|----------|-------------|----------|-------|--------|
| **Master** (Logger) | `src/main.cpp` | `nano_atmega328` | COM? | `Ctrl+Shift+B` → Master | `Ctrl+Alt+U` |
| **Slave** (LEDs) | `src_slave/main.cpp` | `led_slave` | COM? | `Ctrl+Shift+B` → Slave | `Ctrl+Alt+U` |

---

## 🎯 Method 1: VS Code PlatformIO (Recommended)

### First Time Setup

1. **Install PlatformIO Extension** (if not already installed):
   - Open VS Code Extensions (Ctrl+Shift+X)
   - Search "PlatformIO IDE"
   - Click Install
   - Restart VS Code

2. **Open Project**:
   - File → Open Folder → Select `MX5-Telemetry`
   - PlatformIO will auto-detect `platformio.ini`

### Upload Master Arduino (Logger)

1. **Connect Master Arduino** via USB
2. **Open PlatformIO toolbar** (bottom of VS Code - looks like alien head icon)
3. **Select environment**: Click "Switch PlatformIO Environment" → `nano_atmega328` (Master)
4. **Build**: Click "Build" button (✓ checkmark) or press `Ctrl+Alt+B`
5. **Upload**: Click "Upload" button (→ arrow) or press `Ctrl+Alt+U`
6. **Monitor** (optional): Click "Serial Monitor" to see output at 115200 baud

**OR use Command Palette (Ctrl+Shift+P):**
- Type: `PlatformIO: Upload` → Select `nano_atmega328`

### Upload Slave Arduino (LED Controller)

1. **Disconnect Master** Arduino
2. **Connect Slave Arduino** via USB
3. **Switch environment**: Click "Switch PlatformIO Environment" → `led_slave` (Slave)
4. **Build**: Click "Build" button or `Ctrl+Alt+B`
5. **Upload**: Click "Upload" button or `Ctrl+Alt+U`
6. **Monitor** (optional): Serial Monitor at 9600 baud

**OR use Command Palette:**
- Type: `PlatformIO: Upload` → Select `led_slave`

---

## ⚡ Method 2: PowerShell Quick Upload Scripts

I've created helper scripts for you!

### Upload Master
```powershell
.\upload_master.ps1
```

### Upload Slave
```powershell
.\upload_slave.ps1
```

### Upload Both (Interactive)
```powershell
.\upload_both.ps1
```

---

## 🔧 Method 3: Manual PlatformIO CLI

If PlatformIO CLI is in your PATH:

### Master Arduino
```bash
pio run -e nano_atmega328 -t upload
```

### Slave Arduino
```bash
pio run -e led_slave -t upload
```

### Build Only (no upload)
```bash
pio run -e nano_atmega328        # Master
pio run -e led_slave              # Slave
```

---

## 📋 Troubleshooting

### Issue: "avrdude: stk500_recv(): programmer is not responding"

**Solutions:**
1. **Close Serial Monitor** - Can't upload while monitoring
2. **Try old bootloader environment**: Use `nano_atmega328_old` instead
3. **Press Reset** on Arduino right before upload starts
4. **Check USB cable** - Use data cable (not charging-only)
5. **Try different USB port**

### Issue: "Error opening serial port"

**Solutions:**
1. **Check COM port** - Is Arduino plugged in?
2. **Close other programs** - Arduino IDE, Serial monitors
3. **Update CH340 drivers** (for clone Nanos)

### Issue: "Wrong COM port"

**Find your COM port:**
```powershell
# PowerShell
Get-WmiObject Win32_SerialPort | Select-Object Name, DeviceID

# Or use Device Manager (devmgmt.msc)
# Look under "Ports (COM & LPT)"
```

**Then update `platformio.ini`:**
```ini
[env:nano_atmega328]
upload_port = COM3    # Your master Arduino port

[env:led_slave]
upload_port = COM4    # Your slave Arduino port
```

### Issue: "Out of memory" during build

**Solution:** Your code is too large. Try:
1. Disable unused features in `lib/Config/config.h`
2. Use `nano_release` environment (more aggressive optimization)
3. Reduce `LED_COUNT` if using LED library on master

---

## 🎮 Game Plan for Future Uploads

### Quick Daily Workflow

**Making changes to master code:**
1. Edit files in `src/` or `lib/`
2. Press `Ctrl+Alt+B` to build
3. Ensure master Arduino connected
4. Press `Ctrl+Alt+U` to upload
5. Done!

**Making changes to slave LED code:**
1. Edit `src_slave/main.cpp`
2. Switch to `led_slave` environment
3. Build and upload (`Ctrl+Alt+B`, `Ctrl+Alt+U`)
4. Done!

### Tips for Efficiency

1. **Label your Arduinos** - Mark them "MASTER" and "SLAVE" with tape
2. **Use different USB ports** - Always plug master into same port
3. **Keep cables connected** - Leave both plugged in during development
4. **Use Serial Monitor** - Debug with `Serial.print()` statements
5. **Verify first** - Always build before upload to catch errors

### Test After Upload

**Master Arduino:**
- Serial output at 115200 baud should show:
  ```
  MX5-Telemetry Master v1.0.0
  Initializing CAN bus...
  Initializing GPS...
  Initializing SD card...
  System ready!
  ```

**Slave Arduino:**
- LED strip should flash green 3 times on startup
- Sends "RPM:xxxx" commands, LEDs respond immediately

---

## 🔍 Verify Current Configuration

Check what's on each Arduino:

**Master (should show lots of sensor init messages):**
```powershell
# Monitor at 115200 baud
pio device monitor -b 115200 -p COM3
```

**Slave (should respond to commands):**
```powershell
# Monitor at 9600 baud
pio device monitor -b 9600 -p COM4

# Send test command
RPM:3000    # LEDs should show yellow bar
```

---

## 📦 What Gets Uploaded

### Master Arduino (`nano_atmega328`)
- **Source**: `src/main.cpp`
- **Libraries**: CANHandler, GPSHandler, DataLogger, CommandHandler, LEDSlave, Config
- **External**: MCP_CAN, TinyGPSPlus, SdFat, NeoPixel
- **Serial**: 115200 baud (USB + TX to slave)
- **Size**: ~26KB flash, ~1.4KB RAM

### Slave Arduino (`led_slave`)
- **Source**: `src_slave/main.cpp`
- **Libraries**: Adafruit NeoPixel ONLY
- **External**: None (minimalist for speed)
- **Serial**: 9600 baud (RX from master)
- **Size**: ~8KB flash, ~450 bytes RAM

---

## 🆘 Emergency Recovery

If something goes wrong and Arduino won't respond:

### Burn Bootloader (last resort)
1. Get Arduino as ISP programmer or USBasp
2. In PlatformIO: Upload Bootloader
3. This wipes everything and reinstalls firmware loader

### Factory Reset
1. Upload basic blink sketch first
2. Then upload your firmware
3. This clears any stuck states

---

**Need help?** Check [docs/development/BUILD_GUIDE.md](docs/development/BUILD_GUIDE.md) for detailed build information.
