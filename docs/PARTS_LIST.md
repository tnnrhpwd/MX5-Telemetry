# 🛒 MX5-Telemetry Parts List

Complete bill of materials (BOM) for building the MX5-Telemetry system.

## 💰 Budget Overview

| Category | Estimated Cost (USD) |
|----------|---------------------|
| Electronics | $35-45 |
| Wiring & Connectors | $15-25 |
| Enclosure & Mounting | $10-20 |
| Tools (if needed) | $20-50 |
| **Total** | **$80-140** |

*Note: Prices are approximate and vary by supplier/location.*

---

## 📦 Core Electronics

### Microcontroller

| Item | Specifications | Qty | Price | Link/Notes |
|------|---------------|-----|-------|------------|
| Arduino Nano V3.0 | ATmega328P, 16MHz, 5V | 1 | $3-8 | Amazon, AliExpress, eBay |

**Alternatives**: Arduino Nano Every, Arduino Nano 33 IoT (requires code modifications)

---

### CAN Bus Module

| Item | Specifications | Qty | Price | Link/Notes |
|------|---------------|-----|-------|------------|
| MCP2515 CAN Module | MCP2515 + TJA1050, 8MHz or 16MHz crystal | 1 | $3-7 | Must specify 16MHz crystal version |

**Critical**: Ensure your module has a **16MHz crystal** (check product description or visually inspect). The code is configured for 16MHz. If you have an 8MHz version, change `MCP_16MHZ` to `MCP_8MHZ` in the code.

**Recommended suppliers**: 
- Amazon: Search "MCP2515 16MHz"
- AliExpress: Look for "MCP2515 TJA1050 16MHz"

---

### LED Strip

| Item | Specifications | Qty | Price | Link/Notes |
|------|---------------|-----|-------|------------|
| WS2812B LED Strip | 30 LEDs/meter, 5V, addressable RGB | 1m | $5-12 | Waterproof (IP65) recommended |

**Options**:
- **30 LEDs** (1 meter): Good for compact dashboard mounting
- **60 LEDs** (1 meter): More resolution, higher power consumption
- **144 LEDs** (1 meter): Maximum resolution, requires 5A+ power supply

**Note**: Adjust `LED_COUNT` in code to match your LED count.

---

### GPS Module

| Item | Specifications | Qty | Price | Link/Notes |
|------|---------------|-----|-------|------------|
| Neo-6M GPS Module | UART, external antenna | 1 | $8-15 | Includes ceramic antenna |

**Features to look for**:
- External antenna (better reception than internal)
- EEPROM for backup (retains satellite data after power off)
- LED indicators (helpful for debugging)

---

### SD Card Module

| Item | Specifications | Qty | Price | Link/Notes |
|------|---------------|-----|-------|------------|
| MicroSD Card Module | SPI interface, 5V tolerant | 1 | $1-3 | Look for "Arduino SD Card Module" |
| MicroSD Card | Class 10, 8-32GB, FAT32 | 1 | $5-10 | SanDisk or Samsung recommended |

**SD Card Notes**:
- Use Class 10 or higher for reliable write speeds
- Format as FAT32 before first use
- 32GB max for FAT32 compatibility
- Keep a spare card

---

### Power Supply

| Item | Specifications | Qty | Price | Link/Notes |
|------|---------------|-----|-------|------------|
| LM2596 Buck Converter | 12V → 5V, 3A output | 1 | $2-5 | Adjustable voltage (use potentiometer) |
| 2A Blade Fuse + Holder | 12V automotive | 1 | $2-5 | For OBD-II power protection |

**Buck Converter Notes**:
- Must be adjustable (has potentiometer)
- 3A minimum output rating (for LED strip)
- Look for "LM2596 DC-DC Buck Converter"

---

### GoPro Power Control

| Item | Specifications | Qty | Price | Link/Notes |
|------|---------------|-----|-------|------------|
| N-Channel MOSFET | IRF540N or IRLZ44N | 1 | $0.50-2 | Logic-level, VDS ≥20V, ID ≥2A |
| 10kΩ Resistor | 1/4W | 1 | $0.10 | Pull-down resistor for MOSFET gate |
| Small Perfboard | 3×7cm | 1 | $1-3 | For mounting MOSFET circuit |

**MOSFET Alternatives**:
- IRF540N (most common, cheap)
- IRLZ44N (better logic-level performance)
- 2N7000 (lower current, works for GoPro)

---

## 🔌 Wiring & Connectors

| Item | Specifications | Qty | Price | Notes |
|------|---------------|-----|-------|-------|
| 22 AWG Stranded Wire | Various colors | 5m | $5-10 | Red, black, green, blue, yellow |
| 18 AWG Stranded Wire | For LED strip power | 2m | $3-5 | Red and black only |
| Heat Shrink Tubing Kit | Assorted sizes | 1 set | $5-10 | Various diameters |
| Dupont Jumper Wires | Female-to-female | 20pcs | $3-5 | For module connections |
| OBD-II Extension Cable | Male-to-female, 1m | 1 | $8-15 | Optional: for easy access |
| JST Connectors | 3-pin, for LED strip | 2pcs | $1-3 | Makes LED strip detachable |

