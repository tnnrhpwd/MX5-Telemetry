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

## 💾 SD Card Module

| SD Module Pin | Arduino Pin | Wire Color |
|---------------|-------------|------------|
| VCC           | 5V          | Red        |
| GND           | GND         | Black      |
| MISO          | D12         | Blue       |
| MOSI          | D11         | Green      |
| SCK           | D13         | Yellow     |
| CS            | D4          | Purple     |

**Important**: 
- SD module shares SPI bus with CAN (D11, D12, D13)
- Only CS pin is unique (D4)
- Ensure SD module is 5V tolerant OR use level shifters

## 💡 WS2812B LED Strip

### Power Considerations

LED strips draw significant current:
- Each LED: ~60mA at full white brightness
- 30 LEDs: up to 1.8A

**Critical**: Power the LED strip directly from the buck converter, NOT from Arduino's 5V pin!

### Wiring Diagram

```
Buck Converter OUT+ ────────────► LED Strip 5V/VCC
Buck Converter OUT- ────────────► LED Strip GND
Arduino D6 ──[470Ω]──────────────► LED Strip Data In
                     (resistor optional but recommended)

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
- Ensure SD module is 5V tolerant
- Try different SD card

### LED Strip Issues

- Check data pin connection (D6)
- Verify LED strip receives adequate power (thick wires)
- Ensure common ground between Arduino and LED strip
- Try adding 470Ω resistor to data line

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
