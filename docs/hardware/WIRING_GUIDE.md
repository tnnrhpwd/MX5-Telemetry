# 🔌 MX5-Telemetry Wiring Guide

Detailed step-by-step wiring instructions for the MX5-Telemetry system.

## ⚠️ Safety First

- **Disconnect vehicle battery** when making permanent connections
- **Use proper fusing** (2A recommended) on 12V power line
- **Test with multimeter** before connecting to Arduino
- **Ensure proper grounding** to vehicle chassis
- **Keep wires away** from heat sources and moving parts
- **Use heat shrink tubing** on all solder joints
- **Mount securely** to prevent damage from vibration

## 📦 Required Materials

### Wire and Connectors
- 22 AWG stranded wire (various colors for identification)
- Heat shrink tubing (various sizes)
- Dupont connectors (female-to-female)
- OBD-II male connector OR Y-splitter cable
- JST connectors (for LED strip)
- Crimp connectors
- Zip ties for cable management
- Wire labels

### Tools
- Wire strippers
- Soldering iron and solder
- Heat gun or lighter
- Multimeter
- Crimping tool
- Electrical tape
- Hot glue gun (optional, for strain relief)

## 🔋 Power System

### LM2596 Buck Converter Setup

1. **Input Side** (12V from vehicle):
   ```
   OBD-II Pin 16 (12V) → [2A Fuse] → Buck Converter IN+
   OBD-II Pin 5 (GND)  → Buck Converter IN-
   ```

2. **Output Adjustment** (BEFORE connecting Arduino):
   - Connect 12V input to buck converter
   - Measure output voltage with multimeter
   - Adjust potentiometer until output reads **exactly 5.0V**
   - Disconnect power

3. **Output Side** (5V to Arduino):
   ```
   Buck Converter OUT+ → Arduino Nano 5V pin
   Buck Converter OUT- → Arduino Nano GND pin
   ```

### Power Distribution

Create a common 5V and GND rail:

```
Arduino 5V Pin → Power Rail (+)
Arduino GND Pin → Ground Rail (-)

Connect to power rail:
- MCP2515 VCC
- SD Card VCC
- GPS Module VCC
- WS2812B 5V (connect directly to buck converter for high current)

Connect to ground rail:
- MCP2515 GND
- SD Card GND
- GPS Module GND
- WS2812B GND
- MOSFET Source
```

## 🚗 CAN Bus Connection (MCP2515)

### OBD-II Port Pinout

```
       OBD-II Female Connector (looking at pins)
   ┌─────────────────────┐
   │  8  7  6  5  4  3  2  1 │  Pin 6:  CAN-H
   │    16 15 14 13 12 11 10 9│  Pin 14: CAN-L
   └─────────────────────┘     Pin 5:  GND
                               Pin 16: 12V
```

### MCP2515 Module Wiring

| MCP2515 Pin | Arduino Pin | Wire Color (suggested) |
|-------------|-------------|------------------------|
| VCC         | 5V          | Red                    |
| GND         | GND         | Black                  |
| CS          | D10         | Orange                 |
| SO (MISO)   | D12         | Blue                   |
| SI (MOSI)   | D11         | Green                  |
| SCK         | D13         | Yellow                 |
| INT         | (not used)  | -                      |

### CAN Transceiver Connections

| TJA1050 Pin | Connection |
|-------------|------------|
| CANH        | OBD-II Pin 6 (CAN-H) |
| CANL        | OBD-II Pin 14 (CAN-L) |
| GND         | OBD-II Pin 5 (GND) |

**Note**: Most MCP2515 modules have the TJA1050 transceiver already integrated.

### Connection Steps

1. **Strip wires** and tin ends with solder
2. **Connect to OBD-II pins** (use OBD-II male connector):
   - Pin 6 (CAN-H) → Orange wire → MCP2515 CANH
   - Pin 14 (CAN-L) → White wire → MCP2515 CANL
   - Pin 5 (GND) → Black wire → MCP2515 GND
3. **Apply heat shrink** to all solder joints
4. **Test continuity** with multimeter
5. **Connect SPI pins** to Arduino using Dupont wires

## 💾 SD Card Module (WWZMDIB MicroSD Reader)

### WWZMDIB Module Overview

The WWZMDIB is a popular MicroSD card reader module that uses SPI communication. It typically includes:
- Built-in voltage regulator (can accept 3.3V or 5V)
- Level shifters for SD card protection
- Card detection pin (optional)
- Compact design with 6-pin header

