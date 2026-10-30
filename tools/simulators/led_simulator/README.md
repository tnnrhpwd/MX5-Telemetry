# LED strip simulator

![The simulator at 3400 rpm](screenshot.png)

Drag the rpm and watch the bar. Every pixel in that picture is computed by
[`led_engine.py`](led_engine.py), a line-by-line port of the LED rendering in
[`arduino/src/main.cpp`](../../../arduino/src/main.cpp) — the same 20 pixels, the same
ramp table, the same fill geometry, the same truncation.

That matters because the thing you cannot do on a bench with the engine off is judge the
color ramp: whether a stop is in a sensible place, whether the "full at" scale makes the
bar feel quick enough, whether the shift point lands where you expect. This is the tool for
that.

```bash
python tools/simulators/led_simulator/led_simulator_v3.py
```

Windows: double-click [`LED_Simulator.bat`](LED_Simulator.bat), or run
[`run_simulator.bat`](run_simulator.bat) if you want the console output.

## What it simulates

| Control | What it does | Firmware equivalent |
|---|---|---|
| **Engine speed** | the rpm the strip is rendering | `currentRPM` |
| **Sweep** | ramps 0 → full → 0 continuously | n/a (bench convenience) |
| **Strip on** | off = the strip goes dark; decoding is unaffected | `CFG:en=` |
| **Brightness** | 0-255, applied the way `show()` applies it | `CFG:bright=` |
| **Fill pattern** | Center out / Left→right / Right→left / Center in | `SEQ:` |
| **Gradient / Wash** | per-LED gradient vs one wash of color | `CFG:mode=` |
| **Theme dim** | dark-mode dimming (170/255) | `CFG:theme=` |
| **Full at** | the rpm at which the strip is completely lit | last `RAMP:` stop |
| **Stop colors 1-6** | the ramp itself | `RAMP:` |
| **Ramp source** | ROYGBIV (firmware default), App scheme (the phone's ramp), or Custom | `RAMP:` |
| **Scheme / Dark-Light** | which of the phone's twelve themes, and which of its two palettes | `Palette.java`, `MainActivity.ledRampFor()` |
| **Shift light** | start rpm, flash rate, color | `CFG:shift/hz/scol=` |
| **Self test / Identify** | the two bench patterns | `SELFTEST`, `IDENTIFY` |
| **CAN: online / dead** | the CAN-offline pattern (two orange pixels at 1 Hz) | `!canInitialized` |
| **No engine frames** | the error scanner | `displayErrorMode` |
| **RPM smoothing** | the asymmetric filter on incoming rpm, actually applied | `readCANMessages()` |
| **LEDs** | how many pixels the strip has | `LED_COUNT` build flag |

Keys: `Up`/`Down` ±100 rpm, `PageUp`/`PageDown` ±500, `Home`/`End` for 0 and full,
`Space` sweeps, `S` cycles the fill pattern, `M` toggles the color mode, `E` the strip,
`T` self test, `I` identify, `Esc` quits.

**RPM smoothing** runs every rendered value through the firmware's own asymmetric filter
(snap at a 250 rpm delta, no lag rising, 0.75 settling falling), so with it on the bar
chases the slider the way it chases the engine. Turn it off to see the strip's raw
response.

## Starting from the car's real settings

With the Pi reachable, this loads what the strip is actually configured with — ramp,
brightness, fill pattern, color mode, shift light — so you are looking at your car rather
than at the defaults:

```bash
python led_simulator_v3.py --pi 192.168.42.100:5000
# with a token if the API requires one
python led_simulator_v3.py --pi 192.168.42.100:5000 --token <token>
# or set MX5_WEB_TOKEN
```

It reads `GET /api/status` once and applies the `led_*` keys. Nothing is written back: this
is a viewer, so it cannot change the car. Because a ramp that came off the car is neither
the firmware default nor a scheme derived here, loading it also switches the **Ramp source**
chips to *Custom*.

## Choosing the ramp: ROYGBIV, the phone's scheme, or your own

Three sources, picked with the chips above the swatches:

| Source | What it is |
|---|---|
| **ROYGBIV** | The firmware's compiled-in table — blue → cyan → green → yellow → orange → red, full at 8000. What the strip uses until something sends `RAMP:`. |
| **App scheme** | The ramp the phone would push for one of its twelve themes (`aurora`, `crimson`, `emerald`, `sakura`, `midnight`, `sunset`, `ocean`, `cyberpunk`, `monokai`, `usa`, `forest`, `neutral`), in that theme's dark or light palette. |
| **Custom** | Anything you build by hand. Editing a stop color or dragging **Full at** switches you here, because the table no longer matches either of the other two. |

An App-scheme ramp is the theme's own two hues blended from the soft, mode-corrected accent
up to the vivid seed, so all twelve themes produce visibly different bars. That is
deliberate: the strip is part of the app, not a separate instrument, and the alarm colors
(`bad` red, `alert` orange, `warn` amber) are kept out of it because they have to mean the
same thing in every scheme. The things that flash — the shift light, the CAN-offline pair,
the error scanner — keep their own fixed colors. Those are the emergency signals; the bar
is decor that also happens to tell you the rpm.

The App-scheme mode exists so the two color worlds can be compared from the driver's seat
rather than in the source: the phone's schemes are a considered palette, and the firmware's
default is a spectrum. Which one reads better at a glance going into a corner is not a thing
you can settle by reading code.

It also makes one consequence of the app visible. The phone has **two** ramp producers that
disagree:

- `MainActivity.ledRampFor()` — used when the theme changes — uses six **fixed** stop rpms:
  0, 1400, 2800, 4500, 5800, 6800.
- `LedScreen.pushRamp()` — the six swatches in the phone's LED screen — spaces them by
  `STOP_FRACTIONS` of the current "Full at".

So picking a different theme on the phone resets the strip's full-illumination rpm to 6800.
The simulator reproduces that rather than papering over it: selecting an App scheme sets
**Full at** to 6800 (the note under the chips says so). Edit anything afterwards and you are
in Custom, where the scale is yours again. The app itself is unchanged; this is a thing to
notice, not a thing this tool fixes.

CLI equivalents, for starting straight in the mode you want to look at:

```bash
python led_simulator_v3.py --scheme sakura          # that theme, dark palette
python led_simulator_v3.py --scheme ocean --light   # same theme, light palette
```

## How "identical" is proved

Reading the firmware and retyping it in Python is how a port drifts: a cast in the wrong
place, a `<` that should be `<=`, a float where the C is an integer. So this is checked two
ways, both mechanically, both able to fail.

### 1. The logic: the firmware's own code is compiled and diffed

```bash
python tools/simulators/led_simulator/parity_check.py --mutate-check
```

`parity_check.py` **extracts the source text** of the rendering functions out of
`arduino/src/main.cpp` — `rampColorAtRpm`, `barRank`, `barSlots`, `renderBar`,
`drawCanOffline`, `drawSelfTest`, `updateErrorAnimation`, `updateLEDs`, and
`readCANMessages` — drops them into a small C++ program with stubs for the Arduino bits, and
compiles it with MSVC. Then it drives both that binary and the port and requires **every
pixel of every frame to match exactly**:

- **1524 cases, 2724 frames**, at **LED counts 5, 20 and 21**. Odd widths matter: at 21 the
  center pixel has no partner, and the firmware's mirrored geometry leaves it dark at full
  rpm — a quirk the port has to reproduce, not fix.
- Every fill pattern, both color modes, dim on and off, five "full at" scales, and **eight
  ramps** including out-of-order and duplicated stops. A descending table makes the later
  stops unreachable (the lookup returns at the first stop at or above the request), and the
  Pi accepts any order, so that is reachable in the car.
- **Runs of frames rather than single frames**, so the time-driven patterns are covered
  frame by frame: the error scanner's 30 ms walk, the shift light's blink across half
  periods, the self-test sweep and identify blink, and the repaint gate holding an
  unchanged bar still.
- The `0x201` decode and the smoothing filter reading-for-reading, and the NeoPixel
  brightness scale value-for-value — that last one checked *and* cross-checked against the
  installed `Adafruit_NeoPixel.cpp`, because the probe is a transcription and a
  transcription is the thing this exercise distrusts.

Because the C++ side is extracted rather than copied, editing the firmware without touching
the port makes it fail.

`--mutate-check` proves the comparison has teeth: it perturbs the port (`DIM_SCALE` by one,
then `_byte` by one) and fails if the frames *don't* diverge. A check that passes because
both sides are inert is worse than no check. Verified: a one-unit change to either is
caught, and nudging `RPM_ALPHA_FALLING` from 0.75 to 0.90 produces
`rpm 2500: C++ 2525, python 2510`.

Missing a compiler? It reports `SKIPPED` and exits 0, so it can sit in a test run on a
Python-only machine. Point `MX5_CL` at a `cl.exe` if MSVC is somewhere unusual.

### 2. The settings: every copy of every number is parsed and compared

```bash
python tools/simulators/led_simulator/test_settings_parity.py
```

**63 settings** are parsed out of the four places that hold a copy and compared: the
firmware's constants and `CFG:` clamps, the Pi's `Settings` defaults and its validation
ranges, the phone's sliders and ramp fractions, and the simulator's own defaults and slider
ranges. The `RAMP:` contract is also *exercised* — the simulator's parser must accept and
reject exactly what the Pi's validator does (2-6 stops, digit rpm, six hex digits; any
order).

