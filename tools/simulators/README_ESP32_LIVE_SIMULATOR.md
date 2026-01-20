# ESP32-S3 Live Display Simulator

A real-time simulator for the ESP32-S3 display UI that allows you to visualize and test UI changes without flashing the device.

## Features

✨ **Live Source Code Integration** - References the actual C++ source code from `display/src/main.cpp`

🔥 **Hot-Reload** - Automatically detects changes to source files and reloads (press R to manually reload)

🖼️ **Native Windows Window** - Uses pygame to render in a native window

🎮 **Full Interaction** - Simulate all telemetry data and user inputs

📱 **Accurate Rendering** - Mirrors the ESP32 drawing primitives (circles, arcs, text, etc.)

## Installation

The simulator requires `pygame` and `watchdog`:

```bash
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Install dependencies (if not already installed)
pip install pygame watchdog
```

## Running the Simulator

### Option 1: Using VS Code Tasks

Press `Ctrl+Shift+P` and run:
```
Tasks: Run Task > Start ESP32-S3 Live Simulator (Hot-Reload)
```

### Option 2: Command Line

```bash
python tools\simulators\esp32_live_simulator.py
```

## Controls

### Screen Navigation
- **Up Arrow** - Previous screen
- **Down Arrow** - Next screen
- **T** - Cycle through screens manually

### Telemetry Simulation
- **Space** - Toggle engine running
- **+/=** - Increase RPM
- **-/_** - Decrease RPM
- **[** - Decrease speed
- **]** - Increase speed
- **G** - Cycle through gears (N, 1-6)
- **C** - Toggle clutch engagement

### Simulator Controls
- **R** - Reload source code
- **ESC** - Quit simulator

## Usage Workflow

1. **Start the simulator** - Launch using VS Code task or command line
2. **Edit your C++ code** - Make changes to `display/src/main.cpp`
3. **See changes live** - The simulator auto-reloads when files change (or press R)
4. **Test interactions** - Use keyboard controls to simulate telemetry and navigation
5. **Iterate quickly** - No need to compile or flash the ESP32!

## Current Implementation

The simulator currently implements:

- ✅ **Overview Screen** - Full port of `drawOverviewScreen()` function
  - RPM arc gauge around screen edge
  - Gear indicator with color-coded ring
  - Speed display
  - 2x2 grid of key values (Coolant, Oil, Fuel, Voltage)
  - Status indicators (Engine, Connection)
  
- 🔲 **Other Screens** - Placeholder screens (ready to implement)
  - RPM/Speed screen
  - TPMS screen
  - Engine Temps screen
  - G-Force screen
  - Settings screen

## File Structure

```
tools/simulators/
└── esp32_live_simulator.py    # Main simulator (this file)
```

## How It Works

The simulator:

1. **Monitors** `display/src/main.cpp` for changes using watchdog
2. **Parses** the C++ drawing code (currently manual ports of draw functions)
3. **Simulates** the LCD drawing primitives using pygame
4. **Renders** at 30 FPS in a native window
5. **Hot-reloads** when source files change

## Future Enhancements

Potential improvements:

- [ ] Automatic C++ parsing to extract draw functions
- [ ] Implement remaining screen renders (TPMS, Settings, etc.)
- [ ] Serial data injection for realistic testing
- [ ] Record/playback telemetry sequences
- [ ] Screenshot/video capture
- [ ] Side-by-side comparison with actual device

## Advantages Over Old Simulator

| Old Simulator | New Live Simulator |
|---------------|-------------------|
| ❌ Hardcoded UI | ✅ References actual source |
| ❌ Manual updates | ✅ Auto hot-reload |
| ❌ Outdated designs | ✅ Always in sync |
| ❌ Separate codebase | ✅ Uses real ESP32 code |

## Technical Details

### Color Conversion
The simulator converts RGB565 (ESP32 format) to RGB888 (pygame format) for accurate color representation.

### Drawing Primitives
All ESP32 LCD drawing functions are emulated:
- `DrawPixel()` - Single pixel
- `DrawLine()` - Line drawing
- `DrawCircle()` / `FillCircle()` - Circle rendering
- `DrawRect()` / `FillRect()` - Rectangle rendering
- `FillRoundRect()` - Rounded rectangle
- `DrawString()` - Text rendering with size scaling

### Telemetry Simulation
The `TelemetrySimulator` class maintains realistic vehicle state that can be manipulated in real-time.

## Contributing

To add support for additional screens:

1. Find the draw function in `main.cpp` (e.g., `drawRPMScreen()`)
2. Add a corresponding method to the `ESP32LiveSimulator` class
3. Port the C++ drawing calls to pygame using the `LCDSimulator` wrapper
4. Add the screen to the render loop

## License

Part of the MX5-Telemetry project.
