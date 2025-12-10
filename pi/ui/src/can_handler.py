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

import threading
import time
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
    ENGINE_TEMP = 0x420         # Coolant and oil temps
    FUEL_LEVEL = 0x430          # Fuel level
    BATTERY_VOLTAGE = 0x440     # System voltage


# MS-CAN (125kbps) - Body/Accessories  
class MSCanID:
    """Medium-Speed CAN Message IDs"""
    SWC_AUDIO = 0x240           # Steering wheel audio buttons
    SWC_CRUISE = 0x250          # Steering wheel cruise buttons
    LIGHTING = 0x290            # Headlights, turn signals
    CLIMATE = 0x350             # AC status
    DOORS = 0x430               # Door ajar status
    ODOMETER = 0x450            # Odometer reading


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
        """Parse vehicle speed from engine message (ID 0x201)
        Typically bytes 4-5 or similar, in km/h
        """
        if len(data) >= 6:
            raw = (data[4] << 8) | data[5]
            # Speed in km/h, may need scaling
            return raw // 100
        return 0
    
    @staticmethod
    def parse_throttle(data: bytes) -> int:
        """Parse throttle position (ID 0x200)
        Usually 0-255 -> 0-100%
        """
        if len(data) >= 5:
            return int(data[4] * 100 / 255)
        return 0
    
    @staticmethod
    def parse_gear(data: bytes) -> int:
        """Parse gear position (ID 0x231)
        0=N, 1-6=gears, 7+=Reverse
        """
        if len(data) >= 1:
            gear = data[0] & 0x0F
            if gear == 0:
                return 0  # Neutral
            elif gear <= 6:
                return gear
            else:
                return -1  # Reverse
        return 0
    
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
    def parse_oil_temp(data: bytes) -> int:
        """Parse oil temperature (ID 0x420)
        Returns temperature in Fahrenheit
        """
        if len(data) >= 2:
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


# =============================================================================
# CAN Handler Class
# =============================================================================

class CANHandler:
    """Manages CAN bus communication with MCP2515 modules"""
    
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
        
    def start(self) -> bool:
        """Initialize and start CAN bus reading"""
        if not CAN_AVAILABLE:
            print("CAN library not available")
            return False
        
        try:
            # Initialize HS-CAN (CE0, 500kbps)
            self.hs_can = can.interface.Bus(
                channel='can0',
                bustype='socketcan',
                bitrate=500000
            )
            print("HS-CAN (can0) initialized at 500kbps")
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
            # Initialize MS-CAN (CE1, 125kbps)
            self.ms_can = can.interface.Bus(
                channel='can1',
                bustype='socketcan',
                bitrate=125000
            )
            print("MS-CAN (can1) initialized at 125kbps")
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
    
    def _read_hs_can(self):
        """Read HS-CAN messages in background thread"""
        while self._running and self.hs_can:
            try:
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
        
        if can_id == HSCanID.ENGINE_RPM:
            self.telemetry.rpm = CANParser.parse_rpm(data)
            self.telemetry.speed_kmh = CANParser.parse_speed(data)
            
        elif can_id == HSCanID.THROTTLE:
            self.telemetry.throttle_percent = CANParser.parse_throttle(data)
            
        elif can_id == HSCanID.GEAR_POSITION:
            self.telemetry.gear = CANParser.parse_gear(data)
            
        elif can_id == HSCanID.WHEEL_SPEEDS:
            speeds = CANParser.parse_wheel_speeds(data)
            # Store individual wheel speeds if needed
            # Calculate average speed if main speed not available
            
        elif can_id == HSCanID.STEERING_ANGLE:
            # Store steering angle if needed
            pass
            
        elif can_id == HSCanID.BRAKE_STATUS:
            self.telemetry.brake_percent = 100 if CANParser.parse_brake_status(data) else 0
            
        elif can_id == HSCanID.ENGINE_TEMP:
            self.telemetry.coolant_temp_f = CANParser.parse_coolant_temp(data)
            self.telemetry.oil_temp_f = CANParser.parse_oil_temp(data)
            
        elif can_id == HSCanID.FUEL_LEVEL:
            self.telemetry.fuel_level_percent = CANParser.parse_fuel_level(data)
            
        elif can_id == HSCanID.BATTERY_VOLTAGE:
            self.telemetry.voltage = CANParser.parse_voltage(data)
    
    def _process_ms_message(self, msg):
        """Process medium-speed CAN message"""
        can_id = msg.arbitration_id
        data = msg.data
        
        # Steering wheel controls
        if can_id == MSCanID.SWC_AUDIO or can_id == MSCanID.SWC_CRUISE:
            if self.swc_handler:
                self.swc_handler.process_can_message(can_id, data)
        
        # Lighting status
        elif can_id == MSCanID.LIGHTING:
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
   sudo ip link set can0 up type can bitrate 500000
   sudo ip link set can1 up type can bitrate 125000

5. Test CAN:
   candump can0
   candump can1
"""
