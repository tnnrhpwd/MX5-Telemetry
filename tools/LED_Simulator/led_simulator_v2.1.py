"""
MX5-Telemetry LED Simulator v2.1 - Mirrored Progress Bar System
================================================================
Interactive simulator for testing LED strip logic before uploading to Arduino.

LED States (matching Arduino logic):
⚪ State 0: Idle/Neutral (Speed = 0) - White pepper inward
🟢 State 1: Gas Efficiency (2000-2500 RPM) - Steady green edges
🟠 State 2: Stall Danger (750-1999 RPM) - Orange pulse outward
🟡 State 3: Normal Driving (2501-4500 RPM) - Yellow mirrored bar inward
🔴 State 4: High RPM/Shift (4501-7199 RPM) - Red bars with flashing gap
🛑 State 5: Rev Limit (7200+ RPM) - Solid red strip
❌ Error State: CAN Error - Red pepper inward

Features:
- Load custom car configuration files
- Engine start/stop control
- Realistic physics simulation with stalling
- Engine sound synthesis (pitch varies with RPM)
- Interactive LED visualization (mirrored progress bar system)
- Realistic speed decay and drag

Controls:
- Arrow Up: Gas Pedal (increase RPM)
- Arrow Down: Brake (decrease RPM)
- Arrow Right: Shift Up
- Arrow Left: Shift Down
- Shift: Hold for Clutch (RPM can change independently of speed)
- ESC: Quit (with confirmation)

This simulates the WS2812B LED strip behavior with realistic RPM/gear physics.
The LED logic mirrors the Arduino implementation in LEDController.cpp.
"""

import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import json
import os
import math
import wave
import struct
import threading
try:
    import pyaudio
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    print("Note: pyaudio not available. Install with 'pip install pyaudio' for engine sounds.")

# ============================================================================
# LED Configuration - DEFAULT VALUES (can be overridden from Arduino)
# ============================================================================
# These defaults ensure the simulator works even if Arduino config can't be loaded
LED_COUNT = 30  # Fixed hardware constant

# State 0: Idle/Neutral (White Pepper Inward)
STATE_0_SPEED_THRESHOLD = 1
STATE_0_PEPPER_DELAY = 150  # Slowed from 80ms for better visibility
STATE_0_HOLD_TIME = 2000     # Increased from 300ms to hold full pattern longer
STATE_0_COLOR = (255, 255, 255)
STATE_0_BRIGHTNESS = 180

# State 1: Gas Efficiency Zone (Steady Green Edges)
STATE_1_RPM_MIN = 2000
STATE_1_RPM_MAX = 2500
STATE_1_LEDS_PER_SIDE = 2
STATE_1_COLOR = (0, 255, 0)
STATE_1_BRIGHTNESS = 180

# State 2: Stall Danger (Orange Pulse Outward)
STATE_2_RPM_MIN = 750
STATE_2_RPM_MAX = 1999
STATE_2_PULSE_PERIOD = 600
STATE_2_MIN_BRIGHTNESS = 20
STATE_2_MAX_BRIGHTNESS = 200
STATE_2_COLOR = (255, 80, 0)

# State 3: Normal Driving / Power Band (Yellow Mirrored Bar)
STATE_3_RPM_MIN = 2501
STATE_3_RPM_MAX = 4500
STATE_3_COLOR = (255, 255, 0)
STATE_3_BRIGHTNESS = 255

# State 4: High RPM / Shift Danger (Red with Flashing Gap)
STATE_4_RPM_MIN = 4501
STATE_4_RPM_MAX = 7199
STATE_4_FLASH_SPEED_MIN = 150
STATE_4_FLASH_SPEED_MAX = 40
STATE_4_BAR_COLOR = (255, 0, 0)
STATE_4_FLASH_1_COLOR = (255, 0, 0)
STATE_4_FLASH_2_COLOR = (255, 255, 255)
STATE_4_BRIGHTNESS = 255

# State 5: Rev Limit Cut (Solid Red)
STATE_5_RPM_MIN = 7200
STATE_5_COLOR = (255, 0, 0)
STATE_5_BRIGHTNESS = 255

# Error State: CAN Bus Read Error (Red Pepper Inward)
ERROR_PEPPER_DELAY = 80
ERROR_HOLD_TIME = 300
ERROR_COLOR = (255, 0, 0)
ERROR_BRIGHTNESS = 200

# Try to load constants from Arduino LEDStates.h
def load_arduino_config():
    """Attempt to load LED configuration from Arduino code."""
    global STATE_0_SPEED_THRESHOLD, STATE_0_PEPPER_DELAY, STATE_0_HOLD_TIME, STATE_0_COLOR, STATE_0_BRIGHTNESS
    global STATE_1_RPM_MIN, STATE_1_RPM_MAX, STATE_1_LEDS_PER_SIDE, STATE_1_COLOR, STATE_1_BRIGHTNESS
    global STATE_2_RPM_MIN, STATE_2_RPM_MAX, STATE_2_PULSE_PERIOD, STATE_2_MIN_BRIGHTNESS, STATE_2_MAX_BRIGHTNESS, STATE_2_COLOR
    global STATE_3_RPM_MIN, STATE_3_RPM_MAX, STATE_3_COLOR, STATE_3_BRIGHTNESS
    global STATE_4_RPM_MIN, STATE_4_RPM_MAX, STATE_4_FLASH_SPEED_MIN, STATE_4_FLASH_SPEED_MAX
    global STATE_4_BAR_COLOR, STATE_4_FLASH_1_COLOR, STATE_4_FLASH_2_COLOR, STATE_4_BRIGHTNESS
    global STATE_5_RPM_MIN, STATE_5_COLOR, STATE_5_BRIGHTNESS
    global ERROR_PEPPER_DELAY, ERROR_HOLD_TIME, ERROR_COLOR, ERROR_BRIGHTNESS
    
    try:
        from parse_arduino_led_config import load_led_config
        
        print("Loading LED configuration from Arduino LEDStates.h...")
        _led_config = load_led_config()
        
        # State 0: Idle/Neutral
        STATE_0_SPEED_THRESHOLD = _led_config['STATE_0_SPEED_THRESHOLD']
        STATE_0_PEPPER_DELAY = _led_config['STATE_0_PEPPER_DELAY']
        STATE_0_HOLD_TIME = _led_config['STATE_0_HOLD_TIME']
        STATE_0_COLOR = (_led_config['STATE_0_COLOR_R'], _led_config['STATE_0_COLOR_G'], _led_config['STATE_0_COLOR_B'])
        STATE_0_BRIGHTNESS = _led_config['STATE_0_BRIGHTNESS']
        
        # State 1: Gas Efficiency
        STATE_1_RPM_MIN = _led_config['STATE_1_RPM_MIN']
        STATE_1_RPM_MAX = _led_config['STATE_1_RPM_MAX']
        STATE_1_LEDS_PER_SIDE = _led_config['STATE_1_LEDS_PER_SIDE']
        STATE_1_COLOR = (_led_config['STATE_1_COLOR_R'], _led_config['STATE_1_COLOR_G'], _led_config['STATE_1_COLOR_B'])
        STATE_1_BRIGHTNESS = _led_config['STATE_1_BRIGHTNESS']
        
        # State 2: Stall Danger
        STATE_2_RPM_MIN = _led_config['STATE_2_RPM_MIN']
        STATE_2_RPM_MAX = _led_config['STATE_2_RPM_MAX']
        STATE_2_PULSE_PERIOD = _led_config['STATE_2_PULSE_PERIOD']
        STATE_2_MIN_BRIGHTNESS = _led_config['STATE_2_MIN_BRIGHTNESS']
        STATE_2_MAX_BRIGHTNESS = _led_config['STATE_2_MAX_BRIGHTNESS']
        STATE_2_COLOR = (_led_config['STATE_2_COLOR_R'], _led_config['STATE_2_COLOR_G'], _led_config['STATE_2_COLOR_B'])
        
        # State 3: Normal Driving
        STATE_3_RPM_MIN = _led_config['STATE_3_RPM_MIN']
        STATE_3_RPM_MAX = _led_config['STATE_3_RPM_MAX']
        STATE_3_COLOR = (_led_config['STATE_3_COLOR_R'], _led_config['STATE_3_COLOR_G'], _led_config['STATE_3_COLOR_B'])
        STATE_3_BRIGHTNESS = _led_config['STATE_3_BRIGHTNESS']
        
        # State 4: High RPM/Shift
        STATE_4_RPM_MIN = _led_config['STATE_4_RPM_MIN']
        STATE_4_RPM_MAX = _led_config['STATE_4_RPM_MAX']
        STATE_4_FLASH_SPEED_MIN = _led_config['STATE_4_FLASH_SPEED_MIN']
        STATE_4_FLASH_SPEED_MAX = _led_config['STATE_4_FLASH_SPEED_MAX']
        STATE_4_BAR_COLOR = (_led_config['STATE_4_BAR_R'], _led_config['STATE_4_BAR_G'], _led_config['STATE_4_BAR_B'])
        STATE_4_FLASH_1_COLOR = (_led_config['STATE_4_FLASH_1_R'], _led_config['STATE_4_FLASH_1_G'], _led_config['STATE_4_FLASH_1_B'])
        STATE_4_FLASH_2_COLOR = (_led_config['STATE_4_FLASH_2_R'], _led_config['STATE_4_FLASH_2_G'], _led_config['STATE_4_FLASH_2_B'])
        STATE_4_BRIGHTNESS = _led_config['STATE_4_BRIGHTNESS']
        
        # State 5: Rev Limit
        STATE_5_RPM_MIN = _led_config['STATE_5_RPM_MIN']
        STATE_5_COLOR = (_led_config['STATE_5_COLOR_R'], _led_config['STATE_5_COLOR_G'], _led_config['STATE_5_COLOR_B'])
        STATE_5_BRIGHTNESS = _led_config['STATE_5_BRIGHTNESS']
        
        # Error State
        ERROR_PEPPER_DELAY = _led_config['ERROR_PEPPER_DELAY']
        ERROR_HOLD_TIME = _led_config['ERROR_HOLD_TIME']
        ERROR_COLOR = (_led_config['ERROR_COLOR_R'], _led_config['ERROR_COLOR_G'], _led_config['ERROR_COLOR_B'])
        ERROR_BRIGHTNESS = _led_config['ERROR_BRIGHTNESS']
        
        print(f"✓ Loaded {len(_led_config)} constants from Arduino")
        print(f"✓ State 0 Speed: <={STATE_0_SPEED_THRESHOLD} km/h")
        print(f"✓ State 1 RPM: {STATE_1_RPM_MIN}-{STATE_1_RPM_MAX}")
        print(f"✓ State 2 RPM: {STATE_2_RPM_MIN}-{STATE_2_RPM_MAX}")
        print(f"✓ State 3 RPM: {STATE_3_RPM_MIN}-{STATE_3_RPM_MAX}")
        print(f"✓ State 4 RPM: {STATE_4_RPM_MIN}-{STATE_4_RPM_MAX}")
        print(f"✓ State 5 RPM: {STATE_5_RPM_MIN}+")
        return True
        
    except Exception as e:
        print(f"⚠️  Warning: Could not load Arduino config: {e}")
        print("⚠️  Using default values (simulator will still work)")
        return False

