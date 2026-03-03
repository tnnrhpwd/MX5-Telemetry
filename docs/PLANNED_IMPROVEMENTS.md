# Planned Hardware Improvements

**Vehicle:** Mazda MX-5 NC (2006-2015) | **System:** Pi 4B + ESP32-S3 + Arduino Nano + 3× MCP2515

---

## 1. Live 12V Automotive Voltage Monitoring

**Goal:** Read the live 12V+ source voltage (before the LM2596 buck converter) and display it on the Pi UI. This lets you monitor battery health, alternator charging, detect cranking dips, and know exactly what's feeding the 5V circuit.

### Why Monitor Source Voltage?

- **Battery health:** Resting voltage indicates state of charge (~12.6V = full, ~12.0V = 50%, <11.8V = low)
- **Alternator output:** Should read 13.5-14.5V with engine running; outside this range = problem
- **Cranking dips:** Voltage drops to 9-10V during crank — useful for detecting engine start events
- **Brownout warning:** Alert if voltage drops below safe buck converter input range

### Voltage Divider → ADC

The Pi has no built-in ADC, and its GPIOs are 3.3V max. A resistor voltage divider scales 0-16V down to 0-3.3V for safe ADC reading.

**Divider design (10kΩ + 39kΩ):**

$$V_{out} = V_{in} \times \frac{R_2}{R_1 + R_2} = 16V \times \frac{10k}{39k + 10k} = 3.27V$$

| Input Voltage | ADC Voltage | Meaning |
|---------------|-------------|---------|
| 9.0V (cranking) | 1.84V | Engine cranking dip |
| 12.0V (low battery) | 2.45V | Battery needs charge |
| 12.6V (full battery) | 2.57V | Battery at rest, healthy |
| 13.8V (charging) | 2.82V | Alternator charging normally |
| 14.5V (max charge) | 2.96V | Alternator at full output |
| 16.0V (overvolt) | 3.27V | Fault — overvoltage |

### Option A: ADS1115 on Pi I2C (Recommended)

16-bit resolution = ~0.005V accuracy over 0-16V range. Reads directly on the Pi over I2C — no serial dependency, no Arduino involvement. Shares I2C bus with other sensors (BH1750, etc.). If Section 2 (SWC ADC) is also implemented, one ADS1115 handles both — use A0 for 12V sense, A1 for SWC.

> **Why not use the Arduino?** The Arduino's serial link to the Pi is already busy with LED commands and telemetry data. Adding voltage readings would increase traffic and risk corruption/dropped packets. Reading directly on the Pi via I2C is more reliable and independent.

