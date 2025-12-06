# Dual Arduino Setup Backup

This folder contains a backup of the **two-Arduino architecture** created on December 3, 2025.

## Overview

The dual Arduino setup separates concerns:
- **Master Arduino**: CAN bus reading, GPS logging, SD card data logging, USB command interface
- **Slave Arduino**: Dedicated LED strip control, haptic feedback, brightness potentiometer

## Why Two Arduinos?

The original design used two Arduinos to avoid interrupt conflicts:
- WS2812B LED strips disable interrupts during data transmission
- SD card writes can cause timing glitches
- SoftwareSerial for GPS conflicts with LED timing

## Contents

- `master/` - Master Arduino project (CAN + GPS + SD + USB)
- `slave/` - Slave Arduino project (LED + Haptic)
- `lib/` - Shared libraries including LEDSlave communication

## Communication

- Master sends commands to Slave via bit-bang serial on D6 → Slave D2
- Protocol: 1200 baud, commands like `!R3500\n` for RPM 3500
- Common ground required between both Arduinos

## Wiring

See `docs/hardware/WIRING_GUIDE_DUAL_ARDUINO.md` for complete wiring instructions.

## Why Upgraded to Single Arduino?

The single Arduino setup was created to:
1. **Eliminate RPM data corruption** between Master→Slave serial
2. **Reduce latency** (no serial communication delay)
3. **Simplify wiring** (fewer connections)
4. **Improve LED responsiveness** (direct CAN→LED update path)

## Restoring This Backup

To restore the dual Arduino setup:
1. Copy `master/` and `slave/` back to the repository root
2. Copy `lib/` contents back to the repository `lib/` folder
3. Update `docs/` if needed
