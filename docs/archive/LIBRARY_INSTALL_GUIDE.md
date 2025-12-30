# Library Installation Troubleshooting Guide

## Step-by-Step Installation in Arduino IDE

### Method 1: Arduino IDE Library Manager (Recommended)

1. **Open Arduino IDE** (download from https://www.arduino.cc/en/software if needed)

2. **Go to Library Manager**:
   - Click: `Sketch` → `Include Library` → `Manage Libraries...`
   - OR use keyboard shortcut: `Ctrl+Shift+I` (Windows/Linux) or `Cmd+Shift+I` (Mac)

3. **Install MCP_CAN Library**:
   - In the search box, type: `MCP_CAN`
   - Find: `MCP_CAN` by **Cory J. Fowler**
   - Click `Install`
   - Wait for "Installed" message

4. **Install Adafruit NeoPixel Library**:
   - In the search box, type: `Adafruit NeoPixel`
   - Find: `Adafruit NeoPixel` by **Adafruit**
   - Click `Install`
   - If prompted about dependencies, click "Install All"
   - Wait for "Installed" message

5. **Install TinyGPSPlus Library**:
   - In the search box, type: `TinyGPSPlus`
   - Find: `TinyGPSPlus` by **Mikal Hart**
   - Click `Install`
   - Wait for "Installed" message

6. **Verify Installation**:
   - Go to: `Sketch` → `Include Library`
   - Scroll down and you should see:
     - `MCP_CAN`
     - `Adafruit_NeoPixel`
     - `TinyGPSPlus`

7. **Built-in Libraries** (no installation needed):
   - `SPI`, `SD`, `SoftwareSerial` are included with Arduino IDE

### Method 2: Manual ZIP Installation

If Library Manager fails:

1. **Download library ZIP files**:
   - MCP_CAN: https://github.com/coryjfowler/MCP_CAN_lib/archive/master.zip
   - Adafruit NeoPixel: https://github.com/adafruit/Adafruit_NeoPixel/archive/master.zip
   - TinyGPSPlus: https://github.com/mikalhart/TinyGPSPlus/archive/master.zip

2. **Install from ZIP**:
   - In Arduino IDE: `Sketch` → `Include Library` → `Add .ZIP Library...`
   - Select the downloaded ZIP file
   - Click `Open`
   - Repeat for all three libraries

3. **Restart Arduino IDE**

### Method 3: Command Line (arduino-cli)

#### Windows:
```cmd
arduino-cli lib install "MCP_CAN"
arduino-cli lib install "Adafruit NeoPixel"
arduino-cli lib install "TinyGPSPlus"
```

#### Linux/Mac:
```bash
arduino-cli lib install "MCP_CAN"
arduino-cli lib install "Adafruit NeoPixel"
arduino-cli lib install "TinyGPSPlus"
```

OR use the provided scripts:
- Windows: `scripts/install_libraries.bat`
- Linux/Mac: `bash scripts/install_libraries.sh`

---

## Common Errors and Solutions

### Error: "cannot open source file 'mcp_can.h'"

**Solution**:
1. Library not installed. Follow Method 1 above.
2. Verify installation: `File` → `Examples` → Should see "MCP_CAN" in the list
3. If still failing, close and restart Arduino IDE

### Error: "cannot open source file 'Adafruit_NeoPixel.h'"

**Solution**:
1. Install via Library Manager (search: "Adafruit NeoPixel")
2. Make sure to install dependencies if prompted
3. Restart Arduino IDE

### Error: "cannot open source file 'TinyGPS++.h'"

**Solution**:
1. Note the `++` in the library name - it's "TinyGPSPlus" (not "TinyGPS")
2. Install via Library Manager (search: "TinyGPSPlus")
3. Restart Arduino IDE

### Error: "cannot open source file 'SPI.h'" or "'SD.h'" or "'SoftwareSerial.h'"

**Solution**:
These are built-in libraries. Error usually means:
1. Arduino board not selected: `Tools` → `Board` → `Arduino Nano`
2. Arduino core not installed properly. Reinstall Arduino IDE from:
   https://www.arduino.cc/en/software

---

## Verifying Successful Installation

### Test Compilation

1. Open `MX5_Telemetry.ino` in Arduino IDE
2. Select board: `Tools` → `Board` → `Arduino Nano`
3. Select processor: `Tools` → `Processor` → `ATmega328P`
4. Click the ✓ (Verify) button
5. Should see: "Done compiling" (may show warnings, that's OK)

### Check Library Paths

Libraries are installed here:
- **Windows**: `C:\Users\[YourUsername]\Documents\Arduino\libraries\`
- **Mac**: `~/Documents/Arduino/libraries/`
- **Linux**: `~/Arduino/libraries/`

You should see folders:
- `MCP_CAN/` or `MCP_CAN_lib/`
- `Adafruit_NeoPixel/`
- `TinyGPSPlus/`

---

## Library Version Compatibility

### Recommended Versions:

| Library | Minimum Version | Tested Version |
|---------|----------------|----------------|
| MCP_CAN | 1.5.0 | 1.5.1 |
| Adafruit NeoPixel | 1.10.0 | 1.12.0 |
| TinyGPSPlus | 1.0.3 | 1.1.0 |

### Update Libraries:

1. Go to: `Sketch` → `Include Library` → `Manage Libraries...`
2. Find the library
3. Click `Update` if available

---

## Alternative Library Names

If you can't find a library, try these alternative names:

### MCP_CAN:
- `MCP_CAN` (preferred)
- `MCP_CAN_lib`
- `CAN_BUS_Shield`

### Adafruit NeoPixel:
- `Adafruit NeoPixel` (preferred)
- Search for "WS2812" will also show it

### TinyGPSPlus:
- `TinyGPSPlus` (preferred)
- Note: Do NOT install the old "TinyGPS" library (without Plus)

---

## Still Having Issues?

### Option 1: Check Arduino IDE Version
- Minimum required: Arduino IDE 1.8.0
- Recommended: Arduino IDE 2.x (newer interface)
- Download: https://www.arduino.cc/en/software

### Option 2: Check Internet Connection
- Library Manager requires internet to download
- If behind firewall/proxy, try manual ZIP installation

### Option 3: Clean Installation
1. Close Arduino IDE
2. Delete library folders from Arduino/libraries/
3. Reopen Arduino IDE
4. Reinstall libraries via Library Manager

### Option 4: Use Arduino IDE 2.x
- Newer version has better library management
- Download from: https://www.arduino.cc/en/software
- Migration guide: https://docs.arduino.cc/software/ide-v2/

---

## Quick Test Sketches

### Test MCP_CAN:
```cpp
#include <mcp_can.h>
MCP_CAN CAN(10);
void setup() {
  Serial.begin(115200);
  Serial.println("MCP_CAN library loaded successfully!");
}
void loop() {}
```

### Test Adafruit NeoPixel:
```cpp
#include <Adafruit_NeoPixel.h>
Adafruit_NeoPixel strip(30, 6, NEO_GRB + NEO_KHZ800);
void setup() {
  Serial.begin(115200);
  Serial.println("NeoPixel library loaded successfully!");
  strip.begin();
  strip.show();
}
void loop() {}
```

### Test TinyGPSPlus:
```cpp
#include <TinyGPS++.h>
TinyGPSPlus gps;
void setup() {
  Serial.begin(115200);
  Serial.println("TinyGPS++ library loaded successfully!");
}
void loop() {}
```

If these compile successfully, your libraries are installed correctly!

---

## Need More Help?

1. **Arduino Forum**: https://forum.arduino.cc/
2. **GitHub Issues**: Open an issue on this repository
3. **Documentation**: See `README.md` for full project details

---

## Summary Checklist

- [ ] Arduino IDE installed (1.8.0 or newer)
- [ ] MCP_CAN library installed
- [ ] Adafruit NeoPixel library installed
- [ ] TinyGPSPlus library installed
- [ ] Arduino Nano board selected in Tools menu
- [ ] ATmega328P processor selected in Tools menu
- [ ] Test compilation successful (✓ Verify button)
- [ ] No "cannot open source file" errors

Once all checked, you're ready to upload to your Arduino Nano!
