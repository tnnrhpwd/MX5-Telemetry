# LED strip revamp — plan

**Status:** **Phases 0–3 are done; Phase 4 is partially in (shift light, color mode).**
See [§4.1](#41-what-is-already-implemented) for exactly what is in the firmware, the Pi
and the app right now.
**Supersedes:** the "Fixed" verdict on
[KNOWN_ISSUES.md › ISSUE-12](KNOWN_ISSUES.md#issue-12--led-strip-is-laggy-and-lacks-a-gradient).

---

## 1. What is actually wrong today

### 1.1 The failure is invisible (primary root cause)

The Nano reads HS-CAN itself and only paints the strip from `currentRPM`. Every way that
chain can break ends in the *same* picture: two blue edge LEDs.

1. `setup()` runs `startupAnimation()`, which finishes by leaving blue on the two edge
   LEDs, and only then calls `canInitialized = initCAN()`
   ([main.cpp](../arduino/src/main.cpp#L888)).
2. The no-data watchdog is gated on `canInitialized`:
   `if (canInitialized && (nowMs - lastCANData > TIMEOUT_MS))`
   ([main.cpp](../arduino/src/main.cpp#L938)). When `initCAN()` **fails** — bad SPI/CS
   wiring, dead transceiver, 8 MHz vs 16 MHz crystal mismatch, wrong bus — that condition
   is never true, so the `else` branch runs on every loop and forces
   `errorMode = false; displayErrorMode = false;`
   ([main.cpp](../arduino/src/main.cpp#L951)), clearing the flag `setup()` had just set.
3. `updateLEDs()` therefore falls through to `if (currentRPM == 0)`
   ([main.cpp](../arduino/src/main.cpp#L545)) and paints blue edges.

So **"CAN controller dead" and "engine off, everything fine" are the same visual state**,
and `ENABLE_SERIAL_DEBUG` is `false` in the shipped build, so nothing is printed either.

Second, independent path to the same picture: if the Nano's MCP2515 is physically on a
different bus (or its `0x201` frames never arrive), rpm stays 0 and the strip shows the
idle pattern while the car is being driven.

### 1.2 Secondary faults found while reading the code

| # | Fault | Effect |
|---|-------|--------|
| S1 | The app's **Brightness** slider writes `settings.brightness`, which only drives the *Pi display*. The Nano reads a pot on `A6` with no pull-up (`ENABLE_BRIGHTNESS true`, [main.cpp](../arduino/src/main.cpp#L83)) | Strip brightness is random/uncontrollable from the phone; the app appears broken |
| S2 | Only one setting ever reaches the Nano: `SEQ:n` (`_send_led_sequence_to_arduino()`) | Zone boundaries, colors, redline and shift point are compile-time `#define`s |
| S3 | The Pi **never reads** the Nano's serial output (`arduino_serial` is write-only) | No health, no version, no error — a dead strip is indistinguishable from a working one |
| S4 | The Pi has **no settings file** (`Settings` is a dataclass with defaults, nothing persisted) | Every restart reverts to defaults unless the Nano's EEPROM disagrees |
| S5 | `SEQUENCE` names are duplicated in three places: `main.py`, `LCD`/tft screen list, Android `SettingsScreen.LED_NAMES` | Easy to drift |

---

## 2. Goals

- **G1 — Never silent.** Every failure state has its own unmistakable pattern
  (boot, CAN offline, no Pi, bad config). A dead strip must not look like idle.
- **G2 — Everything tunable is a setting**, not a `#define`: brightness, ramp stops,
  fill sequence, color mode, shift light, idle/error behavior, strip length.
- **G3 — The Android app owns the UI** (`LED STRIP` screen), edits apply live.
- **G4 — One source of truth: the Pi.** Phone and ESP32 both write to the Pi; the Pi
  serializes to the Nano. The Nano keeps reading CAN directly for `<1 ms` latency.
- **G5 — Failure is visible in the app too**: "LED strip: OK / no CAN / not answering".

### 2.1 Owner's requirements (2026-10-30, verbatim intent)

These are the requirements that came out of the drive, in the owner's words, with the
design answer each one gets. They extend G2/G3 rather than replace them.

| # | Requirement | Design answer |
|---|---|---|
| R1 | **Follow the app's color scheme.** The strip should use the same colors as the Android app's active theme, and be **dimmer in dark mode, brighter in light mode**. | The phone already owns the theme (`theme_scheme`, `theme_dark` are mirrored to the Pi). The Pi derives the ramp from the theme palette plus a day/night brightness factor and sends it as one `CFG:`+`RAMP:` burst. The app gets a **Follow theme** switch; off = the fixed color/brightness sliders (R2). |
| R2 | **Hard color + brightness settings** as the alternative to R1. | Six editable ramp stops + one brightness value, already in the plan (§6.3, §7.3). The switch in R1 decides which source wins. |
| R3 | **Configurable RPM scale.** "Set the RPM scale that goes from 1-10 or whatever the range is … so it is fully illuminated at different rpm." | `RPM_FULL` becomes a setting (default 6800, range 2000–8000): the rpm at which the strip is completely full. Every LED therefore represents `RPM_FULL / LEDs-per-side` rpm — lowering it makes the bar more granular and *visibly more responsive*. |
| R4 | **Smooth color motion, not instant jumps.** "Change colors more smoothly rather than going from red to blue instantly … over a range of rpm." | New mapping (see 2.2): each lit LED's color is sampled from *its own share of the current rpm* rather than from a fixed position, so colors **flow** along the strip and every LED's color changes continuously as rpm changes. Plus a short temporal blend (~80 ms) so a step never snaps. |
| R5 | **Very high refresh, no protocol change.** "The LED rpm is still very delayed compared to even the ESP's displayed rpm … without changing the baud rate." | The strip is already fed at CAN frame rate (~320 fps); the *apparent* delay is granularity plus the `show()` cadence, not the bus. Fix: sample on **every** CAN frame, keep `show()` gated only on an actual pixel change, cut per-frame work (precomputed ramp LUT), drop the 10 ms poll gate, and reduce the falling-RPM filter. Baud rate is untouched — it only carries settings, not rpm. |

### 2.2 Color mapping — why the current one feels wrong

Today each LED owns a **fixed** color: LED *i* is painted with `ramp(i / (n-1))` and
just switches on when rpm passes its threshold. Two consequences the owner noticed:

- The bar is a static rainbow that grows; the *colors* never move, so nothing looks like
  it is following the engine.
- When the leading edge crosses into the next zone, that one pixel changes color in a
  single step — "red to blue instantly".

The fix is to make the color a function of **rpm**, evaluated per LED:

```
for each lit LED i, with f = (i - firstLit) / (lastLit - firstLit)   // 0 at the root, 1 at the tip
    color(i) = ramp(f * rpm)        // absolute rpm at that share of the bar
```

Now the tip is always `ramp(rpm)` (the true current color), the root is `ramp(small)`
(blue), and every LED's color slides continuously as rpm rises — a gradient that moves.
`ramp()` is a 6-stop linear interpolation over `RPM_FULL`, and a short temporal blend
between the previous and new color removes the remaining step at high frame rates.

---

## 3. Phase 0 — diagnosis (do this first, ~1 hour)

**Done on 2026-10-30, and it changed the diagnosis.** The Nano was reachable over USB
(`/dev/ttyUSB0`, CH340), answered `PING`→`PONG` and `SEQ?`→`SEQ:1`, and — once the firmware
grew a `STATUS` line — reported:

```
STATUS:CAN=1,RPM=0,SEQ=1,ERR=0,FPS=305,LAST=0x201
```

That is a **healthy** strip: MCP2515 initialized, ~320 CAN frames/second arriving, the
engine frame `0x201` being decoded, `ERR=0`. Driving the strip with the firmware's new
bench override then lit **all 20 LEDs in a full gradient at 6500 rpm**. So the LED chain
was never broken; what was broken was that *nothing said so*, and the "always blue"
symptom is consistent with a strip sitting at genuine 0 rpm (engine off) or an older
binary. **The rest of this section is kept for the next time it is not obvious.**

Nothing else in this plan is worth doing until we know *why* the strip is blue.

1. Add a `nano_debug` env to [arduino/platformio.ini](../arduino/platformio.ini) that only
   adds `-DENABLE_SERIAL_DEBUG=1`; it already prints `RPM:`, `SEQ:`, `ERR:` once a second.
2. Flash it, connect USB, engine idling: **if the RPM never moves, the CAN chain is the
   fault** (wiring/crystal/bus), not the LED code.
3. In parallel, check the Nano's own wiring notes: `D2` = MCP2515 INT, `D10` = CS,
   `MCP_8MHZ` ([main.cpp](../arduino/src/main.cpp#L88)). A 16 MHz module with an 8 MHz
   setting produces zero valid frames and exactly this blue state.
4. Record the answer in [KNOWN_ISSUES.md](KNOWN_ISSUES.md).

**Done when:** we can state, in one sentence, whether the Nano decodes `0x201` in the car.

---

## 4. Phase 1 — make failure visible (small, ships first)

| Change | Detail |
|---|---|
| Watchdog ungate | `if (!canInitialized \|\| (nowMs - lastCANData > TIMEOUT_MS))` and a distinct **CAN OFFLINE** pattern, not the scanner |
| Boot status | On boot, one LED shows a color code: green = CAN init OK, orange = CAN init failed |
| Heartbeat | A single dim pixel at position `LED_COUNT-1` blinks 1 Hz while the firmware is alive (proves "alive but no data" vs "not powered") |
| Serial report | Nano prints `STATUS:CAN=1,RPM=812,SEQ=1,ERR=0,FPS=320,LAST=0x201,FULL=6800,DIM=0` at 1 Hz. Harmless today (Pi ignores it) and the foundation for Phase 2 |
| Remove the pot | `ENABLE_BRIGHTNESS false` until a pot is actually fitted and pull-upped; brightness comes from the app |

**Acceptance:** with the MCP2515 unplugged the strip shows CAN OFFLINE within 3 s; plugged
into a 500 kbps source it shows a live bar. No state is mistakable for another.

### 4.1 What is already implemented

Done and verified on the car:

| Item | State |
|---|---|
| Watchdog ungated + `drawCanOffline()` (orange blink) | ✅ in firmware |
| `STATUS:` line with `CAN, RPM, SEQ, ERR, FPS, LAST, FULL, DIM[, DEMO]` | ✅ in firmware, verified at ~320 fps |
| Runtime color ramp (`RAMP:`) — 2–6 `<rpm>:<rrggbb>` stops, last stop = full-illumination rpm | ✅ in firmware, verified |
| `CFG:bright=,theme=,full=,pot=` | ✅ in firmware, verified |
| `DEMO:<rpm>` / `DEMO:OFF` bench override (self-clearing after 60 s) | ✅ in firmware — this is how the strip was validated with the engine off |
| Flowing color mapping (each LED samples its share of the current rpm) + fractional tip | ✅ in firmware |
| Snappier tracking: `RPM_SNAP_DELTA` 400→250, falling alpha 0.60→0.75 | ✅ in firmware |
| Pi→Nano link: identity-checked (`PING`/`PONG`), retries through a reset, never grabs the ESP32's port | ✅ in `main.py` |
| Pi→Nano config forwarding: `led_ramp`, `led_theme_dim`, `led_brightness` settings → `RAMP:`/`CFG:` | ✅ in `main.py` + `link_service.py`, verified through the API |
| Phone pushes a theme-derived ramp (`Palette.ramp()`: accent → primary → the scheme's vivid seed) and the dark/light dim flag | ✅ in `MainActivity.pushThemeToPi()`; fires once the app has a link |
| A 128-byte serial command buffer (the old 32 truncated a full `RAMP:` line and silently produced a 2-stop ramp capped at 1400 rpm) | ✅ fixed |
| `CFG:save` / `CFG?` / `CFG:reset` — ramp, dim, brightness and full-illumination rpm survive a power cycle (EEPROM block behind a magic byte + CRC) | ✅ in firmware, **verified across a watchdog reboot**: `full=4200,dim=1,bright=200` + a 3-stop ramp came back identical |
| The Pi reads the strip's `STATUS:` line and exposes it as `led` in `/api/telemetry` | ✅ live: `{"connected":true,"can":true,"fps":300,"last_id":"0x201","full_rpm":6800,"dim":false,"error":false,"rpm":0}` |
| `CFG:en=`, `CFG:mode=`, `CFG:shift=`, `CFG:hz=`, `CFG:scol=` — strip enable, color mode, shift point/rate/color | ✅ firmware; EEPROM block extended (magic byte bumped to `0x5B`, so an older block is rejected rather than half-read) |
| `SELFTEST` / `IDENTIFY` bench commands | ✅ firmware; 4 s white sweep / 3 s magenta blink, both self-clearing |
| Shift light (whole strip flashes at the configured rpm, rate and color) and color mode (per-LED gradient vs single wash) | ✅ firmware — the shift overlay deliberately bypasses the "same rpm, nothing to do" repaint gate because it changes with time, not with rpm |
| Pi keys `led_enabled`, `led_color_mode`, `led_shift_rpm`, `led_shift_hz`, `led_shift_color` | ✅ `LinkService.update_setting()` validates each (a 400, not a clamp), `/api/status` exposes them, `/api/telemetry.led` carries them back from the strip |
| `POST /api/led/command` (+ the `led.command` op over Bluetooth) | ✅ allow-list: `SELFTEST`, `IDENTIFY`, `PING`, `CFG?`, `DEMO:<rpm>`, `DEMO:OFF`. `CFG:reset` is deliberately absent — it reboots the board |
| Pi persistence: `state/led_settings.json` | ✅ written on change, restored on connect; identical payloads are skipped so a drag cannot hammer the disk. `state/` is gitignored |
| `LED STRIP` settings screen in the app | ✅ `LedScreen.java` — strip / ramp / shift-light / diagnostics groups, phone-only (`piScreen() == -1`), reached from a one-line summary on Settings |
| Slider latency discipline | ✅ sliders push **on release** (`SliderRow.onRelease`), and the Pi skips identical `CFG:`/`RAMP:` writes — 9600 baud cannot absorb a per-tick drag |
| Bench simulator | ✅ `tools/simulators/led_simulator/led_simulator_v3.py` — an rpm slider over `led_engine.py`, a port of the firmware. `parity_check.py` proves the port: the firmware's own functions are extracted from `main.cpp`, compiled, and 1524 cases across three strip widths match pixel for pixel |
| Verification | ✅ `parity_check.py` (2724 frames, rpm filter, brightness; sensitivity proved at every width), `test_settings_parity.py` (63/63 settings), `test_led_engine.py` (43/43), `test_link_protocol.py` (58/58); both APK flavors and both firmwares build |


---

## 5. Phase 2 — settings protocol (Pi ⇄ Nano)

The Nano's UART (`D3`/`D4`, 9600 8N1, line-terminated) currently accepts three commands
(`SEQ:n`, `SEQ?`, `PING`). Extend it, keeping every existing command working.

### 5.1 Pi → Nano

| Command | Example | Notes |
|---|---|---|
| `RAMP:<rpm>:<rrggbb>,…` | `RAMP:0:0000FF,1400:00DCFF,2800:32D782` | 2–6 stops, applied atomically. **The last stop is the full-illumination rpm**, so "fully lit at X rpm" is one number. Replies `OK:RAMP` / `ERR:RAMP` |
| `CFG:<k>=<v>,…` | `CFG:bright=180,theme=1,full=4000` | `bright` 0-255 (also disables the pot), `theme` 0/1 (dark mode = 70 % ramp), `full` 2000-8000, `pot` 0/1, `en` 0/1 (strip off = dark), `mode` 0/1 (gradient / single wash), `shift` 0 or 2000-8000 (0 = no shift light), `hz` 2-15, `scol` rrggbb. Replies `OK:CFG` |
| `CFG:save` | — | Writes the ramp/dim/brightness/full block to EEPROM (magic byte + CRC). Replies `OK:SAVE`. Deliberately explicit so a slider drag cannot wear the EEPROM |
| `CFG?` | — | Replies with the live configuration as one `CFG:seq=…,full=…,dim=…,bright=…,stops=…,ramp=…` line |
| `CFG:reset` | — | Watchdog soft reboot, used to prove a save survives a power cycle. Replies `OK:RESET` first |
| `DEMO:<rpm>` / `DEMO:OFF` | `DEMO:2500` | Bench override: renders that rpm without touching CAN. **Self-clears after 60 s** so a forgotten command cannot leave a fake tacho. Replies `OK:DEMO:<rpm>` / `OK:DEMO_OFF` |
| `SEQ:<1-4>` | `SEQ:2` | Fill pattern, kept from the original protocol |
| `SEQ?` | — | Replies `SEQ:<n>` |
| `PING` | — | Replies `PONG`; used by the Pi as an identity check |

### 5.2 Nano → Pi

| Line | Meaning |
|---|---|
| `PONG` | liveness |
| `OK:CFG` / `ERR:CFG`, `OK:RAMP` / `ERR:RAMP`, `OK:DEMO:<rpm>` | command results |
| `STATUS:CAN=1,RPM=812,SEQ=1,ERR=0,FPS=320,LAST=0x201,FULL=6800,DIM=0` | once a second. `CAN` = controller came up, `ERR` = no data for 3 s, `FPS` = frames in the last second, `LAST` = last arbitration id decoded, `FULL` = full-illumination rpm, `DIM` = dark-mode dimming, plus `EN`/`MODE`/`SHIFT`/`HZ` |

**Done:** the Pi parses these into `led_status` (`/api/telemetry` → `led`), and the app's
`LED STRIP` screen renders them as its diagnostics row.

> **Buffer size matters.** `cmdBuffer` was 32 bytes; a full six-stop `RAMP:` line is ~76
> characters, so it was silently truncated and the firmware accepted a two-stop ramp that
> capped the strip at 1400 rpm while answering `OK`. It is 128 bytes now. Any new command
> must be checked against that limit.

Pi side work:

- `main.py:_init_arduino_serial()` gets a reader thread; store the last `STATUS` in
  `self.led_status`.
- Expose it in `/api/telemetry` and in the `link_service` snapshot as
  `led_ok`, `led_rpm`, `led_version`, so the phone can show strip health.
- Guard the writer with a lock and rate-limit `BRIGHT` (it changes while dragging a slider).

### 5.3 Persistence

- Nano: EEPROM holds the whole config block with a magic byte + CRC (today only `SEQ` is
  stored). Bad CRC → fall back to defaults, don't brick the strip.
- Pi: write `state/led_settings.json` on change and re-apply on boot (fixes S4 generally,
  but LED is the first user).
- App: `SharedPreferences` already holds the UI copy; it re-syncs on connect, so the Pi
  wins if they disagree.

---

## 6. Behavior spec v2

### 6.1 States (in precedence order)

| # | State | Trigger | Pattern (default) |
|---|---|---|---|
| 1 | OFF | app "Enable" off, or ignition off | all pixels off |
| 2 | CAN OFFLINE | `!canInitialized` or no frame > 3 s | two edge pixels, orange, triple-flash 1 Hz |
| 3 | BOOT | power-on | existing startup sweep, then a color-coded "CAN OK/FAIL" pixel |
| 4 | CONFIG ERR | `ERR:CFG` pending | edges blink magenta until the next good `CFG:` |
| 5 | SHIFT | `rpm >= shiftRpm` | whole strip flashes `shiftColor` at `shiftHz` (default 8 Hz) |
| 6 | ENGINE OFF | `rpm == 0` and CAN alive | single blue pixel per the selected sequence |
| 7 | RUNNING | otherwise | ramp fill per sequence + color mode |

### 6.2 Color modes

- `mode=0` **Position** (default, current look): each LED shows its own place on the ramp,
  so the bar runs blue at the bottom to red at the top and the leading edge always shows
  the RPM it represents.
- `mode=1` **RPM** (legacy): the whole lit bar takes the color of the current RPM.
  Kept because it is one line of code and some people prefer a single wash of color.

### 6.3 Default ramp (anchored to the engine, not round numbers)

| RPM | Color | Why |
|---|---|---|
| 800 | `#00B0FF` | idle |
| 1400 | `#00DCFF` | pulling away |
| 2800 | `#32D782` | economical cruise |
| 4500 | `#FFD23C` | waking up |
| 5800 | `#FF8000` | spirited |
| 6800 | `#FF0000` | redline (`RPM_MAX`) |

Same numbers as today, but now editable without reflashing.

---

## 7. Android app: the `LED STRIP` screen

Today `SettingsScreen` exposes exactly one LED control — a 4-way *Sequence* chip row — in
the right-hand column. That is the whole surface. The revamp replaces it with its own
screen, reached from Settings; the Settings page keeps a one-line summary ("LED strip:
Center out · on ›") that opens it. **Both are now built** (see §4.1); what remains is the
device pass in §9.

New `LedScreen extends Screen` with `piScreen() == -1` (phone-only, like the existing
convention), added to the screen list in `MainActivity` next to `new SettingsScreen()`.

### 7.1 Layout (four groups, top to bottom)

| Group | Control | Widget | Range / values | Default |
|---|---|---|---|---|
| **Strip** | Enable | Pill | on/off | on |
| | Brightness | SliderRow | 0–255 (shown as %) | 180 |
| | Fill pattern | Chips | Center out / L→R / R→L / Center in | Center out |
| | Color mode | Chips | Position / RPM | Position |
| **Ramp** | 6 × (RPM + color) | Slider + swatch | 500–7500, 100 rpm steps | see §6.3 |
| | Reset to defaults | Button | — | — |
| **Shift light** | Start RPM | SliderRow | 3000–7500 | 6300 |
| | Flash rate | SliderRow | 2–15 Hz | 8 |
| | Color | Swatch | — | red |
| **Diagnostics** | Status line | Text | `CAN ok · 812 rpm · fw v2` / `no CAN` / `not answering` | — |
| | Run self-test | Button | sends `SELFTEST` | — |
| | Identify strip | Button | sends `IDENTIFY` | — |

### 7.2 Rules

- Color pickers are a compact 8-swatch grid (red/orange/yellow/green/cyan/blue/white/purple),
  not a full HSV wheel — the strip has 8-bit color and a driver has no business with a
  hue wheel at 70 mph.
- **Live preview:** while dragging a ramp RPM slider, push on release only (not per-tick) to
  keep the 9600 baud link from queueing.
- The Pi validates every key and replies 400 on an unknown key, so a stale APK cannot
  silently misconfigure the strip.
- The whole screen is reachable in the **parked** app only. The drive flavor's templated
  screen gets a read-only "LED: on/ok" row at most — no sliders while moving.

### 7.3 Settings keys (Pi ⇄ app contract)

| Key | Type | Default | Nano key |
|---|---|---|---|
| `led_enabled` | 0/1 | 1 | `en` |
| `led_brightness` | 0–255 | 180 | `brt` |
| `led_sequence` | 1–4 | 1 | `seq` |
| `led_color_mode` | 0/1 | 0 | `mode` |
| `led_ramp` | csv `rpm:rrggbb` ×6 | §6.3 | `RAMP:` |
| `led_shift_rpm` | int | 6300 | `shift` |
| `led_shift_hz` | 2–15 | 8 | `hz` |
| `led_shift_color` | rrggbb | `ff0000` | `scol` |

Add each to `link_service.update_setting()` (it currently rejects unknown names with a
400) and to the `Settings` dataclass in `main.py`. Note `led_brightness` is deliberately a
**new** key: `brightness` already means the Pi display, and overloading it would make the
screen and the strip fight.

---

## 8. Phases and order

| Phase | Scope | Depends on | Size | Status |
|---|---|---|---|---|
| 0 | Diagnosis: `nano_debug` build, confirm whether `0x201` is decoded in-car | — | S | ✅ done on the car |
| 1 | Visible failures: watchdog ungate, boot code, heartbeat, `STATUS:` line, pot off | 0 | S | ✅ done on the car |
| 2 | Config protocol + EEPROM block + Pi reader thread + `state/led_settings.json` | 1 | M | ✅ done (`en`/`mode`/`shift`/`hz`/`scol` included) |
| 3 | `LedScreen` in the Android app, keys wired end to end, diagnostics row | 2 | M | ✅ built — needs the device pass |
| 4 | Polish: shift-light overlay, per-sequence animations, `mode=1` legacy ramp | 3 | S | 🟡 shift light and `mode=1` are in; per-sequence animations are not |

Phase 1 alone fixes the reported symptom *as a symptom* — the strip will tell you what it
is doing instead of lying in blue — so it is worth shipping before the rest.

---

## 9. Acceptance criteria

1. With the MCP2515 disconnected the strip shows CAN OFFLINE within 3 s; reconnect it and
   the bar returns without a power cycle.
2. The phone shows `LED strip: no CAN` in the same state (not a green tick).
3. Changing pattern, brightness, ramp, and shift point from the phone changes the strip
   immediately and survives a Nano power cycle and a Pi restart.
4. Shift light starts flashing exactly at the configured RPM and stops on the way down
   without flicker at the boundary.
5. `SELFTEST` proves every pixel works — the one test that separates "code" from "a dead
   LED or a broken data line".
6. The Android app builds and runs with the Pi absent (controls disabled, status shows
   offline) — no hangs.

---

## 10. Test plan

- **Simulator first:** `tools/simulators/led_simulator/` renders the new states —
  `led_engine.py` is a port of the firmware's rendering, `led_simulator_v3.py` drives it with
  an rpm slider, and `parity_check.py` compiles the firmware's own functions and requires
  every pixel of every frame to match (1524 cases, 2724 frames, at three strip widths).
  Keep the port in step with `arduino/src/main.cpp`; `test_settings_parity.py` covers the
  numbers and `parity_check.py` the logic.
- **Unit-ish:** move the ramp/geometry maths into a header that the `native_sim` env can
  compile ([test/test_telemetry.cpp](../test/test_telemetry.cpp) already runs on the host).
  Assert: bar length is monotonic in rpm, color at a stop equals the stop color,
  `shiftRpm > redline` is rejected. *(Partly covered: `parity_check.py` compiles the real
  functions with MSVC and compares them against the port, but nothing yet asserts these
  properties of the compiled firmware in CI.)*
- **Bench:** Nano + a CAN source at 500 kbps feeding `0x201` sweeps; check the strip
  against the simulator frame for the same RPM. The simulator's per-pixel dump is formatted
  for exactly that comparison.
- **Car:** the only test for "feel" — flag as unverified until driven.

---

## 11. Risks

| Risk | Mitigation |
|---|---|
| Writing to the car's HS-CAN from the Nano | It stays `MCP_LISTENONLY`; nothing in this plan transmits |
| Flash size on the ATmega328P (already `-Os`, 20 LEDs, gradient maths) | Config parser and color table must fit; the `native_sim` build catches size regressions early, and if needed the EEPROM-stored ramp is 6 entries, not a table of 20 |
| 9600 baud is slow (~960 B/s) | `CFG:` bursts are rare; `BRIGHT` is rate-limited; `STATUS:` is 1 Hz and TX-only |
| Two writers (phone + ESP32) | The Pi is authoritative and the last write wins; the app re-reads state on focus |
| App and firmware drift | Version byte in `STATUS`; the app disables controls it cannot verify |

---

## 12. Open questions

1. Is the strip physically 20 LEDs, or was it cut/extended? `LED_COUNT` is a build flag.
2. Was a brightness pot ever fitted to `A6`? If yes it needs a pull-up before it can be
   trusted.
3. Should the ESP32's own Settings screen get the LED entries too (it already mirrors
   `led_sequence`), or is the phone the only editor? Recommendation: phone only, ESP32
   read-only.