| Part | Spec | Price | Source |
|------|------|-------|--------|
| **ADS1115** | 16-bit I2C ADC, 4-ch | $3-8 | Amazon, Adafruit (#1085) |
| 39kΩ resistor (1/4W, 1%) | Voltage divider high-side | $0.10 | Amazon, DigiKey |
| 10kΩ resistor (1/4W, 1%) | Voltage divider low-side | $0.10 | Amazon, DigiKey |
| 100nF ceramic capacitor | Filter noise on ADC input | $0.10 | Amazon, DigiKey |
| 3.3V Zener diode (1N4728A) | Overvoltage protection | $0.10 | Amazon, DigiKey |

```
Car 12V+ (before buck) ──[39kΩ]──┬──► ADS1115 A0
                                  ├──[10kΩ]──► GND
                                  ├──[100nF]──► GND  (noise filter)
                                  └──[3.3V Zener]──► GND  (clamp protection)

ADS1115:  VCC → Pi 3.3V (Pin 1) | GND → Pi GND (Pin 9)
          SDA → GPIO 2 (Pin 3)  | SCL → GPIO 3 (Pin 5) | ADDR → GND (0x48)
```

### Option B: INA219 Current/Voltage Sensor (Most Data)

Measures both voltage AND current draw of the entire system. I2C, same bus as ADS1115.

| Part | Spec | Price | Source |
|------|------|-------|--------|
| **INA219** breakout | 0-26V, ±3.2A, 12-bit, I2C | $3-6 | Amazon, Adafruit (#904) |
| INA226 breakout | 0-36V, ±20A, 16-bit, I2C | $4-8 | Amazon, AliExpress |

Wire inline on the 12V+ supply. Reports bus voltage + current + power. **Pro:** Also monitors total current draw. **Con:** Inline wiring slightly more complex.

```
Car 12V+ ──► INA219 VIN+ ──► INA219 VIN- ──► LM2596 input
             │
             I2C → Pi (SDA/SCL, addr 0x40)
```

### Software (ADS1115 — Option A)

```python
# pi/ui/src/voltage_monitor.py
import board, busio, time
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

DIVIDER_RATIO = (39_000 + 10_000) / 10_000  # 4.9x

class VoltageMonitor:
    def __init__(self):
        i2c = busio.I2C(board.SCL, board.SDA)
        ads = ADS.ADS1115(i2c, address=0x48)
        ads.gain = 1  # ±4.096V range
        self.channel = AnalogIn(ads, ADS.P0)

    def read_voltage(self) -> float:
        """Returns the automotive 12V+ source voltage."""
        v_adc = self.channel.voltage
        return v_adc * DIVIDER_RATIO

    def get_status(self, voltage: float) -> str:
        if voltage < 11.0:
            return "CRITICAL"
        elif voltage < 12.0:
            return "LOW"
        elif voltage < 13.0:
            return "BATTERY"
        elif voltage < 14.8:
            return "CHARGING"
        else:
            return "OVERVOLT"
```

### UI Display Ideas

- **Numeric readout:** `12V: 13.82V ▲` (with charge arrow)
- **Bar gauge:** Color-coded (red <11V, yellow 11-12.4V, green 12.4-14.8V, red >14.8V)
- **History sparkline:** Last 60s of voltage readings to catch transient dips
- **Alert:** Flash warning if voltage drops below 11.5V or exceeds 15.0V

### Recommendation

**Option A (ADS1115 + voltage divider on Pi I2C)** — best accuracy, reads directly on the Pi with no serial dependency, and shares the ADC with SWC input (Section 2). **Option B (INA219)** if you also want current monitoring. **~$3-8 total.**

---

## 2. SWC Volume Wire Splice for Pi Input

**Current issue:** Only cruise control buttons (RES+, SET-, ON/OFF, CANCEL) available via CAN `0x250`. Audio buttons (VOL+/-, MODE, SEEK, MUTE) use an **analog resistance ladder wire** to the Axxess ASWC-1 — not on CAN. Only 4 buttons available; need 10.

### SWC Button Clusters

| Cluster | Buttons | Signal | On CAN? |
|---------|---------|--------|---------|
| Cruise (right) | RES+, SET-, ON/OFF, CANCEL | Digital CAN 0x250 | **Yes** |
| Audio (left) | VOL+, VOL-, MODE, SEEK UP/DOWN, MUTE | Analog resistance ladder | **No** |

### MX5 NC Audio SWC Resistance Values

Assumes 10kΩ pull-up to 3.3V. **Measure actual values before implementing.**

| Button | Resistance | Voltage |
|--------|-----------|---------|
| None | Open (∞) | 3.3V |
| VOL+ | ~87Ω | ~0.24V |
| VOL- | ~210Ω | ~0.55V |
| SEEK UP | ~510Ω | ~1.17V |
| SEEK DOWN | ~1kΩ | ~1.88V |
| MODE | ~2.2kΩ | ~2.49V |
| MUTE | ~4.7kΩ | ~2.89V |

### ADC Options

#### Option A: External ADC (Recommended — ADS1115)

| Part | Spec | Price | Source |
|------|------|-------|--------|
| **ADS1115** | 16-bit I2C, 4-ch, PGA | $3-8 | Amazon, Adafruit (#1085) |
| ADS1015 | 12-bit I2C, 4-ch, faster | $3-6 | Amazon, Adafruit |
| MCP3008 | 10-bit SPI, 8-ch | $3-5 | Amazon, Adafruit (#856) |

ADS1115: 16-bit easily distinguishes all buttons, I2C (no SPI conflict), uses unused GPIO 2/3 (SDA/SCL).

#### Option B: Arduino ADC (Existing Hardware)

Use Arduino Nano A0 → identify button → send event to Pi over serial. **Pro:** No new hardware. **Con:** Arduino at gauge cluster (long wire), serial already used for LEDs.

### Wiring (ADS1115)

```
SWC Signal Wire ──┬──► Axxess ASWC-1 (keep existing)
                  └──► ADS1115 A0 (splice in parallel, 10kΩ pull-up to 3.3V)

ADS1115:  VCC→Pi 3.3V (Pin 1) | GND→Pi GND (Pin 9) | SDA→GPIO 2 (Pin 3)
          SCL→GPIO 3 (Pin 5)  | A0→SWC wire         | ADDR→GND (0x48)
```

### Software

```python
# pi/ui/src/swc_adc_handler.py
import board, busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

BUTTON_THRESHOLDS = [
    (0.0,  0.40, "VOL_UP"),      # ~0.24V
    (0.40, 0.85, "VOL_DOWN"),    # ~0.55V
    (0.85, 1.50, "SEEK_UP"),     # ~1.17V
    (1.50, 2.20, "SEEK_DOWN"),   # ~1.88V
    (2.20, 2.70, "MODE"),        # ~2.49V
    (2.70, 3.10, "MUTE"),        # ~2.89V
]

class SWCADCReader:
    def __init__(self):
        i2c = busio.I2C(board.SCL, board.SDA)
        ads = ADS.ADS1115(i2c, address=0x48)
        ads.gain = 1  # ±4.096V range
        self.channel = AnalogIn(ads, ADS.P0)

    def read_button(self) -> str:
        voltage = self.channel.voltage
        for low, high, name in BUTTON_THRESHOLDS:
            if low <= voltage <= high:
                return name
        return None
```

### Wiring Notes

1. **Splice in parallel** — do NOT cut existing SWC wire (Axxess still needs it)
2. Keep signal within 0-3.3V (voltage divider if needed)
3. ADC input impedance >10MΩ — won't affect Axxess readings
4. Measure actual resistances with multimeter before setting thresholds
5. **Splice points:** Axxess module connector (blue/yellow or green wire), behind head unit, or steering column plug

---

## 3. Connector Upgrade: Replace DuPont with Automotive-Grade

**Current issue:** DuPont 0.1" connectors vibrate loose, have no locking, corrode, cause intermittent faults.

### Connector Comparison

| Connector | Lock | Vibration | Waterproof | Price/set | Difficulty |
|-----------|------|-----------|------------|-----------|------------|
| DuPont 0.1" (current) | No | No | No | $0.10 | Easy |
| JST-XH 2.5mm | Tab | Basic | No | $0.20-0.50 | Easy |
| JST-SM 2.5mm | Snap | Good | No | $0.30-0.60 | Easy |
| Molex Micro-Fit 3.0 | Positive | Excellent | No | $0.50-1.50 | Medium |
| Deutsch DTM | Wedge | Automotive | IP68 | $2-5 | Medium |
| Superseal 1.5 (TE) | Positive | Automotive | IP67 | $1-3 | Medium |
| Delphi Metri-Pack 150 | Tab+TPA | OEM auto | Splash | $0.50-2 | Medium |

### Tier 1: JST-SM — Internal Connections

| Part | Price | Source |
|------|-------|--------|
| JST-SM 2-pin (10 pairs) | $6-8 | Amazon |
| JST-SM 3-pin (10 pairs) | $6-8 | Amazon |
| JST-SM 4-pin (10 pairs) | $7-9 | Amazon |
| JST-SM crimping tool (Engineer PA-09) | $25-35 | Amazon |
| 22-28 AWG crimp pins | $5-8 | Amazon |

Snap-lock, compact, pre-crimped pigtails available.

### Tier 2: Molex Micro-Fit 3.0 — Power Connections

| Part | Price | Source |
|------|-------|--------|
| 43045-0200 (2-pin header) | $0.50 | Mouser, DigiKey |
| 43025-0200 (2-pin receptacle) | $0.60 | Mouser, DigiKey |
| 43030-0001 (female pins, 25-pack) | $5 | Mouser, DigiKey |
| 43031-0001 (male pins, 25-pack) | $5 | Mouser, DigiKey |
| Crimper (63819-0000 or Engineer PA-20) | $30-40 | Amazon, Mouser |

Positive lock, 5A/pin, 2-24 pin configs.

### Tier 3: Deutsch DTM — Engine Bay (If Needed)

| Part | Price | Source |
|------|-------|--------|
| DTM04-2P (2-pin plug) | $3-5 | Amazon, Waytek |
| DTM06-2S (2-pin socket) | $3-5 | Amazon, Waytek |
| DTM crimp pins (size 20, 20-22 AWG) | $1/ea | Waytek |
| DTM crimper (HDT-48-00 or Iwiss) | $35-50 | Amazon |

### Replacement Plan

| Connection | Replace With | Pins | Priority |
|------------|-------------|------|----------|
| 12V→buck converter | Molex Micro-Fit 3.0 | 2 | High |
| Buck→breadboard | **Eliminate breadboard** | - | High |
| 5V/GND→Pi | Molex Micro-Fit 3.0 | 2 | High |
| 5V/GND→Arduino | JST-SM | 2 | Medium |
| 5V/GND→each MCP2515 | JST-SM | 2 | Medium |
| SPI bus (MOSI/MISO/SCK) | JST-SM | 4 | Medium |
| Pi→Arduino serial | JST-SM | 3 | Medium |
| MCP2515 INT+CS | JST-SM | 3 | Low |
| LED strip data | JST-SM | 3 | Medium |

### Breadboard Replacement

| Option | Price | Source |
|--------|-------|--------|
| PCB terminal block board | $5-10 | Amazon |
| Custom PCB (JLCPCB/PCBWay) | $2-10 (5pcs) | JLCPCB |
| Wago 221 lever nuts (20pcs) | $10-15 | Amazon |
| Bus bar / power distribution block | $8-15 | Amazon |

**Recommended:** Custom PCB or terminal block — all solder joints, no friction contacts.

---

## 4. Additional Improvements

### 4A. Fused Power Distribution Block

| Part | Spec | Price | Source |
|------|------|-------|--------|
| BlueSea ST Blade (6-circuit) | Screw terminals, 30A bus | $25-35 | Amazon (B001P6FBOW) |
| Fastronix 6-circuit | Mini blade, LED indicators | $15-20 | Amazon |
| Generic 4-way fuse box | Mini blade, with cover | $8-12 | Amazon, AliExpress |

```
Car 12V (ACC) ──► 10A main fuse ──► Fuse Block
                                     ├─► 3A → Buck #1 → Pi
                                     ├─► 2A → Buck #2 → Peripherals
                                     ├─► 1A → Future
                                     └─► 1A → Future
```

### 4B. Strain Relief / Wire Management

| Part | Price | Source |
|------|-------|--------|
| Adhesive cable tie mounts (50pcs) | $5 | Amazon |
| Split wire loom (1/4", 3/8") | $6-8/10ft | Amazon |
| Kapton tape | $5/roll | Amazon |
| Adhesive felt pads | $3/pack | Amazon |
| 3M Dual Lock | $8-12 | Amazon |

Zip tie mounts every 6-8". Split loom for runs >12". Drip loop before connectors. Felt pads under PCBs.

### 4C. Ignition Sense GPIO

Voltage divider (10kΩ+20kΩ) from ignition 12V → Pi GPIO 4 (3.3V safe).

```
Ignition 12V ──[10kΩ + 20kΩ divider]──► Pi GPIO 4
                                          │
                                         10kΩ → GND
```

GPIO 4 HIGH = ignition on (start services). GPIO 4 LOW = ignition off (save data + shutdown). Combined with UPS HAT gives 10-30s shutdown window.

### 4D. EMI/RFI Filtering

| Part | Price | Source |
|------|-------|--------|
| Ferrite snap-on cores (5-pack) | $5-8 | Amazon |
| LC filter module | $3-5 | Amazon, AliExpress |
| 100µF + 0.1µF bypass caps | $1-2 | Amazon |
| Shielded USB cable (Pi↔ESP32) | $5-8 | Amazon |

Add ferrites on: 12V input, Pi↔ESP32 USB, CAN wire pairs at OBD connector. Bypass caps on each MCP2515 VCC.

### 4E. Enclosure / Mounting

| Part | Price | Source |
|------|-------|--------|
| Aluminum Pi 4 case (passive cooling) | $10-15 | Amazon |
| Hammond 1590B (4.4"×2.4"×1.2") | $8-12 | Mouser, DigiKey |
| 3D-printed enclosure (PETG, not PLA) | $2-5 | Local/online |
| DIN rail mount | $5-10 | Amazon |

Use PETG (PLA warps in car heat). Aluminum doubles as heatsink. Add ventilation + cable grommets.

### 4F. CAN Bus Termination

120Ω 1/4W resistor ($1-2, Amazon). Measure CANH↔CANL at OBD with car off: should read ~60Ω (two 120Ω in parallel). If ~120Ω, one termination is missing.

### 4G. GPS Module

| Part | Spec | Price | Source |
|------|------|-------|--------|
| BN-880 | u-blox M8, 10Hz, UART | $12-18 | Amazon, AliExpress |
| Adafruit Ultimate GPS | 66-ch, 10Hz, UART | $30 | Adafruit (#746) |
| u-blox NEO-M9N | Multi-band, 25Hz | $25-35 | SparkFun |

Via Pi UART/USB. Use for: speed verification, lap timing, route logging, GPS-based MPG.

### 4H. Ambient Light Sensor

| Part | Price | Source |
|------|-------|--------|
| BH1750 (I2C lux sensor) | $2-4 | Amazon, AliExpress |
| TSL2591 (high-range I2C) | $6 | Adafruit (#1980) |

Shares I2C bus with ADS1115. Auto-dim LEDs/display at night.

### 4I. OBD-II Y-Splitter

OBD-II Y-splitter cable (1M→2F, all pins): $8-15, Amazon. Keeps one port free for diagnostic scanner.

---

## Priority Matrix

| # | Improvement | Impact | Effort | Cost |
|---|------------|--------|--------|------|
| 1 | 12V voltage monitoring (ADS1115) | High | Low | $3-8 |
| 2 | JST-SM connectors | High | Low | $15-25 |
| 3 | Eliminate breadboard (solder PCB) | High | Medium | $5-15 |
| 4 | SWC wire + ADS1115 (shared ADC) | High | Medium | $0-8 |
| 5 | Ferrite cores / EMI filtering | Medium | Low | $5-8 |
| 6 | Strain relief + wire loom | Medium | Low | $10-15 |
| 7 | OBD-II Y-splitter | Low | Low | $8-15 |
| 8 | Enclosure | Medium | Medium | $10-20 |
| 9 | GPS module | Low | Medium | $15-35 |
| 10 | Ambient light sensor | Low | Low | $2-6 |

---

## Shopping Lists

### Minimum (Priorities 1-3): ~$35-50

| Item | Qty | Price | Source |
|------|-----|-------|--------|
| ADS1115 16-bit ADC | 1 | $3-8 | Amazon, Adafruit |
| Resistor kit (39kΩ + 10kΩ, 1%) | 1 | $1 | Amazon, DigiKey |
| 100nF ceramic cap + 3.3V Zener | 1 | $0.50 | Amazon, DigiKey |
| JST-SM 2/3/4-pin connector kit | 1 | $12-18 | Amazon |
| JST-SM pre-crimped pigtails (or crimper) | 1 | $8-15 | Amazon |
| PCB terminal block board | 1 | $5-8 | Amazon |

### Full (Priorities 1-6): ~$70-110

| Item | Qty | Price | Source |
|------|-----|-------|--------|
| *(All above)* | - | $35-50 | - |
| Ferrite snap-on cores (5-pack) | 1 | $5-8 | Amazon |
| Split wire loom (1/4"+3/8", 10ft ea) | 2 | $10-14 | Amazon |
| Adhesive cable tie mounts (50pcs) | 1 | $5 | Amazon |
| Molex Micro-Fit 3.0 2-pin sets | 4 | $5-8 | Mouser |

---

**Last Updated:** March 2, 2026
