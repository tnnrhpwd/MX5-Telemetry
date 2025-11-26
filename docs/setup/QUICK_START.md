# 🚀 Quick Start Guide - MX5-Telemetry

**Get your telemetry system up and running in 30 minutes!**

## ⚡ Super Quick Setup (For Experienced Arduino Users)

### 1. Hardware Connections (5 min)

```
Arduino Nano Pin Assignments:
D2  → GPS RX        D10 → CAN CS
D3  → GPS TX        D11 → MOSI (shared)
D4  → SD CS         D12 → MISO (shared)
D5  → MOSFET Gate   D13 → SCK (shared)
D6  → LED Data      5V  → Buck converter OUT+
                    GND → Buck converter OUT-
```

**Power**: 12V (OBD pin 16) → Buck converter → 5V Arduino

**CAN Bus**: OBD pins 6 (CAN-H), 14 (CAN-L), 5 (GND) → MCP2515

### 2. Software Setup (10 min)

Install libraries in Arduino IDE:
```
Tools → Manage Libraries → Install:
  - MCP_CAN (by Cory J. Fowler)
  - Adafruit NeoPixel
  - TinyGPSPlus
```

### 3. Upload Firmware (5 min)

```
Tools → Board → Arduino Nano
Tools → Processor → ATmega328P
Tools → Port → [Select your COM port]
Sketch → Upload
```

### 4. Test (10 min)

1. Insert SD card (FAT32 formatted)
2. Connect to OBD-II port
3. Turn ignition ON
4. Watch for LED startup animation
5. Start engine → LEDs should respond to RPM

**Done!** 🎉

---

## 📖 Detailed Setup (For Beginners)

### Step 1: Order Parts (30 min planning)

**Minimum shopping list**:
- [ ] Arduino Nano (~$5)
- [ ] MCP2515 CAN module with 16MHz crystal (~$5)
- [ ] WS2812B LED strip, 30 LEDs (~$8)
- [ ] Neo-6M GPS module (~$10)
- [ ] MicroSD card module (~$2)
- [ ] LM2596 buck converter (~$3)
- [ ] IRF540N MOSFET (~$1)
- [ ] Wires, connectors, heat shrink (~$10)
- [ ] 8-16GB MicroSD card (~$5)

**Total**: ~$50 from Amazon/AliExpress

See `PARTS_LIST.md` for detailed BOM.

---

### Step 2: Wait for Parts (1-3 weeks)

While waiting:
- [ ] Read `README.md` completely
- [ ] Review `WIRING_GUIDE.md`
- [ ] Download Arduino IDE: https://www.arduino.cc/en/software
- [ ] Join Miata forums/communities for tips

---

### Step 3: Bench Test (1 hour)

**Before connecting to car**, test on bench:

1. **Install Arduino IDE** (if not already installed)

2. **Install libraries**:
   - Open Arduino IDE
   - Go to: Sketch → Include Library → Manage Libraries
   - Search and install: `MCP_CAN`, `Adafruit NeoPixel`, `TinyGPSPlus`

3. **Open firmware**:
   - File → Open → `MX5_Telemetry.ino`

4. **Select board**:
   - Tools → Board → Arduino Nano
   - Tools → Processor → ATmega328P

5. **Connect Arduino via USB**:
   - Tools → Port → Select your Arduino's COM port

6. **Upload firmware**:
   - Click Upload button (→)
   - Wait for "Done uploading"

7. **Open Serial Monitor**:
   - Tools → Serial Monitor
   - Set baud rate: 115200
   - You should see: "MX5-Telemetry System Starting..."

---

### Step 4: Wire Components (2-3 hours)

Follow `WIRING_GUIDE.md` step-by-step. Key safety checks:

- [ ] Buck converter adjusted to exactly 5.0V BEFORE connecting Arduino
- [ ] All VCC pins go to 5V rail
- [ ] All GND pins go to common ground
- [ ] No short circuits between power and ground
- [ ] LED strip powered from buck converter, NOT Arduino pin
- [ ] OBD-II connections: Pin 6=CAN-H, Pin 14=CAN-L, Pin 16=12V, Pin 5=GND

**Pro tip**: Test each module individually before connecting all together.

---

### Step 5: Module Testing (30 min)

Test modules one at a time with 5V power supply:

#### Test CAN Module
```cpp
// In setup(), check Serial output:
// "CAN Bus initialized successfully" = GOOD ✓
// "CAN Bus initialization FAILED!" = Check wiring ✗
```

#### Test SD Card
```cpp
// Serial output should show:
// "SD Card initialized successfully" = GOOD ✓
// "Log file created: LOG_XXX.CSV" = GOOD ✓
```

#### Test LED Strip
```cpp
// Should see:
// Rainbow animation on startup = GOOD ✓
// Green fill animation = GOOD ✓
```

#### Test GPS
```cpp
// Wait 2-5 minutes for GPS lock (needs clear sky view)
// Check Serial for: GPS Fix, Satellites count
```

