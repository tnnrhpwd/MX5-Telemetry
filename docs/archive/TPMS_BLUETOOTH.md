# Bluetooth TPMS Sensor Documentation

## Overview
This document contains raw BLE scan data from suspected TPMS sensors captured on December 14, 2025.

## Identified TPMS Sensors

All four sensors show as **Non Connectable** BLE devices (which is correct - TPMS sensors broadcast advertising data without requiring a connection).

| Tire Position | MAC Address | Signal (dBm) | Distance |
|--------------|-------------|--------------|----------|
| Unknown | `14:27:4B:11:11:11` | -87 | 25.12m |
| Unknown | `14:26:6D:11:11:11` | -88 | 28.18m |
| Unknown | `14:10:50:11:11:11` | -91 | 39.81m |
| Unknown | `14:13:1F:11:11:11` | -88 | 28.18m |

**Note:** All MACs share the pattern `14:XX:XX:11:11:11` suggesting same manufacturer.

## Raw Advertising Data

### Full Raw Packet
```
0x0201060303B0FB12FFAC00853D3C000A2500D0281111111F1314
```

### Parsed Structure
| Length | Type | Value | Description |
|--------|------|-------|-------------|
| 2 | 0x01 | 0x06 | Flags: LE General Discoverable, BR/EDR Not Supported |
| 3 | 0x03 | 0xB0FB | Complete 16-bit Service UUID: **0xFBB0** (Common Chinese TPMS) |
| 18 | 0xFF | (see below) | Manufacturer Specific Data |

### Manufacturer Data (18 bytes)
```
AC 00 85 3D 3C 00 0A 25 00 D0 28 11 11 11 1F 13 14
```

Byte-by-byte breakdown:
```
Offset  Hex   Decimal  Notes
------  ----  -------  -----
0       AC    172      Manufacturer ID byte 1? / Header?
1       00    0        Manufacturer ID byte 2?
2       85    133      ** LIKELY PRESSURE ** (see decoding)
3       3D    61       ** LIKELY TEMPERATURE ** (see decoding)
4       3C    60       Alternate temp? / Status?
5       00    0        Padding/reserved?
6       0A    10       Unknown
7       25    37       Unknown (could be secondary temp?)
8       00    0        Padding/reserved?
9       D0    208      Unknown
10      28    40       Unknown
11      11    17       Part of sensor ID (matches MAC)
12      11    17       Part of sensor ID (matches MAC)
13      11    17       Part of sensor ID (matches MAC)
14      1F    31       Sensor ID byte (matches MAC 14:13:1F)
15      13    19       Sensor ID byte
16      14    20       Sensor ID byte
```

## Decoding Analysis

### Expected Values (at time of capture)
- Temperature: **35-40°F** (1.7-4.4°C)
- Pressure: **~28 PSI** (~193 kPa)

### Pressure Decoding (Byte 2 = 0x85)

**Hypothesis:** `0x85` (133 decimal) represents pressure

| Formula | Result | Match? |
|---------|--------|--------|
| 133 × 1.45 = 193 kPa | 193 kPa = **28.0 PSI** | ✅ EXACT MATCH |
| 133 × 1.5 = 199.5 kPa | 199.5 kPa = 28.9 PSI | Close |
| 133 + 60 = 193 kPa | 193 kPa = 28.0 PSI | ✅ Alternative formula |

**Most likely formula:** `pressure_kPa = raw_byte + 60` or `pressure_kPa = raw_byte × 1.45`
**Conversion:** `PSI = kPa / 6.895`

### Temperature Decoding (Byte 3 = 0x3D or Byte 4 = 0x3C)

**Hypothesis:** Temperature with offset

| Raw | Offset | Celsius | Fahrenheit | Match? |
|-----|--------|---------|------------|--------|
| 0x3D (61) | -55 | 6°C | 42.8°F | ✅ Close |
| 0x3D (61) | -57 | 4°C | 39.2°F | ✅ GOOD MATCH |
| 0x3C (60) | -55 | 5°C | 41.0°F | ✅ GOOD MATCH |
| 0x3C (60) | -58 | 2°C | 35.6°F | ✅ EXACT MATCH |

