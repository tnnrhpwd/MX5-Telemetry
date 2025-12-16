# 🛒 MX5-Telemetry Parts List

Complete bill of materials (BOM) for building the MX5-Telemetry system.

## 💰 Budget Overview

| Category | Estimated Cost (USD) |
|----------|---------------------|
| Raspberry Pi 4B + Accessories | $60-80 |
| ESP32-S3 Round Display | $25-35 |
| Arduino Nano + CAN Module | $10-20 |
| MCP2515 Modules (x3 total) | $10-20 |
| LED Strip + Power | $15-25 |
| BLE TPMS Sensors (x4) | $25-40 |
| Wiring & Connectors | $15-25 |
| **Total** | **$160-245** |

*Note: Prices are approximate and vary by supplier/location.*

---

## 🖥️ Raspberry Pi 4B (CAN Hub)

| Item | Specifications | Qty | Price | Notes |
|------|---------------|-----|-------|-------|
| Raspberry Pi 4B | 2GB+ RAM | 1 | $35-55 | 4GB recommended |
| MicroSD Card | 32GB Class 10 | 1 | $8-15 | SanDisk recommended |
| Pi Power Supply | 5V 3A USB-C | 1 | $10-15 | Official Pi PSU recommended |
| MCP2515 CAN Module | 8MHz crystal | 2 | $6-14 | HS-CAN + MS-CAN |
| Heatsink/Cooling | Passive or fan | 1 | $5-10 | Recommended for Pi 4 |

### Pi GPIO Connections
- **SPI Bus** (shared): GPIO 10 (MOSI), GPIO 9 (MISO), GPIO 11 (SCLK)
- **MCP2515 #1 CS**: GPIO 8 (CE0) - HS-CAN
- **MCP2515 #2 CS**: GPIO 7 (CE1) - MS-CAN
- **Interrupts**: GPIO 25 (HS), GPIO 24 (MS)

---

## 📺 ESP32-S3 Round Display

| Item | Specifications | Qty | Price | Notes |
|------|---------------|-----|-------|-------|
| Waveshare ESP32-S3-Touch-LCD-1.85 | 360x360 IPS, Touch | 1 | $25-35 | Built-in IMU (QMI8658) |
| USB-C Cable | Data capable | 1 | $5-10 | For Pi connection |

**Built-in Features**:
- 1.85" Round IPS LCD (360×360)
- Capacitive touch (CST816)
- QMI8658 IMU (accelerometer/gyroscope)
- ESP32-S3 (dual-core 240MHz, BLE 5.0)

---

## 🎯 Arduino Nano (LED Controller)

| Item | Specifications | Qty | Price | Notes |
|------|---------------|-----|-------|-------|
| Arduino Nano V3.0 | ATmega328P, 16MHz, 5V | 1 | $3-8 | Clone or official |
| MCP2515 CAN Module | MCP2515 + TJA1050, 8MHz crystal | 1 | $3-7 | Arduino's dedicated CAN |

**Alternatives**: Arduino Nano Every (requires code modifications)

---

## 💡 LED Strip

| Item | Specifications | Qty | Price | Notes |
|------|---------------|-----|-------|-------|
| WS2812B LED Strip | 20 LEDs, 5V, addressable RGB | 1 | $5-12 | IP65 waterproof recommended |

**Options**:
- **20 LEDs**: Recommended for shift light bar
- **30 LEDs/meter**: Good resolution
- **60 LEDs/meter**: Maximum resolution

---

## 📡 BLE TPMS Sensors

| Item | Specifications | Qty | Price | Notes |
|------|---------------|-----|-------|-------|
| BLE TPMS Cap Sensors | Bluetooth 4.0, cap-mount | 4 | $25-40 | One per tire |

**Features to look for**:
- BLE broadcast (not proprietary app only)
- Pressure range: 0-80 PSI
- Temperature sensing
- Battery included

---

## 🔌 CAN Bus Interface

### OBD-II Connection

| Item | Specifications | Qty | Price | Notes |
|------|---------------|-----|-------|-------|
| OBD-II Extension Cable | Male-to-female, 1m | 1 | $8-15 | For easier access |
| OBD-II Breakout | Screw terminals | 1 | $5-10 | Alternative to splicing |

### MX5 NC CAN Bus Pins
- **HS-CAN (500k)**: Pin 6 (High), Pin 14 (Low)
- **MS-CAN (125k)**: Pin 3 (High), Pin 11 (Low)
- **Ground**: Pin 5
- **12V Power**: Pin 16

---

## 🔋 Power Supply

| Item | Specifications | Qty | Price | Notes |
|------|---------------|-----|-------|-------|
| LM2596 Buck Converter | 12V → 5V, 3A output | 1 | $2-5 | Adjustable voltage |
| 2A Blade Fuse + Holder | 12V automotive | 1 | $2-5 | Protection |

---

## 🔌 Wiring & Connectors

| Item | Specifications | Qty | Price | Notes |
|------|---------------|-----|-------|-------|
| 22 AWG Stranded Wire | Various colors | 5m | $5-10 | Red, black, green, blue, yellow |
| 18 AWG Stranded Wire | For LED strip power | 2m | $3-5 | Red and black only |
| Heat Shrink Tubing Kit | Assorted sizes | 1 set | $5-10 | Various diameters |
| Dupont Jumper Wires | Female-to-female | 20pcs | $3-5 | For module connections |
| JST Connectors | 3-pin, for LED strip | 2pcs | $1-3 | Makes LED strip detachable |

---

## 🖼️ Display Output (Optional)

For Pioneer head unit HDMI input:

| Item | Specifications | Qty | Price | Notes |
|------|---------------|-----|-------|-------|
| Micro HDMI to HDMI Cable | 1-2m | 1 | $5-10 | Pi 4 uses micro HDMI |
| Pioneer AVH-W4500NEX | 800x480 HDMI input | 1 | N/A | Or similar HDMI-capable head unit |

Alternative: 7" Raspberry Pi HDMI display (~$30-50)

---

## 🏠 Enclosure & Mounting

| Item | Specifications | Qty | Price | Notes |
|------|---------------|-----|-------|-------|
| Project Enclosure | For Pi + modules | 1 | $10-20 | 3D printed or purchased |
| Zip Ties | 100mm, various colors | 20pcs | $2-5 | Cable management |
| Double-Sided Tape | 3M VHB or similar | 1 roll | $5-10 | For mounting |
| Velcro Strips | For removable mounting | 1 set | $3-7 | Alternative to tape |

---

## 🔧 Tools Required

If you don't already have these:

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
| 1000µF Capacitor | LED strip power filtering | 1 | $0.50-2 | 6.3V or higher |
| 470Ω Resistor | LED data line protection | 1 | $0.10 | 1/4W |
| Spare Fuses | Replacement fuses | 3 | $1-3 | 2A blade fuses |
| Shielded Cable | Pi to ESP32 serial | 1m | $3-5 | EMI protection |
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
