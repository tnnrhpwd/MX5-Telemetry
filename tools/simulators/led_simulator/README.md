# LED strip simulator

![The simulator at 3400 rpm](screenshot.png)

Drag the rpm and watch the bar. Every pixel in that picture is computed by
[`led_engine.py`](led_engine.py), a line-by-line port of the LED rendering in
[`arduino/src/main.cpp`](../../../arduino/src/main.cpp) — the same 20 pixels, the same
ramp table, the same fill geometry, the same truncation.

That matters because the thing you cannot do on a bench with the engine off is judge the
colour ramp: whether a stop is in a sensible place, whether the "full at" scale makes the
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
| **Gradient / Wash** | per-LED gradient vs one wash of colour | `CFG:mode=` |
| **Theme dim** | dark-mode dimming (170/255) | `CFG:theme=` |
| **Full at** | the rpm at which the strip is completely lit | last `RAMP:` stop |
| **Stop colours 1-6** | the ramp itself | `RAMP:` |
| **Shift light** | start rpm, flash rate, colour | `CFG:shift/hz/scol=` |
| **Self test / Identify** | the two bench patterns | `SELFTEST`, `IDENTIFY` |
| **CAN: online / dead** | the CAN-offline pattern (two orange pixels at 1 Hz) | `!canInitialized` |
| **No engine frames** | the error scanner | `displayErrorMode` |
| **RPM smoothing** | the asymmetric filter on incoming rpm | `readCANMessages()` |
| **LEDs** | how many pixels the strip has | `LED_COUNT` build flag |

Keys: `Up`/`Down` ±100 rpm, `PageUp`/`PageDown` ±500, `Home`/`End` for 0 and full,
`Space` sweeps, `S` cycles the fill pattern, `M` toggles the colour mode, `E` the strip,
`T` self test, `I` identify, `Esc` quits.

## Starting from the car's real settings

With the Pi reachable, this loads what the strip is actually configured with — ramp,
brightness, fill pattern, colour mode, shift light — so you are looking at your car rather
than at the defaults:

```bash
python led_simulator_v3.py --pi 192.168.42.100:5000
# with a token if the API requires one
python led_simulator_v3.py --pi 192.168.42.100:5000 --token <token>
# or set MX5_WEB_TOKEN
```

It reads `GET /api/status` once and applies the `led_*` keys. Nothing is written back: this
is a viewer, so it cannot change the car.

## Why the port, and how it is checked

A simulator that merely *looks* like the strip is worse than none, because it produces
confident answers that the hardware then contradicts. So the engine keeps the firmware's
arithmetic exactly — including float32 rounding via a `struct` round trip, because
`(uint8_t)` truncation after a float multiply lands on a different integer when the product
sits near a whole number.

[`test_led_engine.py`](test_led_engine.py) pins it down with values worked out by hand from
the C++ expressions, each test naming the firmware line it came from:

```bash
python tools/simulators/led_simulator/test_led_engine.py     # 43 tests
python tools/simulators/led_simulator/test_led_engine.py --self-check   # dump one frame
```

If you change `arduino/src/main.cpp`, change `led_engine.py` to match and run that. A test
failing is the simulator telling you it has drifted from the firmware, which is exactly the
alarm you want.

## Reading the screen

- **The strip** is the physical order, pixel 0 at the left. The small number under each
  pixel is its *rank* — how far along the fill it sits — which is what the four fill
  patterns actually change.
- **The gradient bar** under it is the ramp itself, with the stop rpms marked and the shift
  point drawn as a dashed line. A stop that never gets reached, or two stops out of order,
  shows up here without touching the rpm at all.
- **What the firmware computes** is the arithmetic behind the current frame: the fill in
  LED units, the fractional tip, the colour at the present rpm, and a per-pixel dump you
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
