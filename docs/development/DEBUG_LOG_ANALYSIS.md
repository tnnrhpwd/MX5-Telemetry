# Debug Log Analysis

## Log Capture Date: December 21, 2025

### Console Output from Pi Display Navigation Test

```
pi@raspberrypi:~ $ cd ~/MX5-Telemetry/pi/ui/src
pi@raspberrypi:~/MX5-Telemetry/pi/ui/src $ python3 main.py --fullscreen 2>&1 | tee /tmp/perf.log
pygame 1.9.4.post1
Hello from the pygame community. https://www.pygame.org/contribute.html
Warning: python-can not installed. CAN bus disabled.
============================================================
MX5 Telemetry - Raspberry Pi Display
============================================================
Data source can be changed in Settings > Data Source
  CAN BUS = Real vehicle data (default)
  DEMO    = Simulated data for testing
============================================================
Mixer already init: (22050, -16, 2)
Mixer reinitialized: (22050, -16, 2)
Sound effects enabled: 5 sounds, stereo=True, volume=0.7
Loaded car image from: ../../../display/output-onlinepngtools.png
  ✓ Arduino serial connected on /dev/ttyAMA0 (LED sequence control)
Pi: Failed to send LED sequence to Arduino: Write timeout
Data Source: CAN BUS - using real vehicle data
  ✗ CAN library not available - install python-can
  Initializing ESP32 serial...
TPMS: Loaded cached data (age: 0.0 hours)
  Last updates: FL=13:07:31, FR=13:07:31, RL=13:07:31, RR=13:07:31
  Pressures: FL=30.0, FR=28.9, RL=29.2, RR=29.0 PSI
  Temps: FL=18.0, FR=18.0, RL=18.0, RR=17.0 °C
Found ESP32 on USB: /dev/ttyACM0
ESP32 serial opened on /dev/ttyACM0 at 115200 baud
  ✓ ESP32 connected - display sync enabled
ESP32: Queued SCREEN:0 (async)
ESP32: Sent setting brightness=80
ESP32: Sent setting volume=70
ESP32: Sent setting shift_rpm=6500
ESP32: Sent setting redline_rpm=7200
ESP32: Sent setting use_mph=1
ESP32: Sent setting tire_low_psi=28.0
ESP32: Sent setting coolant_warn=220
ESP32: Sent setting demo_mode=0
ESP32: Sent setting led_sequence=1
Pi: Sent initial settings to ESP32
============================================================
MX5 Telemetry - Raspberry Pi Display
============================================================
Resolution: 800x480
Demo Mode: False

Controls:
  Up / W     = Previous screen (RES+)
  Down / S   = Next screen (SET-)
  Right / D  = Increase value (VOL+)
  Left / A   = Decrease value (VOL-)
  Enter      = Select / Edit (ON/OFF)
  Esc / B    = Back / Exit (CANCEL)
  Space      = Toggle sleep mode
  Q          = Quit
============================================================
ESP32: Sent SCREEN:0 (async)
ESP32: Setting confirmed - brightness=80
ESP32: Setting confirmed - volume=70
ESP32: Setting confirmed - shift_rpm=6500
ESP32: Setting confirmed - redline_rpm=7200
ESP32: Setting confirmed - use_mph=1
ESP32: Setting confirmed - tire_low_psi=28.0
ESP32: Setting confirmed - coolant_warn=220
ESP32: Setting confirmed - demo_mode=0
ESP32: Setting confirmed - led_sequence=1
ESP32: CMD: 'SCREEN:0'
ESP32: SCREEN CMD received: 0 (current=0)
ESP32: Screen already at: Overview (0)
DEBUG: _navigate_to_screen called: OVERVIEW -> SETTINGS
Starting transition: OVERVIEW -> SETTINGS
Playing sound: navigate
DEBUG: _sync_esp32_screen_for_transition called with SETTINGS (value=7)
DEBUG: Sending screen change to ESP32: 7
ESP32: Queued SCREEN:7 (async)
DEBUG: _navigate_to_screen completed
ESP32: Sent SCREEN:7 (async)
Transition complete, now on: SETTINGS
ESP32: PERF: Screen=0 (Overview) LoopHz=80 MaxMs=3003
DEBUG: _navigate_to_screen called: SETTINGS -> SYSTEM
Starting transition: SETTINGS -> SYSTEM
Playing sound: navigate
DEBUG: _sync_esp32_screen_for_transition called with SYSTEM (value=6)
DEBUG: Sending screen change to ESP32: 6
ESP32: Queued SCREEN:6 (async)
DEBUG: _navigate_to_screen completed
ESP32: Sent SCREEN:6 (async)
ESP32: CMD: 'SCREEN:6'
ESP32: SCREEN CMD received: 6 (current=0)
ESP32: Screen CHANGED to: System (6)
Transition complete, now on: SYSTEM
ESP32: PERF: Screen=6 (System) LoopHz=158 MaxMs=452
DEBUG: _navigate_to_screen called: SYSTEM -> DIAGNOSTICS
Starting transition: SYSTEM -> DIAGNOSTICS
Playing sound: navigate
DEBUG: _sync_esp32_screen_for_transition called with DIAGNOSTICS (value=5)
DEBUG: Sending screen change to ESP32: 5
ESP32: Queued SCREEN:5 (async)
DEBUG: _navigate_to_screen completed
ESP32: Sent SCREEN:5 (async)
ESP32: CMD: 'SCREEN:5'
ESP32: SCREEN CMD received: 5 (current=6)
ESP32: Screen CHANGED to: Diagnostics (5)
Transition complete, now on: DIAGNOSTICS
ESP32: PERF: Screen=5 (Diagnostics) LoopHz=152 MaxMs=494
DEBUG: _navigate_to_screen called: DIAGNOSTICS -> GFORCE
Starting transition: DIAGNOSTICS -> GFORCE
Playing sound: navigate
DEBUG: _sync_esp32_screen_for_transition called with GFORCE (value=4)
DEBUG: Sending screen change to ESP32: 4
ESP32: Queued SCREEN:4 (async)
DEBUG: _navigate_to_screen completed
ESP32: Sent SCREEN:4 (async)
ESP32: CMD: 'SCREEN:4'
ESP32: SCREEN CMD received: 4 (current=5)
ESP32: Screen CHANGED to: G-Force (4)
Transition complete, now on: GFORCE
ESP32: PERF: Screen=4 (G-Force) LoopHz=148 MaxMs=406
ESP32: PERF: Screen=4 (G-Force) LoopHz=7 MaxMs=224
ESP32: PERF: Screen=4 (G-Force) LoopHz=8 MaxMs=222
ESP32: PERF: Screen=4 (G-Force) LoopHz=5 MaxMs=225
ESP32: PERF: Screen=4 (G-Force) LoopHz=5 MaxMs=221
ESP32: PERF: Screen=4 (G-Force) LoopHz=5 MaxMs=224
ESP32: PERF: Screen=4 (G-Force) LoopHz=5 MaxMs=222
ESP32: PERF: Screen=4 (G-Force) LoopHz=5 MaxMs=230
ESP32: PERF: Screen=4 (G-Force) LoopHz=5 MaxMs=226
ESP32: PERF: Screen=4 (G-Force) LoopHz=5 MaxMs=223
DEBUG: _navigate_to_screen called: GFORCE -> ENGINE
Starting transition: GFORCE -> ENGINE
Playing sound: navigate
DEBUG: _sync_esp32_screen_for_transition called with ENGINE (value=3)
DEBUG: Sending screen change to ESP32: 3
ESP32: Queued SCREEN:3 (async)
DEBUG: _navigate_to_screen completed
ESP32: Sent SCREEN:3 (async)
ESP32: CMD: 'SCREEN:3'
ESP32: SCREEN CMD received: 3 (current=4)
ESP32: Screen CHANGED to: Engine (3)
ESP32: PERF: Screen=3 (Engine) LoopHz=5 MaxMs=222
Transition complete, now on: ENGINE
ESP32: PERF: Screen=3 (Engine) LoopHz=176 MaxMs=238
DEBUG: _navigate_to_screen called: ENGINE -> TPMS
Starting transition: ENGINE -> TPMS
Playing sound: navigate
DEBUG: _sync_esp32_screen_for_transition called with TPMS (value=2)
DEBUG: Sending screen change to ESP32: 2
ESP32: Queued SCREEN:2 (async)
DEBUG: _navigate_to_screen completed
ESP32: Sent SCREEN:2 (async)
ESP32: CMD: 'SCREEN:2'
ESP32: SCREEN CMD received: 2 (current=3)
ESP32: Screen CHANGED to: TPMS (2)
Transition complete, now on: TPMS
ESP32: PERF: Screen=2 (TPMS) LoopHz=34 MaxMs=3506
DEBUG: _navigate_to_screen called: TPMS -> RPM_SPEED
Starting transition: TPMS -> RPM_SPEED
Playing sound: navigate
DEBUG: _sync_esp32_screen_for_transition called with RPM_SPEED (value=1)
DEBUG: Sending screen change to ESP32: 1
ESP32: Queued SCREEN:1 (async)
DEBUG: _navigate_to_screen completed
ESP32: Sent SCREEN:1 (async)
ESP32: PERF: Screen=2 (TPMS) LoopHz=67 MaxMs=3000
Transition complete, now on: RPM_SPEED
ESP32: PERF: Screen=2 (TPMS) LoopHz=80 MaxMs=3000
ESP32: PERF: Screen=2 (TPMS) LoopHz=80 MaxMs=3000
DEBUG: _navigate_to_screen called: RPM_SPEED -> OVERVIEW
Starting transition: RPM_SPEED -> OVERVIEW
Playing sound: navigate
DEBUG: _sync_esp32_screen_for_transition called with OVERVIEW (value=0)
DEBUG: Sending screen change to ESP32: 0
ESP32: Queued SCREEN:0 (async)
DEBUG: _navigate_to_screen completed
ESP32: Sent SCREEN:0 (async)
ESP32: CMD: 'SCREEN:0'
ESP32: SCREEN CMD received: 0 (current=2)
ESP32: Screen CHANGED to: Overview (0)
Transition complete, now on: OVERVIEW
DEBUG: _navigate_to_screen called: OVERVIEW -> RPM_SPEED
Starting transition: OVERVIEW -> RPM_SPEED
Playing sound: navigate
DEBUG: _sync_esp32_screen_for_transition called with RPM_SPEED (value=1)
DEBUG: Sending screen change to ESP32: 1
ESP32: Queued SCREEN:1 (async)
DEBUG: _navigate_to_screen completed
ESP32: Sent SCREEN:1 (async)
Transition complete, now on: RPM_SPEED
ESP32: PERF: Screen=0 (Overview) LoopHz=44 MaxMs=3000

```

