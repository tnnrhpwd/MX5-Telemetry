"""
ADS1115 12V Voltage Monitor for Raspberry Pi

Reads the vehicle 12V source voltage via ADS1115 ADC on I2C bus.
Voltage divider: 2x10kΩ (series) + 4.7kΩ to GND
  V_source = V_adc * (20000 + 4700) / 4700

Hardware:
    ADS1115 VDD  → Pi 3.3V (Pin 1)
    ADS1115 GND  → GND
    ADS1115 SDA  → Pi GPIO 2 (Pin 3)
    ADS1115 SCL  → Pi GPIO 3 (Pin 5)
    ADS1115 ADDR → GND (address 0x48)
    ADS1115 A0   → Voltage divider midpoint
"""

import struct
import threading
import time

# Resistor values for voltage divider
R_HIGH = 20000  # 2x10kΩ in series
R_LOW = 4700    # 4.7kΩ
DIVIDER_RATIO = (R_HIGH + R_LOW) / R_LOW  # ~5.255

# ADS1115 I2C registers
_ADS1115_CONVERSION = 0x00
_ADS1115_CONFIG = 0x01

# Config: single-shot, AIN0 vs GND, gain ±4.096V, 128SPS, single-shot mode
# Bits: OS=1 | MUX=100 | PGA=001 | MODE=1 | DR=100 | COMP_MODE=0 | COMP_POL=0 | COMP_LAT=0 | COMP_QUE=11
_ADS1115_CONFIG_SINGLE_A0 = 0xC383

# Gain ±4.096V → LSB = 0.125 mV
_ADS1115_VOLTS_PER_BIT = 4.096 / 32768.0

# Try to import smbus (standard on Raspberry Pi OS)
try:
    import smbus
    ADS1115_AVAILABLE = True
except ImportError:
    ADS1115_AVAILABLE = False


class VoltageMonitor:
    """Reads 12V source voltage from ADS1115 ADC and updates telemetry."""

    def __init__(self, telemetry_data, read_interval=1.0, i2c_bus=1, address=0x48):
        """
        Args:
            telemetry_data: TelemetryData object — sets .voltage
            read_interval: Seconds between ADC reads (default 1s)
            i2c_bus: I2C bus number (1 on Pi 4)
            address: ADS1115 I2C address (0x48 with ADDR→GND)
        """
        self.telemetry = telemetry_data
        self.read_interval = read_interval
        self._i2c_bus = i2c_bus
        self._address = address
        self._running = False
        self._thread = None
        self._bus = None

    def start(self) -> bool:
        """Start background voltage reading thread. Returns True if ADC initialized."""
        if not ADS1115_AVAILABLE:
            print("VoltageMonitor: smbus library not installed")
            return False

        try:
            self._bus = smbus.SMBus(self._i2c_bus)
            # Verify the device responds by reading the config register
            self._bus.read_word_data(self._address, _ADS1115_CONFIG)
            # Do a test read
            self._read_adc_voltage()
        except Exception as e:
            print(f"VoltageMonitor: Failed to initialize ADS1115: {e}")
            return False

        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        print(f"VoltageMonitor: Started (reading every {self.read_interval}s)")
        return True

    def stop(self):
        """Stop the background reading thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _read_adc_voltage(self):
        """Trigger a single-shot read on AIN0 and return voltage."""
        # Write config to start single-shot conversion
        config_bytes = struct.pack('>H', _ADS1115_CONFIG_SINGLE_A0)
        self._bus.write_i2c_block_data(self._address, _ADS1115_CONFIG, list(config_bytes))
        # Wait for conversion (~8ms at 128SPS)
        time.sleep(0.01)
        # Read 2-byte result (big-endian signed 16-bit)
        raw = self._bus.read_i2c_block_data(self._address, _ADS1115_CONVERSION, 2)
        value = struct.unpack('>h', bytes(raw))[0]
        return value * _ADS1115_VOLTS_PER_BIT

    def _read_loop(self):
        """Background loop: read ADC and update telemetry.voltage."""
        while self._running:
            try:
                adc_voltage = self._read_adc_voltage()
                source_voltage = adc_voltage * DIVIDER_RATIO
                # Clamp to reasonable range
                source_voltage = max(0.0, min(source_voltage, 20.0))
                self.telemetry.voltage = round(source_voltage, 1)
            except Exception as e:
                print(f"VoltageMonitor: Read error: {e}")
            time.sleep(self.read_interval)
