# CC1101 Bench Test — Arduino Nano

Bench test for the **CC1101 module with SMA antenna** before it goes near the
car. Host is a spare **Arduino Nano** on a breadboard (5 V power, USB to PC).

> ⚠️ **Goal of this test is to prove the RF chain works**, not to decode your
> TPMS yet. Your car's stock TPMS sensors are **motion-gated** — they only
> transmit while the wheel is rolling — so they will *not* be heard in the
> bedroom. Silence at 315 MHz here is expected and is **not** a sign of broken
> hardware.
>
> This bench test is **step 1 of the action plan below**. Read that first.

---

## Action plan — the path to a working receiver

Four milestones, plus two prerequisite gates. The order matters: each milestone is only
meaningful once the one above it is *proven*, not assumed. Steps 0 and 1 are the gates that
have cost the most time by being skipped.

| # | Milestone | Gate — how you know it is done |
|---|-----------|-------------------------------|
| **0** | Trustworthy diagnostics | Both chips report `PARTNUM=00` / `VERSION=14`, ten reads in a row, and again after a re-seat |
| **1** | Receive chain proven against a **known** signal | A frame we transmitted ourselves is recovered bit-for-bit at the receiver |
| **2** | **Fob decode** | Two presses of the *same* fob give a byte-identical frame — or a rolling code whose serial field is stable |
| **3** | **TPMS detect + read** | A captured burst repeats the same frame 4–8× inside one 45 ms window |
| **4** | **TPMS decode + corner assignment** | Every sensor ID resolves to a pressure/temperature reading, and all four corners are identified |
| **5** | **Repo integration** | Decoded values reach the display and the logger, sourced from this receiver |

### 0. Trustworthy diagnostics

**Why first:** the register readback currently returns `PARTNUM` and `VERSION` as the
**same byte** on each chip. Those are two different hardware constants (`0x00` and `0x14`),
so no valid read can make them equal — the access is not reaching the registers. Anything
concluded from `DUMP` / `TXV` is therefore void, including several conclusions already
drawn in this project.

- Determine whether the fault is the read sequence or the chip. The library prints its own
  `CC1101 FOUND` / `NOT FOUND` from a *different* read path — capture that banner at boot.
- Remove the mechanical variable: solder the modules down, or fit good sockets. The
  readback has flipped between working and broken purely from re-seating.
- **Gate:** `00` and `14` from both chips, ten consecutive reads, and stable across a re-seat.
- **Consequence:** on this board, verify configuration **behaviourally** (does changing a
  setting change the output?) — never by reading registers back.

### 1. Prove the receive chain against a known signal

**Why first:** you cannot decode a fob until the receiver has been proven on a signal whose
contents you already know. Without this, nothing can distinguish "this fob is unusual" from
"the receiver does not work".

- Transmit the known frame (`AA×8`, `2D D4`, `01 02 04 08 10 20`) from the TX module and
  compare what the RX captures.
- **Variables not yet tested:** move the two modules **apart** — this document's own note
  says two modules on one bench *saturate* the RX, which invalidates the loopback; also sweep
  TX power and both packet modes.
- **Gate:** the 128-bit frame recovered at the receiver, scored against a shuffled-pattern
  control so that a flat capture cannot pass.

### 2. Fob decoding ← *milestone 1 in the original list*

- Capture a real press and get a keyed waveform — high fraction well away from 0 % / 100 %.
- Find the frame: symbol clock, preamble, then payload.
- **Gate:** two presses of the same fob produce the same frame. If they differ, look for a
  **stable serial field before concluding the code is rolling** — rolling codes still carry a
  fixed serial, and that alone identifies the fob.
- **Deliverable:** the webapp reports a fob ID and code from a captured burst.

### 3. TPMS: detect and read ← *milestone 2*

- Sensors are **motion-gated**: wake one with a pressure change, a roll, or an LF tool.
- Expect **FSK** on most Nissan / Mazda / Honda / Toyota sensors, at a **slower** data rate
  than the fobs. Set the receiver accordingly.
- **Gate:** one 45 ms window contains the **same frame repeated 4–8×**. That repeat is
  something a fob cannot give you, and it is the reason TPMS is the easier target.

### 4. TPMS: decode and assign corners ← *milestone 3*

- Decode: sensor ID, pressure, temperature, flags, and check the CRC.
- **Corner assignment:** trigger **one wheel at a time** (deflate or roll just that wheel) and
  record which ID appears. Repeat per corner.
- **Gate:** all four corners identified, each reporting a plausible pressure, and the mapping
  survives a new session.

### 5. Integrate into the repo ← *milestone 4*

- Feed decoded fob/TPMS events into the existing pipeline (`DataLogger`, `CANHandler`, the
  ESP32-S3 display) rather than leaving them inside the bench tool.
- **Gate:** a real sensor's pressure appears on the display and in the log, end to end.

