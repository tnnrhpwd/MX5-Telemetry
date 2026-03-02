# Planned Hardware Improvements

**Vehicle:** Mazda MX-5 NC (2006-2015) | **System:** Pi 4B + ESP32-S3 + Arduino Nano + 3× MCP2515

---

## 1. Dedicated 12V Power Circuit

**Current issue:** OBD-II Pin 16 → single LM2596 → breadboard. No ignition switching, no graceful shutdown, single point of failure, vibration-prone breadboard.

### Option A: Automotive USB-C Power Supply (Simplest)

| Part | Spec | Price | Source |
|------|------|-------|--------|
| DFRobot DFR0756 | 9-36V→5V/5A USB-C | $12-15 | DFRobot, Amazon |
| Tobsun EA15-5 | 12V→5V/3A encapsulated | $8-12 | Amazon, eBay |
| DROK 12V→5V/5A | USB-C output | $8-10 | Amazon |

Handles 9-36V automotive range. Still needs separate peripheral power.

### Option B: Dual Buck Converters (Recommended)

Isolates Pi power from LED/CAN noise.

| Part | Spec | Price | Source |
|------|------|-------|--------|
| Pololu D36V6F5 | 5V/600mA step-down | $5 | Pololu |
| Pololu D36V28F5 | 5V/2.8A, 4.5-50V input | $10 | Pololu |
| Pololu D36V50F5 | 5V/5A step-down | $15 | Pololu |
| BINZET 12V→5V/10A | 50W, screw terminals | $10 | Amazon |

```
Car 12V (ACC) ──[5A fuse]──┬──► Buck #1 (5V 3A) ──► Pi USB-C
                            └──► Buck #2 (5V 2A) ──► Peripherals (3×MCP2515, Arduino, LEDs, ESP32)
```

### Option C: UPS HAT (Best Reliability)

Battery backup for graceful shutdown + clean power during cranking dips.

| Part | Spec | Price | Source |
|------|------|-------|--------|
| Geekworm X728 | 18650 UPS HAT, 5V/6A | $30-40 | Amazon, Geekworm |
| PiSugar S Plus | 5000mAh compact UPS | $35-45 | Amazon |
| Geekworm X1202 | USB-C PD in, auto shutdown | $25-35 | Amazon |
| 52Pi EP-0136 | UPS HAT + RTC + shutdown GPIO | $25-35 | Amazon, AliExpress |

Flow: Car 12V → buck → UPS (charges battery) → Pi (clean 5V). On ignition off, UPS signals GPIO → Pi shuts down gracefully (10-30s window).

```python
# /home/pi/MX5-Telemetry/pi/scripts/safe_shutdown.py
import RPi.GPIO as GPIO
import subprocess, time

SHUTDOWN_PIN = 4  # GPIO pin from UPS "power loss" signal
GPIO.setmode(GPIO.BCM)
GPIO.setup(SHUTDOWN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def shutdown_callback(channel):
    time.sleep(5)
    subprocess.call(['sudo', 'shutdown', '-h', 'now'])

GPIO.add_event_detect(SHUTDOWN_PIN, GPIO.FALLING, callback=shutdown_callback, bouncetime=2000)
```

### Ignition-Switched 12V Sources (MX5 NC)

| Source | Location | Notes |
|--------|----------|-------|
| ACC fuse | Fuse box slot 15 (15A) | On with ACC/RUN |
| Ignition fuse | Fuse box slot 20 (10A) | On with RUN only |
| Radio ACC wire | Behind Pioneer harness | Already switched |
| Add-a-fuse tap | Any switched slot | **Recommended** — no splice needed |

| Part | Spec | Price | Source |
|------|------|-------|--------|
| Nilight Fuse Tap (5-pack) | Mini blade add-a-fuse | $7-10 | Amazon (B077YCQ342) |
| Chanzon Add-a-Fuse (10-pack) | Mini/standard mix | $6-8 | Amazon |

### Recommendation

**Option C (UPS HAT) + add-a-fuse** — battery-buffered Pi power, graceful shutdown, survives cranking dips, isolated peripherals. **~$40-60 total.**

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
| 1 | JST-SM connectors | High | Low | $15-25 |
| 2 | Eliminate breadboard (solder PCB) | High | Medium | $5-15 |
| 3 | Fuse tap for switched 12V | Medium | Low | $7-10 |
| 4 | UPS HAT for Pi | High | Medium | $30-40 |
| 5 | SWC wire + ADS1115 | High | Medium | $3-8 |
| 6 | Dual buck converters | Medium | Low | $10-20 |
| 7 | Ferrite cores / EMI filtering | Medium | Low | $5-8 |
| 8 | Strain relief + wire loom | Medium | Low | $10-15 |
| 9 | OBD-II Y-splitter | Low | Low | $8-15 |
| 10 | Enclosure | Medium | Medium | $10-20 |
| 11 | GPS module | Low | Medium | $15-35 |
| 12 | Ambient light sensor | Low | Low | $2-6 |

---

## Shopping Lists

### Minimum (Priorities 1-4): ~$65-95

| Item | Qty | Price | Source |
|------|-----|-------|--------|
| JST-SM 2/3/4-pin connector kit | 1 | $12-18 | Amazon |
| JST-SM pre-crimped pigtails (or crimper) | 1 | $8-15 | Amazon |
| PCB terminal block board | 1 | $5-8 | Amazon |
| Nilight add-a-fuse (mini blade) | 1 pk | $7-10 | Amazon |
| Geekworm X728 UPS HAT | 1 | $30-40 | Amazon |

### Full (Priorities 1-8): ~$110-160

| Item | Qty | Price | Source |
|------|-----|-------|--------|
| *(All above)* | - | $65-95 | - |
| ADS1115 16-bit ADC | 1 | $3-8 | Amazon, Adafruit |
| Pololu D36V28F5 (5V/2.8A buck) | 2 | $20 | Pololu |
| Ferrite snap-on cores (5-pack) | 1 | $5-8 | Amazon |
| Split wire loom (1/4"+3/8", 10ft ea) | 2 | $10-14 | Amazon |
| Adhesive cable tie mounts (50pcs) | 1 | $5 | Amazon |
| Molex Micro-Fit 3.0 2-pin sets | 4 | $5-8 | Mouser |

---

**Last Updated:** March 1, 2026
