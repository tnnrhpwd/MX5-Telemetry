# CC1101 Bench Test — Arduino Nano

Bench test for the **CC1101 module with SMA antenna** before it goes near the
car. Host is a spare **Arduino Nano** on a breadboard (5 V power, USB to PC).

> ⚠️ **Goal of this test is to prove the RF chain works**, not to decode your
> TPMS yet. Your car's stock TPMS sensors are **motion-gated** — they only
> transmit while the wheel is rolling — so they will *not* be heard in the
> bedroom. Silence at 315 MHz here is expected and is **not** a sign of broken
> hardware.

---

## 1. Power: this module is 3.3 V only (no regulator)

Your module's pin table says **VCC = 1.8–3.6 V** — there is **no onboard
AMS1117 regulator**, so it must be powered from **3.3 V**:

| CC1101 pin | Power |
|------------|-------|
| `VCC` | **3.3 V rail** — output of your added regulator |

- 5 V into this module **will damage it**.
- **Dedicated regulator (your setup):** feed it 5 V from the Nano's `5V` pin,
  run its **3.3 V output** to CC1101 `VCC`. This is the preferred option — the
  Nano's own `3V3` pin is weak (~50 mA).
- **Shared ground is mandatory:** regulator GND, Nano GND, and CC1101 GND must
  all be tied together, or nothing works.
- **Don't double-drive `VCC`:** use *either* the regulator output *or* the
  Nano `3V3` pin — never both at once.
- If the regulator is a bare AMS1117, add a ~10 µF cap on its input and output
  if the breakout doesn't already include them.

## 2. Wiring

```
            Arduino Nano                        CC1101 module (8-pin header)
        ┌─────────────────┐                ┌──────────────────────┐
        │       3V3 rail ├───────────────►│ 2 VCC                │
        │  (regulator out)│                │                      │
        │             GND ├───────────────►│ 1 GND                │
        │             D13 ├───────────────►│ 5 SCK                │
        │             D12 │◄───────────────┤ 7 MISO (MISO/GDO1)   │
        │             D11 ├───────────────►│ 6 MOSI               │
        │             D10 ├───────────────►│ 4 CSN                │
        │              D2 ├───────────────►│ 3 GDO0               │
        │              D3 ├───────────────►│ 8 GDO2      (opt.)   │
        └─────────────────┘                └──────────────────────┘
```

| Header pin | Name | Nano pin | Notes |
|-----------|------|----------|-------|
| 1 | `GND` | `GND` | common ground — required |
| 2 | `VCC` | **`3V3 rail`** (regulator out) | 3.3 V only, no regulator — shared GND with Nano |
| 3 | `GDO0` | `D2` | **direct** — receive interrupt |
| 4 | `CSN` | `D10` | 5 V→3.3 V (see below) |
| 5 | `SCK` | `D13` | 5 V→3.3 V (see below) |
| 6 | `MOSI` | `D11` | 5 V→3.3 V (see below) |
| 7 | `MISO/GDO1` | `D12` | **direct** — 3.3 V out into 5 V in is safe (we use MISO only) |
| 8 | `GDO2` | `D3` | **direct** — optional for this test |

### Grouping into two 4-pin connectors

The natural split is **by function** — all four SPI lines together, everything
else together:

| Connector A — power + status | Connector B — SPI |
|------------------------------|-------------------|
| A1 = `GND` (pin 1) | B1 = `CSN` (pin 4) |
| A2 = `VCC` 3.3 V (pin 2) | B2 = `SCK` (pin 5) |
| A3 = `GDO0` (pin 3) | B3 = `MOSI` (pin 6) |
| A4 = `GDO2` (pin 8) | B4 = `MISO/GDO1` (pin 7) |

Notes:

- Keep the pin-1 orientation identical on both connectors (keyed housings help)
  so a re-plug can never be reversed.
- Connector B has no ground of its own — fine for short bench wires. If you
  want a ground return on both, take the module's single `GND` to a ground rail
  and run one wire from the rail into each connector.
- Use a distinct wire color per signal and match it on both ends.

### Logic-level caution (Nano is 5 V, CC1101 is 3.3 V)

The CC1101's inputs are **not** 5 V tolerant (absolute max `VCC + 0.3 V`). The
Nano drives `SCK`, `MOSI`, `CSN` at 5 V.

- **Correct:** put a resistor divider on those three lines:
  `Nano pin ── 1 kΩ ──┬── CC1101 pin`
  `                2.2 kΩ`
  `                  │`
  `                 GND`
  That gives ≈ 3.4 V.
- **Works for a quick bench test:** wire them straight through. This is the
  overwhelmingly common hobby practice and works because the CC1101 clamps
  internally — but it's out of spec, so don't leave it hard-wired long term.
  (The *real* install is on the 3.3 V ESP32-S3, where this issue disappears.)

