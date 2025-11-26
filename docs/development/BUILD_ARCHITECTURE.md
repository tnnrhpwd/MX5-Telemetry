# Build System Architecture

## Overview
The MX5-Telemetry project separates **Arduino firmware** from **development tools** to keep the hardware build lean and efficient.

## What Gets Uploaded to Arduino?

✅ **ONLY these folders are compiled into the firmware:**
- `src/` - Your main application code (main.cpp)
- `lib/` - Custom libraries (CANHandler, LEDController, DataLogger, etc.)
- Platform libraries from `lib_deps` in platformio.ini

📦 **Approximate firmware size:** ~20-30KB (plenty of room on Arduino Nano's 32KB flash)

## What NEVER Gets Uploaded?

❌ **These folders stay on your computer:**
- `tools/` - Python scripts (LED simulator, parsers)
- `docs/` - Documentation
- `examples/` - Example code
- `test/` - Unit tests
- `scripts/` - Build scripts
- `hardware/` - Wokwi simulation files

## How PlatformIO Builds

```
┌─────────────────────────────────────┐
│  PlatformIO Build Process           │
├─────────────────────────────────────┤
│ 1. Read platformio.ini              │
│ 2. Compile src/*.cpp                │
│ 3. Compile lib/*/*.cpp              │
│ 4. Link platform libraries          │
│ 5. Generate .hex file               │
│ 6. Upload ONLY .hex to Arduino      │
└─────────────────────────────────────┘

❌ Ignored: tools/, docs/, examples/, test/
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
