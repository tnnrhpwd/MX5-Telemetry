"""
CAN Bus Handler for Raspberry Pi

Reads data from two MCP2515 CAN modules via SPI:
- HS-CAN (500kbps): Engine data, RPM, speed, gear, throttle
- MS-CAN (125kbps): Body data, steering wheel controls, accessories

Pin Configuration (from PI_DISPLAY_INTEGRATION.md):
    SPI Bus (shared):
        GPIO 10 (MOSI) -> Both MCP2515 SI
        GPIO 9  (MISO) -> Both MCP2515 SO
        GPIO 11 (SCLK) -> Both MCP2515 SCK
    
    Chip Select:
        GPIO 8  (CE0)  -> MCP2515 #1 CS (HS-CAN)
        GPIO 7  (CE1)  -> MCP2515 #2 CS (MS-CAN)
    
    Interrupts:
        GPIO 25        -> MCP2515 #1 INT (HS-CAN)
        GPIO 24        -> MCP2515 #2 INT (MS-CAN)

Requires: python-can, spidev
    pip install python-can
    
Enable SPI on Pi:
    sudo raspi-config -> Interface Options -> SPI -> Enable
    
Load CAN modules:
    sudo modprobe spi-bcm2835
    sudo modprobe can
    sudo modprobe can-raw
    sudo modprobe mcp251x
"""

import math
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional, Callable
from enum import Enum

# Try to import CAN library
try:
    import can
    CAN_AVAILABLE = True
except ImportError:
    CAN_AVAILABLE = False
    print("Warning: python-can not installed. CAN bus disabled.")


# =============================================================================
# Mazda MX-5 NC CAN IDs (2006-2015)
# =============================================================================

# HS-CAN (500kbps) - Engine/Drivetrain
class HSCanID:
    """High-Speed CAN Message IDs"""
    ENGINE_RPM = 0x201          # RPM, speed
    THROTTLE = 0x200            # Throttle position
    WHEEL_SPEEDS = 0x4B0        # Individual wheel speeds
    STEERING_ANGLE = 0x4B8      # Steering wheel angle
    BRAKE_STATUS = 0x212        # Brake pedal status
    GEAR_POSITION = 0x231       # Current gear
    ENGINE_TEMP = 0x420         # Coolant and ambient temps
    FUEL_LEVEL = 0x430          # Fuel level
    BATTERY_VOLTAGE = 0x440     # System voltage


# MS-CAN (125kbps) - Body/Accessories  
class MSCanID:
    """Medium-Speed CAN Message IDs"""
    # NOTE: SWC_AUDIO (0x240) is NOT readable on the MS-CAN bus
    # Only cruise control buttons are available via CAN
    SWC_CRUISE = 0x250          # Steering wheel cruise buttons (only readable SWC)
    LIGHTING = 0x290            # Headlights, turn signals
    LIGHTING_STATUS = 0x4A0     # Additional lighting status (headlights, high beams)
    CLIMATE = 0x350             # AC status
    DOORS = 0x430               # Door ajar status
    ODOMETER = 0x450            # Odometer reading


# =============================================================================
# OBD-II (Mode 01) request/response IDs - used for MAF air flow
# =============================================================================
class OBD2:
    REQUEST_ID = 0x7DF   # Functional request (broadcast to all ECUs)
    RESPONSE_ID = 0x7E8  # Engine ECU response
    MODE_CURRENT_DATA = 0x01
    PID_MAF = 0x10       # Mass Air Flow rate (g/s)
    PID_INTAKE_AIR = 0x0F  # Intake air temperature (degC + 40)


# =============================================================================
# CAN Data Parser
# =============================================================================

