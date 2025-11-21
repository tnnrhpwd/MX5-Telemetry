# LED Simulator v2.1 - Quick Test Guide

## 🚀 Quick Start

```powershell
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Run simulator
python tools\LED_Simulator\led_simulator_v2.1.py

# Optional: Install audio support
pip install pyaudio
```

## 🧪 Test Scenarios for LED Logic

### Test 1: Normal Acceleration & Shift Light
**Goal**: Verify LED color progression and shift light activation

1. Click **START ENGINE**
2. Hold **Up Arrow** (gas)
3. **Observe**: LEDs fill from left to right
   - Green at 1000-3000 RPM
   - Yellow at 3000-5000 RPM
   - Orange at 5000-6500 RPM
   - **Red flash at 6500+ RPM** ← SHIFT LIGHT
4. **Listen**: Engine pitch increases with RPM (if audio enabled)
5. Release gas before redline (7200 RPM)

**Expected**: Smooth color gradient, red flash at shift point

---

### Test 2: Engine Stall (High Gear, Low Speed)
**Goal**: Test LED behavior during stall and recovery

1. Start engine
2. Accelerate to ~40 km/h in 2nd gear
3. **Shift to 6th gear** (Right Arrow x4)
4. Release throttle
5. **Watch for warning**: "⚠️ RPM TOO LOW"
6. **Engine stalls**: RPM drops to 0, all LEDs go dark
7. Button shows "⚠️ ENGINE STALLED"
8. Click button to restart
9. Engine returns to idle, LEDs light up at idle RPM

**Expected**: Warning before stall, clean LED shutdown, successful restart

---

### Test 3: Realistic Coast Down
**Goal**: Verify LEDs respond to natural speed decay

