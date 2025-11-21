# LED Simulator v2.1 - Release Notes

## 🎉 New Features

### 🔊 **Engine Sound Synthesis**
- Real-time engine audio that changes pitch with RPM
- Sawtooth wave synthesis with harmonics for realistic engine tone
- Smooth RPM transitions in audio
- Optional feature (requires `pyaudio` package)
- Audio automatically starts/stops with engine

**Installation for Audio:**
```powershell
.\venv\Scripts\Activate.ps1
pip install pyaudio
```

### ⚠️ **Engine Stalling**
- Engine stalls if RPM drops too low without clutch
- Stall warning system (flashing orange warning)
- Realistic stall behavior when shifting to high gear at low speed
- Must press START ENGINE button to restart after stall
- Stall threshold: 500 RPM (configurable per car)

### 🌊 **Realistic Speed Decay**
- Speed now decreases over time when coasting
- Drag coefficient simulation (air resistance increases with speed)
- Rolling resistance simulation (constant friction)
- Natural deceleration when clutch is engaged
- No more unrealistic constant speed without throttle

### 🚗 **Enhanced Physics**

**Stall Protection System:**
- Monitors RPM vs. speed for current gear
- Warns when approaching stall condition
- Calculates minimum speed needed per gear
- Automatic stall when RPM < 500 (or configured threshold)

**Natural Deceleration:**
- Rolling resistance: ~0.05 km/h per frame
- Drag coefficient: ~0.02 × speed (increases with speed)
- Combined effect creates realistic coast-down
- Higher gears maintain speed better (lower RPM loss)

## 🎮 Usage Changes

### Starting the Engine
1. Click "START ENGINE" button
2. Engine starts at idle (800 RPM for Miata)
3. Audio begins playing (if pyaudio installed)
4. Gear indicator shows "1"

### Avoiding Stalls
- **Use clutch when shifting**: Hold Shift key
- **Downshift at low speed**: Don't stay in 6th gear at 20 km/h
- **Watch the warning**: Orange "RPM TOO LOW" message appears before stall
- **Match speed to gear**: Each gear has minimum speed requirement

### After Stalling
1. Warning message: "⚠️ ENGINE STALLED"
2. Button changes to "⚠️ ENGINE STALLED"
3. Gear shows "N" in red
4. Click button to restart engine
5. Engine returns to idle, ready to drive

## 📊 New Configuration Options

### Car JSON Files

Added to `engine` section:
```json
"stall_rpm": 500
```
- RPM below which engine will stall
- Typically 400-600 for most cars

Added to `physics` section:
```json
"drag_coefficient": 0.02,
"rolling_resistance": 0.05
```
- `drag_coefficient`: Air resistance multiplier (higher = more drag)
- `rolling_resistance`: Base friction loss per frame (km/h)

## 🎵 Audio System Details

### How It Works
1. Separate thread generates audio in real-time
2. Base frequency calculated from RPM: `40 + (RPM/7200) × 200 Hz`
3. Sawtooth wave creates rough engine-like tone
4. Harmonics (2x, 3x base frequency) add richness
5. Noise component adds realistic roughness

### Audio Quality
- 44.1 kHz sample rate
- 32-bit float format
- Low latency (1024 sample buffer)
- Smooth RPM transitions

### Performance
- Audio runs in background thread
- No impact on GUI performance
- Automatically synchronized with RPM
- Clean shutdown on exit

## 🔬 Testing the LED Logic

### Realistic Test Scenarios

**1. Normal Acceleration**
- Start engine
- Hold Up Arrow (gas)
- Watch LEDs progress through colors
- Shift at 6500 RPM when red flashes

**2. Stall Test (High Gear at Low Speed)**
- Accelerate to 40 km/h in 2nd gear
- Shift to 6th gear
- Release throttle
- Watch RPM drop
- Warning appears: "RPM TOO LOW"
- Engine stalls when RPM < 500

**3. Coast Down Test**
- Accelerate to 100 km/h
- Release throttle (no brake)
- Watch speed naturally decay
- Higher speeds decay faster (drag)
- LEDs dim as RPM decreases

**4. Clutch Control Test**
- Start engine
- Hold Shift (clutch)
- Press Up Arrow to rev engine
- RPM increases, speed stays zero
- Release clutch suddenly = RPM drops to match speed

**5. Shift Light Test**
- Accelerate to redline
- Watch LEDs flash red at 6500+ RPM
- Hear pitch increase (if audio enabled)
- Perfect for testing shift light thresholds

## 🐛 Known Limitations

1. **Audio on Windows**: `pyaudio` installation can be tricky on Windows
   - May need Microsoft C++ Build Tools
   - Works fine without audio (simulator displays notice)

2. **Simplified Clutch**: No clutch slip simulation
   - Clutch is either engaged or disengaged
   - Real cars have gradual engagement zone

3. **No Transmission Damage**: Can over-rev without consequence
   - Real life: money-shift destroys engine
   - Simulator: RPM just caps at redline

4. **Instant Gear Changes**: Shifts happen immediately
   - Real life: takes ~0.2 seconds
   - Good enough for LED testing

## 📈 Performance Impact

- **Without Audio**: Negligible (same as v2.0)
- **With Audio**: ~1-2% CPU for audio thread
- **Memory**: +5 MB for audio buffers
- **Frame Rate**: Solid 60 FPS maintained

## 🔄 Backwards Compatibility

- All v2.0 car files work in v2.1
- New physics parameters have defaults if missing
- v2.0 simulator still available (`led_simulator_v2.py`)
- No breaking changes to JSON format

## 🎯 Why These Features?

### Engine Sounds
- **Testing**: Helps identify RPM transitions aurally
- **Immersion**: Makes testing more engaging
- **Debugging**: Hear when RPM calculations are wrong

### Stalling
- **Realism**: Real manual transmissions stall
- **Testing**: Ensures LED logic handles sudden RPM drops
- **Education**: Teaches proper clutch usage

### Speed Decay
- **Accuracy**: Matches real driving physics
- **Testing**: LEDs must respond to natural RPM changes
- **Realism**: No more infinite coasting at constant speed

## 🚀 Future Enhancements (v3.0 Ideas)

- [ ] Clutch slip simulation (gradual engagement)
- [ ] Transmission damage (money-shift detection)
- [ ] Turbo lag simulation (for turbocharged cars)
- [ ] Launch control simulation
- [ ] Data logging (record test sessions)
- [ ] Replay mode (play back recorded sessions)
- [ ] Multiple audio profiles (4-cyl, V6, V8 sounds)
- [ ] Rev limiter simulation (bouncing at redline)
- [ ] Actual audio samples (instead of synthesis)

## 📝 Version History

**v2.1** (Current)
- ✅ Engine sound synthesis
- ✅ Stalling system
- ✅ Realistic speed decay
- ✅ Stall warning system
- ✅ Enhanced physics

**v2.0**
- ✅ Car configuration files
- ✅ Engine start/stop button
- ✅ Car file loading
- ✅ Per-vehicle physics

**v1.0**
- ✅ Basic LED simulation
- ✅ Keyboard controls
- ✅ RPM/speed gauges
- ✅ Hardcoded Miata physics