# ============================================================================
# Audio Engine (Synthesized Engine Sound)
# ============================================================================
class AudioEngine:
    """Generates and plays synthesized engine sounds based on RPM."""
    
    def __init__(self):
        self.enabled = AUDIO_AVAILABLE
        self.playing = False
        self.rpm = 0
        self.target_rpm = 0
        self.volume = 0.20  # Default volume
        self.stream = None
        self.audio_thread = None
        self.pa = None
        
        if self.enabled:
            try:
                self.pa = pyaudio.PyAudio()
            except Exception as e:
                print(f"Audio initialization failed: {e}")
                self.enabled = False
    
    def start(self, idle_rpm):
        """Start engine audio."""
        if not self.enabled or self.playing:
            return
        
        self.playing = True
        self.rpm = idle_rpm
        self.target_rpm = idle_rpm
        
        # Start audio generation thread
        self.audio_thread = threading.Thread(target=self._audio_loop, daemon=True)
        self.audio_thread.start()
    
    def stop(self):
        """Stop engine audio."""
        self.playing = False
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except:
                pass
            self.stream = None
    
    def update_rpm(self, rpm):
        """Update target RPM for audio pitch."""
        self.target_rpm = rpm
    
    def set_volume(self, volume):
        """Set audio volume (0.0 to 1.0)."""
        self.volume = max(0.0, min(1.0, volume))
    
    def _audio_loop(self):
        """Audio generation loop (runs in separate thread)."""
        if not self.enabled:
            return
        
        sample_rate = 44100
        chunk_size = 1024
        
        try:
            self.stream = self.pa.open(
                format=pyaudio.paFloat32,
                channels=1,
                rate=sample_rate,
                output=True,
                frames_per_buffer=chunk_size
            )
            
            phase = 0
            explosion_phase = 0
            exhaust_phase = 0
            
            while self.playing:
                # Smooth RPM changes for audio
                if abs(self.rpm - self.target_rpm) > 10:
                    if self.rpm < self.target_rpm:
                        self.rpm = min(self.target_rpm, self.rpm + 30)
                    else:
                        self.rpm = max(self.target_rpm, self.rpm - 30)
                else:
                    self.rpm = self.target_rpm
                
                # Calculate frequencies based on RPM
                # 4-cylinder fires twice per revolution
                firing_freq = (self.rpm / 60.0) * 2.0  # Firing frequency in Hz
                base_freq = firing_freq  # Base frequency matches firing rate
                
                # RPM-dependent characteristics
                rpm_ratio = self.rpm / 7200.0  # 0.0 to 1.0
                
                # Generate audio chunk
                audio_data = []
                for i in range(chunk_size):
                    t = phase / sample_rate
                    
                    # 1. COMBUSTION EXPLOSIONS - sharp, percussive
                    # Use pulse train for individual cylinder firings
                    explosion_t = t * firing_freq
                    explosion_cycle = explosion_t - math.floor(explosion_t)
                    
                    # Sharp attack, quick decay (explosion characteristic)
                    # More pronounced at lower RPMs, crisper at high RPMs
                    explosion_strength = 0.48 * (1.0 - rpm_ratio * 0.25)
                    if explosion_cycle < 0.10:
                        # Sharper attack with more aggressive decay
                        explosion = (math.exp(-explosion_cycle * 30) * 
                                   (math.sin(2 * math.pi * base_freq * 3 * t) + 
                                    0.35 * math.sin(2 * math.pi * base_freq * 5 * t) +
                                    0.15 * math.sin(2 * math.pi * base_freq * 7 * t)))
                        explosion *= explosion_strength
                    else:
                        explosion = 0
                    
                    # 2. EXHAUST NOTE - raspy, with harmonics
                    # Dominant component, varies with RPM
                    exhaust_fundamental = 0.40 * math.sin(2 * math.pi * base_freq * t)
                    exhaust_2nd = 0.24 * math.sin(2 * math.pi * base_freq * 2 * t + 0.5)
                    exhaust_3rd = 0.16 * math.sin(2 * math.pi * base_freq * 3 * t + 1.2)
                    exhaust_4th = 0.10 * math.sin(2 * math.pi * base_freq * 4 * t + 0.8)
                    exhaust_5th = 0.06 * math.sin(2 * math.pi * base_freq * 5 * t + 0.3)
                    # Add phase modulation for more organic sound
                    phase_mod = 0.06 * math.sin(2 * math.pi * 2.3 * t)
                    exhaust_note = (exhaust_fundamental + exhaust_2nd + exhaust_3rd + exhaust_4th + exhaust_5th) * (1.0 + phase_mod)
                    
                    # 3. INTAKE SOUND - subtle whoosh at higher RPMs
                    intake_freq = base_freq * 0.7
                    # Increases with RPM, more pronounced at high revs
                    intake_amount = 0.10 * (rpm_ratio ** 1.5)
                    intake = intake_amount * (math.sin(2 * math.pi * intake_freq * t) + 
                                             0.3 * math.sin(2 * math.pi * intake_freq * 1.5 * t))
                    
                    # 4. MECHANICAL NOISE - valvetrain, pistons
                    # Higher frequency components, more present at high RPM
                    mechanical_amount = 0.06 + (0.03 * rpm_ratio)
                    mechanical = mechanical_amount * (math.sin(2 * math.pi * base_freq * 7 * t) + 
                                                     0.7 * math.sin(2 * math.pi * base_freq * 11 * t) +
                                                     0.4 * math.sin(2 * math.pi * base_freq * 13 * t))
                    
                    # 5. SUB-BASS RUMBLE - engine block vibrations
                    rumble_freq = base_freq * 0.5
                    # Stronger at lower RPMs, adds depth
                    rumble_amount = 0.18 * (1.0 - rpm_ratio * 0.4)
                    rumble = rumble_amount * (math.sin(2 * math.pi * rumble_freq * t) +
                                             0.3 * math.sin(2 * math.pi * rumble_freq * 0.75 * t))
                    
                    # 6. ENGINE ROUGHNESS - combustion irregularities
                    # More pronounced at lower RPMs (idle)
                    roughness_amount = 0.14 * (1.0 - rpm_ratio * 0.65)
                    roughness = (roughness_amount * 
                               (math.sin(2 * math.pi * base_freq * 13.7 * t) * math.sin(2 * math.pi * 3.3 * t) +
                                0.3 * math.sin(2 * math.pi * base_freq * 17.3 * t)))
                    
                    # 7. HIGH RPM RASP - screaming exhaust at high revs
                    if rpm_ratio > 0.55:
                        rasp_amount = ((rpm_ratio - 0.55) ** 1.3) * 0.6
                        rasp = rasp_amount * 0.20 * (math.sin(2 * math.pi * base_freq * 5 * t) + 
                                                     0.8 * math.sin(2 * math.pi * base_freq * 7 * t) +
                                                     0.5 * math.sin(2 * math.pi * base_freq * 9 * t) +
                                                     0.3 * math.sin(2 * math.pi * base_freq * 11 * t))
                    else:
                        rasp = 0
                    
                    # 8. BACKFIRE/BURBLE - occasional pops (especially mid-RPM)
                    burble = 0
                    if 0.35 < rpm_ratio < 0.82:
                        burble_chance = math.sin(2 * math.pi * 0.7 * t) * math.sin(2 * math.pi * 13.1 * t)
                        if burble_chance > 0.90:
                            burble = 0.10 * math.exp(-explosion_cycle * 35) * (1.0 + 0.3 * math.sin(2 * math.pi * base_freq * 2 * t))
                    
                    # Combine all engine sounds
                    sample = (explosion + exhaust_note + intake + mechanical + 
                             rumble + roughness + rasp + burble) * self.volume
                    
                    # Soft clipping for more natural saturation
                    sample = max(-1.0, min(1.0, sample))
                    if abs(sample) > 0.8:
                        sample = 0.8 * math.tanh(sample / 0.8)
                    
                    audio_data.append(sample)
                    phase += 1
                    explosion_phase += 1
                    exhaust_phase += 1
                
                # Convert to bytes and play
                audio_bytes = struct.pack('f' * len(audio_data), *audio_data)
                self.stream.write(audio_bytes)
        
        except Exception as e:
            print(f"Audio loop error: {e}")
            self.playing = False
    
    def _sawtooth(self, t):
        """Generate sawtooth wave (more engine-like than sine)."""
        return 2 * (t - math.floor(t + 0.5))
    
    def _square(self, t):
        """Generate square wave for harsher engine tone."""
        return 1.0 if (t - math.floor(t)) < 0.5 else -1.0
    
    def cleanup(self):
        """Clean up audio resources."""
        self.stop()
        if self.pa:
            try:
                self.pa.terminate()
            except:
                pass

