# In-Car Findings — 2026-11-26

**Recorded:** 2026-11-26 · **Reported from:** the car (carried over after a drive)
**Vehicle:** Mazda MX-5 NC · Pi 4B · ESP32-S3 1.85" · Arduino Nano + 20-LED strip · Android Auto head unit

> **Verification status.** The car is not on the network and the phone is not plugged in, so
> **nothing in this document has been verified on hardware**. The findings were recorded from
> the owner's report plus the code, and the fixes were then made and checked offline — each one
> against a test, a build or a rendered artefact, listed in
> [Resolution status](#resolution-status-after-the-2026-11-26-desk-pass). Anything still
> marked "needs the car" is a judgement only the panel or a drive can make.

This is a *new* round of findings, not a re-opening of the 2026-10-30 file. Each section names
the earlier issue it recurs from (see [KNOWN_ISSUES.md](KNOWN_ISSUES.md)) and what is genuinely
new about it.

---

## Resolution status (after the 2026-11-26 desk pass)

Every item below was worked offline. "Verified" means a test or a rendered artefact, never a
claim; "needs the car" is the one thing code cannot settle.

| ID | What changed | How it was verified | Still needs the car |
|----|--------------|---------------------|---------------------|
| [19](#issue-19--reverse-still-reads-as-gear-1) | Reverse is the sign of the speed, in one place on the Pi, with nothing allowed to override it (not the neutral bit); the display now also derives `R` from a negative speed, so a missing/misaligned flag can no longer leave a confident `1`. New `REV:` line in the journal on every state change. | `test_can_speed.py` 19/19, including a test that a negative speed beats a stuck neutral bit; a synthetic frame at `0x251C` (`−5 km/h`) runs the whole chain to `TEL:…,-5,-1,…,1`; the simulator renders `--reverse-sign` (speed −3, flag false, gear 1) **pixel-identical** to `--reverse` on Overview and RPM | whether the Pi and panel in the car are running this code — the `REV:` line prints the decoded speed, so one shift into R says so |
| [20](#issue-20--gear-ladder-predicts-rpm-about-5-low) | Ladder table derived from `GEAR_RATIO`/`FINAL_DRIVE`/`TIRE_DIAMETER_IN` (24.3") instead of a hand-typed table that implied a 25.5" wheel | re-rendered ladder: 100 km/h now predicts 2971 rpm in 6th and 4183 in 4th, matching the derivation | the residual from the loaded rolling radius; `RPM_CALIBRATION` is the single number to set |
| [21](#issue-21--startup-animation-flickers-all-through) | Boot animation composes each frame in a PSRAM frame buffer and flushes it in 8 bands, instead of ~500–700 panel writes per frame | firmware builds for `esp32s3_display`; the rect mapping (including clipping) is verified by an executable check | whether the flicker is gone, judged on the panel |
| [22](#issue-22--dashboard-is-not-viewable-while-driving) | In-motion screen now blanks readings older than 3 s or reported not-live, instead of holding the last value for ever | code review; `can_connected` is the Pi's liveness flag | the tile itself still needs a Play internal track, or the HDMI route |
| [23](#issue-23--led-strip-still-feels-laggy) | Nano serial 9600 → 115200 at both ends; `STATUS` now reports `PER=` (measured `0x201` period) and `LAG=` (worst loop iteration), both surfaced in `/api/telemetry`; predictor ceiling 40 → 60 ms | Nano firmware builds (53.5 % flash); the Pi's STATUS parser ignores unknown keys and the whole Pi suite passes | read `PER`/`LAG` on a drive — that picks the remaining fix |
| [24](#issue-24--led-colours-are-washed-out-and-red-reads-pink) | The strip's ramp is the engine's ramp again — identical in all 12 schemes and both modes; the theme reaches it only as the dark-mode dim factor; shift light is red | `javac` + harness: 24/24 scheme/mode pairs checked for chroma floor, red redline, no white, red shift light; the `Color` bit-op refactor is asserted against Android's semantics. **Second pass:** two engine stops were still 23�24 % white and the bar measured 50 % saturation at 3300 rpm; re-measured at 100 % everywhere after the fix � see [the second pass](#second-pass-2026-11-26-after-the-fix-above-shipped) | a photo at ~6800 rpm |

**Still open by nature:** the reverse signal question (19) and the Android Auto distribution
step (22). Neither is a code defect that can be closed from this repo without the car or a
Play account, and both now report what they need instead of guessing.

### Audit pass — duplicated logic found and closed (second look, 2026-11-26)

Every fix above was re-read against the rest of the repo for a second implementation of the
same rule. Seven were hiding, and each one could have restored the old symptom:

| Duplicate | Where | Closed by |
|---|---|---|
| Three separate Android reverse decisions — and the in-motion one tested **neutral before reverse**, so it could show `N` while backing up | `OverviewScreen`, `RpmScreen`, `Mx5CarScreen` | one `Telemetry.isReverse()` / `Telemetry.gearText()`, used by all three |
| A second implementation of the app's ramp | `tools/simulators/led_simulator/app_palette.py` | ported to the engine ramp; `palette_parity.py` now asserts Java ⇄ Python ⇄ **firmware `rampStops[]`** |
| A third copy of the colours in the LED editor's defaults (`0a84ff` vs `0000ff`, `ef4444` vs `ff0000`) | `LedScreen.DEFAULT_COLOURS` | aligned, and `palette_parity.py` now parses and checks it — proven to fail when perturbed |
| A second gear-text chain (clutch tested **before** reverse) | `tools/simulators/esp32_live_simulator.py` | mirrors the `ui_core` chain and gained `isReverse()` |
| A wrong 5-speed ratio table (`3.136 … 0.814`) plus a made-up `/25` divisor for demo speed | `main.py:_update_demo` | derives speed from `GearEstimator.MPH_PER_1000_RPM` |
| A calibration knob that existed on **one of three** surfaces, i.e. a new way for the ladder and the gear to disagree | `ui_core.cpp: RPM_CALIBRATION` | removed; `TIRE_DIAMETER_IN` is the only knob, and the comment names the other two files that must change with it |
| An unused `LCD_FramebufferActive()` in the new driver API | `Display_ST77916` | removed |
| The Pi's default address written twice, in `MainActivity` and again in `Mx5CarScreen` | — | one `PiClient.DEFAULT_ADDRESS` |

Also reconciled: the stale "the phone pushes a theme-derived ramp" claims in
[LED_REVAMP_PLAN.md](LED_REVAMP_PLAN.md), `tools/simulators/led_simulator/README.md` and two
code comments, and a comment that still pointed at the deleted `KMH_PER_1000_RPM`.

Two things were checked and deliberately **not** changed: `Telemetry.connected` turned out to
be `Led.connected` (live, not a dead field — the in-motion staleness check correctly uses
`canConnected`), and the `test_parser.py` / `test_sound.py` failures are environmental
(Windows console encoding, no audio device), not code.

### Drive-mode review (the in-motion Android Auto surface)

Read end to end: manifest, service, session, screen, the `/api/telemetry` payload it consumes,
and the transport layer behind it.

**Correct as found.** The drive manifest is the only one with no `android:appCategory`, and the
only one declaring `CarAppService` + `category.IOT` + the `template` descriptor; the service is
exported with the right action and label; `PaneTemplate` carries six text-only rows and one
`APP_ICON` header action, so nothing interactive is asked of the host in motion;
`Mx5CarScreen` does all I/O on a worker thread, posts only `invalidate()` to the main looper,
guards against overlapping fetches, releases the shared client on teardown, and re-reads
`use_mph` per template so the phone's toggle applies without restarting the session.
`PiClient.isConfigured()` reads as "configured" but means "at least one transport is
addressable" — with `DEFAULT_ADDRESS` always set, the fetch is attempted rather than skipped, so
there is no spinner-forever path.

**Fixed in this pass:**

- the staleness timestamp used `System.currentTimeMillis()`; a phone that syncs its clock after
  boot can jump it backwards, which would make a minute-old reading look fresh. Now
  `SystemClock.elapsedRealtime()`, which is monotonic;
- the Pi's default address was duplicated between `MainActivity` and `Mx5CarScreen` — one
  `PiClient.DEFAULT_ADDRESS` now.

**Two limitations, documented rather than papered over:**

- `can_connected` means "either bus has traffic", not "the engine frame is arriving". If HS-CAN
  dies while the body bus keeps talking, the drive screen shows `0` and `N` instead of `--`.
  Fixing that properly needs an `engine_live` field on the Pi's payload — a Pi/API change, not
  an app one;
- `MX5 Drive` is a **separate package**, so its `mx5` SharedPreferences start empty even when
  the parked app is configured. Over the USB tether that is harmless (HTTP is unauthenticated);
  over Bluetooth the Pi requires a token *if it has one*, so a fresh install links on the cable
  and is rejected over Bluetooth until the token is entered in *that* app once. The comment in
  `Mx5CarScreen` now says so, because this looks exactly like "the drive app doesn't work".

---

## Summary

| ID | Finding | Subsystem | Type | Severity | Relation |
|----|---------|-----------|------|----------|----------|
| [ISSUE-19](#issue-19--reverse-still-reads-as-gear-1) | Reverse still shows **gear 1**, never `R` | Pi → ESP32-S3 | Bug | 🟠 High | Recurs [ISSUE-01](KNOWN_ISSUES.md#issue-01--reverse-gear-not-detected-on-esp32) / [ISSUE-14](KNOWN_ISSUES.md#issue-14--reverse-reports-a-positive-speed-and-gear-1) |
| [ISSUE-20](#issue-20--gear-ladder-predicts-rpm-about-5-low) | Predicted RPM on the gear ladder is ~5% **low** | ESP32-S3 (+ Android) | Bug | 🟡 Medium | New |
| [ISSUE-21](#issue-21--startup-animation-flickers-all-through) | Startup animation **flickers constantly**; needs polish | ESP32-S3 | Bug + Polish | 🟠 High | Recurs [ISSUE-07](KNOWN_ISSUES.md#issue-07--startup-animation-is-plain) |
| [ISSUE-22](#issue-22--dashboard-is-not-viewable-while-driving) | Dashboard **not viewable while driving** | Android Auto | Feature | 🟠 High | Recurs [ISSUE-09](KNOWN_ISSUES.md#issue-09--app-is-not-available-while-driving) |
| [ISSUE-23](#issue-23--led-strip-still-feels-laggy) | LED strip **still laggy**; gradient not smooth | Arduino Nano | Bug | 🟠 High | Recurs [ISSUE-12](KNOWN_ISSUES.md#issue-12--led-strip-is-laggy-and-lacks-a-gradient) |
| [ISSUE-24](#issue-24--led-colours-are-washed-out-and-red-reads-pink) | LEDs **washed out**, red reads **pink**, colours no longer track RPM | Android theme → Nano | Bug | 🟠 High | New (introduced by the theme ramp) |

**Severity key:** 🔴 Critical = wrong data a driver may act on · 🟠 High = clearly broken or
visibly bad · 🟡 Medium = wrong but minor · ⚪ Low = cosmetic.

---

## Work queue

Ordered by *certainty of the fix*, not severity — the first three can be closed without driving.

| # | Item | Blocked on | Effort |
|---|------|-----------|--------|
| 1 | **LED colours** ([24](#issue-24--led-colours-are-washed-out-and-red-reads-pink)) | nothing — reproducible offline from the palette code | S |
| 2 | **Predicted RPM** ([20](#issue-20--gear-ladder-predicts-rpm-about-5-low)) | nothing — a table is simply wrong | S |
| 3 | **Startup flicker** ([21](#issue-21--startup-animation-flickers-all-through)) | nothing — root cause is visible in the draw path | M–L |
| 4 | **LED lag** ([23](#issue-23--led-strip-still-feels-laggy)) | one `STATUS` line from the car to separate the causes | S → M |
| 5 | **Reverse** ([19](#issue-19--reverse-still-reads-as-gear-1)) | **one 8 s capture in park + one in reverse** — this is the only thing left | S (capture) → M |
| 6 | **Driving visibility** ([22](#issue-22--dashboard-is-not-viewable-while-driving)) | Play Console ($25 one-time) or the HDMI route | M → L |

---

## Measurement prerequisites

Three of the six need evidence that only the car can produce. Get these in one session and
five of the six become decidable:

1. `curl -s localhost:5000/api/telemetry` while rolling backwards → `speed_raw`,
   `transmission_range`, `speed_kmh`, `gear`.
2. `python3 tools/can/reverse_probe.py capture park --seconds 8` then
   `... capture reverse --seconds 8`, then `... diff park reverse`.
3. The Nano's once-a-second `STATUS:` line (already printed) — plus the two fields proposed in
   [ISSUE-23](#issue-23--led-strip-still-feels-laggy) (`PER=`, `LAG=`), which do not exist yet.
4. A phone screenshot of the LED strip at ~6800 rpm, and the scheme + dark/light mode in use.

---

## ISSUE-19 — Reverse still reads as gear 1

**Reported:** “Reverse detect gear, esp32 is not detecting the gear as reverse when speed is
backwards. Only shows gear 1 for in reverse. This has been an issue for literally like a year
after many many attempts to fix.”

**Status:** ❌ **Still broken in the car.** Recurs [ISSUE-01](KNOWN_ISSUES.md#issue-01--reverse-gear-not-detected-on-esp32)
and [ISSUE-14](KNOWN_ISSUES.md#issue-14--reverse-reports-a-positive-speed-and-gear-1). The code
half was closed on 2026-10-30; the open half has not moved because the capture was never taken.

### The thing to state plainly

**The ESP32 is not the suspect, and a year of attempts has been spent on it.** The display
already gives the explicit reverse flag priority over the gear number, on both screens:

- [ui_core.cpp](../display/src/ui_core/ui_core.cpp) — Overview at the gear glyph
  (`telemetry.isInReverse || telemetry.gear == -1` → `R`) and the RPM screen at
  `snprintf(gearStr, ..., "R")`.
- The flag arrives in `TEL:` field 16 and is parsed in
  [main.cpp](../display/src/main.cpp#L1203).

The flag is written by exactly one function on the Pi,
[`_update_gear_estimation()`](../pi/ui/src/can_handler.py#L1047), and that function only sets it
when **`speed_kmh < 0`** or when the `0x231` range code is in
[`REVERSE_RANGE_CODES`](../pi/ui/src/can_handler.py#L255) — which ships **empty**.

So: if the strip shows `1`, the Pi sent `is_in_reverse = 0`, which means the Pi never saw a
negative speed and never saw a configured range code. Nothing the display does can change that.

### Why it lands on exactly 1

This is the part that explains the *specific* number, and it is worth recording because it will
happen again the moment anyone "fixes" the estimator:

```python
# can_handler.py — estimate_gear()
if speed_mph < 3:                       # walking pace, i.e. every reverse manoeuvre
    return (recommended_gear, ...)      # recommended_gear == 1 for anything under ~2 mph
```

With a **positive** speed of 2–3 mph, `estimate_gear()` never even reaches the ratio comparison:
it returns the *recommended* gear for that speed, and `suggest_gear_for_speed()` picks 1st
because 2 mph in 1st is closest to its 3500 rpm target. So `1` is not a bad ratio match — it is
the deliberate "we can't tell, suggest the lowest gear" branch. It will look identical in
reverse and in 1st, by construction.

### Where the sign comes from

The field is **not signed on the wire** — it is `speed + 100 km/h` in 0.01 km/h units, so
`0x2710` is 0.00 km/h and the sign only exists *after* the offset is removed. Forward can never
fall below that zero point, which is what makes a re-offset value below zero **proof** that the
car is rolling backwards rather than an inference to be corroborated.

`parse_speed()` does exactly that, and it is the only decoder in the repo — there is no second
path that could be reading the offset value raw. The encoding is documented by two independent
sources (RaceChrono's MX-5 NC decode and a published DBC); see
[CAN_MANUAL.md](CAN_MANUAL.md#the-rule-that-keeps-getting-re-derived-speed-is-offset-not-signed).
A synthetic frame at `0x251C` (95.00 km/h of offset = −5.00 km/h) runs the whole chain correctly:

```
raw 0x251C -> decode -5 -> gear -1 -> TEL:…,-5,-1,…,1
```

So the code was never missing the sign. What it *was* doing is letting other things override
it. Two did, and both are now gone:

1. the **neutral bit** from `0x231` — whose range semantics on this car have never been
   confirmed — was allowed to veto a negative speed;
2. each display re-derived reverse from its own flag instead of from the sign, and the
   in-motion screen even tested neutral *first*.

Reverse is now `speed < 0`, full stop, in exactly one place per platform.

### Why it lands on exactly 1

This is the part that explains the *specific* number, and it is worth recording because it will
happen again the moment anyone "fixes" the estimator:

```python
# can_handler.py — estimate_gear()
if speed_mph < 3:                       # walking pace, i.e. every reverse manoeuvre
    return (recommended_gear, ...)      # recommended_gear == 1 for anything under ~2 mph
```

With a **non-negative** speed of 2–3 mph, `estimate_gear()` never even reaches the ratio
comparison: it returns the *recommended* gear for that speed, and `suggest_gear_for_speed()`
picks 1st because 2 mph in 1st is closest to its 3500 rpm target. So `1` is not a bad ratio
match — it is the deliberate "we can't tell, suggest the lowest gear" branch. It is only ever
reached with a non-negative speed, which is precisely why the sign must be checked first.

### What is left

Only one question remains, and it is not about the encoding: **is the car running this code?**
The `REV:` journal line prints the decoded speed, the raw field, the neutral bit, the range code
and the gear on every state change, so a single shift into R says whether the Pi produced a
negative number. If it did, the panel shows `R`; if it did not, the raw field will be sitting at
or above `0x2710`, and then — and only then — these fallbacks matter:

| Candidate source | Where | State |
|---|---|---|
| `0x231` transmission-range nibble | [`parse_range()`](../pi/ui/src/can_handler.py#L229) keeps the raw code in `telemetry.transmission_range`; `REVERSE_RANGE_CODES` turns it into `R` | **Wired, set empty.** One capture fills it in |
| Backup-lamp bit on `0x290` / `0x4A0` | [`parse_headlights()`](../pi/ui/src/can_handler.py#L361) decodes only bit 0 of byte 0 and bit 0 of byte 1 — 14 bits unused | Not decoded |
| Physical reverse switch → spare Pi GPIO | — | Not wired |

`tools/can/reverse_probe.py` diffs two captures and names the frame, byte and bit that changes
(`tools/can/test_reverse_probe.py`, 7/7). If a range code is ever observed, putting it in
`REVERSE_RANGE_CODES` makes reverse independent of the sign entirely — no other change needed.

### Done when

Selecting reverse shows `R` on Overview and RPM within one refresh; the speed card shows the
reverse speed (or `0` with the `R` marker); the gear ladder shows `REVERSE`; neutral does not
flicker between `R` and `1` at walking pace.

---

## ISSUE-20 — Gear ladder predicts RPM about 5% low

**Reported:** “Predicted RPMs in from the gear are slightly too low than actual.”

**Status:** 🟡 **Open, and reproducible offline.** This one is a wrong constant, not a sensor.

### Evidence

The ladder on the Overview screen converts road speed to RPM with a hard-coded table,
[`KMH_PER_1000_RPM`](../display/src/ui_core/ui_core.cpp#L1226):

```c
static const float KMH_PER_1000_RPM[7] = {
    0.0f, 7.92f, 13.13f, 18.11f, 25.09f, 29.79f, 35.32f
};
```

Computing the same thing from the driveline everyone else uses — ratios `3.760/2.269/1.645/1.187/1.000/0.843`,
4.10 final drive, 24.3" tire — gives a table that is **4.9% lower**, consistently across all six
gears:

| Gear | km/h per 1000 rpm (from 24.3") | In `ui_core.cpp` | Implied tire diameter |
|---|---|---|---|
| 1 | 7.547 | 7.92 | 25.50" |
| 2 | 12.506 | 13.13 | 25.51" |
| 3 | 17.250 | 18.11 | 25.51" |
| 4 | 23.906 | 25.09 | 25.50" |
| 5 | 28.376 | 29.79 | 25.51" |
| 6 | 33.661 | 35.32 | 25.50" |

Every entry implies the **same 25.5" wheel**, so the table is internally consistent — it was
just computed from the wrong tire (or a wheel-diameter/rolling-radius mix-up). Because
`predictedRpm()` divides by this table, a larger km/h-per-1000-rpm makes the predicted RPM
**lower**:

```
predicted = speed / 7.92 * 1000      at 20 km/h in 1st → 2525 rpm
actual    = speed / 7.547 * 1000     at 20 km/h in 1st → 2650 rpm
```

At a genuine 3000 rpm in 4th the ladder prints **2860** — the ~140 rpm drift the owner sees.

The other two implementations of the same maths use 24.3" and agree with each other, which is
what makes this a one-file bug rather than a calibration argument:

- [GearEstimator](../pi/ui/src/can_handler.py#L396) — `TIRE_DIAMETER_INCHES = 24.3`
- [GearRpmView.java](../android/mx5-remote/src/main/java/com/mx5/remote/GearRpmView.java#L46) —
  `TIRE_DIAMETER_IN = 24.3f`

### Second-order error (applies to all three)

24.3" is the *static* outside diameter of a 205/45R17. A loaded tire rolls on a smaller radius
(typically ~2–3%), so even the "correct" table under-predicts by another few percent. A
calibration that uses the **measured** rolling circumference, or a single scale factor measured
against the tachometer, is the robust fix; the nominal geometry is only a starting point.

### Proposed approach

1. Fix the table (or delete it and derive it from named constants) → closes the 4.9%.
2. Stop keeping three copies of the driveline. Either generate the ESP table and the Java
   constants from one source, or at minimum add a comment on each pointing at the other two and
   a test that asserts they agree.
3. Optionally add a `rpm_scale` calibration factor (default 1.00) applied in all three, set from
   one steady-speed drive: at 3000 rpm in 4th, `scale = 3000 / ladder_rpm`.

### Verify

Park on a flat road, hold **3000 rpm in 4th** at steady speed. The ladder's 4th-gear figure must
read 3000 ± 15 rpm, and the Android `GearRpmView` must read the same. No car needed for the
arithmetic half: the table above is checkable with a calculator.

### Done when

All three surfaces agree within 1% and within 1% of the tachometer at a steady 3000 rpm.

---

## ISSUE-21 — Startup animation flickers all through

**Reported:** “ESP32-S3 startup animation polishing, I want the startup for the device to be more
polished and impressive, maybe a cool animation. Currently the startup animation flickers
constantly throughout the whole animation.”

**Status:** 🟠 **Open.** Recurs [ISSUE-07](KNOWN_ISSUES.md#issue-07--startup-animation-is-plain),
which rebuilt the sequence but only ever rendered it through the desktop simulator. The simulator
cannot show this defect: it draws into a pixel buffer, while the panel is written **region by
region, straight to GRAM**.

### Root cause

The boot film repaints the whole panel every frame — that part is by design ("every frame
repaints the backdrop and the whole effect", [ui_core.cpp](../display/src/ui_core/ui_core.cpp#L614))
— but every primitive in that repaint is its own QSPI transaction:

| Call | Implementation | Transactions |
|---|---|---|
| `drawBackground()` | [`LCD_DrawImage`](../display/lib/WaveshareDisplay/Display_ST77916.cpp#L1089) | 8 (32 KB bands) |
| `LCD_DrawPixel()` | one `esp_lcd_panel_draw_bitmap(x, y, x+1, y+1, &px)` | **1 per pixel** |
| `LCD_FillCircle()` | [`LCD_FillCircle`](../display/lib/WaveshareDisplay/Display_ST77916.cpp#L747) — one `LCD_FillRect` per scanline | **2·r+1 per circle** |

Count one particle-phase frame ([`bootFilm()`](../display/src/ui_core/ui_core.cpp#L803)):

- 120 particles × 4 trail dots = **480** circle calls (each r = 1–2 → one `FillRect` each) = **480 transactions**
- ignition (0–0.9 s, its own beat): one disc at r ≈ 14 (**~29** scanline writes) + 2 rings × 60 dots = **~150 transactions**
- impact: a core disc up to r = 58 (**~117**) + 3 shockwave rings of `64 + 0.45·r` dots ≈ **~400** → **~520 transactions**
- emblem scale-in: **one `LCD_DrawBuffer` per row → ~200 transactions** per frame
- plus the 8-band backdrop

So a single frame is **~500–700 separate panel writes**, spread over tens of milliseconds,
against a panel that has no frame buffer of its own to hide the partial state. The panel therefore
displays a *mixture* of the previous frame and the new one for most of the animation: bright dots
appear, vanish and reappear as their regions are rewritten. That is the flicker, and it is why it
is constant for the whole animation rather than at one beat.

The "25 fps while particles are on screen" figure in ISSUE-07 is not achievable at that
transaction count; it was a design target, not a measurement.

### Proposed approach

The panel is a 360×360 ST77916 over QSPI and the board has **OPI PSRAM enabled**
(`display/platformio.ini`), so there is room for a real frame:

1. **Compose into a PSRAM framebuffer** (360 × 360 × 2 = 259,200 bytes) and push it once per
   frame in 32 KB bands → **8 transactions per frame** instead of ~600. All the effects in
   `bootFilm()` are closed-form functions of `(time, index)`, so they can simply write bytes.
   The existing background image becomes a `memcpy` into the same buffer instead of a blit.
2. **Push bands only where they changed** once the film reaches its incremental tail (the settle
   and wordmark beats already work that way) — or double-buffer and swap.
3. **Optional, and the real fix for tearing:** the ST77916 has a tearing-effect (TE) output. If
   it is available on this module, gate the band push on it. Not required once the whole frame
   lands inside one scan period.
4. **Measure, don't assume.** Print `micros()` deltas around `ui_startupFrame()` for the duration
   of the boot, and the number of `draw_bitmap` calls per frame, behind a `#ifdef`. Every future
   animation change gets judged against that instead of against the simulator.

### On “more polished and impressive”

Worth deciding *before* the implementation, because it changes the design:

- One continuous timeline with no dead frames (the current beats already overlap — keep that).
- Fewer, larger, *slower* elements read as premium; many small fast particles read as busy and
  are also the most expensive thing here.
- Land the animation on the exact frame the wait screen starts: one 1-frame crossfade, no flash
  of a different background.
- The boot theme is already loaded from NVS before the animation, so the polish can be per-theme
  — but see [ISSUE-24](#issue-24--led-colours-are-washed-out-and-red-reads-pink): do not derive
  the *tach ring's* colours from the theme, only the decorative ones.

### Done when

No visible flicker at arm's length in the car; measured full-frame time < 40 ms with fewer than
16 panel transactions per frame; the sequencer still reproduces frame-for-frame in
`esp32_ui_simulator` (the stills must not change *because* of the transport change).

---

## ISSUE-22 — Dashboard is not viewable while driving

**Reported:** “App and drive mode, app not allowable in car driving mode. I want it to be viewable
during driving.”

**Status:** 🟠 **Open.** Recurs [ISSUE-09](KNOWN_ISSUES.md#issue-09--app-is-not-available-while-driving),
which fixed the manifest and identified the distribution blocker but never saw a tile on the head
unit.

### Why the app you can see is disabled in motion

It is not a bug in the app — it is the classification:

```xml
<!-- src/parked/AndroidManifest.xml -->
<application android:appCategory="game" ...>
    <activity ...>
        <category android:name="android.intent.category.CAR_LAUNCHER" />
```

Android Auto greys out a `game`-category `CAR_LAUNCHER` activity as soon as the vehicle moves.
That is the documented behaviour and the reason two flavours exist.

The in-motion surface is the **drive** flavour (`com.mx5.remote.drive`): no `appCategory`, a
`CarAppService` with `androidx.car.app.category.IOT`, and the
`com.google.android.gms.car.application` → `automotive_app_desc.xml` meta-data, all present in
[src/drive/AndroidManifest.xml](../android/mx5-remote/src/drive/AndroidManifest.xml). It builds.
What fails is that Android Auto stopped enumerating **sideloaded** templated apps
(`CAR.AUTH: … isPackageAllowed = false`), so a hand-installed APK does not appear.

### The three routes — pick one deliberately

| Route | Allowed in motion | Cost | Notes |
|---|---|---|---|
| **A. Drive flavour via Play internal test track** | ✅ yes, host-drawn templates | $25 one-time, no review | The supported path. 6 rows at 367 dp; interactive controls are limited by AA policy |
| **B. Parked dashboard over HDMI** (Pi → AVH-W4500NEX) | ✅ yes — the head unit does not know what is on the HDMI input | already-planned hardware | The *only* way to show the full, interactive dashboard in motion. Blocked on the Pi4B HDMI issue in [TROUBLESHOOTING_GAMEPLAN.md](../TROUBLESHOOTING_GAMEPLAN.md) |
| **C. Parked dashboard in Android Auto** | ❌ never | $0 | Keep for stopped use only |

If the requirement is “I want to see the dashboard while driving”, route **B** is the only one
that delivers the actual dashboard; route **A** delivers a six-row glanceable summary and is
subject to Google's driving-distraction rules. Worth deciding which one “viewable” means before
spending on either.

### Verify

Route A: the “MX5 Drive” tile appears in the AA launcher, opens while rolling, and refreshes once
a second. Route B: the head unit shows the Pi's output with the car in gear.

---

## ISSUE-23 — LED strip still feels laggy

**Reported:** “LED refresh rate, the Arduino LEDs are wayyy too laggy and also the colours should
transition smoother so there is a smooth colour gradient from bottom to top of the RPM range.”

**Status:** 🟠 **Open.** Recurs [ISSUE-12](KNOWN_ISSUES.md#issue-12--led-strip-is-laggy-and-lacks-a-gradient).
The 2026-10-30 fix removed the float maths, the lost interrupt and the 10 ms timer, and
`test_latency.py` models ~4 rpm mean error — **yet it still feels laggy in the car**. That means
the model is missing a term, and the terms below are the candidates, ranked.

### What the chain is today

| Stage | Value | Source |
|---|---|---|
| `0x201` period | ~50 Hz on the bench model (20 ms) | [LED_REVAMP_PLAN.md](LED_REVAMP_PLAN.md#42-refresh-path-where-the-delay-actually-is) |
| CAN poll fallback | 2 ms | `CAN_POLL_INTERVAL` [main.cpp](../arduino/src/main.cpp#L103) |
| Repaint cadence | 4 ms | `LED_UPDATE_INTERVAL` [main.cpp](../arduino/src/main.cpp#L105) |
| Prediction horizon | one sample period, **capped at 40 ms** | `RPM_EXTRAPOLATE_MS` [main.cpp](../arduino/src/main.cpp#L244) |
| Rising / falling filter | 1.00 / 0.75 | [main.cpp](../arduino/src/main.cpp#L229) |
| `strip.show()` | ~0.6 ms, interrupts off | 20 × 24 bits |
| Bar resolution | **10 ranks** (`SEQ_CENTER_OUT` mirrors 20 LEDs) | [`barRank()`](../arduino/src/main.cpp#L923) |

### Candidate causes, ranked

**1. The serial port is 9600 baud and the loop blocks on it.** (Most likely single cause of a
*periodic* hitch.) The shipped build is `ENABLE_SERIAL_CMD true`, `ENABLE_SERIAL_DEBUG false`, so
[`Serial.begin(9600)`](../arduino/src/main.cpp#L1332). The once-a-second `STATUS:` line is ~110
bytes = **~115 ms of wire time**; the AVR's TX ring is 64 bytes, so `print()` inside `loop()`
blocks for roughly **50 ms every second**. A `RAMP:` line is 76 bytes ≈ 79 ms. That is a visible
hitch, once per second, forever, and it is not in the latency model.

**2. Ten ranks is coarse.** A centre-out strip of 20 LEDs has `LED_COUNT / 2 = 10` ranks, so one
rank is `6800 / 10 = 680 rpm`. At a normal 2000 rpm/s rev that is a step every ~340 ms — which
reads as “laggy” even with perfect timing. `SEQ_LEFT_TO_RIGHT` gives 20 ranks (340 rpm/step) at
zero cost if the strip is physically wired end-to-end; more LEDs is the only real fix.

**3. The predictor stops early if this car's `0x201` is slower than 40 ms.** The horizon is
`min(sample_gap, RPM_EXTRAPOLATE_MS)`. The 50 Hz figure came from a bench model, not from this
car. If `0x201` is, say, 20 Hz (50 ms), the last 10 ms of every period is frozen — and if it is
slower than 100 ms, `RPM_MAX_SAMPLE_GAP` rejects the sample as a stalled link and the bar is a
pure staircase.

**4. Falling filter.** `RPM_ALPHA_FALLING 0.75` at 50 Hz costs about two samples (~40 ms) on a
closed throttle. `RPM_SNAP_DELTA 250` only bypasses large drops — a normal gear change drops
~2000 rpm so it snaps, but a lift-off roll-down does not.

**5. `strip.show()` is unavoidable** (0.6 ms with interrupts masked) but a frame arriving inside
that window loses its edge-triggered interrupt and waits for the 2 ms poll. Already mitigated,
worth keeping in mind before blaming the renderer.

### What to instrument (one drive, no guessing)

Add two fields to the existing `STATUS:` line — this is the whole diagnostic:

- `PER=` — the measured `0x201` inter-arrival period, averaged over the last second.
- `LAG=` — the maximum loop iteration time in the last second, in µs. If `LAG` spikes to ~50000
  once a second, cause 1 is confirmed; if `PER` is 50, cause 3 is dead; if both are clean and it
  still feels laggy, it is cause 2 (resolution) and the answer is more LEDs.

Also worth printing the count of dropped/overrun frames (MCP2515 EFLG RX1OVR/RX0OVR) — 2 RX
buffers behind a 0.6 ms `show()` can silently lose the newest engine frame.

### Proposed approach

1. `Serial.begin(115200)` and/or shorten `STATUS:` (print only when it changed, or split it across
   two lines). Free, and removes a known 50 ms/s block.
2. Raise `RPM_MAX_SAMPLE_GAP` and the `RPM_EXTRAPOLATE_MS` ceiling to the *measured* period,
   keeping `RPM_MAX_SLOPE` as the plausibility guard.
3. Try `SEQ_LEFT_TO_RIGHT` on the car (one app tap) and compare — if the strip is wired as a single
   run this halves the step size immediately.
4. Consider `RPM_ALPHA_FALLING 0.85`.

### On “smoother gradient bottom to top”

The firmware already samples each LED's own position on the ramp
([`renderBar()`](../arduino/src/main.cpp#L989), `rampColorAtRpm((p_q * rpm) >> 16)`), so the
*shape* is right. What is not smooth today is the **colour set** — see
[ISSUE-24](#issue-24--led-colours-are-washed-out-and-red-reads-pink), which is the larger half of
this complaint. Two numerical contributors that belong here:

- `renderBar()` interpolates and writes **sRGB values with no gamma correction**, while the boot
  animation uses `strip.gamma32()`. WS2812 output is linear in light, so an sRGB-space ramp has
  uneven perceived steps and a crushed low end.
- Six stops spread over ten ranks means each LED can jump several stops between frames. Either
  send more stops (the Pi already streams the ramp — 12 would cost ~150 bytes once) or pre-compute
  a 256-entry LUT on the Pi and stream that.

### Done when

Full-throttle blips track the tach with no visible step at ~2000 rpm/s; there is no once-a-second
hitch; `LAG` stays under ~5 ms and `PER` matches the horizon in use.

---

## ISSUE-24 — LED colours are washed out and red reads pink

**Reported:** “The colours should transition smoother… also we need to look at the colours again to
ensure they make sense for the respective RPMs. Currently the LEDs are way too white washed,
especially in dark mode. I don't want the colours white washed at all unless the target colour was
white. The red LED currently looks like light pink.”

**Status:** 🟠 **Open, and reproducible offline** — the colours can be computed from the palette
code without the car.

### Root cause: the strip's ramp is derived from the theme, not from RPM

The firmware ships a semantic ramp ([`rampStops[]`](../arduino/src/main.cpp#L172)): blue → cyan →
green → yellow → orange → **red at 6800**. But as soon as the app can reach the Pi it **replaces**
that table with one derived from the colour scheme — it pushes on launch and on every theme change,
because `led_follow_theme` defaults to `true`
([`pushThemeToPi()`](../android/mx5-remote/src/main/java/com/mx5/remote/MainActivity.java#L908) →
`led_ramp` → `RAMP:` on the Nano).

That derived ramp is [`Palette.ramp()`](../android/mx5-remote/src/main/java/com/mx5/remote/Palette.java#L145):

```java
return new int[]{ accent, mix(accent, primary, 0.40f), mix(accent, primary, 0.75f),
                  primary, mix(primary, seedB, 0.55f), seedB };
```

with, in dark mode, `accent = lift(seedA, 0.18)` and `primary = lift(seedB, 0.18)` — i.e. **both
seeds blended 18% toward white**. Two things follow:

1. **White wash.** `lift()` adds white in sRGB, which raises R, G and B toward equal values: it
   desaturates, it does not brighten. Aurora's dark ramp computes to

   ```
   #2ECCCC  #829FC0  #CB77B5  #FF5BAD  #FF47A3  #FF379B
             ^^^^^^  — a grey-blue; the middle of the bar has almost no chroma
   ```

2. **Red is pink, and the top of the range is not red at all.** The last stop is `seedB`, verbatim.
   For `crimson` the second seed *is* `#F472B6`; for `aurora` it is `#FF379B`; for `sunset`,
   `#EC4899`. So the “redline” LED is magenta on most schemes:

   ```
   crimson dark: #E24D4D #EA667C #F17CA6 #F68BC3 #F57DBC #F472B6
   ```

Brightness dimming (`DIM_SCALE 170` for dark mode) cannot restore saturation, so the strip is
washed in exactly the mode that gets dimmed.

This is also why the request “make the colours make sense for the respective RPMs” cannot be
answered by tuning numbers today: **the ramp does not encode RPM.** The same 5000 rpm is green in
one theme and orange in another, and several themes have no red anywhere on the bar.

The design intent is recorded in [LED_REVAMP_PLAN.md §2.2](LED_REVAMP_PLAN.md#22-color-mapping--why-the-current-one-feels-wrong)
and it was a deliberate choice — “every stop is this scheme's own two hues, so changing the theme
changes the whole bar”. It is the wrong choice for an instrument, and the owner has now said so.

### Proposed approach

1. **Make the semantic ramp the truth again**: blue/cyan at idle → green in the economical band →
   yellow → orange → **red at the redline**. That is what a shift light has to mean, and it is
   what makes a bottom-to-top gradient informative.
2. **If theme-following is kept at all**, keep saturation: derive variant *hues* at fixed
   saturation/lightness (HSL `S ≥ 0.85`), never by blending toward white. Concretely: `lift()` must
   not be used for LED colours in dark mode; dark mode should lower lightness, not add white.
3. **Never let the ramp's top stop be a theme colour.** Whatever the other five stops are, the last
   one is the redline red.
4. **Interpolate in a perceptual space, or pre-compute.** The Nano can only do integer
   interpolation, so either (a) interpolate in HSV with S,V held and convert per stop, or (b) let
   the Pi/phone compute a 256-entry gamma-corrected LUT and stream it once (the settings channel
   already carries `RAMP:`; a `LUT:` line is the same mechanism). Option (b) also removes the
   banding from [ISSUE-23](#issue-23--led-strip-still-feels-laggy) and makes the perceived ramp
   smooth on a 16 MHz AVR.
5. **Gamma.** Apply a 2.2-ish gamma to the final 8-bit values (Adafruit's `gamma32` table is
   already linked and used by `startupAnimation()`; `renderBar()` does not use it).
6. **Guard it in the app.** If a derived colour comes out with chroma below a floor, re-saturate
   it or refuse it — so a future scheme cannot reintroduce this silently.

### Verify

No car needed for most of it:

- Render the six stops for all twelve schemes in both modes and assert: chroma floor, last stop is
  red-dominant (`R > 200`, `G < 60`, `B < 60`), and R/G/B are not all within 10% of each other
  except at a stop that is explicitly white.
- `esp32_ui_simulator` / the LED simulator for the bar itself.
- In the car: a photo at ~6800 rpm. Red must photograph as red; nothing may be white except a
  deliberate white stop.

### Done when

Red is red in every theme and mode; the bar is monotone in hue from bottom to top; no washed-out
middle; `renderBar()` applies gamma; and a scheme can no longer produce a low-chroma stop.

### Second pass, 2026-11-26 (after the fix above shipped)

The theme-derived ramp is gone and red is exactly `#ff0000`, but a measured re-check found the fix
**incomplete**: two of the six *engine* stops were themselves 23–24 % toward white.

Measured against the compiled firmware — `parity_check.py`'s harness extracts `rampColorAtRpm()`
and `renderBar()` from `arduino/src/main.cpp`, so these are the bytes the Nano writes:

| Stop | Colour | HSV saturation | White-ness (min/max) |
|---|---|---|---|
| 0 | `#0000ff` | 100 % | 0.00 |
| 1400 | `#00dcff` | 100 % | 0.00 |
| 2800 | `#32d782` | **77 %** | **0.23** |
| 4500 | `#ffd23c` | **76 %** | **0.24** |
| 5800 | `#ff8000` | 100 % | 0.00 |
| 6800 | `#ff0000` | 100 % | 0.00 |

and worse *between* the stops, because the bar interpolates in RGB:

| Where | Colour | Saturation |
|---|---|---|
| 3300 rpm, any mode, any dim | `#6cd66e` | **50 %** |

That is the number behind "way too white washed": half way to grey, in the middle of the bar, in
every mode. It survived the first fix for two reasons — the ramp *stops* looked defensible in a
swatch, and the regression test only asserted "not white" (`high - low < 20`), which a 77 % stop
passes comfortably.

**The fix is a property, not a palette.** Every stop now has one channel at zero, and adjacent
stops share that zero channel, so the RGB interpolation keeps it at zero along the whole segment:

```
#0000ff → #00dcff → #00d700 → #ffd500 → #ff8000 → #ff0000
 (R=0)     (R=0)     (R=B=0)   (B=0)     (B=0)     (G=B=0)
```

Measured after the change, over 1108 configurations (both colour modes × both dim states ×
0–6900 rpm in 25 rpm steps) and every lit LED with value ≥ 25 %: **worst saturation 100 %,
white-ness 0.00**, redline `#ff0000`, dark-mode redline `#aa0000`. Dark mode stays safe because
`renderBar()` applies `DIM_SCALE` as a *multiplicative* gain on all three channels, which cannot
change a ratio.

What changed, and what now stops it coming back:

- the six hexes, in all five copies (firmware `rampStops[]`, `Palette.ENGINE_RAMP`,
  `LedScreen.DEFAULT_COLOURS` + swatches, `led_engine.DEFAULT_RAMP`, `app_palette.ENGINE_RAMP`);
- a dead `PALETTE` constant in [`led_simulator_v3.py`](../tools/simulators/led_simulator/led_simulator_v3.py)
  that still held the pre-fix `0a84ff … ef4444` colours, removed;
- [`palette_parity.py`](../tools/simulators/led_simulator/palette_parity.py) now requires every
  stop **and** seven interpolated points per segment to have a zero channel. Reverting the two
  stops to the old values makes it fail with `(127, 213, 104) is only 51% saturated` — proven,
  not assumed.

### A second drift the same audit found

`led_engine.py` — the port `parity_check.py` compares against the firmware — still had
`EXTRAPOLATE_MS = 40` while the firmware had been raised to 60 for ISSUE-23. The comparison that
would have caught it (`check_prediction`) had been *failing to compile* since the `PER=`/`LAG=`
instrumentation was added, because the harness did not stub `micros()` or the three period
globals. Both are fixed: the harness stubs them, and `parity_check.py` now reports 1608 cases,
2892 frames, every pixel identical, plus 784 prediction cases.

---

## Cross-cutting notes

These showed up in more than one issue and are worth fixing once:

- **Three copies of the driveline constants** (Pi `GearEstimator`, ESP `ui_core.cpp`, Android
  `GearRpmView`) already drifted by 4.9% ([ISSUE-20](#issue-20--gear-ladder-predicts-rpm-about-5-low)).
  One source, or a test that compares all three.
- **The simulator cannot see transport defects.** ISSUE-07's animation was signed off on
  simulator stills and flickers on the panel; the LED colour ramp was signed off on computed
  colours and is washed on the strip. Both need a measurement from the device (frame time;
  a photo).
- **Theme-derived device colours are the common cause of**
  [ISSUE-24](#issue-24--led-colours-are-washed-out-and-red-reads-pink) **and the boot palette
  notes in ISSUE-07.** Decorative surfaces may follow the theme; anything that encodes a physical
  quantity (RPM, redline, fault) must not.
- **9600 baud serial is the default on the shipped Nano build** and blocks the LED loop for
  ~50 ms/s ([ISSUE-23](#issue-23--led-strip-still-feels-laggy)). One-line change, no reason to
  keep it.

---

## ISSUE-25 — The Bluetooth link does not survive a reboot or a radio reset

Not one of the six in-car findings; it was reported separately while those were being fixed,
and it shares their shape: **a single wrong assumption, no recovery path.**

### Root cause

`BtLink.start()` ran exactly once, from `PiDisplayApp.__init__` — the moment the Pi is least
likely to have a working radio. `systemd` starts this service and `bluetoothd`, the USB
dongle, or the adapter's own power-on all within the same few seconds, and the unit had no
`After=bluetooth.service` to stop it losing that race on purpose. When the first attempt
failed, `spp` and `ble` were set to `None` and **nothing ever tried again**: the Pi kept
answering on the USB tether and silently had no Bluetooth until the next reboot.

The only recovery was `mx5-bt-agent` noticing that no BLE advertisement existed 90 s later and
running `systemctl restart mx5-display`, which also drops CAN, the panel and every live
session. Fixing a radio problem by restarting the whole car.

There was a second, quieter version of the same fault: both servers' `start()` return early
when a thread handle is set, so a transport whose loop had died (a `bluetoothd` restart takes
the accept loop's socket with it) could never be reopened — `start()` was a no-op on it, and
nothing could tell a live loop from a dead one.

### Fixed

| Change | Where |
|---|---|
| Both transports are supervised for the life of the process: retry at 5 → 10 → 20 → 40 → 60 s, and restart a transport whose loop died | [`bt_link.py`](../pi/ui/src/bt_link.py) |
| `is_alive()` on both servers, so "started once" and "is up" are no longer the same question | [`bt_spp_server.py`](../pi/ui/src/bt_spp_server.py), [`bt_ble_server.py`](../pi/ui/src/bt_ble_server.py) |
| `After=`/`Wants=bluetooth.service`, so the first attempt usually succeeds | [`mx5-display.service`](../pi/mx5-display.service) |
| The agent's whole-service restart is a last resort at 180 s, not the first response at 90 s | [`mx5-bt-agent.py`](../pi/mx5-bt-agent.py) |
| The supervisor is stopped on shutdown, and a transport that finishes starting afterwards is closed rather than adopted | [`bt_link.py`](../pi/ui/src/bt_link.py), [`main.py`](../pi/ui/src/main.py) |

Verified with 8 checks in [`test_bt_link.py`](../pi/ui/src/test_bt_link.py) over fake
transports (no radio needed), plus the existing 70 + 10 Bluetooth checks. Not verified on the
car: that the link now returns after a real ignition cycle. The journal says so within one
tick — `SPP stopped; restarting it` / `BLE link up` — which is the line to look for.

Details, including what supervision deliberately does *not* do: [BLUETOOTH_LINK.md](BLUETOOTH_LINK.md#how-supervision-behaves).

---

## Not the cause

Stated so the next session does not re-check it: the car being offline and the phone being
unplugged are **not** explanations for any of the six. Every finding above is either a wrong
constant, a wrong derived colour, a transport/timing property of the firmware, or a manifest
classification — none of them depends on a live CAN bus or a connected phone.
