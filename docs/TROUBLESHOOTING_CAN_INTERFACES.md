# CAN Interface Mapping Troubleshooting

**Issue:** Coolant showing 0°F and Oil showing WARNING despite good CAN bus data reaching MCP2515 modules.

**Root Cause:** The Linux kernel CAN interface names (can0/can1) are assigned based on SPI device order (spi0.0/spi0.1), NOT based on which bus they're physically connected to. This can cause software to read from the wrong interface.

---

## Symptoms

- Display shows `Coolant=0F Oil=WARNING`
- Car is in ACC mode with ignition on
- MCP2515 modules are receiving good CAN data (verified with oscilloscope or logic analyzer)
- One CAN interface has many packets, the other has zero packets
- Issue appears after Pi reboot or configuration changes

---

## Diagnosis

### 1. Check which interface has data

```bash
ssh pi@192.168.1.23
ip -s link show can0
ip -s link show can1
```

Look at the `RX: packets` count. One interface will have many packets (100k+), the other will have 0.

### 2. Identify what data is on each interface

**Check can1 at 500kbps (HS-CAN speed):**
```bash
sudo ip link set can1 down
sudo ip link set can1 up type can bitrate 500000 listen-only on
timeout 3 candump can1 | head -10
```

**Look for HS-CAN message IDs:**
- `0x200` - Throttle position
- `0x201` - RPM and speed
- `0x211` - Brake and oil pressure switch
- `0x4B0` - Wheel speeds
- `0x420` - **Coolant temperature** (this is what we need!)

**Check can0 at 125kbps (MS-CAN speed):**
```bash
sudo ip link set can0 down
sudo ip link set can0 up type can bitrate 125000 listen-only on
timeout 3 candump can0 | head -10
```

**Look for MS-CAN message IDs:**
- `0x250` - Steering wheel controls (cruise buttons)
- `0x290` - Lighting status

### 3. Determine the actual mapping

Based on which interface receives which data:

| If HS-CAN data (0x201, 0x420) is on... | Then actual wiring is... |
|----------------------------------------|-------------------------|
| **can1** | HS=can1, MS=can0 (CURRENT SYSTEM) |
| **can0** | HS=can0, MS=can1 (ORIGINAL ASSUMPTION) |

---

## The Fix

The mapping must be corrected in **TWO** places. Both must match!

### File 1: Python CAN Handler

**Location:** `pi/ui/src/can_handler.py`

**Current (CORRECT) configuration for our system:**
```python
# Initialize HS-CAN (CE0, 500kbps) - Physical wiring: can1
self.hs_can = can.interface.Bus(
    channel='can1',  # HS-CAN is on can1
    bustype='socketcan',
    bitrate=500000
)

# Initialize MS-CAN (CE1, 125kbps) - Physical wiring: can0
self.ms_can = can.interface.Bus(
    channel='can0',  # MS-CAN is on can0
    bustype='socketcan',
    bitrate=125000
)
```

**If your system has opposite wiring:** Swap `'can0'` ↔ `'can1'` in the code above.

### File 2: Boot CAN Setup Script

**Location:** `/usr/local/bin/mx5-can-setup.sh` (on the Pi)

**Current (CORRECT) configuration for our system:**
```bash
#!/bin/bash
# MX5 Telemetry - Bring up CAN interfaces
# Called by systemd service on boot

# Wait for interfaces to be ready
sleep 2

# ACTUAL WIRING: HS-CAN is on can1 (spi0.0, CE0)
if ip link show can1 > /dev/null 2>&1; then
    ip link set can1 up type can bitrate 500000 restart-ms 100 listen-only on
    echo "can1 (HS-CAN) up at 500kbps (listen-only, auto-restart)"
else
    echo "can1 not found - check MCP2515 wiring"
fi

# ACTUAL WIRING: MS-CAN is on can0 (spi0.1, CE1)
if ip link show can0 > /dev/null 2>&1; then
    ip link set can0 up type can bitrate 125000 restart-ms 100 listen-only on
    echo "can0 (MS-CAN) up at 125kbps (listen-only, auto-restart)"
else
    echo "can0 not found - check MCP2515 wiring"
fi
```

