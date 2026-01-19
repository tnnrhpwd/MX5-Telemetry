"""
Telemetry Data Structures for Raspberry Pi UI

Shared data structures for telemetry information received from CAN bus.
"""

from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class GearPosition(Enum):
    """Gear position values"""
    NEUTRAL = 0
    FIRST = 1
    SECOND = 2
    THIRD = 3
    FOURTH = 4
    FIFTH = 5
    SIXTH = 6
    REVERSE = -1


@dataclass
class TelemetryData:
    """Complete telemetry data from vehicle"""
    
    # Engine/Drivetrain (HS-CAN)
    rpm: int = 0
    speed_kmh: int = 0
    gear: int = 0
    gear_estimated: bool = False  # True if gear was estimated from speed/RPM ratio
    clutch_engaged: bool = False  # True if clutch appears to be pressed
    throttle_percent: int = 0
    brake_active: bool = False
    
    # Temperatures
    coolant_temp_f: int = 0
    intake_temp_f: int = 0
    ambient_temp_f: int = 0
    
    # Oil status (TRUE = oil present, FALSE = no oil/warning)
    oil_status: bool = False
    
    # Wheel speeds (individual)
    wheel_speed_fl: float = 0.0
    wheel_speed_fr: float = 0.0
    wheel_speed_rl: float = 0.0
    wheel_speed_rr: float = 0.0
    
    # Steering
    steering_angle: float = 0.0
    
    # Fuel
    fuel_level_percent: float = 0.0
    instant_mpg: float = 0.0
    average_mpg: float = 0.0
    range_miles: int = 0
    
    # Odometer
    odometer_miles: int = 0
    
    # Lights/Accessories (MS-CAN)
    headlights_on: bool = False
    high_beams_on: bool = False
    turn_signal_left: bool = False
    turn_signal_right: bool = False
    ac_running: bool = False
    
    # IMU - Raw accelerometer (includes gravity)
    g_lateral: float = 0.0       # Accel X (left/right)
    g_longitudinal: float = 0.0  # Accel Y (forward/back)
    g_vertical: float = 0.0      # Accel Z (up/down)
    
    # IMU - Gyroscope (rotation rates in deg/sec)
    gyro_x: float = 0.0
    gyro_y: float = 0.0
    gyro_z: float = 0.0
    
    # IMU - Pure linear acceleration (gravity subtracted)
    linear_accel_x: float = 0.0
    linear_accel_y: float = 0.0
    
    # IMU - Orientation (from gyro integration)
    orientation_pitch: float = 0.0
    orientation_roll: float = 0.0
    
    # TPMS (from ESP32-S3 via BLE)
    tire_pressure: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    tire_temp: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    tire_battery: List[int] = field(default_factory=lambda: [0, 0, 0, 0])
    
    # Timestamps
    last_update_ms: int = 0
    can_connected: bool = False
    tpms_connected: bool = False


@dataclass
class UISettings:
    """UI configuration settings"""
    
    # Display
    brightness: int = 80  # 0-100%
    theme: str = "dark"  # "dark" or "light"
    
    # Units
    use_mph: bool = True
    use_fahrenheit: bool = True
    use_psi: bool = True
    
    # Alerts
    shift_rpm: int = 6500
    redline_rpm: int = 7200
    coolant_warn_f: int = 220
    oil_warn_f: int = 250
    tire_low_psi: float = 28.0
    tire_high_psi: float = 36.0
    
    # Active device
    pi_active: bool = True  # True = Pi has SWC focus, False = ESP32


@dataclass 
class AppState:
    """Application state"""
    current_screen: str = "home"
    previous_screen: str = "home"
    menu_selection: int = 0
    is_sleeping: bool = False
    device_focus: str = "pi"  # "pi" or "esp32"


# Screen IDs
SCREEN_HOME = "home"
SCREEN_MAPS = "maps"
SCREEN_MUSIC = "music"
SCREEN_TELEMETRY = "telemetry"
SCREEN_TPMS = "tpms"
SCREEN_SETTINGS = "settings"

SCREENS = [
    SCREEN_HOME,
    SCREEN_MAPS,
    SCREEN_MUSIC,
    SCREEN_TELEMETRY,
    SCREEN_TPMS,
    SCREEN_SETTINGS,
]

SCREEN_NAMES = {
    SCREEN_HOME: "Home",
    SCREEN_MAPS: "Maps",
    SCREEN_MUSIC: "Music",
    SCREEN_TELEMETRY: "Telemetry",
    SCREEN_TPMS: "TPMS",
    SCREEN_SETTINGS: "Settings",
}

SCREEN_ICONS = {
    SCREEN_HOME: "🏠",
    SCREEN_MAPS: "🗺️",
    SCREEN_MUSIC: "🎵",
    SCREEN_TELEMETRY: "📊",
    SCREEN_TPMS: "🔧",
    SCREEN_SETTINGS: "⚙️",
}
