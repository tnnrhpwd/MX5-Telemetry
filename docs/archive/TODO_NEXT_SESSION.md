# MX5 Telemetry - Next Session To-Do List

**Date Created:** December 1, 2025  
**Last Updated:** December 20, 2025  


## 🎯 Current Architecture

| Device | Purpose | Location 
|--------|---------|----------
| **Raspberry Pi 4B** | CAN hub + settings cache + HDMI display | Hidden (dashboard)
| **ESP32-S3 Round Display** | Gauge display + BLE TPMS + G-force IMU | Stock oil gauge hole
| **Arduino Nano** | Direct CAN → LED strip + receives LED pattern from Pi | Hidden (dashboard)

### Data Flow Summary

```
OBD-II Port
    │
    ├─── HS-CAN (500k) ──┬──► Pi MCP2515 #1 ──► Pi processes all telemetry
    │    (SHARED)        │
    │                    └──► Arduino MCP2515 ──► RPM → LED strip (<1ms)
    │
    └─── MS-CAN (125k) ──────► Pi MCP2515 #2 ──► Steering wheel buttons
    
Pi (Central Hub + Settings Cache)
    │
    ├──► ESP32-S3 (Serial) ──► Telemetry + SWC buttons + settings sync
    │    ◄─── ESP32-S3 ◄───── TPMS (BLE sensors) + G-force (IMU)
    │
    ├──► Arduino (Serial) ───► LED sequence selection + settings sync
    │
    └──► Pioneer (HDMI) ─────► Full dashboard display
```

See [PI_DISPLAY_INTEGRATION.md](PI_DISPLAY_INTEGRATION.md) for full architecture.

---

## 📋 Remaining Tasks

### Hardware (Before Full Testing)
- [ ] Wire MCP2515 modules to Pi GPIO (see wiring table below)
- [ ] Test CAN interfaces with `candump can0` and `candump can1`

### Hardware
- [ ] Test Pi with actual MCP2515 modules in car
- [ ] Verify BLE TPMS sensor data accuracy
- [ ] Mount ESP32-S3 round display in dash
- [ ] Run wires from Pi to NANO

### Software
- [ ] Fine-tune Pi CAN bus timing
- [ ] Implement lap timer on RPM/Speed screen
- [ ] Add TPMS low-pressure alerts with audio (May not add)

### Testing
- [ ] Full car test with all components
- [ ] Verify steering wheel button mapping (CAN IDs 0x240, 0x250 - may need adjustment)
- [ ] Test G-force calibration during driving

---


## 🔧 Code Cleanup (Lower Priority)
- [ ] Remove unused features and dead code
- [ ] Remove or disable features not needed for core RPM display:
  - [ ] Haptic feedback code

---

## 🗑️ Priority 4: Feature Removal Candidates

### Consider Removing/Disabling
- [ ] **SD Card Logging** - Major source of delays (move to archive)
  - Blocking writes can take 10-100ms+
  - Not needed for real-time RPM display
  - Can add back later as optional feature
  
- [ ] **GPS Logging** - Adds complexity, not needed for RPM LEDs (move to archive)
  - GPS parsing takes time each loop
  - SoftwareSerial can interfere with timing
  
- [ ] **Comprehensive Data Logging** - Overkill for RPM display (move to archive)
  
- [ ] **Log Rotation** - Only needed if keeping SD logging (move to archive)

### Keep These Features
- [ ] CAN Bus reading (core functionality)
- [ ] RPM to LED mapping (core functionality)
- [ ] Potentiometer brightness control (hardware feature, minimal overhead)
- [ ] Basic startup animation (good UX, runs once)

---

## 📊 Priority 5: Performance Optimizations

### Timing Analysis
- [ ] Add performance profiling code to measure loop time
- [ ] Target: LED update within 50ms of CAN message (20Hz minimum)
- [ ] Ideal: LED update within 16ms (60Hz, smooth animation)

### Code Optimizations
- [ ] Use `FastLED` library instead of Adafruit NeoPixel? (reportedly faster)
- [ ] Pre-calculate LED colors in lookup table
- [ ] Avoid floating-point math in hot paths
- [ ] Use `constexpr` for compile-time calculations
- [ ] Minimize `map()` calls - use bit shifting where possible