`MISO` and `GDO0`/`GDO2` are 3.3 V *outputs* from the module and can go
straight into the Nano's 5 V inputs.

## 3. Flash the scan sketch

Sketch: `tools/cc1101/cc1101_scan/cc1101_scan.ino`

1. **Install the library** — Arduino IDE → *Tools → Manage Libraries* →
   search **`SmartRC CC1101`** → install **SmartRC-CC1101-Driver-Lib** (V3.x).
2. Open `cc1101_scan.ino`.
3. Board: *Tools → Board → Arduino AVR Boards → **Arduino Nano***.
4. Processor: **`ATmega328P`** (if upload fails, switch to
   **`ATmega328P (Old Bootloader)`**).
5. Port: the COM port your Nano shows up on.
6. Upload, then open **Serial Monitor at 115200 baud**.

## 4. What you should see

1. **`CC1101: FOUND`** — SPI link and chip are good.
   If you see `NOT FOUND`, check `VCC`/`GND` and the three SPI lines.
2. **A sweep** of 300–348 MHz, each line `F=xxx.x MHz  RSSI=xx dBm`.
   A quiet room reads **-90 to -105 dBm** everywhere (the noise floor).
3. **A 433 MHz sweep** — a sanity check. If you have any 433 MHz devices
   (doorbell, weather station, key fob), you'll see a spike when it fires.
4. **Live 315 MHz monitor** — prints RSSI four times a second.

**How to prove it hears something:** press a **315 MHz key fob / garage remote**
(or 433 MHz) next to the antenna. The RSSI should jump to roughly -50…-70 dBm
and the sketch prints `>>> SIGNAL ABOVE -85 dBm DETECTED <<<`.

## 5. Antenna note

The antenna shipped with these kits is usually tuned for **433 MHz**, not 315.
For this bench test it's fine (strong nearby signals still get through). For
the in-car build, use a **315 MHz SMA antenna** (~24 cm quarter-wave).
## 6. Loopback test — prove the receive chain with a known signal

If a fob or TPMS signal is *not* seen, the fastest way to split "dead receiver"
from "weak / wrong-frequency signal" is to transmit a known carrier from a
**second CC1101 module** and read the RSSI on the first.

> This is the definitive test: it removes the fob, the battery, the frequency
> guess, and the modulation guess from the equation all at once.

### Wiring the second module as a transmitter

Everything is shared with the existing module — only **one new wire**:

| TX module pin | Connect to |
|---------------|------------|
| `GND` (1) | Nano `GND` *(share)* |
| `VCC` (2) | 3.3 V rail *(share)* |
| `GDO0` (3) | *(unconnected)* |
| `CSN` (4) | **`D9`** ← the only new wire |
| `SCK` (5) | `D13` *(share)* |
| `MOSI` (6) | `D11` *(share)* |
| `MISO/GDO1` (7) | `D12` *(share)* |
| `GDO2` (8) | *(unconnected)* |

No GDO pins are needed on the transmitter — the sketch uses a timed send, not
a GDO handshake.

### Firmware

Sketch: `tools/cc1101/pio_loopback/` (PlatformIO project, board
`nanoatmega328`). Its `main.cpp` drives **two** `SmartRC_CC1101` objects over
one shared SPI bus: the receiver on `CSN D10`, the transmitter on `CSN D9`.

Serial commands (115200):

| Command | Effect |
|---------|--------|
| `F 433.92` / `F 315.0` | retune **both** modules and keep the carrier on |
| `P -20` / `P -30` | set TX power in dBm |

### Run it

1. Stop anything else holding COM3 (e.g. the live-readout webapp).
2. Build & upload:
   `pio run -d tools/cc1101/pio_loopback --target upload`
3. Open a monitor at 115200. Expect `RX FOUND`, `TX FOUND`, `READY`, then a
   stream of `433.920 MHz   RSSI=xx dBm` lines.

### What it proves

- At **433.92 MHz** (the module's native band), RSSI should jump from the quiet
  floor (~`-124`) to a strong value (roughly `-20` or better at close range).
  **This proves the receive chain — antenna, matching, LNA, SPI — is healthy.**
- Send `F 315.0`. The RSSI at the same distance shows the **315 MHz penalty**
  of this 433-tuned module. If 433 is loud but 315 sits near the floor at close
  range, the module is simply too deaf at 315 for fob/TPMS work and you need a
  315 MHz-tuned board (E07-M1101D-315 or equivalent).
- If **neither** frequency moves the RSSI, the receiver itself is faulty
  (antenna path or front-end) and should be swapped for the spare module.
## Next steps

Once this test confirms the chain works, the next milestone is capturing a real
TPMS transmission (requires a rolling wheel or a pressure change) and
reverse-engineering / matching the frame format — the step before writing the
decoder that replaces the BLE scanner on the ESP32-S3.