# ============================================================================
# Car Configuration Class
# ============================================================================
class CarConfig:
    """Handles loading and storing car configuration from JSON files."""
    
    def __init__(self, filepath=None):
        """Load car configuration from JSON file."""
        if filepath:
            self.load_from_file(filepath)
        else:
            # Default configuration (2008 Miata NC)
            self.load_default()
    
    def load_from_file(self, filepath):
        """Load configuration from JSON file."""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            self._parse_config(data)
            self.filepath = filepath
            self.filename = os.path.basename(filepath)
        except Exception as e:
            messagebox.showerror("Error Loading Car File", 
                               f"Failed to load car configuration:\n{str(e)}")
            self.load_default()
    
    def load_default(self):
        """Load default 2008 Miata NC configuration."""
        self.name = "2008 Mazda MX-5 NC (Default)"
        self.year = 2008
        self.make = "Mazda"
        self.model = "MX-5 NC"
        
        # Engine
        self.redline_rpm = 7200
        self.idle_rpm = 800
        self.shift_light_rpm = 6500
        self.min_display_rpm = 1000
        self.max_display_rpm = 7000
        self.stall_rpm = 500  # Engine stalls below this
        
        # Transmission
        self.transmission_type = "manual"
        self.gears = 6
        self.gear_ratios = {1: 3.760, 2: 2.269, 3: 1.645, 4: 1.187, 5: 1.000, 6: 0.843}
        self.final_drive = 4.100
        self.clutch_engagement_rpm = 1200
        
        # Tires
        self.tire_circumference = 1.937
        
        # Performance
        self.top_speed_kmh = 215
        # Speed limits per gear (realistic for MX-5 NC)
        self.gear_speed_limits = {
            1: 50,   # 1st gear: 50 km/h
            2: 85,   # 2nd gear: 85 km/h
            3: 120,  # 3rd gear: 120 km/h
            4: 160,  # 4th gear: 160 km/h
            5: 200,  # 5th gear: 200 km/h
            6: 215   # 6th gear: top speed
        }
        
        # Physics
        self.rpm_accel_rate = 50
        self.rpm_decel_rate = 80  # Faster drop for realistic Miata NC (was 30)
        self.rpm_idle_return_rate = 70  # Much faster return to idle (was 20)
        self.speed_accel_rate = 0.5
        self.speed_decel_rate = 1.0
        self.drag_coefficient = 0.00005  # Very slow deceleration: 2 mph over 5 seconds
        self.rolling_resistance = 0.009  # Base rolling resistance (very slow coast)
        
        self.filepath = None
        self.filename = "Default Configuration"
    
    def _parse_config(self, data):
        """Parse JSON data into configuration attributes."""
        self.name = data.get('name', 'Unknown Car')
        self.year = data.get('year', 0)
        self.make = data.get('make', '')
        self.model = data.get('model', '')
        
        # Engine
        engine = data.get('engine', {})
        self.redline_rpm = engine.get('redline_rpm', 7200)
        self.idle_rpm = engine.get('idle_rpm', 800)
        self.shift_light_rpm = engine.get('shift_light_rpm', 6500)
        self.min_display_rpm = engine.get('min_display_rpm', 1000)
        self.max_display_rpm = engine.get('max_display_rpm', 7000)
        self.stall_rpm = engine.get('stall_rpm', 500)
        
        # Transmission
        trans = data.get('transmission', {})
        self.transmission_type = trans.get('type', 'manual')
        self.gears = trans.get('gears', 6)
        gear_ratios_raw = trans.get('gear_ratios', {})
        self.gear_ratios = {int(k): float(v) for k, v in gear_ratios_raw.items()}
        self.final_drive = trans.get('final_drive', 4.100)
        self.clutch_engagement_rpm = trans.get('clutch_engagement_rpm', 1200)
        
        # Tires
        tires = data.get('tires', {})
        self.tire_circumference = tires.get('circumference_meters', 1.937)
        
        # Performance
        perf = data.get('performance', {})
        self.top_speed_kmh = perf.get('top_speed_kmh', 200)
        
        # Gear speed limits
        gear_limits_raw = perf.get('gear_speed_limits', {})
        if gear_limits_raw:
            self.gear_speed_limits = {int(k): float(v) for k, v in gear_limits_raw.items()}
        else:
            # Default limits if not specified
            self.gear_speed_limits = {1: 50, 2: 85, 3: 120, 4: 160, 5: 200, 6: 215}
        
        # Physics
        physics = data.get('physics', {})
        self.rpm_accel_rate = physics.get('rpm_accel_rate', 50)
        self.rpm_decel_rate = physics.get('rpm_decel_rate', 30)
        self.rpm_idle_return_rate = physics.get('rpm_idle_return_rate', 20)
        self.speed_accel_rate = physics.get('speed_accel_rate', 0.5)
        self.speed_decel_rate = physics.get('speed_decel_rate', 1.0)
        self.drag_coefficient = physics.get('drag_coefficient', 0.00005)
        self.rolling_resistance = physics.get('rolling_resistance', 0.009)

# ============================================================================
# LED State Logic (matching Arduino mirrored progress bar system)
# ============================================================================
def is_state_0(speed_kmh):
    """Check if vehicle is in State 0 (Idle/Neutral - speed = 0)."""
    return speed_kmh <= STATE_0_SPEED_THRESHOLD

def is_state_1(rpm):
    """Check if RPM is in State 1 (Gas Efficiency Zone)."""
    return STATE_1_RPM_MIN <= rpm <= STATE_1_RPM_MAX

def is_state_2(rpm):
    """Check if RPM is in State 2 (Stall Danger)."""
    return STATE_2_RPM_MIN <= rpm <= STATE_2_RPM_MAX

def is_state_3(rpm):
    """Check if RPM is in State 3 (Normal Driving / Power Band)."""
    return STATE_3_RPM_MIN <= rpm <= STATE_3_RPM_MAX

def is_state_4(rpm):
    """Check if RPM is in State 4 (High RPM / Shift Danger)."""
    return STATE_4_RPM_MIN <= rpm <= STATE_4_RPM_MAX

def is_state_5(rpm):
    """Check if RPM is in State 5 (Rev Limit Cut)."""
    return rpm >= STATE_5_RPM_MIN

def get_pulse_brightness(current_time_ms, period, min_bright, max_bright):
    """Calculate pulsing brightness."""
    phase = (current_time_ms % period) / period
    angle = phase * 2.0 * math.pi
    sine_value = (math.sin(angle) + 1.0) / 2.0  # Normalize to 0.0 to 1.0
    brightness = min_bright + sine_value * (max_bright - min_bright)
    return int(brightness)

def scale_color(color, brightness):
    """Scale an RGB color by brightness (0-255)."""
    return tuple(int(c * brightness / 255) for c in color)

