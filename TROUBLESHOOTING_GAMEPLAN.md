# MX5 Telemetry System - Troubleshooting Game Plan

**Updated:** December 31, 2024  
**System:** MX5 + Raspberry Pi 4B + ESP32-S3 1.85" + Pioneer AVH-W4500NEX + 2x MCP2515

---

## 🎯 Current Issues & Feature Requests

| Priority | Status | Item | Impact | Estimated Time |
|----------|--------|------|--------|----------------|
| **HIGH** | 🔴 **OPEN** | Pi4B HDMI not outputting to AVH head unit | No dashboard display on Pioneer | 2-4 hours |
| **MEDIUM** | 🟡 **NEW** | Add headlight indicators to overview screens | Enhanced driver awareness | 1-2 hours |

### ✅ System Status
- ✅ Both MCP2515 modules operational (listen-only mode)
- ✅ ESP32-S3 serial connection stable
- ✅ CAN bus wiring verified and tested

---

## 📋 Issue #1: Pi4B HDMI Not Outputting to AVH-W4500NEX

### Symptoms
- Pi4B powers on but Pioneer head unit shows no signal on HDMI input
- May work briefly then lose signal, or never establish connection

### Root Cause Analysis

The Pi → Pioneer HDMI connection is notoriously difficult due to:
1. **EDID handshake issues** - Pioneer may not properly report capabilities
2. **Resolution mismatch** - Pi defaults to 1080p, Pioneer expects 720p
3. **Hotplug detection** - Pi may not detect Pioneer on boot
4. **CEC conflicts** - Consumer electronics control can interfere
5. **Power timing** - Pi boots before Pioneer is ready

### Testing Procedure

#### Step 1: Verify Basic HDMI Functionality
```bash
# SSH into Pi (home network or hotspot)
ssh pi@192.168.1.23  # home network
ssh pi@10.62.26.67   # phone hotspot

# Check if HDMI is detected
tvservice -s
# Should show: "state 0x120009 [HDMI CEA (4) RGB lim 16:9], 1280x720 @ 60.00Hz, progressive"

# Check current display settings
vcgencmd get_config int | grep hdmi
```

**Expected output:**
```
hdmi_group=1
hdmi_mode=4
hdmi_drive=2
```

#### Step 2: Check Boot Config
```bash
cat /boot/config.txt | grep -A5 "HDMI"
```

**Required settings for Pioneer AVH-W4500NEX:**
```ini
# Force HDMI even if not detected
hdmi_force_hotplug=1

# Force 720p (CEA mode 4)
hdmi_group=1
hdmi_mode=4

# Force HDMI audio (not DVI)
hdmi_drive=2

# Disable overscan
disable_overscan=1

# Use compatibility mode for older displays
dtoverlay=vc4-fkms-v3d,audio=on
```

#### Step 3: Test HDMI Output Live
```bash
# Run the diagnostic script
cd ~/MX5-Telemetry/tools
python3 hdmi_diag.py

# If diagnostic shows issues, try force config
python3 fix_hdmi1_config.py
```

#### Step 4: Manual HDMI Force (if scripts fail)
```bash
# Backup current config
sudo cp /boot/config.txt /boot/config.txt.backup

# Edit config
sudo nano /boot/config.txt
```

**Add/modify these lines:**
```ini
# Force HDMI for Pioneer AVH-W4500NEX
hdmi_force_hotplug=1
hdmi_ignore_edid=0xa5000080
hdmi_group=1
hdmi_mode=4
hdmi_drive=2
disable_overscan=1
dtoverlay=vc4-fkms-v3d,audio=on

# Optional: Force to HDMI 0 (closest to power)
hdmi_force_port=0
```

**Reboot:**
```bash
sudo reboot
```

#### Step 5: Verify After Reboot
```bash
ssh pi@192.168.1.23
tvservice -s
```

### Solutions (in order of likelihood)

#### Solution A: Add EDID Override ⭐ Most Common
```bash
sudo nano /boot/config.txt
```
Add:
```ini
hdmi_ignore_edid=0xa5000080  # Forces 720p CEA mode
hdmi_force_hotplug=1
```

#### Solution B: Force Specific Timing
```bash
sudo nano /boot/config.txt
```
Replace mode with custom timing:
```ini
# Remove hdmi_mode=4, add:
hdmi_timings=1280 0 110 40 220 720 0 5 5 20 0 0 0 60 0 74250000 1
```

#### Solution C: Disable CEC (if interference suspected)
```bash
sudo nano /boot/config.txt
```
Add:
```ini
hdmi_ignore_cec=1
hdmi_ignore_cec_init=1
```

