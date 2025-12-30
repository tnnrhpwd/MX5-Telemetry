# LED Simulator Arduino Connection Troubleshooting

## Issue: Arduino LEDs not lighting up during LED simulation

### Quick Checklist

1. **Is the Arduino connected and showing "🟢 Connected" in simulator?**
   - If NO: Check COM port selection and click "Connect"
   - If YES: Continue to next step

2. **Has the latest firmware been uploaded to Arduino?**
   - The firmware MUST include the LED command handlers
   - Last successful build: BUILD SUCCEEDED (94.1% Flash, 82.9% RAM)
   - Upload with: `C:\Users\tanne\.platformio\penv\Scripts\platformio.exe run --target upload`

3. **Are LEDs wired correctly?**
   - LED Data Pin: D5 (defined in config.h as LED_DATA_PIN)
   - Power: 5V
   - Ground: GND
   - Test with Arduino Actions tool to verify hardware works

4. **Is LED strip enabled in config?**
   - Check `lib/Config/config.h`: `#define ENABLE_LED_STRIP true`
   - Currently: **ENABLED** ✓

5. **Is engine running in simulator?**
   - LEDs won't light until engine is started
   - Click "START ENGINE" button (or press SPACE with clutch+brake held)

### Diagnostic Steps

#### Step 1: Verify Arduino is Running Correct Firmware

Connect to Arduino's serial monitor at 115200 baud and look for:
```
MX5v3
CAN: Disabled
LED: Disabled
GPS: OK
SD: OK (or FAIL)
OK
```

If you see this, firmware is loaded correctly.

#### Step 2: Test LED Strip Hardware

Use the Arduino Actions tool to verify LEDs work:
```powershell
python tools\Arduino_Actions\arduino_actions.py
# Select "Test LED Strip" option
```

If LEDs light up with Arduino Actions but not with simulator, the issue is communication.

#### Step 3: Check Serial Communication

In the simulator console (bottom panel), you should see:
```
✓ Arduino connected on COMx
```

If you see:
```
❌ Arduino connection failed: [error message]
```
This indicates a serial port issue.

#### Step 4: Verify LED Commands Are Being Sent

Add debug logging to verify commands are sent:

1. In simulator, start engine and press throttle
2. Watch the console for any error messages
3. LEDs should update ~20 times per second

#### Step 5: Test Direct LED Command

Open Arduino serial monitor (115200 baud) and manually send:
```
LED:FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000FF0000
```

This should light first few LEDs red. If LEDs light up, the command handler works.

### Common Issues and Solutions

#### Issue: "Connection Lost" immediately after connecting
**Cause:** Arduino serial buffer overflow or incorrect baud rate
**Solution:** 
- Verify Arduino Serial.begin(115200) matches simulator
- Ensure no other programs are using the serial port
- Try unplugging and reconnecting Arduino

#### Issue: LEDs flicker or show wrong colors
**Cause:** Serial data corruption or timing issues
**Solution:**
- Rate limiting is set to 20Hz (50ms between updates)
- Check USB cable quality
- Try reducing update rate in simulator code

#### Issue: Simulator shows connected but no LED updates
**Cause:** LED commands not being processed by Arduino
**Solution:**
1. Verify `cmdHandler.setLEDController(&ledStrip)` is called in main.cpp setup()
2. Check that `ENABLE_LED_STRIP` is true
3. Verify LEDController::handleLED() is implemented in CommandHandler.cpp

#### Issue: Arduino resets when simulator connects
**Cause:** DTR signal triggers Arduino reset
**Solution:**
- Add 10µF capacitor between RESET and GND (blocks auto-reset)
- Or wait 2 seconds after connection before sending commands

### Debug Mode

Enable verbose logging in simulator by modifying `send_leds_to_arduino()`:

```python
def send_leds_to_arduino(self, led_pattern):
    if not self.arduino_connected or not self.arduino_port:
        return
    
    try:
        hex_data = ''.join(f'{r:02X}{g:02X}{b:02X}' for r, g, b in led_pattern)
        command = f"LED:{hex_data}\n"
        
        # DEBUG: Print first command
        if not hasattr(self, '_debug_printed'):
            print(f"DEBUG: Sending LED command: {command[:50]}...")
            self._debug_printed = True
        
        self.arduino_port.write(command.encode('utf-8'))
        self.arduino_port.flush()
    except Exception as e:
        print(f"ERROR sending LED data: {e}")
```

### Hardware Wiring Verification

```
Arduino D5 ──────► LED Strip DIN (Data In)
Arduino 5V ──────► LED Strip 5V
Arduino GND ─────► LED Strip GND

Important:
- Use thick wires for 5V and GND (LED strips draw significant current)
- Add 470Ω resistor between D5 and LED DIN (protects first LED)
- Add 1000µF capacitor across 5V and GND near LED strip (power filtering)
```

### Expected Behavior

When working correctly:
1. Simulator starts, Arduino panel shows "⚪ Not Connected"
2. Select COM port and click "Connect"
3. Status changes to "🟢 Connected"
4. Start engine in simulator
5. **LEDs immediately light up white** (State 0: Idle)
6. Press throttle (Up Arrow)
7. **LEDs change color** based on RPM:
   - White: Idle (speed = 0)
   - Green: 2000-2500 RPM
   - Orange: 750-1999 RPM
   - Yellow: 2501-4500 RPM
   - Red: 4501+ RPM

### Still Not Working?

If you've tried all the above and LEDs still don't work:

1. **Verify LED strip is WS2812B** (not WS2811 or other type)
2. **Check LED strip power** - Arduino 5V pin can only supply ~500mA, may not be enough for 40 LEDs
3. **Test with fewer LEDs** - Try changing LED_COUNT to 10 in config.h and rebuild
4. **Use external power** - Power LED strip separately from Arduino (common ground!)
5. **Check LED strip direction** - Data flows one way, ensure DIN is connected correctly

### Recent Fix Applied

**2025-11-23**: Fixed issue where `current_led_pattern` was not updated when engine was off in simulator. This prevented Arduino from receiving LED commands to turn off all LEDs.

**Change made in `led_simulator_v2.1.py` line ~1439:**
```python
if not self.engine_running:
    # All LEDs off when engine is off - subtle gray with minimal border
    # BUT STILL update the pattern for Arduino sync!
    self.current_led_pattern = [(0, 0, 0)] * LED_COUNT  # <-- ADDED THIS LINE
    
    # ... rest of drawing code ...
    return
```

This ensures the Arduino always receives LED updates even when the simulator engine is off.