def draw_mirrored_bar(leds_per_side, color):
    """Draw mirrored bar from edges inward."""
    pattern = []
    for i in range(LED_COUNT):
        if i < LED_COUNT // 2:
            # Left side: lit from edge inward
            is_lit = (i < leds_per_side)
        else:
            # Right side: lit from edge inward
            is_lit = (i >= (LED_COUNT - leds_per_side))
        
        if is_lit:
            pattern.append(color)
        else:
            pattern.append((0, 0, 0))
    
    return pattern

def get_state_0_pattern(pepper_position):
    """
    State 0: Idle/Neutral - White pepper inward from edges.
    Returns list of RGB tuples for all LEDs.
    """
    pattern = []
    # Use maximum brightness for debugging - ensure LEDs are visible!
    bright_white = (255, 255, 255)  # Full brightness white
    
    for i in range(LED_COUNT):
        # Calculate distance from nearest edge (0 for edge LEDs, increases toward center)
        if i < LED_COUNT // 2:
            distance_from_edge = i  # Left side: 0, 1, 2, ...
        else:
            distance_from_edge = LED_COUNT - 1 - i  # Right side: ..., 2, 1, 0
        
        # Light up LEDs from edge inward up to pepper_position
        # Cap at half the strip (center point) - during hold time, keep all lit
        max_position = LED_COUNT // 2 - 1  # 14 for 30 LEDs (reaches center)
        
        if pepper_position <= max_position:
            # Animation in progress - light up based on distance
            if distance_from_edge <= pepper_position:
                pattern.append(bright_white)
            else:
                pattern.append((0, 0, 0))
        else:
            # Hold time - keep entire strip lit
            pattern.append(bright_white)
    
    return pattern

def get_state_1_pattern():
    """
    State 1: Gas Efficiency Zone - Steady green on outermost LEDs.
    Returns list of RGB tuples for all LEDs.
    """
    pattern = []
    for i in range(LED_COUNT):
        if i < STATE_1_LEDS_PER_SIDE or i >= (LED_COUNT - STATE_1_LEDS_PER_SIDE):
            pattern.append(STATE_1_COLOR)
        else:
            pattern.append((0, 0, 0))
    
    return pattern

def get_state_2_pattern(current_time_ms):
    """
    State 2: Stall Danger - Orange pulse outward.
    Returns list of RGB tuples for all LEDs.
    """
    brightness = get_pulse_brightness(current_time_ms, STATE_2_PULSE_PERIOD, 
                                      STATE_2_MIN_BRIGHTNESS, STATE_2_MAX_BRIGHTNESS)
    scaled_color = scale_color(STATE_2_COLOR, brightness)
    
    # All LEDs pulsing orange
    return [scaled_color] * LED_COUNT