#### Solution D: Use Legacy Framebuffer (last resort)
```bash
cd ~/MX5-Telemetry/tools
python3 use_legacy_framebuffer.py
sudo reboot
```

### Testing Tools Available
Your repo already has these tools (use them!):
- `tools/hdmi_diag.py` - Full diagnostic
- `tools/fix_hdmi1_config.py` - Auto-fix config
- `tools/check_hdmi.py` - Quick status check
- `tools/deep_hdmi_diag.py` - Detailed analysis
- `tools/fix_hdmi_signal_loss.py` - Signal stability fix
- `tools/force_hdmi_active.py` - Force active output

### Hardware Checks
- [ ] Try different HDMI cable (not all cables support ARC/CEC)
- [ ] Verify using HDMI 0 port (closest to USB-C power) on Pi
- [ ] Check Pioneer input source is set to "HDMI"
- [ ] Verify Pi has adequate power (5V 3A minimum)
- [ ] Test with another display to confirm Pi HDMI works

### Success Criteria
- ✅ `tvservice -s` shows 720p @ 60Hz
- ✅ Pioneer displays Pi output on HDMI input
- ✅ Signal remains stable (no dropout after 10 minutes)
- ✅ Pi display starts automatically on boot

---

## 🎨 Feature Request: Headlight Indicators on Overview Screens

### Description
Add visual indicators to the overview screens showing headlight status:
- **Headlight ON indicator** (low beams active)
- **Bright/High beam indicator** (high beams active)

### Use Case
- Provide driver awareness of headlight status at a glance
- Helpful for confirming automatic headlight operation
- Useful during day/night transitions

### Implementation Notes

**CAN Bus Data Source:**
- HS-CAN (can0) typically carries lighting status
- Common CAN IDs for headlights (need to monitor car to identify):
  - Headlight status: Often in 0x420-0x430 range
  - High beam status: Often in body control module messages
  - Mazda-specific IDs to be determined

**UI Design:**
- Add icons to ESP32-S3 overview screen
- Icon suggestions: 💡 for headlights, ⚡ or ☀️ for high beams
- Use color coding: Green=ON, Gray/Dim=OFF
- Position: Top corner alongside existing indicators

**Implementation Steps:**
1. **Monitor car CAN bus** to identify headlight status CAN IDs
   ```bash
   # With car on, toggle headlights and capture CAN data
   candump -L can0 > headlights_off.log
   # Turn on headlights
   candump -L can0 > headlights_on.log
   # Compare logs to find changed CAN IDs
   ```

2. **Add headlight state tracking** to `can_handler.py`
   - Parse identified CAN IDs
   - Track low beam state
   - Track high beam state

3. **Update displays**
   - ESP32-S3: Add icons to overview screen
   - Pi UI: Add indicators to dashboard

4. **Test with car**
   - Verify off state
   - Verify low beams
   - Verify high beams
   - Verify real-time updates

**Files to Modify:**
- `pi/ui/src/can_handler.py` - Add headlight state parsing
- `pi/ui/src/main.py` - Display headlight indicators
- `display/src/main.cpp` - ESP32 display updates
- `display/ui/` - Screen layouts

**Priority:** After HDMI fix is complete

---

## 🛠️ General Troubleshooting Tools

### Remote Access
```bash
# SSH into Pi
ssh pi@192.168.1.23

# View system logs
journalctl -u mx5-display -f

# View CAN traffic
candump can0
candump can1

# Monitor serial traffic
cat /dev/ttyACM0
```

### Quick Health Checks

**USB Issues:**
- Check ESP32 connection: `ls -la /dev/ttyACM0`
- Verify ESP32 device ID: `lsusb | grep 303a`
- Test serial: `python3 tools/test_esp32_sync.py`

**CAN Bus Issues:**
- Verify interfaces: `ip link show can0 can1`
- Check dmesg: `dmesg | grep mcp251`
- Test loopback: `python3 tools/test_mcp2515_loopback_active.py`
- Verify listen-only: `python3 tools/verify_listen_only.py`

**HDMI Issues:**
- Check status: `tvservice -s`
- Run diagnostic: `python3 tools/hdmi_diag.py`
- Auto-fix: `python3 tools/fix_hdmi1_config.py`

### Available Scripts in Your Repo
Located in `tools/`:
- **HDMI Diagnostics:** `hdmi_diag.py`, `deep_hdmi_diag.py`
- **HDMI Fixes:** `fix_hdmi1_config.py`, `force_hdmi_active.py`
- **CAN Testing:** `test_mcp2515_loopback_active.py`, `verify_listen_only.py`
- **ESP32 Testing:** `test_esp32_sync.py`