1. Start engine
2. Accelerate to 100 km/h in 4th or 5th gear
3. Release throttle (don't brake)
4. **Observe**: 
   - Speed decreases gradually (drag + rolling resistance)
   - RPM decreases proportionally
   - LEDs dim and count decreases
   - No sudden jumps in LED display
5. At ~30 km/h, RPM approaches idle
6. LEDs show minimal or no lighting at idle

**Expected**: Smooth, natural deceleration; LEDs follow RPM smoothly

---

### Test 4: Clutch Control & Rev
**Goal**: Test LED response to RPM independent of speed

1. Start engine (speed = 0)
2. Hold **Shift** (clutch)
3. Hold **Up Arrow** (gas)
4. **Observe**:
   - RPM climbs to redline
   - Speed stays at 0 km/h
   - LEDs fill and flash red
5. Release Up Arrow
6. RPM returns to idle
7. Release Shift (clutch)
8. Nothing changes (speed still 0)

**Expected**: LEDs respond to RPM only when clutch engaged

---

### Test 5: Downshift at High Speed
**Goal**: Test LED behavior during RPM spike

1. Start engine
2. Accelerate to 100 km/h in 6th gear
3. **Downshift to 3rd gear** (Left Arrow x3)
4. **Observe**:
   - RPM jumps from ~3000 to ~6000
   - LEDs instantly fill to near-redline
   - Color jumps to orange/red
   - Shift light may flash briefly
5. Speed naturally decreases
6. RPM settles to match new speed

**Expected**: Instant LED response to RPM spike, accurate color

---

### Test 6: Progressive Gear Changes
**Goal**: Verify LED behavior through all gears

1. Start in 1st gear, idle
2. **Accelerate to 3000 RPM** (LEDs ~1/3 full, yellow)
3. **Shift to 2nd**, keep throttle
4. RPM drops to ~2000, LEDs decrease
5. **Accelerate back to 3000 RPM**
6. **Repeat for gears 3-6**
7. **Observe**: Consistent LED behavior across all gears

**Expected**: LEDs always match RPM regardless of gear

---

### Test 7: Rapid Throttle Changes
**Goal**: Test LED responsiveness to quick RPM changes

1. Start engine in 2nd gear
2. **Tap Up Arrow rapidly** (quick throttle blips)
3. **Observe**:
   - RPM jumps up quickly
   - RPM falls back to idle
   - LEDs respond immediately
   - No lag or stuttering
4. Try at different RPM ranges
5. Try with clutch engaged (RPM should respond faster)

**Expected**: LEDs track RPM with minimal latency (<16ms)

---

### Test 8: Brake vs. Coast Comparison
**Goal**: Compare LED behavior with active braking

1. **Test A - Coast**:
   - Accelerate to 80 km/h in 5th gear
   - Release throttle
   - Note: Slow deceleration (~2 seconds to 60 km/h)

2. **Test B - Brake**:
   - Accelerate to 80 km/h in 5th gear
   - Hold **Down Arrow** (brake)
   - Note: Fast deceleration (~0.5 seconds to 60 km/h)

3. **Compare**:
   - Brake: LEDs drop faster
   - Coast: LEDs drop gradually
   - Both: Smooth transitions

**Expected**: Different deceleration rates, both smooth

---

### Test 9: Stall Recovery Procedure
**Goal**: Test full stall and restart cycle

1. Start engine
2. Deliberately stall (6th gear at low speed)
3. **Verify**:
   - ⚠️ Warning appears
   - Engine stalled message
   - Gear shows "N" in red
   - All LEDs dark
   - Button text changes
4. Click **START ENGINE**
5. **Verify**:
   - Engine returns to idle
   - RPM = 800
   - Gear shows "1" in green
   - LEDs light at idle level
   - Ready to drive

**Expected**: Clean stall detection, clear restart procedure

---

### Test 10: Audio Sync Test (If Audio Enabled)
**Goal**: Verify audio pitch matches RPM

1. Ensure `pyaudio` installed
2. Start engine
3. **Listen**: Low rumble at idle
4. Hold clutch + gas
5. **Rev to 3000 RPM**
   - Audio pitch increases
   - Clear pitch change
6. **Rev to 6000 RPM**
   - Higher pitch
   - More intense sound
7. Release throttle
8. **Listen**: Pitch drops as RPM decreases

**Expected**: Audio pitch correlates with RPM, smooth transitions

---

## 🎯 LED Logic Validation Checklist

Use this checklist to verify your Arduino LED code will work correctly:

- [ ] LEDs off below 1000 RPM
- [ ] Green color at 1000-3000 RPM
- [ ] Yellow color at 3000-5000 RPM
- [ ] Orange color at 5000-6500 RPM
- [ ] Red flash at 6500+ RPM
- [ ] LED count increases linearly with RPM
- [ ] Smooth transitions between colors
- [ ] Instant response to RPM changes (<16ms)
- [ ] All LEDs off when engine stopped
- [ ] Correct behavior during stall
- [ ] No flickering or stuttering

## 📊 Common Issues & Solutions

### Issue: LEDs flicker
**Cause**: Frame rate issues or threshold problems
**Solution**: Check RPM calculation logic, ensure consistent updates

### Issue: Wrong color at specific RPM
**Cause**: Color calculation thresholds incorrect
**Solution**: Verify `get_rpm_color()` function matches your Arduino code

### Issue: LEDs don't fill linearly
**Cause**: LED count calculation error
**Solution**: Check `get_active_led_count()` formula

### Issue: Shift light activates too early/late
**Cause**: Wrong `shift_light_rpm` value
**Solution**: Adjust in car JSON file: `"shift_light_rpm": 6500`

### Issue: Engine stalls too easily
**Cause**: `stall_rpm` too high or gear ratios wrong
**Solution**: Lower `stall_rpm` in car JSON or fix gear ratios

### Issue: Speed doesn't decay realistically
**Cause**: Drag/rolling resistance values incorrect
**Solution**: Adjust in car JSON:
```json
"drag_coefficient": 0.02,
"rolling_resistance": 0.05
```

## 🔧 Advanced Testing

### Custom RPM Thresholds
Edit `tools/cars/2008_miata_nc.json`:
```json
"shift_light_rpm": 6000,  // Earlier shift light
"max_display_rpm": 6500,  // Different LED range
```

### Stall Behavior Tuning
```json
"stall_rpm": 400,  // Harder to stall
"clutch_engagement_rpm": 1000  // Earlier engagement
```

### Physics Tuning
```json
"rpm_accel_rate": 70,  // Faster revs
"rpm_decel_rate": 20,  // Slower RPM drop
"drag_coefficient": 0.03,  // More drag
"rolling_resistance": 0.08  // More friction
```

## 📝 Notes

- All tests assume default Miata NC configuration
- Adjust expectations for different car files
- Audio is optional but recommended for full experience
- Run tests in order for comprehensive validation
- Each test focuses on specific LED logic aspect