It found three real disagreements in the first pass, all now fixed:

| Disagreement | Was | Now |
|---|---|---|
| Simulator shift-light slider | 3000-8000 | **2000-8000**, the firmware's clamp |
| Phone shift-light slider | 3000-7500 | **2000-8000**, the firmware's clamp |
| Phone brightness fallback | 180 (invented) | **255**, the strip's boot value |

A second pass found a further set in how the simulator *handles* a loaded configuration,
all now fixed: an out-of-range "Full at" was clamped to the slider's 2000 floor instead of
being shown; a ramp that arrived with fewer than six stops silently ignored edits to stops
4-6; and the parser accepted a signed rpm the Pi would have rejected.

It is not vacuous: drifting `DIM_SCALE` to 169 makes it exit 1 and name the firmware line.

### 3. The app's palettes: the real `Palette.java` is compiled and diffed

```bash
python tools/simulators/led_simulator/palette_parity.py
```

[`app_palette.py`](app_palette.py) is a port of the phone's `Palette.java`, and a port of a
color derivation is exactly the kind of thing that drifts silently — a blend in the wrong
direction, a lift that stops at the top instead of stopping short of it. So `palette_parity.py` compiles the **real** `Palette.java` against a
small `android.graphics.Color` stub and compares all **12 schemes × 2 modes = 24 ramps**,
stop by stop, channel by channel. The harness calls the app's own `Palette.ramp()`, so the
derivation is exercised rather than transcribed; `MainActivity.ledRampFor()` is separately
checked to still take its colors from there.