---

## Analysis & Issues Identified

### 1. 🔴 CRITICAL: G-Force Screen Drops to 5 Hz

**Observation:**
```
ESP32: PERF: Screen=4 (G-Force) LoopHz=148 MaxMs=406   <- Initial draw
ESP32: PERF: Screen=4 (G-Force) LoopHz=7 MaxMs=224    <- Steady state
ESP32: PERF: Screen=4 (G-Force) LoopHz=5 MaxMs=224
ESP32: PERF: Screen=4 (G-Force) LoopHz=5 MaxMs=225
```

**Issue:** G-Force screen runs at only **5 Hz** after initial draw, with ~220ms per loop iteration.

**Impact:** Ball movement will be extremely choppy (5 FPS instead of target 60 FPS).

**Root Cause:** The `drawGForceScreen()` function is doing a full screen redraw every frame, including:
- Background fill
- All ring graphics
- Text labels
- Ball rendering

**Fix Required:** Implement partial redraw - only redraw the ball area, not the entire screen.

---

### 2. 🔴 CRITICAL: TPMS/Overview Screens Block for 3+ Seconds

**Observation:**
```
ESP32: PERF: Screen=2 (TPMS) LoopHz=34 MaxMs=3506     <- 3.5 second block!
ESP32: PERF: Screen=2 (TPMS) LoopHz=67 MaxMs=3000
ESP32: PERF: Screen=0 (Overview) LoopHz=80 MaxMs=3003
ESP32: PERF: Screen=0 (Overview) LoopHz=44 MaxMs=3000
```

