# Dual Arduino Architecture (Archived)

This folder contains the archived **dual-arduino** setup which has been superseded by the simpler single Arduino + ESP32-S3 display architecture.

## Why Archived?

The dual-arduino setup used:
- **Master Arduino**: CAN bus, GPS, SD card logging, serial command interface
- **Slave Arduino**: Dedicated LED strip controller

This was complex and had latency issues (~70ms CAN→LED). The new architecture uses:
- **Single Arduino**: Direct CAN→LED with <1ms latency
- **ESP32-S3 Display**: Round touch screen for visual dashboard (optional)

## Contents

```
dual-arduino/
├── master/           # Master Arduino (telemetry logger)
├── slave/            # Slave Arduino (LED controller)
├── backup/           # Additional backups of dual-arduino code
├── lib_LEDSlave/     # LEDSlave library (serial protocol)
├── build-automation/ # Upload scripts for master/slave
└── docs/
    └── archive/      # Old documentation
```

## Restoring the Dual-Arduino Setup

If you need to restore this configuration:

1. Move `master/` and `slave/` back to the project root
2. Move `lib_LEDSlave/` to `lib/LEDSlave/`
3. Restore the build scripts from `build-automation/`
4. Update `.vscode/tasks.json` with the dual-arduino tasks

## Original Features

- GPS logging with Neo-6M module
- SD card data logging in CSV format
- USB command interface (START, PAUSE, STOP, DUMP, etc.)
- Auto-start logging after 10 seconds
- Serial link between Arduinos (1200 baud)
