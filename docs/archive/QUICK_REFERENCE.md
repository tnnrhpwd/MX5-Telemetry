# Quick Reference - Dual Arduino Setup

## 🎯 Two Configurations in One Project

```
MX5-Telemetry/
├── src/              → Master Arduino (Logger)
└── src_led_slave/    → Slave Arduino (LED Controller)
```

## ⚡ Quick Commands

### Build
```bash
platformio run -e nano_atmega328  # Master
platformio run -e led_slave       # Slave
```

### Upload
```bash
platformio run -e nano_atmega328 --target upload --upload-port COM3
platformio run -e led_slave --target upload --upload-port COM4
```

## 🔌 Wiring

**Master → Slave:**
- TX (D1) → RX (D0)
- GND → GND

**Slave → LED:**
- D5 → WS2812B Data

## 📡 Serial Commands

**Master Serial:** 115200 baud (USB to computer)
**Slave Serial:** 9600 baud (Master TX to Slave RX)

**Commands to Slave:**
- `RPM:3500` - Set RPM
- `SPD:65` - Set speed
- `ERR` - Error state
- `CLR` - Clear LEDs
- `BRT:128` - Brightness

## 🎨 LED States

| RPM | Visual | Description |
|-----|--------|-------------|
| 0 | ⚪ White pepper | Idle |
| 2000-2500 | 🟢 Green edges | Efficiency |
| 750-1999 | 🟠 Orange pulse | Stall danger |
| 2501-4500 | 🟡 Yellow bar | Normal |
| 4501-7199 | 🔴 Red flash | Shift! |
| 7200+ | 🔴 Solid red | Rev limit |

## 🔧 Configuration

**Master:** `lib/Config/config.h`
```cpp
#define ENABLE_LED_SLAVE    1    // Use slave controller
#define ENABLE_LED_STRIP    0    // Disable local LED
```

**Slave:** `src_slave/main.cpp`
```cpp
#define LED_DATA_PIN        5    // D5
#define LED_COUNT          20    // Your LED count
```

## 📚 Documentation

- **[BUILD_GUIDE.md](docs/BUILD_GUIDE.md)** - How to build & upload
- **[DUAL_ARDUINO_SETUP.md](docs/DUAL_ARDUINO_SETUP.md)** - Complete setup
- **[CLEANUP_GUIDE.md](CLEANUP_GUIDE.md)** - Remove old project

## 🧪 Testing

**Test Master:**
```
Serial Monitor @ 115200
> START
```

**Test Slave:**
```
Serial Monitor @ 9600
> RPM:3000
> ERR
> CLR
```

## 🆘 Troubleshooting

**LEDs not working?**
1. Check TX → RX connection
2. Verify shared ground
3. Confirm `ENABLE_LED_SLAVE = 1`
4. Check slave baud = 9600

**Can't upload?**
1. Close Serial Monitors
2. Verify COM port
3. Try different USB port
4. Install CH340 drivers

**Build errors?**
```bash
platformio run --target clean
platformio run
```

---

**More help:** See full documentation in `docs/` folder
