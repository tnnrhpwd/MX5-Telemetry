#!/usr/bin/env python3
"""
MX5 Telemetry - Raspberry Pi Display Application

This is the production display application for the Raspberry Pi 4B.
UI is identical to the simulator at tools/simulators/ui_simulator/combined_simulator.py

Hardware:
    - Raspberry Pi 4B
    - 800x480 HDMI Display (7" or similar)
    - Connected to Arduino via serial for telemetry data
    - SWC buttons via GPIO or CAN bus

Screens (synchronized with ESP32):
    1. Overview    - Gear, speed, TPMS summary, alerts
    2. RPM/Speed   - Primary driving data
    3. TPMS        - Tire pressure and temperatures
    4. Engine      - Coolant, oil, fuel, voltage
    5. G-Force     - Lateral and longitudinal G
    6. Settings    - Configuration options

Usage:
    python3 main.py              # Normal mode (data source set in Settings)
    python3 main.py --fullscreen # Fullscreen mode for production
    python3 main.py -f           # Fullscreen shortcut
    
    Data source (Demo/CAN Bus) is configured in Settings > Data Source

Requirements:
    pip install pygame

Compatible with pygame 1.9.x and 2.x
"""

import os
# Set SDL audio driver before importing pygame (fixes HDMI audio on Pi)
os.environ.setdefault('SDL_AUDIODRIVER', 'alsa')

import pygame
import pygame.sndarray
import math
import sys
import os
import time
import argparse
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

# Try to import numpy for sound generation
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    print("Warning: numpy not installed. Sound effects disabled.")

# Try to import CAN handler (optional on non-Pi systems)
try:
    from can_handler import CANHandler, CAN_AVAILABLE
except ImportError:
    CAN_AVAILABLE = False
    CANHandler = None

# Try to import SWC handler for steering wheel controls
try:
    from swc_handler import SWCHandler, ButtonEvent, BUTTON_NAMES
    SWC_AVAILABLE = True
except ImportError:
    SWC_AVAILABLE = False
    SWCHandler = None

# Try to import ESP32 serial handler (optional on non-Pi systems)
try:
    from esp32_serial_handler import ESP32SerialHandler, SERIAL_AVAILABLE
except ImportError:
    SERIAL_AVAILABLE = False
    ESP32SerialHandler = None

# =============================================================================
# CONSTANTS
# =============================================================================

# Display size - will be updated at runtime based on actual display
# These are defaults, actual values set in PiDisplayApp.__init__
PI_WIDTH = 800
PI_HEIGHT = 480

# Modern Color Palette (matching simulator exactly)
COLOR_BG = (12, 12, 18)
COLOR_BG_DARK = (8, 8, 12)
COLOR_BG_CARD = (22, 22, 32)
COLOR_BG_ELEVATED = (32, 32, 45)
COLOR_WHITE = (245, 245, 250)
COLOR_GRAY = (140, 140, 160)
COLOR_DARK_GRAY = (55, 55, 70)
COLOR_RED = (255, 70, 85)
COLOR_GREEN = (50, 215, 130)
COLOR_SUCCESS = (50, 215, 130)  # Alias for green - used in diagnostics
COLOR_BLUE = (65, 135, 255)
COLOR_YELLOW = (255, 210, 60)
COLOR_ORANGE = (255, 140, 50)
COLOR_CYAN = (50, 220, 255)
COLOR_ACCENT = (100, 140, 255)
COLOR_PURPLE = (175, 130, 255)
COLOR_PINK = (255, 100, 180)
COLOR_TEAL = (45, 200, 190)

# =============================================================================
# ENUMS AND DATA CLASSES
# =============================================================================

class ButtonEvent(Enum):
    """Button events - cruise control buttons only (volume buttons not on CAN bus)"""
    NONE = auto()
    ON_OFF = auto()      # Select / Enter / Confirm edit
    CANCEL = auto()      # Back / Exit edit mode
    RES_PLUS = auto()    # UP - Previous page / Navigate up / Increase value
    SET_MINUS = auto()   # DOWN - Next page / Navigate down / Decrease value


class Screen(Enum):
    OVERVIEW = 0
    RPM_SPEED = 1
    TPMS = 2
    ENGINE = 3
    GFORCE = 4
    DIAGNOSTICS = 5
    SYSTEM = 6
    SETTINGS = 7


SCREEN_NAMES = {
    Screen.OVERVIEW: "Overview",
    Screen.RPM_SPEED: "RPM / Speed",
    Screen.TPMS: "Tire Pressure",
    Screen.ENGINE: "Engine",
    Screen.GFORCE: "G-Force",
    Screen.DIAGNOSTICS: "Diagnostics",
    Screen.SYSTEM: "System",
    Screen.SETTINGS: "Settings",
}


@dataclass
class TelemetryData:
    rpm: int = 0
    speed_kmh: int = 0
    gear: int = 0
    throttle_percent: int = 0
    brake_percent: int = 0
    coolant_temp_f: int = 0
    oil_temp_f: int = 0
    oil_pressure_psi: float = 0.0
    intake_temp_f: int = 0
    ambient_temp_f: int = 0
    fuel_level_percent: float = 0.0
    voltage: float = 0.0
    tire_pressure: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    tire_temp: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    tpms_last_update_str: List[str] = field(default_factory=lambda: ["--:--:--", "--:--:--", "--:--:--", "--:--:--"])  # HH:MM:SS per tire
    tpms_connected: bool = False  # True if TPMS data has been received
    g_lateral: float = 0.0
    g_longitudinal: float = 0.0
    lap_time_ms: int = 0
    best_lap_ms: int = 0
    
    # Diagnostics data
    check_engine_light: bool = False
    abs_warning: bool = False
    traction_control_off: bool = False
    traction_control_active: bool = False
    oil_pressure_warning: bool = False
    battery_warning: bool = False
    door_ajar: bool = False
    seatbelt_warning: bool = False
    airbag_warning: bool = False
    brake_warning: bool = False
    high_beam_on: bool = False
    fog_light_on: bool = False
    
    # DTC codes
    dtc_codes: List[str] = field(default_factory=list)
    dtc_count: int = 0
    
    # Wheel slip (for traction display)
    wheel_slip: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])


# LED Sequence modes (must match Arduino enum)
LED_SEQ_CENTER_OUT = 1      # Default: Fill from edges toward center (mirrored)
LED_SEQ_LEFT_TO_RIGHT = 2   # Fill left to right (double resolution)
LED_SEQ_RIGHT_TO_LEFT = 3   # Fill right to left
LED_SEQ_CENTER_IN = 4       # Fill from center outward to edges
LED_SEQ_COUNT = 4           # Total number of sequences

LED_SEQUENCE_NAMES = {
    LED_SEQ_CENTER_OUT: "Center-Out",
    LED_SEQ_LEFT_TO_RIGHT: "Left-Right",
    LED_SEQ_RIGHT_TO_LEFT: "Right-Left",
    LED_SEQ_CENTER_IN: "Center-In",
}


@dataclass
class Settings:
    brightness: int = 80
    volume: int = 70  # Sound effects volume (0-100)
    shift_rpm: int = 6500
    redline_rpm: int = 7200
    use_mph: bool = True
    tire_low_psi: float = 28.0
    tire_high_psi: float = 36.0
    coolant_warn_f: int = 220
    oil_warn_f: int = 260
    demo_mode: bool = False  # False = use real CAN data, True = simulated data
    led_sequence: int = LED_SEQ_CENTER_OUT  # LED sequence mode (1-4)


# =============================================================================
# SOUND MANAGER
# =============================================================================

class SoundManager:
    """Manages UI sound effects using pygame.mixer"""
    
    def __init__(self, volume: int = 70):
        """Initialize sound system"""
        self._volume = volume / 100.0
        self._enabled = True
        self._sounds = {}
        self._stereo = False
        
        if not NUMPY_AVAILABLE:
            print("Sound effects disabled (numpy not available)")
            self._enabled = False
            return
        
        try:
            # Check if mixer is already initialized by pygame.init()
            mixer_info = pygame.mixer.get_init()
            print(f"Mixer already init: {mixer_info}")
            
            if mixer_info:
                # Mixer already initialized - reinit with low-latency settings
                freq, fmt, channels = mixer_info
                self._stereo = channels == 2
                # Always reinitialize with low-latency buffer
                pygame.mixer.quit()
                pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=256)
                mixer_info = pygame.mixer.get_init()
                print(f"Mixer reinitialized: {mixer_info}")
            else:
                pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=256)
                mixer_info = pygame.mixer.get_init()
                self._stereo = mixer_info[2] == 2 if mixer_info else False
                print(f"Mixer initialized: {mixer_info}")
            
            self._generate_sounds()
            print(f"Sound effects enabled: {len(self._sounds)} sounds, stereo={self._stereo}, volume={self._volume}")
        except Exception as e:
            print(f"Sound init failed: {e}")
            self._enabled = False
    
    def _make_sound(self, wave: 'np.ndarray') -> pygame.mixer.Sound:
        """Create sound from wave array, handling mono/stereo conversion"""
        if self._stereo:
            # Convert mono to stereo by duplicating channel
            stereo_wave = np.column_stack((wave, wave))
            return pygame.sndarray.make_sound(stereo_wave)
        return pygame.sndarray.make_sound(wave)
    
    def _generate_sounds(self):
        """Generate modern UI sound effects programmatically"""
        sample_rate = 22050
        
        # Navigate sound - modern soft pop with harmonics
        duration = 0.06
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        # Layer multiple frequencies for richer sound
        wave = (np.sin(2 * np.pi * 1400 * t) * 0.15 +  # High
                np.sin(2 * np.pi * 700 * t) * 0.2 +    # Mid
                np.sin(2 * np.pi * 350 * t) * 0.1)     # Low warmth
        # Snappy attack, quick decay
        envelope = np.exp(-t * 50) * (1 - np.exp(-t * 500))
        wave = (wave * envelope * 32767).astype(np.int16)
        self._sounds['navigate'] = self._make_sound(wave)
        
        # Select sound - satisfying two-tone confirmation (like modern UI)
        duration = 0.12
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        # Rising two-note chime
        freq1 = 880  # A5
        freq2 = 1320  # E6 (perfect fifth up)
        # First note then second
        wave1 = np.sin(2 * np.pi * freq1 * t) * np.exp(-t * 25)
        wave2 = np.sin(2 * np.pi * freq2 * t) * np.exp(-(t - 0.04) * 20) * (t > 0.04)
        wave = (wave1 * 0.25 + wave2 * 0.2)
        # Add subtle harmonics
        wave += np.sin(2 * np.pi * freq1 * 2 * t) * 0.05 * np.exp(-t * 30)
        envelope = 1 - np.exp(-t * 200)  # Quick attack
        wave = (wave * envelope * 32767).astype(np.int16)
        self._sounds['select'] = self._make_sound(wave)
        
        # Adjust sound - subtle tick with body
        duration = 0.04
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        # Crisp tick with subtle sub
        wave = (np.sin(2 * np.pi * 1800 * t) * 0.15 +
                np.sin(2 * np.pi * 900 * t) * 0.1 +
                np.sin(2 * np.pi * 300 * t) * 0.08)
        envelope = np.exp(-t * 80) * (1 - np.exp(-t * 800))
        wave = (wave * envelope * 32767).astype(np.int16)
        self._sounds['adjust'] = self._make_sound(wave)
        
        # Back/cancel sound - soft descending whoosh
        duration = 0.1
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        # Smooth frequency sweep down
        freq_start, freq_end = 800, 300
        freq = freq_start + (freq_end - freq_start) * (t / duration) ** 0.7
        phase = 2 * np.pi * np.cumsum(freq) / sample_rate
        wave = np.sin(phase) * 0.2
        # Add noise for "whoosh" texture
        noise = np.random.randn(len(t)) * 0.03
        wave += noise * np.exp(-t * 30)
        envelope = np.sin(np.pi * t / duration) ** 0.5
        wave = (wave * envelope * 32767).astype(np.int16)
        self._sounds['back'] = self._make_sound(wave)
        
        # Error sound - gentle warning pulse
        duration = 0.2
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        # Two quick low pulses
        freq = 280
        pulse1 = np.sin(2 * np.pi * freq * t) * (t < 0.08) * np.exp(-((t - 0.04) ** 2) * 500)
        pulse2 = np.sin(2 * np.pi * freq * 0.9 * t) * (t > 0.1) * np.exp(-((t - 0.14) ** 2) * 500)
        wave = (pulse1 + pulse2) * 0.3
        # Add harmonics for character
        wave += np.sin(2 * np.pi * freq * 2 * t) * 0.1 * (pulse1 + pulse2) / 0.3
        wave = (wave * 32767).astype(np.int16)
        self._sounds['error'] = self._make_sound(wave)
        
        self._update_volumes()
    
    def _update_volumes(self):
        """Update volume for all sounds"""
        for sound in self._sounds.values():
            sound.set_volume(self._volume)
    
    def set_volume(self, volume: int):
        """Set volume (0-100)"""
        self._volume = max(0, min(100, volume)) / 100.0
        self._update_volumes()
    
    def play(self, sound_name: str):
        """Play a sound effect"""
        if self._enabled and sound_name in self._sounds and self._volume > 0:
            print(f"Playing sound: {sound_name}")  # Debug
            self._sounds[sound_name].play()


# =============================================================================
# MAIN APPLICATION
# =============================================================================

class TransitionType(Enum):
    """Page transition animation types"""
    NONE = auto()
    SLIDE_LEFT = auto()   # Going to next screen
    SLIDE_RIGHT = auto()  # Going to previous screen
    FADE = auto()         # Fade transition
    ZOOM = auto()         # Zoom effect


