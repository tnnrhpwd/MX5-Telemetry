# Known Issues — In-Car Findings

**Recorded:** 2026-10-18
**Vehicle:** Mazda MX-5 NC (2006-2015)
**Source:** Issues identified during real in-car testing

> ⚠️ **Verification status.** Every issue below was investigated in code and **fixed**
> (see each issue's **Status** line). Nothing has been re-tested against the car: it is
> offline and the test phone is not plugged in, so each fix is verified only as far as
> "the project builds" — see [Build verification](#build-verification). Issues whose
> correct behaviour depends on a CAN frame layout still carry a **Needs hardware** note.
>
> Changes are staged in the repository but **not deployed**. See
> [Staging & deployment](#staging--deployment) for what has to be flashed/installed and
> in what order.
>
> The **Status** line at the top of each issue is authoritative. The *Working theory* and
> *Proposed approach* sections below it are the investigation notes from before the fix
> and are kept for context; line-number links point at the code as it was then, so the
> file links still work but the `#L…` anchors may have drifted.

---

## Summary

| ID | Issue | Device(s) | Type | Severity | Status |
|----|-------|-----------|------|----------|--------|
| [ISSUE-01](#issue-01--reverse-gear-not-detected-on-esp32) | Reverse gear not detected when speed goes backwards | ESP32-S3 | Bug | 🟠 High | ✅ Fixed (unverified in car) |
| [ISSUE-02](#issue-02--esp32-theme-does-not-match-the-android-app) | ESP display theme/dark-light mode does not match the Android app | ESP32-S3 | Feature | 🟡 Medium | ✅ Fixed (unverified in car) |
| [ISSUE-03](#issue-03--intake-air-temperature-always-zero-on-android) | Intake air temperature always 0 | Android | Bug | 🟡 Medium | ✅ Fixed (needs ECU reply) |
| [ISSUE-04](#issue-04--throttle-and-brake-wrong-on-the-rpm-page) | Throttle and brake wrong on the RPM page | Android (+ ESP) | Bug | 🟠 High | ✅ Fixed (needs CAN log) |
| [ISSUE-05](#issue-05--esp32-gyro-screen-still-uses-the-old-visualization) | Gyro screen still uses the old display code | ESP32-S3 | Bug | 🟡 Medium | ✅ Fixed (unverified in car) |
| [ISSUE-06](#issue-06--android-speed-reads-about-two-thirds-of-actual) | Speed reads ~⅔ of actual | Android | Bug | 🔴 Critical | ✅ Fixed (unverified in car) |
| [ISSUE-07](#issue-07--startup-animation-is-plain) | Startup animation needs polish | ESP32-S3 | Polish | ⚪ Low | ✅ Fixed (unverified in car) |
| [ISSUE-08](#issue-08--fuel-percentage-is-not-stable) | Fuel % jumps around; needs averaging | Pi / all UIs | Bug | 🟡 Medium | ✅ Fixed (unverified in car) |
| [ISSUE-09](#issue-09--app-is-not-available-while-driving) | App not viewable while driving | Android Auto | Feature | 🟠 High | ✅ Implemented (needs head unit) |
| [ISSUE-10](#issue-10--instantaneous-mpg-always-shows-the-empty-placeholder) | Instantaneous MPG always shows `---` | ESP32-S3 / Pi | Bug | 🟡 Medium | ⚠️ Partial — needs MAF reply |
| [ISSUE-11](#issue-11--tpms-card-should-become-a-gear--rpm-card) | TPMS card on Overview → 3-gear RPM view | ESP32-S3 | Feature | 🟡 Medium | ✅ Fixed (unverified in car) |
| [ISSUE-12](#issue-12--led-strip-is-laggy-and-lacks-a-gradient) | LED strip laggy; flat colours, no gradient | Arduino Nano | Bug / Polish | 🟠 High | ✅ Fixed (needs car to judge feel) |

**Status key:** ✅ code complete and building · ⚠️ partially addressed, see the issue ·
⏳ open. "Unverified in car" means the build passes but the car has not been driven
since.

**Severity key:** 🔴 Critical = wrong data a driver may act on · 🟠 High = clearly broken or
dangerously stale · 🟡 Medium = visibly wrong or missing information · ⚪ Low = cosmetic.

---

## ISSUE-01 — Reverse gear not detected on ESP32

**Status:** ✅ **Fixed.** Reverse is now an explicit flag in the link protocol instead
of something the ESP infers from a rounded speed.

- `esp32_serial_handler.py` clamps the transmitted speed to `0` and appends
  `reverse` as field 16 of `TEL:`.
- `display/src/main.cpp` reads it into `telemetry.isInReverse`;
  `ui_core.cpp` uses that flag on the Overview and RPM screens.
- `telemetry.isInReverse` is set by the Pi whenever speed is negative, and held for
  500 ms after it returns to zero.

**Remaining:** drive in reverse on the car to confirm. Watch the Pi console for the
`TEL:` line — field 3 should be `-1` and field 16 should be `1`.

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

**Status:** ✅ **Fixed (pending an ECU reply).** The field was never written; it now is.

- `can_handler.py` polls OBD-II PID `0x0F` on the existing request slot, alternating
  with MAF so bus load is unchanged, and decodes the reply into
  `telemetry.intake_temp_f`.
- The demo generator is no longer the only thing that sets it.

**Remaining:** confirm the NC's ECU answers PID `0x0F`. If it does not, the value stays
0 and the next option is a broadcast frame on the MS-CAN body bus (needs a log).

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

**Status:** ✅ **Fixed.** `playStartupAnimation()` in `main.cpp` replaces the single blit
and 1.5 s `delay()`.

Three beats, fixed total length (~1.45 s, no longer than before):
1. the logo zooms in from 40% to 100%;
2. a tach-style arc sweeps 135°→405° and settles back to empty, matching the RPM
   screen's geometry;
3. the title `MX5 TELEMETRY` fades in over a growing accent rule.

The theme is loaded from NVS *before* the animation, so the boot sequence is already in
the phone's colours.

**Remaining:** judge the pacing on the real panel.

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

**Status:** ✅ **Implemented** as option 1 (Car App Library, Driving category).

- New `Mx5CarAppService` (`CarAppService`) declared in the manifest with
  `<category android:name="androidx.car.app.category.DRIVING" />`.
- `Mx5CarSession` → `Mx5CarScreen`, a `PaneTemplate` showing Speed, Gear, RPM and Fuel,
  polled once a second from the shared `PiLink` client.
- `androidx.car.app:app:1.4.0` is now the module's only dependency.
- The parked dashboard is untouched: the host offers whichever surface the user opens.

The template is deliberately four rows and read-only — that is what keeps it compliant
with the driving rules, and it is also why the parked dashboard's custom views cannot be
reused in motion.

**Remaining:** test on the head unit with the car moving. Note that
`HostValidator.ALLOW_ALL_HOSTS_VALIDATOR` is used because the app is sideloaded.

**Reported:** The app cannot be opened in Android Auto while the car is moving. That was
expected, but the app should be viewable during driving.

**Where it lives:**
- [AndroidManifest.xml](../android/mx5-remote/src/main/AndroidManifest.xml#L1) —
  `android:appCategory="game"` + `category.CAR_LAUNCHER`
- [android/README.md](../android/README.md#L31) — the "parked-app gate" findings
- [docs/ANDROID_AUTO_PLAN.md](ANDROID_AUTO_PLAN.md) — the original phasing

**Working theory:**
This is a platform rule, not a bug. `appCategory="game"` is a **parked** category: Android
Auto deliberately greys it out while the vehicle is in motion, and games are the only
AA-supported *parked* category. No manifest flag lifts that restriction.

There are only two honest paths:
1. **Car App Library with the Driving category.** A `CarAppService` declaring
   `androidx.car.app.category.DRIVING` gets template-rendered UI that *is* allowed while
   moving. The catch is that the UI must be built from AA templates (`NavigationTemplate`,
   `PaneTemplate`, `MessageTemplate`, …) — the current custom dashboard views cannot be
   reused directly, and everything shown while driving must be distraction-optimised.
2. **Keep the parked app** and accept that it is only usable stationary.

The research in [android/README.md](../android/README.md) already established that
**both** mechanisms were accepted by the test head unit, so the driving category is not a
blind alley — but its UI model is different enough that this is a significant piece of
work, not a manifest tweak.

⚠️ **Safety note.** Driver-distraction rules exist for a reason. Whatever is added under
the Driving category must be glanceable, must not require scrolling to find critical data,
and must not add interaction-heavy surfaces. Prefer read-only templates.

**Proposed approach:** Decide explicitly between "template UI while driving" and "parked
only", then either add a `CarAppService` + `CarAppExtender` alongside the existing
activity (both can ship in one APK) or accept the limitation. Do not attempt to defeat the
parked gate.

**Needs hardware:** Yes — the head unit is the only real test for driving-category
rendering.

**Done when:** The app is openable with the vehicle in motion *through a supported
mechanism*, or the limitation is documented and accepted.

---

## ISSUE-10 — Instantaneous MPG always shows the empty placeholder

**Status:** ⚠️ **Partially fixed.** The UI no longer lies, but the underlying reading
still depends on a MAF reply the car may not be sending.

- "Unknown" is now distinct from "0 mpg": `instant_mpg_valid` travels in `TEL:` and in
  the HTTP snapshot, and both the ESP and the Android Engine page show `--` only when it
  is false.
- OBD-II requests now rotate MAF (`0x10`) and intake air (`0x0F`) on one slot.

**Remaining:** the primary suspect — a `0x7DF` request that is never transmitted because
the interface is listen-only — cannot be confirmed or fixed from here. A silent `MAF:`
log line on the car means no reply is arriving. Until that is resolved the page will show
`--`, which is now accurate rather than a fake `0.0`.

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

**Status:** ✅ **Fixed.** The Overview tire grid is replaced by `drawGearLadder()`.

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

**Status:** ✅ **Fixed** in `arduino/src/main.cpp`.

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

## Resolution order (as implemented)

Shared plumbing landed once, then each device, so every group could be built before the
next depended on it. All groups are now done.

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
- [ISSUE-09](#issue-09--app-is-not-available-while-driving) — Car App Library driving
  surface.

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
| 09 driving | `Mx5CarAppService` → session → `PaneTemplate` → shared `PiLink` | ✅ Service + DRIVING category present in the built APK |
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
  DRIVING service for an app also declared as a parked game can only be confirmed on the
  head unit.
- The gear-ratio constants assume the 6-speed / 4.10 final drive.
- `HSCanID.GEAR_POSITION` is read from `0x231`, while `docs/ARCHITECTURE.md` documents
  gear on `0x228`. Gears 1-6 are estimated regardless, so this only affects **neutral**
  detection — worth watching for whether `N` appears reliably at a standstill.

---

## Build verification

What was actually run after the changes (no car, no phone):

| Component | Command | Result |
|-----------|---------|--------|
| ESP32-S3 UI (native sim) | `tools\simulators\native\build.bat` | ✅ builds; screens rendered to `shot_0..7.bmp` |
| ESP32-S3 firmware | `pio run -d display` | ✅ SUCCESS — RAM 30.0%, flash 34.3% |
| Arduino Nano firmware | `pio run -d arduino -e nano` (after clean) | ✅ SUCCESS — RAM 20.3%, flash 42.5% |
| Android app | `gradle -p android :mx5-remote:assembleDebug` | ✅ BUILD SUCCESSFUL |
| Pi Python + link protocol | `python pi/ui/src/test_link_protocol.py` | ✅ 50/50 passed |
| Pi CAN parsing | ad-hoc checks | ✅ speed km/h, negative flooring, throttle `0x201`, IAT `0x0F`, 60 s fuel window, reverse flag |

`pio run -d arduino` also reports the `native_sim` environment as FAILED on this machine
because it compiles for the host and no `g++` is installed. That is an environment
limitation, not a code failure; `nano` — the environment that ships — succeeds.

---

## Staging & deployment

Nothing has been flashed or installed. The changes are committed in the repository and
ready to deploy in this order; the order matters because the link protocol changed on
both ends.

| Step | Target | Command / action | Why this order |
|------|--------|------------------|----------------|
| 1 | **Pi** | `ssh pi@192.168.1.23 'cd ~/MX5-Telemetry && git pull && sudo systemctl restart mx5-display'` | The Pi is the source of every value. The new `TEL:` fields are appended, so an old ESP still parses fields 0-14 correctly. |
| 2 | **ESP32-S3** | `ssh pi@192.168.1.23 'cd ~/MX5-Telemetry && git pull && ~/.local/bin/pio run -d display --target upload'` | Adds the reverse/brake/MPG-valid fields, theme support, gear ladder, G-force port and boot animation. Works against a new Pi; against an old Pi it just keeps the defaults. |
| 3 | **Android phone** | `adb install -r android\mx5-remote\build\outputs\apk\debug\mx5-remote-debug.apk` | The app now pushes the theme and reads `instant_mpg_valid`. |
| 4 | **Arduino Nano** | Plug into the PC, then `pio run -d arduino --target upload` | Independent of the link protocol; can be done any time. |

Then, with the car:

1. Ignition on, engine running: confirm the ESP boots to dark aurora, then change scheme
   in the phone app and confirm the ESP follows within ~1 s.
2. Reverse: `R` on both the ESP Overview and RPM pages.
3. Stationary: press each pedal; throttle % and the brake ON/OFF indicator must track.
   Capture a `0x200`/`0x201`/`0x212` log if throttle still looks wrong.
4. Steady 40 mph: phone, ESP and the car's speedometer agree.
5. Check the `MAF:` log line. If it never appears, instant MPG will correctly show `--`
   until the listen-only question is resolved.
6. Drive: fuel % and range hold steady; the LED strip tracks a blip with no visible lag.

---

## Decisions taken

1. **ISSUE-09:** a reading-glanceable Car App Library driving UI (not "parked only").
2. **ISSUE-11:** the three gears whose predicted RPM is closest to the 2400–4500 band.
3. **ISSUE-06:** km/h is the canonical unit inside the Pi; mph is a display conversion.
4. **ISSUE-04:** brake stays a binary pedal switch and is displayed as ON/OFF. If a real
   travel/pressure value is ever found on the bus, it should become a bar.

---

## Still open

- **ISSUE-04:** confirm the `0x201` byte-6 throttle layout with a pedal log.
- **ISSUE-03:** confirm the ECU answers PID `0x0F`; otherwise find the MS-CAN IAT frame.
- **ISSUE-10:** determine whether the CAN interface is listen-only, which would explain
  the missing MAF reply. Until then instant MPG shows `--` rather than a false zero.
- **ISSUE-02:** the light theme is an sRGB approximation of the app's OKLCH derivation.
- **ISSUE-12:** the zones are anchored to a 6800 redline; adjust if the real limiter
  differs.