class CANParser:
    """Parse CAN messages into telemetry values"""
    
    @staticmethod
    def parse_rpm(data: bytes) -> int:
        """Parse RPM from engine message (ID 0x201)
        Typically bytes 0-1, big-endian, scale factor varies by ECU
        """
        if len(data) >= 2:
            raw = (data[0] << 8) | data[1]
            # Mazda NC typically uses raw/4 for RPM
            return raw // 4
        return 0
    
    @staticmethod
    def parse_speed(data: bytes) -> int:
        """Parse vehicle speed from engine message (ID 0x201).

        Returns **km/h** - the canonical speed unit for the whole system. The
        Android app converts to mph for display, and the ESP32 does the same.

        MX5 NC uses a 16-bit value in 0.01 km/h units with a 100 km/h offset:
        - 0 km/h actual = 10000 raw (100.00 km/h in raw units)
        - -5 km/h (reverse) = 9500 raw (95.00 km/h in raw units)
        - +50 km/h forward = 15000 raw (150.00 km/h in raw units)

        IMPORTANT: For negative speeds (reverse), the sign must be preserved even
        for small values. int() truncates toward zero, which would turn -0.4 km/h
        into 0 and lose the reverse indicator, so negatives are floored instead.
        """
        if len(data) >= 6:
            raw = (data[4] << 8) | data[5]

            # Raw value is in 0.01 km/h units with +100 km/h offset
            true_kmh = (raw - 10000) / 100.0

            # Floor for negative: -0.4 -> -1, ensuring reverse is detected.
            if true_kmh < 0:
                return int(math.floor(true_kmh))
            return int(true_kmh)
        return 0

    @staticmethod
    def parse_throttle(data: bytes) -> int:
        """Parse throttle position (ID 0x200 byte 4, legacy 0-255 scale).

        Kept as a fallback only: the NC broadcasts the pedal position in the
        engine frame (0x201 byte 6, 0-200 = 0-100%), see parse_throttle_engine().
        """
        if len(data) >= 5:
            return int(data[4] * 100 / 255)
        return 0

    @staticmethod
    def parse_throttle_engine(data: bytes) -> Optional[int]:
        """Parse throttle position from the engine frame (ID 0x201).

        Byte 6 carries 0-200 where 200 = fully open. Returns None when the frame
        is too short or the byte is outside that range, so the caller can fall
        back to the legacy 0x200 decode instead of showing a garbage value.
        """
        if len(data) >= 7:
            raw = data[6]
            if raw <= 210:
                return int(min(100, raw * 100 / 200))
        return None

    @staticmethod
    def parse_intake_temp(data: bytes) -> Optional[int]:
        """Parse intake air temperature from an OBD-II PID 0x0F response.

        Response layout: [len=3, mode=0x41, pid=0x0F, A, ...]
        A is degC + 40. Returns Fahrenheit, or None when this is not an IAT reply.
        """
        if len(data) >= 4 and data[1] == 0x41 and data[2] == OBD2.PID_INTAKE_AIR:
            temp_c = data[3] - 40
            return int(temp_c * 9 / 5 + 32)
        return None

    @staticmethod
    def parse_maf(data: bytes) -> float:
        """Parse MAF from an OBD-II Mode 01 PID 0x10 response.

        Response layout: [len=4, mode=0x41, pid=0x10, A, B, ...]
        MAF (g/s) = (256 * A + B) / 100
        """
        if len(data) >= 5 and data[1] == 0x41 and data[2] == OBD2.PID_MAF:
            return ((data[3] << 8) | data[4]) / 100.0
        return 0.0
    
    @staticmethod
    def parse_gear(data: bytes) -> int:
        """Parse gear position (ID 0x231)
        
        2008 MX5 NC GT does NOT have a gear position sensor for gears 1-6!
        Only Neutral can be reliably detected via the neutral safety switch.
        Gears 1-6 must be ESTIMATED from speed/RPM ratio.
        
        Returns:
            0 = Neutral (detected from CAN)
            None = Not in neutral (gear must be estimated from speed/RPM)
        
        Note: Reverse is detected separately via negative speed from CAN message 0x201
        """
        if len(data) >= 1:
            # Check byte 1 for neutral/park indicators
            if len(data) >= 2 and data[1] == 0x04:
                return 0  # Neutral/Park - reliable from CAN
            gear = data[0] & 0x0F
            if gear == 0:
                return 0  # Neutral - reliable from CAN
            # For any other value, we cannot reliably determine the gear
            # The MX5 NC doesn't report gears 1-6 accurately - must estimate from speed/RPM
            return None  # Return None to indicate gear must be estimated
        return None
    
    @staticmethod
    def parse_wheel_speeds(data: bytes) -> tuple:
        """Parse individual wheel speeds (ID 0x4B0)
        Returns (FL, FR, RL, RR) in km/h
        """
        if len(data) >= 8:
            fl = ((data[0] << 8) | data[1]) / 100.0
            fr = ((data[2] << 8) | data[3]) / 100.0
            rl = ((data[4] << 8) | data[5]) / 100.0
            rr = ((data[6] << 8) | data[7]) / 100.0
            return (fl, fr, rl, rr)
        return (0, 0, 0, 0)
    
    @staticmethod
    def parse_steering_angle(data: bytes) -> float:
        """Parse steering wheel angle (ID 0x4B8)
        Returns degrees, positive = right, negative = left
        """
        if len(data) >= 2:
            raw = (data[0] << 8) | data[1]
            # Convert from unsigned to signed
            if raw > 32767:
                raw -= 65536
            return raw / 10.0  # Typically 0.1 degree resolution
        return 0.0
    
    @staticmethod
    def parse_coolant_temp(data: bytes) -> int:
        """Parse coolant temperature (ID 0x420)
        Returns temperature in Fahrenheit
        """
        if len(data) >= 1:
            # Typically offset by 40C
            temp_c = data[0] - 40
            temp_f = int(temp_c * 9 / 5 + 32)
            return temp_f
        return 0
    
    @staticmethod
    def parse_ambient_temp(data: bytes) -> int:
        """Parse ambient/outside temperature (ID 0x420, byte 1)
        Returns temperature in Fahrenheit
        """
        if len(data) >= 2:
            # Same offset as coolant: value - 40 = °C
            temp_c = data[1] - 40
            temp_f = int(temp_c * 9 / 5 + 32)
            return temp_f
        return 0
    
    @staticmethod
    def parse_fuel_level(data: bytes) -> float:
        """Parse fuel level percentage (ID 0x430)"""
        if len(data) >= 1:
            return data[0] * 100 / 255
        return 0.0
    
    @staticmethod
    def parse_voltage(data: bytes) -> float:
        """Parse battery voltage (ID 0x440)"""
        if len(data) >= 2:
            raw = (data[0] << 8) | data[1]
            return raw / 100.0  # Typically in 0.01V units
        return 0.0
    
    @staticmethod
    def parse_brake_status(data: bytes) -> bool:
        """Parse brake pedal status (ID 0x212)"""
        if len(data) >= 1:
            return bool(data[0] & 0x08)  # Brake bit
        return False
        
    @staticmethod
    def parse_oil_pressure(data: bytes) -> bool:
        """Parse oil pressure switch status (ID 0x212)
        Returns True if oil pressure detected, False if no pressure
        CAN data: 98 00 20 40 01 00 00 00 (byte 4 = 0x01 indicates oil pressure)
        """
        if len(data) >= 5:
            # Oil pressure switch is in byte 4 (0x01 = pressure present)
            return bool(data[4] & 0x01)
        return False    
    @staticmethod
    def parse_headlights(data: bytes) -> tuple:
        """Parse headlight status from lighting message
        Returns: (headlights_on, high_beams_on)
        """
        if len(data) >= 2:
            # Byte 0 typically has headlight status
            # Byte 1 typically has high beam status
            # Exact bit positions may need adjustment based on actual CAN data
            headlights_on = bool(data[0] & 0x01)  # Bit 0 for headlights
            high_beams_on = bool(data[1] & 0x01)  # Bit 0 of byte 1 for high beams
            return (headlights_on, high_beams_on)
        return (False, False)


