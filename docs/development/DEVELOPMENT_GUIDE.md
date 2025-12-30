# Development Guide - Analysis & Debugging

Complete guide for analyzing telemetry data and debugging the MX5-Telemetry system.

---

## 📊 Data Analysis

### Current Architecture

Data logging is handled by the **Raspberry Pi 4B**, which:
- Reads HS-CAN (RPM, speed, throttle, temps) and MS-CAN (steering wheel buttons)
- Receives TPMS and G-force data from ESP32-S3
- Logs to local storage or streams to external services

### Data Sources

**CAN Bus Data (Pi reads directly):**

| Data | CAN ID | Source |
|------|--------|--------|
| Engine RPM | 0x201 | HS-CAN (500 kbaud) |
| Vehicle Speed | 0x420 | HS-CAN |
| Throttle Position | 0x201 | HS-CAN |
| Coolant Temperature | OBD-II PID | HS-CAN |
| Steering Wheel Buttons | MS-CAN IDs | MS-CAN (125 kbaud) |

**Sensor Data (ESP32-S3 → Pi via serial):**

| Data | Source | Update Rate |
|------|--------|-------------|
| TPMS (4 tires) | BLE sensors | ~1 Hz |
| G-Force (lateral/longitudinal) | QMI8658 IMU | ~50 Hz |

### Basic Analysis

If your logging system outputs CSV:

```python
import pandas as pd

# Load telemetry data
df = pd.read_csv('telemetry_log.csv')

# Max RPM
max_rpm = df['RPM'].max()
print(f"Max RPM: {max_rpm}")

# Average speed
avg_speed = df['Speed'].mean()
print(f"Average Speed: {avg_speed} mph")

# Max G-force
max_g_lateral = df['G_Lateral'].abs().max()
max_g_long = df['G_Longitudinal'].abs().max()
print(f"Max Lateral G: {max_g_lateral}g")
print(f"Max Longitudinal G: {max_g_long}g")
```

### Visualization

```python
import matplotlib.pyplot as plt

# Plot RPM over time
plt.figure(figsize=(12, 6))
plt.plot(df['Time'], df['RPM'])
plt.xlabel('Time (s)')
plt.ylabel('RPM')
plt.title('Engine RPM Over Time')
plt.grid(True)
plt.show()

# Plot G-force scatter
plt.figure(figsize=(8, 8))
plt.scatter(df['G_Lateral'], df['G_Longitudinal'], alpha=0.5)
plt.xlabel('Lateral G')
plt.ylabel('Longitudinal G')
plt.title('G-Force Distribution')
plt.axhline(0, color='k', linewidth=0.5)
plt.axvline(0, color='k', linewidth=0.5)
plt.grid(True)
plt.show()
```

---

## 🐛 Debugging Guide

### System Logs

**Raspberry Pi Display Service:**
```bash
# View real-time logs
ssh pi@192.168.1.23 'journalctl -u mx5-display -f'

# Last 100 lines
ssh pi@192.168.1.23 'journalctl -u mx5-display -n 100'

# Logs since last boot
ssh pi@192.168.1.23 'journalctl -u mx5-display -b'
```

**Arduino Serial Debug:**
```bash
# Monitor Arduino serial output
pio device monitor -b 115200

# Or with PlatformIO
pio run -d arduino --target monitor
```

**ESP32-S3 Serial Debug:**
```bash
# Via Pi (ESP32 connected to Pi)
ssh pi@192.168.1.23 'cat /dev/ttyACM0'

# Or monitor directly
pio device monitor -b 115200 -p /dev/ttyACM0
```

### Common Issues

#### CAN Bus Not Working

**Symptoms:**
- No RPM data on displays
- LEDs show error animation
- "CAN OFFLINE" message

**Debug Steps:**
```bash
# Check CAN interfaces exist
ip link show can0
ip link show can1

# Bring up interfaces
sudo ip link set can0 up type can bitrate 500000
sudo ip link set can1 up type can bitrate 125000

# Monitor CAN traffic
candump can0  # HS-CAN (should show frequent messages)
candump can1  # MS-CAN (shows steering wheel buttons)
```

**Common Causes:**
- MCP2515 wiring incorrect
- CAN bus not connected to OBD-II
- Wrong bitrate configured
- Missing kernel modules

#### Serial Communication Errors

**Symptoms:**
- ESP32 not receiving data from Pi
- Arduino not responding to commands
- Timeout errors in logs

**Debug:**
```bash
# Check serial ports
ls -l /dev/ttyAMA0  # Pi → Arduino
ls -l /dev/ttyACM0  # Pi → ESP32

# Check permissions
sudo usermod -a -G dialout pi

# Monitor serial traffic
cat /dev/ttyACM0
```

**Common Causes:**
- Wrong baud rate (ESP32: 115200, Arduino: 9600)
- TX/RX swapped
- Ground not connected
- EMI interference (long wires)

#### Display Issues

**Symptoms:**
- Blank screen on ESP32
- No HDMI output from Pi
- Display frozen

**Debug:**
```bash
# Check display service status
systemctl status mx5-display

# Restart display
sudo systemctl restart mx5-display

# Check display errors
grep -i error /var/log/syslog | tail -50
```

