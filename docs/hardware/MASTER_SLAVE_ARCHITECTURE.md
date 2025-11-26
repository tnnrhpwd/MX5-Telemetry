# Master + Slave Architecture

## Overview

The MX5-Telemetry system now uses a **two-Arduino architecture** to eliminate SD card/LED interrupt conflicts:

### Arduino #1 - Master (Logger)
**Project:** `MX5-Telemetry`
- CAN Bus reading (50Hz)
- GPS logging (10Hz)
- SD card data logging (5Hz)
- USB command interface
- Serial TX (Pin 1) → Slave RX

**Flash:** 96.0% | **RAM:** 83.2%

### Arduino #2 - Slave (LED Controller)
**Project:** `MX5-Telemetry-LED-Slave`
- WS2812B LED strip control
- Serial RX (Pin 0) ← Master TX
- No SD/GPS/CAN conflicts!

**Flash:** ~15% | **RAM:** ~30%

## Wiring

```
Master Arduino #1              Slave Arduino #2
─────────────────              ────────────────
TX (Pin 1) ──────────1kΩ────→ RX (Pin 0)
GND ──────────────────────────┐
                              GND
5V ←──── Buck Converter ────→ 5V
          (from 12V car)

CAN Bus, SD Card, GPS          LED Strip (Pin D5)
```

## Build & Upload

### 1. Flash Master (Logger)
```powershell
cd MX5-Telemetry
platformio run --target upload --upload-port COM3
```

### 2. Flash Slave (LED)
```powershell
cd ..\MX5-Telemetry-LED-Slave
platformio run --target upload --upload-port COM4
```

## Serial Protocol

Master sends simple commands to slave at 9600 baud:
- `RPM:3500` - Update RPM display
- `SPD:60` - Update speed (affects idle state)
- `ERR` - Show error animation
- `CLR` - Clear display

## Benefits

✅ **No more interrupt conflicts** - Each Arduino has dedicated tasks
✅ **Faster logging** - No LED strip delays during SD writes
✅ **Better LED performance** - Dedicated CPU for smooth animations
✅ **96% → 96% flash** - Removed 3% bloat from master
✅ **Easier debugging** - Isolate LED issues separately

## Testing

1. Connect both Arduinos via USB
2. Power on - Slave shows green flash (3x) on startup
3. Send commands from master - LEDs respond
4. File operations (I command) no longer freeze!