class PiDisplayApp:
    def __init__(self, fullscreen: bool = False):
        global PI_WIDTH, PI_HEIGHT
        pygame.init()
        
        # UI is designed for 800x480, we render to this then scale to display
        PI_WIDTH = 800
        PI_HEIGHT = 480
        
        if fullscreen:
            # Get display info before setting mode
            info = pygame.display.Info()
            print(f"DISPLAY: pygame.display.Info() = {info.current_w}x{info.current_h}")
            
            # Fullscreen: auto-detect display resolution and scale UI to fit
            self.display_surface = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            self.display_width, self.display_height = self.display_surface.get_size()
            print(f"DISPLAY: Fullscreen set to {self.display_width}x{self.display_height}")
            
            # Render to 800x480 surface, then scale to display
            self.screen = pygame.Surface((PI_WIDTH, PI_HEIGHT))
            self.scale_output = True
            print(f"DISPLAY: Rendering UI at {PI_WIDTH}x{PI_HEIGHT}, scaling to {self.display_width}x{self.display_height}")
        else:
            # Windowed mode: render directly at 800x480
            self.screen = pygame.display.set_mode((PI_WIDTH, PI_HEIGHT), 0)
            self.display_surface = self.screen
            self.display_width, self.display_height = PI_WIDTH, PI_HEIGHT
            self.scale_output = False
            print(f"DISPLAY: Windowed mode at {PI_WIDTH}x{PI_HEIGHT}")
        
        pygame.display.set_caption("MX5 Telemetry Display")
        
        # State
        self.current_screen = Screen.OVERVIEW
        self.sleeping = False
        self.demo_rpm_dir = 1
        self.show_exit_dialog = False  # Exit confirmation dialog state
        
        # Page transition animation state
        self.transition_type = TransitionType.NONE
        self.transition_from_screen = Screen.OVERVIEW
        self.transition_to_screen = Screen.OVERVIEW
        self.transition_start_time = 0
        self.transition_duration = 0.2  # 200ms
        self.transition_progress = 0.0
        
        # Offscreen surfaces for transition effects
        self.transition_surface_old = None
        self.transition_surface_new = None
        
        # Lap timer state
        self.lap_timer_running = False
        self.lap_timer_start_time = 0
        
        # Settings navigation
        self.settings_selection = 0
        self.settings_edit_mode = False
        
        # Data
        self.telemetry = TelemetryData()
        self.settings = Settings()  # demo_mode is controlled via settings.demo_mode
        
        # Sound manager
        self.sound = SoundManager(self.settings.volume)
        
        # Load car image for TPMS display
        self.car_image = None
        self.car_image_small = None
        self._load_car_image()
        
        # Fonts
        self.font_huge = pygame.font.Font(None, 120)
        self.font_large = pygame.font.Font(None, 80)
        self.font_medium = pygame.font.Font(None, 56)
        self.font_small = pygame.font.Font(None, 32)
        self.font_tiny = pygame.font.Font(None, 24)
        
        # Clock
        self.clock = pygame.time.Clock()
        
        # Serial connection (for production)
        self.serial_conn = None
        
        # CAN bus handler (for real data from vehicle)
        self.can_handler = None
        
        # SWC handler (steering wheel controls)
        self.swc_handler = SWCHandler() if SWC_AVAILABLE and SWCHandler else None
        
        # ESP32 serial handler (for TPMS + IMU data)
        self.esp32_handler = None
        
        # Arduino serial handler (for LED sequence commands)
        self.arduino_serial = None
        
        # Initialize data sources based on settings
        self._init_data_sources()
    
    def _init_data_sources(self):
        """Initialize or reinitialize CAN and ESP32 handlers based on demo_mode setting"""
        # Stop existing handlers if running
        if self.can_handler:
            self.can_handler.stop()
            self.can_handler = None
        if self.esp32_handler:
            self.esp32_handler.stop()
            self.esp32_handler = None
        
        # Initialize Arduino serial for LED sequence commands (optional, non-blocking)
        try:
            self._init_arduino_serial()
        except Exception as e:
            print(f"  ✗ Arduino serial init failed: {e}")
        
        if self.settings.demo_mode:
            print("Data Source: DEMO MODE - using simulated data")
            # Still try to connect ESP32 for display sync even in demo mode
            self._init_esp32_handler()
            return
        
        # Production mode - initialize real data sources
        print("Data Source: CAN BUS - using real vehicle data")
        
        # CAN bus handler
        if CAN_AVAILABLE and CANHandler:
            print("  Initializing CAN bus...")
            self.can_handler = CANHandler(self.telemetry, swc_handler=self.swc_handler)
            if self.can_handler.start():
                print("  ✓ CAN bus connected - reading RPM, speed, gear, temps")
                if self.swc_handler:
                    print("  ✓ Steering wheel controls enabled (MS-CAN)")
            else:
                print("  ✗ CAN bus failed - check MCP2515 wiring")
                self.can_handler = None
        else:
            print("  ✗ CAN library not available - install python-can")
        
        # ESP32 serial handler
        self._init_esp32_handler()
    
    def _init_arduino_serial(self):
        """Initialize serial connection to Arduino for LED sequence commands (optional)"""
        if not SERIAL_AVAILABLE:
            # Serial not available - this is fine, LED sequences just won't sync
            return
        
        # Close existing connection if any
        if self.arduino_serial:
            try:
                self.arduino_serial.close()
            except:
                pass
            self.arduino_serial = None
        
        # Arduino serial port options (different from ESP32)
        # Pi GPIO UART: /dev/serial0 (pins 14/15 - TXD0/RXD0) 
        # Or USB: /dev/ttyUSB0, /dev/ttyUSB1
        arduino_ports = ['/dev/serial0', '/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyAMA0']
        
        for port in arduino_ports:
            try:
                import serial
                self.arduino_serial = serial.Serial(
                    port=port,
                    baudrate=9600,  # Match Arduino SoftwareSerial baud rate
                    timeout=0.05,   # Very short timeout to avoid blocking
                    write_timeout=0.05
                )
                print(f"  ✓ Arduino serial connected on {port} (LED sequence control)")
                # Send current LED sequence setting on connect
                self._send_led_sequence_to_arduino()
                return
            except Exception:
                # Port not available - try next one
                continue
        
        # No Arduino serial found - this is normal if not wired up
        # LED sequences will just use Arduino's default
    
    def _init_esp32_handler(self):
        """Initialize ESP32 serial handler for display sync"""
        if SERIAL_AVAILABLE and ESP32SerialHandler:
            print("  Initializing ESP32 serial...")
            self.esp32_handler = ESP32SerialHandler(
                self.telemetry, 
                on_screen_change=self._on_esp32_screen_change,
                on_setting_change=self._on_esp32_setting_change,
                on_settings_sync=self._on_esp32_settings_sync
            )
            # Set up selection change callback
            self.esp32_handler.on_selection_change = self._on_esp32_selection_change
            if self.esp32_handler.start():
                print("  ✓ ESP32 connected - display sync enabled")
                # Sync initial screen
                self._sync_esp32_screen()
                # Send initial settings to ESP32
                self._sync_settings_to_esp32()
                # Register SWC lock callback to sync lock state to ESP32
                if self.swc_handler:
                    self.swc_handler.add_lock_callback(self._on_nav_lock_changed)
                    print("  ✓ Navigation lock callback registered")
            else:
                print("  ✗ ESP32 serial failed - check USB connection")
                self.esp32_handler = None
        else:
            print("  ✗ Serial library not available - install pyserial")
    
    def _on_nav_lock_changed(self, locked: bool):
        """Callback when navigation lock state changes - sync to ESP32"""
        lock_status = "LOCKED" if locked else "UNLOCKED"
        print(f"Navigation {lock_status}")
        if self.esp32_handler:
            self.esp32_handler.send_nav_lock(locked)
    
    def _on_esp32_screen_change(self, screen_index: int):
        """Callback when ESP32 display changes screen via touch (bidirectional sync)"""
        # Map ESP32 screen index to Pi Screen enum
        # ESP32: 0=Overview, 1=RPM, 2=TPMS, 3=Engine, 4=GForce, 5=Diagnostics, 6=System, 7=Settings
        # Pi: 0=Overview, 1=RPM_SPEED, 2=TPMS, 3=ENGINE, 4=GFORCE, 5=DIAGNOSTICS, 6=SYSTEM, 7=SETTINGS
        if 0 <= screen_index <= 7:
            screens = list(Screen)
            if screen_index < len(screens):
                target_screen = screens[screen_index]
                # Only start transition if:
                # 1. Not already on this screen
                # 2. Not currently transitioning (Pi initiated the change)
                # 3. Not transitioning TO this screen already
                if (target_screen != self.current_screen and 
                    not self._is_transitioning() and
                    (not hasattr(self, 'transition_to_screen') or target_screen != self.transition_to_screen)):
                    direction = 'next' if screen_index > self.current_screen.value else 'prev'
                    self._start_transition(target_screen, 
                        TransitionType.SLIDE_LEFT if direction == 'next' else TransitionType.SLIDE_RIGHT)
                    print(f"Pi: Synced to screen {screen_index} ({target_screen.name})")
                else:
                    print(f"Pi: Screen {screen_index} already current/transitioning, skipping")
    
    def _on_esp32_setting_change(self, name: str, value: str):
        """Callback when ESP32 display changes a setting - sync to Pi settings"""
        changed = False
        
        if name == "brightness":
            self.settings.brightness = int(value)
            changed = True
        elif name == "volume":
            self.settings.volume = int(value)
            self.sound.set_volume(self.settings.volume)
            changed = True
        elif name == "shift_rpm":
            self.settings.shift_rpm = int(value)
            changed = True
        elif name == "redline_rpm":
            self.settings.redline_rpm = int(value)
            changed = True
        elif name == "use_mph":
            self.settings.use_mph = (value == "1" or value.lower() == "true")
            changed = True
        elif name == "tire_low_psi":
            self.settings.tire_low_psi = float(value)
            changed = True
        elif name == "coolant_warn":
            self.settings.coolant_warn_f = int(value)
            changed = True
        elif name == "demo_mode":
            new_demo = (value == "1" or value.lower() == "true")
            if new_demo != self.settings.demo_mode:
                self.settings.demo_mode = new_demo
                self._on_data_source_changed()
            changed = True
        elif name == "led_sequence":
            new_seq = int(value)
            if 1 <= new_seq <= LED_SEQ_COUNT:
                self.settings.led_sequence = new_seq
                self._send_led_sequence_to_arduino()
            changed = True
        elif name == "timeout":
            # Screen timeout - Pi doesn't use this currently but store it
            pass
        
        if changed:
            print(f"Pi: Setting synced from ESP32 - {name}={value}")
    
    def _on_esp32_selection_change(self, index: int):
        """Callback when ESP32 settings selection changes - sync to Pi"""
        if self.current_screen == Screen.SETTINGS:
            items = self._get_settings_items()
            if 0 <= index < len(items):
                self.settings_selection = index
                print(f"Pi: Selection synced from ESP32 - index {index}")
    
    def _sync_selection_to_esp32(self):
        """Send current settings selection to ESP32"""
        if self.esp32_handler and self.esp32_handler.connected:
            self.esp32_handler.send_selection(self.settings_selection)
    
    def _send_led_sequence_to_arduino(self):
        """Send LED sequence command to Arduino via dedicated serial port"""
        try:
            if hasattr(self, 'arduino_serial') and self.arduino_serial and self.arduino_serial.is_open:
                cmd = f"SEQ:{self.settings.led_sequence}\n"
                self.arduino_serial.write(cmd.encode())
                print(f"Pi: Sent LED sequence {self.settings.led_sequence} to Arduino")
            else:
                # Arduino serial not connected - this is normal if not wired up
                pass
        except Exception as e:
            print(f"Pi: Failed to send LED sequence to Arduino: {e}")
    
    def _on_esp32_settings_sync(self, settings_dict: dict):
        """Callback when ESP32 sends all settings - full sync to Pi"""
        for name, value in settings_dict.items():
            self._on_esp32_setting_change(name, value)
        print(f"Pi: Full settings sync from ESP32 complete ({len(settings_dict)} settings)")
    
    def _sync_settings_to_esp32(self):
        """Send all current Pi settings to ESP32 for initial sync"""
        if self.esp32_handler and self.esp32_handler.connected:
            self.esp32_handler.send_all_settings(self.settings)
            print("Pi: Sent initial settings to ESP32")
    
    def _on_data_source_changed(self):
        """Called when demo_mode setting is toggled"""
        # Reset telemetry data when switching modes
        self.telemetry = TelemetryData()
        
        # Reinitialize data sources
        self._init_data_sources()
        
        # Update handlers to use new telemetry object
        if self.can_handler:
            self.can_handler.telemetry = self.telemetry
        if self.esp32_handler:
            self.esp32_handler.telemetry = self.telemetry
    
    def _load_car_image(self):

        """Load and prepare car silhouette image for TPMS display"""
        # Try multiple possible paths for the car image
        possible_paths = [
            os.path.join(os.path.dirname(__file__), '..', '..', '..', 'display', 'output-onlinepngtools.png'),
            os.path.join(os.path.dirname(__file__), '..', 'assets', 'car_topdown.png'),
            '/home/pi/MX5-Telemetry/display/output-onlinepngtools.png',
            'C:/Users/tanne/Documents/Github/MX5-Telemetry/display/output-onlinepngtools.png',
        ]
        
        for path in possible_paths:
            try:
                if os.path.exists(path):
                    img = pygame.image.load(path).convert_alpha()
                    # Scale for full TPMS screen (target ~200px wide)
                    scale = 200 / img.get_width()
                    new_w = 200
                    new_h = int(img.get_height() * scale)
                    self.car_image = pygame.transform.smoothscale(img, (new_w, new_h))
                    
                    # Scale for overview mini TPMS (target ~80px wide)
                    scale_small = 80 / img.get_width()
                    small_w = 80
                    small_h = int(img.get_height() * scale_small)
                    self.car_image_small = pygame.transform.smoothscale(img, (small_w, small_h))
                    
                    print(f"Loaded car image from: {path}")
                    return
            except Exception as e:
                print(f"Failed to load {path}: {e}")
        
        print("Warning: Could not load car image, using rectangle placeholder")
    
    def run(self):
        """Main application loop"""
        running = True
        
        print("=" * 60)
        print("MX5 Telemetry - Raspberry Pi Display")
        print("=" * 60)
        print(f"Render Resolution: {PI_WIDTH}x{PI_HEIGHT}")
        print(f"Display Resolution: {self.display_width}x{self.display_height}")
        print(f"Scale Output: {self.scale_output}")
        print(f"Demo Mode: {self.settings.demo_mode}")
        print()
        print("Controls:")
        print("  Up / W     = Previous screen (RES+)")
        print("  Down / S   = Next screen (SET-)")
        print("  Right / D  = Increase value (VOL+)")
        print("  Left / A   = Decrease value (VOL-)")
        print("  Enter      = Select / Edit (ON/OFF)")
        print("  Esc / B    = Back / Exit (CANCEL)")
        print("  Space      = Toggle sleep mode")
        print("  L          = Toggle navigation lock")
        print("  Q          = Quit")
        print("=" * 60)
        
        while running:
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    # Handle exit confirmation dialog
                    if self.show_exit_dialog:
                        if event.key == pygame.K_y or event.key == pygame.K_RETURN:
                            running = False  # Yes, exit
                        elif event.key == pygame.K_n or event.key == pygame.K_ESCAPE:
                            self.show_exit_dialog = False  # No, cancel
                        continue
                    
                    # ESC key shows exit confirmation
                    if event.key == pygame.K_ESCAPE:
                        self.show_exit_dialog = True
                        continue
                    
                    button = self._key_to_button(event.key)
                    if button == ButtonEvent.NONE:
                        if event.key == pygame.K_q:
                            self.show_exit_dialog = True  # Q also shows confirmation
                        elif event.key == pygame.K_SPACE:
                            self.sleeping = not self.sleeping
                        elif event.key == pygame.K_l:
                            # L key toggles navigation lock (for testing)
                            if self.swc_handler:
                                self.swc_handler.toggle_nav_lock()
                    else:
                        self._handle_button(button)
            
            # Poll for steering wheel control buttons from CAN bus (MS-CAN)
            if self.swc_handler:
                for swc_button in self.swc_handler.poll_buttons():
                    self._on_swc_button(swc_button)
            
            # Update data source
            if self.settings.demo_mode and not self.sleeping:
                # Demo mode: simulate data for testing
                self._update_demo()
            # Real mode: CAN handler reads data automatically in background thread
            # Real mode: ESP32 handler receives TPMS/IMU data automatically
            
            # Update lap timer if running (independent of demo mode)
            if self.lap_timer_running:
                import time
                self.telemetry.lap_time_ms = int(time.time() * 1000 - self.lap_timer_start_time)
            
            # Forward telemetry to ESP32 (if connected)
            if self.esp32_handler and self.esp32_handler.connected:
                # Send telemetry at ~5Hz (every 6 frames at 30fps) - reduced to avoid serial congestion
                if hasattr(self, '_esp32_tx_counter'):
                    self._esp32_tx_counter += 1
                else:
                    self._esp32_tx_counter = 0
                if self._esp32_tx_counter >= 6:
                    self._esp32_tx_counter = 0
                    self.esp32_handler.send_telemetry()
            
            # Render
            self._render()
            
            # Draw exit dialog on top if active
            if self.show_exit_dialog:
                self._render_exit_dialog()
            
            # Scale render surface to display if needed
            if self.scale_output:
                scaled = pygame.transform.scale(self.screen, (self.display_width, self.display_height))
                self.display_surface.blit(scaled, (0, 0))
            
            pygame.display.flip()
            self.clock.tick(60)  # 60 FPS for smooth G-force ball movement
        
        # Cleanup
        if self.can_handler:
            self.can_handler.stop()
        if self.esp32_handler:
            self.esp32_handler.stop()
        pygame.quit()
    
    def _on_swc_button(self, button: ButtonEvent):
        """Callback for steering wheel control button events from CAN bus
        
        NOTE: Only cruise control buttons are available (ON_OFF, CANCEL, RES_PLUS, SET_MINUS).
        Volume/audio buttons are NOT readable on the MS-CAN bus.
        
        Navigation lock: When locked, all button presses are ignored to prevent
        accidental changes while driving. Lock/unlock via 3-second ON_OFF hold.
        """
        if button == ButtonEvent.NONE:
            return
        
        # Check if navigation is locked (ignore all buttons when locked)
        if self.swc_handler and self.swc_handler.is_nav_locked():
            # Silently ignore - lock toggle is handled by swc_handler hold detection
            return
        
        # Route to normal button handler
        self._handle_button(button)
    
    def _key_to_button(self, key) -> ButtonEvent:
        """Map keyboard to SWC buttons (cruise control only)
        
        Navigation scheme:
        - UP/W: RES_PLUS (previous page / navigate up / increase value)
        - DOWN/S: SET_MINUS (next page / navigate down / decrease value)
        - ENTER/SPACE: ON_OFF (select / confirm)
        - B/BACKSPACE: CANCEL (back / exit edit mode)
        """
        mapping = {
            # UP - RES_PLUS: Previous page / Navigate up / Increase value
            pygame.K_UP: ButtonEvent.RES_PLUS,
            pygame.K_w: ButtonEvent.RES_PLUS,
            # DOWN - SET_MINUS: Next page / Navigate down / Decrease value
            pygame.K_DOWN: ButtonEvent.SET_MINUS,
            pygame.K_s: ButtonEvent.SET_MINUS,
            # SELECT - ON_OFF: Select / Confirm edit
            pygame.K_RETURN: ButtonEvent.ON_OFF,
            pygame.K_SPACE: ButtonEvent.ON_OFF,
            # BACK - CANCEL: Back / Exit edit mode
            pygame.K_b: ButtonEvent.CANCEL,
            pygame.K_BACKSPACE: ButtonEvent.CANCEL,
        }
        return mapping.get(key, ButtonEvent.NONE)
    
    def _handle_button(self, button: ButtonEvent):
        """Handle button press"""
        if self.current_screen == Screen.SETTINGS:
            self._handle_settings_button(button)
        elif self.current_screen == Screen.RPM_SPEED:
            self._handle_lap_timer_button(button)
        else:
            self._handle_navigation_button(button)
    
    def _handle_navigation_button(self, button: ButtonEvent):
        """Handle normal screen navigation with transitions
        
        Cruise control navigation scheme:
        - RES_PLUS (UP): Previous screen
        - SET_MINUS (DOWN): Next screen
        - CANCEL: Go to Overview screen
        """
        screens = list(Screen)
        
        # Determine target screen based on button
        if button == ButtonEvent.RES_PLUS:
            # UP - previous screen
            if self._is_transitioning():
                # Update transition target to previous from current target
                current_idx = screens.index(self.transition_to_screen)
                new_idx = (current_idx - 1) % len(screens)
                self._update_transition_target(screens[new_idx], 'prev')
            else:
                idx = screens.index(self.current_screen)
                idx = (idx - 1) % len(screens)
                self._navigate_to_screen(screens[idx], 'prev')
        elif button == ButtonEvent.SET_MINUS:
            # DOWN - next screen
            if self._is_transitioning():
                # Update transition target to next from current target
                current_idx = screens.index(self.transition_to_screen)
                new_idx = (current_idx + 1) % len(screens)
                self._update_transition_target(screens[new_idx], 'next')
            else:
                idx = screens.index(self.current_screen)
                idx = (idx + 1) % len(screens)
                self._navigate_to_screen(screens[idx], 'next')
        elif button == ButtonEvent.CANCEL:
            # CANCEL - Go back to Overview
            if not self._is_transitioning():
                self._navigate_to_screen(Screen.OVERVIEW, 'prev')
    
    def _update_transition_target(self, new_target: Screen, direction: str):
        """Update the transition target during an active transition"""
        if new_target == self.transition_to_screen:
            return  # Already going there
        
        # Update destination
        self.transition_to_screen = new_target
        
        # Re-render the new destination screen
        saved_screen = self.screen
        self.screen = self.transition_surface_new
        saved_current = self.current_screen
        self.current_screen = new_target
        self._render_screen_content()
        self.current_screen = saved_current
        self.screen = saved_screen
        
        # Sync ESP32 to new target
        self._sync_esp32_screen_for_transition(new_target)
        print(f"Updated transition target to: {new_target.name}")
    
    def _sync_esp32_screen(self):
        """Sync ESP32 display to match Pi screen (all 8 screens)"""
        if self.esp32_handler:
            # Map Pi screens to ESP32 screens (ESP32 has 8 screens: 0-7)
            # Pi: OVERVIEW=0, RPM_SPEED=1, TPMS=2, ENGINE=3, GFORCE=4, DIAGNOSTICS=5, SYSTEM=6, SETTINGS=7
            # ESP: OVERVIEW=0, RPM=1, TPMS=2, ENGINE=3, GFORCE=4, DIAGNOSTICS=5, SYSTEM=6, SETTINGS=7
            screen_idx = self.current_screen.value
            if screen_idx <= 7:
                self.esp32_handler.send_screen_change(screen_idx)
    
    # === PAGE TRANSITION ANIMATION METHODS ===
    
    def _is_transitioning(self) -> bool:
        """Check if a page transition is in progress"""
        return self.transition_type != TransitionType.NONE
    
    def _ease_out_cubic(self, t: float) -> float:
        """Easing function - smooth deceleration"""
        return 1.0 - pow(1.0 - t, 3)
    
    def _ease_in_out_quad(self, t: float) -> float:
        """Easing function - smooth acceleration and deceleration"""
        if t < 0.5:
            return 2 * t * t
        return 1 - pow(-2 * t + 2, 2) / 2
    
    def _start_transition(self, to_screen: Screen, transition_type: TransitionType):
        """Start a page transition animation"""
        if to_screen == self.current_screen:
            return  # No transition needed
        
        # Capture current screen to offscreen surface
        self.transition_surface_old = self.screen.copy()
        
        # Set up transition state
        self.transition_from_screen = self.current_screen
        self.transition_to_screen = to_screen
        self.transition_type = transition_type
        self.transition_start_time = time.time()
        self.transition_progress = 0.0
        
        # Render destination screen to offscreen surface
        self.transition_surface_new = pygame.Surface((PI_WIDTH, PI_HEIGHT))
        saved_screen = self.screen
        self.screen = self.transition_surface_new
        self.current_screen = to_screen
        self._render_screen_content()
        self.current_screen = self.transition_from_screen
        self.screen = saved_screen
        
        print(f"Starting transition: {self.transition_from_screen.name} -> {to_screen.name}")
    
    def _update_transition(self):
        """Update transition animation progress"""
        if self.transition_type == TransitionType.NONE:
            return
        
        elapsed = time.time() - self.transition_start_time
        self.transition_progress = elapsed / self.transition_duration
        
        if self.transition_progress >= 1.0:
            # Transition complete
            self.transition_progress = 1.0
            self.current_screen = self.transition_to_screen
            self.transition_type = TransitionType.NONE
            self.transition_surface_old = None
            self.transition_surface_new = None
            print(f"Transition complete, now on: {self.current_screen.name}")
    
    def _render_transition(self):
        """Render the transition animation effect"""
        if self.transition_type == TransitionType.NONE:
            return
        
        eased = self._ease_out_cubic(self.transition_progress)
        
        if self.transition_type == TransitionType.SLIDE_LEFT:
            # Old screen slides left, new slides in from right
            offset = int(PI_WIDTH * eased)
            if self.transition_surface_old:
                self.screen.blit(self.transition_surface_old, (-offset, 0))
            if self.transition_surface_new:
                self.screen.blit(self.transition_surface_new, (PI_WIDTH - offset, 0))
            # Draw accent line at transition edge
            line_x = PI_WIDTH - offset
            pygame.draw.rect(self.screen, COLOR_ACCENT, (line_x - 2, 0, 4, PI_HEIGHT))
            
        elif self.transition_type == TransitionType.SLIDE_RIGHT:
            # Old screen slides right, new slides in from left
            offset = int(PI_WIDTH * eased)
            if self.transition_surface_old:
                self.screen.blit(self.transition_surface_old, (offset, 0))
            if self.transition_surface_new:
                self.screen.blit(self.transition_surface_new, (offset - PI_WIDTH, 0))
            # Draw accent line at transition edge
            line_x = offset
            pygame.draw.rect(self.screen, COLOR_ACCENT, (line_x - 2, 0, 4, PI_HEIGHT))
            
        elif self.transition_type == TransitionType.FADE:
            # Crossfade between screens
            if self.transition_surface_old:
                self.transition_surface_old.set_alpha(int(255 * (1 - eased)))
                self.screen.blit(self.transition_surface_old, (0, 0))
            if self.transition_surface_new:
                self.transition_surface_new.set_alpha(int(255 * eased))
                self.screen.blit(self.transition_surface_new, (0, 0))
                
        elif self.transition_type == TransitionType.ZOOM:
            # Zoom out old, zoom in new
            if eased < 0.5:
                # First half: zoom out old screen
                scale = 1.0 - eased
                if self.transition_surface_old and scale > 0.1:
                    w = int(PI_WIDTH * scale)
                    h = int(PI_HEIGHT * scale)
                    scaled = pygame.transform.scale(self.transition_surface_old, (w, h))
                    x = (PI_WIDTH - w) // 2
                    y = (PI_HEIGHT - h) // 2
                    self.screen.fill(COLOR_BG_DARK)
                    self.screen.blit(scaled, (x, y))
            else:
                # Second half: zoom in new screen
                scale = (eased - 0.5) * 2
                if self.transition_surface_new:
                    w = int(PI_WIDTH * scale)
                    h = int(PI_HEIGHT * scale)
                    if w > 10 and h > 10:
                        scaled = pygame.transform.scale(self.transition_surface_new, (w, h))
                        x = (PI_WIDTH - w) // 2
                        y = (PI_HEIGHT - h) // 2
                        self.screen.fill(COLOR_BG_DARK)
                        self.screen.blit(scaled, (x, y))
    
    def _render_screen_content(self):
        """Render just the screen content (for transition capture)"""
        self.screen.fill(COLOR_BG_DARK)
        renderers = {
            Screen.OVERVIEW: self._render_overview,
            Screen.RPM_SPEED: self._render_rpm_speed,
            Screen.TPMS: self._render_tpms,
            Screen.ENGINE: self._render_engine,
            Screen.GFORCE: self._render_gforce,
            Screen.DIAGNOSTICS: self._render_diagnostics,
            Screen.SYSTEM: self._render_system,
            Screen.SETTINGS: self._render_settings,
        }
        renderers[self.current_screen]()
        
        # Title bar
        pygame.draw.rect(self.screen, (30, 30, 45), (0, 0, PI_WIDTH, 50))
        title = SCREEN_NAMES[self.current_screen]
        txt = self.font_small.render(title, True, COLOR_WHITE)
        self.screen.blit(txt, (20, 8))
        
        # Screen indicator dots
        screens = list(Screen)
        dot_x = PI_WIDTH - 20 - len(screens) * 18
        for i, scr in enumerate(screens):
            color = COLOR_ACCENT if scr == self.current_screen else COLOR_DARK_GRAY
            pygame.draw.circle(self.screen, color, (dot_x + i * 18, 25), 6)
    
    def _navigate_to_screen(self, to_screen: Screen, direction: str = 'auto'):
        """Navigate to a screen with animation"""
        print(f"DEBUG: _navigate_to_screen called: {self.current_screen.name} -> {to_screen.name}")
        if to_screen == self.current_screen:
            return
        
        # Determine transition type based on direction
        if direction == 'next' or (direction == 'auto' and to_screen.value > self.current_screen.value):
            trans_type = TransitionType.SLIDE_LEFT
        elif direction == 'prev' or (direction == 'auto' and to_screen.value < self.current_screen.value):
            trans_type = TransitionType.SLIDE_RIGHT
        else:
            trans_type = TransitionType.SLIDE_LEFT
        
        self._start_transition(to_screen, trans_type)
        self.sound.play('navigate')
        self._sync_esp32_screen_for_transition(to_screen)
        print(f"DEBUG: _navigate_to_screen completed")
    
    def _sync_esp32_screen_for_transition(self, to_screen: Screen):
        """Sync ESP32 to destination screen during transition"""
        print(f"DEBUG: _sync_esp32_screen_for_transition called with {to_screen.name} (value={to_screen.value})")
        if self.esp32_handler:
            screen_idx = to_screen.value
            print(f"DEBUG: Sending screen change to ESP32: {screen_idx}")
            if screen_idx <= 7:
                self.esp32_handler.send_screen_change(screen_idx)
    
    # === END TRANSITION METHODS ===
    
    def _handle_lap_timer_button(self, button: ButtonEvent):
        """Handle lap timer controls on RPM/Speed screen
        
        Cruise control navigation:
        - RES_PLUS (UP): Previous screen
        - SET_MINUS (DOWN): Next screen  
        - ON_OFF: Start/Stop lap timer
        - CANCEL: Reset lap timer
        """
        import time
        
        # Ignore input during transitions
        if self._is_transitioning():
            return
        
        # Navigation still works
        if button == ButtonEvent.RES_PLUS:
            # UP - previous screen
            screens = list(Screen)
            idx = screens.index(self.current_screen)
            idx = (idx - 1) % len(screens)
            self._navigate_to_screen(screens[idx], 'prev')
        elif button == ButtonEvent.SET_MINUS:
            # DOWN - next screen
            screens = list(Screen)
            idx = screens.index(self.current_screen)
            idx = (idx + 1) % len(screens)
            self._navigate_to_screen(screens[idx], 'next')
        elif button == ButtonEvent.ON_OFF:
            # Enter/Select - Start/Stop lap timer
            if self.lap_timer_running:
                # Stop timer - record lap if better than best
                if self.telemetry.lap_time_ms > 0:
                    if self.telemetry.best_lap_ms == 0 or self.telemetry.lap_time_ms < self.telemetry.best_lap_ms:
                        self.telemetry.best_lap_ms = self.telemetry.lap_time_ms
                self.lap_timer_running = False
                self.sound.play('select')
            else:
                # Start timer
                self.lap_timer_running = True
                self.lap_timer_start_time = time.time() * 1000
                self.telemetry.lap_time_ms = 0
                self.sound.play('select')
        elif button == ButtonEvent.CANCEL:
            # Cancel/Back - Reset timer
            self.lap_timer_running = False
            self.telemetry.lap_time_ms = 0
            self.sound.play('back')
    
    def _handle_settings_button(self, button: ButtonEvent):
        """Handle settings screen navigation
        
        Cruise control navigation (settings screen):
        
        Normal mode (not editing):
        - RES_PLUS (UP): If at top setting, go to previous page. Otherwise, move selection up.
        - SET_MINUS (DOWN): If at bottom setting, go to next page. Otherwise, move selection down.
        - ON_OFF: Enter edit mode for selected setting
        - CANCEL: Exit to Overview screen
        
        Edit mode:
        - RES_PLUS (UP): Increase setting value
        - SET_MINUS (DOWN): Decrease setting value
        - ON_OFF: Confirm and exit edit mode
        - CANCEL: Cancel and exit edit mode
        """
        # Ignore input during transitions
        if self._is_transitioning():
            return
            
        items = self._get_settings_items()
        
        if self.settings_edit_mode:
            # In edit mode: UP/DOWN adjust value, ON_OFF/CANCEL exit
            if button == ButtonEvent.RES_PLUS:
                # UP - Increase value
                self._adjust_setting(1)
                self.sound.play('adjust')
            elif button == ButtonEvent.SET_MINUS:
                # DOWN - Decrease value
                self._adjust_setting(-1)
                self.sound.play('adjust')
            elif button == ButtonEvent.ON_OFF:
                # Confirm and exit edit mode
                self.settings_edit_mode = False
                self.sound.play('select')
            elif button == ButtonEvent.CANCEL:
                # Cancel and exit edit mode (could restore value, but just exit for now)
                self.settings_edit_mode = False
                self.sound.play('back')
        else:
            # Normal mode: navigate settings list, boundary transitions to pages
            if button == ButtonEvent.RES_PLUS:
                # UP - Move selection up, or go to previous page if at top
                if self.settings_selection > 0:
                    self.settings_selection -= 1
                    self.sound.play('navigate')
                    self._sync_selection_to_esp32()
                else:
                    # At top of settings - go to previous screen
                    screens = list(Screen)
                    idx = screens.index(self.current_screen)
                    idx = (idx - 1) % len(screens)
                    self.settings_selection = 0
                    self._navigate_to_screen(screens[idx], 'prev')
            elif button == ButtonEvent.SET_MINUS:
                # DOWN - Move selection down, or go to next page if at bottom
                if self.settings_selection < len(items) - 1:
                    self.settings_selection += 1
                    self.sound.play('navigate')
                    self._sync_selection_to_esp32()
                else:
                    # At bottom of settings - go to next screen
                    screens = list(Screen)
                    idx = screens.index(self.current_screen)
                    idx = (idx + 1) % len(screens)
                    self.settings_selection = 0
                    self._navigate_to_screen(screens[idx], 'next')
            elif button == ButtonEvent.ON_OFF:
                # Enter edit mode for current setting
                self.settings_edit_mode = True
                self.sound.play('select')
            elif button == ButtonEvent.CANCEL:
                # Exit settings to overview
                self.settings_selection = 0
                self._navigate_to_screen(Screen.OVERVIEW, 'prev')
                self.sound.play('adjust')
    
    def _adjust_setting(self, delta: int):
        """Adjust currently selected setting"""
        sel = self.settings_selection
        # Settings are now 0-indexed without Back button
        if sel == 0:  # Data Source (Demo Mode)
            self.settings.demo_mode = not self.settings.demo_mode
            self._on_data_source_changed()
            self._sync_setting_to_esp32("demo_mode", self.settings.demo_mode)
        elif sel == 1:  # Brightness
            self.settings.brightness = max(10, min(100, self.settings.brightness + delta * 5))
            self._sync_setting_to_esp32("brightness", self.settings.brightness)
        elif sel == 2:  # Volume
            self.settings.volume = max(0, min(100, self.settings.volume + delta * 5))
            self.sound.set_volume(self.settings.volume)
            self._sync_setting_to_esp32("volume", self.settings.volume)
        elif sel == 3:  # Shift RPM
            self.settings.shift_rpm = max(4000, min(7500, self.settings.shift_rpm + delta * 100))
            self._sync_setting_to_esp32("shift_rpm", self.settings.shift_rpm)
        elif sel == 4:  # Redline
            self.settings.redline_rpm = max(5000, min(8000, self.settings.redline_rpm + delta * 100))
            self._sync_setting_to_esp32("redline_rpm", self.settings.redline_rpm)
        elif sel == 5:  # Units
            self.settings.use_mph = not self.settings.use_mph
            self._sync_setting_to_esp32("use_mph", self.settings.use_mph)
        elif sel == 6:  # Low tire PSI
            self.settings.tire_low_psi = max(20, min(35, self.settings.tire_low_psi + delta * 0.5))
            self._sync_setting_to_esp32("tire_low_psi", self.settings.tire_low_psi)
        elif sel == 7:  # Coolant warn
            self.settings.coolant_warn_f = max(180, min(250, self.settings.coolant_warn_f + delta * 5))
            self._sync_setting_to_esp32("coolant_warn", self.settings.coolant_warn_f)
        elif sel == 8:  # LED Sequence
            # Cycle through LED sequences (1-4)
            new_seq = self.settings.led_sequence + delta
            if new_seq > LED_SEQ_COUNT:
                new_seq = 1
            elif new_seq < 1:
                new_seq = LED_SEQ_COUNT
            self.settings.led_sequence = new_seq
            self._sync_setting_to_esp32("led_sequence", self.settings.led_sequence)
            # Also send to Arduino via ESP32 serial handler
            self._send_led_sequence_to_arduino()
    
    def _sync_setting_to_esp32(self, name: str, value):
        """Send a single setting to ESP32 for synchronization"""
        if self.esp32_handler and self.esp32_handler.connected:
            self.esp32_handler.send_setting(name, value)
    
    def _get_settings_items(self):
        """Return list of (name, value, unit) tuples"""
        led_seq_name = LED_SEQUENCE_NAMES.get(self.settings.led_sequence, "Unknown")
        return [
            ("Data Source", "DEMO" if self.settings.demo_mode else "CAN BUS", ""),
            ("Brightness", self.settings.brightness, "%"),
            ("Volume", self.settings.volume, "%"),
            ("Shift RPM", self.settings.shift_rpm, ""),
            ("Redline", self.settings.redline_rpm, ""),
            ("Units", "MPH" if self.settings.use_mph else "KMH", ""),
            ("Low Tire PSI", self.settings.tire_low_psi, ""),
            ("Coolant Warn", self.settings.coolant_warn_f, "°F"),
            ("LED Sequence", led_seq_name, f"({self.settings.led_sequence}/{LED_SEQ_COUNT})"),
        ]
    
    def _update_demo(self):
        """Update demo animation with complete simulated data"""
        import time
        t = time.time()
        
        # RPM oscillation
        self.telemetry.rpm += 50 * self.demo_rpm_dir
        if self.telemetry.rpm >= 7200:
            self.demo_rpm_dir = -1
        if self.telemetry.rpm <= 800:
            self.demo_rpm_dir = 1
        
        # Gear based on RPM
        if self.telemetry.rpm < 2000:
            self.telemetry.gear = 1
        elif self.telemetry.rpm < 3500:
            self.telemetry.gear = 2
        elif self.telemetry.rpm < 5000:
            self.telemetry.gear = 3
        elif self.telemetry.rpm < 6000:
            self.telemetry.gear = 4
        else:
            self.telemetry.gear = 5
        
        # Speed approximation (more realistic: gear ratios)
        gear_ratios = [0, 3.136, 1.888, 1.330, 1.000, 0.814, 0.0]  # MX5 NC gear ratios
        if 1 <= self.telemetry.gear <= 5:
            # Speed = (RPM * tire_circumference) / (gear_ratio * diff_ratio * 60)
            # Simplified: ~rpm/gear_ratio * factor for km/h
            self.telemetry.speed_kmh = int(self.telemetry.rpm / (gear_ratios[self.telemetry.gear] * 25))
        else:
            self.telemetry.speed_kmh = 0
        
        # G-force simulation (from IMU)
        self.telemetry.g_lateral = math.sin(t) * 0.8
        self.telemetry.g_longitudinal = math.cos(t * 1.5) * 0.5
        
        # Throttle/brake simulation
        self.telemetry.throttle_percent = int(50 + math.sin(t * 2) * 50)
        self.telemetry.brake_percent = int(max(0, -math.sin(t * 2) * 30))
        
        # Engine temperatures (simulate warm engine with slight variation)
        self.telemetry.coolant_temp_f = int(195 + math.sin(t * 0.1) * 10)  # 185-205°F
        self.telemetry.oil_temp_f = int(210 + math.sin(t * 0.08) * 15)     # 195-225°F
        self.telemetry.oil_pressure_psi = 45 + math.sin(t * 0.2) * 10      # 35-55 PSI
        self.telemetry.intake_temp_f = int(85 + math.sin(t * 0.05) * 10)   # 75-95°F
        self.telemetry.ambient_temp_f = 72  # Static ambient temp
        
        # Fuel and voltage
        self.telemetry.fuel_level_percent = max(0, 65 - (t % 3600) * 0.001)  # Slowly decreasing
        self.telemetry.voltage = 14.2 + math.sin(t * 0.5) * 0.3  # 13.9-14.5V
        
        # TPMS simulation (slight variations in tire pressure/temp)
        base_psi = 32.0
        base_temp = 75.0
        for i in range(4):
            self.telemetry.tire_pressure[i] = base_psi + math.sin(t * 0.1 + i) * 1.5
            self.telemetry.tire_temp[i] = base_temp + math.sin(t * 0.15 + i * 0.5) * 8 + i * 2
        
        # Wheel slip simulation (occasional slip during acceleration)
        for i in range(4):
            if self.telemetry.throttle_percent > 80 and self.telemetry.rpm > 5000:
                self.telemetry.wheel_slip[i] = abs(math.sin(t * 5 + i)) * 15  # 0-15% slip
            else:
                self.telemetry.wheel_slip[i] = 0
        
        # Lap time simulation - only if manual timer is not running
        if not self.lap_timer_running:
            self.telemetry.lap_time_ms += 33
            if self.telemetry.lap_time_ms > 120000:  # 2 minute lap
                # Record best lap occasionally
                if self.telemetry.best_lap_ms == 0 or self.telemetry.lap_time_ms < self.telemetry.best_lap_ms + 5000:
                    self.telemetry.best_lap_ms = 85000 + int(math.sin(t) * 5000)  # ~1:20-1:30
                self.telemetry.lap_time_ms = 0
        
        # Diagnostics simulation (occasional warnings)
        self.telemetry.check_engine_light = False
        self.telemetry.abs_warning = False
        self.telemetry.traction_control_active = self.telemetry.wheel_slip[2] > 5 or self.telemetry.wheel_slip[3] > 5
        self.telemetry.traction_control_off = False
        self.telemetry.oil_pressure_warning = self.telemetry.oil_pressure_psi < 20
        self.telemetry.battery_warning = self.telemetry.voltage < 12.0
        self.telemetry.door_ajar = False
        self.telemetry.seatbelt_warning = False
        self.telemetry.brake_warning = False
        self.telemetry.high_beam_on = False
        self.telemetry.fog_light_on = False
    
    def _get_rpm_color(self, rpm: int) -> Tuple[int, int, int]:
        """Get color based on RPM percentage"""
        pct = rpm / self.settings.redline_rpm
        if pct >= 0.95:
            return COLOR_RED
        elif pct >= 0.85:
            return COLOR_ORANGE
        elif pct >= 0.70:
            return COLOR_YELLOW
        return COLOR_GREEN
    
    def _get_alerts(self) -> List[Tuple[str, Tuple[int, int, int]]]:
        """Get list of active alerts"""
        alerts = []
        
        # Check tire pressures
        tire_names = ["FL", "FR", "RL", "RR"]
        for i, psi in enumerate(self.telemetry.tire_pressure):
            if psi < self.settings.tire_low_psi:
                alerts.append((f"{tire_names[i]} LOW: {psi:.1f} PSI", COLOR_RED))
            elif psi > self.settings.tire_high_psi:
                alerts.append((f"{tire_names[i]} HIGH: {psi:.1f} PSI", COLOR_YELLOW))
        
        # Check temperatures
        if self.telemetry.coolant_temp_f >= self.settings.coolant_warn_f:
            alerts.append((f"COOLANT: {self.telemetry.coolant_temp_f}F", COLOR_RED))
        if self.telemetry.oil_temp_f >= self.settings.oil_warn_f:
            alerts.append((f"OIL TEMP: {self.telemetry.oil_temp_f}F", COLOR_RED))
        
        # Check voltage
        if self.telemetry.voltage < 12.0:
            alerts.append((f"LOW VOLTAGE: {self.telemetry.voltage:.1f}V", COLOR_YELLOW))
        
        # Check fuel
        if self.telemetry.fuel_level_percent < 15:
            alerts.append((f"LOW FUEL: {self.telemetry.fuel_level_percent:.0f}%", COLOR_YELLOW))
        
        return alerts
    
    def _draw_arc(self, surface, cx, cy, radius, thickness, start_angle, end_angle, color):
        """Draw a thick arc"""
        start_rad = math.radians(start_angle)
        end_rad = math.radians(end_angle)
        
        steps = int(abs(end_angle - start_angle) / 2)
        if steps < 1:
            steps = 1
        
        for i in range(steps):
            a1 = start_rad + (end_rad - start_rad) * i / steps
            a2 = start_rad + (end_rad - start_rad) * (i + 1) / steps
            
            for t in range(-thickness // 2, thickness // 2 + 1):
                r = radius + t
                x1 = int(cx + math.cos(a1) * r)
                y1 = int(cy + math.sin(a1) * r)
                x2 = int(cx + math.cos(a2) * r)
                y2 = int(cy + math.sin(a2) * r)
                pygame.draw.line(surface, color, (x1, y1), (x2, y2), 1)
    
    # =========================================================================
    # RENDERING
    # =========================================================================
    
    def _render(self):
        """Render current screen"""
        self.screen.fill(COLOR_BG_DARK)
        
        if self.sleeping:
            self._render_sleep()
        elif self._is_transitioning():
            # Update and render transition animation
            self._update_transition()
            self._render_transition()
        else:
            try:
                renderers = {
                    Screen.OVERVIEW: self._render_overview,
                    Screen.RPM_SPEED: self._render_rpm_speed,
                    Screen.TPMS: self._render_tpms,
                    Screen.ENGINE: self._render_engine,
                    Screen.GFORCE: self._render_gforce,
                    Screen.DIAGNOSTICS: self._render_diagnostics,
                    Screen.SYSTEM: self._render_system,
                    Screen.SETTINGS: self._render_settings,
                }
                renderers[self.current_screen]()
            except Exception as e:
                # DEBUG: Show exception on screen
                import traceback
                traceback.print_exc()
                err_txt = self.font_small.render(f"RENDER ERROR: {e}", True, (255, 0, 0))
                self.screen.blit(err_txt, (20, 100))
            
            # Title bar
            pygame.draw.rect(self.screen, (30, 30, 45), (0, 0, PI_WIDTH, 50))
            title = SCREEN_NAMES[self.current_screen]
            txt = self.font_small.render(title, True, COLOR_WHITE)
            self.screen.blit(txt, (20, 8))
            
            # Screen indicator dots
            screens = list(Screen)
            dot_x = PI_WIDTH - 20 - len(screens) * 18
            for i, scr in enumerate(screens):
                color = COLOR_ACCENT if scr == self.current_screen else COLOR_DARK_GRAY
                pygame.draw.circle(self.screen, color, (dot_x + i * 18, 25), 6)
    
    def _render_sleep(self):
        """Render sleep screen"""
        txt = self.font_large.render("SLEEP MODE", True, COLOR_DARK_GRAY)
        self.screen.blit(txt, txt.get_rect(center=(PI_WIDTH // 2, PI_HEIGHT // 2)))
    
    def _render_exit_dialog(self):
        """Render exit confirmation dialog overlay"""
        # Semi-transparent overlay
        overlay = pygame.Surface((PI_WIDTH, PI_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))
        
        # Dialog box
        dialog_w, dialog_h = 400, 180
        dialog_x = (PI_WIDTH - dialog_w) // 2
        dialog_y = (PI_HEIGHT - dialog_h) // 2
        
        pygame.draw.rect(self.screen, COLOR_BG_CARD, (dialog_x, dialog_y, dialog_w, dialog_h))
        pygame.draw.rect(self.screen, COLOR_ACCENT, (dialog_x, dialog_y, dialog_w, dialog_h), 3)
        
        # Title
        txt = self.font_medium.render("Exit Application?", True, COLOR_WHITE)
        self.screen.blit(txt, txt.get_rect(center=(PI_WIDTH // 2, dialog_y + 45)))
        
        # Message
        txt = self.font_small.render("Are you sure you want to close?", True, COLOR_GRAY)
        self.screen.blit(txt, txt.get_rect(center=(PI_WIDTH // 2, dialog_y + 90)))
        
        # Buttons hint
        txt = self.font_small.render("Y / Enter = Yes     N / Esc = No", True, COLOR_ACCENT)
        self.screen.blit(txt, txt.get_rect(center=(PI_WIDTH // 2, dialog_y + 140)))
    
    def _render_overview(self):
        """Overview screen - matches simulator exactly"""
        alerts = self._get_alerts()
        TOP = 55
        
        left_panel_x = 20
        left_panel_w = 180
        
        # Gear card
        pygame.draw.rect(self.screen, COLOR_BG_CARD, (left_panel_x, TOP, left_panel_w, 150))
        
        rpm_color = self._get_rpm_color(self.telemetry.rpm)
        gear = "N" if self.telemetry.gear == 0 else str(self.telemetry.gear)
        
        # Gear glow effect
        glow = pygame.Surface((90, 90), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*rpm_color[:3], 50), (45, 45), 40)
        self.screen.blit(glow, (left_panel_x + left_panel_w//2 - 45, TOP + 5))
        
        txt = self.font_large.render(gear, True, rpm_color)
        self.screen.blit(txt, txt.get_rect(center=(left_panel_x + left_panel_w//2, TOP + 55)))
        
        # Speed below gear
        speed = self.telemetry.speed_kmh
        if self.settings.use_mph:
            speed = int(speed * 0.621371)
        unit = "MPH" if self.settings.use_mph else "KMH"
        txt = self.font_medium.render(f"{speed:.0f} {unit}", True, COLOR_WHITE)
        self.screen.blit(txt, txt.get_rect(center=(left_panel_x + left_panel_w//2, TOP + 120)))
        
        # RPM bar card
        pygame.draw.rect(self.screen, COLOR_BG_CARD, (left_panel_x, TOP + 160, left_panel_w, 50))
        rpm_pct = min(1.0, self.telemetry.rpm / self.settings.redline_rpm)
        bar_x, bar_y = left_panel_x + 12, TOP + 168
        bar_w = left_panel_w - 24
        pygame.draw.rect(self.screen, COLOR_DARK_GRAY, (bar_x, bar_y, bar_w, 10))
        pygame.draw.rect(self.screen, rpm_color, (bar_x, bar_y, int(bar_w * rpm_pct), 10))
        txt = self.font_tiny.render(f"{self.telemetry.rpm} RPM", True, COLOR_GRAY)
        self.screen.blit(txt, txt.get_rect(center=(left_panel_x + left_panel_w//2, TOP + 195)))
        
        # Key values grid
        values = [
            ("COOL", f"{self.telemetry.coolant_temp_f:.0f}", 
             COLOR_RED if self.telemetry.coolant_temp_f >= self.settings.coolant_warn_f else COLOR_TEAL),
            ("OIL", f"{self.telemetry.oil_temp_f:.0f}",
             COLOR_RED if self.telemetry.oil_temp_f >= self.settings.oil_warn_f else COLOR_GREEN),
            ("FUEL", f"{self.telemetry.fuel_level_percent:.0f}%",
             COLOR_RED if self.telemetry.fuel_level_percent < 10 else 
             COLOR_YELLOW if self.telemetry.fuel_level_percent < 20 else COLOR_GREEN),
            ("VOLT", f"{self.telemetry.voltage:.1f}V",
             COLOR_RED if self.telemetry.voltage < 12.0 else
             COLOR_YELLOW if self.telemetry.voltage < 13.0 else COLOR_GREEN),
        ]
        
        card_w, card_h = 85, 50
        for i, (label, val, color) in enumerate(values):
            col = i % 2
            row = i // 2
            x = left_panel_x + col * (card_w + 10)
            y = TOP + 210 + row * (card_h + 6)
            
            pygame.draw.rect(self.screen, COLOR_BG_CARD, (x, y, card_w, card_h))
            pygame.draw.rect(self.screen, color, (x, y, 3, card_h))
            
            txt = self.font_tiny.render(label, True, COLOR_GRAY)
            self.screen.blit(txt, (x + 10, y + 5))
            txt = self.font_small.render(val, True, color)
            self.screen.blit(txt, (x + 10, y + 22))
        
        # Center: Modern TPMS diagram with car silhouette
        tpms_cx, tpms_cy = 340, TOP + 160
        
        # Draw car silhouette (small version)
        if self.car_image_small:
            car_rect = self.car_image_small.get_rect(center=(tpms_cx, tpms_cy))
            self.screen.blit(self.car_image_small, car_rect)
            car_w = self.car_image_small.get_width()
            car_h = self.car_image_small.get_height()
        else:
            # Fallback to rectangle
            car_w, car_h = 55, 100
            pygame.draw.rect(self.screen, COLOR_BG_CARD, 
                            (tpms_cx - car_w//2, tpms_cy - car_h//2, car_w, car_h))
        
        box_w, box_h = 60, 65
        tire_offset_x = car_w // 2 + box_w // 2 + 12
        tire_offset_y = car_h // 2 - 10
        
        tire_positions = [
            (0, -tire_offset_x, -tire_offset_y, "FL"),
            (1, tire_offset_x, -tire_offset_y, "FR"),
            (2, -tire_offset_x, tire_offset_y, "RL"),
            (3, tire_offset_x, tire_offset_y, "RR"),
        ]
        
        for idx, dx, dy, name in tire_positions:
            psi = self.telemetry.tire_pressure[idx]
            temp = self.telemetry.tire_temp[idx]
            x = tpms_cx + dx
            y = tpms_cy + dy
            
            if psi < self.settings.tire_low_psi:
                color = COLOR_RED
            elif psi > self.settings.tire_high_psi:
                color = COLOR_YELLOW
            else:
                color = COLOR_GREEN
            
            # Draw centered box
            pygame.draw.rect(self.screen, COLOR_BG_CARD, (x - box_w//2, y - box_h//2, box_w, box_h))
            pygame.draw.rect(self.screen, color, (x - box_w//2, y - box_h//2, 3, box_h))
            
            txt = self.font_tiny.render(name, True, COLOR_GRAY)
            self.screen.blit(txt, txt.get_rect(center=(x, y - 18)))
            txt = self.font_small.render(f"{psi:.0f}", True, color)
            self.screen.blit(txt, txt.get_rect(center=(x, y + 2)))
            txt = self.font_tiny.render(f"{temp:.1f}F", True, COLOR_GRAY)
            self.screen.blit(txt, txt.get_rect(center=(x, y + 20)))
        
        # Right panel: Alerts
        alerts_x = 490
        alerts_y = TOP
        alerts_w = 290
        alerts_h = PI_HEIGHT - TOP - 10
        
        pygame.draw.rect(self.screen, COLOR_BG_CARD, (alerts_x, alerts_y, alerts_w, alerts_h))
        
        header_color = COLOR_RED if alerts else COLOR_GREEN
        pygame.draw.rect(self.screen, header_color, (alerts_x, alerts_y, alerts_w, 45))
        header_text = "! ALERTS" if alerts else "ALL GOOD"
        txt = self.font_small.render(header_text, True, COLOR_WHITE)
        self.screen.blit(txt, txt.get_rect(center=(alerts_x + alerts_w//2, alerts_y + 22)))
        
        if alerts:
            alert_y = alerts_y + 55
            for i, (alert_text, alert_color) in enumerate(alerts[:8]):
                pygame.draw.rect(self.screen, COLOR_BG_ELEVATED,
                               (alerts_x + 10, alert_y, alerts_w - 20, 38))
                pygame.draw.rect(self.screen, alert_color,
                               (alerts_x + 10, alert_y, 3, 38))
                txt = self.font_small.render(alert_text, True, alert_color)
                self.screen.blit(txt, (alerts_x + 20, alert_y + 10))
                alert_y += 45
        else:
            check_y = alerts_y + 60
            checks = [
                ("Tire Pressures", True),
                ("Coolant Temp", True),
                ("Oil Temp", True),
                ("Fuel Level", self.telemetry.fuel_level_percent >= 15),
                ("Voltage", self.telemetry.voltage >= 12.0),
            ]
            for label, ok in checks:
                color = COLOR_GREEN if ok else COLOR_YELLOW
                pygame.draw.rect(self.screen, COLOR_BG_ELEVATED,
                               (alerts_x + 10, check_y, alerts_w - 20, 38))
                symbol = "+" if ok else "!"
                txt = self.font_small.render(f"{symbol}  {label}", True, color)
                self.screen.blit(txt, (alerts_x + 20, check_y + 10))
                check_y += 45
    
    def _render_rpm_speed(self):
        """RPM/Speed screen"""
        TOP = 55
        
        # Left side: RPM gauge
        gauge_cx, gauge_cy = 220, 275
        gauge_r = 160
        
        pygame.draw.circle(self.screen, COLOR_BG_CARD, (gauge_cx, gauge_cy), gauge_r + 12)
        pygame.draw.circle(self.screen, COLOR_BG, (gauge_cx, gauge_cy), gauge_r - 5)
        
        self._draw_arc(self.screen, gauge_cx, gauge_cy, gauge_r, 24, 135, 405, COLOR_DARK_GRAY)
        
        rpm_pct = self.telemetry.rpm / self.settings.redline_rpm
        rpm_angle = min(270, max(0, rpm_pct * 270))
        rpm_color = self._get_rpm_color(self.telemetry.rpm)
        
        if rpm_angle > 0:
            self._draw_arc(self.screen, gauge_cx, gauge_cy, gauge_r, 24, 135, 135 + rpm_angle, rpm_color)
        
        # Shift light
        if self.telemetry.rpm >= self.settings.shift_rpm:
            glow = pygame.Surface((40, 40), pygame.SRCALPHA)
            pygame.draw.circle(glow, (255, 70, 85, 100), (20, 20), 18)
            self.screen.blit(glow, (gauge_cx - 20, gauge_cy - gauge_r - 40))
            pygame.draw.circle(self.screen, COLOR_RED, (gauge_cx, gauge_cy - gauge_r - 20), 14)
        
        # Gear
        pygame.draw.circle(self.screen, COLOR_BG_CARD, (gauge_cx, gauge_cy), 70)
        
        gear = "N" if self.telemetry.gear == 0 else str(self.telemetry.gear)
        glow = pygame.Surface((80, 80), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*rpm_color[:3], 40), (40, 40), 35)
        self.screen.blit(glow, (gauge_cx - 40, gauge_cy - 50))
        
        txt = self.font_large.render(gear, True, rpm_color)
        self.screen.blit(txt, txt.get_rect(center=(gauge_cx, gauge_cy - 10)))
        
        txt = self.font_small.render(f"{self.telemetry.rpm} RPM", True, COLOR_GRAY)
        self.screen.blit(txt, txt.get_rect(center=(gauge_cx, gauge_cy + 35)))
        
        # Right side
        right_x = 440
        
        # Speed card
        pygame.draw.rect(self.screen, COLOR_BG_CARD, (right_x, TOP, 340, 150))
        
        speed = self.telemetry.speed_kmh
        if self.settings.use_mph:
            speed = int(speed * 0.621371)
        
        txt = self.font_huge.render(str(speed), True, COLOR_WHITE)
        self.screen.blit(txt, txt.get_rect(center=(right_x + 170, TOP + 60)))
        
        unit = "MPH" if self.settings.use_mph else "KMH"
        txt = self.font_medium.render(unit, True, COLOR_GRAY)
        self.screen.blit(txt, txt.get_rect(center=(right_x + 170, TOP + 120)))
        
        # Throttle/Brake
        pygame.draw.rect(self.screen, COLOR_BG_CARD, (right_x, TOP + 165, 165, 80))
        txt = self.font_tiny.render("THROTTLE", True, COLOR_GRAY)
        self.screen.blit(txt, (right_x + 15, TOP + 172))
        pygame.draw.rect(self.screen, COLOR_DARK_GRAY, (right_x + 15, TOP + 195, 135, 14))
        throttle_w = int(135 * self.telemetry.throttle_percent / 100)
        pygame.draw.rect(self.screen, COLOR_GREEN, (right_x + 15, TOP + 195, throttle_w, 14))
        txt = self.font_small.render(f"{self.telemetry.throttle_percent}%", True, COLOR_GREEN)
        self.screen.blit(txt, (right_x + 15, TOP + 215))
        
        pygame.draw.rect(self.screen, COLOR_BG_CARD, (right_x + 175, TOP + 165, 165, 80))
        txt = self.font_tiny.render("BRAKE", True, COLOR_GRAY)
        self.screen.blit(txt, (right_x + 190, TOP + 172))
        pygame.draw.rect(self.screen, COLOR_DARK_GRAY, (right_x + 190, TOP + 195, 135, 14))
        brake_w = int(135 * self.telemetry.brake_percent / 100)
        pygame.draw.rect(self.screen, COLOR_RED, (right_x + 190, TOP + 195, brake_w, 14))
        txt = self.font_small.render(f"{self.telemetry.brake_percent}%", True, COLOR_RED)
        self.screen.blit(txt, (right_x + 190, TOP + 215))
        
        # Lap times
        pygame.draw.rect(self.screen, COLOR_BG_CARD, (right_x, TOP + 260, 340, 90))
        
        lap_ms = self.telemetry.lap_time_ms
        lap_min = lap_ms // 60000
        lap_sec = (lap_ms % 60000) / 1000
        
        # Show timer status indicator
        status_text = "● RUN" if self.lap_timer_running else "○ STOP"
        status_color = COLOR_GREEN if self.lap_timer_running else COLOR_GRAY
        txt = self.font_tiny.render("CURRENT LAP", True, COLOR_GRAY)
        self.screen.blit(txt, (right_x + 20, TOP + 270))
        status_txt = self.font_tiny.render(status_text, True, status_color)
        self.screen.blit(status_txt, (right_x + 130, TOP + 270))
        txt = self.font_medium.render(f"{lap_min}:{lap_sec:05.2f}", True, COLOR_WHITE)
        self.screen.blit(txt, (right_x + 20, TOP + 290))
        
        best_ms = self.telemetry.best_lap_ms
        best_min = best_ms // 60000
        best_sec = (best_ms % 60000) / 1000
        
        txt = self.font_tiny.render("BEST", True, COLOR_GRAY)
        self.screen.blit(txt, (right_x + 220, TOP + 270))
        txt = self.font_medium.render(f"{best_min}:{best_sec:05.2f}", True, COLOR_PURPLE)
        self.screen.blit(txt, (right_x + 190, TOP + 295))
        
        # Lap timer button hints at bottom
        hint_y = PI_HEIGHT - 25
        hint = self.font_tiny.render("ENTER: Start/Stop   B: Reset", True, COLOR_GRAY)
        hint_rect = hint.get_rect(center=(PI_WIDTH // 2, hint_y))
        self.screen.blit(hint, hint_rect)
    
    def _render_tpms(self):
        """TPMS screen - Modern design with car silhouette"""
        TOP = 55
        
        car_cx, car_cy = PI_WIDTH // 2, TOP + (PI_HEIGHT - TOP) // 2
        
        # Draw car silhouette
        if self.car_image:
            car_rect = self.car_image.get_rect(center=(car_cx, car_cy))
            self.screen.blit(self.car_image, car_rect)
            car_w = self.car_image.get_width()
            car_h = self.car_image.get_height()
        else:
            # Fallback to rectangle
            car_w, car_h = 150, 250
            pygame.draw.rect(self.screen, COLOR_BG_CARD, 
                            (car_cx - car_w//2, car_cy - car_h//2, car_w, car_h))
            pygame.draw.rect(self.screen, COLOR_DARK_GRAY, 
                            (car_cx - car_w//2, car_cy - car_h//2, car_w, car_h), 2)
        
        # Tire info card positions around the car
        box_w, box_h = 140, 110
        tire_offset_x = car_w // 2 + box_w // 2 + 30
        tire_offset_y = car_h // 2 - 40
        
        positions = [
            (car_cx - tire_offset_x, car_cy - tire_offset_y, "FL", 0),
            (car_cx + tire_offset_x, car_cy - tire_offset_y, "FR", 1),
            (car_cx - tire_offset_x, car_cy + tire_offset_y, "RL", 2),
            (car_cx + tire_offset_x, car_cy + tire_offset_y, "RR", 3),
        ]
        
        for x, y, label, idx in positions:
            psi = self.telemetry.tire_pressure[idx]
            temp = self.telemetry.tire_temp[idx]
            last_update = self.telemetry.tpms_last_update_str[idx]
            
            # Determine color
            if psi < self.settings.tire_low_psi:
                color = COLOR_RED
            elif psi > self.settings.tire_high_psi:
                color = COLOR_YELLOW
            else:
                color = COLOR_GREEN
            
            # Modern card with glow effect
            glow = pygame.Surface((box_w + 8, box_h + 8), pygame.SRCALPHA)
            glow.fill((*color[:3], 30))
            self.screen.blit(glow, (x - box_w//2 - 4, y - box_h//2 - 4))
            
            # Card background
            pygame.draw.rect(self.screen, COLOR_BG_CARD,
                           (x - box_w//2, y - box_h//2, box_w, box_h))
            
            # Color accent bar
            pygame.draw.rect(self.screen, color,
                           (x - box_w//2, y - box_h//2, 5, box_h))
            
            # Label and timestamp on same line
            txt = self.font_small.render(label, True, COLOR_GRAY)
            self.screen.blit(txt, (x - box_w//2 + 12, y - box_h//2 + 5))
            
            # Per-tire timestamp (right side of label)
            timestamp_color = COLOR_GREEN if last_update != "--:--:--" else COLOR_DARK_GRAY
            time_txt = self.font_tiny.render(last_update, True, timestamp_color)
            self.screen.blit(time_txt, (x + box_w//2 - time_txt.get_width() - 8, y - box_h//2 + 8))
            
            # PSI value (large)
            txt = self.font_large.render(f"{psi:.1f}", True, color)
            self.screen.blit(txt, txt.get_rect(center=(x + 5, y - 5)))
            
            # Unit label
            txt = self.font_tiny.render("PSI", True, COLOR_GRAY)
            self.screen.blit(txt, txt.get_rect(center=(x + 5, y + 22)))
            
            # Temperature
            txt = self.font_small.render(f"{temp:.1f}°F", True, COLOR_GRAY)
            self.screen.blit(txt, txt.get_rect(center=(x + 5, y + 42)))
        
        # Status bar at bottom
        all_ok = all(
            self.settings.tire_low_psi <= psi <= self.settings.tire_high_psi
            for psi in self.telemetry.tire_pressure
        )
        
        status_color = COLOR_GREEN if all_ok else COLOR_YELLOW
        status_text = "ALL PRESSURES NORMAL" if all_ok else "! CHECK TIRE PRESSURES"
        
        pygame.draw.rect(self.screen, COLOR_BG_CARD, (PI_WIDTH//2 - 150, PI_HEIGHT - 45, 300, 35))
        pygame.draw.rect(self.screen, status_color, (PI_WIDTH//2 - 150, PI_HEIGHT - 45, 5, 35))
        txt = self.font_small.render(status_text, True, status_color)
        self.screen.blit(txt, txt.get_rect(center=(PI_WIDTH//2, PI_HEIGHT - 28)))
    
    def _render_engine(self):
        """Engine screen"""
        TOP = 55
        row1_y = TOP + 110
        row2_y = TOP + 290
        
        # Coolant
        cool = self.telemetry.coolant_temp_f
        cool_color = COLOR_RED if cool >= self.settings.coolant_warn_f else COLOR_TEAL
        self._render_gauge(150, row1_y, "COOLANT", cool, "F", 180, self.settings.coolant_warn_f, 250, cool_color)
        
        # Oil Temp
        oil = self.telemetry.oil_temp_f
        oil_color = COLOR_RED if oil >= self.settings.oil_warn_f else COLOR_GREEN
        self._render_gauge(400, row1_y, "OIL TEMP", oil, "F", 150, self.settings.oil_warn_f, 280, oil_color)
        
        # Oil Pressure
        self._render_gauge(650, row1_y, "OIL PSI", self.telemetry.oil_pressure_psi, "", 0, 30, 80, COLOR_ACCENT)
        
        # Fuel
        fuel = self.telemetry.fuel_level_percent
        fuel_color = COLOR_RED if fuel < 15 else (COLOR_YELLOW if fuel < 25 else COLOR_GREEN)
        self._render_gauge_bar(150, row2_y, "FUEL", fuel, "%", fuel_color)
        
        # Voltage
        volt = self.telemetry.voltage
        volt_color = COLOR_RED if volt < 12.0 else (COLOR_YELLOW if volt < 13.0 else COLOR_GREEN)
        self._render_gauge(400, row2_y, "VOLTAGE", volt, "V", 11, 13.5, 15, volt_color)
        
        # Intake
        self._render_gauge(650, row2_y, "INTAKE", self.telemetry.intake_temp_f, "F", 50, 120, 180, COLOR_CYAN)
    
    def _render_gauge(self, cx, cy, label, value, unit, min_v, warn_v, max_v, color):
        """Render a circular gauge"""
        r = 65
        
        pygame.draw.circle(self.screen, COLOR_BG_CARD, (cx, cy), r + 5)
        pygame.draw.circle(self.screen, COLOR_BG, (cx, cy), r - 5)
        
        # Arc background
        self._draw_arc(self.screen, cx, cy, r, 8, 135, 405, COLOR_DARK_GRAY)
        
        # Value arc
        pct = (value - min_v) / (max_v - min_v) if max_v != min_v else 0
        pct = max(0, min(1, pct))
        angle = 270 * pct
        if angle > 0:
            self._draw_arc(self.screen, cx, cy, r, 8, 135, 135 + angle, color)
        
        # Value text
        val_str = f"{value:.1f}" if isinstance(value, float) else str(value)
        txt = self.font_medium.render(val_str, True, color)
        self.screen.blit(txt, txt.get_rect(center=(cx, cy - 5)))
        
        # Label
        txt = self.font_tiny.render(label, True, COLOR_GRAY)
        self.screen.blit(txt, txt.get_rect(center=(cx, cy + 25)))
    
    def _render_gauge_bar(self, cx, cy, label, value, unit, color):
        """Render a horizontal bar gauge"""
        bar_w, bar_h = 120, 20
        
        pygame.draw.rect(self.screen, COLOR_BG_CARD, (cx - 70, cy - 40, 140, 80))
        
        txt = self.font_tiny.render(label, True, COLOR_GRAY)
        self.screen.blit(txt, txt.get_rect(center=(cx, cy - 25)))
        
        pygame.draw.rect(self.screen, COLOR_DARK_GRAY, (cx - bar_w//2, cy - 5, bar_w, bar_h))
        fill_w = int(bar_w * value / 100)
        if fill_w > 0:
            pygame.draw.rect(self.screen, color, (cx - bar_w//2, cy - 5, fill_w, bar_h))
        
        txt = self.font_small.render(f"{value:.0f}{unit}", True, color)
        self.screen.blit(txt, txt.get_rect(center=(cx, cy + 25)))
    
    def _is_imu_data_stale(self, timeout_sec: float = 1.0) -> bool:
        """Check if IMU data is stale (no IMU data received within timeout)"""
        # In demo mode, data is never stale
        if self.settings.demo_mode:
            return False
        # Check if ESP32 handler is connected and receiving IMU data specifically
        if self.esp32_handler and self.esp32_handler.connected:
            # Use last_imu_time (specific to IMU messages) instead of last_rx_time (any message)
            # This prevents false 'no data' when ESP32 sends other messages but IMU rate varies
            return (time.time() - self.esp32_handler.last_imu_time) > timeout_sec
        # No handler = no data
        return True
    
    def _render_gforce(self):
        """
        Tilt/G-Force screen - ball position from orientation, size from forward acceleration
        
        CIRCLE POSITION = Car orientation (tilt from gyroscope integration)
          - Nose DOWN  → circle moves UP (top of screen)
          - Nose UP    → circle moves DOWN (bottom of screen)
          - Roll LEFT  → circle moves LEFT
          - Roll RIGHT → circle moves RIGHT
          - 10 degrees tilt = circle at outer ring edge
        
        CIRCLE SIZE = Forward acceleration (linear accel, gravity-subtracted)
          - Zero acceleration → normal size
          - Acceleration (speeding up) → circle GROWS
          - Deceleration (braking) → circle SHRINKS
        """
        TOP = 55
        
        # Check if IMU data is being received (2 second timeout)
        # ESP32 sends IMU at 10Hz, 2s allows for occasional missed packets
        imu_data_stale = self._is_imu_data_stale(timeout_sec=2.0)
        
        ball_cx, ball_cy = 230, TOP + 180
        ball_r = 155
        
        pygame.draw.circle(self.screen, COLOR_BG_CARD, (ball_cx, ball_cy), ball_r + 8)
        pygame.draw.circle(self.screen, COLOR_BG, (ball_cx, ball_cy), ball_r)
        
        # Draw rings for tilt degrees (2.5°, 5°, 10°)
        # 10° = full radius
        deg_scale = ball_r / 10.0  # pixels per degree
        for deg in [2.5, 5.0, 10.0]:
            r = int(deg * deg_scale)
            pygame.draw.circle(self.screen, COLOR_DARK_GRAY, (ball_cx, ball_cy), r, 1)
        
        pygame.draw.line(self.screen, COLOR_DARK_GRAY,
                        (ball_cx - ball_r, ball_cy), (ball_cx + ball_r, ball_cy), 1)
        pygame.draw.line(self.screen, COLOR_DARK_GRAY,
                        (ball_cx, ball_cy - ball_r), (ball_cx, ball_cy + ball_r), 1)
        
        # Ring labels (degrees)
        for deg, r in [(2.5, int(2.5 * deg_scale)), (5, int(5 * deg_scale)), (10, int(10 * deg_scale))]:
            label = f"{deg}°" if deg == 10 else f"{deg}"
            txt = self.font_tiny.render(label, True, COLOR_DARK_GRAY)
            self.screen.blit(txt, (ball_cx + r + 3, ball_cy - 8))
        
        if imu_data_stale:
            # Show "No Data" message in the G-ball area
            txt = self.font_medium.render("NO DATA", True, COLOR_YELLOW)
            self.screen.blit(txt, txt.get_rect(center=(ball_cx, ball_cy - 15)))
            txt = self.font_tiny.render("Waiting for ESP32 IMU...", True, COLOR_GRAY)
            self.screen.blit(txt, txt.get_rect(center=(ball_cx, ball_cy + 20)))
        else:
            # Ball POSITION from orientation (pitch/roll in degrees)
            # Received from ESP32 via serial: pitch positive = nose UP, roll positive = roll RIGHT
            pitch = getattr(self.telemetry, 'orientation_pitch', 0.0)
            roll = getattr(self.telemetry, 'orientation_roll', 0.0)
            
            # Position mapping (same as ESP32):
            # - Nose DOWN (negative pitch) → ball UP (negative Y offset)
            # - Nose UP (positive pitch) → ball DOWN (positive Y offset)
            # - Roll LEFT (negative roll) → ball LEFT
            # - Roll RIGHT (positive roll) → ball RIGHT
            gx = ball_cx + int(roll * deg_scale)
            gy = ball_cy + int(pitch * deg_scale)  # Nose up = ball down
            
            # Ball SIZE from FORWARD acceleration only (not total magnitude)
            # linear_accel_y = forward acceleration with gravity subtracted
            # Positive = accelerating forward, Negative = braking
            forward_accel = getattr(self.telemetry, 'linear_accel_y', 0.0)
            
            # Normal size 14, grows with accel (+10 pixels per G), shrinks with braking
            ball_size = 14 + int(forward_accel * 10)
            ball_size = max(6, min(24, ball_size))
            
            # Clamp to circle
            dx, dy = gx - ball_cx, gy - ball_cy
            dist = math.sqrt(dx*dx + dy*dy)
            if dist > ball_r - ball_size - 2:
                scale = (ball_r - ball_size - 2) / dist
                gx = ball_cx + int(dx * scale)
                gy = ball_cy + int(dy * scale)
            
            # Color based on forward acceleration direction
            # Red/Orange = acceleration, Green = neutral, Yellow/Cyan = braking
            if forward_accel > 0.3:
                ball_color = COLOR_RED       # Hard acceleration
            elif forward_accel > 0.1:
                ball_color = COLOR_ORANGE    # Light acceleration
            elif forward_accel < -0.3:
                ball_color = COLOR_CYAN      # Hard braking
            elif forward_accel < -0.1:
                ball_color = COLOR_YELLOW    # Light braking
            else:
                ball_color = COLOR_GREEN     # Neutral
            
            # Glow size also scales
            glow_size = ball_size + 10
            glow = pygame.Surface((glow_size * 2, glow_size * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*ball_color[:3], 100), (glow_size, glow_size), glow_size - 5)
            self.screen.blit(glow, (gx - glow_size, gy - glow_size))
            
            pygame.draw.circle(self.screen, ball_color, (gx, gy), ball_size)
            pygame.draw.circle(self.screen, COLOR_WHITE, (gx, gy), ball_size, 2)
        
        # Right panel cards - RAW DATA DISPLAY
        right_x = 440
        card_w = 340
        card_h = 60
        spacing = 8
        
        # Card 1: Accelerometer (raw)
        y = TOP
        pygame.draw.rect(self.screen, COLOR_BG_CARD, (right_x, y, card_w, card_h))
        pygame.draw.rect(self.screen, COLOR_CYAN, (right_x, y, 4, card_h))
        txt = self.font_tiny.render("ACCELEROMETER (G)", True, COLOR_GRAY)
        self.screen.blit(txt, (right_x + 15, y + 5))
        if not imu_data_stale:
            g_vert = getattr(self.telemetry, 'g_vertical', 0.0)
            txt = self.font_small.render(f"X:{self.telemetry.g_lateral:+.2f}  Y:{self.telemetry.g_longitudinal:+.2f}  Z:{g_vert:+.2f}", True, COLOR_CYAN)
        else:
            txt = self.font_small.render("--", True, COLOR_DARK_GRAY)
        self.screen.blit(txt, (right_x + 15, y + 28))
        
        # Card 2: Gyroscope
        y += card_h + spacing
        pygame.draw.rect(self.screen, COLOR_BG_CARD, (right_x, y, card_w, card_h))
        pygame.draw.rect(self.screen, COLOR_ORANGE, (right_x, y, 4, card_h))
        txt = self.font_tiny.render("GYROSCOPE (°/s)", True, COLOR_GRAY)
        self.screen.blit(txt, (right_x + 15, y + 5))
        if not imu_data_stale:
            gx = getattr(self.telemetry, 'gyro_x', 0.0)
            gy = getattr(self.telemetry, 'gyro_y', 0.0)
            gz = getattr(self.telemetry, 'gyro_z', 0.0)
            txt = self.font_small.render(f"X:{gx:+.1f}  Y:{gy:+.1f}  Z:{gz:+.1f}", True, COLOR_ORANGE)
        else:
            txt = self.font_small.render("--", True, COLOR_DARK_GRAY)
        self.screen.blit(txt, (right_x + 15, y + 28))
        
        # Card 3: Linear Acceleration (gravity removed)
        y += card_h + spacing
        pygame.draw.rect(self.screen, COLOR_BG_CARD, (right_x, y, card_w, card_h))
        pygame.draw.rect(self.screen, COLOR_GREEN, (right_x, y, 4, card_h))
        txt = self.font_tiny.render("LINEAR ACCEL (G)", True, COLOR_GRAY)
        self.screen.blit(txt, (right_x + 15, y + 5))
        if not imu_data_stale:
            lin_x = getattr(self.telemetry, 'linear_accel_x', 0.0)
            lin_y = getattr(self.telemetry, 'linear_accel_y', 0.0)
            txt = self.font_small.render(f"X:{lin_x:+.3f}  Y:{lin_y:+.3f}", True, COLOR_GREEN)
        else:
            txt = self.font_small.render("--", True, COLOR_DARK_GRAY)
        self.screen.blit(txt, (right_x + 15, y + 28))
        
        # Card 4: Orientation (from gyro integration)
        y += card_h + spacing
        pygame.draw.rect(self.screen, COLOR_BG_CARD, (right_x, y, card_w, card_h))
        pygame.draw.rect(self.screen, COLOR_PURPLE, (right_x, y, 4, card_h))
        txt = self.font_tiny.render("ORIENTATION (°)", True, COLOR_GRAY)
        self.screen.blit(txt, (right_x + 15, y + 5))
        if not imu_data_stale:
            pitch = getattr(self.telemetry, 'orientation_pitch', 0.0)
            roll = getattr(self.telemetry, 'orientation_roll', 0.0)
            txt = self.font_small.render(f"Pitch:{pitch:+.1f}  Roll:{roll:+.1f}", True, COLOR_PURPLE)
        else:
            txt = self.font_small.render("--", True, COLOR_DARK_GRAY)
        self.screen.blit(txt, (right_x + 15, y + 28))
        
        # Card 5: Forward Acceleration (what affects ball size)
        y += card_h + spacing
        pygame.draw.rect(self.screen, COLOR_BG_CARD, (right_x, y, card_w, card_h))
        pygame.draw.rect(self.screen, COLOR_ACCENT, (right_x, y, 4, card_h))
        txt = self.font_tiny.render("FORWARD ACCEL", True, COLOR_GRAY)
        self.screen.blit(txt, (right_x + 15, y + 5))
        if not imu_data_stale:
            forward = getattr(self.telemetry, 'linear_accel_y', 0.0)
            # Color matches ball color logic
            if forward > 0.3:
                fwd_color = COLOR_RED
            elif forward > 0.1:
                fwd_color = COLOR_ORANGE
            elif forward < -0.3:
                fwd_color = COLOR_CYAN
            elif forward < -0.1:
                fwd_color = COLOR_YELLOW
            else:
                fwd_color = COLOR_GREEN
            txt = self.font_medium.render(f"{forward:+.2f}G", True, fwd_color)
        else:
            txt = self.font_medium.render("--", True, COLOR_DARK_GRAY)
        self.screen.blit(txt, (right_x + 15, y + 25))
        
        # IMU source / status
        if imu_data_stale:
            txt = self.font_tiny.render("⚠ ESP32 IMU: No Data", True, COLOR_YELLOW)
        else:
            txt = self.font_tiny.render("Source: QMI8658 IMU (6-axis)", True, COLOR_DARK_GRAY)
        self.screen.blit(txt, txt.get_rect(center=(ball_cx, PI_HEIGHT - 15)))
    
    def _render_diagnostics(self):
        """Diagnostics screen - vehicle warnings, DTCs, and system status"""
        TOP = 55
        
        # Warning colors
        COLOR_WARNING_ON = (255, 50, 50)      # Red when active
        COLOR_WARNING_OFF = (50, 50, 50)      # Dark gray when inactive
        COLOR_CAUTION = (255, 180, 0)         # Amber for cautions
        COLOR_INFO_BLUE = (50, 150, 255)      # Blue for info indicators
        
        # --- Left Column: Warning Indicators (2x4 grid) ---
        left_x = 30
        icon_w, icon_h = 170, 80
        gap = 15
        
        # Warning indicator data: (name, short_label, is_active, severity)
        # severity: 'critical'=red, 'warning'=amber, 'info'=blue
        warnings = [
            ("CHECK ENGINE", "CEL", self.telemetry.check_engine_light, 'critical'),
            ("ABS WARNING", "ABS", self.telemetry.abs_warning, 'critical'),
            ("TRACTION OFF", "TC OFF", self.telemetry.traction_control_off, 'warning'),
            ("OIL PRESSURE", "OIL", self.telemetry.oil_pressure_warning, 'critical'),
            ("BATTERY", "BATT", self.telemetry.battery_warning, 'warning'),
            ("BRAKE", "BRAKE", self.telemetry.brake_warning, 'critical'),
            ("AIRBAG", "SRS", self.telemetry.airbag_warning, 'critical'),
            ("SEATBELT", "BELT", self.telemetry.seatbelt_warning, 'warning'),
        ]
        
        for i, (name, short, active, severity) in enumerate(warnings):
            row = i // 2
            col = i % 2
            x = left_x + col * (icon_w + gap)
            y = TOP + row * (icon_h + gap)
            
            # Background
            if active:
                if severity == 'critical':
                    bg_color = (80, 20, 20)
                    border_color = COLOR_WARNING_ON
                elif severity == 'warning':
                    bg_color = (80, 60, 0)
                    border_color = COLOR_CAUTION
                else:
                    bg_color = (20, 50, 80)
                    border_color = COLOR_INFO_BLUE
            else:
                bg_color = COLOR_BG_CARD
                border_color = COLOR_WARNING_OFF
            
            pygame.draw.rect(self.screen, bg_color, (x, y, icon_w, icon_h))
            pygame.draw.rect(self.screen, border_color, (x, y, icon_w, icon_h), 2)
            
            # Icon text (short label)
            icon_color = border_color if active else COLOR_DARK_GRAY
            txt = self.font_small.render(short, True, icon_color)
            self.screen.blit(txt, txt.get_rect(center=(x + icon_w//2, y + 30)))
            
            # Full name below
            txt = self.font_tiny.render(name, True, COLOR_GRAY if not active else border_color)
            self.screen.blit(txt, txt.get_rect(center=(x + icon_w//2, y + 58)))
        
        # --- Middle Column: DTC Codes ---
        mid_x = 390
        dtc_w = 200
        
        # DTC Header
        pygame.draw.rect(self.screen, COLOR_BG_CARD, (mid_x, TOP, dtc_w, 35))
        pygame.draw.rect(self.screen, COLOR_WARNING_ON, (mid_x, TOP, 4, 35))
        txt = self.font_small.render("DTC CODES", True, COLOR_WHITE)
        self.screen.blit(txt, (mid_x + 15, TOP + 8))
        
        # DTC Count badge
        dtc_count = self.telemetry.dtc_count
        count_color = COLOR_WARNING_ON if dtc_count > 0 else COLOR_SUCCESS
        pygame.draw.circle(self.screen, count_color, (mid_x + dtc_w - 25, TOP + 17), 14)
        txt = self.font_small.render(str(dtc_count), True, COLOR_WHITE)
        self.screen.blit(txt, txt.get_rect(center=(mid_x + dtc_w - 25, TOP + 17)))
        
        # DTC List
        dtc_y = TOP + 45
        dtc_item_h = 55
        if dtc_count > 0:
            for i in range(min(dtc_count, 5)):  # Show up to 5 codes
                code = self.telemetry.dtc_codes[i] if i < len(self.telemetry.dtc_codes) else "-----"
                pygame.draw.rect(self.screen, (40, 25, 25), (mid_x, dtc_y + i * dtc_item_h, dtc_w, dtc_item_h - 5))
                pygame.draw.rect(self.screen, COLOR_WARNING_ON, (mid_x, dtc_y + i * dtc_item_h, 3, dtc_item_h - 5))
                
                # Code
                txt = self.font_small.render(code, True, COLOR_WARNING_ON)
                self.screen.blit(txt, (mid_x + 15, dtc_y + i * dtc_item_h + 12))
                
                # Description placeholder
                txt = self.font_tiny.render("Tap to view details", True, COLOR_DARK_GRAY)
                self.screen.blit(txt, (mid_x + 15, dtc_y + i * dtc_item_h + 32))
        else:
            # No codes - show success message
            pygame.draw.rect(self.screen, (20, 40, 20), (mid_x, dtc_y, dtc_w, 80))
            txt = self.font_small.render("NO CODES", True, COLOR_SUCCESS)
            self.screen.blit(txt, txt.get_rect(center=(mid_x + dtc_w//2, dtc_y + 30)))
            txt = self.font_tiny.render("System OK", True, COLOR_SUCCESS)
            self.screen.blit(txt, txt.get_rect(center=(mid_x + dtc_w//2, dtc_y + 55)))
        
        # --- Right Column: Traction & Slip ---
        right_x = 610
        col_w = 170
        
        # Traction Control Status
        pygame.draw.rect(self.screen, COLOR_BG_CARD, (right_x, TOP, col_w, 90))
        tc_active = self.telemetry.traction_control_active
        tc_off = self.telemetry.traction_control_off
        
        if tc_off:
            tc_color = COLOR_CAUTION
            tc_status = "DISABLED"
        elif tc_active:
            tc_color = COLOR_INFO_BLUE
            tc_status = "ACTIVE"
        else:
            tc_color = COLOR_SUCCESS
            tc_status = "READY"
        
        pygame.draw.rect(self.screen, tc_color, (right_x, TOP, 4, 90))
        txt = self.font_tiny.render("TRACTION CTRL", True, COLOR_GRAY)
        self.screen.blit(txt, (right_x + 15, TOP + 10))
        txt = self.font_small.render(tc_status, True, tc_color)
        self.screen.blit(txt, (right_x + 15, TOP + 40))
        
        # Wheel Slip Visualization (mini car top view)
        slip_y = TOP + 110
        pygame.draw.rect(self.screen, COLOR_BG_CARD, (right_x, slip_y, col_w, 150))
        pygame.draw.rect(self.screen, COLOR_CYAN, (right_x, slip_y, 4, 150))
        txt = self.font_tiny.render("WHEEL SLIP", True, COLOR_GRAY)
        self.screen.blit(txt, (right_x + 15, slip_y + 8))
        
        # Mini car outline
        car_cx = right_x + col_w // 2
        car_cy = slip_y + 90
        car_w, car_h = 50, 80
        pygame.draw.rect(self.screen, COLOR_DARK_GRAY, 
                        (car_cx - car_w//2, car_cy - car_h//2, car_w, car_h), 1)
        
        # Wheel positions (FL, FR, RL, RR)
        wheel_pos = [
            (car_cx - 30, car_cy - 25),  # FL
            (car_cx + 30, car_cy - 25),  # FR
            (car_cx - 30, car_cy + 25),  # RL
            (car_cx + 30, car_cy + 25),  # RR
        ]
        wheel_labels = ["FL", "FR", "RL", "RR"]
        
        for i, ((wx, wy), label) in enumerate(zip(wheel_pos, wheel_labels)):
            slip = self.telemetry.wheel_slip[i] if i < len(self.telemetry.wheel_slip) else 0.0
            
            # Color based on slip percentage
            if slip > 15:
                w_color = COLOR_WARNING_ON
            elif slip > 5:
                w_color = COLOR_CAUTION
            else:
                w_color = COLOR_SUCCESS
            
            # Wheel rectangle
            pygame.draw.rect(self.screen, w_color, (wx - 8, wy - 12, 16, 24))
            
            # Slip percentage
            txt = self.font_tiny.render(f"{slip:.0f}%", True, w_color)
            self.screen.blit(txt, txt.get_rect(center=(wx, wy + 22)))
        
        # --- Bottom: Additional Indicators ---
        bottom_y = TOP + 280
        ind_w = 110
        ind_h = 50
        indicators = [
            ("DOOR", self.telemetry.door_ajar, COLOR_CAUTION),
            ("HIGH BEAM", self.telemetry.high_beam_on, COLOR_INFO_BLUE),
            ("FOG LIGHT", self.telemetry.fog_light_on, COLOR_SUCCESS),
        ]
        
        for i, (name, active, color) in enumerate(indicators):
            x = right_x + (i % 2) * (ind_w + 10) - 60
            y = bottom_y + (i // 2) * (ind_h + 5)
            
            bg = (40, 40, 40) if not active else (color[0]//4, color[1]//4, color[2]//4)
            border = COLOR_DARK_GRAY if not active else color
            
            pygame.draw.rect(self.screen, bg, (x, y, ind_w, ind_h))
            pygame.draw.rect(self.screen, border, (x, y, ind_w, ind_h), 1)
            
            txt = self.font_tiny.render(name, True, border if active else COLOR_DARK_GRAY)
            self.screen.blit(txt, txt.get_rect(center=(x + ind_w//2, y + ind_h//2)))
        
        # Status summary at very bottom
        active_warnings = sum([
            self.telemetry.check_engine_light,
            self.telemetry.abs_warning,
            self.telemetry.oil_pressure_warning,
            self.telemetry.battery_warning,
            self.telemetry.brake_warning,
            self.telemetry.airbag_warning,
        ])
        
        if active_warnings > 0:
            status_txt = f"{active_warnings} ACTIVE WARNING{'S' if active_warnings > 1 else ''}"
            status_color = COLOR_WARNING_ON
        else:
            status_txt = "ALL SYSTEMS NORMAL"
            status_color = COLOR_SUCCESS
        
        txt = self.font_small.render(status_txt, True, status_color)
        self.screen.blit(txt, txt.get_rect(center=(PI_WIDTH // 2, PI_HEIGHT - 20)))
    
    def _render_system(self):
        """System screen - Raspberry Pi hardware diagnostics"""
        TOP = 55
        
        # Get Pi system info
        import subprocess
        
        # CPU Temperature
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                cpu_temp_c = int(f.read().strip()) / 1000.0
                cpu_temp_f = cpu_temp_c * 9.0 / 5.0 + 32.0
        except:
            cpu_temp_c = 0
            cpu_temp_f = 0
        
        # CPU Usage
        try:
            with open('/proc/stat', 'r') as f:
                cpu_line = f.readline()
                cpu_parts = cpu_line.split()[1:5]
                idle = int(cpu_parts[3])
                total = sum(int(x) for x in cpu_parts)
                # This is instantaneous, not averaged
                cpu_usage = 100 - (idle * 100 / total) if total > 0 else 0
        except:
            cpu_usage = 0
        
        # Memory info
        try:
            with open('/proc/meminfo', 'r') as f:
                lines = f.readlines()
                mem_total = int(lines[0].split()[1]) / 1024  # MB
                mem_free = int(lines[1].split()[1]) / 1024   # MB
                mem_available = int(lines[2].split()[1]) / 1024  # MB
                mem_used_pct = (1 - mem_available / mem_total) * 100 if mem_total > 0 else 0
        except:
            mem_total = 0
            mem_available = 0
            mem_used_pct = 0
        
        # Disk usage
        try:
            result = subprocess.run(['df', '-h', '/'], capture_output=True, text=True)
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:
                parts = lines[1].split()
                disk_total = parts[1]
                disk_used_pct = parts[4].replace('%', '')
            else:
                disk_total = "?"
                disk_used_pct = 0
        except:
            disk_total = "?"
            disk_used_pct = 0
        
        # Uptime
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_secs = int(float(f.read().split()[0]))
                hours = uptime_secs // 3600
                mins = (uptime_secs % 3600) // 60
        except:
            hours = 0
            mins = 0
        
        # Network IP
        try:
            result = subprocess.run(['hostname', '-I'], capture_output=True, text=True)
            ip_addr = result.stdout.strip().split()[0] if result.stdout.strip() else "N/A"
        except:
            ip_addr = "N/A"
        
        # Card layout - 2 columns, 5 rows (smaller cards to fit)
        card_w = 370
        card_h = 65  # Reduced from 75 to fit 5 rows
        gap = 10     # Reduced gap
        left_x = 20
        right_x = left_x + card_w + gap
        
        # Row 1: CPU Temp and Memory
        y = TOP + 5
        
        # CPU Temperature
        pygame.draw.rect(self.screen, COLOR_BG_CARD, (left_x, y, card_w, card_h))
        temp_color = COLOR_RED if cpu_temp_f > 175 else COLOR_YELLOW if cpu_temp_f > 150 else COLOR_CYAN
        pygame.draw.rect(self.screen, temp_color, (left_x, y, 5, card_h))
        txt = self.font_tiny.render("CPU TEMPERATURE", True, COLOR_GRAY)
        self.screen.blit(txt, (left_x + 15, y + 5))
        txt = self.font_small.render(f"{cpu_temp_f:.1f}°F ({cpu_temp_c:.1f}°C)", True, temp_color)
        self.screen.blit(txt, (left_x + 15, y + 28))
        
        # Memory card
        pygame.draw.rect(self.screen, COLOR_BG_CARD, (right_x, y, card_w, card_h))
        pygame.draw.rect(self.screen, COLOR_GREEN, (right_x, y, 5, card_h))

        txt = self.font_tiny.render("MEMORY USAGE", True, COLOR_GRAY)
        self.screen.blit(txt, (right_x + 15, y + 5))
        mem_color = COLOR_RED if mem_used_pct > 85 else COLOR_YELLOW if mem_used_pct > 70 else COLOR_GREEN
        txt = self.font_small.render(f"{mem_used_pct:.0f}% ({mem_available:.0f}MB free)", True, mem_color)
        self.screen.blit(txt, (right_x + 15, y + 28))
        
        # Row 2: Disk and Network
        y = TOP + 5 + card_h + gap
        
        # Disk Usage
        pygame.draw.rect(self.screen, COLOR_BG_CARD, (left_x, y, card_w, card_h))
        pygame.draw.rect(self.screen, COLOR_PURPLE, (left_x, y, 5, card_h))
        txt = self.font_tiny.render("DISK USAGE", True, COLOR_GRAY)
        self.screen.blit(txt, (left_x + 15, y + 5))
        try:
            disk_pct = int(disk_used_pct)
        except:
            disk_pct = 0
        disk_color = COLOR_RED if disk_pct > 90 else COLOR_YELLOW if disk_pct > 75 else COLOR_PURPLE
        txt = self.font_small.render(f"{disk_pct}% (Total: {disk_total})", True, disk_color)
        self.screen.blit(txt, (left_x + 15, y + 28))
        
        # Network IP
        pygame.draw.rect(self.screen, COLOR_BG_CARD, (right_x, y, card_w, card_h))
        pygame.draw.rect(self.screen, COLOR_ACCENT, (right_x, y, 5, card_h))
        txt = self.font_tiny.render("NETWORK IP", True, COLOR_GRAY)
        self.screen.blit(txt, (right_x + 15, y + 5))
        txt = self.font_small.render(ip_addr, True, COLOR_ACCENT)
        self.screen.blit(txt, (right_x + 15, y + 28))
        
        # Row 3: Uptime and Power Status
        y = TOP + 5 + 2 * (card_h + gap)
        
        # Uptime
        pygame.draw.rect(self.screen, COLOR_BG_CARD, (left_x, y, card_w, card_h))
        pygame.draw.rect(self.screen, COLOR_ORANGE, (left_x, y, 5, card_h))
        txt = self.font_tiny.render("UPTIME", True, COLOR_GRAY)
        self.screen.blit(txt, (left_x + 15, y + 5))
        if hours > 24:
            days = hours // 24
            hrs = hours % 24
            uptime_str = f"{days}d {hrs}h {mins}m"
        else:
            uptime_str = f"{hours}h {mins}m"
        txt = self.font_small.render(uptime_str, True, COLOR_ORANGE)
        self.screen.blit(txt, (left_x + 15, y + 28))
        
        # Power Status (check for undervoltage/throttling)
        pygame.draw.rect(self.screen, COLOR_BG_CARD, (right_x, y, card_w, card_h))
        pygame.draw.rect(self.screen, COLOR_YELLOW, (right_x, y, 5, card_h))
        txt = self.font_tiny.render("POWER STATUS", True, COLOR_GRAY)
        self.screen.blit(txt, (right_x + 15, y + 5))
        
        # Check throttle status via vcgencmd
        try:
            result = subprocess.run(['vcgencmd', 'get_throttled'], capture_output=True, text=True)
            throttle_hex = result.stdout.strip().split('=')[1] if '=' in result.stdout else '0x0'

            throttle_val = int(throttle_hex, 16)
            
            # Bit meanings: 0=undervoltage, 1=arm freq capped, 2=throttled, 3=soft temp limit
            undervoltage = throttle_val & 0x1
            throttled = throttle_val & 0x4
            
            if undervoltage:
                power_status = "LOW VOLTAGE!"
                power_color = COLOR_RED
            elif throttled:
                power_status = "THROTTLED"
                power_color = COLOR_YELLOW
            else:
                power_status = "5V OK"
                power_color = COLOR_GREEN
        except:
            power_status = "5V (est)"
            power_color = COLOR_GREEN
        
        txt = self.font_small.render(power_status, True, power_color)
        self.screen.blit(txt, (right_x + 15, y + 28))
        
        # Row 4: Display and CAN status
        y = TOP + 5 + 3 * (card_h + gap)
        
        # Display FPS/Status
        pygame.draw.rect(self.screen, COLOR_BG_CARD, (left_x, y, card_w, card_h))
        pygame.draw.rect(self.screen, COLOR_TEAL, (left_x, y, 5, card_h))
        txt = self.font_tiny.render("DISPLAY INFO", True, COLOR_GRAY)
        self.screen.blit(txt, (left_x + 15, y + 5))
        
        fps = self.clock.get_fps()
        txt = self.font_tiny.render(f"FPS: {fps:.1f}  {PI_WIDTH}x{PI_HEIGHT}  {self.current_screen.name}", True, COLOR_TEAL)
        self.screen.blit(txt, (left_x + 15, y + 28))
        
        # CAN Bus Status
        pygame.draw.rect(self.screen, COLOR_BG_CARD, (right_x, y, card_w, card_h))
        
        if self.settings.demo_mode:
            pygame.draw.rect(self.screen, COLOR_ORANGE, (right_x, y, 5, card_h))
            txt = self.font_tiny.render("CAN BUS", True, COLOR_GRAY)
            self.screen.blit(txt, (right_x + 15, y + 5))
            txt = self.font_small.render("DEMO MODE", True, COLOR_ORANGE)
            self.screen.blit(txt, (right_x + 15, y + 28))
        elif self.can_handler and self.can_handler.is_receiving_data():
            pygame.draw.rect(self.screen, COLOR_GREEN, (right_x, y, 5, card_h))
            txt = self.font_tiny.render("CAN BUS", True, COLOR_GRAY)
            self.screen.blit(txt, (right_x + 15, y + 5))
            hs = "HS " if self.can_handler.hs_can else ""
            ms = "MS" if self.can_handler.ms_can else ""
            txt = self.font_small.render(f"OK ({hs}{ms})", True, COLOR_GREEN)
            self.screen.blit(txt, (right_x + 15, y + 28))
        elif self.can_handler and self.can_handler.connected:
            pygame.draw.rect(self.screen, COLOR_YELLOW, (right_x, y, 5, card_h))
            txt = self.font_tiny.render("CAN BUS", True, COLOR_GRAY)
            self.screen.blit(txt, (right_x + 15, y + 5))
            txt = self.font_small.render("WAITING...", True, COLOR_YELLOW)
            self.screen.blit(txt, (right_x + 15, y + 28))
        else:
            pygame.draw.rect(self.screen, COLOR_RED, (right_x, y, 5, card_h))
            txt = self.font_tiny.render("CAN BUS", True, COLOR_GRAY)
            self.screen.blit(txt, (right_x + 15, y + 5))
            txt = self.font_small.render("OFFLINE", True, COLOR_RED)
            self.screen.blit(txt, (right_x + 15, y + 28))
        
        # Row 5: ESP32 Serial Status
        y = TOP + 5 + 4 * (card_h + gap)
        
        # ESP32 Serial Status
        pygame.draw.rect(self.screen, COLOR_BG_CARD, (left_x, y, card_w, card_h))
        
        if self.settings.demo_mode:
            pygame.draw.rect(self.screen, COLOR_ORANGE, (left_x, y, 5, card_h))
            txt = self.font_tiny.render("ESP32 SERIAL (TPMS + IMU)", True, COLOR_GRAY)
            self.screen.blit(txt, (left_x + 15, y + 5))
            txt = self.font_small.render("DEMO MODE", True, COLOR_ORANGE)
            self.screen.blit(txt, (left_x + 15, y + 28))
        elif self.esp32_handler and self.esp32_handler.is_receiving_data():
            pygame.draw.rect(self.screen, COLOR_GREEN, (left_x, y, 5, card_h))
            txt = self.font_tiny.render("ESP32 SERIAL (TPMS + IMU)", True, COLOR_GRAY)
            self.screen.blit(txt, (left_x + 15, y + 5))
            txt = self.font_small.render("RECEIVING DATA", True, COLOR_GREEN)
            self.screen.blit(txt, (left_x + 15, y + 28))
        elif self.esp32_handler and self.esp32_handler.connected:
            pygame.draw.rect(self.screen, COLOR_YELLOW, (left_x, y, 5, card_h))
            txt = self.font_tiny.render("ESP32 SERIAL (TPMS + IMU)", True, COLOR_GRAY)
            self.screen.blit(txt, (left_x + 15, y + 5))
            txt = self.font_small.render("WAITING...", True, COLOR_YELLOW)
            self.screen.blit(txt, (left_x + 15, y + 28))
        else:
            pygame.draw.rect(self.screen, COLOR_RED, (left_x, y, 5, card_h))
            txt = self.font_tiny.render("ESP32 SERIAL (TPMS + IMU)", True, COLOR_GRAY)
            self.screen.blit(txt, (left_x + 15, y + 5))
            txt = self.font_small.render("OFFLINE", True, COLOR_RED)
            self.screen.blit(txt, (left_x + 15, y + 28))
        
        # Bottom status (skip the second card in row 5)
        txt = self.font_tiny.render("Raspberry Pi 4B", True, COLOR_DARK_GRAY)
        self.screen.blit(txt, txt.get_rect(center=(PI_WIDTH // 2, PI_HEIGHT - 10)))

    
    def _render_settings(self):
        """Settings screen with scrolling support"""
        TOP = 55
        BOTTOM_MARGIN = 40
        
        items = self._get_settings_items()
        item_h = 50
        visible_height = PI_HEIGHT - TOP - BOTTOM_MARGIN
        max_visible = visible_height // item_h
        
        # Calculate scroll offset to keep selected item visible
        scroll_offset = 0
        if self.settings_selection >= max_visible:
            scroll_offset = self.settings_selection - max_visible + 1
        
        # Render visible items
        for i, (name, value, unit) in enumerate(items):
            display_index = i - scroll_offset
            y = TOP + display_index * item_h
            
            # Skip items outside visible area
            if y < TOP - item_h or y > PI_HEIGHT - BOTTOM_MARGIN:
                continue
            
            is_selected = i == self.settings_selection
            
            bg_color = COLOR_BG_ELEVATED if is_selected else COLOR_BG_CARD
            pygame.draw.rect(self.screen, bg_color, (40, y, PI_WIDTH - 80, item_h - 5))
            
            if is_selected:
                pygame.draw.rect(self.screen, COLOR_ACCENT, (40, y, 5, item_h - 5))
                if self.settings_edit_mode:
                    pygame.draw.rect(self.screen, COLOR_ACCENT, (40, y, PI_WIDTH - 80, item_h - 5), 2)
            
            color = COLOR_WHITE if is_selected else COLOR_GRAY
            txt = self.font_small.render(name, True, color)
            self.screen.blit(txt, (60, y + 12))
            
            if value != "":
                val_color = COLOR_ACCENT if is_selected else COLOR_WHITE
                txt = self.font_small.render(f"{value}{unit}", True, val_color)
                self.screen.blit(txt, (PI_WIDTH - 60 - txt.get_width(), y + 12))
        
        # Scroll indicators
        if scroll_offset > 0:
            # Up arrow indicator
            pygame.draw.polygon(self.screen, COLOR_GRAY, [
                (PI_WIDTH // 2, TOP - 15),
                (PI_WIDTH // 2 - 10, TOP - 5),
                (PI_WIDTH // 2 + 10, TOP - 5)
            ])
        
        if scroll_offset + max_visible < len(items):
            # Down arrow indicator
            arrow_y = PI_HEIGHT - BOTTOM_MARGIN + 5
            pygame.draw.polygon(self.screen, COLOR_GRAY, [
                (PI_WIDTH // 2, arrow_y + 10),
                (PI_WIDTH // 2 - 10, arrow_y),
                (PI_WIDTH // 2 + 10, arrow_y)
            ])
        
        # Hint at bottom
        current_name = items[self.settings_selection][0] if self.settings_selection < len(items) else ""
        if current_name != "Back":
            hint = "<- VOL+/VOL- to adjust ->" if self.settings_edit_mode else "Press ON/OFF to edit"
            txt = self.font_tiny.render(hint, True, COLOR_DARK_GRAY)
            self.screen.blit(txt, txt.get_rect(center=(PI_WIDTH // 2, PI_HEIGHT - 15)))


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="MX5 Telemetry Pi Display")
    parser.add_argument("--fullscreen", "-f", action="store_true", help="Run in fullscreen mode")
    args = parser.parse_args()
    
    print("="*60)
    print("MX5 Telemetry - Raspberry Pi Display")
    print("="*60)
    print("Data source can be changed in Settings > Data Source")
    print("  CAN BUS = Real vehicle data (default)")
    print("  DEMO    = Simulated data for testing")
    print("="*60)
    
    app = PiDisplayApp(fullscreen=args.fullscreen)
    app.run()


if __name__ == "__main__":
    main()
