# Known Issues — In-Car Findings

**Recorded:** 2026-10-18 · **Re-tested in the car:** 2026-10-30
**Vehicle:** Mazda MX-5 NC (2006-2015)
**Source:** Issues identified during real in-car testing

> ⚠️ **Verification status.** The car was driven on the first round of fixes on
> 2026-10-30 and **five of them were still wrong**: the LEDs never left blue (12), instant
> MPG never showed a number (10), the drive app was unreachable (9), the gear ladder was in
> a confusing order (13), and reverse still showed a positive speed and gear 1 (14/01).
> Those five became the work queue.
>
> **Later the same day** the Pi, the ESP32, the phone and the Nano were all reachable, so
> most of that queue was worked *on the hardware* rather than reasoned about. What that
> proved is recorded per issue; in short:
>
> | Proved live | Evidence |
> |---|---|
> | HS-CAN was listen-only, so no OBD-II reply was ever possible | `ip -details link show can1` reported `LISTEN-ONLY`, TX packets 0 |
> | Intake air and MAF **do** answer once TX is enabled | `IAT: 87F` in the journal; `04 41 10 00 …` reply to `7DF#020110…` |
> | The drive app was missing its Android Auto descriptor | APK rebuilt with `com.google.android.gms.car.application`; service now enumerates on the phone |
> | The gear ladder is numeric and fits the panel | `ui_core.cpp` rewritten, rendered through the native simulator, flashed to the ESP32 |
> | The Nano's CAN link and the strip itself are healthy | `STATUS:CAN=1,FPS=320,LAST=0x201`; the strip lit **all** LEDs in a full gradient at 6500 rpm |
> | The Pi writes to the Nano and the Nano answers | `PING`→`PONG`, `SEQ?`→`SEQ:1`, `SEQ:1` delivered from the dashboard |
>
> The 2026-10-30 round also turned two "suspicions" into confirmed causes, both visible in
> this repo:
> - The Pi brought **HS-CAN up listen-only** (`pi/mx5-can-setup.sh` line 13), so the OBD-II
>   request for MAF/IAT was never transmitted — that is why 10 was dead, and also why 03
>   (intake air temperature) was still 0.
> - The drive app's manifest was **missing the
>   `com.google.android.gms.car.application` → `automotive_app_desc.xml` meta-data** that
>   every Android Auto templated app must declare, so the host had nothing to enumerate —
>   that is why 9 was unreachable.
>
> The **Status** line at the top of each issue is authoritative. The *Working theory* and
> *Proposed approach* sections below it are the investigation notes from before the fix
> and are kept for context; line-number links point at the code as it was then, so the
> file links still work but the `#L…` anchors may have drifted.

---

## Summary