**Most likely formula:** `temperature_C = raw_byte - 55` (or -58)
**Conversion:** `°F = °C × 9/5 + 32`

## Proposed Decoding Functions

```cpp
// Pressure decoding (returns PSI)
// Calibrated 2025-12-15 against manufacturer app
float decodePressure(uint8_t raw) {
    float kPa = raw + 56.0f;  // Calibrated offset
    return kPa / 6.895f;
}

// Temperature decoding (returns Fahrenheit)
// Calibrated 2025-12-15 against manufacturer app
float decodeTemperature(uint8_t raw) {
    float celsius = raw - 40.0f;  // Calibrated offset
    return celsius * 9.0f / 5.0f + 32.0f;
}
```

## Service UUID

- **UUID:** `0xFBB0`
- **Type:** 16-bit BLE Service UUID
- **Notes:** Common UUID used by Chinese/generic BLE TPMS sensors (SYSGRATION compatible)

## Next Steps

1. **Verify decoding** - Capture more data at known pressures/temperatures
2. **Map tire positions** - Identify which MAC belongs to which tire (FL, FR, RL, RR)
3. ~~Implement BLE scanning on ESP32~~ ✅ DONE
4. ~~Integrate with telemetry~~ ✅ DONE - Data flows to Pi display

## Implementation Status

### ESP32-S3 BLE TPMS Scanner ✅
- Location: `display/src/main.cpp`
- Uses NimBLE-Arduino library for BLE scanning
- Scans every 5 seconds for TPMS sensors
- Decodes pressure and temperature from manufacturer data
- Sends data to Pi via Serial: `TPMS_PSI:FL,FR,RL,RR` and `TPMS_TEMP:FL,FR,RL,RR`

### Raspberry Pi Integration ✅
- Location: `pi/ui/src/esp32_serial_handler.py`
- Receives TPMS_PSI and TPMS_TEMP messages from ESP32
- Updates telemetry object with tire pressure and temperature
- Sets `tpms_connected = True` when valid data received

### Tire Position Mapping
To update which sensor is on which tire, edit `tpmsTireMapping` in `display/src/main.cpp`:
```cpp
// Tire positions: 0=FL, 1=FR, 2=RL, 3=RR
int tpmsTireMapping[4] = {0, 1, 2, 3};  // FL=sensor0, FR=sensor1, RL=sensor2, RR=sensor3
```

## Integration Notes

### For Raspberry Pi (Python with bleak)
```python
import asyncio
from bleak import BleakScanner

TPMS_SERVICE_UUID = "0000fbb0-0000-1000-8000-00805f9b34fb"
TPMS_MACS = [
    "14:27:4B:11:11:11",
    "14:26:6D:11:11:11",
    "14:10:50:11:11:11",
    "14:13:1F:11:11:11",
]

def decode_tpms(manufacturer_data: bytes):
    """Decode TPMS manufacturer data"""
    if len(manufacturer_data) < 5:
        return None
    
    pressure_raw = manufacturer_data[2]
    temp_raw = manufacturer_data[3]
    
    pressure_psi = (pressure_raw + 60) / 6.895
    temp_f = (temp_raw - 55) * 9/5 + 32
    
    return {
        'pressure_psi': round(pressure_psi, 1),
        'temperature_f': round(temp_f, 1)
    }

async def scan_tpms():
    devices = await BleakScanner.discover(timeout=5.0)
    for device in devices:
        if device.address in TPMS_MACS:
            # Process advertising data
            pass
```

### For ESP32 (Arduino/BLE)
The ESP32 can also scan for these BLE advertisements using the `NimBLE` library.

## Raw Scan Screenshots

Captured: December 14, 2025
Location: Mountain road, vehicle parked
Conditions: Cold (~35-40°F)
App: BLE Scanner (Android)

---

*Last updated: December 14, 2025*
