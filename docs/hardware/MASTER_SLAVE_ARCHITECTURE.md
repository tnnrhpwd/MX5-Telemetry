# Master + Slave Architecture

## Overview

The MX5-Telemetry system uses a **two-Arduino architecture** to eliminate SD card/LED interrupt conflicts:

### Arduino #1 - Master (Logger)
**Project:** `master/`
- CAN Bus reading (50Hz)
- GPS logging (10Hz)
- SD card data logging (5Hz)
- USB command interface
- Bit-bang serial TX on **Pin D6** → Slave RX (1200 baud)

**Flash:** ~81% | **RAM:** ~77%

### Arduino #2 - Slave (LED Controller)
**Project:** `slave/`
- WS2812B LED strip control on **Pin D5**
- SoftwareSerial RX on **Pin D2** ← Master TX (1200 baud)
- Haptic motor on **Pin D3** (optional)
- Brightness potentiometer on **Pin A6**
- No SD/GPS/CAN conflicts!

**Flash:** ~33% | **RAM:** ~46%

## Wiring

```
Master Arduino #1              Slave Arduino #2
─────────────────              ────────────────
D6 (TX bit-bang) ────────────→ D2 (SoftwareSerial RX)
GND ──────────────────────────→ GND
5V ←──── Buck Converter ────→ 5V
          (from 12V car)

CAN Bus (SPI)                  LED Strip (D5)
SD Card (SPI)                  Haptic Motor (D3)
GPS (D2/D3 SoftwareSerial)
```

**IMPORTANT:**
- Master uses **D6** for Slave communication (NOT D1/TX - that's USB Serial)
- Slave uses **D2** for receiving commands (SoftwareSerial RX)
- Both communicate at **1200 baud** (slow but reliable, avoids corruption from interrupts)
- **Common ground is required** between both Arduinos
- See [LED Timing and Performance](../features/LED_TIMING_AND_PERFORMANCE.md) for why 1200 baud

## Build & Upload

### 1. Flash Master (Logger)
```powershell
# From repository root
pio run -d master -t upload --upload-port COM6
```

### 2. Flash Slave (LED)
```powershell
# Swap USB cable to Slave Arduino
pio run -d slave -t upload --upload-port COM6
```

## Serial Protocol

Master sends simple commands to slave at **1200 baud** via bit-bang serial on D6.

**Message format:** `!<cmd>\n` (start marker + command + newline)

| Command | Example | Description |
|---------|---------|-------------|
| R | `!R3500\n` | Set RPM value |
| S | `!S60\n` | Set speed (km/h) |
| E | `!E\n` | Show error animation |
| W | `!W\n` | Show rainbow wave animation |
| C | `!C\n` | Clear display |
| B | `!B128\n` | Set brightness (0-255) |
| V | `!V100\n` | Trigger haptic (ms) |

**Timing:** Each message takes ~67ms at 1200 baud. Updates are sent at 10Hz (every 100ms).

## LED States

| State | Condition | Animation |
|-------|-----------|-----------|
| Idle | Speed = 0 | White pepper animation |
| Gas Efficiency | RPM 800-1500 | Static blue bars |
| Stall Danger | RPM 500-800 | Pulsing yellow |
| Normal Driving | RPM 1500-5500 | Green bar fills with RPM |
| High RPM | RPM 5500-6500 | Orange bar with flashing |
| Rev Limit | RPM > 6500 | Solid red + haptic pulse |
| Error | No CAN data | Red pepper animation |

## Benefits

✅ **No more interrupt conflicts** - Each Arduino has dedicated tasks
✅ **Faster logging** - No LED strip delays during SD writes
✅ **Better LED performance** - Dedicated CPU for smooth animations
✅ **Easier debugging** - Isolate LED issues separately
✅ **D6 avoids USB conflict** - D1 is shared with USB Serial

## Troubleshooting

### LEDs stuck on red error animation
1. Check wire from **Master D6** to **Slave D2**
2. Verify **common ground** between Arduinos
3. Confirm both are running at **1200 baud** (check config)
4. Master logs should show `CAN->LED: RPM=...` etc.

### No data received on Slave
1. Connect Slave to USB and open Serial Monitor at 115200
2. Send any USB command (e.g., `R3000`) to enable debug mode
3. When Master sends commands, you should see `RX: ...` debug output
4. If no RX output, check wiring (D6 → D2)
5. Debug mode auto-disables after 10 seconds of no USB activity

### LEDs updating slowly (3+ second delay)
See [LED Timing and Performance](../features/LED_TIMING_AND_PERFORMANCE.md) - this was fixed in Dec 2025.

### Power surge on USB
1. Disconnect LED strip 5V before plugging in USB
2. Power LEDs from external 5V supply, not USB