| ID | Issue | Device(s) | Type | Severity | Status |
|----|-------|-----------|------|----------|--------|
| [ISSUE-01](#issue-01--reverse-gear-not-detected-on-esp32) | Reverse gear not detected when speed goes backwards | ESP32-S3 | Bug | 🟠 High | ❌ Still open in the car — see ISSUE-14 |
| [ISSUE-02](#issue-02--esp32-theme-does-not-match-the-android-app) | ESP display theme/dark-light mode does not match the Android app | ESP32-S3 | Feature | 🟡 Medium | ✅ Fixed (unverified in car) |
| [ISSUE-03](#issue-03--intake-air-temperature-always-zero-on-android) | Intake air temperature always 0 | Android | Bug | 🟡 Medium | ✅ **Fixed, verified live** — `IAT: 89F` |
| [ISSUE-04](#issue-04--throttle-and-brake-wrong-on-the-rpm-page) | Throttle and brake wrong on the RPM page | Android (+ ESP) | Bug | 🟠 High | ✅ Fixed (needs CAN log) |
| [ISSUE-05](#issue-05--esp32-gyro-screen-still-uses-the-old-visualization) | Gyro screen still uses the old display code | ESP32-S3 | Bug | 🟡 Medium | ✅ Fixed (unverified in car) |
| [ISSUE-06](#issue-06--android-speed-reads-about-two-thirds-of-actual) | Speed reads ~⅔ of actual | Android | Bug | 🔴 Critical | ✅ Fixed (unverified in car) |
| [ISSUE-07](#issue-07--startup-animation-is-plain) | Startup animation needs polish | ESP32-S3 | Polish | ⚪ Low | 🟡 Improved, **not done** — wants a proper, impressive animation |
| [ISSUE-08](#issue-08--fuel-percentage-is-not-stable) | Fuel % jumps around; needs averaging | Pi / all UIs | Bug | 🟡 Medium | ✅ Fixed (unverified in car) |
| [ISSUE-09](#issue-09--app-is-not-available-while-driving) | App not viewable while driving | Android Auto | Feature | 🟠 High | 🟡 **Descriptor added + installed** — needs the head unit, then possibly a Play track |
| [ISSUE-10](#issue-10--instantaneous-mpg-always-shows-the-empty-placeholder) | Instantaneous MPG always shows `---` | ESP32-S3 / Pi | Bug | 🟡 Medium | ✅ **Fixed, verified live** — MAF and IAT answer |
| [ISSUE-11](#issue-11--tpms-card-should-become-a-gear--rpm-card) | TPMS card on Overview → 3-gear RPM view | ESP32-S3 | Feature | 🟡 Medium | ✅ Fixed — numeric order, see ISSUE-13 |
| [ISSUE-12](#issue-12--led-strip-is-laggy-and-lacks-a-gradient) | LED strip laggy; flat colours, no gradient | Arduino Nano | Bug / Polish | 🟠 High | ✅ **Verified working on the strip** — full gradient at 6500 rpm |
| **ISSUE-13** | Overview gear ladder is not in numeric order | ESP32-S3 | Bug | 🟡 Medium | ✅ **Fixed, flashed** — 2 × 3 grid |
| **ISSUE-14** | Reverse shows a **positive** speed and gear 1, never `R` | Pi → ESP32-S3 | Bug | 🟠 High | ⏳ Open — probe tool ready and analysed offline, capture pending |
| **ISSUE-15** | LED control surface is one chip row; needs a real settings screen | Android + Arduino | Feature | 🟠 High | ✅ **Built** — screen, firmware keys and Pi API; needs a device pass |

**Status key:** ✅ code complete and building · ❌ **verified still broken in the car** ·
🟡 works but wrong/misleading · ⚠️ partially addressed, see the issue · ⏳ open.
"Unverified in car" means the build passes but the car has not been driven since.

**Severity key:** 🔴 Critical = wrong data a driver may act on · 🟠 High = clearly broken or
dangerously stale · 🟡 Medium = visibly wrong or missing information · ⚪ Low = cosmetic.

---

## Work queue (2026-10-30 in-car round)

Ordered by what unblocks the most, not by severity. Everything here is a *new* finding or a
fix that did not survive contact with the car.

| # | Item | Next action | Effort |
|---|------|-------------|--------|
| 1 | **LED strip** ([12](#issue-12--led-strip-is-laggy-and-lacks-a-gradient), [15](#issue-15--the-led-control-surface-is-one-chip-row)) | ✅ firmware, Pi API and the `LED STRIP` app screen are all built. Next: one pass on the car, then power-cycle both ends. | done → verify |
| 2 | **Instant MPG never shows a number** ([10](#issue-10--instantaneous-mpg-always-shows-the-empty-placeholder)) | ✅ fixed on the Pi (`listen-only off` on `can1`) and verified: the ECU answers MAF and IAT. | done |
| 3 | **Drive app not reachable** ([09](#issue-09--app-is-not-available-while-driving)) | ✅ descriptor added, APK rebuilt and installed, service enumerates. Remaining: check it on the head unit, and a Play internal test track if AA still refuses sideloaded templated apps. | S → L |
| 4 | **Gear ladder order** ([11](#issue-11--tpms-card-should-become-a-gear--rpm-card), [13](#issue-13--overview-gear-ladder-is-not-in-numeric-order)) | ✅ numeric 2 × 3 grid implemented and flashed. | done |
| 5 | **Reverse still shows positive speed / gear 1** ([01](#issue-01--reverse-gear-not-detected-on-esp32), [14](#issue-14--reverse-reports-a-positive-speed-and-gear-1)) | Probe tool written (`tools/can/reverse_probe.py`); one capture in neutral vs reverse is still needed. | S (log) → M (fix) |
| 6 | **Startup animation** ([07](#issue-07--startup-animation-is-plain)) | Design pass, then implement. Cosmetic but explicitly wanted. | M |
| 7 | **Fuel % / IAT** ([08](#issue-08--fuel-percentage-is-not-stable), [03](#issue-03--intake-air-temperature-always-zero-on-android)) | ✅ IAT reports live (`89F`); fuel needs a drive to confirm the averaging now that the bus is clean. | S, needs drive |


---

## ISSUE-01 — Reverse gear not detected on ESP32

**Status:** ❌ **Still broken in the car (2026-10-30).** The explicit `reverse` flag was
added and the ESP honours it, but the flag is never true when it matters: driving in
reverse the ESP shows a **positive** speed and gear **1**, not `R`. See
[ISSUE-14](#issue-14--reverse-reports-a-positive-speed-and-gear-1) for the follow-up
investigation — the fault is upstream of the link, so this issue's fix (the flag) is
correct but was never the whole problem.

- `esp32_serial_handler.py` clamps the transmitted speed to `0` and appends
  `reverse` as field 16 of `TEL:`.
- `display/src/main.cpp` reads it into `telemetry.isInReverse`;
  `ui_core.cpp` uses that flag on the Overview and RPM screens.
- `telemetry.isInReverse` is set by the Pi whenever speed is negative, and held for
  500 ms after it returns to zero.

**Remaining:** find a reverse signal that actually exists on this car — the sign of the
speed field does not appear to carry it (ISSUE-14).

**Reported:** When the car is reversing, the ESP32-S3 does not show `R`. The speed value
itself goes backwards (negative), so the CAN data is reaching the system.

**Where it lives:**
- [can_handler.py](../pi/ui/src/can_handler.py#L799) — `_update_gear_estimation()`, reverse
  is detected from negative speed and stored as `gear = -1`
- [esp32_serial_handler.py](../pi/ui/src/esp32_serial_handler.py#L634) — `TEL:` field 3 (gear)
- [ui_core.cpp](../display/src/ui_core/ui_core.cpp#L764) — Overview renders `R` when
  `speed < 0 || gear == -1`
- [ui_core.cpp](../display/src/ui_core/ui_core.cpp#L1061) — same test on the RPM screen

**Working theory:**
The Pi logic and both ESP render paths already look correct, so the break is most likely
in the hand-off rather than in either end. Candidates, in order:

1. **Pi never sets `gear = -1`.** `_update_gear_estimation()` is only called from the
   `0x201` (RPM/speed) branch, and only when `speed_kmh < 0`. If `speed_kmh` arrives as
   `0` (or `-0`) at the moment the frame is sampled, the branch is skipped entirely and
   the estimator runs with a non-negative speed and overwrites the gear.
2. **`-0` in the serial payload.** `esp32_serial_handler` formats speed with `:.0f`, so a
   small negative speed serialises as `-0`. `String::toFloat("-0")` yields `-0.0`, and
   `-0.0 < 0` is **false** in C++. The `speed < 0` half of the render test silently fails,
   leaving only `gear == -1` to carry the state.
3. **Field misalignment** in the `TEL:` parser if any field ever renders empty or
   non-numeric, which would shift gear into a neighbouring slot.

Note that the Pi-side reverse detection deliberately uses `math.floor()` for negative
values so that *any* reverse motion becomes at least `-1`. That part looks sound, which
points at (1) or (2).

**Proposed approach:** Treat reverse as an explicit boolean in the link protocol rather
than inferring it from a signed speed on the ESP. Send `is_in_reverse` as its own `TEL:`
field (or a new `REV:0/1` message), and keep the negative-speed check only as a
backstop. Also stop relying on `-0` formatting: clamp the serialised speed to `0` and
carry the sign in the dedicated field.

**Needs hardware:** Yes — capture the raw `TEL:` line while reversing (Pi console log or
`pio device monitor` on the ESP) to confirm whether field 3 is `-1` and what field 2
actually contains.

**Done when:** Shifting into reverse shows `R` on the ESP32 Overview and RPM screens
within one display refresh, and releasing into neutral shows `N` without flickering
between `R` and `1`.

---

## ISSUE-02 — ESP32 theme does not match the Android app

**Status:** ✅ **Fixed.** The display now follows the phone's scheme and dark/light mode,
and boots dark when the phone has never connected.

- `ui_core.h` colours became a runtime `ThemePalette` (`COLOR_BG`, `MX5_*` are now
  macros over `g_theme`, so every existing call site follows the theme).
- `ui_core.cpp` carries the same 12 schemes as `Palette.SCHEMES`, plus dark/light
  derivation and light-mode contrast adjustments.
- `main.cpp` handles `THEME:<scheme>,<0|1>`, persists it in NVS (`theme` namespace), and
  loads it before the boot animation. No stored theme ⇒ dark aurora.
- `MainActivity` pushes `theme_scheme` / `theme_dark` to the Pi on every change and at
  start-up; `link_service.update_setting` mirrors it and re-syncs the ESP32.
- The Pi only forwards a theme it has actually received (`theme_scheme` starts empty).
  A Pi restart therefore cannot overwrite the display's stored theme with a default —
  the authority stays with the phone, and the display keeps its last known theme.
- Light mode fills the background with the theme colour instead of the fixed dark carbon
  image, the "unlit" stroke colour is a mid-grey, and the RPM arcs/halos now use the
  theme's semantic colours instead of the strip's pure RGB ramp — so page-indicator dots,
  unlit arc segments and the yellow segment all stay visible on a light background.

**Remaining:** visual check on the device. Note the light theme is a deliberate
approximation of the app's OKLCH derivation (sRGB blends), not a pixel match.

**Reported:** The ESP32-S3's colour scheme and dark/light mode should match the Android
app. When the phone is not connected, the ESP should default to dark mode.

**Where it lives:**
- [ui_core.h](../display/src/ui_core/ui_core.h#L39) — `COLOR_BG`, `COLOR_BG_CARD`,
  `MX5_*` palette, all hard-coded "modern dark theme" constants
- [ui_config.h](../display/src/ui_config.h#L27) — duplicate colour definitions
- [Palette.java](../android/mx5-remote/src/main/java/com/mx5/remote/Palette.java#L1) — the
  Android app's 12 schemes (aurora, crimson, emerald, sakura, midnight, sunset, ocean,
  cyberpunk, monokai, usa, forest, neutral) plus dark/light resolution
- [led_simulator/README.md](../tools/simulators/led_simulator/README.md) and
  [ui_simulator/README.md](../tools/simulators/ui_simulator/README.md) — existing harnesses
  worth reusing for visual checks

**Working theory:**
The ESP firmware has no theme concept at all: every colour is a compile-time constant,
there is no light mode, and nothing in the `TEL:`/serial protocol carries the phone's
selected scheme or mode. Matching the app therefore needs three things: a theme table on
the ESP, a protocol message carrying the active scheme + mode, and Pi passthrough of
whatever the phone has selected (the Pi already caches settings, so it is the natural
place to hold the value when the phone is absent).

**Proposed approach:**
1. Extract every colour currently in `ui_core.h` / `ui_config.h` into a single
   `Theme` struct (background, card, elevated, text, text-dim, accent, and the five
   semantic status colours).
2. Port the 12 `Palette.SCHEMES` seeds to the ESP as sRGB pairs and derive the same
   way Android does (two seed hues, lifted for dark / sunk for light).
3. Add a serial command, e.g. `THEME:<scheme>,<dark|light>`, with the Pi echoing the
   phone's current selection. Persist it in NVS so it survives a power cycle, and
   **default to `dark` + the app's default scheme when no theme has ever been
   received** (i.e. phone not connected).
4. `ui_config.h` should include the shared header instead of redefining the colours.

**Done when:** Changing the scheme or toggling dark/light in the Android app is reflected
on the ESP32 within a second; with the phone disconnected the ESP boots in dark mode and
looks like the app's dark theme.

---

## ISSUE-03 — Intake air temperature always zero on Android

**Status:** ❌ **Root cause confirmed (2026-10-30), not yet fixed.** The decode path is
fine; the request is never sent. `pi/mx5-can-setup.sh` line 13 brings the **HS-CAN
interface up with `listen-only on`**, so the OBD-II Mode 01 request on `0x7DF` is dropped
by the kernel before it reaches the bus and no reply can ever arrive. Every PID-based
field is affected — this one and
[ISSUE-10](#issue-10--instantaneous-mpg-always-shows-the-empty-placeholder).

- `can_handler.py` polls OBD-II PID `0x0F` on the existing request slot, alternating
  with MAF so bus load is unchanged, and decodes the reply into
  `telemetry.intake_temp_f`.
- The demo generator is no longer the only thing that sets it.

**Remaining:** enable TX on the HS-CAN interface (see ISSUE-10, *Proposed approach*),
then confirm the NC's ECU answers PID `0x0F`. If it still does not, the fallback is an
MS-CAN body-bus frame (needs a log).

**Reported:** The Engine page always shows an intake temperature of 0 (and the intake bar
pinned empty).

**Where it lives:**
- [telemetry_data.py](../pi/ui/src/telemetry_data.py#L43) — `intake_temp_f: int = 0`
- [main.py](../pi/ui/src/main.py#L184) — same default
- [can_handler.py](../pi/ui/src/can_handler.py) — **no assignment to `intake_temp_f`
  anywhere in the CAN path**
- [link_service.py](../pi/ui/src/link_service.py#L103) — sends `intake_temp_f` as-is
- [EngineScreen.java](../android/mx5-remote/src/main/java/com/mx5/remote/EngineScreen.java#L67)

**Working theory:**
This one is not a display bug — the field is never populated. Nothing in `can_handler.py`
writes `telemetry.intake_temp_f`, so it stays at its `0` default and the app faithfully
renders zero. The only code that sets it is the **demo mode** generator in
`main.py`, which is why the value may have looked plausible during simulator runs.

There is no known dedicated intake-air CAN ID in the current decoder set (`ENGINE_TEMP`
gives coolant + ambient). Intake air on this platform is normally available two ways:
- **OBD-II Mode 01 PID 0x0F** (intake air temperature, 1 byte, °C + 40) — the Pi already
  owns an OBD-II request/response path for MAF, so this is the smallest change.
- **A CAN frame on the MS-CAN body bus**, if the NC broadcasts one — needs a log to prove.

**Proposed approach:** Add PID `0x0F` to the existing OBD-II polling loop, decode it, and
store °C → °F in `telemetry.intake_temp_f`. If a broadcast frame already carries IAT,
prefer that and drop the poll. Whatever the source, remove the demo-only path as the
sole writer so the two can't be confused again.

**Needs hardware:** Yes — confirm which PID/frame the car actually answers, and whether
the ECU answers at all while the engine is cold.

**Done when:** The Engine page shows a plausible ambient-ish value at key-on that rises
with engine bay heat, and the intake bar moves with it.

---

## ISSUE-04 — Throttle and brake wrong on the RPM page

**Status:** ✅ **Fixed** for everything that was provably wrong in code.

- **Throttle** now comes from the engine frame (`0x201` byte 6, `0-200` → `0-100%`),
  which is what `docs/ARCHITECTURE.md` documents for this car. The old `0x200` byte 4
  decode is kept only as a fallback for short frames.
- **Brake** is rendered as an ON/OFF indicator on both the ESP32 and the Android RPM
  page, because the car only exposes a pedal switch. A proportional bar that can only be
  empty or full was what made it look broken.
- **The ESP now receives brake at all** — it was not in the `TEL:` payload, so its RPM
  page brake meter was permanently zero.
- **Staleness:** a pedal value that stops arriving is zeroed instead of freezing on
  the dash. Throttle uses 750 ms (`PEDAL_STALE_SEC`); brake uses 2.5 s
  (`BRAKE_STALE_SEC`) because `0x212` is a body-status frame that may not be broadcast
  as often, and a brake light that flickers off mid-stop is worse than one that clears late.
- The Android RPM page gained the missing brake row.
- A `THR: engine(0x201)=…% legacy(0x200)=…%` line is printed every 5 s so the two decodes
  can be compared on the first drive without any extra tooling.

**Remaining:** a stationary pedal log to confirm the `0x201` byte-6 assumption and to
check whether a real brake travel/pressure value exists. If it does, the ON/OFF
indicator should become a bar.

**Reported:** On the Android RPM page, throttle and brake are always wrong.

**Where it lives:**
- [can_handler.py](../pi/ui/src/can_handler.py#L159) — `parse_throttle()` uses `data[4]` of
  `0x200` scaled `0-255 → 0-100`
- [can_handler.py](../pi/ui/src/can_handler.py#L261) — `parse_brake_status()` returns a
  **boolean**, stored as `brake_percent = 100` or `0`
- [can_handler.py](../pi/ui/src/can_handler.py#L747) — the `0x212` brake branch
- [link_service.py](../pi/ui/src/link_service.py#L100) — `throttle_percent` / `brake_percent`
- [RpmScreen.java](../android/mx5-remote/src/main/java/com/mx5/remote/RpmScreen.java#L61) —
  Android renders a throttle bar only; **there is no brake bar on this screen**
- [ui_core.cpp](../display/src/ui_core/ui_core.cpp#L1093) and
  [ui_core.cpp](../display/src/ui_core/ui_core.cpp#L1102) — the ESP RPM screen draws both

**Working theory:**
Several independent problems could produce "always wrong", so they should be separated:

1. **The byte offset is unverified.** `parse_throttle` reads `data[4]` of `0x200`. If the
   NC actually carries throttle in a different byte (or on a different ID), the value will
   look like noise or sit pinned. This needs a CAN log with a known pedal position.
2. **Brake is binary, not a percentage.** `brake_percent` is 0 or 100 — the UI renders it
   as a proportional bar, so it will snap rather than sweep, which reads as "wrong".
3. **The Android RPM page has no brake readout at all.** If brake was expected there, the
   bar is simply missing rather than incorrect.
4. **The ESP never receives brake.** The `TEL:` payload has no brake field at all (see
   [esp32_serial_handler.py](../pi/ui/src/esp32_serial_handler.py#L634)), so
   `telemetry.brake` on the ESP stays `0` forever, while
   [ui_core.cpp](../display/src/ui_core/ui_core.cpp#L1102) still draws it.
5. **Staleness.** Throttle is only updated when `0x200` arrives; if that ID is intermittent
   the last value sticks.

**Proposed approach:**
1. Log `0x200` and `0x212` with the car stationary and press the pedals deliberately;
   confirm offsets before changing any decode.
2. Decide the semantic for brake: keep binary and render it as an on/off indicator, or
   find a real pressure/position value. Don't render binary data as a proportional bar.
3. Add a brake field to the `TEL:` protocol so the ESP RPM page is not permanently zero.
4. Add a staleness guard (like `maf_timestamp`) so a stale pedal value decays to 0 rather
   than freezing on the dash.
5. Add the brake bar to the Android RPM page if it is wanted there for parity.

**Needs hardware:** Yes — pedal-position CAN log.

**Done when:** With the car stationary and the ignition on, pressing each pedal moves the
matching indicator on both the Android and ESP RPM pages, proportionally and promptly,
and releasing it returns to zero.

---

## ISSUE-05 — ESP32 gyro screen still uses the old visualization

**Status:** ✅ **Fixed.** `drawGForceScreen()` was rewritten to match the Android
`GForceView`.

- Rings at 0.4 g / 0.8 g and a 1.2 g outer limit, crosshair and `ACCEL`/`BRAKE`/`L`/`R`
  labels.
- A 24-point trail sampled at 20 Hz, older points fading and shrinking, so a corner has
  a readable shape instead of a single dot.
- Colour (green → yellow → orange → red) and dot size follow the magnitude; the current
  position is clamped to the outer ring.
- Readouts changed from pitch/roll to `MAG` / `LAT` / `LONG`.

**Remaining:** check axis signs on the car (or a board held at known angles).

**Reported:** The gyroscope/G-force visualization was updated in the Android app, but the
ESP32 is still drawing the old version.

**Where it lives:**
- [ui_core.cpp](../display/src/ui_core/ui_core.cpp#L1313) — `drawGForceScreen()`
- [main.cpp](../display/src/main.cpp#L491) — IMU orientation/calibration pipeline that feeds
  it (`linearAccelX/Y`, pitch, roll)
- [GForceView.java](../android/mx5-remote/src/main/java/com/mx5/remote/GForceView.java) and
  [GForceScreen.java](../android/mx5-remote/src/main/java/com/mx5/remote/GForceScreen.java) —
  the newer Android implementation to port from

**Working theory:**
This is expected rather than surprising: the ESP renders the G-force screen entirely from
its own `ui_core.cpp`, and the Android work never had a corresponding firmware change.
The two only share the *idea*, not the drawing code.

The ESP already receives what it needs — the IMU is local to the ESP (`imu.ax/ay/az`), and
the screen renders a single dot plus pitch/roll/accel text. What is missing is whatever
the Android view added visually (layout, trail, scale rings, colouring, smoothing).

**Proposed approach:** Diff
[GForceView.java](../android/mx5-remote/src/main/java/com/mx5/remote/GForceView.java)
against `drawGForceScreen()` and port the visual treatment into the same LVGL-style
drawing primitives the rest of `ui_core.cpp` uses. Keep the existing IMU complementary
filter in `main.cpp` as the data source unless the Android math differs meaningfully.

**Needs hardware:** Partial — the drawing can be developed in the
[UI simulator](../tools/simulators/ui_simulator/README.md); confirming the axes and sign
conventions needs the car (or a board held at known angles).

**Done when:** The ESP G-force screen is visually consistent with the Android version and
shows correct lateral/longitudinal sign for a left turn, a right turn, acceleration and
braking.

---

## ISSUE-06 — Android speed reads about two-thirds of actual

**Status:** 🔴→✅ **Fixed.** Root cause confirmed as the unit double-conversion described
below.

- `CANParser.parse_speed()` now returns **km/h** (still flooring negatives so reverse
  stays detectable).
- The gear estimator converts to mph itself (`speed_kmh * 0.621371`); the ratio table is
  the only thing that is in mph.
- `main.py`'s MPG calculator also converts explicitly.
- The ESP32 converts km/h → mph for display when `useMPH` is set.
- Android needed no change: `Telemetry.speedKmh` is now genuinely km/h, so
  `speedMph()` is correct.

**Remaining:** compare against the car's speedometer at a steady 40 mph.

**Reported:** The speed shown in the Android app is roughly ⅔ of the real speed. The ESP32
shows the correct speed, which points at the phone app.

**Where it lives:**
- [can_handler.py](../pi/ui/src/can_handler.py#L111) — `parse_speed()` converts km/h → **mph**
- [can_handler.py](../pi/ui/src/can_handler.py#L713) — the result is stored in
  `telemetry.speed_kmh`
- [link_service.py](../pi/ui/src/link_service.py#L92) — sends it as `speed_kmh`
- [Telemetry.java](../android/mx5-remote/src/main/java/com/mx5/remote/Telemetry.java#L154) —
  `speedMph()` = `speedKmh * 0.621371`
- [esp32_serial_handler.py](../pi/ui/src/esp32_serial_handler.py#L634) — the same number is
  sent to the ESP in the `speed` field

**Working theory:**
This looks like a straightforward unit double-conversion, and it matches the observed
ratio almost exactly:

1. `parse_speed()` already converts the raw CAN value to **mph**.
2. The result is nevertheless stored in a field named `speed_kmh`.
3. The Android app assumes that field is km/h and multiplies by `0.621371` to get mph.
4. Result: `actual_mph × 0.621371` ≈ **62% of actual** — the reported "about ⅔".

The ESP shows the same number but labels it MPH (it renders the raw field), which is why
the round display looks correct while the phone does not.

There is even a comment in `_update_gear_estimation()` acknowledging the misnaming
("`speed_kmh` is actually in MPH"), so the field name has been lying for a while.

**Proposed approach:** Fix the unit at the source and make the name honest:
- Either have `parse_speed()` return **km/h** and rename nothing, or rename the field to
  `speed_mph` throughout and delete the conversion in `Telemetry.speedMph()`.
- Whichever is chosen, the reverse-detection `floor()` behaviour must be preserved
  (negative values must stay negative by at least 1 unit).
- The `TEL:` payload field meaning and the ESP's "MPH" label must stay aligned — update
  the ESP label if the unit changes.
- The gear estimator consumes this same value and its ratio table is in mph; keep it
  consistent.

**Needs hardware:** No — the unit mismatch is visible in code. A quick sanity check against
the car's own speedometer after the fix is still worthwhile.

**Done when:** At a steady 40 mph the phone shows 40 (±1) in mph mode and 64 (±2) in km/h
mode, and the ESP and phone agree.

---

## ISSUE-07 — Startup animation is plain

**Status:** 🟡 **Improved, not done (2026-10-30).** `playStartupAnimation()` in `main.cpp`
replaced the single blit and 1.5 s `delay()`, and the car no longer shows a static logo —
but it is not the "wow" the owner wants. Treat the three beats below as the *baseline* to
build on, not the answer.

Baseline (fixed total length ~1.45 s):
1. the logo zooms in from 40% to 100%;
2. a tach-style arc sweeps 135°→405° and settles back to empty, matching the RPM
   screen's geometry;
3. the title `MX5 TELEMETRY` fades in over a growing accent rule.

The theme is loaded from NVS *before* the animation, so the boot sequence is already in
the phone's colours.

**Remaining (this is a design task, not a bug fix):** make it genuinely impressive.
Constraints that must survive: it runs before the Pi link is up, it must not add more than
~2 s to boot, it must run on the ESP32-S3's existing draw primitives, and it must look
right in both the dark and light themes. Ideas worth prototyping on the round panel:
a rotating "startup sweep" that lights each screen's accent in turn, a needle sweep with
overshoot and settle, a particle/afterglow trail on the arc, and a hard cut to the first
frame rather than a fade to black.

**Reported:** The device boot experience should be more polished and impressive — a cool
animation.

**Where it lives:**
- [main.cpp](../display/src/main.cpp#L259) — currently `LCD_DrawImageScaled(boot_logo_data,
  …)` followed by `delay(1500)`
- [main.cpp](../display/src/main.cpp#L296) — the boot countdown / loading-message state that
  follows the logo
- [ui_core.cpp](../display/src/ui_core/ui_core.cpp) — drawing primitives available for an
  animation

**Working theory:**
There is no animation today: the boot logo is blitted once, the firmware blocks for
1.5 seconds, and then the loading state begins. The 240×240 round display and the
`LCD_*` primitives can already do fades, arcs and text, so this is a design/effort problem
rather than a capability one.

Note that the current `delay(1500)` also blocks anything else that could be initialised in
parallel; an animation loop is a good excuse to make startup non-blocking.

**Proposed approach:** Ideas, in rough order of payoff per line of code:
1. Logo fade-in with a slight scale-up, then a sweep.
2. A needle/sweep gauge self-test that mirrors the real cluster's power-on sweep.
3. A segmented arc that fills to 100% and settles at zero — ties into the
   [LED system](LED_SYSTEM.md) language.
4. Show real boot progress instead of a fixed delay (display init, IMU, BLE, first `TEL:`).

Keep total startup time under ~2 s and make the animation interruptible once real telemetry
arrives, so it can never mask a working connection.

**Done when:** Power-on shows a smooth, intentional animation that ends in the normal
screen, and the device reaches live telemetry no later than it does today.

---

## ISSUE-08 — Fuel percentage is not stable

**Status:** ✅ **Fixed.** The EMA was replaced with a wall-clock rolling average.

- `_smooth_fuel_level()` now keeps timestamped raw samples and averages the last
  **60 s** (`FUEL_AVERAGE_WINDOW_SEC`). Because the window is time-based, the smoothing
  no longer changes when the fuel frame rate changes or stalls.
- Integer hysteresis stays, so the display still doesn't twitch between adjacent values.
- Verified on a simulated clock: raw ±4% at 1 Hz produced a display that never moved
  off 50%.

**Remaining:** tune the window length on a real drive (cornering slosh).

**Reported:** Fuel %, and therefore the gas-mile-range estimate, jumps around. It should
be averaged over roughly the last minute so it reads steadily.

**Where it lives:**
- [can_handler.py](../pi/ui/src/can_handler.py#L618) — `_smooth_fuel_level()`, an EMA
  (`FUEL_EMA_ALPHA`) plus hysteresis
- [can_handler.py](../pi/ui/src/can_handler.py#L756) — where it is applied to the raw value
- [ui_core.cpp](../display/src/ui_core/ui_core.cpp#L881) — ESP range estimate
  (`12.7 gal × fuel% × mpg`)
- [mpg_calculator.py](../pi/ui/src/mpg_calculator.py) — its own `_current_fuel_pct`
- [OverviewScreen.java](../android/mx5-remote/src/main/java/com/mx5/remote/OverviewScreen.java#L119)
  and [EngineScreen.java](../android/mx5-remote/src/main/java/com/mx5/remote/EngineScreen.java#L47)

**Working theory:**
There *is* already smoothing, but it is an EMA whose time constant depends on the sample
rate rather than on wall-clock time, plus integer hysteresis. That means:
- The effective averaging window changes if the fuel frame rate changes (or stalls).
- Under braking/acceleration the float in the tank sloshes, and the filter is too far
  behind to hide it but not stable enough to ignore it.
- The range estimate multiplies the smoothed percentage by a *different* MPG source, so
  the two can disagree and make the range swing more than the percentage.

**Proposed approach:** Replace the EMA with a genuine time-based **rolling average over a
~60 s window** of raw fuel samples (timestamped; drop samples older than 60 s). Keep a
small hysteresis on the displayed integer so it still doesn't twitch between adjacent
values, but derive it from the window rather than from a fixed alpha. Then feed the same
averaged value to the range calculation on all three UIs so they can't disagree.

Consider a fuller-tank correction: average over a longer window (or only during steady
speed) so cornering slosh doesn't drag the value down for a full minute after the fact.

**Needs hardware:** Ideally yes — a drive with sloshing, to tune the window length.

**Done when:** Fuel % and range hold steady (±1%) during normal driving and only move
when the tank actually changes, with no jump larger than a percent or two after a corner.

---

## ISSUE-09 — App is not available while driving

**Status:** ❌ **Still unreachable in the car (2026-10-30).** The two-app split is correct
and builds, but the head unit never offers "MX5 Drive". Two independent causes, both
confirmed in this repo / in the field:

1. **The drive flavor never declares the Android Auto template hookup.** Every templated
   AA app must declare
   `<meta-data android:name="com.google.android.gms.car.application"
   android:resource="@xml/automotive_app_desc"/>` with an `automotive_app_desc.xml`
   containing `<uses name="template"/>`. The drive manifest has the `CarAppService` and the
   `category.IOT` filter but **not** this meta-data, so the host has nothing to enumerate.
   The AOSP `car-samples` `mobile` manifest shows the exact shape.
2. **Android Auto stopped listing sideloaded Car App Library apps** (field reports from
   June 2026): logcat shows `CAR.AUTH: … isPackageAllowed = false` and
   `Finsky: PlayGearheadService <package>, app owners empty` even with developer mode and
   *Unknown sources* on. Sideload is no longer a route for the templated app; it has to
   come from a Play channel (internal app sharing / internal test track — $25 one-time,
   no review).

The first attempt was wrong in a way worth recording: it declared
`androidx.car.app.category.DRIVING` on a `CarAppService` inside the same APK as the
parked game. **That category does not exist.** The documented set is `NAVIGATION`,
`POI`, `IOT`, `WEATHER` plus the messaging/media categories, and the AOSP
`androidx.car.app` artifact has no `category` package at all — so the host had no
reason to list the service, and a package classified `appCategory="game"` stays
game-classified no matter which component is opened.

What ships now:

| Flavor | applicationId | Launcher name | Car entry point |
| --- | --- | --- | --- |
| `parked` | `com.mx5.remote` | MX5 Remote | `CAR_LAUNCHER` activity, `appCategory=game`, full dashboard |
| `drive` | `com.mx5.remote.drive` | MX5 Drive | `CarAppService` with `category.IOT`, templates, no `appCategory` |

- `Mx5CarService` → `Mx5CarSession` → `Mx5CarScreen`: one `PaneTemplate` carrying the
  Overview page's readings — speed, RPM, gear, coolant, fuel, range, battery, average
  MPG — polled once a second from the shared `PiLink` client. Value first, label
  second, because the host draws the row title large.
- `IOT` is the only documented category that fits: the app reports the state of a
  connected device. The probe notes in [android/README.md](../android/README.md)
  record a real AA app (Tuya) being enumerated with exactly that category.
- The parked dashboard is untouched and remains the in-depth surface.

**Remaining / next steps,** in order:
1. Add `res/xml/automotive_app_desc.xml` (`<uses name="template"/>`) and the
   `com.google.android.gms.car.application` meta-data to the drive manifest, then rebuild
   and re-check the launcher list. This is a prerequisite for every other option.
2. Confirm what the head unit actually shows today (missing tile / greyed tile / tile that
   opens then closes) — the three look identical from the driver's seat but point at
   different causes.
3. If it still does not appear: publish the drive flavor to a Play **internal test track**
   (the only supported route for templated apps). Budget the $25 one-time developer fee.
4. Decide the fallback if (3) is refused: run the phone dashboard on a mount/tablet, or
   move to an Android Automotive head unit.

**Reported:** The app cannot be opened in Android Auto while the car is moving. That was
expected, but the app should be viewable during driving.

**Where it lives:**
- [android/mx5-remote/build.gradle](../android/mx5-remote/build.gradle) — the flavor split
- [android/mx5-remote/src/parked/AndroidManifest.xml](../android/mx5-remote/src/parked/AndroidManifest.xml)
  — `android:appCategory="game"` + `category.CAR_LAUNCHER`
- [android/mx5-remote/src/drive/AndroidManifest.xml](../android/mx5-remote/src/drive/AndroidManifest.xml)
  — `CarAppService` + `category.IOT`
- [android/README.md](../android/README.md#L31) — the "parked-app gate" findings
- [docs/ANDROID_AUTO_PLAN.md](ANDROID_AUTO_PLAN.md) — the original phasing

**Working theory:**
This is a platform rule, not a bug. `appCategory="game"` is a **parked** category: Android
Auto deliberately greys it out while the vehicle is in motion, and games are the only
AA-supported *parked* category. No manifest flag lifts that restriction.

There are only two honest paths:
1. **Car App Library with a driving-capable category.** A `CarAppService` in one of the
   documented categories gets template-rendered UI that *is* allowed while moving. The
   catch is that the UI must be built from AA templates (`NavigationTemplate`,
   `PaneTemplate`, `MessageTemplate`, …) — the current custom dashboard views cannot be
   reused directly, and everything shown while driving must be distraction-optimised.
2. **Keep the parked app** and accept that it is only usable stationary.

The research in [android/README.md](../android/README.md) already established that
**both** mechanisms were accepted by the test head unit, so the templated path is not a
blind alley — but its UI model is different enough that this is a significant piece of
work, not a manifest tweak.

⚠️ **Safety note.** Driver-distraction rules exist for a reason. Whatever is added under
a driving-capable category must be glanceable, must not require scrolling to find critical
data, and must not add interaction-heavy surfaces. Prefer read-only templates.

**Proposed approach (as shipped):** Both, as two apps. The parked dashboard keeps its
`game` classification, and a second package carries the templated overview in a
documented category. They cannot share an APK — `android:appCategory` is application-wide
— so the module builds two flavors from one source set. Do not attempt to defeat the
parked gate.

**Needs hardware:** Yes — the head unit is the only real test for driving-category
rendering.

**Done when:** The app is openable with the vehicle in motion *through a supported
mechanism*, or the limitation is documented and accepted.

---

## ISSUE-10 — Instantaneous MPG always shows the empty placeholder

**Status:** ✅ **Fixed, verified live (2026-10-30) — plus one Android bug found afterwards.**

Root cause, confirmed on the car: `pi/mx5-can-setup.sh` brought the HS-CAN interface up
with `listen-only on`, so the kernel dropped every `0x7DF` request and no ECU reply could
ever arrive. `ip -details link show can1` reported `LISTEN-ONLY` with `TX packets 0`.

- The bring-up script now transmits on **can1 only** and keeps **can0 (MS-CAN)
  listen-only** — that bus is body-bus and read-only by design:
  `ip link set can1 up type can bitrate 500000 restart-ms 100 listen-only off`.
- With TX enabled the ECU answers: `04 41 10 00 …` to `7DF#020110…`, and `IAT: 87F` in
  the journal. MAF (`0x10`) and intake air (`0x0F`) share one rotating poll slot.
- "Unknown" is distinct from "0 mpg": `instant_mpg_valid` travels in `TEL:` and in the
  HTTP snapshot, and both the ESP and the Android Engine page show `--` only when it is
  false.

**Found afterwards, in code (2026-10-30, no car needed):** the Android page would still
have shown `--` even with a working MAF. The shell keeps one long-lived `Telemetry` and
copied every field by hand on each poll — and `instantMpgValid` was not in that list. The
Engine page therefore read the default `false` forever. The copy now lives in
`Telemetry.copyFrom()` next to the fields, so a new field cannot be forgotten again. This
is the second time a hand-maintained copy list caused a "no data" symptom, and it is the
reason the symptom survived the Pi-side fix.

**Reported:** Instantaneous fuel economy is always `---` (the ESP draws `--`).

**Where it lives:**
- [main.py](../pi/ui/src/main.py#L1043) — instant MPG from MAF, with guards
  `speed_mph > 1.0 && maf > 0.5 && maf_age < 2.0`
- [can_handler.py](../pi/ui/src/can_handler.py#L650) — `_maybe_request_maf()`, OBD-II
  request `0x7DF`, PID `0x10`
- [can_handler.py](../pi/ui/src/can_handler.py#L698) — response parse on `0x7E8`
- [ui_core.cpp](../display/src/ui_core/ui_core.cpp#L915) — renders `--` when the value is
  `<= 0.1`

**Working theory:**
The `--` placeholder means `telemetry.instant_mpg` is effectively zero, which happens
whenever **any** of the three guards fails. The most likely failure is the MAF term
itself, since nothing else in the chain looks broken:

1. **No MAF response.** The request uses the functional broadcast ID `0x7DF` and expects
   the reply on `0x7E8`. If the Pi's CAN interface is configured or operated listen-only —
   the header comment in `can_handler.py` even documents bring-up with `listen-only on` —
   the request is never transmitted and no response can ever arrive.
2. **PID not answered.** If the NC's ECU does not answer PID `0x10` on that address, the
   same thing happens.
3. **Response layout mismatch.** `parse_maf()` expects `[len, 0x41, 0x10, A, B]`. A
   different PCI/ISO-TP framing would parse to 0 (and is rejected by `maf > 0`).
4. **Speed guard.** `speed_mph > 1.0` is evaluated against the mis-unit-ed speed field
   (see [ISSUE-06](#issue-06--android-speed-reads-about-two-thirds-of-actual)) — the
   threshold itself is fine, but it is worth confirming the sign/magnitude once units are
   fixed.

**Proposed approach:**
1. Confirm on the car that a MAF response is arriving at all — the code already logs
   `MAF: x g/s` every 5 s, so a silent log is the tell.
2. If the bus is listen-only, the request path cannot work; either enable transmission on
   the HS-CAN interface or compute instantaneous MPG from something the car *does*
   broadcast (e.g. injector pulse width / fuel-flow frame), falling back to a
   load-and-RPM model.
3. Make "no data" explicit rather than `0.0`: distinguish *unknown* from *zero* so the UI
   can show `--` for genuinely unavailable data and a real number otherwise.
4. Consider a smoothed instantaneous value (e.g. 1–2 s) so it is readable rather than
   flickering.

**Needs hardware:** Yes — needs a MAF log from the running engine.

**Done when:** Cruising at a steady speed shows a plausible instant MPG that rises on
lift-off and drops under load, instead of `--`.

---

## ISSUE-11 — TPMS card should become a gear / RPM card

**Status:** 🟡 **Works, but the order is wrong (2026-10-30).** The ladder renders; the
problem is *which* gears it shows and in what order. It ranks all six gears by distance
from the 2400–4500 sweet spot and prints the best three, so at any given speed the three
numbers appear in an order that has nothing to do with 1→6 — e.g. `4, 3, 5` or `2, 1, 3`.
A driver glancing at it sees a scrambled list, not a gear ladder. See
[ISSUE-13](#issue-13--overview-gear-ladder-is-not-in-numeric-order) — that is the change
to make; the rest of this issue's work stands.

- Three rows: gear number, predicted RPM at the current road speed.
- Ranking is **sweet-spot** based, as chosen: all six gears are scored by how far their
  predicted RPM is from the 2400–4500 band, and the three closest are shown.
- The current gear's row is elevated; RPM colour is green inside the band, blue below,
  red above.
- `R` shows `REVERSE` and a stopped car shows `STOPPED` rather than a meaningless ladder.
- **Layout:** the block starts at y=250, below the COOL/OIL/VOLT and MPG/FUEL/RANGE
  cards (which end at y=244). It previously started at 242, so its first row sat under
  "RANGE" and its background clear-rect erased the right card's bottom corner.
- The full TPMS page and the BLE scanning code are untouched, ready for the 315 MHz
  sensors.

**Remaining:** confirm the three-gear choice reads well at a glance while driving.

**Reported:** The Bluetooth TPMS is broken until it is replaced with 315 MHz sensors. The
tire card on the ESP32-S3 Overview screen should be replaced with a gear/RPM view — similar
to the Android Overview screen, but simplified: show roughly the three most likely gears
with the RPM they would be at the current speed.

**Where it lives:**
- [ui_core.cpp](../display/src/ui_core/ui_core.cpp#L940) — the 2×2 tire grid
  (`FL/FR/RL/RR`, `tireW 56`, `tireH 32`, `tpmsStartY 256`)
- [ui_core.cpp](../display/src/ui_core/ui_core.cpp#L1124) — the full-page TPMS screen
  (should stay, or be handled separately)
- [GearRpmView.java](../android/mx5-remote/src/main/java/com/mx5/remote/GearRpmView.java#L37) —
  the Android ladder to model this on
- [main.cpp](../display/src/main.cpp#L70) — BLE TPMS scanning, MAC mapping, NVS cache
- [archive/TPMS_BLUETOOTH.md](archive/TPMS_BLUETOOTH.md) — background on the current TPMS

**Working theory:**
The Overview tire card is a fixed 2×2 grid sized for four tire tiles. Replacing it with a
three-row gear ladder fits the same footprint and requires no protocol change: the ESP
already receives `rpm`, `speed` and `gear` in `TEL:`.

The Android `GearRpmView` already has the maths worth reusing:
`RATIO[6]`, `FINAL_DRIVE 4.10`, `TYRE_DIAMETER_IN 24.3`, and
`rpm = ratio × speed × slope`. It then colour-codes each gear against
`OVER_REV 7000`, `SWEET_LOW/HIGH 2400/4500` and `LUG_BELOW 1200`.

**Proposed approach:**
1. Lift the gear ratio / final drive / tire constants into a shared header so the Pi, the
   ESP and the Android app cannot disagree about gearing.
2. Replace the tire grid with three rows: gear number, predicted RPM at current speed, and
   the same sweet-spot colour code the Android view uses. Highlight the current gear if it
   is known.
3. Decide whether "three most likely" means *the current gear ± 1* or *the three gears
   whose RPM falls in the sweet spot at this speed*. The latter is closer to the Android
   ladder; the former is closer to "what should I do now". Pick one and document it.
4. Keep the TPMS full-page screen and the BLE scanning code intact so the 315 MHz work can
   land later; only the Overview card changes.
5. Handle `speed == 0` and `R`/`N` explicitly (show the ladder dimmed or hidden).

**Done when:** The Overview screen shows three gear/RPM rows that update with speed, the
current gear is visually obvious, and nothing regresses on the dedicated TPMS page.

---

## ISSUE-12 — LED strip is laggy and lacks a gradient

**Status:** ✅ **Verified working on the car (2026-10-30).** The strip is fine; the reported
"permanently blue" was not reproducible once the board could be interrogated.

What the hardware said, in order:

- The Nano answers `PING`→`PONG` and `SEQ?`→`SEQ:1` on `/dev/ttyUSB0`, so the firmware and
  the Pi's link were never dead.
- With a `STATUS` line added, it reported `CAN=1, ERR=0, FPS≈320, LAST=0x201` — the MCP2515
  is up, ~320 frames/s arrive, and the engine frame is being decoded.
- Driving the strip from the firmware's new `DEMO:<rpm>` override lit **all 20 LEDs in a
  full blue→red gradient at 6500 rpm**.

So the old failure was a *silent* one: a strip at genuine 0 rpm (engine off) and a strip
whose CAN link is dead looked identical, and nothing reported either. That is now fixed,
along with the revamp the owner asked for — runtime colour ramp, theme-linked colours,
configurable full-illumination rpm, flowing colour mapping and a faster update path. The
full list is in [LED_REVAMP_PLAN.md §4.1](LED_REVAMP_PLAN.md#41-what-is-already-implemented).

**Remaining:** one drive to confirm it tracks the tach, plus the `LED STRIP` settings
screen and EEPROM persistence of the ramp (Phases 2–3).


- **Gradient:** `scaleColorAt()` is now the single colour ramp, and each LED is painted
  at *its own* position on that ramp (`setLedAtPos()`). The bar therefore runs blue at
  the bottom to red at the top, and the leading edge always shows the RPM it represents.
  Previously one colour was computed from the current RPM and copied to every lit LED.
- **Lag:** LEDs are painted immediately after a CAN frame is decoded (the separate 10 ms
  timer no longer gates it); rising RPM is unfiltered (`RPM_ALPHA_RISING = 1.0`) and the
  snap threshold halved to 400; `strip.show()` is skipped when no pixel changed
  (`showIfChanged()`); and the per-LED maths is skipped entirely when the RPM has not
  changed, because this runs at CAN frame rate rather than at the LED rate.
- **Zones:** rebalanced to the engine — blue/cyan at idle, green through the economical
  band, yellow/orange building, and full red at the real 6800 redline. `RPM_MAX` was
  6200, which saturated the strip ~600 RPM early.
- `docs/LED_SYSTEM.md` updated to match.

**Remaining:** judge the feel on the car; the simulator cannot model `strip.show()`
timing on the Nano.

**Reported:**
1. The Arduino-driven LEDs are far too laggy.
2. Colours should transition smoothly, giving a smooth colour gradient from the bottom to
   the top of the RPM range.
3. The colour zones should be reviewed so they actually make sense for their RPMs.

**Where it lives:**
- [main.cpp](../arduino/src/main.cpp#L96) — `RPM_ZONE_BLUE/GREEN/YELLOW/ORANGE`,
  `RPM_MAX 6200`, `RPM_REDLINE 6800`
- [main.cpp](../arduino/src/main.cpp#L106) — timing constants
  (`CAN_POLL_INTERVAL 10000`, `LED_UPDATE_INTERVAL 10000`)
- [main.cpp](../arduino/src/main.cpp#L147) — `RPM_SNAP_DELTA 800`,
  `RPM_ALPHA_RISING 0.70`, `RPM_ALPHA_FALLING 0.40`
- [main.cpp](../arduino/src/main.cpp#L423) — `getRPMColor()`, the zone interpolation
- [main.cpp](../arduino/src/main.cpp#L527) — `updateLEDsCenterOut()` and the sibling
  sequence handlers
- [LED_SYSTEM.md](LED_SYSTEM.md) — the documented behaviour to keep in sync

**Working theory:**

*Lag* has several stacked contributors:
1. **Two independent 10 ms timers.** CAN is polled every 10 ms and LEDs are only updated
   every 10 ms, so worst-case latency before a new RPM reaches the strip is ~20 ms.
2. **The EMA filter dominates.** With `alpha 0.70` rising and `0.40` falling at a ~100 Hz
   update rate, the falling edge alone has a time constant on the order of 50 ms. A
   `RPM_SNAP_DELTA` of 800 only bypasses this for large jumps, so normal revving is
   visibly filtered.
3. **`strip.show()` blocks with interrupts disabled.** On a 16 MHz ATmega328P this is
   ~30 µs per LED, so a long strip spends a meaningful fraction of every frame pushing
   bits out, and the CAN interrupt is masked while it happens.
4. **`getRPMColor()` runs per update, and the sequence handlers write every LED every
   frame** — including clearing the whole strip on each pass, rather than only the pixels
   that changed.

*The gradient* is a separate design issue: `updateLEDs*` calls `getRPMColor(currentRPM)`
**once** and paints every lit LED with that single colour
([main.cpp](../arduino/src/main.cpp#L586)). So the strip is one flat hue that changes as a
whole, not a gradient across the strip. That is exactly why it does not read as a
progression from "low" at the bottom to "high" at the top.

*The colour zones* deserve another look:
- `RPM_MAX` is **6200**, but the engine and every other UI treat the redline as ~7200
  (the ESP RPM arc spans 8000, the Android gauge uses shift 6500 / redline 7200). The
  strip therefore saturates ~1000 RPM early and shows nothing for the last part of the
  range.
- Everything below 2000 RPM is pure blue, including idle — that is a large fraction of
  normal driving shown as one colour.
- The blue→green→yellow→orange→red ramp is a fairly standard "eco to danger" ramp, but
  the *boundaries* are arbitrary relative to the shift point. They should be anchored to
  the real shift/redline points, not to round numbers.

**Proposed approach:**
1. **Colour by LED position, not by current RPM.** Give each LED a fixed colour derived
   from its own position along the RPM scale (green at the bottom → amber → red at the
   top), then light or dim it according to the current RPM. The lit bar then always shows
   the same colour ramp, and the top LED is always red — which is what makes a shift
   light readable at a glance. Use `LEDLinear`/gamma-corrected interpolation so the
   gradient is smooth in perceived brightness, not just in sRGB.
2. **Cut the lag.** Update the strip at the same 100 Hz CAN rate rather than on a separate
   timer; raise the rising alpha toward 1.0 (or bypass the filter entirely and rely on
   `strip.show()` cadence for smoothing); keep a modest falling filter only to stop
   trailing pixels flickering.
3. **Dirty-region updates.** Only rewrite pixels whose colour changed since the last
   frame, and compare against the previous frame buffer rather than clearing the strip.
4. **Revisit the zones.** Anchor the red zone to the real redline (~7000–7200), rebalance
   the low end so idle is distinguishable from cruise, and confirm the scheme against the
   rest of the system (ESP arc, Android gauge) so all three tell the same story.
5. Update [LED_SYSTEM.md](LED_SYSTEM.md) and the
   [LED simulator](../tools/simulators/led_simulator/README.md) to match.

**Needs hardware:** Ideally yes — the perceived smoothness is a real-world judgement. The
[LED simulator](../tools/simulators/led_simulator/README.md) and its canned car logs cover
most of the iteration, though the actual `strip.show()` timing is Nano-specific.

**Done when:** Full-throttle blips in neutral track the tachometer with no visible delay;
the strip shows a continuous bottom-to-top gradient; and the top of the strip reaches red
at the true redline rather than 1000 RPM early.

---

## ISSUE-13 — Overview gear ladder is not in numeric order

**Status:** ✅ **Fixed and flashed (2026-10-30).**

`drawGearLadder()` now draws all six gears in numeric order on a 2 × 3 grid — `1 2` /
`3 4` / `5 6` — with the current gear's cell elevated and the sweet-spot information
carried only by the colour of each RPM figure (green inside 2400–4500, blue below, red
above). The rows are painted only when their own value changes, so the ladder no longer
flashes as the speed changes.

**Where it lives:** [ui_core.cpp](../display/src/ui_core/ui_core.cpp) — `drawGearLadder()`.

**Reported:** "On the overview ESP32 screen where it shows gears and the associated RPM, it
should order the gears from 1-6 numerically rather than random order."

**What it did before:** the old code scored all six gears by how far their predicted RPM
was from the 2400–4500 band and printed the three lowest scores in score order. That is
*by design* ("the three most likely"), but the visible result was a list whose numbers
jumped around (`4, 3, 5`), which reads as broken rather than helpful.

**Done when:** At 60 km/h in 4th the ladder reads `1 2 / 3 4 / 5 6` with 4 highlighted,
and the numbers never reorder as speed changes. — *believe met; confirm on the next drive.*

---

## ISSUE-14 — Reverse reports a positive speed and gear 1

**Status:** ⏳ **Open — blocked on one capture** (found in the car 2026-10-30, supersedes
the "fixed" claim in ISSUE-01).

`tools/can/reverse_probe.py` captures both buses in two states and diffs them. The
*analysis* half is now verified without the car: `tools/can/test_reverse_probe.py` pins
down what "the signal" looks like against synthetic captures (7/7 pass), and two real
defects were fixed while doing it:

1. **The tool refused to run without `python-can`**, even for `diff`, which only needs the
   saved JSON. Captures are taken on the Pi and read wherever it is comfortable; the import
   is now inside `capture()`.
2. **One noisy byte demoted an entire frame.** `0x201` carries the engine speed, so most of
   it changes constantly — which meant a clean reverse bit sitting in byte 5 of `0x201`
   was reported as a weak candidate, exactly the frame most likely to hold the answer. A
   frame is now a strong candidate when *at least one* changed byte is stable in each
   capture and takes different values in each, and the report names that byte.

**Reported:** "When driving in reverse, the ESP32 shown speed is still positive, meaning
the translated gear is still first rather than reverse."

**Why this is a different bug from ISSUE-01:** ISSUE-01 fixed the *transport* — the ESP no
longer has to infer reverse from a rounded speed, it gets an explicit flag. But the flag is
only ever set by `_update_gear_estimation()` when `telemetry.speed_kmh < 0`
([can_handler.py](../pi/ui/src/can_handler.py#L924)). A **positive** reading while
reversing means `parse_speed()`
([can_handler.py](../pi/ui/src/can_handler.py#L108)) is not producing a negative number in
reverse, so:

- the reverse branch never runs, `is_in_reverse` stays false, `gear` is estimated from
  `speed/rpm` at a few km/h → the estimator returns gear **1**; and
- the wire speed is positive, so the ESP shows a positive speed by design
  (`esp32_serial_handler.py` clamps `<= 0` to 0, it does not take an absolute value).

So the offset assumption `true_kmh = (raw - 10000) / 100` is either wrong in reverse or the
car does not encode reverse in this field at all.

**Proposed approach — measure before changing the decode:**

1. **Raw-frame log.** Add a `--can-log-reverse` mode to `can_handler.py` that dumps every
   HS-CAN and MS-CAN frame (id + 8 bytes + timestamp) to `state/reverse_probe.log`, started
   and stopped from the Android app's System page. Reverse for ~5 s, then drive forward at
   the same speed in 1st.
2. Diff the two logs. The answer is one of:
   - `0x201` bytes 4–5 *does* go below the zero point → the offset/scale is wrong; fix the
     decode (and confirm the forward scale still matches GPS/known speed).
   - `0x201` never changes in reverse (unsigned field) → **the sign is not available**;
     find the real reverse signal instead.
3. **Likely real reverse sources on an NC**, in order of preference:
   - the **backup-lamp switch** state, which the body module broadcasts on MS-CAN
     (search the probe log for a bit that toggles only in reverse);
   - the PCM's transmission-range frame, if it distinguishes R from N;
   - last resort: a physical tap on the reverse switch wire, read on a spare Pi GPIO.
4. **Make it explicit end to end.** Once a source is chosen, set
   `telemetry.is_in_reverse` from it directly (not from the sign of speed), keep the
   500 ms hold, and keep the negative-speed path only as a backstop.
5. **Do not hide it in the UI.** If no reverse signal is found, the ESP should show `N`
   plus a `REV?` hint rather than confidently showing `1`.

**Done when:** Selecting reverse shows `R` on the ESP32 within one refresh, the speed card
shows the reverse speed (or `0` with the `R` marker, per the existing clamping rule), and
the gear ladder shows `REVERSE`. Neutral must not flicker between `R` and `1`.

---

## ISSUE-15 — The LED control surface is one chip row

**Status:** ✅ **Built end to end (2026-10-30, no car needed) — needs one device pass.**

- **Firmware:** besides the ramp/`CFG:bright|theme|full`/`DEMO:` work already on the
  strip, the Nano now takes `en=`, `mode=`, `shift=`, `hz=` and `scol=` in `CFG:`, plus
  `SELFTEST` and `IDENTIFY`. Those five used to be compile-time constants, so "switch the
  strip off" and "set the shift point" both needed a reflash. They persist in the EEPROM
  block, whose magic byte is now a layout version (`0x5B`) so an older block is rejected
  instead of half-read.
- **Pi:** `led_enabled`, `led_color_mode`, `led_shift_rpm`, `led_shift_hz` and
  `led_shift_color` are validated in `update_setting()` (an out-of-range value is a 400,
  not a silently-clamped surprise), exposed in `/api/status`, forwarded to the strip, and
  persisted to `state/led_settings.json` so a Pi restart no longer undoes the app's
  choices. `POST /api/led/command` forwards `SELFTEST`/`IDENTIFY`/`DEMO:` from an
  allow-list — `CFG:reset` is deliberately not in it, because that reboots the board.
- **App:** `LedScreen` (phone-only, `piScreen() == -1`) replaces the single chip row.
  Strip group (enable, brightness, fill pattern, colour mode), colour-ramp group
  (follow-theme switch, a "Full at" rpm scale, six colour swatches), shift-light group
  (on/off, start rpm, flash rate, colour) and a diagnostics group that renders the Nano's
  live `STATUS:` line, with self-test and identify buttons. Settings keeps a one-line
  summary that opens it.
- **Latency:** the sliders push on release, not per tick, and both the serial write and
  the JSON save skip identical payloads. A drag would otherwise queue more commands than
  9600 baud can carry.

**Remaining:** one pass on the car — change each control and watch the strip, then power
cycle the Nano and the Pi and confirm the values come back.

**Reported:** "I want to totally revamp the LED logic, but need to develop the plan more,
specifically improving the Android MX5 app settings menu for the LEDs."

**Owner's requirements, verbatim (2026-10-30).** Kept word for word so the intent cannot
drift while the plan is implemented — the design answer for each is in
[LED_REVAMP_PLAN.md §2.1](LED_REVAMP_PLAN.md#21-owners-requirements-2026-10-30-verbatim-intent).

> here is my idea for the arduino led strip. firstly, it should reference the andriod app
> color scheme colors, so the leds match the color scheme, when in dark color mode, it
> shuold be dimmer than when in color scheme light mode. the andriod mx5 app settings
> shoudl be able to enable/disable this feature, going to hard color and brightness
> settings instead. addistionally, i want to be able to set the Rpm scale that goes from
> 1-10 or whatever the range is on the outside in rpm led color leds basically, so it is
> fully iluminated at different rpm customizable. also, i want it to change colors more
> seemlessly rather than going from red to blue for example instantly, it should do that
> over a range of rpmssmoothly. the led rpm is also still very delayed, compared to even
> the esp displayed rpm. I want a very high refresh rate on the arduino leds, without
> changing the baud rate or anything that would break it.

**What exists:** `SettingsScreen` has a `LED STRIP` group containing one 4-way *Sequence*
chip row ([SettingsScreen.java](../android/mx5-remote/src/main/java/com/mx5/remote/SettingsScreen.java#L115)).
Brightness in that screen controls the **Pi display**, not the strip. Everything else about
the strip — zone boundaries, redline, colours, shift point, brightness — was compiled into
the Nano's firmware, and no state came back from it.

**What the revamp replaces it with:** a dedicated `LED STRIP` screen (phone-only,
`piScreen() == -1`) with strip enable + brightness, fill pattern, colour mode, a 6-stop
editable colour ramp, a shift-light group, and a diagnostics group (live `STATUS:` from the
Nano, self-test, identify). The Nano gains a `CFG:` command set and reports
`STATUS:`/`OK:`/`ERR:` back over the same UART, which the Pi currently never reads.

**Done when:** every LED behaviour can be changed from the phone, takes effect live,
survives a power cycle, and a dead strip says so on both the strip and the phone.

---

## Historical resolution order (first in-car round, 2026-10-18)

Shared plumbing landed once, then each device, so every group could be built before the
next depended on it. **This is the record of that round, not the current state** — see the
status table at the top for what the car actually does.

**Group A — data correctness** ✅
- [ISSUE-06](#issue-06--android-speed-reads-about-two-thirds-of-actual) — speed is km/h
  everywhere; the double conversion is gone.
- [ISSUE-03](#issue-03--intake-air-temperature-always-zero-on-android) — IAT is decoded
  from OBD-II PID `0x0F`.
- [ISSUE-08](#issue-08--fuel-percentage-is-not-stable) — 60 s wall-clock rolling average.

**Group B — link protocol** ✅
- [ISSUE-01](#issue-01--reverse-gear-not-detected-on-esp32) — explicit reverse flag.
- [ISSUE-04](#issue-04--throttle-and-brake-wrong-on-the-rpm-page) — brake in the payload,
  engine-frame throttle, staleness guard.
- [ISSUE-10](#issue-10--instantaneous-mpg-always-shows-the-empty-placeholder) — validity
  flag separates "unknown" from `0` (reading still depends on a MAF reply).

**Group C — ESP rendering** ✅
- [ISSUE-02](#issue-02--esp32-theme-does-not-match-the-android-app) — runtime theme first,
  since it touches every screen.
- [ISSUE-11](#issue-11--tpms-card-should-become-a-gear--rpm-card) — Overview gear ladder.
- [ISSUE-05](#issue-05--esp32-gyro-screen-still-uses-the-old-visualization) — G-force port.
- [ISSUE-07](#issue-07--startup-animation-is-plain) — boot animation.

**Group D — independent** ✅
- [ISSUE-12](#issue-12--led-strip-is-laggy-and-lacks-a-gradient) — Arduino only.
- [ISSUE-09](#issue-09--app-is-not-available-while-driving) — Android only: the
  `drive` flavor's templated surface, alongside the parked app.

---

## Second-pass audit (before in-car testing)

Each fix was re-read end-to-end — producer → wire → consumer — rather than trusted
because it compiled.

| Issue | Traced path | Result |
|-------|-------------|--------|
| 01 reverse | `0x201` decode → estimator → `TEL` field 16 → ESP `isInReverse` → Overview/RPM gear text | ✅ Confirmed; wire line verified field-by-field |
| 02 theme | phone toggle → `PiClient.updateSetting` → `/api/settings/update` → Pi settings → `send_all_settings`/`send_theme` → ESP `THEME:` → NVS → repaint | ✅ Confirmed; dark **and light** rendered in the simulator |
| 03 IAT | OBD request rotation → `0x7E8` reply → `parse_intake_temp` → telemetry → HTTP → Engine tile+bar | ✅ Confirmed; needs an ECU reply |
| 04 pedals | `0x201` b6 / `0x200` b4 fallback → staleness → `TEL` field 3/17 → ESP meter + Android bar | ✅ Confirmed; source choice still needs a log |
| 05 gyro | local IMU → `linearAccelX/Y` → scatter/trail → restore-then-draw | ✅ Confirmed; rings, labels and trail render |
| 06 speed | `parse_speed` → telemetry → HTTP `speed_kmh` → `speedFor()`; `TEL` → `displaySpeedKmhOrMph()` | ✅ Confirmed numerically (km/h in, km/h out, sign preserved) |
| 07 boot | NVS theme → logo zoom → arc sweep → title | ✅ Builds; pacing is a hardware judgement |
| 08 fuel | raw frame → 60 s deque average → hysteresis → telemetry → all three UIs and the MPG calculator | ✅ Confirmed; running sum matches a brute-force recompute |
| 09 driving | flavor split → `Mx5CarAppService` → session → `PaneTemplate` → shared `PiLink` | ✅ Two APKs verified: parked = game + `CAR_LAUNCHER`; drive = `category.IOT` service, no `appCategory` |
| 10 instant MPG | MAF reply → guards → `instant_mpg_valid` → `TEL` field 18 / HTTP → `--` | ✅ Confirmed; still depends on a MAF reply |
| 11 ladder | speed → six predicted RPMs → band distance → top three | ✅ Confirmed against the screenshot values |
| 12 LEDs | CAN frame → immediate render → per-LED ramp → changed-only transfer | ✅ Ramp table checked; build clean |

### Defects the audit found and fixed

1. **Brake staleness was tuned for the wrong frame.** Using the 750 ms throttle window on
   `0x212` could blink the brake indicator off during a long stop if that body frame is
   slower than the engine frame. Brake now has its own 2.5 s window.
2. **Light mode had two invisible elements.** The dark carbon background image stayed
   behind light cards, and the "unlit" stroke colour (201,202,214) vanished on a near-white
   page. Light mode now fills a themed background and uses a mid-grey stroke; verified by
   rendering the simulator in light mode.
3. **LED update ran at CAN frame rate.** Painting after every CAN read is what removes the
   lag, but it also recomputed 20 LED colours hundreds of times a second for an unchanged
   RPM. A `lastRenderedRPM` gate now skips both the maths and the transfer, and is
   invalidated on sequence change and when error mode ends.
4. **`interpolateColor` cast a negative delta to `uint8_t`.** Undefined behaviour on any
   descending ramp (yellow's green 210 → orange's 128). It happened to land correctly on
   AVR because the arithmetic wraps mod 256, but it is now done in float and cast once.
5. **Fuel averaging did O(n) work per frame.** A minute of samples at 10-20 Hz is fine, but
   `sum()` over the window on every frame is avoidable; a running total over a `deque`
   makes it O(1) and bounded.
6. **Throttle source was unverifiable from the car.** A periodic
   `THR: engine(0x201)=…% legacy(0x200)=…%` log was added so the first drive settles the
   question without any extra tooling.
7. **The Overview gear ladder overlapped the MPG/FUEL/RANGE card.** The block started at
   y=242 while the cards end at y=244, and its background clear-rect wiped the right
   card's bottom corner. It now starts at y=250 with a 24 px row height; verified by
   cropping the rendered frame.
8. **A Pi restart could clobber the display's theme.** The Pi's `theme_scheme` defaulted
   to `aurora`, and the connect-time settings sync would push that (dark) over whatever
   the ESP had stored. It now defaults to empty and is only forwarded once the phone has
   actually sent one.
9. **G-force trail could erase its own axis labels** at full deflection. Labels moved
   outside the clamp radius and the clamp moved 4 px inside the ring.

### Remaining risks that only the car can settle

- `0x201` byte 6 may not be throttle on this particular car; the fallback and the log are
  the mitigation.
- `0x212` may not carry a brake bit at all on this model year.
- PID `0x0F` may go unanswered.
- MAF (`0x10`) may never be received if the interface is listen-only.
- `android:appCategory="game"` is application-wide; whether a head unit offers the
  drive package's `IOT` service as a launcher tile, and keeps it available in motion, can
  only be confirmed on the head unit. The split removes the package-level conflict, but
  the host still has the final say.
- The gear-ratio constants assume the 6-speed / 4.10 final drive.
- `HSCanID.GEAR_POSITION` is read from `0x231`, while `docs/ARCHITECTURE.md` documents
  gear on `0x228`. Gears 1-6 are estimated regardless, so this only affects **neutral**
  detection — worth watching for whether `N` appears reliably at a standstill.

---

## Build verification

What was actually run after the LED-screen round (2026-10-30, no car, no phone, and
**nothing uploaded**):

| Component | Command | Result |
|-----------|---------|--------|
| Arduino Nano firmware | `pio run -d arduino -e nano` | ✅ SUCCESS — RAM 33.6%, flash **52.4%** (16 KB free; the CFG keys, shift light and bench commands cost ~1.4 KB) |
| ESP32-S3 firmware | `pio run -d display` | ✅ SUCCESS — RAM 30.0%, flash 35.2% |
| Android app (both flavors) | `gradlew --offline :mx5-remote:assembleParkedDebug :mx5-remote:assembleDriveDebug` | ✅ BUILD SUCCESSFUL |
| Pi link protocol + LED keys | `python pi/ui/src/test_link_protocol.py` | ✅ **58/58** passed (was 50; +8 for the new settings and the LED command allow-list) |
| Reverse probe analysis | `python tools/can/test_reverse_probe.py` | ✅ **7/7** passed |
| Pi LED persistence | ad-hoc round trip | ✅ save → load identical; missing file and corrupt JSON both fall back to defaults without raising |
| Pi modules | `python -m py_compile main.py link_service.py web_server.py link_protocol.py` | ✅ clean |

Earlier round, for the record:

| Component | Command | Result |
|-----------|---------|--------|
| ESP32-S3 UI (native sim) | `tools\simulators\native\build.bat` | ✅ builds; screens rendered to `shot_0..7.bmp` |
| Android manifests | `aapt2 dump xmltree` | ✅ parked = `game` + `CAR_LAUNCHER`; drive = `category.IOT` service |
| Pi CAN parsing | ad-hoc checks | ✅ speed km/h, negative flooring, throttle `0x201`, IAT `0x0F`, 60 s fuel window, reverse flag |

`pio run -d arduino` also reports the `native_sim` environment as FAILED on this machine
because it compiles for the host and no `g++` is installed. That is an environment
limitation, not a code failure; `nano` — the environment that ships — succeeds.

---

## Staging & deployment

> **Status:** the first round *was* deployed and driven (see the result table at the end of
> this section). The original ordering notes are kept because the link protocol still
> changed on both ends, and the next delta is small and listed below the table.

| Step | Target | Command / action | Why this order |
|------|--------|------------------|----------------|
| 1 | **Pi** | `ssh pi@192.168.1.23 'cd ~/MX5-Telemetry && git pull && sudo systemctl restart mx5-display'` | The Pi is the source of every value. The new `TEL:` fields are appended, so an old ESP still parses fields 0-14 correctly. |
| 2 | **Arduino Nano** | Plug into the PC, then `pio run -d arduino -e nano --target upload` | **Not protocol-order-dependent, but do it with the phone work:** the new `CFG:en/mode/shift/hz/scol` keys and `SELFTEST`/`IDENTIFY` only exist in this build. An old Nano answers `OK:CFG` to keys it ignores, so the app would look like it worked while nothing changed. |
| 3 | **ESP32-S3** | `ssh pi@192.168.1.23 'cd ~/MX5-Telemetry && git pull && ~/.local/bin/pio run -d display --target upload'` | Adds the reverse/brake/MPG-valid fields, theme support, gear ladder, G-force port and boot animation. Works against a new Pi; against an old Pi it just keeps the defaults. |
| 4 | **Android phone** | `adb install -r android\mx5-remote\build\outputs\apk\parked\debug\mx5-remote-parked-debug.apk` and `...\apk\drive\debug\mx5-remote-drive-debug.apk` | The parked app now pushes the theme and carries the `LED STRIP` screen; the drive app is the templated surface. Both are needed for the two launcher tiles. |

Then, with the car:

1. Ignition on, engine running: confirm the ESP boots to dark aurora, then change scheme
   in the phone app and confirm the ESP follows within ~1 s.
2. Reverse: `R` on both the ESP Overview and RPM pages, and a **negative** or `0` speed.
   If it still shows gear 1, run the two-state capture
   (`python3 tools/can/reverse_probe.py capture park` / `capture reverse`, then
   `diff park reverse` — the diff runs anywhere, no `python-can` needed).
3. Stationary: press each pedal; throttle % and the brake ON/OFF indicator must track.
   Capture a `0x200`/`0x201`/`0x212` log if throttle still looks wrong.
4. Steady 40 mph: phone, ESP and the car's speedometer agree, and the Engine page shows a
   real instantaneous MPG rather than `--`.
5. `LED STRIP` screen: toggle enable (strip goes dark), move each slider, pick a colour,
   set "Full at" to ~4000 and watch the bar fill sooner, then `Self test` and `Identify`.
   Power-cycle the Nano **and** the Pi and confirm every value comes back.
6. Drive: fuel % and range hold steady; the LED strip tracks a blip with no visible lag.

### Result of that run (2026-10-30)

### Result of that run (2026-10-30)

The build **was** deployed and driven. Verdicts from the list above:

| Check | Result |
|-------|--------|
| 1. Theme follows the phone | ✅ works |
| 2. `R` in reverse | ❌ shows a positive speed and gear 1 — see ISSUE-14 |
| 3. Pedals | ✅ works |
| 4. Speed agrees | ✅ works |
| 5. `MAF:` log line | ❌ never appears — HS-CAN is listen-only (ISSUE-03/10) |
| 6. Fuel steady, LED tracks RPM | fuel ✅ · **LED ❌ permanently blue** (ISSUE-12) |

Additional findings not on that list: the Overview gear ladder's ordering is confusing
(ISSUE-13), the drive app is still not reachable (ISSUE-09), and the boot animation is not
impressive enough yet (ISSUE-07).

**Next deploy delta** (nothing else needs reflashing):

| Step | Target | Action |
|------|--------|--------|
| 1 | **Pi** | Edit `pi/mx5-can-setup.sh` line 13 to `listen-only off` for `can1` (HS), leave `can0` (MS) listen-only, re-run it, restart `mx5-display`. Then watch for `MAF:` in the log. |
| 2 | **Arduino Nano** | Nothing yet — wait for Phase 0/1 of [LED_REVAMP_PLAN.md](LED_REVAMP_PLAN.md). |
| 3 | **Android** | Rebuild once the drive manifest meta-data is added (ISSUE-09). |

---

## Decisions taken

1. **ISSUE-09:** a reading-glanceable Car App Library driving UI (not "parked only").
2. **ISSUE-11 → ISSUE-13:** superseded. The ladder now shows all six gears **in numeric
   order** (2 × 3 grid) with the sweet-spot colour still carried by the RPM text; "three
   most likely, ranked" read as scrambled in the car.
3. **ISSUE-06:** km/h is the canonical unit inside the Pi; mph is a display conversion.
4. **ISSUE-04:** brake stays a binary pedal switch and is displayed as ON/OFF. If a real
   travel/pressure value is ever found on the bus, it should become a bar.
5. **ISSUE-12/15:** LED behaviour is settings, not `#define`s. The Pi is the single source
   of truth and serialises to the Nano; the Nano keeps reading CAN itself so the sub-
   millisecond path is untouched. See [LED_REVAMP_PLAN.md](LED_REVAMP_PLAN.md).

---

## Still open

- **ISSUE-14:** find the real reverse signal. The sign of the `0x201` speed field does not
  carry it on this car. The probe tool now diffs two captures offline
  (`tools/can/reverse_probe.py diff park reverse`, no `python-can` needed) and picks the
  byte that actually discriminates; what is missing is the one 8-second capture in each
  state.
- **ISSUE-15 / 12:** built end to end — one device pass to confirm every control moves the
  strip and survives a power cycle on both ends.
- **ISSUE-09:** check the drive package on the head unit; a Play internal test track if the
  host refuses sideloaded templated apps.
- **ISSUE-04:** confirm the `0x201` byte-6 throttle layout with a pedal log.
- **ISSUE-03 / 10:** ✅ *answered* — HS-CAN now transmits (`listen-only off` on `can1`,
  MS-CAN stays listen-only), the ECU answers `0x0F` and `0x10`, and the Android page's
  lost validity flag is fixed.
- **ISSUE-07:** a proper startup animation. Design pass, then implement; only the car can
  judge the pacing.
- **ISSUE-02:** the light theme is an sRGB approximation of the app's OKLCH derivation.