---

### Step 6: Vehicle Installation (1 hour)

1. **Mount enclosure** in convenient location (under dash, center console)

2. **Route wires** neatly:
   - LED strip → Dashboard/windshield
   - GPS antenna → Near windshield (clear sky view)
   - CAN wires → OBD-II port

3. **Connect to OBD-II**:
   - Use extension cable (recommended) OR
   - Direct plug-in

4. **Secure cables** with zip ties

5. **Test fit** everything before final installation

---

### Step 7: First Drive Test (30 min)

1. **Turn ignition ON** (engine can be off)
   - LEDs should do startup animation
   - Check Serial monitor for initialization messages

2. **Wait for GPS lock** (2-5 min, clear sky view)
   - LED strip will remain off until RPM > 0

3. **Start engine**:
   - LEDs should immediately respond to RPM
   - Check color gradient changes as you rev
   - GoPro should power ON (if connected)

4. **Drive around the block**:
   - Verify LEDs track RPM accurately
   - Rev to shift point → should see red flashing
   - Stop and wait → GoPro should turn OFF after 10 seconds

5. **Check data logging**:
   - Turn off vehicle
   - Remove SD card
   - Check for `LOG_XXX.CSV` file
   - Open in Excel → verify data looks correct

---

## 🔧 Common Issues & Quick Fixes

| Problem | Quick Fix |
|---------|-----------|
| **No power** | Check buck converter output = 5V, check fuse |
| **LEDs not working** | Check D6 connection, verify LED count matches code |
| **CAN errors** | Verify CAN-H/CAN-L not swapped, check vehicle is ON |
| **No SD card** | Format as FAT32, try different card |
| **GPS no fix** | Move near window, wait 5 min for cold start |
| **RPM stuck at 0** | Check CAN wiring, verify MCP2515 is 16MHz version |

See `README.md` Troubleshooting section for detailed solutions.

---

## 🎯 Configuration Tips

### Adjust for Your Miata

**Different redline?** Edit these in code:
```cpp
#define RPM_SHIFT_LIGHT 6500  // Your shift point
#define RPM_REDLINE     7200  // Your redline
```

**Different LED count?** Edit:
```cpp
#define LED_COUNT       20    // Number of LEDs in your strip
```

**Want faster data logging?**
```cpp
#define LOG_INTERVAL    200   // Decrease for faster logging (ms)
```

### Color Customization

**Want different colors?** Modify `getRPMColor()` function:
```cpp
// Example: Blue → Red gradient
uint32_t getRPMColor(int ledIndex, int totalLEDs) {
  float position = (float)ledIndex / (float)totalLEDs;
  uint8_t red = (uint8_t)(position * 255);
  uint8_t blue = (uint8_t)((1.0 - position) * 255);
  return strip.Color(red, 0, blue);
}
```

---

## 📊 Using Your Data

### Quick Data Check

1. Remove SD card
2. Insert into computer
3. Open CSV file in Excel
4. Check columns: RPM, Speed, GPS coordinates

### Advanced Analysis

Use Python scripts in `DATA_ANALYSIS.md`:
- RPM distribution histograms
- GPS track maps
- Speed vs RPM scatter plots
- Lap time analysis

---

## 🚨 Safety Reminders

- **Test in safe environment** before track use
- **Do not use as primary instrument** (always watch factory gauges)
- **Check local laws** regarding LED usage while driving
- **Secure all wiring** away from pedals and controls
- **Use proper fusing** on all power connections

---

## 📱 Support & Community

**Having issues?**
1. Check `README.md` Troubleshooting section
2. Review `WIRING_GUIDE.md` connections
3. Open GitHub issue with:
   - Serial monitor output
   - Photos of wiring
   - Description of problem

**Want to share your build?**
- Post photos to GitHub Discussions
- Share data analysis results
- Contribute improvements via Pull Requests

---

## ✅ Pre-Drive Checklist

Before every drive, verify:

- [ ] SD card inserted and has free space
- [ ] GPS has clear sky view
- [ ] All wires secure (no loose connections)
- [ ] Buck converter not overheating
- [ ] LEDs respond to startup animation
- [ ] Serial monitor shows no errors (if connected)

---

## 🏁 You're Ready!

Your MX5 telemetry system is now operational. Enjoy your data-rich driving experience!

**Remember**:
- Data logs to SD card every 200ms (5Hz)
- GPS updates every 100ms (10Hz)
- LEDs refresh every 20ms (50Hz)
- GoPro auto-powers with engine

**Have fun and drive safe!** 🏎️💨

---

**Need more details?** See complete documentation:
- `README.md` - Full system overview
- `WIRING_GUIDE.md` - Detailed wiring instructions
- `PARTS_LIST.md` - Complete bill of materials
- `DATA_ANALYSIS.md` - Data visualization and analysis
- `libraries_needed.txt` - Library installation guide
