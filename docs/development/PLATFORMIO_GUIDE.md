# 🚀 PlatformIO Guide for MX5-Telemetry

Complete guide for using PlatformIO IDE with this project, including simulation and testing.

## 📋 Table of Contents

- [Initial Setup](#initial-setup)
- [Building the Project](#building-the-project)
- [Uploading to Hardware](#uploading-to-hardware)
- [Simulation Options](#simulation-options)
- [Testing](#testing)
- [Debugging](#debugging)
- [Common Tasks](#common-tasks)

---

## 🔧 Initial Setup

### 1. Install PlatformIO

You mentioned you have the PlatformIO IDE addon installed - great! If not:

**VS Code Extension**:
1. Open VS Code
2. Go to Extensions (Ctrl+Shift+X)
3. Search: "PlatformIO IDE"
4. Click Install
5. Reload VS Code

### 1.5. Enable PlatformIO CLI in PowerShell (Windows)

If you get "pio: command not found" in PowerShell, you have two options:

#### Option A: Use PlatformIO Core CLI (Already Installed)

PlatformIO is installed, but not in your PATH. Use the full path:

```powershell
# Find PlatformIO path
$env:USERPROFILE\.platformio\penv\Scripts\platformio.exe --version

# Or use the shorter alias
$env:USERPROFILE\.platformio\penv\Scripts\pio.exe --version
```

**Create an alias** for your current PowerShell session:
```powershell
Set-Alias pio "$env:USERPROFILE\.platformio\penv\Scripts\pio.exe"
```

**Make it permanent** - Add to PowerShell profile:
```powershell
# Open/create PowerShell profile
notepad $PROFILE

# Add this line to the file:
Set-Alias pio "$env:USERPROFILE\.platformio\penv\Scripts\pio.exe"

# Save and close, then reload:
. $PROFILE
```

#### Option B: Add to PATH Permanently

Add PlatformIO to your system PATH:

1. **Find PlatformIO path**:
   - Usually: `C:\Users\YourUsername\.platformio\penv\Scripts`

2. **Add to PATH**:
   - Right-click "This PC" → Properties
   - Click "Advanced system settings"
   - Click "Environment Variables"
   - Under "User variables", select "Path"
   - Click "Edit" → "New"
   - Add: `C:\Users\tanne\.platformio\penv\Scripts`
   - Click OK on all dialogs
   - **Restart PowerShell**

3. **Verify**:
   ```powershell
   pio --version
   ```

#### Option C: Use VS Code Terminal Instead

The easiest option - use VS Code's integrated terminal:

1. Open VS Code
2. Press **Ctrl+`** (backtick) to open terminal
3. Terminal should auto-detect PlatformIO
4. Run: `pio --version`

If not working in VS Code terminal, reload the window:
- Press **Ctrl+Shift+P**
- Type "Reload Window"
- Try again

#### Option D: Use PlatformIO GUI (No CLI Needed)

You don't actually need the CLI! Use the VS Code interface:

1. Open project in VS Code
2. Click **PlatformIO icon** in sidebar (alien head 👽)
3. Use GUI for all operations:
   - Build → Click "Build" button
   - Upload → Click "Upload" button
   - Test → Click "Test" button
   - Monitor → Click "Monitor" button

**This is the recommended approach for beginners!**

---

### 2. Initialize Project

The project is already configured with `platformio.ini`. Just open the folder:

```bash
cd C:\Users\tanne\Documents\Github\MX5-Telemetry
```

In VS Code:
- File → Open Folder → Select `MX5-Telemetry` folder
- PlatformIO will auto-detect `platformio.ini`

### 3. Install Dependencies

PlatformIO will automatically install libraries when you first build:

```bash
pio lib install
```

Or click the "Build" button in PlatformIO toolbar.

---

## 🔨 Building the Project

### Method 1: VS Code Interface

1. Click PlatformIO icon in sidebar (alien head 👽)
2. Expand "Project Tasks"
3. Expand "nano_atmega328" (or desired environment)
4. Click "Build"

### Method 2: Command Line

```bash
# Build for Arduino Nano (default)
pio run

# Build for specific environment
pio run -e nano_atmega328

# Clean and rebuild
pio run --target clean
pio run
```

### Build Environments

The project has 4 build environments:

| Environment | Purpose | Use Case |
|------------|---------|----------|
| `nano_atmega328` | Production build | Upload to real Arduino Nano |
| `nano_debug` | Debug build | Serial debugging with symbols |
| `wokwi_sim` | Wokwi simulator | Visual hardware simulation |
| `native_sim` | Native testing | Run unit tests on PC |

---

## 📤 Uploading to Hardware

### Prerequisites

1. Connect Arduino Nano via USB
2. Drivers should auto-install (or install CH340 drivers if needed)

### Upload Methods

**VS Code Interface**:
1. PlatformIO sidebar → Project Tasks → nano_atmega328 → Upload

**Command Line**:
```bash
# Upload to connected Arduino Nano
pio run --target upload

# Upload and open serial monitor
pio run --target upload && pio device monitor
```

**Keyboard Shortcut**:
- `Ctrl+Alt+U` (Upload)
- `Ctrl+Alt+B` (Build)

### Monitor Serial Output

```bash
# Open serial monitor (115200 baud)
pio device monitor

# Monitor with filters
pio device monitor --filter time --filter default

# Exit monitor: Ctrl+C
```

---

## 🎮 Simulation Options

### Option 1: Wokwi Simulator (Visual Hardware Simulation)

Wokwi provides a visual, interactive simulation with virtual components.

#### Setup Wokwi:

1. **Install Wokwi Extension**:
   - VS Code Extensions → Search "Wokwi"
   - Install "Wokwi Simulator"

2. **Build for Wokwi**:
   ```bash
   pio run -e wokwi_sim
   ```

3. **Start Simulation**:
   - Press `F1` → Type "Wokwi: Start Simulator"
   - OR click "Start Simulation" in Wokwi panel

4. **Interact with Simulation**:
   - LED ring shows RPM visualization
   - Adjust potentiometer to simulate RPM input
   - View Serial output in simulator

#### Wokwi Features:

- ✅ Visual LED strip (30 LEDs)
- ✅ Real-time serial monitor
- ✅ Adjustable RPM input via potentiometer
- ✅ Full Arduino Nano simulation
- ⚠️ No CAN bus simulation (limited external chips)
- ⚠️ No SD card simulation

**Note**: The included `hardware/diagram.json` provides a basic Wokwi circuit. For full testing, you'll need to test on real hardware for CAN/SD/GPS.

---

### Option 2: Native Unit Testing

Run tests on your PC without any hardware.

#### Run Unit Tests:

```bash
# Run all tests
pio test -e native_sim

# Run with verbose output
pio test -e native_sim -v

# Run specific test
pio test -e native_sim --filter test_rpm_calculation
```

#### What Gets Tested:

- ✅ RPM calculation logic
- ✅ Throttle position conversion
- ✅ Temperature calculations
- ✅ LED mapping algorithms
- ✅ GoPro control logic
- ✅ CSV data formatting

#### Test Results Example:

```
test/test_telemetry.cpp:XX: test_rpm_calculation_idle [PASSED]
test/test_telemetry.cpp:XX: test_rpm_calculation_cruise [PASSED]
test/test_telemetry.cpp:XX: test_rpm_calculation_redline [PASSED]
...
-----------------------
15 Tests 0 Failures 0 Ignored
OK
```

---

### Option 3: SimAVR (Advanced)

For full AVR chip simulation:

```bash
# Install SimAVR (Linux/Mac)
sudo apt-get install simavr  # Ubuntu/Debian
brew install simavr          # macOS

# Run simulation
pio run -e nano_atmega328
simavr -m atmega328p .pio/build/nano_atmega328/firmware.elf
```

---

## 🐛 Debugging

### Serial Print Debugging

Add debug output to your code:

```cpp
#ifdef DEBUG_MODE
  Serial.print("RPM: ");
  Serial.println(currentRPM);
#endif
```

Build with debug environment:

```bash
pio run -e nano_debug --target upload
pio device monitor
```

### PlatformIO Debugger (Advanced)

For hardware debugging (requires debug probe):

1. Add debug configuration to `platformio.ini`:
   ```ini
   [env:nano_debug]
   debug_tool = simavr
   debug_init_break = tbreak setup
   ```

2. Start debugging:
   - Press `F5` in VS Code
   - OR PlatformIO → Debug → Start Debugging

---

## 💡 Common Tasks

### Task: Check Code Quality

```bash
# Run static analysis
pio check

# Specific tool
pio check --tool cppcheck
```

### Task: Clean Build

```bash
# Remove build files
pio run --target clean

# Clean all environments
pio run --target cleanall
```

### Task: Update Libraries

```bash
# Update all libraries
pio lib update

# Update specific library
pio lib update "Adafruit NeoPixel"
```

### Task: List Installed Libraries

```bash
pio lib list
```

### Task: Show Device Info

```bash
# List connected devices
pio device list

# Show detailed info
pio device monitor --describe
```

### Task: Build Size Analysis

```bash
# Show memory usage
pio run --target size

# Verbose size info
pio run -v --target size
```

---

## 📊 Simulation Workflow

### Recommended Testing Workflow:

1. **Unit Tests First** (Native):
   ```bash
   pio test -e native_sim
   ```
   - Verify all calculations and logic
   - Fast iteration (no upload needed)

2. **Wokwi Visual Sim** (Wokwi):
   ```bash
   pio run -e wokwi_sim
   # Start Wokwi simulator
   ```
   - Test LED patterns
   - Verify timing
   - Check serial output

3. **Bench Test** (Hardware without vehicle):
   ```bash
   pio run -e nano_atmega328 --target upload
   ```
   - Test all modules independently
   - Verify SD card logging
   - Test GPS lock

4. **Vehicle Integration** (Final):
   - Test CAN bus communication
   - Verify RPM reading
   - Full system test

---

## 🎯 Quick Reference

### Most Common Commands

```bash
# Build project
pio run

# Upload to Arduino
pio run --target upload

# Build + Upload + Monitor
pio run -t upload && pio device monitor

# Run unit tests
pio test -e native_sim

# Clean everything
pio run -t cleanall

# Update all libraries
pio lib update
```

### VS Code Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Alt+B` | Build |
| `Ctrl+Alt+U` | Upload |
| `Ctrl+Alt+T` | Run tests |
| `F5` | Start debugging |
| `Ctrl+C` then `M` | Serial monitor |

---

## 🔍 Troubleshooting

### Error: "Could not find a board"

**Solution**: Ensure `platformio.ini` is in project root and contains board definition.

### Error: "Library not found"

**Solution**:
```bash
pio lib install
pio run
```

### Error: "Device not found" when uploading

**Solution**:
1. Check USB connection
2. Install CH340 drivers (for cheap Arduino clones)
3. Try different USB port
4. Check device manager for COM port

### Error: "Permission denied" (Linux/Mac)

**Solution**:
```bash
# Add user to dialout group
sudo usermod -a -G dialout $USER
# Log out and back in
```

### Wokwi Simulator Not Starting

**Solution**:
1. Ensure Wokwi extension is installed
2. Build firmware first: `pio run -e wokwi_sim`
3. Check `hardware/wokwi.toml` path is correct
4. Try: F1 → "Wokwi: Start Simulator"

---

## 📚 Advanced Features

### Custom Scripts

Add build scripts in `platformio.ini`:

```ini
extra_scripts = 
    pre:scripts/pre_build.py
    post:scripts/post_build.py
```

### Environment Variables

Set in `platformio.ini`:

```ini
[env:nano_atmega328]
build_flags = 
    -DVERSION="1.0.0"
    -DMAX_RPM=7200
```

### OTA Updates (Future)

For wireless updates (requires ESP32):

```ini
upload_protocol = espota
upload_port = 192.168.1.100
```

---

## 🎓 Learning Resources

- **PlatformIO Docs**: https://docs.platformio.org
- **Wokwi Docs**: https://docs.wokwi.com
- **Unity Testing**: https://github.com/ThrowTheSwitch/Unity

---

## ✅ Next Steps

1. **Build the project**:
   ```bash
   pio run
   ```

2. **Run tests**:
   ```bash
   pio test -e native_sim
   ```

3. **Try Wokwi simulation**:
   - Install Wokwi extension
   - Build for Wokwi: `pio run -e wokwi_sim`
   - Start simulator

4. **Upload to hardware** (when ready):
   ```bash
   pio run --target upload
   pio device monitor
   ```

---

**Happy coding with PlatformIO!** 🚀

For project-specific questions, see `README.md` and `WIRING_GUIDE.md`.
