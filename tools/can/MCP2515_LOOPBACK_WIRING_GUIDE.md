# MCP2515 Loopback Debug Wiring Guide

## Purpose

This guide shows how to connect your two MCP2515 modules together to test that both are working correctly **before** connecting them to the car's CAN bus.

---

## Why Test This Way?

By connecting the two MCP2515 modules directly to each other, you can:
- ✅ Verify both modules are detected by the Pi
- ✅ Verify SPI communication is working
- ✅ Verify CAN transceivers are functioning
- ✅ Verify your wiring and configuration are correct
- ✅ Test without risk of interfering with the vehicle CAN bus

---

## Wiring Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      RASPBERRY PI 4B                            │
│                                                                 │
│  ┌──────────────────────┐          ┌──────────────────────┐    │
│  │    MCP2515 #1        │          │    MCP2515 #2        │    │
│  │    (can0)            │          │    (can1)            │    │
│  │                      │          │                      │    │
│  │  VCC ──── 5V/3.3V ───┼──────────┼──── VCC              │    │
│  │  GND ──── GND ───────┼──────────┼──── GND              │    │
│  │  CS  ──── GPIO 8     │          │  GPIO 7 ──── CS      │    │
│  │  SO  ──── GPIO 9 (MISO) ────────┼──── GPIO 9 (MISO)    │    │
│  │  SI  ──── GPIO 10 (MOSI) ───────┼──── GPIO 10 (MOSI)   │    │
│  │  SCK ──── GPIO 11 ───┼──────────┼──── GPIO 11          │    │
│  │  INT ──── GPIO 25    │          │  GPIO 24 ──── INT    │    │
│  │                      │          │                      │    │
│  │  CAN-H ───────┐      │          │      ┌────── CAN-H  │    │
│  │               │      │          │      │               │    │
│  │  CAN-L ─────┐ │      │          │      │ ┌──── CAN-L  │    │
│  └─────────────┼─┼──────┘          └──────┼─┼─────────────┘    │
│                │ │                         │ │                 │
└────────────────┼─┼─────────────────────────┼─┼─────────────────┘
                 │ │                         │ │
                 │ └─────────────────────────┘ │  ← Connect CAN-H to CAN-H
                 │                             │
                 └─────────────────────────────┘  ← Connect CAN-L to CAN-L
```

---

## Physical Connections

### Step 1: Connect Both MCPs to Raspberry Pi (Already Done)

Both modules should already be wired to the Pi as shown in your architecture docs:

**MCP2515 #1 (can0 - HS-CAN):**
| MCP2515 Pin | Pi Pin | GPIO | Signal |
|-------------|--------|------|--------|
| VCC | Pin 2 or 4 | - | 5V or 3.3V (match module) |
| GND | Pin 6, 9, 14, 20, etc | - | Ground |
| CS | Pin 24 | GPIO 8 | SPI Chip Select 0 |
| SO (MISO) | Pin 21 | GPIO 9 | SPI Data Out |
| SI (MOSI) | Pin 19 | GPIO 10 | SPI Data In |
| SCK | Pin 23 | GPIO 11 | SPI Clock |
| INT | Pin 22 | GPIO 25 | Interrupt |

**MCP2515 #2 (can1 - MS-CAN):**
| MCP2515 Pin | Pi Pin | GPIO | Signal |
|-------------|--------|------|--------|
| VCC | Pin 2 or 4 | - | 5V or 3.3V (match module) |
| GND | Pin 6, 9, 14, 20, etc | - | Ground (common with MCP #1) |
| CS | Pin 26 | GPIO 7 | SPI Chip Select 1 |
| SO (MISO) | Pin 21 | GPIO 9 | SPI Data Out (shared) |
| SI (MOSI) | Pin 19 | GPIO 10 | SPI Data In (shared) |
| SCK | Pin 23 | GPIO 11 | SPI Clock (shared) |
| INT | Pin 18 | GPIO 24 | Interrupt |

### Step 2: Connect CAN Bus Wires Together

**This is the temporary test connection:**

1. **CAN-H to CAN-H:**
   - Connect the CAN-H terminal from MCP2515 #1 to CAN-H on MCP2515 #2
   - Use a jumper wire or connect both to a common screw terminal

2. **CAN-L to CAN-L:**
   - Connect the CAN-L terminal from MCP2515 #1 to CAN-L on MCP2515 #2
   - Use a jumper wire or connect both to a common screw terminal

```
MCP2515 #1          MCP2515 #2
┌──────────┐        ┌──────────┐
│          │        │          │
│  CAN-H ──┼────────┼── CAN-H  │  ← Jumper wire
│          │        │          │
│  CAN-L ──┼────────┼── CAN-L  │  ← Jumper wire
│          │        │          │
└──────────┘        └──────────┘
```

### Step 3: Enable Termination Resistors

CAN bus requires 120Ω termination at **both ends** of the bus. Since you're connecting two modules together:

1. **Check each MCP2515 module** for a termination jumper or resistor
2. **Enable 120Ω termination on BOTH modules**
   - Most modules have a jumper labeled "120Ω" or "TERM"
   - If no jumper, you may need to solder a 120Ω resistor between CAN-H and CAN-L

**Without proper termination, CAN communication will NOT work!**

---

## Running the Test

### Step 1: Upload Test Script to Pi

```bash
# From your PC, copy the test script to the Pi
scp tools/can/test_mcp2515_loopback.py pi@192.168.1.23:~/

