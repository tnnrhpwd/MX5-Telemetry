# MX-5 NC CAN manual

What this car actually broadcasts, what the scaling is, and where this repo matches or does not.
Written 2026-11-26 because the speed encoding was re-litigated for a year — it is not a guess and
it does not need another capture to settle.

**Read the next section before touching anything that reads speed.**

---

## Sources

| # | Source | What it gives | Confidence |
|---|---|---|---|
| S1 | RaceChrono DIY BLE device, `can_db/mazda_mx5_nc.md` (timurrrr) — <https://github.com/timurrrr/RaceChronoDiyBleDevice/blob/master/can_db/mazda_mx5_nc.md> | Per-ID byte maps and decode equations, plus update rates and a packet histogram | High. Written for this exact car (2005-2015 NC/NCFL/MK3), with equations derived from real driving |
| S2 | `testors/can_tools`, `dbcs/Mazda/MX-5 (NC) 2005-2015.dbc` | DBC signal factor/offset pairs (the repository is no longer publicly reachable; figures below are quoted from its published content) | High for scale/offset; it independently agrees with S1 |
| S3 | AiM MX5-NC ECU connection document, `MazdaMX5-NC_104_eng.pdf` | Channel list (RPM, four wheel speeds, …) | Medium — a vendor feature list, not a decode |
| R | Repo-local (**not** in S1-S3) | IDs and scales this project added on its own | Unverified unless a test or a drive says otherwise |

Two sources describe the speed field the same way. That is why the encoding below is stated as
fact rather than as a hypothesis.

---

## The rule that keeps getting re-derived: **speed is offset, not signed**

> S1, CAN ID `0x201`, channel *Speed*:
> `((bytestoint(raw,4,2)/100.00)-100)/3.6`
> “Raw speed data is given in km/h with a **100 km/h offset**.”

> S2, in km/h terms: `SG_ … : 32|16@0+ (0.01,-100)` — factor `0.01`, offset `-100`.

So the 16-bit field at **bytes 4-5 of `0x201`** carries

```
raw  =  (speed_kmh + 100) * 100        # what the PCM puts on the wire
speed_kmh  =  raw / 100 - 100          # what we must compute
```

| Raw | Speed |
|---|---|
| `0x2710` (10000) | 0.00 km/h |
| `0x251C` (9500) | **−5.00 km/h** |
| `0x26AC` (9900) | **−1.00 km/h** |
| `0x38A4` (14500) | 45.00 km/h |

**The wire value is never negative.** It is an offset field, so the *only* place the sign exists
is after the subtraction. Forward motion physically cannot produce a raw value below the zero
point, which makes a decoded negative **proof** that the car is rolling backwards — not an
inference to be corroborated, and not something to go and capture before believing.

### What that means in practice

- **Do not** ask for a reverse capture to “prove the field goes negative”. It does not, and that
  is expected. The sign is produced by our subtraction, exactly as above.
- **Do not** let a secondary signal override it. The neutral/clutch bits on `0x231` are, at best,
  partially documented (see below) and must never veto a negative speed.
- **Do not** infer reverse from the speed/RPM ratio. Reverse gearing is close enough to 1st that
  the ratio match answers “1”, which is precisely the symptom this project spent a year chasing.
- **Do not** re-implement the decision per screen. One function per platform:
  `CANHandler._update_gear_estimation()` (Pi), `uiIsReverse()` (ESP32), `Telemetry.isReverse()`
  (Android), `isReverse()` (desktop simulators).

---

## 0x201 — engine (100 Hz, S1)

| Byte | Meaning |
|---|---|
| 0-1 | Engine RPM, `uint16 / 4` |
| 2-3 | WIP (follows RPM) |
| **4-5** | **Vehicle speed**, `0.01 km/h` with a **+100 km/h offset** |
| 6 | Accelerator pedal, `0…200` = `0…100 %` |
| 7 | Always `FF` |

Repo: `parse_rpm()`, `parse_speed()`, `parse_throttle_engine()` — **all three match S1.**
`parse_speed_raw()` keeps the literal field so `/api/telemetry` can show it.

`parse_speed()` also rejects impossible magnitudes (below −50 km/h, above 250 km/h) so a blanked
field reads as “no reading” rather than −100 km/h. That guard is a sanity check on *corruption*,
not a reason to disbelieve a −5.

---

## 0x231 — transmission (40 Hz, S1) — mostly useless on a manual

> S1: “On MT cars only interesting bit is the clutch switch.”

