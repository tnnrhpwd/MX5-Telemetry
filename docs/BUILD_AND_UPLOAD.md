# 🚀 Build and Upload Guide

**One-stop guide for building and uploading firmware to both Arduinos.**

---

## Quick Reference

| Arduino | Purpose | Build Command | Upload Command |
|---------|---------|---------------|----------------|
| **Master** | Logger (CAN, GPS, SD) | `pio run -d master` | `pio run -d master --target upload --upload-port COM3` |
| **Slave** | LED Controller | `pio run -d slave` | `pio run -d slave --target upload --upload-port COM4` |

---

## 🔧 Prerequisites

- **VS Code** with PlatformIO extension installed
- **Two Arduino Nano boards** (CH340 or FTDI)
- **USB data cables** (not charge-only)

---

## Method 1: VS Code Tasks (Easiest)

Press `Ctrl+Shift+B` and select:
- **PlatformIO: Build Master** - Build master firmware
- **PlatformIO: Build Slave** - Build slave firmware
- **PlatformIO: Upload Master** - Upload to master Arduino
- **PlatformIO: Upload Slave** - Upload to slave Arduino

---

## Method 2: Command Line

### Find Your COM Ports

```powershell
# Windows - List COM ports
Get-WmiObject Win32_SerialPort | Select-Object DeviceID, Description
```

### Build Both

```powershell
cd C:\Users\tanne\Documents\Github\MX5-Telemetry
pio run -d master   # Build master
pio run -d slave    # Build slave
```

### Upload Both

```powershell
# Upload Master (adjust COM port as needed)
pio run -d master --target upload --upload-port COM3

# Upload Slave (adjust COM port as needed)
pio run -d slave --target upload --upload-port COM4
```

### Upload Both in One Command

```powershell
pio run -d master --target upload --upload-port COM3; pio run -d slave --target upload --upload-port COM4
```

---

## Method 3: PowerShell Scripts

```powershell
.\build-automation\upload_master.ps1
.\build-automation\upload_slave.ps1
.\build-automation\upload_both.ps1    # Interactive
```

---

## 🧪 Verify Upload

### Master Arduino (115200 baud)

1. Open Serial Monitor at **115200 baud**
2. Press reset or type `STATUS`
3. Expected output:
   ```
   MX5-Telemetry v3.2
   CAN: OK
   GPS: Waiting...
   SD: OK
   Ready
   ```

### Slave Arduino (9600 baud for USB, 1200 baud from Master)

1. LEDs should show startup animation
2. Open Serial Monitor at **9600 baud**
3. Type `R3000` to test RPM display
4. Type `C` to clear

---

## 🔌 Hardware Setup

### Wiring Diagram

```
┌──────────────────┐                    ┌──────────────────┐
│   MASTER         │                    │   SLAVE          │
│   (Logger)       │                    │   (LEDs)         │
│                  │                    │                  │
│  D6 (TX) ────────┼──── 1200 baud ────►│ D2 (RX)          │
│  GND ────────────┼────────────────────│ GND              │
│                  │                    │  D5 ─────────────┼──► LED Strip Data
│  D10 ← CAN CS    │                    │                  │
│  D4  ← SD CS     │                    │                  │
│  D2  ← GPS TX    │                    │                  │
│  D3  → GPS RX    │                    │                  │
└──────────────────┘                    └──────────────────┘
```

### Pin Assignments

**Master Arduino:**
| Pin | Function |
|-----|----------|
| D2 | GPS RX (from GPS TX) |
| D3 | GPS TX (to GPS RX) |
| D4 | SD Card CS |
| D6 | Serial TX to Slave (1200 baud) |
| D10 | MCP2515 CAN CS |
| D11-D13 | SPI (MOSI, MISO, SCK) |

**Slave Arduino:**
| Pin | Function |
|-----|----------|
| D2 | Serial RX from Master (1200 baud) |
| D5 | WS2812B LED Data |
| A6 | Brightness potentiometer (optional) |

---

## 📡 Communication Protocol

**Master → Slave (1200 baud, bit-bang serial):**

| Command | Format | Example | Description |
|---------|--------|---------|-------------|
| RPM | `R<value>` | `R3500` | Set RPM display |
| Speed | `S<value>` | `S65` | Set speed (km/h) |
| Clear | `C` | `C` | Clear all LEDs |
| Error | `E` | `E` | Show error animation |
| Wave | `W` | `W` | Rainbow wave |
| Brightness | `B<value>` | `B128` | Set brightness (0-255) |

---

## 🔧 Troubleshooting

### "avrdude: stk500_recv(): programmer is not responding"

1. **Close Serial Monitor** - can't upload while monitoring
2. **Try different USB port**
3. **Press reset button** while upload starts
4. **Check USB cable** - must be data cable, not charge-only

### "Access denied" on COM port

1. Close any other program using the port
2. Close Serial Monitor in VS Code
3. Restart VS Code

### Upload works but LEDs don't respond

1. Check D6→D2 wire connection
2. Verify shared GND between Arduinos
3. Check LED strip data wire on D5
4. Verify 5V power to LED strip

### Old bootloader (clone Nanos)

Some clone Nanos use the old bootloader. Use these commands instead:
```powershell
pio run -d master -e nano_old_bootloader --target upload
pio run -d slave -e nano_old_bootloader --target upload
```

---

## 📊 Expected Memory Usage

| Arduino | RAM | Flash |
|---------|-----|-------|
| Master | ~77% (1584/2048 bytes) | ~83% (25416/30720 bytes) |
| Slave | ~46% (934/2048 bytes) | ~33% (10122/30720 bytes) |

---

## See Also

- [WIRING_GUIDE.md](hardware/WIRING_GUIDE.md) - Detailed wiring diagrams
- [MASTER_SLAVE_ARCHITECTURE.md](hardware/MASTER_SLAVE_ARCHITECTURE.md) - System architecture
- [LED_STATE_SYSTEM.md](features/LED_STATE_SYSTEM.md) - LED behavior documentation