**Issue:** Both TPMS and Overview screens have **3+ second blocking operations**.

**Impact:** 
- UI freezes for 3 seconds periodically
- Touch input unresponsive during block
- Screen transitions delayed

**Root Cause:** BLE TPMS scanning is blocking the main loop. The `BLEDevice::getScan()` operations are synchronous.

**Fix Required:** 
- Make BLE scanning asynchronous (non-blocking)
- Or reduce scan duration
- Or only scan when explicitly requested

---

### 3. ⚠️ Screen Sync Lag / Desynchronization

**Observation:**
```
ESP32: SCREEN CMD received: 0 (current=2)
ESP32: PERF: Screen=2 (TPMS) LoopHz=80 MaxMs=3000  <- Still reporting TPMS after CMD
```

**Pattern:** ESP32 receives screen change command but still reports old screen in PERF output.

**Impact:** Visual desync between Pi and ESP32 displays during navigation.

**Recommendation:** Process screen commands immediately, not just at loop start.

---

### 4. ⚠️ Arduino Write Timeout

**Issue:**
```
Pi: Failed to send LED sequence to Arduino: Write timeout
```

**Impact:** LED sequence changes may be missed on startup.

**Recommendation:** Add retry logic for LED commands.

---

### 5. ✅ Fast Screens Working Well