| Byte | Meaning on a **manual** |
|---|---|
| 0 | **Always `FF`** |
| 1 | bit 7 = clutch switch; bit 6 “**may** be related to neutral/in gear?” (author's uncertainty) |
| 2-7 | Constant on MT |

Repo reality check:

- `parse_range()` reads `data[0] & 0x0F` as a range code. On an MT byte 0 is always `FF`, so this
  returns **15, always** — meaningless.
- `parse_range()` also treats `data[1] == 0x04` as neutral/park. That encoding is **not** in S1,
  which says byte 1 carries clutch/neutral *bits*. On an MT it does not occur.
- Net effect: `telemetry.is_in_neutral` is effectively **never true** on this car. Anything that
  depends on it (neutral display, a reverse veto) is therefore dead or wrong.

**Do not build on `is_in_neutral` until bit 6 of byte 1 has been observed in both states.** If it
is ever pinned down, the right way to record it is a single named constant with the observed
sample beside it, not a guess.

`REVERSE_RANGE_CODES` exists for the day a real reverse code is observed here. It ships **empty**
on purpose: a guessed code puts a confident `R` on screen while driving forward.

---

## 0x4B0 — wheel speeds (100 Hz, S1)

| Bytes | Signal |
|---|---|
| 0-1 | Front left |
| 2-3 | Front right |
| 4-5 | Rear left |
| 6-7 | Rear right |

Same `100 km/h` offset as `0x201`: S1 decodes each as `((int/100)-100)/3.6`, S2 declares
`(0.01,-100)`.

Signedness is **not settled** between the sources: S1 reads them with `bytestoint`, while S2
declares a minimum of `0` (i.e. magnitude only). Do not treat these as a reverse signal until a
drive shows them going below the zero point.

Repo: `parse_wheel_speeds()` **omits the −100 offset entirely** — it returns `100 km/h` for a
stationary car. It is currently **unused** (nothing calls it, and `0x4B0` is not dispatched in
`_process_hs_message`). Fix the offset before wiring it to anything.

---

## 0x240 — engine temperatures (10 Hz, S1)

| Byte | Meaning |
|---|---|
| 0 | Calculated load, `%/255` |
| 1 | Coolant, `raw − 40` °C |
| 2 | Ignition timing (WIP) |
| 3 | Throttle valve position |
| 4 | Intake air, `raw − 40` °C |
| 5-7 | Constant |

S1 also notes coolant is available in `0x420` byte 0. Repo uses `0x420` for coolant and ambient —
**the ambient byte is repo-local and unverified**.

---

## 0x081 / 0x085 — DSC-equipped cars only (2007+, 100 Hz, S1)

| ID | Signal |
|---|---|
| `0x081` | Steering angle, signed, bytes 2-3, positive = right |
| `0x085` | Brake pressure (bytes 0-1), brake switch (byte 2, bit 0) |

Repo uses **`0x4B8`** for steering angle and **`0x212`** for the brake switch. **Neither ID
appears in S1**, so both are repo-local/unsourced. If a steering or brake reading ever looks
wrong, the documented fallback is `0x081` / `0x085` (DSC cars only).

---

## 0x200 / 0x215 — throttle duplicates (100 Hz, S1)

`0x200` byte 7 and `0x215` byte 6 both carry throttle valve position, `raw * 100 / 255`.

Repo: the primary path uses `0x201` byte 6 (correct, and preferred — it is the pedal, not the
valve). The **legacy fallback** `parse_throttle()` reads `0x200` **byte 4**, which does not match
S1's byte 7. It is only used when the engine frame is short, but it is wrong.

---

## Update rates (S1) — relevant to any latency work

| ID | Rate |
|---|---|
| `0x201`, `0x200`, `0x215`, `0x4B0`, `0x081`, `0x085`, `0x211` | ~100 Hz |
| `0x231`, `0x4EC` | ~40 Hz |
| `0x240`, `0x212`, `0x39A`, `0x420`, `0x430`, `0x4FF` | ~10 Hz |
| `0x204`, `0x21A` | ~50 Hz |
| `0x4F0`, `0x4F1` | ~1 Hz |

The LED strip therefore has engine data at 100 Hz, not the 50 Hz a bench model once assumed —
`RPM_EXTRAPOLATE_MS 60` and `RPM_MAX_SAMPLE_GAP 100` are comfortably above the real 10 ms period.

---

## Checklist before changing anything here

1. Find the ID and bytes in the table above. If it is not there, say so in the commit message —
   do not present a guess as a decode.
2. Scale **and offset**. A missing −100 km/h offset is the single most expensive mistake this
   project has made.
3. `raw` is unsigned on the wire; the sign exists only after the offset is removed.
4. If a value disagrees with the car, print `raw`. `REV:` already does
   (`speed`, `raw`, `neutral`, `range`, `rpm`, `gear`) on every reverse state change, and
   `/api/telemetry` carries `speed_raw` and `transmission_range`.
5. One implementation per rule, one place per platform. If you find two, delete one.

---

## Anti-patterns, with the cost

| Anti-pattern | What it did |
|---|---|
| Treating the speed field as signed on the wire | “Reverse” arrived as +555 km/h, then as a confident gear 1 |
| Inferring reverse from the speed/RPM ratio | Reverse gearing is near 1st, so the answer was always 1 |
| Letting the `0x231` neutral bit veto a negative speed | Discarded the one signal that is actually proof |
| Clamping speed to ≥ 0 “because negative is invalid” | Destroyed the direction at the wire, in three separate places |
| Hand-typing a km/h-per-1000-rpm table | Used a 25.5" wheel instead of 24.3"; every predicted RPM read 4.7 % low |
| Adding a calibration factor to one of three surfaces | Guarantees the ladder and the reported gear disagree |
| Asking for a CAN capture to prove an offset field can go negative | A year of the same question, already answered by S1 and S2 |
