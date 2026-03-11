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

import threading
import time

# Resistor values for voltage divider
R_HIGH = 20000  # 2x10kΩ in series
R_LOW = 4700    # 4.7kΩ
DIVIDER_RATIO = (R_HIGH + R_LOW) / R_LOW  # ~5.255

# Try to import I2C / ADS1115 libraries
try:
    import board
    import busio
    import adafruit_ads1x15.ads1115 as ADS
    from adafruit_ads1x15.analog_in import AnalogIn
    ADS1115_AVAILABLE = True
except ImportError:
    ADS1115_AVAILABLE = False


class VoltageMonitor:
    """Reads 12V source voltage from ADS1115 ADC and updates telemetry."""

    def __init__(self, telemetry_data, read_interval=1.0):
        """
        Args:
            telemetry_data: TelemetryData object — sets .voltage
            read_interval: Seconds between ADC reads (default 1s)
        """
        self.telemetry = telemetry_data
        self.read_interval = read_interval
        self._running = False
        self._thread = None
        self._ads = None
        self._channel = None

    def start(self) -> bool:
        """Start background voltage reading thread. Returns True if ADC initialized."""
        if not ADS1115_AVAILABLE:
            print("VoltageMonitor: adafruit_ads1x15 library not installed")
            return False

        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self._ads = ADS.ADS1115(i2c, address=0x48)
            self._ads.gain = 1  # ±4.096V range
            self._channel = AnalogIn(self._ads, ADS.P0)
            # Verify we can read
            _ = self._channel.voltage
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

    def _read_loop(self):
        """Background loop: read ADC and update telemetry.voltage."""
        while self._running:
            try:
                adc_voltage = self._channel.voltage
                source_voltage = adc_voltage * DIVIDER_RATIO
                # Clamp to reasonable range
                source_voltage = max(0.0, min(source_voltage, 20.0))
                self.telemetry.voltage = round(source_voltage, 1)
            except Exception as e:
                print(f"VoltageMonitor: Read error: {e}")
            time.sleep(self.read_interval)
