# MX5 Telemetry System - Troubleshooting Game Plan

**Created:** December 30, 2024  
**System:** MX5 + Raspberry Pi 4B + ESP32-S3 1.85" + Pioneer AVH-W4500NEX + 2x MCP2515

---

## 🎯 Known Issues Summary

| Priority | Issue | Impact | Estimated Time |
|----------|-------|--------|----------------|
| **HIGH** | Pi4B HDMI not outputting to AVH head unit | No dashboard display on Pioneer | 2-4 hours |
| **HIGH** | 1x MCP2515 not sending CAN data to Pi4B | Missing engine/body data | 1-2 hours |
| **MEDIUM** | Faulty USB-C connection Pi4B → ESP32-S3 | Unreliable serial communication | 30min-1 hour |

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
# SSH into Pi
ssh pi@192.168.1.23

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

## 📋 Issue #2: MCP2515 Not Sending CAN Data to Pi4B

### Symptoms
- One MCP2515 module working, one not detected or not receiving data
- `candump can0` or `candump can1` shows no traffic
- dmesg shows errors or missing interface

### Root Cause Analysis

Likely causes:
1. **Wiring error** - SPI pins misconnected or loose
2. **Interrupt not configured** - GPIO not assigned correctly
3. **Wrong oscillator frequency** - Config says 8MHz but module is 16MHz
4. **Chip select conflict** - Both modules using same CS pin
5. **Power issue** - Insufficient 3.3V or 5V to module
6. **Boot config missing** - dtoverlay not loaded

### Testing Procedure

#### Step 1: Check Interface Detection
```bash
ssh pi@192.168.1.23

# List network interfaces
ip link show

# Should see:
# can0: <NOARP> mtu 16 qdisc noop state DOWN
# can1: <NOARP> mtu 16 qdisc noop state DOWN
```

**If missing:** Check boot config and wiring

#### Step 2: Check Kernel Messages
```bash
dmesg | grep -i mcp251
dmesg | grep -i spi
```

**Look for:**
- `mcp251x spi0.0 can0: MCP2515 successfully initialized`
- `mcp251x spi0.1 can1: MCP2515 successfully initialized`

**Error examples:**
- `mcp251x: probe of spi0.0 failed with error -2` → Wiring/power issue
- `spi_master spi0: Failed to setup GPIO: -22` → Wrong GPIO pin

#### Step 3: Verify Boot Config
```bash
cat /boot/config.txt | grep mcp2515
```

**Expected:**
```ini
dtparam=spi=on
dtoverlay=mcp2515-can0,oscillator=8000000,interrupt=25
dtoverlay=mcp2515-can1,oscillator=8000000,interrupt=24
```

#### Step 4: Check Physical Wiring

**MCP2515 Module #1 (HS-CAN - can0):**
| Pin | Connection | GPIO | Notes |
|-----|------------|------|-------|
| VCC | 5V or 3.3V | - | Match module voltage |
| GND | GND | - | Common ground |
| CS | CE0 | GPIO 8 | Chip select 0 |
| SO | MISO | GPIO 9 | SPI data out |
| SI | MOSI | GPIO 10 | SPI data in |
| SCK | SCLK | GPIO 11 | SPI clock |
| INT | GPIO 25 | 25 | Interrupt pin |

**MCP2515 Module #2 (MS-CAN - can1):**
| Pin | Connection | GPIO | Notes |
|-----|------------|------|-------|
| VCC | 5V or 3.3V | - | Match module voltage |
| GND | GND | - | Common ground |
| CS | CE1 | GPIO 7 | Chip select 1 |
| SO | MISO | GPIO 9 | **SHARED with can0** |
| SI | MOSI | GPIO 10 | **SHARED with can0** |
| SCK | SCLK | GPIO 11 | **SHARED with can0** |
| INT | GPIO 24 | 24 | Interrupt pin |

**Critical points:**
- MISO, MOSI, SCK are SHARED between both modules
- CS pins MUST be different (GPIO 8 vs GPIO 7)
- INT pins MUST be different (GPIO 25 vs GPIO 24)

#### Step 5: Test Each Interface Individually
```bash
# Bring up can0 (HS-CAN)
sudo ip link set can0 up type can bitrate 500000 listen-only on
candump can0

# In another SSH session, bring up can1 (MS-CAN)
sudo ip link set can1 up type can bitrate 125000 listen-only on
candump can1
```

**Expected when car is running:**
- `can0` should show constant traffic (HS-CAN is very active)
- `can1` may be quiet unless pressing steering wheel buttons

### Solutions (in order of likelihood)