### Pin Configuration

| WWZMDIB Pin | Arduino Nano Pin | Wire Color (suggested) | Description |
|-------------|------------------|------------------------|-------------|
| GND         | GND              | Black                  | Ground      |
| VCC         | 5V               | Red                    | Power (5V)  |
| MISO        | D12              | Blue                   | Master In Slave Out |
| MOSI        | D11              | Green                  | Master Out Slave In |
| SCK         | D13              | Yellow                 | SPI Clock   |
| CS          | D4               | Purple                 | Chip Select |

**Note**: Some WWZMDIB modules may have additional pins (CD for card detect) - these are optional and not required for basic operation.

### Module Identification

The WWZMDIB module typically has:
- Blue PCB with white silkscreen labeling
- MicroSD card slot on top
- 6 pins on one side (or 8 pins with CD/GND duplicates)
- Small size (~15mm x 20mm)

### Connection Steps

1. **Orient the module**: SD card slot should face up, pins facing toward you
2. **Identify pin 1 (GND)**: Usually marked on silkscreen, typically leftmost pin
3. **Connect power**:
   - GND → Arduino GND (black wire)
   - VCC → Arduino 5V (red wire)
4. **Connect SPI pins** (shared with CAN module):
   - MISO → Arduino D12 (blue wire)
   - MOSI → Arduino D11 (green wire)
   - SCK → Arduino D13 (yellow wire)
5. **Connect chip select**:
   - CS → Arduino D4 (purple wire)

### Wiring Diagram

```
WWZMDIB MicroSD Reader          Arduino Nano
┌─────────────────┐             ┌──────────────┐
│   [SD SLOT]     │             │              │
│                 │             │              │
│  GND ○──────────┼─────────────┤ GND          │
│  VCC ○──────────┼─────────────┤ 5V           │
│ MISO ○──────────┼─────────────┤ D12 (MISO)   │
│ MOSI ○──────────┼─────────────┤ D11 (MOSI)   │
│  SCK ○──────────┼─────────────┤ D13 (SCK)    │
│   CS ○──────────┼─────────────┤ D4           │
└─────────────────┘             └──────────────┘
```

### Important Notes

- **Shared SPI Bus**: SD module shares SPI bus with CAN module (D11, D12, D13)
- **Unique CS Pin**: Only CS pin (D4) is unique to SD module
- **5V Safe**: WWZMDIB has built-in voltage regulation and level shifters
- **Card Format**: Use FAT32 formatted MicroSD card (32GB or smaller recommended)
- **Card Speed**: Class 10 or UHS-I recommended for fast logging

### MicroSD Card Preparation

1. **Format card**: Use SD Card Formatter tool (FAT32)
2. **Card size**: 8GB to 32GB recommended (larger cards may be slower)
3. **Insert card**: Push until it clicks, label facing up
4. **Test detection**: Card should be detected on Arduino startup

## 💡 WS2812B LED Strip (Slave Arduino)

### Dual Arduino Architecture

The LED strip is controlled by a **separate Slave Arduino** to avoid interrupt conflicts with SD card logging. See [MASTER_SLAVE_ARCHITECTURE.md](MASTER_SLAVE_ARCHITECTURE.md) for details.

### Master to Slave Communication

| Master Pin | Slave Pin | Description |
|------------|-----------|-------------|
| D6         | D2        | Serial data (9600 baud bit-bang) |
| GND        | GND       | Common ground (REQUIRED) |

```
Master Arduino (Logger)         Slave Arduino (LED Controller)
┌──────────────────┐            ┌──────────────────┐
│                  │            │                  │
│  D6 (TX) ────────┼────────────┤ D2 (RX)          │
│                  │            │                  │
│  GND ────────────┼────────────┤ GND              │
│                  │            │                  │
└──────────────────┘            └──────────────────┘
```

**IMPORTANT:**
- Master uses **D6** (NOT D1/TX which is USB Serial)
- Slave uses **D2** (SoftwareSerial RX)
- Communication is **9600 baud** (bit-bang on Master, SoftwareSerial on Slave)
- **Common ground is essential** - without it, serial communication will fail!

### Power Considerations

LED strips draw significant current:
- Each LED: ~60mA at full white brightness
- 20 LEDs: up to 1.2A

