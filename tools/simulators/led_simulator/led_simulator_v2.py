"""
MX5-Telemetry LED Simulator v2.0
=================================
Interactive simulator for testing LED strip logic before uploading to Arduino.

Features:
- Load custom car configuration files
- Engine start/stop control
- Realistic physics simulation
- Interactive LED visualization

Controls:
- Arrow Up: Gas Pedal (increase RPM)
- Arrow Down: Brake (decrease RPM)
- Arrow Right: Shift Up
- Arrow Left: Shift Down
- Shift: Hold for Clutch (RPM can change independently of speed)
- ESC: Quit (with confirmation)

This simulates the WS2812B LED strip behavior with realistic RPM/gear physics.
"""

import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import json
import os
import math

# ============================================================================
# LED Configuration (matching config.h from Arduino)
# ============================================================================
LED_COUNT = 20

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
        
        # Physics
        self.rpm_accel_rate = 50
        self.rpm_decel_rate = 30
        self.rpm_idle_return_rate = 20
        self.speed_accel_rate = 0.5
        self.speed_decel_rate = 1.0
        
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
        
        # Physics
        physics = data.get('physics', {})
        self.rpm_accel_rate = physics.get('rpm_accel_rate', 50)
        self.rpm_decel_rate = physics.get('rpm_decel_rate', 30)
        self.rpm_idle_return_rate = physics.get('rpm_idle_return_rate', 20)
        self.speed_accel_rate = physics.get('speed_accel_rate', 0.5)
        self.speed_decel_rate = physics.get('speed_decel_rate', 1.0)

# ============================================================================
# LED Color Calculation (matching Arduino logic)
# ============================================================================
def get_rpm_color(rpm, config):
    """
    Calculate LED color based on RPM.
    Returns RGB tuple (0-255 for each channel).
    """
    if rpm < config.min_display_rpm:
        return (0, 0, 0)  # Off
    
    if rpm >= config.shift_light_rpm:
        # Red flash for shift light
        return (255, 0, 0)
    
    # Calculate position in gradient (0.0 to 1.0)
    position = (rpm - config.min_display_rpm) / (config.max_display_rpm - config.min_display_rpm)
    position = max(0.0, min(1.0, position))
    
    # Color gradient: Green -> Yellow -> Orange -> Red
    if position < 0.33:
        # Green to Yellow
        t = position / 0.33
        r = int(t * 255)
        g = 255
        b = 0
    elif position < 0.66:
        # Yellow to Orange
        t = (position - 0.33) / 0.33
        r = 255
        g = int(255 - (t * 100))
        b = 0
    else:
        # Orange to Red
        t = (position - 0.66) / 0.34
        r = 255
        g = int(155 - (t * 155))
        b = 0
    
    return (r, g, b)

def get_active_led_count(rpm, config):
    """Calculate how many LEDs should be lit based on RPM."""
    if rpm < config.min_display_rpm:
        return 0
    
    if rpm >= config.max_display_rpm:
        return LED_COUNT
    
    # Linear mapping
    count = int(((rpm - config.min_display_rpm) / (config.max_display_rpm - config.min_display_rpm)) * LED_COUNT)
    return max(0, min(LED_COUNT, count))

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