# Or if already on Pi, clone the repo
cd ~
git clone https://github.com/tnnrhpwd/MX5-Telemetry.git
cd MX5-Telemetry
```

### Step 2: SSH into Pi

```bash
ssh pi@192.168.1.23
```

### Step 3: Install python-can (if not already installed)

```bash
pip3 install python-can
```

### Step 4: Run the Test

```bash
cd ~/MX5-Telemetry
python3 tools/can/test_mcp2515_loopback.py
```

### Expected Output (Success)

```
============================================================
MCP2515 Loopback Debug Test
============================================================

This script tests both MCP2515 modules by connecting them together.
Make sure you have wired CAN-H to CAN-H and CAN-L to CAN-L!

ℹ Checking for CAN interfaces...
✓ can0 found
✓ can1 found

ℹ Using 500kbps for testing (HS-CAN speed)

============================================================
Step 1: Configure CAN Interfaces
============================================================

✓ can0 configured at 500000 bps
✓ can1 configured at 500000 bps

============================================================
Step 2: Single Message Tests
============================================================

ℹ Test: can0 → can1
      Sender: can0, Receiver: can1
      Sending: ID=0x123, Data=[17, 34, 51, 68, 85, 102, 119, 136]
✓     Message received correctly!
      Received: ID=0x123, Data=[17, 34, 51, 68, 85, 102, 119, 136]

ℹ Test: can1 → can0
      Sender: can1, Receiver: can0
      Sending: ID=0x123, Data=[17, 34, 51, 68, 85, 102, 119, 136]
✓     Message received correctly!
      Received: ID=0x123, Data=[17, 34, 51, 68, 85, 102, 119, 136]

============================================================
Step 3: Burst Tests
============================================================

ℹ Burst test: Sending 20 messages from can0 to can1
      Sent 20 messages
      Received 20 messages
✓     All 20 messages received!

ℹ Burst test: Sending 20 messages from can1 to can0
      Sent 20 messages
      Received 20 messages
✓     All 20 messages received!

============================================================
Test Summary
============================================================

✓ can0 → can1                     PASSED
✓ can1 → can0                     PASSED
✓ can0 → can1 (burst)             PASSED
✓ can1 → can0 (burst)             PASSED

✓ All tests passed! Both MCP2515 modules are working correctly.
ℹ Your wiring and configuration are correct.
ℹ You can now connect them to the vehicle CAN bus.
```

---

## Troubleshooting

### Problem: `can0` or `can1` not found

**Solution:**
1. Check `/boot/config.txt` has the dtoverlay lines:
   ```bash
   cat /boot/config.txt | grep mcp2515
   ```
   Should show:
   ```
   dtoverlay=mcp2515-can0,oscillator=8000000,interrupt=25
   dtoverlay=mcp2515-can1,oscillator=8000000,interrupt=24
   ```

2. Check kernel messages:
   ```bash
   dmesg | grep mcp251
   ```
   Look for initialization messages or errors

3. If missing, run the setup script:
   ```bash
   cd ~/MX5-Telemetry/pi
   sudo bash setup_can_bus.sh
   sudo reboot
   ```

### Problem: Interfaces found but no messages received

**Possible causes:**

1. **Missing termination resistors**
   - Enable 120Ω jumper on BOTH modules
   - Or solder 120Ω resistor between CAN-H and CAN-L on each module

2. **CAN-H and CAN-L swapped**
   - Verify CAN-H goes to CAN-H, not CAN-L
   - Some modules label them as CANH and CANL

3. **Wrong oscillator frequency**
   - Check crystal on module (8MHz or 16MHz)
   - Update boot config to match:
     ```
     dtoverlay=mcp2515-can0,oscillator=16000000,interrupt=25
     dtoverlay=mcp2515-can1,oscillator=16000000,interrupt=24
     ```

4. **Loose connections**
   - Check all SPI wires (MISO, MOSI, SCK, CS)
   - Check interrupt wires (GPIO 25, GPIO 24)
   - Check power and ground

5. **Wrong bitrate**
   - Make sure both interfaces use the same bitrate
   - Script defaults to 500kbps

### Problem: One interface works, the other doesn't

**Solution:**
1. Swap the modules physically
2. If problem follows the module → hardware fault in that module
3. If problem stays with same interface → wiring or config issue for that interface

### Problem: Some burst messages dropped

**Possible causes:**
- Normal for high-speed CAN testing on Pi (not real-time OS)
- If >5% dropped, check termination and wiring quality
- Try lower burst count or slower message rate

---

## Next Steps

### Once Tests Pass:

1. **Disconnect the loopback connection**
   - Remove the jumper wires between CAN-H and CAN-L

2. **Connect to vehicle CAN bus**
   - MCP2515 #1 (can0) → HS-CAN from OBD-II pins 6 (H) and 14 (L)
   - MCP2515 #2 (can1) → MS-CAN from OBD-II pins 3 (H) and 11 (L)

3. **Disable termination on MCP2515 modules**
   - The vehicle CAN bus already has termination resistors
   - Remove 120Ω jumpers from your MCP2515 modules
   - If you soldered resistors, desolder them

4. **Use LISTEN-ONLY mode**
   - Your Pi should only listen, not transmit (already configured in `setup_can_bus.sh`)
   - This prevents interfering with vehicle CAN bus

5. **Test with vehicle**
   - Start car
   - Run: `candump can0` to see HS-CAN traffic (RPM, speed, etc)
   - Run: `candump can1` to see MS-CAN traffic (steering wheel buttons)

---

## Additional Testing Commands

### Monitor CAN traffic in real-time:
```bash
candump can0
```

### Send a test message manually:
```bash
cansend can0 123#1122334455667788
```

### Check interface status:
```bash
ip -details -statistics link show can0
ip -details -statistics link show can1
```

### Bring interfaces up/down manually:
```bash
sudo ip link set can0 down
sudo ip link set can0 up type can bitrate 500000
```

---

**Good luck with your debugging!** 🚗💨