# =============================================================================
# Gear Estimation (for 2008 MX5 NC GT without gear sensor)
# =============================================================================

class GearEstimator:
    """Estimates gear position from speed/RPM ratio for MX5 NC 6-speed transmission
    
    2008 MX5 NC GT does not have a gear position sensor - only Neutral can be detected
    via CAN bus. This class estimates the current gear based on the relationship between
    vehicle speed and engine RPM.
    
    MX5 NC 6-Speed Manual Transmission Ratios (2006-2015):
        1st: 3.760    Final Drive: 4.10
        2nd: 2.269    Tire Size: 205/45R17 (24.3" diameter)
        3rd: 1.645
        4th: 1.187
        5th: 1.000
        6th: 0.843
    """
    
    # Gear ratios for 2008 MX5 NC 6-speed manual
    GEAR_RATIOS = {
        1: 3.760,
        2: 2.269,
        3: 1.645,
        4: 1.187,
        5: 1.000,
        6: 0.843,
    }
    
    FINAL_DRIVE = 4.10
    TIRE_DIAMETER_INCHES = 24.3  # 205/45R17
    
    # Calculated expected MPH per 1000 RPM for each gear
    # Formula: (RPM * tire_circumference * 60) / (gear_ratio * final_drive * 63360)
    # where 63360 = inches per mile
    MPH_PER_1000_RPM = {}
    
    def __init__(self):
        """Calculate MPH per 1000 RPM for each gear"""
        tire_circumference = 3.14159 * self.TIRE_DIAMETER_INCHES
        for gear, ratio in self.GEAR_RATIOS.items():
            # MPH = (RPM * tire_circ * 60) / (gear_ratio * final_drive * 63360)
            mph_per_rpm = (tire_circumference * 60) / (ratio * self.FINAL_DRIVE * 63360)
            self.MPH_PER_1000_RPM[gear] = mph_per_rpm * 1000
    
    def suggest_gear_for_speed(self, speed_mph: float) -> int:
        """Suggest the appropriate gear for a given speed
        
        Returns the gear that would put the engine in optimal RPM range (~3000-4000 RPM)
        """
        if speed_mph < 2:
            return 1  # Suggest 1st gear when stationary/very slow
        
        # Find gear that gives ~3500 RPM at current speed (middle of optimal range)
        target_rpm = 3500
        best_gear = 1
        best_rpm_diff = float('inf')
        
        for gear, mph_per_1k in self.MPH_PER_1000_RPM.items():
            # Calculate what RPM would be in this gear at current speed
            expected_rpm = (speed_mph / mph_per_1k) * 1000
            rpm_diff = abs(expected_rpm - target_rpm)
            if rpm_diff < best_rpm_diff:
                best_rpm_diff = rpm_diff
                best_gear = gear
        
        return best_gear
    
    def get_expected_rpm_for_gear(self, speed_mph: float, gear: int) -> float:
        """Calculate the expected RPM for a given speed and gear
        
        Returns expected RPM, or 0 if gear invalid
        """
        if gear < 1 or gear > 6:
            return 0.0
        mph_per_1k = self.MPH_PER_1000_RPM.get(gear, 0)
        if mph_per_1k <= 0:
            return 0.0
        return (speed_mph / mph_per_1k) * 1000
    
    def get_gear_color(self, speed_mph: float, rpm: int, recommended_gear: int) -> str:
        """Determine gear indicator color based on RPM vs expected for recommended gear
        
        Returns color string:
            'red' - RPM too high for recommended gear (need to shift up or let off gas)
            'blue' - RPM too low for recommended gear (need to shift down or give gas)
            'green' - RPM is appropriate for recommended gear
            'yellow' - RPM slightly off
        """
        if recommended_gear < 1 or recommended_gear > 6:
            return 'green'
        
        if speed_mph < 2:
            # At very low/no speed, color based on absolute RPM
            if rpm > 4000:
                return 'red'  # Too high for starting
            elif rpm < 1000:
                return 'blue'  # Too low / stall risk
            else:
                return 'green'
        
        # Calculate expected RPM for recommended gear at current speed
        expected_rpm = self.get_expected_rpm_for_gear(speed_mph, recommended_gear)
        if expected_rpm <= 0:
            return 'green'
        
        rpm_diff_percent = ((rpm - expected_rpm) / expected_rpm) * 100
        
        # Color coding:
        # Green: within ±15% of expected (good match)
        # Yellow: 15-30% off (slightly off)
        # Red: >30% too high (RPM too high - shift up or let off)
        # Blue: >30% too low (RPM too low - shift down or more gas)
        if abs(rpm_diff_percent) <= 15:
            return 'green'
        elif rpm_diff_percent > 30:
            return 'red'
        elif rpm_diff_percent < -30:
            return 'blue'
        elif rpm_diff_percent > 15:
            return 'yellow'  # Slightly high
        else:
            return 'cyan'  # Slightly low
    
    def estimate_gear(self, speed_mph: float, rpm: int, is_in_neutral: bool = False) -> tuple:
        """Estimate gear from speed and RPM
        
        Args:
            speed_mph: Vehicle speed in MPH
            rpm: Engine RPM
            is_in_neutral: True if CAN bus neutral signal detected
        
        Returns:
            tuple: (gear, clutch_engaged, confidence, recommended_gear, gear_color)
                gear: Estimated current gear (1-6), 0 for neutral, -1 for reverse
                clutch_engaged: True if clutch appears to be pressed (ratio mismatch)
                confidence: How well the ratio matches expected (0.0-1.0)
                recommended_gear: Suggested gear for current speed (1-6)
                gear_color: Color indicator ('red', 'blue', 'green', 'yellow', 'cyan')
        """
        # If CAN reports neutral, return neutral
        if is_in_neutral:
            recommended = self.suggest_gear_for_speed(speed_mph)
            color = self.get_gear_color(speed_mph, rpm, recommended)
            return (0, False, 1.0, recommended, color)
        
        # Check for reverse (negative speed from CAN)
        if speed_mph < 0:
            return (-1, False, 1.0, -1, 'green')
        
        # Always calculate recommended gear based on speed
        recommended_gear = self.suggest_gear_for_speed(speed_mph)
        
        # If RPM is too low to calculate ratio, return recommended gear
        # This handles stationary/idle cases
        if rpm < 500:
            color = self.get_gear_color(speed_mph, rpm, recommended_gear)
            return (recommended_gear, True, 0.0, recommended_gear, color)
        
        # Very low speed - can't reliably estimate from ratio
        if speed_mph < 3:
            color = self.get_gear_color(speed_mph, rpm, recommended_gear)
            return (recommended_gear, True, 0.0, recommended_gear, color)
        
        # Calculate actual speed/RPM ratio
        actual_ratio = speed_mph / rpm
        
        # Find best matching gear from ratio
        best_gear = 1
        best_error = float('inf')
        
        for gear, mph_per_1k in self.MPH_PER_1000_RPM.items():
            expected_ratio = mph_per_1k / 1000
            error = abs(actual_ratio - expected_ratio)
            if error < best_error:
                best_error = error
                best_gear = gear
        
        # Calculate confidence (how close the ratio is to expected)
        expected_ratio = self.MPH_PER_1000_RPM[best_gear] / 1000
        ratio_difference = abs(actual_ratio - expected_ratio) / expected_ratio
        confidence = max(0.0, 1.0 - ratio_difference * 2.0)
        
        # Detect clutch engagement: ratio is way off (>40% difference)
        clutch_engaged = ratio_difference > 0.40
        
        # Determine which gear to display:
        # - If ratio matches a gear reasonably (>30% confidence), show that gear
        # - If ratio doesn't match (clutch in, shifting), show recommended gear
        display_gear = best_gear if confidence > 0.30 else recommended_gear
        
        # Calculate color based on RPM vs recommended gear
        color = self.get_gear_color(speed_mph, rpm, recommended_gear)
        
        return (display_gear, clutch_engaged, confidence, recommended_gear, color)


