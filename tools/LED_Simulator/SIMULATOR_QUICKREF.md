# LED Simulator Quick Reference

```
┌─────────────────────────────────────────────────────────────┐
│          MX5-TELEMETRY LED SIMULATOR                        │
│          Interactive LED Testing Tool                       │
└─────────────────────────────────────────────────────────────┘

LAUNCH
======
Windows:   tools\run_simulator.bat
All:       python tools/LED_Simulator/led_simulator_v2.1.py


KEYBOARD CONTROLS
=================
┌──────────────┬──────────────────────────────────────┐
│ Key          │ Action                               │
├──────────────┼──────────────────────────────────────┤
│ ↑ Up Arrow   │ Gas Pedal (increase RPM)             │
│ ↓ Down Arrow │ Brake (decrease RPM)                 │
│ → Right      │ Shift Up (1st → 6th gear)            │
│ ← Left       │ Shift Down (6th → 1st gear)          │
│ Shift Key    │ Clutch (hold while shifting/revving) │
│ ESC          │ Quit (with confirmation)             │
└──────────────┴──────────────────────────────────────┘


LED COLOR GUIDE
===============
RPM Range     Color          LED Behavior
─────────────────────────────────────────
0 - 1000      Off            No LEDs lit
1000 - 3000   Green          Low RPM range
3000 - 5000   Yellow         Mid RPM range
5000 - 6500   Orange         High RPM range
6500+         Red Flash      SHIFT! indicator


DISPLAY ELEMENTS
================
┌─────────────────────────────────────────────┐
│  RPM Gauge    │  Speed Gauge                │
│  (0-7200)     │  (0-200 km/h)               │
│               │                             │
│         GEAR INDICATOR                      │
│         (1-6, Yellow when clutch pressed)   │
│                                             │
│  LED STRIP VISUALIZATION                    │
│  [30 individual LEDs numbered 1-30]         │
│                                             │
│  Status: Shows active inputs               │
│  ⚡THROTTLE | 🔴BRAKE | ⚙️CLUTCH | 🔺SHIFT  │
└─────────────────────────────────────────────┘


REALISTIC DRIVING
=================
Starting from stop:
  1. Hold Shift (clutch)
  2. Press Up Arrow (gas) to rev
  3. Release Shift (clutch out)
  4. Continue Up Arrow to accelerate

Shifting up:
  1. Hold Shift (clutch in)
  2. Press Right Arrow (shift up)
  3. Release Shift (clutch out)
  4. Continue accelerating

Downshifting:
  1. Hold Shift (clutch in)
  2. Press Left Arrow (shift down)
  3. Tap Up Arrow (rev match)
  4. Release Shift (clutch out)

Test shift light:
  1. Stay in 1st gear
  2. Hold Shift (clutch)
  3. Hold Up Arrow to redline
  4. Watch LED flash red at 6500 RPM


CONFIGURATION
=============
File: tools/LED_Simulator/led_simulator_v2.1.py

Key Settings (match with config.h):
  LED_COUNT = 30
  RPM_IDLE = 800
  RPM_MIN_DISPLAY = 1000
  RPM_MAX_DISPLAY = 7000
  RPM_SHIFT_LIGHT = 6500
  RPM_REDLINE = 7200


CUSTOMIZING LED COLORS
======================
Edit function in led_simulator.py:

  def get_rpm_color(rpm):
      """Calculate LED color based on RPM."""
      # Your custom color logic here
      # Return (R, G, B) tuple (0-255 each)

Test changes:
  1. Edit led_simulator.py
  2. Run simulator
  3. Test LED behavior
  4. Apply to LEDController.cpp when satisfied


PHYSICS SIMULATION
==================
Gear Ratios (MX-5 NC 6-speed):
  1st: 3.760    4th: 1.187
  2nd: 2.269    5th: 1.000
  3rd: 1.645    6th: 0.843
  
Final Drive: 4.100:1
Tire Size: 205/45R17


TIPS
====
• Click window to ensure keyboard focus
• Use realistic shifting with clutch
• Test all RPM ranges (1000-7200)
• Try all 6 gears for different characteristics
• Rev in neutral (clutch + gas) to test colors
• Watch for smooth color transitions


TROUBLESHOOTING
===============
Python not found:
  Install from python.org
  Check "Add to PATH" during install

Window not responding:
  Click on window for keyboard focus

Colors not matching Arduino:
  Verify LED_COUNT and RPM values match config.h
  Check get_rpm_color() logic


FILE LOCATIONS
==============
Simulator:     tools/LED_Simulator/led_simulator_v2.1.py
Launcher:      tools/run_simulator.bat
Arduino LED:   lib/LEDController/LEDController.cpp
Config:        lib/Config/config.h
Documentation: tools/README.md


┌─────────────────────────────────────────────────────────────┐
│  MX5-Telemetry Project                                      │
│  github.com/tnnrhpwd/MX5-Telemetry                          │
└─────────────────────────────────────────────────────────────┘
```
