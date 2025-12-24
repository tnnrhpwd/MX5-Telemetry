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

**Possible Causes:**
1. Pi HDMI resolution not compatible with Pioneer head unit
2. Pioneer requires specific HDMI-CEC or EDID settings
3. Boot timing issue - Pi may boot faster than head unit

**Diagnostic Steps:**
1. [ ] Test Pi HDMI output with regular monitor/TV
2. [ ] Check Pi `/boot/config.txt` for HDMI settings
3. [ ] Try forcing HDMI resolution: `hdmi_mode=16` (1080p) or `hdmi_mode=4` (720p)
4. [ ] Check if Pioneer has HDMI input settings

---

## Fixes Applied

### 1. CAN Bus Listen-Only Mode (December 23, 2024)

**File:** `pi/setup_can_bus.sh`

**Change:** Added `listen-only on` to both CAN interface configurations:

```bash
# HS-CAN (500kbps)
ip link set can0 up type can bitrate 500000 listen-only on

# MS-CAN (125kbps)  
ip link set can1 up type can bitrate 125000 listen-only on
```

**Effect:** 
- MCP2515 will NOT send ACK signals
- Completely passive - only receives CAN frames
- Should not interfere with existing vehicle CAN devices
- May see error frames in candump (expected - no ACK sent)

---

## Next Steps

### Immediate Actions
1. [ ] **Re-run setup script on Pi** - Apply listen-only mode fix
   ```bash
   ssh pi@192.168.1.28 'cd ~/MX5-Telemetry && git pull && sudo bash pi/setup_can_bus.sh'
   sudo reboot
   ```

2. [ ] **Reprogram PAC SWC Controller** - May have entered fault state
   - Follow PAC programming procedure
   - May need to disconnect battery briefly to reset

3. [ ] **Test HDMI separately** - Connect Pi to regular monitor first
   ```bash
   ssh pi@192.168.1.28 'tvservice -s'  # Check current HDMI status
   ```

### Before Next Car Test
1. [ ] Verify listen-only mode is active:
   ```bash
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

---

## Safety Notes

⚠️ **IMPORTANT:** This system is designed to be **READ-ONLY** on the CAN bus.

- All CAN transmit code has been removed from the codebase
- Listen-only mode prevents ACK signals from interfering with vehicle
- If any dashboard warnings appear, disconnect the system immediately
- The PAC SWC controller may need reprogramming after bus interference