**Good Performance:**
```
ESP32: PERF: Screen=3 (Engine) LoopHz=176 MaxMs=238      <- Good!
ESP32: PERF: Screen=6 (System) LoopHz=158 MaxMs=452     <- Acceptable
ESP32: PERF: Screen=5 (Diagnostics) LoopHz=152 MaxMs=494 <- Acceptable
```

These screens don't have BLE or continuous redraw, so they perform well.

---

## Performance Summary Table

| Screen | LoopHz | MaxMs | Status | Issue |
|--------|--------|-------|--------|-------|
| Overview (0) | 44-80 | 3000-3003 | 🔴 BAD | BLE blocking |
| RPM/Speed (1) | - | - | ❓ | Not measured |
| TPMS (2) | 34-80 | 3000-3506 | 🔴 BAD | BLE blocking |
| Engine (3) | 176 | 238 | ✅ GOOD | - |
| G-Force (4) | 5-8 | 220-225 | 🔴 BAD | Full redraw every frame |
| Diagnostics (5) | 152 | 494 | ✅ OK | - |
| System (6) | 158 | 452 | ✅ OK | - |
| Settings (7) | - | - | ❓ | Not measured |

---

## Recommended Fixes (Priority Order)

### Priority 1: Fix G-Force Partial Redraw
The G-Force screen should only redraw the ball, not the entire screen.

**Current:** Full screen redraw at 5 Hz = choppy ball
**Target:** Partial ball redraw at 60 Hz = smooth ball

**Implementation:**
1. Draw background/rings once on screen entry
2. Only clear and redraw ball area each frame
3. Use sprite or dirty-rectangle technique

### Priority 2: Make BLE Scanning Non-Blocking
BLE scans are blocking for 3 seconds, freezing the entire UI.

**Options:**
1. Use async BLE scanning (FreeRTOS task)
2. Reduce scan window to 100-200ms
3. Only scan when user is on TPMS screen AND requests refresh
4. Cache TPMS data and only scan every 30 seconds

### Priority 3: Screen Change Immediate Processing
Process SCREEN commands immediately when received, not at loop boundary.

---

## Test Commands

### Monitor PERF output:
```bash
# On Pi
python3 main.py --fullscreen 2>&1 | grep PERF
```

### Direct ESP32 serial monitor:
```bash
sudo systemctl stop mx5-display
cat /dev/ttyACM0 | grep PERF
```

---

## Related Files

- ESP32 firmware: `display/src/main.cpp`
  - `drawGForceScreen()` - needs partial redraw optimization
  - BLE scanning code - needs async implementation
- Pi serial handler: `pi/ui/src/esp32_serial_handler.py`
- Pi main: `pi/ui/src/main.py`