### VS Code Tasks
Use `Ctrl+Shift+P` → "Tasks: Run Task":
- **Pi: View Display Logs** - Monitor Pi app in real-time
- **Pi: SSH Connect** - Quick SSH session
- **Pi: Flash ESP32 (Remote)** - Update ESP32 firmware
- **Pi: Git Pull & Restart UI** - Deploy updates

### Emergency Recovery
```bash
# Reboot Pi
ssh pi@192.168.1.23 'sudo reboot'

# Or use tool
cd ~/MX5-Telemetry/tools
python3 reboot_pi.py

# Factory reset config (if all else fails)
python3 emergency_recovery.py
```

---

## 📝 Troubleshooting Status & Next Steps

### ✅ Completed Sessions

#### Session 1: CAN Bus Fix ✅ COMPLETED (Dec 31, 2024)
1. ✅ Fixed H/L wiring on both MCP2515 modules
2. ✅ Verified with loopback test (100% success rate)
3. ✅ Configured listen-only mode for production
4. ✅ Both can0 and can1 operational
5. ✅ Ready for car CAN bus connection

#### Session 2: USB-C Fix ✅ COMPLETED (Dec 31, 2024)
1. ✅ Replaced faulty USB-C cable
2. ✅ ESP32 detected reliably as /dev/ttyACM0
3. ✅ Serial communication stable
4. ✅ Tested with test_esp32_sync.py
5. ✅ Connection verified working

### 🔴 Current Work

#### Session 3: HDMI Fix - IN PROGRESS
1. ⬜ SSH into Pi and check current HDMI status
2. ⬜ Run `hdmi_diag.py` to identify specific issue
3. ⬜ Apply appropriate fix from Solution A/B/C/D
4. ⬜ Test with Pioneer head unit
5. ⬜ Verify stability over 30 minutes

### 🟡 Upcoming Work

#### Session 4: Headlight Indicators Feature
1. ⬜ Monitor car CAN bus to identify headlight CAN IDs
2. ⬜ Implement state tracking in can_handler.py
3. ⬜ Add UI elements to displays
4. ⬜ Test with car (off/low/high beam states)

---

## 🎯 Success Criteria Checklist

**System Fully Operational When:**
- [ ] Pi boots and HDMI signal appears on Pioneer head unit
- [ ] Dashboard displays on Pioneer without signal loss
- [x] **Both CAN buses (can0 + can1) operational** ✅
- [x] **ESP32 serial connection stable** ✅
- [ ] ESP32 display shows live telemetry data (needs car CAN data)
- [ ] Arduino LED strip responds to RPM (needs car CAN data)
- [ ] Headlight indicators working on overview screens
- [ ] No disconnects or errors over 30-minute test drive
- [ ] All devices survive power cycle (car off → on)

**Progress: 2/9 Complete (22%)** 🔄

---

## 📋 Archived Issues (Resolved)

### ✅ MCP2515 CAN Bus Wiring (Fixed Dec 31, 2024)
- Both modules now operational in listen-only mode
- Verified with loopback test: 10/10 messages bidirectional
- Ready for production use
- Test script: `tools/test_mcp2515_loopback_active.py`

### ✅ USB-C Connection Pi → ESP32 (Fixed Dec 31, 2024)
- Replaced faulty cable with quality cable
- Serial communication stable
- `/dev/ttyACM0` detected reliably
- Test script: `tools/test_esp32_sync.py`

---

## 📚 References

- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - Complete system architecture
- [DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) - Setup and deployment
- [Pi Backup](backups/pi-backup-2024-12-24/) - Configuration backups
- [CAN Setup Script](pi/setup_can_bus.sh) - Automated CAN bus config

---

## 💡 Tips for Success

1. **Work on ONE issue at a time** - Don't change multiple things simultaneously
2. **Document what you try** - Keep notes on what worked/didn't work
3. **Take backups** - `sudo cp /boot/config.txt /boot/config.txt.backup` before edits
4. **Use your existing tools** - You have great diagnostic scripts already!
5. **Test incrementally** - Verify each fix before moving to next issue
6. **Check power** - Many issues trace back to insufficient power supply
7. **Consider EMI** - Car electrical systems are noisy; use shielded cables
8. **Be patient** - Some HDMI issues require trying multiple solutions

---

**Focus:** Get HDMI working first, then add headlight indicators! 🎯