#### TPMS Not Receiving

**Symptoms:**
- "No TPMS data" on display
- Stale tire pressure readings

**Debug:**
```bash
# Check ESP32 logs for BLE scanning
# Should see "Scanning for TPMS..." messages

# Verify sensors are powered
# Battery level should be > 20%

# Check sensor proximity
# Must be within ~5m of ESP32
```

### Performance Analysis

**Log Sample from Pi Display (Dec 21, 2025):**

```
============================================================
MX5 Telemetry - Raspberry Pi Display
============================================================
Resolution: 800x480
Data Source: CAN BUS - using real vehicle data

✓ Arduino serial connected on /dev/ttyAMA0 (LED sequence control)
✓ ESP32 connected - display sync enabled
✓ ESP32 serial opened on /dev/ttyACM0 at 115200 baud

TPMS: Loaded cached data (age: 0.0 hours)
  Last updates: FL=13:07:31, FR=13:07:31, RL=13:07:31, RR=13:47:55
  Pressures: FL=30.0, FR=28.9, RL=29.2, RR=29.0 PSI
  Temps: FL=18.0, FR=18.0, RL=18.0, RR=17.0 °C

ESP32: Sent initial settings to ESP32
  brightness=80, volume=70, shift_rpm=6500, redline_rpm=7200
  use_mph=1, tire_low_psi=28.0, coolant_warn=220, demo_mode=0
```

**Key Metrics:**
- Display refresh: 30 FPS
- Serial latency: ~50ms
- TPMS update: 1 Hz
- Settings sync: Complete on startup

### Debug Commands

**Quick System Check:**
```bash
# Full system status
ssh pi@192.168.1.23 '
  echo "=== CAN Status ===";
  ip -s link show can0 can1;
  echo -e "\n=== Display Service ===";
  systemctl status mx5-display --no-pager;
  echo -e "\n=== Serial Devices ===";
  ls -l /dev/ttyA* /dev/ttyACM*;
  echo -e "\n=== Recent Errors ===";
  journalctl -u mx5-display --since "1 hour ago" | grep -i error
'
```

**Performance Monitoring:**
```bash
# CPU & Memory usage
ssh pi@192.168.1.23 'top -b -n 1 | head -20'

# Temperature
ssh pi@192.168.1.23 'vcgencmd measure_temp'

# CAN message rates
ssh pi@192.168.1.23 'canbusload can0@500000 -r'
```

### Test Commands

**Test Serial Communication:**
```bash
# Test Pi → ESP32
echo "PING" > /dev/ttyACM0

# Test Pi → Arduino
echo "SEQ?" > /dev/ttyAMA0

# Should receive responses
cat /dev/ttyACM0  # PONG
cat /dev/ttyAMA0  # SEQ:1
```

**Test CAN Sending (diagnostic):**
```bash
# Send test RPM message (DO NOT USE ON REAL VEHICLE!)
cansend can0 201#1F4000000000000  # 2000 RPM
```

---

## 🔍 Advanced Debugging

### Packet Capture

**Serial Traffic:**
```bash
# Log all ESP32 serial communication
cat /dev/ttyACM0 | tee esp32_log.txt

# Parse telemetry packets
grep "TEL:" esp32_log.txt | tail -50
```

**CAN Traffic Analysis:**
```bash
# Log 1000 CAN messages
candump -n 1000 can0 > can_log.txt

# Analyze message frequency
cat can_log.txt | awk '{print $3}' | sort | uniq -c | sort -nr

# Filter specific ID (e.g., RPM)
grep "201#" can_log.txt
```

### Memory & Performance

**Pi Memory Usage:**
```bash
free -h
ps aux | grep python | grep -v grep
```

**Arduino Memory:**
```cpp
// Add to main.cpp setup()
Serial.println(F("Free RAM: "));
Serial.println(freeMemory());
```

**ESP32 Memory:**
```cpp
// Add to main.cpp loop()
Serial.printf("Heap: %d, PSRAM: %d\n", 
  ESP.getFreeHeap(), 
  ESP.getFreePsram());
```

---

## 📝 Logging Best Practices

### File Locations

```
Pi: /var/log/mx5-telemetry/
├── can_data.csv         # CAN bus logs
├── tpms_data.csv        # Tire pressure logs
├── system.log           # System events
└── errors.log           # Error messages
```

### Log Rotation

```bash
# Configure logrotate
sudo nano /etc/logrotate.d/mx5-telemetry

# Add:
/var/log/mx5-telemetry/*.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
}
```

---

## 🧪 Testing

### Unit Tests

Run project unit tests:
```bash
# Arduino tests
pio test -d arduino

# Pi tests (if implemented)
cd pi/ui
python3 -m pytest tests/
```

### Integration Testing

```bash
# Test full system
cd ~/MX5-Telemetry
python3 tools/test_integration.py
```

---

## See Also

- [ARCHITECTURE.md](../ARCHITECTURE.md) - System architecture
- [DEPLOYMENT_GUIDE.md](../DEPLOYMENT_GUIDE.md) - Troubleshooting guide
- [setup/PLATFORMIO_GUIDE.md](../setup/PLATFORMIO_GUIDE.md) - Build environment

---

**Last Updated:** December 29, 2025