**Critical**: Power the LED strip directly from the buck converter, NOT from Arduino's 5V pin!

### Slave Arduino Wiring

| Component | Slave Pin | Notes |
|-----------|-----------|-------|
| LED Strip Data | D5 | 470Ω resistor recommended |
| LED Strip 5V | Buck Converter OUT+ | Use thick wire (18-20 AWG) |
| LED Strip GND | Common GND | Shared with Arduino GND |
| Haptic Motor + | D3 | Optional vibration feedback |
| Haptic Motor - | GND | |
| Master TX | D2 | SoftwareSerial RX |
| Master GND | GND | Common ground |

### Wiring Diagram

```
Buck Converter OUT+ ────────────► LED Strip 5V/VCC
Buck Converter OUT- ────────────► LED Strip GND
Slave Arduino D5 ──[470Ω]───────► LED Strip Data In
                     (resistor optional but recommended)

Master-Slave Connection:
Master D6 ──────────────────────► Slave D2
Master GND ─────────────────────► Slave GND

LED Strip Power:
    Add 1000µF capacitor across 5V and GND near strip
```

### Connection Table

| LED Strip Wire | Connection | Notes |
|----------------|------------|-------|
| Red (5V)       | Buck Converter OUT+ | Use thick wire (18-20 AWG) |
| Black (GND)    | Buck Converter OUT- | Common ground with Arduino |
| White/Green (Data) | Arduino D6 | Use 470Ω resistor in series |

### Best Practices

1. **Solder connections** for reliability (avoid connectors on high-current lines)
2. **Use thick wire** for power (18-20 AWG)
3. **Keep data wire short** (<1 meter if possible)
4. **Add capacitor** (1000µF, 6.3V or higher) across power at LED strip
5. **Test with low brightness first** before full brightness

## 📡 GPS Module (Neo-6M)

| GPS Module Pin | Arduino Pin | Wire Color |
|----------------|-------------|------------|
| VCC            | 5V          | Red        |
| GND            | GND         | Black      |
| TX             | D2 (RX)     | Yellow     |
| RX             | D3 (TX)     | Green      |

**Note**: GPS TX connects to Arduino RX (D2), and GPS RX connects to Arduino TX (D3)

### Antenna Placement

- Mount GPS module near window or windshield
- Keep antenna away from metal surfaces (at least 5cm clearance)
- Ensure clear view of sky for best satellite reception
- Use extension cable if needed (4-conductor)

## 🎥 GoPro Power Control (MOSFET Circuit)

### Component Selection

**MOSFET Requirements**:
- N-channel logic-level MOSFET
- VDS ≥ 20V
- ID ≥ 2A
- RDS(on) < 0.1Ω
- Suggested: IRF540N, IRLZ44N, or 2N7000

### Circuit Diagram

```
                  ┌──────────────┐
                  │   IRF540N    │
Arduino D5 ───┬───┤ Gate         │
              │   │              │
           [10kΩ] │              │
              │   │              │
         GND──┴───┤ Source       │
                  │              │
                  │              │  To GoPro
    5V+ ──────────┤ Drain        ├─────► USB 5V+
    (Buck Conv.)  │              │
                  └──────────────┘

    GoPro USB GND ──────► Common GND
```

### Component Connections

| Connection | From | To |
|------------|------|-----|
| Gate       | Arduino D5 | MOSFET Gate pin |
| Pull-down Resistor | MOSFET Gate | GND (10kΩ) |
| Source     | GND | MOSFET Source pin |
| Drain      | Buck Converter 5V | MOSFET Drain pin |
| Output     | MOSFET Drain | GoPro USB 5V+ |

### Assembly Steps

1. **Solder MOSFET** to small perfboard or use breadboard
2. **Add 10kΩ pull-down resistor** between Gate and Source
3. **Connect Gate** to Arduino D5
4. **Cut GoPro USB cable** 5V+ wire (red wire)
5. **Splice MOSFET** into 5V+ line:
   - Buck converter 5V → MOSFET Drain
   - MOSFET Source → GoPro USB 5V+
6. **Leave GND wire intact** (common ground)
7. **Insulate all connections** with heat shrink
8. **Test with multimeter**:
   - D5 LOW → No voltage at MOSFET output
   - D5 HIGH → 5V at MOSFET output

## 🧰 Complete Assembly Checklist

### Before Powering On

