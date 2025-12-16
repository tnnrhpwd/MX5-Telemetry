# Dual Arduino Architecture (Archived)

This folder contains the archived **dual-arduino** setup which has been superseded by the **Pi 4B + Arduino Nano + ESP32-S3** architecture.

## Why Archived?

The dual-arduino setup used:
- **Master Arduino**: CAN bus, GPS, SD card logging, serial command interface
- **Slave Arduino**: Dedicated LED strip controller

This was complex and had issues:
- ~70ms CAN→LED latency (serial link bottleneck)
- Serial data corruption from interrupts
- Complex wiring between two Arduinos

## Current Architecture (Replacement)

The new architecture uses:
- **Raspberry Pi 4B**: CAN hub reading both HS-CAN and MS-CAN, HDMI display
- **ESP32-S3 Round Display**: Visual dashboard, BLE TPMS receiver, G-force (IMU)
- **Arduino Nano**: Direct CAN→LED with <1ms latency (standalone, no serial dependency)

See [../docs/PI_DISPLAY_INTEGRATION.md](../docs/PI_DISPLAY_INTEGRATION.md) for full architecture details.

## Contents

```
dual-arduino/
├── master/              # Master Arduino (telemetry logger)
├── slave/               # Slave Arduino (LED controller)
├── backup/              # Additional backups of dual-arduino code
├── lib_LEDSlave/        # LEDSlave library (serial protocol)
├── build-automation/    # Upload scripts for master/slave
├── docs/                # Archived documentation
│   ├── MASTER_SLAVE_ARCHITECTURE.md
│   ├── WIRING_GUIDE_DUAL_ARDUINO.md
│   ├── DUAL_ARDUINO_SETUP.md
│   ├── GPS_TROUBLESHOOTING.md
│   ├── COMPREHENSIVE_DATA_LOGGING.md
│   ├── LOG_ROTATION_FEATURE.md
│   └── AUTO_START_FEATURE.md
└── README.md            # This file
```

## Original Features (Dual Arduino)

- GPS logging with Neo-6M module
- SD card data logging in CSV format
- USB command interface (START, PAUSE, STOP, DUMP, etc.)
- Auto-start logging after 10 seconds
- Serial link between Arduinos (1200 baud bit-bang)

## Restoring the Dual-Arduino Setup

If you need to restore this configuration:

1. Move `master/` and `slave/` back to the project root
2. Move `lib_LEDSlave/` to `lib/LEDSlave/`
3. Restore the build scripts from `build-automation/`
4. Restore docs from `docs/` to `../docs/`
5. Update `.vscode/tasks.json` with the dual-arduino tasks
