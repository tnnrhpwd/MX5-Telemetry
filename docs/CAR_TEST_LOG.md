# MX5 Telemetry - Car Test Log

## Test Session: December 23, 2024

### Hardware Configuration
| Component | Status | Notes |
|-----------|--------|-------|
| Raspberry Pi 4B | Connected | HDMI to head unit |
| ESP32-S3 Display | ✅ Working | Waveshare 1.85" LCD |
| Arduino Nano | ✅ Working | CAN via MCP2515 |
| LED Strip | ✅ Working | RPM display |
| MCP2515 #1 (HS-CAN) | Connected | GPIO8/25, 500kbps |
| MCP2515 #2 (MS-CAN) | Connected | GPIO7/24, 125kbps |

### Vehicle Information
- **Car:** Mazda MX-5 (NC)
- **Head Unit:** Pioneer AVH-W4500NEX (aftermarket)
- **SWC Controller:** PAC (aftermarket)

---

## Test Results

### ✅ PASSED

| Component | Observation |
|-----------|-------------|
| ESP32-S3 Display | Working as expected |
| Arduino Nano | Working as expected |
| LED Strip | Working as expected |
| CAN Read (HS-CAN) | Data received from vehicle |

### ❌ FAILED

| Issue | Severity | Description |
|-------|----------|-------------|
| SWC Controls | **CRITICAL** | Volume controls stopped working for normal infotainment |
| HDMI Video | **HIGH** | No video displayed on Pioneer head unit |
| Tire Slip Warning | **HIGH** | Dashboard warning triggered when car started with circuit connected |
| SWC After Disconnect | **MEDIUM** | SWC still not working after unplugging circuit (may need PAC reprogramming) |

---

## Root Cause Analysis

### SWC & Tire Slip Warning

**Problem:** MCP2515 modules were configured in **NORMAL** mode, which sends ACK signals for every CAN frame received.

**Impact:**
- Adding a device that ACKs on the CAN bus can confuse existing modules
- The PAC SWC controller may have detected unexpected ACKs and entered a fault state
- The tire slip warning is likely from ABS/stability control module seeing unexpected bus activity

**Solution:** Configure MCP2515 modules in **LISTEN-ONLY** mode:
```bash
# Before (WRONG - sends ACKs)
ip link set can0 up type can bitrate 500000

# After (CORRECT - completely passive)
ip link set can0 up type can bitrate 500000 listen-only on
```

### HDMI Not Displaying

**Findings:**
- ✅ Laptop HDMI works with Pioneer AVH-W4500NEX (Dec 24) - head unit HDMI input is functional
- ✅ Pi HDMI works with regular monitor (tested a few days ago) - Pi HDMI output is functional
- ✅ Pi power voltage is good (Dec 24) - not a power issue
- ❌ Pi HDMI does NOT work with Pioneer head unit

**Conclusion:** The issue is **compatibility between Pi and Pioneer**, not a hardware failure or power issue.

**Possible Causes:**
1. Pi not detecting Pioneer's EDID (no hotplug signal from head unit)
2. Pi auto-detecting wrong resolution/timing for Pioneer
3. Boot timing - Pi may output HDMI before Pioneer is ready to receive
4. Pioneer may require specific HDMI-CEC settings

**Diagnostic Steps:**
1. [x] ~~Test Pioneer HDMI input with laptop~~ - ✅ WORKS
2. [x] ~~Test Pi HDMI output with regular monitor~~ - ✅ WORKS (few days ago)
3. [ ] Force Pi HDMI output with `hdmi_force_hotplug=1` (ignore EDID detection)
4. [ ] Try forcing common resolution: `hdmi_mode=4` (720p) or `hdmi_mode=16` (1080p)
5. [ ] Try `hdmi_safe=1` for maximum compatibility
6. [ ] Check if Pioneer has HDMI input resolution requirements

---

## Fixes Applied

### 1. CAN Bus Listen-Only Mode (December 23, 2024)

**File:** `pi/setup_can_bus.sh` and `/usr/local/bin/mx5-can-setup.sh`

**Change:** Added `listen-only on` to both CAN interface configurations:

```bash
#!/bin/bash
sleep 2
ip link set can0 down 2>/dev/null
ip link set can0 up type can bitrate 500000 listen-only on
ip link set can1 down 2>/dev/null
ip link set can1 up type can bitrate 125000 listen-only on
```

**Verified Working:**
```
can0: can <LISTEN-ONLY> state ERROR-ACTIVE
can1: can <LISTEN-ONLY> state ERROR-ACTIVE
```

**Effect:** 
- MCP2515 will NOT send ACK signals
- Completely passive - only receives CAN frames
- Should not interfere with existing vehicle CAN devices (PAC SWC, ABS, etc.)
- May see error frames in candump (expected - no ACK sent by us)

---

## Next Steps

### Immediate Actions
1. [x] **~~Re-run setup script on Pi~~** - ✅ DONE - Listen-only mode applied and verified
   
2. [ ] **Reprogram PAC SWC Controller** - May have entered fault state
   - Follow PAC programming procedure
   - May need to disconnect battery briefly to reset

3. [ ] **Fix Pi↔Pioneer HDMI compatibility**
   - Current config: 800x480 @ 59Hz (custom CVT mode)
   - ✅ Pi works with regular monitor
   - ✅ Laptop works with Pioneer
   - ❌ Pi does NOT work with Pioneer
   - Likely cause: Pi not detecting Pioneer's EDID, or custom resolution incompatible
   - Try adding to `/boot/config.txt`:
     ```
     hdmi_force_hotplug=1
     hdmi_group=1
     hdmi_mode=4  # 720p 60Hz - safe starting point
     ```

### Before Next Car Test
1. [x] Verify listen-only mode is active: ✅ CONFIRMED
   ```
   can0: can <LISTEN-ONLY> state ERROR-ACTIVE
   can1: can <LISTEN-ONLY> state ERROR-ACTIVE
   ```
   ip -details link show can0 | grep "listen-only"
   ```

2. [ ] Test CAN reception still works in listen-only mode:
   ```bash
   candump can0  # Should still see frames (may show error flags)
   ```

3. [ ] Document Pioneer HDMI requirements

---

## Configuration Reference

### Listen-Only Mode Verification
```bash
# Check if listen-only is enabled
ip -details link show can0

# Expected output should include:
# can state ERROR-ACTIVE restart-ms 0
# can <LISTEN-ONLY,LOOPBACK> ...  <-- Look for LISTEN-ONLY flag
```

### CAN Interface Status
```bash
# View interface statistics
ip -s link show can0
ip -s link show can1

# Real-time CAN traffic
candump can0 can1
```

### MCP2515 Module Behavior Comparison

| Mode | Receives | Sends ACK | Sends Data | Safe for Car |
|------|----------|-----------|------------|--------------|
| NORMAL | ✅ | ✅ | ✅ | ⚠️ Risky |
| LISTEN-ONLY | ✅ | ❌ | ❌ | ✅ Safe |
| LOOPBACK | Internal only | N/A | Internal only | ✅ Safe |

---

## Test Log History

| Date | Test | Result | Notes |
|------|------|--------|-------|
| 2024-12-23 | Initial car test | Partial | ESP32/Arduino/LEDs work, SWC/HDMI fail |
| 2024-12-23 | Apply listen-only fix | Pending | Need to re-test in car |
| ~2024-12-20 | Pi HDMI to regular monitor | ✅ Pass | Pi HDMI output works |
| 2024-12-24 | Laptop HDMI to Pioneer | ✅ Pass | Head unit HDMI input works |
| 2024-12-24 | Pi HDMI to Pioneer | ❌ Fail | Pi↔Pioneer compatibility issue |
| 2024-12-24 | Pi power voltage check | ✅ Pass | Voltage is good |

---

## Safety Notes

⚠️ **IMPORTANT:** This system is designed to be **READ-ONLY** on the CAN bus.

- All CAN transmit code has been removed from the codebase
- Listen-only mode prevents ACK signals from interfering with vehicle
- If any dashboard warnings appear, disconnect the system immediately
- The PAC SWC controller may need reprogramming after bus interference