- [ ] All VCC connections go to 5V rail
- [ ] All GND connections go to common ground
- [ ] Buck converter output verified at 5.0V
- [ ] No short circuits between power and ground
- [ ] All solder joints are clean and secure
- [ ] Heat shrink applied to all exposed connections
- [ ] SPI pins correctly connected (D10-D13)
- [ ] GPS TX/RX not reversed
- [ ] LED strip powered from buck converter, not Arduino
- [ ] MOSFET pull-down resistor installed
- [ ] All modules mechanically secured
- [ ] Wires secured with zip ties
- [ ] No wires near hot or moving parts

### After Powering On (Vehicle Off, Ignition On)

- [ ] LED startup animation displays
- [ ] Serial monitor shows initialization messages
- [ ] No smoke or burning smell
- [ ] Buck converter not excessively hot
- [ ] All modules receiving power (check with multimeter)

### Testing Sequence

1. **Bench Test** (Arduino only, USB power):
   - Upload firmware
   - Verify Serial output
   - No modules connected yet

2. **Module Test** (one at a time, 5V bench power):
   - Connect CAN module → Test CAN init
   - Connect SD module → Test SD card detection
   - Connect GPS module → Test GPS data reception
   - Connect LED strip → Test LED animations

3. **Integration Test** (all modules, 5V bench power):
   - All modules connected
   - Verify no conflicts
   - Check current draw (<250mA without LEDs)

4. **Vehicle Test** (12V vehicle power):
   - Connect to OBD-II port
   - Turn on ignition
   - Verify CAN data reception
   - Start engine and check RPM reading

5. **Full System Test** (driving):
   - Verify LED display tracks RPM
   - Check GoPro power control
   - Verify GPS lock
   - Confirm SD card logging
   - Monitor for any errors

## 🛠️ Troubleshooting Wire Connections

### No Power to Arduino

- Check buck converter input (12V present?)
- Check buck converter output (5.0V present?)
- Check fuse continuity
- Verify ground connection to vehicle chassis

### CAN Bus Not Working

- Verify CAN-H and CAN-L not swapped
- Check continuity from OBD-II pins to MCP2515
- Ensure proper ground connection
- Check 120Ω termination resistor (usually built into module)

### SD Card Issues

- Verify CS pin connection (D4)
- Check shared SPI pins (D11, D12, D13)
- Ensure MicroSD card is fully inserted (should click)
- Format card as FAT32 (use SD Card Formatter tool)
- Try different SD card (Class 10 recommended)
- Check for bent pins on WWZMDIB module
- Verify VCC receives stable 5V
- Test with a known-good SD card first

### LED Strip Issues

- Check data pin connection (Slave D5)
- Verify LED strip receives adequate power (thick wires from buck converter)
- Ensure common ground between Slave Arduino and LED strip
- Try adding 470Ω resistor to data line

### Master-Slave Communication Issues

- Check wire from **Master D6** to **Slave D2**
- Verify **common ground** between both Arduinos
- Confirm both use **9600 baud** (Master bit-bang, Slave SoftwareSerial)
- Master logs should show `LED->Slave: RPM:0`, `LED->Slave: SPD:0`, etc.
- If Slave shows red error animation, it's not receiving valid commands
- Connect Slave to USB Serial Monitor (115200) to see `RX:` debug output

### GPS Not Working

- Verify TX/RX not reversed
- Check antenna has clear sky view
- Wait 2-5 minutes for cold start GPS lock
- Verify baud rate (9600)

### MOSFET Issues

- Check Gate connection to D5
- Verify pull-down resistor (10kΩ)
- Test MOSFET with multimeter (should switch)
- Ensure MOSFET can handle current

## 📸 Installation Photos (Recommended)

Take photos during installation for reference:

1. OBD-II connector pinout
2. Buck converter adjustment
3. Complete wiring before closing enclosure
4. Final installation in vehicle
5. GPS antenna placement
6. LED strip mounting

These will be invaluable for troubleshooting later!

## 🔐 Final Tips

- **Label all wires** with wire labels or colored tape
- **Create a wiring diagram** specific to your installation
- **Use proper strain relief** on all connections
- **Test incrementally** - don't connect everything at once
- **Keep spare parts** (fuses, connectors, wire)
- **Document your build** for future reference

---

**Ready to wire your system?** Follow these steps carefully, test thoroughly, and enjoy your custom telemetry system!