#### Solution A: Fix Boot Config ⭐ Most Common
```bash
sudo nano /boot/config.txt
```

**Ensure these exact lines exist:**
```ini
# Enable SPI
dtparam=spi=on

# MCP2515 #1 (HS-CAN)
dtoverlay=mcp2515-can0,oscillator=8000000,interrupt=25

# MCP2515 #2 (MS-CAN)
dtoverlay=mcp2515-can1,oscillator=8000000,interrupt=24
```

**If oscillator is 16MHz:**
```ini
dtoverlay=mcp2515-can0,oscillator=16000000,interrupt=25
dtoverlay=mcp2515-can1,oscillator=16000000,interrupt=24
```

**Reboot:**
```bash
sudo reboot
```

#### Solution B: Re-run CAN Setup Script
```bash
cd ~/MX5-Telemetry/pi
sudo bash setup_can_bus.sh
sudo reboot
```

#### Solution C: Check Oscillator Crystal
- Examine MCP2515 module for crystal marking
- Common: 8MHz (stamped "8.000") or 16MHz (stamped "16.000")
- Update boot config to match

#### Solution D: Swap Modules
- If can0 works but can1 doesn't, physically swap the modules
- If the problem follows the module → hardware fault
- If the problem stays with can1 → wiring/config issue

### Hardware Checks
- [ ] Verify oscillator frequency on module (8MHz vs 16MHz)
- [ ] Check all solder joints on MCP2515 modules
- [ ] Measure voltage at VCC pin (should be stable 5V or 3.3V)
- [ ] Verify continuity from Pi GPIO to module pins
- [ ] Check CAN-H and CAN-L have 120Ω termination at OBD-II
- [ ] Ensure module has 120Ω termination resistor enabled (check jumper)

### Testing with OBD-II
```bash
# With car running and ignition on
candump -L can0

# Should see messages like:
# can0  201   [8]  00 00 0D B8 00 00 00 00   # RPM
# can0  420   [8]  00 4B 00 00 00 00 00 00   # Speed
```

### Success Criteria
- ✅ Both `can0` and `can1` appear in `ip link show`
- ✅ `dmesg` shows successful MCP2515 initialization for both
- ✅ `candump can0` shows HS-CAN traffic when engine running
- ✅ `candump can1` shows MS-CAN traffic when pressing SWC buttons
- ✅ No errors in dmesg related to SPI or MCP2515

---

## 📋 Issue #3: Faulty USB-C Connection Pi4B → ESP32-S3

### Symptoms
- Serial communication intermittent or dropped
- ESP32 display freezes or shows stale data
- Connection works sometimes but not reliably

### Root Cause Analysis

Common USB-C serial issues:
1. **Worn USB-C port** - Mechanical wear from repeated plugging
2. **Bad cable** - Cheap or damaged USB-C cable
3. **Loose connection** - Vibration causes intermittent contact
4. **Insufficient power** - Cable can't carry both data + power
5. **EMI interference** - Engine electrical noise on long cable

### Testing Procedure

#### Step 1: Verify USB Detection
```bash
ssh pi@192.168.1.23

# List USB devices
lsusb

# Check serial ports
ls -la /dev/ttyACM* /dev/ttyUSB*

# Monitor kernel messages while plugging/unplugging
dmesg -w
```

**Expected when ESP32 plugged in:**
```
usb 1-1.2: new full-speed USB device number X using xhci_hcd
usb 1-1.2: New USB device found, idVendor=303a, idProduct=1001
cdc_acm 1-1.2:1.0: ttyACM0: USB ACM device
```

#### Step 2: Test Serial Communication
```bash
# Send test data to ESP32
echo "TEST:123\n" > /dev/ttyACM0

# Monitor serial output (if ESP32 sends data back)
cat /dev/ttyACM0
```

#### Step 3: Check Connection Stability
```bash
# Monitor for disconnects (let run for 10 minutes)
while true; do
  if [ -e /dev/ttyACM0 ]; then
    echo "$(date): Connected"
  else
    echo "$(date): DISCONNECTED!"
  fi
  sleep 1
done
```

### Solutions (in order of likelihood)

#### Solution A: Replace USB-C Cable ⭐ Most Common
**Recommended cable specs:**
- USB 2.0 or 3.0
- Data + power support (not charge-only)
- Shielded for EMI protection
- Length: 1-2 feet (shorter = more reliable)
- Right-angle connector preferred (less stress on port)

**Suggested cables:**
- Anker PowerLine+ USB-C
- Cable Matters USB-C with ferrite cores
- Startech shielded USB-C