# ============================================================================
# Main Simulator Class
# ============================================================================
class LEDSimulator:
    def __init__(self, root):
        self.root = root
        self.root.title("MX5-Telemetry LED Simulator v2.0")
        self.root.geometry("1000x780")
        self.root.configure(bg='#1a1a1a')
        self.root.resizable(False, False)
        
        # Load default car configuration
        default_car_path = os.path.join(os.path.dirname(__file__), 'cars', '2008_miata_nc.json')
        if os.path.exists(default_car_path):
            self.car_config = CarConfig(default_car_path)
        else:
            self.car_config = CarConfig()
        
        # Simulation state
        self.engine_running = False
        self.rpm = 0
        self.speed = 0.0  # km/h
        self.gear = 1
        self.throttle = False
        self.brake = False
        self.clutch = False
        self.shift_light_flash = False
        
        # Create UI
        self.create_ui()
        
        # Bind keyboard
        self.root.bind('<KeyPress>', self.on_key_press)
        self.root.bind('<KeyRelease>', self.on_key_release)
        self.root.bind('<Escape>', self.on_escape)
        
        # Start simulation loop
        self.update_simulation()
    
    def create_ui(self):
        """Create the user interface."""
        
        # Title
        title = tk.Label(self.root, text="MX5-Telemetry LED Simulator v2.0", 
                        font=("Arial", 20, "bold"), fg="#00ff00", bg="#1a1a1a")
        title.pack(pady=5)
        
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
        
        # Controls help
        controls_frame = tk.Frame(self.root, bg="#2a2a2a", relief=tk.RIDGE, bd=2)
        controls_frame.pack(pady=5, padx=20, fill=tk.X)
        
        tk.Label(controls_frame, text="CONTROLS", font=("Arial", 12, "bold"), 
                fg="#ffff00", bg="#2a2a2a").pack(pady=3)
        
        controls_text = [
            "↑ Up: Gas | ↓ Down: Brake | → Right: Shift Up | ← Left: Shift Down | ⇧ Shift: Clutch | ESC: Quit"
        ]
        
        for control in controls_text:
            tk.Label(controls_frame, text=control, font=("Courier", 9), 
                    fg="#ffffff", bg="#2a2a2a").pack(pady=2)
        
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
        
        # LED Strip visualization
        led_frame = tk.Frame(self.root, bg="#2a2a2a", relief=tk.RIDGE, bd=2)
        led_frame.pack(pady=5, padx=20, fill=tk.X)
        
        tk.Label(led_frame, text="LED STRIP (WS2812B Simulation)", 
                font=("Arial", 11, "bold"), fg="#00ffff", bg="#2a2a2a").pack(pady=3)
        
        self.led_canvas = tk.Canvas(led_frame, width=940, height=60, 
                                   bg="#000000", highlightthickness=0)
        self.led_canvas.pack(pady=8, padx=10)
        
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
            
            messagebox.showinfo("Car Loaded", 
                              f"Successfully loaded:\n{self.car_config.name}")
    
    def toggle_engine(self):
        """Toggle engine on/off."""
        self.engine_running = not self.engine_running
        
        if self.engine_running:
            self.rpm = self.car_config.idle_rpm
            self.gear = 1
            self.engine_btn.config(text="🟢 STOP ENGINE", bg="#00aa00")
            self.gear_label.config(text="1", fg="#00ff00")
        else:
            self.rpm = 0
            self.speed = 0.0
            self.throttle = False
            self.brake = False
            self.engine_btn.config(text="🔴 START ENGINE", bg="#cc0000")
            self.gear_label.config(text="N", fg="#666666")
    
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
        
        # Tick marks
        for i in range(0, 11):
            angle = (i / 10) * 270 - 225  # -225 to 45 degrees
            angle_rad = math.radians(angle)
            
            start_x = center_x + (radius - 15) * math.cos(angle_rad)
            start_y = center_y + (radius - 15) * math.sin(angle_rad)
            end_x = center_x + (radius - 5) * math.cos(angle_rad)
            end_y = center_y + (radius - 5) * math.sin(angle_rad)
            
            canvas.create_line(start_x, start_y, end_x, end_y, 
                             fill="#666666", width=2)
            
            # Labels
            label_value = int((i / 10) * max_value)
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
        """Draw the LED strip."""
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
        
        active_count = get_active_led_count(self.rpm, self.car_config)
        
        for i in range(LED_COUNT):
            x = 10 + i * 32
            
            if i < active_count:
                # Shift light flash effect
                if self.rpm >= self.car_config.shift_light_rpm and self.shift_light_flash:
                    color = "#ff0000"
                else:
                    rgb = get_rpm_color(self.rpm, self.car_config)
                    color = f'#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}'
            else:
                color = "#1a1a1a"  # Off
            
            # Draw LED
            self.led_canvas.create_rectangle(x, 5, x + 30, 55,
                                            fill=color, outline="#333333", width=1)
            
            # LED number
            if i < active_count:
                rgb = get_rpm_color(self.rpm, self.car_config)
                text_color = "#ffffff" if sum(rgb) < 400 else "#000000"
            else:
                text_color = "#444444"
            
            self.led_canvas.create_text(x + 15, 30, text=str(i+1), 
                                       fill=text_color, font=("Arial", 8))
    
    def update_simulation(self):
        """Main simulation loop."""
        
        if self.engine_running:
            # Physics simulation
            if self.clutch:
                # Clutch engaged - RPM can change independently
                if self.throttle:
                    self.rpm = min(self.car_config.redline_rpm, 
                                 self.rpm + self.car_config.rpm_accel_rate)
                else:
                    # Return to idle
                    if self.rpm > self.car_config.idle_rpm:
                        self.rpm = max(self.car_config.idle_rpm, 
                                     self.rpm - self.car_config.rpm_idle_return_rate)
            else:
                # Normal driving - RPM linked to speed/gear
                target_rpm = calculate_rpm_from_speed(self.speed, self.gear, self.car_config)
                
                if self.throttle:
                    # Accelerate
                    self.rpm = min(self.car_config.redline_rpm, 
                                 self.rpm + self.car_config.rpm_accel_rate)
                    self.speed = min(self.car_config.top_speed_kmh, 
                                   self.speed + self.car_config.speed_accel_rate)
                elif self.brake:
                    # Brake
                    self.speed = max(0, self.speed - self.car_config.speed_decel_rate)
                    target_rpm = calculate_rpm_from_speed(self.speed, self.gear, self.car_config)
                    self.rpm = max(target_rpm, self.rpm - self.car_config.rpm_decel_rate)
                else:
                    # Coast - RPM follows gear ratio
                    if abs(self.rpm - target_rpm) > 50:
                        if self.rpm > target_rpm:
                            self.rpm = max(target_rpm, 
                                         self.rpm - self.car_config.rpm_idle_return_rate)
                        else:
                            self.rpm = min(target_rpm, 
                                         self.rpm + self.car_config.rpm_idle_return_rate)
                    else:
                        self.rpm = target_rpm
            
            # Shift light flash effect
            self.shift_light_flash = not self.shift_light_flash
        
        # Update UI
        gauge_color = "#ff0000" if self.rpm >= self.car_config.shift_light_rpm else "#00ff00"
        self.draw_gauge(self.rpm_canvas, self.rpm, self.car_config.redline_rpm, 
                       "RPM", "rpm", gauge_color if self.engine_running else "#333333")
        
        self.draw_gauge(self.speed_canvas, self.speed, self.car_config.top_speed_kmh, 
                       "SPEED", "km/h", "#00aaff" if self.engine_running else "#333333")
        
        if self.engine_running:
            self.gear_label.config(text=str(self.gear))
            if self.clutch:
                self.gear_label.config(fg="#ffff00")  # Yellow when clutch engaged
            else:
                self.gear_label.config(fg="#00ff00")  # Green normally
        else:
            self.gear_label.config(text="N", fg="#666666")
        
        self.draw_leds()
        
        # Status update
        if not self.engine_running:
            status = "Engine OFF | Press START ENGINE to begin"
            self.status_label.config(text=status, fg="#ff6600")
        else:
            status_parts = []
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
        
        # Schedule next frame (60 FPS)
        self.root.after(16, self.update_simulation)
    
    def on_key_press(self, event):
        """Handle key press events."""
        if not self.engine_running:
            return
        
        if event.keysym == 'Up':
            self.throttle = True
        elif event.keysym == 'Down':
            self.brake = True
        elif event.keysym == 'Shift_L' or event.keysym == 'Shift_R':
            self.clutch = True
        elif event.keysym == 'Right':
            if self.gear < self.car_config.gears:
                self.gear += 1
        elif event.keysym == 'Left':
            if self.gear > 1:
                self.gear -= 1
    
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
            self.root.destroy()

# ============================================================================
# Main Entry Point
# ============================================================================
def main():
    root = tk.Tk()
    app = LEDSimulator(root)
    root.mainloop()

if __name__ == "__main__":
    main()