---

## 🏠 Enclosure & Mounting

| Item | Specifications | Qty | Price | Notes |
|------|---------------|-----|-------|-------|
| Project Enclosure | 100×60×25mm plastic | 1 | $3-8 | Weatherproof recommended |
| Zip Ties | 100mm, various colors | 20pcs | $2-5 | Cable management |
| Double-Sided Tape | 3M VHB or similar | 1 roll | $5-10 | For mounting enclosure |
| Velcro Strips | For removable mounting | 1 set | $3-7 | Alternative to tape |

---

## 🔧 Tools Required

If you don't already have these, budget accordingly:

| Tool | Purpose | Approx. Cost |
|------|---------|--------------|
| Soldering Iron + Solder | Wire connections | $15-40 |
| Wire Strippers | Strip wire insulation | $5-15 |
| Multimeter | Voltage/continuity testing | $10-25 |
| Heat Gun or Lighter | Shrink tubing | $10-30 |
| Crimping Tool | Crimp connectors | $10-25 |
| Small Screwdriver Set | Module mounting | $5-15 |

---

## 📋 Optional / Recommended

| Item | Purpose | Qty | Price | Notes |
|------|---------|-----|-------|-------|
| Mini Breadboard | Testing before soldering | 1 | $2-5 | 400 tie-points |
| Logic Level Converter | If SD module is 3.3V only | 1 | $2-5 | Bi-directional, 4-channel |
| 1000µF Capacitor | LED strip power filtering | 1 | $0.50-2 | 6.3V or higher |
| 470Ω Resistor | LED data line protection | 1 | $0.10 | 1/4W |
| Spare Fuses | Replacement fuses | 3 | $1-3 | 2A blade fuses |
| Cable Labels | Wire identification | 1 sheet | $2-5 | Printable or write-on |
| Hot Glue Gun + Sticks | Strain relief | 1 | $5-10 | For connector reinforcement |

---

## 🛍️ Where to Buy

### Recommended Suppliers

#### 🚚 **Fast Shipping (1-3 days)**
- **Amazon** - Prime shipping, easy returns, higher prices
  - Search: "Arduino Nano", "MCP2515", "WS2812B"
  