#### Solution B: Secure Cable with Strain Relief
- Add cable tie to secure USB-C cable to Pi mounting
- Use hot glue or silicone around connector (removable)
- 3D print a strain relief bracket
- Avoid sharp bends near connector

#### Solution C: Add Ferrite Cores
- Install snap-on ferrite beads on USB cable
- Place near both Pi and ESP32 ends
- Reduces EMI from engine/alternator

#### Solution D: Use Alternate Serial Connection
If USB-C continues to fail, use GPIO UART:

**Wiring:**
| Pi GPIO | ESP32 Pin | Signal |
|---------|-----------|--------|
| GPIO 14 (TX) | RX (GPIO 44) | Pi → ESP32 |
| GPIO 15 (RX) | TX (GPIO 43) | ESP32 → Pi |
| GND | GND | Common ground |

**Enable UART on Pi:**
```bash
sudo nano /boot/config.txt
```
Add:
```ini
enable_uart=1
dtoverlay=uart0
```

**Update Pi code to use `/dev/serial0` instead of `/dev/ttyACM0`**

**Reboot:**
```bash
sudo reboot
```

#### Solution E: Replace ESP32 USB-C Port (hardware repair)
If port is physically damaged:
1. Purchase replacement USB-C connector (USB 2.0 Type C)
2. Requires hot air station and soldering skills
3. Alternative: Use USB-C breakout board soldered to ESP32 pads

### Hardware Checks
- [ ] Inspect USB-C port on Pi for bent pins or debris
- [ ] Inspect USB-C port on ESP32 for damage
- [ ] Try different USB-C cable
- [ ] Test with short cable (<2 feet)
- [ ] Check for loose connector (wiggle test)
- [ ] Verify 5V power on ESP32 board when connected
- [ ] Try different USB port on Pi

### Software Checks
```bash
# Check serial port permissions
ls -la /dev/ttyACM0
# Should show: crw-rw---- 1 root dialout

# Add user to dialout group if needed
sudo usermod -a -G dialout pi

# Check serial baud rate in Pi code
grep -r "115200" ~/MX5-Telemetry/pi/
```

### Success Criteria
- ✅ `/dev/ttyACM0` appears consistently
- ✅ No disconnects over 30-minute test drive
- ✅ ESP32 receives telemetry data without gaps
- ✅ Connection survives engine start/bumps/vibration
- ✅ No serial errors in Pi or ESP32 logs

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

### Available Scripts in Your Repo
Located in `tools/`:
- **HDMI Diagnostics:** `hdmi_diag.py`, `deep_hdmi_diag.py`
- **HDMI Fixes:** `fix_hdmi1_config.py`, `force_hdmi_active.py`
- **CAN Testing:** Located in `pi/setup_can_bus.sh`
- **ESP32 Testing:** `test_esp32_sync.py`

### VS Code Tasks
Use `Ctrl+Shift+P` → "Tasks: Run Task":
- **Pi: View Display Logs** - Monitor Pi app in real-time
- **Pi: SSH Connect** - Quick SSH session
- **Pi: Flash ESP32 (Remote)** - Update ESP32 firmware

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

## 📝 Recommended Troubleshooting Order

### Session 1: HDMI Fix (2-4 hours)
1. ✅ SSH into Pi and check current HDMI status
2. ✅ Run `hdmi_diag.py` to identify specific issue
3. ✅ Apply appropriate fix from Solution A/B/C/D
4. ✅ Test with Pioneer head unit
5. ✅ Verify stability over 30 minutes

### Session 2: CAN Bus Fix (1-2 hours)
1. ✅ Check which MCP2515 is failing (can0 or can1)
2. ✅ Verify boot config has correct dtoverlay lines
3. ✅ Check physical wiring with multimeter
4. ✅ Test with `candump` while engine running
5. ✅ Verify both buses working

### Session 3: USB-C Fix (30min-1 hour)
1. ✅ Replace USB-C cable with quality shielded cable
2. ✅ Add strain relief to secure connection
3. ✅ Test connection stability over drive
4. ✅ Consider GPIO UART if USB continues to fail

---

## 🎯 Success Criteria Checklist

**System Fully Operational When:**
- [ ] Pi boots and HDMI signal appears on Pioneer head unit
- [ ] Dashboard displays on Pioneer without signal loss
- [ ] Both CAN buses (can0 + can1) show traffic in `candump`
- [ ] ESP32 display shows live telemetry data
- [ ] Arduino LED strip responds to RPM
- [ ] No disconnects or errors over 30-minute test drive
- [ ] All devices survive power cycle (car off → on)

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

**Good luck! Start with the HDMI issue first since it's the most visible problem.**
