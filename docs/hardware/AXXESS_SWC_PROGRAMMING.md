# Axxess SWC Module Programming Guide

## Overview

This guide covers programming the Axxess (Metra) Steering Wheel Control interface module to work with the Pioneer AVH-W4500NEX head unit in a Mazda MX-5 NC.

**Module:** Axxess ASWC-1 (or similar)  
**Head Unit:** Pioneer AVH-W4500NEX  
**Vehicle:** Mazda MX-5 NC (2006-2015)

---

## LED Indicators

| LED State | Meaning |
|-----------|---------|
| **Green Solid** | Ready / Normal operation |
| **Green Blinking** | Programming mode active |
| **Red Solid** | Error / Not recognized |
| **Red Blinking** | Waiting for button press |
| **Both LEDs** | Updating / Processing |

---

## Initial Setup (Auto-Detect)

The ASWC-1 can auto-detect most vehicles. Try this first:

1. **Power off** the head unit
2. **Disconnect** the SWC module from the head unit's remote wire
3. **Reconnect** everything:
   - SWC harness to steering wheel connector
   - Ground wire to chassis ground
   - 12V ACC to switched power
   - Remote wire to head unit's SWC input
4. **Turn ignition ON** (ACC or RUN position)
5. **Wait 30 seconds** - module will attempt auto-detection
6. **Green LED** should illuminate when successful

---

## Manual Programming Mode

If auto-detect fails, program manually:

### Enter Programming Mode

1. **Turn ignition ON** (engine off is fine)
2. **Locate the program button** on the ASWC module (small button on the module housing)
3. **Press and HOLD** the program button for **5+ seconds**
4. **Release** when the **Green LED starts blinking**
5. You are now in Programming Mode

### Program Each Button

The module will cycle through functions. For each function you want to assign:

1. **Wait for Red LED to blink** - module is waiting for a button press
2. **Press the steering wheel button** you want to assign to this function
3. **Green LED will flash** to confirm the button was learned
4. Module advances to next function

### Button Functions (in order)

The ASWC-1 typically programs these functions in sequence:

| # | Function | Description |
|---|----------|-------------|
| 1 | Volume Up | Increase volume |
| 2 | Volume Down | Decrease volume |
| 3 | Seek Up / Next | Next track / Seek forward |
| 4 | Seek Down / Previous | Previous track / Seek back |
| 5 | Source | Change audio source |
| 6 | Mute | Mute/unmute audio |
| 7 | Phone / Bluetooth | Answer/end call |
| 8 | Voice | Activate voice control |

### Skip a Function

If you don't have a button for a function:
- **Press and hold** the program button briefly (1 second)
- Or **wait 10 seconds** - module will timeout and move to next function

### Exit Programming Mode

After programming all buttons:
- **Press and hold** program button for **3 seconds**
- Or **wait for timeout** (module exits after no input for 30 seconds)
- **Green LED goes solid** = programming complete

---

## Pioneer AVH-W4500NEX Specific Setup

### Head Unit Configuration

1. Go to **System Settings** → **Input/Output**
2. Set **Steering Wheel Control** to **Wired Remote** or **Learning**
3. Select **Preset 1** or **Custom**

### Wiring to Head Unit

| ASWC Wire | Pioneer Wire | Color |
|-----------|--------------|-------|
| SWC Output | Wired Remote Input | Varies (check Pioneer harness) |
| Ground | Ground | Black |
| 12V ACC | Accessory 12V | Red |

---

## Troubleshooting

### Red LED Stays On
- Module not detecting steering wheel controls
- Check SWC harness connection to vehicle
- Verify ground connection

### Green LED Never Comes On
- No power to module
- Check 12V ACC and ground connections
- Verify ignition is ON

### Buttons Don't Work After Programming
1. **Re-enter programming mode** and reprogram
2. Check head unit SWC settings
3. Verify remote wire connection to head unit
4. Try different Pioneer SWC preset

### Module Won't Enter Programming Mode
- Hold program button longer (10+ seconds)
- Disconnect and reconnect power
- Try with engine running

---

## Factory Reset

To completely reset the module:

1. **Disconnect** the module from power
2. **Press and hold** the program button
3. **While holding**, reconnect power
4. **Continue holding** for 10 seconds
5. **Release** - both LEDs will flash
6. Module is now reset to factory defaults

---

## After CAN Bus Interference

If the module stopped working after connecting the telemetry system:

1. **Disconnect** the telemetry system from the car
2. **Disconnect** the vehicle battery for 30 seconds
3. **Reconnect** battery
4. **Perform factory reset** on ASWC module (see above)
5. **Reprogram** all buttons
6. **Test** steering wheel controls work
7. **Reconnect** telemetry system (now in listen-only mode)

---

## Quick Reference Card

```
ENTER PROGRAMMING:  Hold program button 5+ sec → Green LED blinks
PROGRAM BUTTON:     Red LED blinks → Press SWC button → Green LED confirms
SKIP FUNCTION:      Press program button briefly OR wait 10 sec
EXIT PROGRAMMING:   Hold program button 3 sec OR wait 30 sec timeout
FACTORY RESET:      Hold button + connect power → hold 10 sec
```

---

## Resources

- [Axxess ASWC-1 Manual (PDF)](https://axxessinterfaces.com/product/ASWC-1)
- [Pioneer AVH-W4500NEX Manual](https://www.pioneerelectronics.com/PUSA/Car/DVD+Receivers/AVH-W4500NEX)
- [Metra SWC Programming Video](https://www.youtube.com/results?search_query=axxess+aswc-1+programming)

---

## Notes

- The MX5-Telemetry system is now in **listen-only mode** and should not interfere with the SWC module
- If issues persist after reprogramming, the ASWC module may need replacement
- Keep this guide in the car for future reference