- **Adafruit** - Quality components, US-based, excellent support
  - [www.adafruit.com](https://www.adafruit.com)
  
- **SparkFun** - Quality electronics, tutorials, US-based
  - [www.sparkfun.com](https://www.sparkfun.com)

#### 💰 **Budget Options (2-4 weeks shipping)**
- **AliExpress** - Very cheap, long shipping times
  - Search: "Arduino Nano ATmega328P", "MCP2515 16MHz"
  
- **eBay** - Mix of domestic and international sellers
  - Check seller location for shipping estimate
  
- **Banggood** - Similar to AliExpress, slightly faster
  - [www.banggood.com](https://www.banggood.com)

#### 🏪 **Local Options**
- **Micro Center** - If near a store, excellent prices
- **Fry's Electronics** - Limited locations
- **RadioShack** - Mostly closed, but some still exist

---

## 📦 Pre-Made Kits

Some sellers offer "Arduino CAN bus kits" that include most components. Search for:
- "Arduino CAN bus logger kit"
- "MCP2515 Arduino starter kit"

**Pros**: Convenient, often cheaper bundled
**Cons**: May include wrong crystal frequency, lower quality components

---

## 🚗 Vehicle-Specific Parts

### OBD-II Connection

**Option 1: OBD-II Extension Cable** (Recommended)
- Allows easy disconnect
- Doesn't block OBD-II port permanently
- Can use for diagnostics while system is installed
- **Cost**: $8-15

**Option 2: Direct OBD-II Male Connector**
- Permanent installation
- Requires cutting/splicing
- More compact
- **Cost**: $5-10

### GoPro USB Cable

- **Original GoPro USB Cable** - Most reliable
- **Third-party USB-C Cable** - Works, cheaper
- **Splice existing cable** - Cut and add MOSFET inline

---

## 💡 LED Strip Options

### LED Density Comparison

| LEDs/meter | Visual Quality | Power Consumption | Price | Recommended For |
|------------|---------------|-------------------|-------|-----------------|
| 30 LEDs    | Good          | ~1.8A max         | $5-8  | Dashboard, compact |
| 60 LEDs    | Better        | ~3.6A max         | $8-12 | Windshield, larger displays |
| 144 LEDs   | Best          | ~8.6A max         | $15-25 | Professional setups (requires 10A supply) |

**Recommendation**: Start with 30 LEDs/meter (1 meter = 30 LEDs) for reliability and lower power consumption.

### Waterproof vs Non-Waterproof

| Type | Protection | Use Case | Price Difference |
|------|-----------|----------|------------------|
| IP30 (Non-waterproof) | None | Indoor, dry environment | Baseline |
| IP65 (Splash-resistant) | Silicone coating | Most car interiors | +20-30% |
| IP67 (Waterproof) | Silicone tube | Outdoor, under hood | +40-50% |

**Recommendation**: IP65 for car interior (protects against humidity and accidental spills).

---

## 🔋 Power Budget Calculator

Calculate your power requirements:

```
Component Power Draw (at 5V):
- Arduino Nano:         50 mA
- MCP2515 Module:       30 mA
- GPS Module:           40 mA
- SD Card Module:      100 mA (active writing)
- WS2812B LEDs:         60 mA per LED at full brightness

Example with 30 LEDs:
- LEDs at 50% brightness: 30 LEDs × 30 mA = 900 mA
- Total system:           50 + 30 + 40 + 100 + 900 = 1120 mA (1.12A)

Recommended buck converter: 3A minimum
```

---

## ✅ Shopping Checklist

Print this list and check off items as you order:

### Essential Components
- [ ] Arduino Nano (ATmega328P, 5V, 16MHz)
- [ ] MCP2515 CAN Module (16MHz crystal!)
- [ ] WS2812B LED Strip (30 LEDs, 1 meter)
- [ ] Neo-6M GPS Module (with external antenna)
- [ ] MicroSD Card Module (SPI, 5V tolerant)
- [ ] MicroSD Card (8-32GB, Class 10, FAT32)
- [ ] LM2596 Buck Converter (12V→5V, 3A)
- [ ] N-Channel MOSFET (IRF540N or IRLZ44N)
- [ ] 10kΩ Resistor (1/4W, for MOSFET)
- [ ] 2A Blade Fuse + Holder

### Wiring & Connectors
- [ ] 22 AWG Stranded Wire (5 meters, various colors)
- [ ] 18 AWG Stranded Wire (2 meters, red + black)
- [ ] Heat Shrink Tubing Kit (assorted sizes)
- [ ] Dupont Jumper Wires (female-to-female, 20pcs)
- [ ] OBD-II Extension Cable OR Male Connector
- [ ] JST Connectors (optional, for LED strip)

### Enclosure & Mounting
- [ ] Project Enclosure (100×60×25mm)
- [ ] Zip Ties (100mm, 20+ pieces)
- [ ] Double-Sided Tape OR Velcro Strips

### Optional Components
- [ ] 1000µF Capacitor (for LED strip power filtering)
- [ ] 470Ω Resistor (for LED data line protection)
- [ ] Logic Level Converter (if SD module is 3.3V only)
- [ ] Mini Breadboard (for testing)
- [ ] Spare Fuses (2A blade fuses)

### Tools (if you don't have them)
- [ ] Soldering Iron + Solder
- [ ] Wire Strippers
- [ ] Multimeter
- [ ] Heat Gun or Lighter
- [ ] Screwdriver Set

---

## 💾 Save Money Tips

1. **Buy in bulk**: Many components sold in 5-packs for slight discount
2. **Use coupon codes**: Check RetailMeNot, Honey for Amazon/AliExpress coupons
3. **Wait for sales**: Prime Day, Black Friday, 11.11 (AliExpress)
4. **Bundle shipping**: Order multiple items from same seller
5. **Check local makers**: Sometimes cheaper to buy from local hackerspace/makerspace
6. **Reuse what you have**: Old USB cables, wire from other projects, etc.

---

## ⏱️ Lead Time Planning

| Supplier | Typical Shipping | Order By | Total Time |
|----------|-----------------|----------|------------|
| Amazon (Prime) | 1-2 days | Today | 1-2 days |
| Amazon (Non-Prime) | 3-5 days | Today | 3-5 days |
| Adafruit/SparkFun | 3-7 days | Today | 3-7 days |
| AliExpress | 15-45 days | 4-6 weeks ahead | 4-6 weeks |
| eBay (varies) | 1-30 days | Check listing | Varies |

**Recommendation**: Order from AliExpress for budget build (plan 6 weeks ahead), or Amazon/Adafruit for fast build (1 week).

---

## 📧 Example Order (Budget Build)

**Example AliExpress Cart** (~$35 shipped):

1. Arduino Nano ATmega328P × 1 = $3.50
2. MCP2515 16MHz CAN Module × 1 = $4.20
3. WS2812B LED Strip 30LEDs/m × 1m = $6.80
4. Neo-6M GPS Module × 1 = $9.50
5. MicroSD Card Module × 1 = $1.80
6. LM2596 Buck Converter × 1 = $2.10
7. IRF540N MOSFET × 5pcs = $1.50
8. Dupont Jumper Wires 40pcs = $2.30
9. Heat Shrink Tubing Kit = $3.50

**Total**: ~$35 + $0-5 shipping

**Add locally** (same-day from hardware store):
- MicroSD Card 16GB = $8
- Wire (22 AWG + 18 AWG) = $10
- Fuse + holder = $5
- Enclosure = $5
- Zip ties = $3

**Grand Total**: ~$66

---

**Ready to order?** Use this parts list as your shopping guide. Double-check component specifications before purchasing!

**Questions?** Open an issue on GitHub or check the Troubleshooting section of the main README.