### Hardware Optimizations
- [ ] Ensure CAN bus is running at correct speed (500kbps for OBD-II)
- [ ] Check if MCP2515 interrupt pin could speed up CAN reads
- [ ] Consider ESP32 for future (faster processor, built-in CAN on some)

---

## Quick Reference: Current Architecture

```
                           ┌──────────────────────────────────────────┐
                           │            RASPBERRY PI 4B               │
                           │      (Central Hub + Settings Cache)      │
                           │          [Hidden in console]             │
                           │                                          │
┌────────────────┐         │  ┌──────────────┐    ┌──────────────┐   │
│   OBD-II Port  │         │  │   MCP2515    │    │   MCP2515    │   │
│                │         │  │   HS-CAN     │    │   MS-CAN     │   │
│  HS-CAN ───────┼────┬───►│  │   (500k)     │    │   (125k)     │   │
│  (SHARED)      │    │    │  └──────────────┘    └──────────────┘   │
│                │    │    │                                          │
│  MS-CAN ───────┼────┼───►│  • Reads all CAN data                   │
│  (Pi only)     │    │    │  • Caches settings → syncs on startup   │
└────────────────┘    │    │  • Sends telemetry to ESP32 (serial)    │
                      │    │  • Sends LED pattern to Arduino (serial)│
                      │    │                                          │
                      │    │    HDMI ─────► Pioneer AVH-W4500NEX     │
                      │    └──────────────────────────────────────────┘
                      │
                      │    ┌────────────────────┐  ┌──────────────────┐
                      │    │   ESP32-S3 Round   │  │   Arduino Nano   │
                      └───►│     Display        │  │   + LED Strip    │
                           │  [Oil gauge hole]  │  │  [Gauge bezel]   │
                           │                    │  │                  │
BLE TPMS Sensors ─────────►│ • BLE TPMS → Pi    │  │ • Direct CAN RPM │
(4x cap-mount)             │ • G-Force IMU → Pi │  │ • Receives LED   │
                           │ • Displays gauges  │  │   pattern from Pi│
                           │ • SWC navigation   │  │ • WS2812B strip  │
                           └────────────────────┘  └──────────────────┘
```

### Pi Wiring Summary

| Pi GPIO | Function | Connected To |
|---------|----------|--------------|
| GPIO 8 (CE0) | SPI CS | MCP2515 #1 (HS-CAN) |
| GPIO 7 (CE1) | SPI CS | MCP2515 #2 (MS-CAN) |
| GPIO 10 | SPI MOSI | Both MCP2515 SI |
| GPIO 9 | SPI MISO | Both MCP2515 SO |
| GPIO 11 | SPI SCLK | Both MCP2515 SCK |
| GPIO 25 | Interrupt | MCP2515 #1 INT |
| GPIO 24 | Interrupt | MCP2515 #2 INT |
| GPIO 14 (TXD) | UART TX | Arduino RX (D3) |
| GPIO 15 (RXD) | UART RX | Arduino TX (D4) |
| USB-A | USB Serial | ESP32-S3 USB-C (/dev/ttyACM0) |

### Build Commands

```powershell
# Arduino LED Controller
pio run -d arduino --target upload

# ESP32-S3 Display  
pio run -d display --target upload

# Pi Display (run on Pi)
python3 pi/ui/src/main.py --fullscreen
```

### Pi Setup Commands (run once)

```bash
# 1. Enable SPI
sudo raspi-config  # Interface Options → SPI → Enable

# 2. Edit boot config
sudo nano /boot/config.txt
# Add:
#   dtparam=spi=on
#   dtoverlay=mcp2515-can0,oscillator=8000000,interrupt=25
#   dtoverlay=mcp2515-can1,oscillator=8000000,interrupt=24,cs_pin=7
#   enable_uart=1

# 3. Reboot
sudo reboot

# 4. Bring up CAN interfaces
sudo ip link set can0 up type can bitrate 500000
sudo ip link set can1 up type can bitrate 125000

# 5. Test CAN
candump can0  # Should see HS-CAN traffic when car is on
candump can1  # Should see MS-CAN traffic
```

---

## Session Notes

_Add notes here during next session:_

- 
- 
-