def get_state_3_pattern(rpm):
    """
    State 3: Normal Driving - Yellow mirrored bar growing inward.
    Returns list of RGB tuples for all LEDs.
    """
    # Calculate position within State 3 range (0.0 to 1.0)
    position = (rpm - STATE_3_RPM_MIN) / (STATE_3_RPM_MAX - STATE_3_RPM_MIN)
    position = max(0.0, min(1.0, position))
    
    # Calculate how many LEDs per side should be lit
    leds_per_side = int(position * (LED_COUNT // 2))
    
    return draw_mirrored_bar(leds_per_side, STATE_3_COLOR)

def get_state_4_pattern(rpm, flash_state):
    """
    State 4: High RPM/Shift - Red bars with flashing gap in center.
    Returns list of RGB tuples for all LEDs.
    """
    # Calculate position within State 4 range (0.0 to 1.0)
    position = (rpm - STATE_4_RPM_MIN) / (STATE_4_RPM_MAX - STATE_4_RPM_MIN)
    position = max(0.0, min(1.0, position))
    
    # Calculate how many LEDs per side should be lit (red bars)
    leds_per_side = int(position * (LED_COUNT // 2))
    
    pattern = []
    for i in range(LED_COUNT):
        if i < LED_COUNT // 2:
            # Left side: red bar from edge inward
            is_in_bar = (i < leds_per_side)
        else:
            # Right side: red bar from edge inward
            is_in_bar = (i >= (LED_COUNT - leds_per_side))
        
        if is_in_bar:
            # Red bar
            pattern.append(STATE_4_BAR_COLOR)
        else:
            # Flashing gap in center
            if flash_state:
                pattern.append(STATE_4_FLASH_1_COLOR)
            else:
                pattern.append(STATE_4_FLASH_2_COLOR)
    
    return pattern

def get_state_5_pattern():
    """
    State 5: Rev Limit Cut - Solid red strip.
    Returns list of RGB tuples for all LEDs.
    """
    return [STATE_5_COLOR] * LED_COUNT

def get_error_pattern(pepper_position):
    """
    Error State: CAN Error - Red pepper inward from edges.
    Returns list of RGB tuples for all LEDs.
    """
    pattern = []
    for i in range(LED_COUNT):
        distance_from_edge = min(i, LED_COUNT - 1 - i)
        
        if distance_from_edge <= pepper_position and pepper_position < (LED_COUNT // 2):
            # Light up this LED with red
            pattern.append(ERROR_COLOR)
        else:
            pattern.append((0, 0, 0))
    
    return pattern

# ============================================================================
# Physics Simulation
# ============================================================================
def calculate_rpm_from_speed(speed_kmh, gear, config):
    """Calculate RPM based on vehicle speed and gear."""
    if gear == 0 or speed_kmh == 0:
        return config.idle_rpm
    
    speed_ms = speed_kmh / 3.6  # Convert to m/s
    wheel_rpm = (speed_ms * 60) / config.tire_circumference
    engine_rpm = wheel_rpm * config.gear_ratios[gear] * config.final_drive
    
    return max(config.idle_rpm, min(config.redline_rpm, int(engine_rpm)))

def calculate_max_speed_for_gear(gear, config):
    """Get maximum speed allowed in a given gear."""
    if gear == 0:
        return 0
    return config.gear_speed_limits.get(gear, config.top_speed_kmh)

def calculate_min_speed_for_gear(gear, config):
    """Calculate minimum speed to avoid stalling in a given gear."""
    # Neutral (gear 0) has no minimum speed
    if gear == 0:
        return 0
    
    # Minimum RPM to avoid stall is clutch engagement RPM
    min_rpm = config.clutch_engagement_rpm
    
    # Reverse calculation: RPM -> Speed
    wheel_rpm = min_rpm / (config.gear_ratios[gear] * config.final_drive)
    speed_ms = (wheel_rpm * config.tire_circumference) / 60
    speed_kmh = speed_ms * 3.6
    
    return speed_kmh

# ============================================================================
# Main Simulator Class
# ============================================================================
class LEDSimulator:
    def __init__(self, root):
        self.root = root
        self.root.title("MX5-Telemetry LED Simulator v2.1 - Three-State System")
        self.root.geometry("1000x820")
        self.root.configure(bg='#1a1a1a')
        self.root.resizable(False, False)
        
        # Load default car configuration
        default_car_path = os.path.join(os.path.dirname(__file__), 'cars', '2008_miata_nc.json')
        if os.path.exists(default_car_path):
            self.car_config = CarConfig(default_car_path)
        else:
            self.car_config = CarConfig()
        
        # Audio engine
        self.audio_engine = AudioEngine()
        
        # Simulation state
        self.engine_running = False
        self.engine_stalled = False
        self.check_engine_light = False  # CEL for starting in gear without brake
        self.rpm = 0
        self.speed = 0.0  # km/h
        self.gear = 0  # Start in neutral (0 = neutral)
        self.last_shutdown_gear = 0  # Track gear when engine was last stopped
        self.session_started = False  # Track if we've run the engine this session
        self.throttle = False
        self.brake = False
        self.clutch = False
        self.clutch_was_pressed = False  # Track previous clutch state
        self.previous_gear = 0  # Track previous gear for upshift detection
        self.clutch_slipping = False  # Currently experiencing clutch slip
        self.clutch_slip_counter = 0  # Frames of clutch slip remaining
        self.shift_light_flash = False
        self.stall_warning_counter = 0  # Counter for stall warning flashing
        self.use_mph = True  # Speed unit toggle (False = km/h, True = mph)
        self.stalling = False  # Currently in stall animation
        self.stall_animation_frames = 0  # Frames remaining in stall animation
        
        # LED animation state (for mirrored progress bar system)
        self.start_time_ms = 0  # Simulation start time in milliseconds
        self.current_time_ms = 0  # Current simulation time in milliseconds
        self.pepper_position = 3  # Position for inward pepper animations - start at 3 for visibility
        self.flash_state = False  # Flash state for State 4 gap flashing
        self.last_animation_update = 0  # Last time animation was updated
        
        # Create UI
        self.create_ui()
        
        # Bind keyboard
        self.root.bind('<KeyPress>', self.on_key_press)
        self.root.bind('<KeyRelease>', self.on_key_release)
        self.root.bind('<Escape>', self.on_escape)
        
        # Cleanup on close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Start simulation loop
        self.update_simulation()
    
    def create_ui(self):
        """Create the user interface."""
        
        # Title
        title = tk.Label(self.root, text="MX5-Telemetry LED Simulator v2.1 - Mirrored Progress Bar", 
                        font=("Arial", 18, "bold"), fg="#00ff00", bg="#1a1a1a")
        title.pack(pady=2)
        
        # State indicators (change color based on active state)
        state_frame = tk.Frame(self.root, bg="#1a1a1a")
        state_frame.pack(pady=2)
        
        self.state_labels = []
        state_names = ["Idle", "Efficiency", "Stall", "Normal", "Shift", "Limit"]
        for i, name in enumerate(state_names):
            if i > 0:
                tk.Label(state_frame, text=" | ", bg="#1a1a1a", fg="#444444",
                        font=("Arial", 10)).pack(side=tk.LEFT)
            label = tk.Label(state_frame, text=name, bg="#1a1a1a", fg="#666666",
                           font=("Arial", 10))
            label.pack(side=tk.LEFT)
            self.state_labels.append(label)
        
        # Car selection and engine control frame
        control_frame = tk.Frame(self.root, bg="#2a2a2a", relief=tk.RIDGE, bd=2)
        control_frame.pack(pady=5, padx=20, fill=tk.X)
        
        # Car info and selection
        car_info_frame = tk.Frame(control_frame, bg="#2a2a2a")
        car_info_frame.pack(side=tk.LEFT, padx=10, pady=5)
        
        tk.Label(car_info_frame, text="CAR:", font=("Arial", 10, "bold"), 
                fg="#ffff00", bg="#2a2a2a").pack(side=tk.LEFT, padx=5)
        
        self.car_name_label = tk.Label(car_info_frame, text=self.car_config.name, 
                                       font=("Arial", 10), fg="#ffffff", bg="#2a2a2a")
        self.car_name_label.pack(side=tk.LEFT, padx=5)
        
        self.load_car_btn = tk.Button(car_info_frame, text="Load Car File", 
                                      command=self.load_car_file,
                                      bg="#444444", fg="#ffffff", font=("Arial", 9))
        self.load_car_btn.pack(side=tk.LEFT, padx=5)
        
        # Engine start/stop
        engine_frame = tk.Frame(control_frame, bg="#2a2a2a")
        engine_frame.pack(side=tk.RIGHT, padx=10, pady=5)
        
        self.engine_btn = tk.Button(engine_frame, text="🔴 START ENGINE", 
                                    command=self.toggle_engine,
                                    bg="#cc0000", fg="#ffffff", 
                                    font=("Arial", 12, "bold"),
                                    width=18, height=1)
        self.engine_btn.pack(padx=5)
        
        # Audio status and volume control
        audio_frame = tk.Frame(control_frame, bg="#2a2a2a")
        audio_frame.pack(pady=5)
        
        audio_status = "🔊 Audio: " + ("Enabled" if AUDIO_AVAILABLE else "Disabled (install pyaudio)")
        tk.Label(audio_frame, text=audio_status, font=("Arial", 8), 
                fg="#888888" if AUDIO_AVAILABLE else "#ff6600", bg="#2a2a2a").pack()
        
        if AUDIO_AVAILABLE:
            volume_frame = tk.Frame(audio_frame, bg="#2a2a2a")
            volume_frame.pack(pady=3)
            
            tk.Label(volume_frame, text="Volume:", font=("Arial", 8), 
                    fg="#ffffff", bg="#2a2a2a").pack(side=tk.LEFT, padx=3)
            
            self.volume_slider = tk.Scale(volume_frame, from_=0, to=100, orient=tk.HORIZONTAL,
                                         command=self.on_volume_change, bg="#2a2a2a", fg="#ffffff",
                                         highlightthickness=0, length=150, width=10)
            self.volume_slider.set(20)  # Default 20%
            self.volume_slider.pack(side=tk.LEFT, padx=3)
        
        # Speed unit toggle
        unit_frame = tk.Frame(audio_frame, bg="#2a2a2a")
        unit_frame.pack(pady=3)
        
        tk.Label(unit_frame, text="Speed Unit:", font=("Arial", 8), 
                fg="#ffffff", bg="#2a2a2a").pack(side=tk.LEFT, padx=3)
        
        self.unit_toggle_btn = tk.Button(unit_frame, text="km/h", 
                                        command=self.toggle_speed_unit,
                                        bg="#00aa00", fg="#ffffff", 
                                        font=("Arial", 8, "bold"),
                                        width=8)
        self.unit_toggle_btn.pack(side=tk.LEFT, padx=3)
        
        # Controls help
        controls_frame = tk.Frame(self.root, bg="#2a2a2a", relief=tk.RIDGE, bd=2)
        controls_frame.pack(pady=5, padx=20, fill=tk.X)
        
        tk.Label(controls_frame, text="CONTROLS", font=("Arial", 12, "bold"), 
                fg="#ffff00", bg="#2a2a2a").pack(pady=3)
        
        controls_text = [
            "SPACE: Start/Stop Engine (hold SHIFT/clutch + DOWN/brake to start) | ↑ Up: Gas | ↓ Down: Brake",
            "→ Right: Shift Up | ← Left: Shift Down | ⇧ Shift: Clutch | ESC: Quit"
        ]
        
        for control in controls_text:
            tk.Label(controls_frame, text=control, font=("Courier", 9), 
                    fg="#ffffff", bg="#2a2a2a").pack(pady=2)
        
        # LED Strip visualization - Using grid layout for absolute control
        led_frame = tk.Frame(self.root, bg="#2a2a2a", relief=tk.RIDGE, bd=2)
        led_frame.pack(pady=5, padx=20, fill=tk.X, expand=False)
        
        tk.Label(led_frame, text="LED STRIP (WS2812B Simulation)", 
                font=("Arial", 11, "bold"), fg="#00ffff", bg="#2a2a2a").grid(row=0, column=0, pady=3, sticky='ew')
        
        # Create canvas with grid - ABSOLUTE positioning
        self.led_canvas = tk.Canvas(led_frame, bg="#ff0000", 
                                   highlightthickness=3, highlightbackground="#00ff00")
        self.led_canvas.config(width=980, height=60)
        self.led_canvas.grid(row=1, column=0, pady=5, padx=10)
        
        # Draw immediate test pattern
        self.led_canvas.create_rectangle(50, 10, 200, 50, fill="#ffff00", outline="#0000ff", width=3)
        self.led_canvas.create_text(125, 30, text="CANVAS TEST", fill="#000000", font=("Arial", 14, "bold"))
        
        # Force immediate update
        self.led_canvas.update_idletasks()
        
        # Gauges frame
        gauges_frame = tk.Frame(self.root, bg="#1a1a1a")
        gauges_frame.pack(pady=5)
        
        # RPM Gauge
        self.rpm_canvas = tk.Canvas(gauges_frame, width=280, height=280, 
                                   bg="#1a1a1a", highlightthickness=0)
        self.rpm_canvas.pack(side=tk.LEFT, padx=15)
        
        # Speed Gauge
        self.speed_canvas = tk.Canvas(gauges_frame, width=280, height=280, 
                                     bg="#1a1a1a", highlightthickness=0)
        self.speed_canvas.pack(side=tk.LEFT, padx=15)
        
        # Gear indicator
        self.gear_frame = tk.Frame(self.root, bg="#2a2a2a", relief=tk.RIDGE, bd=3)
        self.gear_frame.pack(pady=5)
        
        tk.Label(self.gear_frame, text="GEAR", font=("Arial", 10, "bold"), 
                fg="#888888", bg="#2a2a2a").pack(pady=3)
        
        self.gear_label = tk.Label(self.gear_frame, text="N" if not self.engine_running else "1", 
                                  font=("Arial", 60, "bold"), 
                                  fg="#666666", bg="#2a2a2a", width=3)
        self.gear_label.pack(pady=5, padx=30)
        
        # Warning and CEL indicators
        indicator_frame = tk.Frame(self.root, bg="#1a1a1a")
        indicator_frame.pack(pady=2)
        
        self.cel_label = tk.Label(indicator_frame, text="", 
                                 font=("Arial", 10, "bold"), 
                                 fg="#ff0000", bg="#1a1a1a")
        self.cel_label.pack()
        
        self.warning_label = tk.Label(indicator_frame, text="", 
                                     font=("Arial", 12, "bold"), 
                                     fg="#ff0000", bg="#1a1a1a")
        self.warning_label.pack()
        
        # Status bar
        self.status_label = tk.Label(self.root, text="Engine OFF | Press START ENGINE to begin", 
                                    font=("Arial", 10), fg="#ff6600", bg="#1a1a1a")
        self.status_label.pack(pady=5)
    
    def load_car_file(self):
        """Open file dialog to load a car configuration."""
        cars_dir = os.path.join(os.path.dirname(__file__), 'cars')
        initial_dir = cars_dir if os.path.exists(cars_dir) else os.path.dirname(__file__)
        
        filepath = filedialog.askopenfilename(
            title="Select Car Configuration File",
            initialdir=initial_dir,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filepath:
            old_engine_state = self.engine_running
            if self.engine_running:
                self.toggle_engine()  # Stop engine before switching
            
            self.car_config = CarConfig(filepath)
            self.car_name_label.config(text=self.car_config.name)
            self.rpm = 0
            self.speed = 0.0
            self.gear = 1
            self.engine_stalled = False
            
            messagebox.showinfo("Car Loaded", 
                              f"Successfully loaded:\n{self.car_config.name}")
    
    def toggle_engine(self):
        """Toggle engine on/off (requires brake if in gear)."""
        if self.engine_stalled:
            # Need to restart after stall
            self.engine_stalled = False
            self.warning_label.config(text="")
            self.check_engine_light = False
            self.cel_label.config(text="")
        
        if not self.engine_running:
            # Starting engine
            # Default to neutral UNLESS last shutdown was in neutral during this session
            if not self.session_started or self.last_shutdown_gear != 0:
                self.gear = 0  # Neutral (safe default)
            else:
                # Last shutdown was in neutral, stay in neutral
                self.gear = 0
            
            if self.gear != 0 and not self.clutch:
                # Trying to start in gear without clutch - STALL and throw CEL
                self.engine_stalled = True
                self.check_engine_light = True
                self.engine_btn.config(text="⚠️ ENGINE STALLED", bg="#cc6600")
                self.cel_label.config(text="⚠️ CHECK ENGINE - Started in gear without clutch!", fg="#ff0000")
                self.warning_label.config(text="Hold SHIFT (clutch) + DOWN (brake) and press SPACE to restart", fg="#ff6600")
                self.gear_label.config(text="N", fg="#ff0000")
                return
            
            if not self.clutch:
                # Must hold clutch to start (even in neutral)
                return
            
            if not self.brake:
                # Must hold brake to start (safety feature)
                return
            
            # Successful start - stay in neutral
            self.engine_running = True
            self.session_started = True
            self.rpm = self.car_config.idle_rpm
            # Keep gear as-is (neutral unless last shutdown was in gear)
            self.engine_btn.config(text="🟢 STOP ENGINE", bg="#00aa00")
            gear_text = "N" if self.gear == 0 else str(self.gear)
            self.gear_label.config(text=gear_text, fg="#00ff00")
            self.audio_engine.start(self.car_config.idle_rpm)
        else:
            # Stopping engine - remember what gear we're in
            self.last_shutdown_gear = self.gear
            self.engine_running = False
            self.rpm = 0
            self.speed = 0.0
            self.throttle = False
            self.brake = False
            self.engine_btn.config(text="🔴 START ENGINE", bg="#cc0000")
            self.gear_label.config(text="N", fg="#666666")
            self.audio_engine.stop()
    
    def on_volume_change(self, value):
        """Handle volume slider changes."""
        volume = float(value) / 100.0
        self.audio_engine.set_volume(volume)
    
    def toggle_speed_unit(self):
        """Toggle between km/h and mph."""
        self.use_mph = not self.use_mph
        if self.use_mph:
            self.unit_toggle_btn.config(text="mph", bg="#0066cc")
        else:
            self.unit_toggle_btn.config(text="km/h", bg="#00aa00")
    
    def check_for_stall(self):
        """Check if engine should stall due to low RPM without clutch."""
        if not self.engine_running or self.clutch or self.engine_stalled:
            return False
        
        # Can't stall in neutral
        if self.gear == 0:
            return False
        
        # Calculate minimum speed needed for current gear
        min_speed = calculate_min_speed_for_gear(self.gear, self.car_config)
        
        # If speed is too low for gear and RPM drops below stall threshold
        if self.speed < min_speed and self.rpm < self.car_config.stall_rpm:
            return True
        
        # Also stall if RPM drops too low
        if self.rpm < self.car_config.stall_rpm:
            return True
        
        return False
    
    def stall_engine(self):
        """Begin stall animation - smooth transition to stalled state."""
        if not self.stalling:
            self.stalling = True
            self.stall_animation_frames = 45  # ~0.75 seconds of stall animation
            self.check_engine_light = True
            self.cel_label.config(text="⚠️ CHECK ENGINE - Engine stalling!", fg="#ff6600")
    
    def complete_stall(self):
        """Complete the stall - engine fully stopped."""
        self.engine_stalled = True
        self.engine_running = False
        self.stalling = False
        self.rpm = 0
        self.speed = 0.0
        self.throttle = False
        self.brake = False
        self.last_shutdown_gear = self.gear
        self.engine_btn.config(text="⚠️ ENGINE STALLED", bg="#cc6600")
        self.gear_label.config(text="N", fg="#ff0000")
        self.cel_label.config(text="⚠️ CHECK ENGINE - Engine stalled!", fg="#ff0000")
        self.warning_label.config(text="⚠️ ENGINE STALLED - Hold SHIFT (clutch) + DOWN (brake) and press SPACE to restart", fg="#ff0000")
        self.audio_engine.stop()
    
    def draw_gauge(self, canvas, value, max_value, label, unit, color):
        """Draw a circular gauge."""
        canvas.delete("all")
        
        # Gauge parameters
        center_x, center_y = 140, 140
        radius = 110
        
        # Background circle
        canvas.create_oval(center_x - radius, center_y - radius,
                          center_x + radius, center_y + radius,
                          outline="#333333", width=3)
        
        # Determine tick increment based on gauge type
        is_rpm_gauge = (unit == "rpm")
        if is_rpm_gauge:
            # RPM gauge: use 1000 RPM increments (0, 1000, 2000, ... 7000)
            tick_count = 8  # 0 to 7000 in steps of 1000
            tick_increment = 1000
        else:
            # Speed gauge: keep 11 ticks
            tick_count = 11
            tick_increment = max_value / 10
        
        # Tick marks
        for i in range(tick_count):
            if is_rpm_gauge:
                value_ratio = i / (tick_count - 1)
            else:
                value_ratio = i / (tick_count - 1)
            
            angle = (value_ratio * 270 - 225)  # -225 to 45 degrees
            angle_rad = math.radians(angle)
            
            start_x = center_x + (radius - 15) * math.cos(angle_rad)
            start_y = center_y + (radius - 15) * math.sin(angle_rad)
            end_x = center_x + (radius - 5) * math.cos(angle_rad)
            end_y = center_y + (radius - 5) * math.sin(angle_rad)
            
            canvas.create_line(start_x, start_y, end_x, end_y, 
                             fill="#666666", width=2)
            
            # Labels
            if is_rpm_gauge:
                label_value = i * tick_increment  # 0, 1000, 2000, etc.
            else:
                label_value = int(value_ratio * max_value)
            
            label_x = center_x + (radius - 35) * math.cos(angle_rad)
            label_y = center_y + (radius - 35) * math.sin(angle_rad)
            canvas.create_text(label_x, label_y, text=str(label_value), 
                             fill="#888888", font=("Arial", 9))
        
        # Needle
        value_ratio = min(value / max_value, 1.0)
        needle_angle = (value_ratio * 270 - 225)
        needle_angle_rad = math.radians(needle_angle)
        
        needle_x = center_x + (radius - 20) * math.cos(needle_angle_rad)
        needle_y = center_y + (radius - 20) * math.sin(needle_angle_rad)
        
        canvas.create_line(center_x, center_y, needle_x, needle_y, 
                          fill=color, width=4, arrow=tk.LAST, arrowshape=(10, 12, 5))
        
        # Center circle
        canvas.create_oval(center_x - 10, center_y - 10,
                          center_x + 10, center_y + 10,
                          fill="#555555", outline=color, width=2)
        
        # Label
        canvas.create_text(center_x, center_y + 55, text=label, 
                          fill="#ffffff", font=("Arial", 13, "bold"))
        
        # Value
        canvas.create_text(center_x, center_y + 75, 
                          text=f"{int(value)} {unit}", 
                          fill=color, font=("Arial", 14, "bold"))
    
    def draw_leds(self):
        """Draw the LED strip using three-state system."""
        self.led_canvas.delete("all")
        
        if not self.engine_running:
            # All LEDs off when engine is off
            for i in range(LED_COUNT):
                x = 10 + i * 32
                self.led_canvas.create_rectangle(x, 5, x + 30, 55,
                                                fill="#0a0a0a", outline="#333333", width=1)
                self.led_canvas.create_text(x + 15, 30, text=str(i+1), 
                                           fill="#222222", font=("Arial", 8))
            return
        
        # Determine which state we're in and get the pattern
        # Priority order matches Arduino: State 0 > State 5 > State 4 > State 3 > State 1 > State 2
        # State 0: Idle/Neutral (speed = 0)
        if is_state_0(self.speed):
            led_pattern = get_state_0_pattern(self.pepper_position)
            active_state = "State 0 (Idle)"
        # State 5: Rev Limit Cut (7200+ RPM)
        elif is_state_5(self.rpm):
            led_pattern = get_state_5_pattern()
            active_state = "State 5 (Rev Limit)"
        # State 4: High RPM / Shift Danger (4501-7199 RPM)
        elif is_state_4(self.rpm):
            led_pattern = get_state_4_pattern(self.rpm, self.flash_state)
            active_state = "State 4 (Shift)"
        # State 3: Normal Driving / Power Band (2501-4500 RPM)
        elif is_state_3(self.rpm):
            led_pattern = get_state_3_pattern(self.rpm)
            active_state = "State 3 (Normal)"
        # State 1: Gas Efficiency Zone (2000-2500 RPM)
        elif is_state_1(self.rpm):
            led_pattern = get_state_1_pattern()
            active_state = "State 1 (Efficiency)"
        # State 2: Stall Danger (750-1999 RPM)
        elif is_state_2(self.rpm):
            led_pattern = get_state_2_pattern(self.current_time_ms)
            active_state = "State 2 (Stall)"
        else:
            # Below minimum RPM - all off
            led_pattern = [(0, 0, 0)] * LED_COUNT
            active_state = "Off"
        
        # Debug: Print first time we detect a state (only once per second to avoid spam)
        if hasattr(self, '_last_debug_time'):
            if self.current_time_ms - self._last_debug_time > 1000:
                lit_count = sum(1 for rgb in led_pattern if sum(rgb) > 0)
                print(f"[DEBUG] RPM:{self.rpm} Speed:{self.speed:.1f} State:{active_state} Pepper:{self.pepper_position} LEDs lit:{lit_count}/30")
                self._last_debug_time = self.current_time_ms
        else:
            self._last_debug_time = self.current_time_ms
        
        # Update state indicators at top
        state_colors = ["#666666"] * 6  # Default: all gray
        if active_state == "State 0 (Idle)":
            state_colors[0] = "#00ff00"  # Green for Idle
        elif active_state == "State 1 (Efficiency)":
            state_colors[1] = "#00ff00"  # Green for Efficiency
        elif active_state == "State 2 (Stall)":
            state_colors[2] = "#ff8800"  # Orange for Stall
        elif active_state == "State 3 (Normal)":
            state_colors[3] = "#ffff00"  # Yellow for Normal
        elif active_state == "State 4 (Shift)":
            state_colors[4] = "#ff0000"  # Red for Shift
        elif active_state == "State 5 (Rev Limit)":
            state_colors[5] = "#ff0000"  # Red for Rev Limit
        
        for i, label in enumerate(self.state_labels):
            label.config(fg=state_colors[i])
        
        # Draw all LEDs
        for i in range(LED_COUNT):
            x = 10 + i * 32
            rgb = led_pattern[i]
            
            # FORCE first LED to be BRIGHT MAGENTA for testing
            if i == 0:
                color = '#ff00ff'
            else:
                color = f'#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}'
            
            # Draw LED
            self.led_canvas.create_rectangle(x, 5, x + 30, 55,
                                            fill=color, outline="#00ff00", width=2)
            
            # LED number - adjust text color based on background
            if sum(rgb) > 400:
                text_color = "#000000"  # Dark text on bright background
            elif sum(rgb) > 0:
                text_color = "#ffffff"  # White text on dim background
            else:
                text_color = "#444444"  # Gray text on black
            
            self.led_canvas.create_text(x + 15, 30, text=str(i+1), 
                                       fill=text_color, font=("Arial", 8))
    
    def update_simulation(self):
        """Main simulation loop."""
        
        # Update simulation time (milliseconds) - using frame count * 16ms
        import time
        if self.start_time_ms == 0:
            self.start_time_ms = int(time.time() * 1000)
        self.current_time_ms = int(time.time() * 1000) - self.start_time_ms
        
        # Update animations based on state
        if self.engine_running and not self.engine_stalled:
            # State 0: Update pepper animation (white inward)
            if is_state_0(self.speed):
                if self.current_time_ms - self.last_animation_update >= STATE_0_PEPPER_DELAY:
                    self.last_animation_update = self.current_time_ms
                    self.pepper_position += 1
                    if self.pepper_position >= (LED_COUNT // 2) + (STATE_0_HOLD_TIME // STATE_0_PEPPER_DELAY):
                        self.pepper_position = 0
            
            # State 4: Update flash animation (flashing gap)
            elif is_state_4(self.rpm):
                # Calculate flash speed based on RPM
                rpm_ratio = (self.rpm - STATE_4_RPM_MIN) / (STATE_4_RPM_MAX - STATE_4_RPM_MIN)
                rpm_ratio = max(0.0, min(1.0, rpm_ratio))
                flash_speed = STATE_4_FLASH_SPEED_MIN - int(rpm_ratio * (STATE_4_FLASH_SPEED_MIN - STATE_4_FLASH_SPEED_MAX))
                
                if self.current_time_ms - self.last_animation_update >= flash_speed:
                    self.last_animation_update = self.current_time_ms
                    self.flash_state = not self.flash_state
        
        # Handle stall animation
        if self.stalling and self.stall_animation_frames > 0:
            self.stall_animation_frames -= 1
            
            # Gradually drop RPM with realistic curve
            rpm_drop_rate = 60 + (45 - self.stall_animation_frames) * 2  # Accelerating drop
            self.rpm = max(0, self.rpm - rpm_drop_rate)
            
            # Speed drops from engine drag and friction
            speed_drop_rate = 1.5 + (45 - self.stall_animation_frames) * 0.1
            self.speed = max(0, self.speed - speed_drop_rate)
            
            # Update audio to reflect dying engine
            self.audio_engine.update_rpm(self.rpm)
            
            # Flash warning during stall
            if self.stall_animation_frames % 10 < 5:
                self.warning_label.config(text="⚠️ ENGINE STALLING...", fg="#ff6600")
            else:
                self.warning_label.config(text="")
            
            # Complete stall when animation finishes
            if self.stall_animation_frames <= 0:
                self.complete_stall()
            
            # Skip normal simulation during stall animation
            self.shift_light_flash = not self.shift_light_flash
            self.draw_gauges_and_ui()
            self.root.after(16, self.update_simulation)
            return
        
        if self.engine_running and not self.engine_stalled:
            # Check for stall condition
            if self.check_for_stall():
                self.stall_engine()
                self.update_simulation()
                return
            
            # Physics simulation
            if self.clutch:
                # Clutch engaged - RPM can change independently
                if self.throttle:
                    self.rpm = min(self.car_config.redline_rpm, 
                                 self.rpm + self.car_config.rpm_accel_rate)
                else:
                    # Return to idle - faster drop with clutch in
                    if self.rpm > self.car_config.idle_rpm:
                        self.rpm = max(self.car_config.idle_rpm, 
                                     self.rpm - self.car_config.rpm_idle_return_rate)
                
                # Speed naturally decays when clutch is in
                if self.speed > 0:
                    natural_decay = self.car_config.rolling_resistance + (self.speed * self.car_config.drag_coefficient)
                    self.speed = max(0, self.speed - natural_decay)
                
                self.clutch_was_pressed = True
            else:
                # Check if clutch was just released (transition from pressed to released)
                if self.clutch_was_pressed and self.gear != 0:
                    # Calculate ideal RPM for current speed and gear
                    ideal_rpm = calculate_rpm_from_speed(self.speed, self.gear, self.car_config)
                    rpm_difference = abs(self.rpm - ideal_rpm)
                    
                    # If RPM mismatch is significant, simulate clutch slippage
                    if rpm_difference > 300:  # Threshold for noticeable slip
                        self.clutch_slipping = True
                        # Slip duration depends on RPM difference (more difference = longer slip)
                        self.clutch_slip_counter = int(rpm_difference / 50)  # Frames of slip
                        self.clutch_slip_counter = min(self.clutch_slip_counter, 60)  # Cap at 1 second
                
                self.clutch_was_pressed = False
                
                # Handle clutch slippage
                if self.clutch_slipping and self.clutch_slip_counter > 0:
                    # During slip, RPM gradually moves toward ideal RPM
                    ideal_rpm = calculate_rpm_from_speed(self.speed, self.gear, self.car_config)
                    
                    # Slip rate depends on remaining slip time - faster for realistic feel
                    slip_rate = 100 + (50 * (1.0 - self.clutch_slip_counter / 60.0))
                    
                    if self.rpm > ideal_rpm:
                        # Engine RPM drops during slip (absorbing flywheel energy)
                        self.rpm = max(ideal_rpm, self.rpm - slip_rate)
                        # Speed increases slightly from engine braking
                        if self.gear != 0:
                            self.speed = min(self.speed + 0.2, calculate_max_speed_for_gear(self.gear, self.car_config))
                    else:
                        # Engine RPM rises during slip (clutch transfers power)
                        self.rpm = min(ideal_rpm, self.rpm + slip_rate)
                        # Speed decreases slightly from clutch drag
                        self.speed = max(0, self.speed - 0.3)
                    
                    self.clutch_slip_counter -= 1
                    
                    if self.clutch_slip_counter <= 0:
                        self.clutch_slipping = False
                        # Snap to ideal RPM when slip completes
                        self.rpm = ideal_rpm
                else:
                    # Normal driving - RPM linked to speed/gear
                    self.clutch_slipping = False
                
                target_rpm = calculate_rpm_from_speed(self.speed, self.gear, self.car_config)
                
                if self.throttle:
                    # Accelerate
                    self.rpm = min(self.car_config.redline_rpm, 
                                 self.rpm + self.car_config.rpm_accel_rate)
                    
                    # Enforce gear speed limit
                    max_speed_in_gear = calculate_max_speed_for_gear(self.gear, self.car_config)
                    self.speed = min(max_speed_in_gear, 
                                   self.speed + self.car_config.speed_accel_rate)
                elif self.brake:
                    # Brake
                    self.speed = max(0, self.speed - self.car_config.speed_decel_rate)
                    target_rpm = calculate_rpm_from_speed(self.speed, self.gear, self.car_config)
                    self.rpm = max(target_rpm, self.rpm - self.car_config.rpm_decel_rate)
                else:
                    # Coast - natural deceleration from drag and rolling resistance
                    if self.speed > 0:
                        natural_decay = self.car_config.rolling_resistance + (self.speed * self.car_config.drag_coefficient)
                        self.speed = max(0, self.speed - natural_decay)
                    
                    # RPM follows gear ratio - faster tracking
                    target_rpm = calculate_rpm_from_speed(self.speed, self.gear, self.car_config)
                    if abs(self.rpm - target_rpm) > 50:
                        if self.rpm > target_rpm:
                            self.rpm = max(target_rpm, 
                                         self.rpm - self.car_config.rpm_idle_return_rate)
                        else:
                            # Faster rise when RPM needs to catch up
                            self.rpm = min(target_rpm, 
                                         self.rpm + self.car_config.rpm_idle_return_rate)
                    else:
                        self.rpm = target_rpm
            
            # Check if RPM gets too low for current conditions - stall the engine
            min_speed = calculate_min_speed_for_gear(self.gear, self.car_config)
            if not self.clutch and self.gear != 0 and self.speed < min_speed * 1.2 and self.rpm < self.car_config.clutch_engagement_rpm * 1.3:
                self.stall_warning_counter += 1
                # After 30 frames (~0.5 seconds) of too-low RPM, stall the engine
                if self.stall_warning_counter > 30:
                    self.stall_engine()
                    self.update_simulation()
                    return
            else:
                self.stall_warning_counter = 0
            
            # Update audio engine
            self.audio_engine.update_rpm(self.rpm)
            
            # Shift light flash effect
            self.shift_light_flash = not self.shift_light_flash
        
        # Draw gauges and UI
        self.draw_gauges_and_ui()
        
        # Schedule next frame (60 FPS)
        self.root.after(16, self.update_simulation)
    
    def draw_gauges_and_ui(self):
        """Draw all gauges and update UI elements."""
        # Update UI
        gauge_color = "#ff0000" if self.rpm >= self.car_config.shift_light_rpm else "#00ff00"
        if self.engine_stalled or self.stalling:
            gauge_color = "#ff6600"
        
        # RPM gauge with 1000 RPM increments (max 7000 for display)
        rpm_max = 7000  # Clean 7000 max for 1000 RPM increments
        self.draw_gauge(self.rpm_canvas, self.rpm, rpm_max, 
                       "RPM", "rpm", gauge_color if (self.engine_running or self.stalling) else "#333333")
        
        # Speed gauge with unit conversion
        if self.use_mph:
            speed_display = self.speed * 0.621371  # km/h to mph
            speed_max = self.car_config.top_speed_kmh * 0.621371
            speed_unit = "mph"
        else:
            speed_display = self.speed
            speed_max = self.car_config.top_speed_kmh
            speed_unit = "km/h"
        
        self.draw_gauge(self.speed_canvas, speed_display, speed_max, 
                       "SPEED", speed_unit, "#00aaff" if (self.engine_running or self.stalling) else "#333333")
        
        if self.engine_running and not self.engine_stalled:
            gear_text = "N" if self.gear == 0 else str(self.gear)
            self.gear_label.config(text=gear_text)
            if self.clutch:
                self.gear_label.config(fg="#ffff00")  # Yellow when clutch engaged
            else:
                self.gear_label.config(fg="#00ff00")  # Green normally
        elif self.engine_stalled:
            self.gear_label.config(text="N", fg="#ff0000")
        elif self.stalling:
            gear_text = "N" if self.gear == 0 else str(self.gear)
            self.gear_label.config(text=gear_text, fg="#ff6600")  # Orange during stall
        else:
            self.gear_label.config(text="N", fg="#666666")
        
        self.draw_leds()
        
        # Update CEL indicator
        if self.check_engine_light:
            self.cel_label.config(text="⚠️ CHECK ENGINE LIGHT", fg="#ff0000")
        else:
            self.cel_label.config(text="")
        
        # Status update
        if self.engine_stalled:
            status = "⚠️ ENGINE STALLED - Hold SHIFT (clutch) + DOWN (brake) and press SPACE to restart"
            self.status_label.config(text=status, fg="#ff6600")
        elif not self.engine_running and not self.stalling:
            status = "Engine OFF | Hold SHIFT (clutch) + DOWN (brake) and press SPACE to start"
            self.status_label.config(text=status, fg="#ff6600")
        else:
            status_parts = []
            if self.clutch_slipping:
                status_parts.append("⚠️ CLUTCH SLIPPING")
            if self.throttle:
                status_parts.append("⚡ THROTTLE")
            if self.brake:
                status_parts.append("🔴 BRAKE")
            if self.clutch:
                status_parts.append("⚙️ CLUTCH")
            if self.rpm >= self.car_config.shift_light_rpm:
                status_parts.append("🔺 SHIFT!")
            
            status = " | ".join(status_parts) if status_parts else "Engine Running"
            self.status_label.config(text=status, fg="#00ff00")
    
    def on_key_press(self, event):
        """Handle key press events."""
        # Handle spacebar for engine start/stop
        if event.keysym == 'space':
            self.toggle_engine()
            return
        
        # Brake can be pressed even when engine is off
        if event.keysym == 'Down':
            self.brake = True
        
        # Clutch can be pressed even when engine is off (needed for starting)
        if event.keysym == 'Shift_L' or event.keysym == 'Shift_R':
            self.clutch = True
        
        if not self.engine_running or self.engine_stalled:
            return
        
        if event.keysym == 'Up':
            self.throttle = True
        elif event.keysym == 'Right':
            # Shift up (neutral counts as gear 0)
            old_gear = self.gear
            if self.gear == 0:
                self.gear = 1  # Neutral to first
            elif self.gear < self.car_config.gears:
                self.gear += 1
            
            # Trigger clutch slip on upshift to simulate RPM drop
            if old_gear != self.gear and self.gear > 0 and old_gear > 0:
                ideal_rpm = calculate_rpm_from_speed(self.speed, self.gear, self.car_config)
                rpm_difference = abs(self.rpm - ideal_rpm)
                
                # Always trigger slip on upshift (even if RPM will drop)
                if rpm_difference > 100:  # Lower threshold for upshifts
                    self.clutch_slipping = True
                    # Shorter slip duration for upshifts (quicker)
                    self.clutch_slip_counter = max(15, int(rpm_difference / 80))  # Faster slip
                    self.clutch_slip_counter = min(self.clutch_slip_counter, 30)  # Cap at 0.5 seconds
        elif event.keysym == 'Left':
            # Shift down
            if self.gear > 0:
                self.gear -= 1  # Can go to neutral (0)
    
    def on_key_release(self, event):
        """Handle key release events."""
        if event.keysym == 'Up':
            self.throttle = False
        elif event.keysym == 'Down':
            self.brake = False
        elif event.keysym == 'Shift_L' or event.keysym == 'Shift_R':
            self.clutch = False
    
    def on_escape(self, event):
        """Handle ESC key - quit with confirmation."""
        result = messagebox.askyesno(
            "Quit Simulator",
            "Are you sure you want to exit the LED simulator?",
            icon='question'
        )
        if result:
            self.on_close()
    
    def on_close(self):
        """Clean up and close the simulator."""
        self.audio_engine.cleanup()
        self.root.destroy()

# ============================================================================
# Main Entry Point
# ============================================================================
def main():
    # Try to load Arduino configuration before starting GUI
    print("\n" + "="*70)
    print("MX5-Telemetry LED Simulator v2.1 - Starting...")
    print("="*70)
    load_arduino_config()
    print("="*70 + "\n")
    
    root = tk.Tk()
    root.geometry("1200x1100")  # Make window even taller so LED strip canvas is visible
    root.resizable(True, True)   # Allow resizing
    app = LEDSimulator(root)
    root.mainloop()

if __name__ == "__main__":
    main()