### Known state — 2026-10-09

- **Receiver as a signal detector: working.** Live level, floor ≈ −110 dBm, responds to a fob press.
- **Receiver as a data output: none obtained.** A known transmission produces no usable capture.
- **Transmitter: no measurable effect at the receiver** on any setting tried.
- **Register readback: unusable** (`PARTNUM` = `VERSION`), so it is not evidence either way.
- Working habits worth keeping: verify behaviourally; **snapshot the capture log before
  restarting the webapp** (it has been wiped mid-session several times); record the settings
  (`MOD=`, `DRATE=`, `FREQ=`) with every capture.

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

Two CC1101 modules share **one SPI bus**. They are told apart by chip select
alone — **RX on `CSN D10`**, **TX on `CSN D9`** — so power and the three SPI
lines are wired in parallel, and only the two chip selects plus the receiver's
`GDO0` are unique to a module.

```
                        CC1101 "RX"                     CC1101 "TX"
   Arduino Nano         CSN → D10                       CSN → D9
 ┌────────────────┐    ┌──────────────────┐           ┌──────────────────┐
 │  3V3 rail ─────┼───►│ 2  VCC ──────────┼──────────►│ 2  VCC           │
 │           GND ─┼───►│ 1  GND ──────────┼──────────►│ 1  GND           │
 │                │    │                  │           │                  │
 │           D13 ─┼─[÷]► 5  SCK ──────────┼──────────►│ 5  SCK           │
 │           D11 ─┼─[÷]► 6  MOSI ─────────┼──────────►│ 6  MOSI          │
 │           D12 ◄┼──── 7  MISO/GDO1 ◄───┼───────────┤ 7  MISO/GDO1     │
 │                │    │                  │           │                  │
 │           D10 ─┼─[÷]► 4  CSN           │           │                  │
 │            D9 ─┼─[÷]──────────────────────────────►│ 4  CSN           │
 │                │    │                  │           │                  │
 │            D2 ◄┼──── 3  GDO0           │           │ 3  GDO0    (n/c) │
 │            D3 ◄┼──── 8  GDO2  (opt.)   │           │ 8  GDO2    (n/c) │
 └────────────────┘    └──────────────────┘           └──────────────────┘

 [÷]  = 5 V → 3.3 V divider on every Nano OUTPUT (D13, D11, D10, D9):
            Nano pin ── 1 kΩ ──┬── CC1101 pin
                             2.2 kΩ
                               │
                              GND
```

| Header pin | Name | RX module (`D10`) | TX module (`D9`) | Notes |
|-----------|------|-------------------|------------------|-------|
| 1 | `GND` | `GND` | `GND` | common ground — required, shared |
| 2 | `VCC` | **`3V3 rail`** | **`3V3 rail`** | 3.3 V only, no onboard regulator — shared |
| 3 | `GDO0` | `D2` | *not connected* | **direct** — demodulated data out; receiver only |
| 4 | `CSN` | `D10` | `D9` | the only pin that separates the two chips |
| 5 | `SCK` | `D13` | `D13` | shared, 5 V→3.3 V |
| 6 | `MOSI` | `D11` | `D11` | shared, 5 V→3.3 V |
| 7 | `MISO/GDO1` | `D12` | `D12` | shared, **direct** (3.3 V out into 5 V in is safe) |
| 8 | `GDO2` | `D3` | *not connected* | **direct**, optional for this test |

### Grouping into two 4-pin connectors

Do this **per module** — each CC1101 gets its own pair, so four connectors in
total. The natural split is **by function** — all four SPI lines together,
everything else together:

| Connector A — power + status | Connector B — SPI |
|------------------------------|-------------------|
| A1 = `GND` (pin 1) | B1 = `CSN` (pin 4) |
| A2 = `VCC` 3.3 V (pin 2) | B2 = `SCK` (pin 5) |
| A3 = `GDO0` (pin 3) | B3 = `MOSI` (pin 6) |
| A4 = `GDO2` (pin 8) | B4 = `MISO/GDO1` (pin 7) |

Notes:

- On the **TX** module only `GND` and `VCC` are used from connector A — its
  `GDO0` and `GDO2` are not connected.
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

Sketch: `tools/cc1101/firmware/cc1101_scan/cc1101_scan.ino`

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

Both modules are already wired in **[§2 Wiring](#2-wiring)** above. The
transmitter shares `VCC`, `GND`, `SCK`, `MOSI` and `MISO` with the receiver, and
needs **no GDO pins at all**, because the sketch uses a timed send rather than a
GDO handshake. The one wire unique to it is **`CSN` → `D9`**.

### Firmware

Sketch: `tools/cc1101/firmware/pio_loopback/` (PlatformIO project, board
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
   `pio run -d tools/cc1101/firmware/pio_loopback --target upload`
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