Two mismatches in the first run, both real. Java's `Math.round(float)` is
`floor(x + 0.5)`, not Python's round-half-to-even: `152.5` is `153` in the app and was `152`
here. The port now rounds the way the app rounds and the 24 ramps match exactly.

Matching the app is not the same as the ramp following the theme, though: a faithful port of
a ramp built from `good`, `warn`, `bad` and `alert` would pass and still paint four of its
six stops the same color in all twelve schemes — which is what it used to do. So the check
also asserts, mechanically, that:

- each of the twelve schemes produces a **different color at every stop** (per mode), and
- **no stop is one of the fixed alarm colors** — those belong to the things that flash.

Both were confirmed to fail when the old mapping is put back (`stop 2 is 22c55e in 12 dark
schemes — the ramp is not following the theme`).

Requires a JDK (`javac` and `java` on `PATH`). Without one it reports `SKIPPED` and exits
0, like the compiler check above.

### 4. What is deliberately *not* modeled

Nothing here changes a pixel, but claiming "identical" without saying this would be
overclaiming:

| Not simulated | Why |
|---|---|
| The startup animation | A boot sequence, not a state you can select. It has its own issue ([ISSUE-07](../../../docs/KNOWN_ISSUES.md)). |
| The 3 s error debounce (`ERROR_DEBOUNCE_MS`) | "No engine frames" switches the scanner on immediately, because that is what you want on a bench. The firmware waits 3 s first. |
| `DEMO:<rpm>` and its 60 s self-clear | The rpm slider is the override; there is no second one to expire. |
| The brightness pot on `A6` | `ENABLE_BRIGHTNESS` is on and the pin floats on this build, so until the Pi sends `CFG:bright` the real strip's brightness can disagree with any slider. The simulator shows the value the strip is *told*. |
| `CFG:pot=`, `CFG:save`, `CFG:reset`, `CFG?` | The pot switch, EEPROM persistence and the config query. None of them change a pixel; the simulator's settings are the live ones. |
| `showIfChanged()` and the repaint gate | Performance only: they skip work, not pixels. Both are exercised anyway by the multi-frame cases. |
| `LED_COUNT` as a build flag | Defaults to 20; the **LEDs** slider covers 5-60 for a strip that was cut or extended. |

## Reading the screen

- **The strip** is the physical order, pixel 0 at the left. The small number under each
  pixel is its *rank* — how far along the fill it sits — which is what the four fill
  patterns actually change.
- **The gradient bar** under it is the ramp itself, with the stop rpms marked and the shift
  point drawn as a dashed line. A stop that never gets reached, or two stops out of order,
  shows up here without touching the rpm at all.
- **What the firmware computes** is the arithmetic behind the current frame: the fill in
  LED units, the fractional tip, the color at the present rpm, and a per-pixel dump you
  can compare against a real strip read back over serial.

## Legacy versions

`led_simulator.py`, `led_simulator_v2.py` and `led_simulator_v2.1.py` are kept for
reference only and are **superseded**. They simulate a six-state LED program (white pepper
inward, steady green edges, orange stall pulse, yellow bar, red flashing gap, solid red)
that lived in the old `lib/LEDController` architecture and no longer exists in the shipping
firmware. They also drive a gearbox/physics model rather than the current ramp, and they
read `lib/Config/LEDStates.h`, which nothing builds any more.

Use `led_simulator_v3.py`. If you need the physics model back for a different purpose, it is
still there — but do not trust its LED output.

`parse_arduino_led_config.py` and `test_parser.py` belong to that same generation: they read
`lib/Config/LEDStates.h`, which nothing builds. `test_parser.py` looks for it at a path that
no longer exists and so reports `✗ LEDStates.h NOT found` — expected, and unrelated to the
current simulator.