# =============================================================================
# CAN Handler Class
# =============================================================================

class CANHandler:
    """Manages CAN bus communication with MCP2515 modules"""
    
    # Fuel level smoothing parameters
    FUEL_AVERAGE_WINDOW_SEC = 60.0  # Average the last minute of RAW samples
    FUEL_HYSTERESIS = 1.5  # Only update displayed value if change > 1.5%

    # A pedal reading that stops arriving is zeroed after this long. Brake gets a
    # longer window because 0x212 is a body-status frame: it is not certain to be
    # broadcast as often as the engine frame, and a brake indicator that flickers
    # off while the pedal is held is worse than one that clears late.
    PEDAL_STALE_SEC = 0.75
    BRAKE_STALE_SEC = 2.5
    
    def __init__(self, telemetry_data, swc_handler=None):
        """
        Args:
            telemetry_data: TelemetryData object to update with CAN values
            swc_handler: Optional SWCHandler for button events
        """
        self.telemetry = telemetry_data
        self.swc_handler = swc_handler
        
        self.hs_can = None  # High-speed CAN bus (500k)
        self.ms_can = None  # Medium-speed CAN bus (125k)
        
        self._running = False
        self._hs_thread = None
        self._ms_thread = None
        
        self.connected = False
        self.last_hs_msg_time = 0
        self.last_ms_msg_time = 0
        
        # Gear estimator for vehicles without gear position sensor
        self.gear_estimator = GearEstimator()
        
        # Reverse detection hysteresis - once reverse is detected, hold it for a short
        # time to prevent flickering when CAN speed oscillates around zero offset
        self._reverse_hold_until = 0  # time.time() until which to keep showing reverse
        self._REVERSE_HOLD_SECONDS = 0.5  # Hold reverse for 500ms after speed goes to 0
        
        self._last_thr_log = 0.0

        # Fuel level smoothing state - a wall-clock rolling average, so the window
        # length does not drift when the fuel frame rate changes or stalls.
        self._fuel_samples = deque()     # (timestamp, raw_pct), oldest first
        self._fuel_sum = 0.0             # running sum, so each frame is O(1)
        self._fuel_displayed = None      # Last displayed integer (with hysteresis)

        # Pedal staleness: a value that stops arriving must decay, not freeze on
        # the dash showing a throttle that is no longer applied.
        self.throttle_timestamp = 0.0
        self.brake_timestamp = 0.0
        self._engine_throttle_pct = -1   # last decode from 0x201, for the cross-check log

        # OBD-II polling state. MAF and intake air share one request slot, so they
        # alternate rather than doubling the request rate on the bus.
        self._last_obd_request = 0.0
        self.obd_request_interval = 0.25   # 4 requests/second, alternating PIDs
        self._obd_pid_index = 0
        self._obd_pids = (OBD2.PID_MAF, OBD2.PID_INTAKE_AIR)

    def start(self) -> bool:
        """Initialize and start CAN bus reading"""
        if not CAN_AVAILABLE:
            print("CAN library not available")
            return False
        
        try:
            # Initialize HS-CAN (CE0, 500kbps) - Physical wiring: can1
            self.hs_can = can.interface.Bus(
                channel='can1',
                bustype='socketcan',
                bitrate=500000
            )
            print("HS-CAN (can1) initialized at 500kbps")
        except Exception as e:
            print(f"Failed to initialize HS-CAN: {e}")
            print("Trying MCP2515 SPI interface...")
            try:
                self.hs_can = can.interface.Bus(
                    channel='spi:0:0',  # SPI bus 0, CE0
                    bustype='mcp2515',
                    bitrate=500000,
                    gpio_int=25  # GPIO 25 for interrupt
                )
                print("HS-CAN (MCP2515 SPI) initialized at 500kbps")
            except Exception as e2:
                print(f"Failed to initialize HS-CAN via SPI: {e2}")
                self.hs_can = None
        
        try:
            # Initialize MS-CAN (CE1, 125kbps) - Physical wiring: can0
            self.ms_can = can.interface.Bus(
                channel='can0',
                bustype='socketcan',
                bitrate=125000
            )
            print("MS-CAN (can0) initialized at 125kbps")
        except Exception as e:
            print(f"Failed to initialize MS-CAN: {e}")
            try:
                self.ms_can = can.interface.Bus(
                    channel='spi:0:1',  # SPI bus 0, CE1
                    bustype='mcp2515',
                    bitrate=125000,
                    gpio_int=24  # GPIO 24 for interrupt
                )
                print("MS-CAN (MCP2515 SPI) initialized at 125kbps")
            except Exception as e2:
                print(f"Failed to initialize MS-CAN via SPI: {e2}")
                self.ms_can = None
        
        # Start reader threads
        self._running = True
        
        if self.hs_can:
            self._hs_thread = threading.Thread(target=self._read_hs_can, daemon=True)
            self._hs_thread.start()
            
        if self.ms_can:
            self._ms_thread = threading.Thread(target=self._read_ms_can, daemon=True)
            self._ms_thread.start()
        
        self.connected = self.hs_can is not None or self.ms_can is not None
        return self.connected
    
    def stop(self):
        """Stop CAN bus reading"""
        self._running = False
        
        if self._hs_thread:
            self._hs_thread.join(timeout=1.0)
        if self._ms_thread:
            self._ms_thread.join(timeout=1.0)
        
        if self.hs_can:
            self.hs_can.shutdown()
        if self.ms_can:
            self.ms_can.shutdown()
        
        self.connected = False
    
    def _smooth_fuel_level(self, raw_fuel: float) -> float:
        """Average the fuel level over a wall-clock window to stop it flickering.

        The fuel sender is coarse (roughly 1% steps) and the fuel in the tank
        sloshes under braking and cornering, so a single frame is not trustworthy.
        Averaging over a fixed *time* window - rather than an EMA whose time
        constant depends on how often the frame happens to arrive - gives the same
        smoothing whether the frame rate is stable, intermittent or stalled.

        A short hysteresis is still applied to the displayed integer so it does not
        twitch between adjacent values.

        Args:
            raw_fuel: Raw fuel percentage from CAN (0-100)

        Returns:
            Smoothed, hysteresis-filtered fuel percentage.
        """
        now = time.time()
        self._fuel_samples.append((now, raw_fuel))
        self._fuel_sum += raw_fuel

        # Drop samples older than the averaging window. The running sum keeps this
        # O(1) per frame: recomputing sum() over a whole minute of samples on every
        # fuel frame would be pointless work at 10-20 Hz.
        cutoff = now - self.FUEL_AVERAGE_WINDOW_SEC
        while self._fuel_samples and self._fuel_samples[0][0] < cutoff:
            _, old = self._fuel_samples.popleft()
            self._fuel_sum -= old

        averaged = self._fuel_sum / len(self._fuel_samples)

        if self._fuel_displayed is None:
            self._fuel_displayed = float(round(averaged))
            return self._fuel_displayed

        # Hysteresis: only move the displayed value once the average has moved
        # far enough to be meaningful.
        if abs(averaged - self._fuel_displayed) >= self.FUEL_HYSTERESIS:
            self._fuel_displayed = float(round(averaged))

        return self._fuel_displayed

    def _maybe_request_obd(self):
        """Alternately request MAF (0x10) and intake air temp (0x0F) from the ECU.

        Both PIDs share one request slot so the bus load stays the same as when
        only MAF was polled.
        """
        if not self.hs_can:
            return
        now = time.time()
        if now - self._last_obd_request < self.obd_request_interval:
            return
        self._last_obd_request = now

        pid = self._obd_pids[self._obd_pid_index]
        self._obd_pid_index = (self._obd_pid_index + 1) % len(self._obd_pids)

        try:
            msg = can.Message(
                arbitration_id=OBD2.REQUEST_ID,
                data=[0x02, OBD2.MODE_CURRENT_DATA, pid, 0, 0, 0, 0, 0],
                is_extended_id=False,
            )
            self.hs_can.send(msg)
        except Exception as e:
            # Don't spam on transient send errors (bus off, listen-only, etc.)
            print(f"OBD-II request error (pid 0x{pid:02X}): {e}")

    def _apply_pedal_staleness(self):
        """Zero a pedal reading that has stopped arriving.

        Without this, a dropped or intermittent frame leaves the last value frozen
        on the dash - which reads as a stuck throttle.
        """
        now = time.time()
        if self.throttle_timestamp and now - self.throttle_timestamp > self.PEDAL_STALE_SEC:
            self.telemetry.throttle_percent = 0
        if self.brake_timestamp and now - self.brake_timestamp > self.BRAKE_STALE_SEC:
            self.telemetry.brake_percent = 0

    def _read_hs_can(self):
        """Read HS-CAN messages in background thread"""
        while self._running and self.hs_can:
            try:
                self._maybe_request_obd()
                self._apply_pedal_staleness()
                msg = self.hs_can.recv(timeout=0.1)
                if msg:
                    self.last_hs_msg_time = time.time()
                    self._process_hs_message(msg)
            except Exception as e:
                print(f"HS-CAN read error: {e}")
                time.sleep(0.1)
    
    def _read_ms_can(self):
        """Read MS-CAN messages in background thread"""
        while self._running and self.ms_can:
            try:
                msg = self.ms_can.recv(timeout=0.1)
                if msg:
                    self.last_ms_msg_time = time.time()
                    self._process_ms_message(msg)
            except Exception as e:
                print(f"MS-CAN read error: {e}")
                time.sleep(0.1)
    
    def _process_hs_message(self, msg):
        """Process high-speed CAN message"""
        can_id = msg.arbitration_id
        data = msg.data

        if can_id == OBD2.RESPONSE_ID:
            now = time.time()

            # Intake air temperature (PID 0x0F) shares the response ID with MAF.
            intake_f = CANParser.parse_intake_temp(data)
            if intake_f is not None:
                self.telemetry.intake_temp_f = intake_f
                if now - getattr(self, '_last_iat_log', 0.0) >= 10.0:
                    self._last_iat_log = now
                    print(f"IAT: {intake_f}F")
                return

            maf = CANParser.parse_maf(data)
            if maf > 0:
                # EMA-smooth MAF (polled, alternating with IAT) to reduce inst-MPG flicker.
                prev = self.telemetry.maf
                self.telemetry.maf = (0.5 * maf + 0.5 * prev) if prev > 0 else maf
                self.telemetry.maf_timestamp = now
                if now - getattr(self, '_last_maf_log', 0.0) >= 5.0:
                    self._last_maf_log = now
                    print(f"MAF: {maf:.1f} g/s (smoothed {self.telemetry.maf:.1f})")
            return

        if can_id == HSCanID.ENGINE_RPM:
            self.telemetry.rpm = CANParser.parse_rpm(data)
            self.telemetry.speed_kmh = CANParser.parse_speed(data)

            # The pedal position rides in the same engine frame (byte 6). Prefer it:
            # the legacy 0x200 decode is only a fallback for short/odd frames.
            pedal = CANParser.parse_throttle_engine(data)
            if pedal is not None:
                self.telemetry.throttle_percent = pedal
                self._engine_throttle_pct = pedal
                self.throttle_timestamp = time.time()

            # Estimate gear and clutch status after we have RPM and speed
            self._update_gear_estimation()

        elif can_id == HSCanID.THROTTLE:
            # Fallback only - do not overwrite a fresh read from the engine frame.
            if time.time() - self.throttle_timestamp > 0.5:
                self.telemetry.throttle_percent = CANParser.parse_throttle(data)
                self.throttle_timestamp = time.time()

            # Cross-check log while the pedal source is being confirmed on the car:
            # both decodes side by side make a wrong assumption obvious in seconds.
            now = time.time()
            if now - getattr(self, '_last_thr_log', 0.0) >= 5.0:
                self._last_thr_log = now
                print(f"THR: engine(0x201)={self._engine_throttle_pct}% "
                      f"legacy(0x200)={CANParser.parse_throttle(data)}%")

        elif can_id == HSCanID.GEAR_POSITION:
            can_gear = CANParser.parse_gear(data)
            # Use CAN neutral signal directly - the neutral safety switch is reliable
            # 2008 MX5 NC GT reliably detects Neutral via the neutral safety switch
            # Trust CAN neutral signal and store it so gear estimation can use it
            # Note: Gears 1-6 cannot be detected from CAN - must be estimated
            # Note: Reverse is detected from negative speed (CAN ID 0x201), not gear position
            if can_gear == 0:
                self.telemetry.is_in_neutral = True
                self.telemetry.is_in_reverse = False
            else:
                # can_gear is None - not in neutral, need to estimate gear from speed/RPM
                # is_in_reverse is set based on negative speed in _update_gear_estimation()
                self.telemetry.is_in_neutral = False
            # Don't set gear here - let _update_gear_estimation handle it
            # The gear estimation will check is_in_neutral and calculate from speed/RPM
            
        elif can_id == HSCanID.WHEEL_SPEEDS:
            speeds = CANParser.parse_wheel_speeds(data)
            # Store individual wheel speeds if needed
            # Calculate average speed if main speed not available
            
        elif can_id == HSCanID.STEERING_ANGLE:
            # Store steering angle if needed
            pass
            
        elif can_id == HSCanID.BRAKE_STATUS:
            self.telemetry.brake_percent = 100 if CANParser.parse_brake_status(data) else 0
            self.brake_timestamp = time.time()
            # Oil presence switch (TRUE/FALSE only)
            self.telemetry.oil_status = CANParser.parse_oil_pressure(data)
            
        elif can_id == HSCanID.ENGINE_TEMP:
            self.telemetry.coolant_temp_f = CANParser.parse_coolant_temp(data)
            self.telemetry.ambient_temp_f = CANParser.parse_ambient_temp(data)
            
        elif can_id == HSCanID.FUEL_LEVEL:
            # Apply EMA smoothing + hysteresis to reduce fluctuations
            raw_fuel = CANParser.parse_fuel_level(data)
            smoothed_fuel = self._smooth_fuel_level(raw_fuel)
            self.telemetry.fuel_level_percent = smoothed_fuel
            
        elif can_id == HSCanID.BATTERY_VOLTAGE:
            self.telemetry.voltage = CANParser.parse_voltage(data)
    
    def _process_ms_message(self, msg):
        """Process medium-speed CAN message"""
        can_id = msg.arbitration_id
        data = msg.data
        
        # Steering wheel cruise controls (only cruise buttons readable on MS-CAN)
        # NOTE: Audio buttons (0x240) are NOT available on this bus
        if can_id == MSCanID.SWC_CRUISE:
            if self.swc_handler:
                self.swc_handler.process_can_message(can_id, data)
        
        # Lighting status
        elif can_id == MSCanID.LIGHTING or can_id == MSCanID.LIGHTING_STATUS:
            # Parse headlight status
            headlights, high_beams = CANParser.parse_headlights(data)
            self.telemetry.headlights_on = headlights
            self.telemetry.high_beams_on = high_beams
            # Legacy fields (kept for compatibility)
            if len(data) >= 1:
                self.telemetry.high_beam_on = bool(data[0] & 0x02)
                self.telemetry.fog_light_on = bool(data[0] & 0x04)
        
        # Door status
        elif can_id == MSCanID.DOORS:
            if len(data) >= 1:
                self.telemetry.door_ajar = bool(data[0] & 0x0F)  # Any door open
    
    def is_receiving_data(self) -> bool:
        """Check if we're receiving CAN data"""
        now = time.time()
        hs_ok = (now - self.last_hs_msg_time) < 1.0 if self.hs_can else False
        ms_ok = (now - self.last_ms_msg_time) < 1.0 if self.ms_can else False
        return hs_ok or ms_ok

    def _update_gear_estimation(self):
        """Update gear estimation based on current speed and RPM
        
        Called after receiving RPM/speed data. Uses CAN neutral signal and
        speed/RPM ratio to determine:
        1. If speed is negative - show R (reverse)
        2. If in neutral (CAN signal) - show N with recommended gear color
        3. If ratio matches a gear - show that gear (1-6)
        4. If ratio doesn't match - show recommended gear for speed
        
        Color coding shows if RPM is appropriate for the recommended gear:
        - Green: RPM is good for the speed
        - Red: RPM too high (shift up or let off gas)
        - Blue: RPM too low (shift down or more gas)
        """
        # Check for reverse first - negative speed from CAN indicates reverse
        # Note: is_in_reverse flag is no longer set from gear position CAN message
        # Reverse is detected solely from negative speed value
        #
        # Hysteresis: At low reverse speeds, CAN speed oscillates between -1 and 0
        # (raw value bounces around the 10000 zero-offset). Without hysteresis, gear
        # flickers between R and 1. We hold reverse state for 500ms after speed
        # returns to 0 to prevent this.
        now = time.time()
        if self.telemetry.speed_kmh < 0:
            # Actively in reverse - extend hold timer
            self._reverse_hold_until = now + self._REVERSE_HOLD_SECONDS
            self.telemetry.gear = -1  # -1 = Reverse
            self.telemetry.is_in_reverse = True  # Set for other code that might check this
            self.telemetry.gear_estimated = False  # Direct detection, not estimated
            self.telemetry.clutch_engaged = False
            self.telemetry.recommended_gear = -1
            self.telemetry.gear_color = 'green'
            return
        elif now < self._reverse_hold_until and self.telemetry.speed_kmh == 0:
            # Speed returned to 0 but we were just in reverse - hold reverse state
            # Only hold if speed is exactly 0 (not positive/moving forward)
            self.telemetry.gear = -1  # -1 = Reverse
            self.telemetry.is_in_reverse = True
            self.telemetry.gear_estimated = False
            self.telemetry.clutch_engaged = False
            self.telemetry.recommended_gear = -1
            self.telemetry.gear_color = 'green'
            return
        else:
            self.telemetry.is_in_reverse = False  # Not in reverse
            self._reverse_hold_until = 0  # Clear hold timer
        
        # speed_kmh is kilometres per hour everywhere in the system; the gear
        # estimator's ratio table is in MPH, so convert here and nowhere else.
        speed_mph = self.telemetry.speed_kmh * 0.621371
        
        # Get gear estimation with all new fields
        result = self.gear_estimator.estimate_gear(
            speed_mph, 
            self.telemetry.rpm,
            self.telemetry.is_in_neutral
        )
        
        # Unpack the 5-tuple result
        estimated_gear, clutch_engaged, confidence, recommended_gear, gear_color = result
        
        # Update all telemetry fields
        self.telemetry.gear = estimated_gear
        self.telemetry.gear_estimated = (confidence < 1.0)  # True if not 100% from CAN
        self.telemetry.clutch_engaged = clutch_engaged
        self.telemetry.recommended_gear = recommended_gear
        self.telemetry.gear_color = gear_color


# =============================================================================
# Setup Instructions
# =============================================================================
"""
To use CAN on Raspberry Pi with MCP2515:

1. Enable SPI:
   sudo raspi-config
   -> Interface Options -> SPI -> Enable

2. Add to /boot/config.txt:
   dtparam=spi=on
   dtoverlay=mcp2515-can0,oscillator=8000000,interrupt=25
   dtoverlay=mcp2515-can1,oscillator=8000000,interrupt=24,spi0-1

3. Install python-can:
   pip install python-can

4. Bring up CAN interfaces (if using socketcan):
   sudo ip link set can0 up type can bitrate 500000 listen-only on
   sudo ip link set can1 up type can bitrate 125000 listen-only on

5. Test CAN:
   candump can0
   candump can1

NOTE: listen-only mode prevents transmission to car CAN bus (read-only)
"""