**To update this file on the Pi:**
1. Edit `pi/mx5-can-setup.sh` in the repo
2. Copy to Pi: `scp pi/mx5-can-setup.sh pi@192.168.1.23:/tmp/`
3. Install: `ssh pi@192.168.1.23 "sudo mv /tmp/mx5-can-setup.sh /usr/local/bin/mx5-can-setup.sh && sudo chmod +x /usr/local/bin/mx5-can-setup.sh"`

---

## Apply the Fix

### Quick Fix (Temporary - until next reboot)

```bash
ssh pi@192.168.1.23
sudo systemctl restart mx5-display
```

Check if coolant now shows correct temperature (not 0°F).

### Permanent Fix

After editing **BOTH** files:

```bash
# Test the new CAN setup script
ssh pi@192.168.1.23
sudo ip link set can0 down
sudo ip link set can1 down
sudo /usr/local/bin/mx5-can-setup.sh

# Restart display service
sudo systemctl restart mx5-display

# Verify it's working
sudo journalctl -u mx5-display -n 20 --no-pager | grep Coolant
```

You should see `Coolant=XX°F` (not 0°F) and `Oil=OK` (not WARNING).

### Reboot Test

```bash
ssh pi@192.168.1.23 "sudo reboot"
# Wait 45 seconds
ssh pi@192.168.1.23 "sudo journalctl -u mx5-display -n 20 --no-pager | grep Coolant"
```

Should still show correct temperature after reboot.

---

## Understanding the Kernel Interface Names

**Critical knowledge:**

| Kernel Device | SPI Device | GPIO CS Pin | GPIO INT Pin | What determines can0 vs can1? |
|---------------|------------|-------------|--------------|-------------------------------|
| can0 | spi0.1 | GPIO 7 (CE1) | GPIO 24 | **Lower SPI device number = can0** |
| can1 | spi0.0 | GPIO 8 (CE0) | GPIO 25 | **Higher SPI device number = can1** |

The interface name (can0/can1) is assigned by the kernel based on **SPI device order**, NOT based on:
- ❌ Which GPIO CS pin it uses
- ❌ Which CAN bus (HS/MS) it's physically connected to
- ❌ The order in /boot/config.txt

**This means:** The software must be configured to match whatever interface names the kernel assigns.

---

## Prevention Checklist

When setting up a new Pi or after changing MCP2515 configuration:

- [ ] Boot the Pi and run diagnosis commands above
- [ ] Identify which interface (can0/can1) has HS-CAN data
- [ ] Update `pi/ui/src/can_handler.py` to match
- [ ] Update `pi/mx5-can-setup.sh` to match
- [ ] Copy updated script to Pi
- [ ] Test before and after reboot
- [ ] Document actual wiring in hardware notes

---

## Quick Reference

**Our system's actual configuration (as of Jan 18, 2026):**

| Physical Connection | Kernel Interface | Software Assignment |
|---------------------|------------------|---------------------|
| HS-CAN (OBD pins 6/14, 500kbps) | **can1** (spi0.0, CE0) | `hs_can` in Python |
| MS-CAN (OBD pins 3/11, 125kbps) | **can0** (spi0.1, CE1) | `ms_can` in Python |

**Boot script config:** can1=500k, can0=125k  
**Python code:** `channel='can1'` for HS, `channel='can0'` for MS

---

## Related Files

- `pi/ui/src/can_handler.py` - Python CAN interface initialization
- `pi/mx5-can-setup.sh` - Boot script (copied to `/usr/local/bin/` on Pi)
- `/boot/config.txt` - Device tree overlay config (defines SPI devices)
- `pi/setup_can_bus.sh` - Initial Pi setup script

---

**Last Updated:** January 18, 2026  
**Issue Resolved:** CAN interface mapping corrected to match actual hardware wiring
