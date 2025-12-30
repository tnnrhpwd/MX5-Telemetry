# Build System Architecture

## System Overview

The MX5-Telemetry project uses a **three-device architecture**:

| Device | Build Location | Tools |
|--------|----------------|-------|
| **Arduino Nano** | `arduino/` | PlatformIO |
| **ESP32-S3 Display** | `display/` | PlatformIO |
| **Raspberry Pi 4B** | `pi/` | Python (no build) |

## What Gets Uploaded to Hardware?

### Arduino Nano (`arduino/`)

✅ **Compiled into firmware:**
- `arduino/src/` - Main application code (main.cpp)
- `lib/` - Custom libraries (CANHandler, LEDController, etc.)
- Platform libraries from `lib_deps` in platformio.ini

📦 **Approximate firmware size:** ~20-30KB (plenty of room on Arduino Nano's 32KB flash)

### ESP32-S3 Display (`display/`)

✅ **Compiled into firmware:**
- `display/src/` - Main application code (main.cpp, ui_config.h)
- `display/include/` - Header files (display_config.h, boot_logo.h, etc.)
- `display/lib/` - Display-specific libraries (WaveshareDisplay)
- LVGL and LovyanGFX libraries from `lib_deps`

📦 **Approximate firmware size:** ~1-2MB (ESP32-S3 has 4MB+ flash)

### Raspberry Pi (`pi/`)

✅ **Runs directly (no compilation):**
- `pi/ui/` - Python UI application
- `pi/start_display.sh` - Startup script

## What NEVER Gets Uploaded?

❌ **These folders stay on your development computer:**
- `tools/` - Python simulators, utilities
- `docs/` - Documentation
- `test/` - Unit tests
- `archive/` - Legacy code
- `hardware/` - Wokwi simulation files
- `build-automation/` - Build/upload scripts

## PlatformIO Build Process

```
┌─────────────────────────────────────┐
│  Arduino Build (pio run -d arduino) │
├─────────────────────────────────────┤
│ 1. Read arduino/platformio.ini      │
│ 2. Compile arduino/src/*.cpp        │
│ 3. Compile lib/*/*.cpp              │
│ 4. Link platform libraries          │
│ 5. Generate .hex file               │
│ 6. Upload ONLY .hex to Arduino      │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│  ESP32 Build (pio run -d display)   │
├─────────────────────────────────────┤
│ 1. Read display/platformio.ini      │
│ 2. Compile display/src/*.cpp        │
│ 3. Compile display/lib/*/*.cpp      │
│ 4. Link LVGL + LovyanGFX            │
│ 5. Generate .bin file               │
│ 6. Upload to ESP32-S3               │
└─────────────────────────────────────┘
```

## LED Simulator Architecture

### The Flow:
```
LEDStates.h (Arduino)
     ↓
parse_arduino_led_config.py (Python parser)
     ↓
led_simulator_v2.1.py (Python simulator)
```

### Single Source of Truth:
- **LEDStates.h** contains ALL LED configuration constants
- **Parser** reads the Arduino header file using regex
- **Simulator** imports values from parser on startup
- Changes in Arduino → automatically reflected in simulator

### Why This Works:
1. **No bloat**: Parser only runs on your PC, never uploaded to Arduino
2. **Always in sync**: Simulator reads directly from Arduino code
3. **Fail-safe**: Simulator has defaults if Arduino file unavailable
4. **Same repo**: Everything stays organized together

## Testing the Setup

### Test parser independently:
```powershell
cd tools
python test_parser.py
```

### Test simulator:
```powershell
cd tools
python led_simulator_v2.1.py
```

### Build Arduino firmware:
```powershell
pio run
```

### Check firmware size:
```
RAM:   [====      ]  42.1% (used 863 bytes from 2048 bytes)
Flash: [===       ]  28.4% (used 8734 bytes from 30720 bytes)
```

## Benefits

✅ **Lean Firmware**: Only essential code on Arduino  
✅ **Rich Tooling**: Full Python ecosystem for development  
✅ **Auto-Sync**: Tools always match Arduino logic  
✅ **Single Repo**: Everything version controlled together  
✅ **Safe Separation**: No risk of bloating firmware  

## Common Questions

**Q: Will the simulator slow down my Arduino?**  
A: No! The simulator never runs on Arduino. It only runs on your PC.

**Q: What if I change LED values in Arduino?**  
A: The simulator automatically reads the new values when you start it.

**Q: Can I delete the tools folder to save space?**  
A: You can, but you'd lose the simulator. It doesn't affect Arduino builds.

**Q: What happens if the parser fails?**  
A: The simulator falls back to hardcoded defaults and still works.

## File Size Comparison

```
Arduino Firmware:     ~25 KB  (uploaded to hardware)
Python Simulator:     ~50 KB  (stays on your PC)
Documentation:       ~100 KB  (stays on your PC)
Total Project:       ~200 KB  (organized in one repo)
```

**Result**: Clean separation, zero bloat, maximum flexibility! 🎯
