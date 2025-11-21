"""
MX5-Telemetry LED Simulator
============================
Interactive simulator for testing LED strip logic before uploading to Arduino.

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
from tkinter import messagebox
import math
import colorsys

# ============================================================================
# Configuration (matching config.h from Arduino)
# ============================================================================
LED_COUNT = 30
RPM_IDLE = 800
RPM_MIN_DISPLAY = 1000
RPM_MAX_DISPLAY = 7000
RPM_SHIFT_LIGHT = 6500
RPM_REDLINE = 7200

# Gear ratios for realistic simulation (Mazda MX-5 NC 6-speed)
GEAR_RATIOS = {
    1: 3.760,
    2: 2.269,
    3: 1.645,
    4: 1.187,
    5: 1.000,
    6: 0.843
}

FINAL_DRIVE = 4.100
TIRE_CIRCUMFERENCE = 1.937  # meters (205/45R17)

# Physics simulation
RPM_ACCEL_RATE = 50  # RPM per frame when accelerating
RPM_DECEL_RATE = 30  # RPM per frame when decelerating
RPM_IDLE_RETURN_RATE = 20  # RPM per frame returning to idle
SPEED_ACCEL_RATE = 0.5  # km/h per frame
SPEED_DECEL_RATE = 1.0  # km/h per frame

# ============================================================================
# LED Color Calculation (matching Arduino logic)
# ============================================================================
def get_rpm_color(rpm):
    """
    Calculate LED color based on RPM.
    Returns RGB tuple (0-255 for each channel).
    """
    if rpm < RPM_MIN_DISPLAY:
        return (0, 0, 0)  # Off
    
    if rpm >= RPM_SHIFT_LIGHT:
        # Red flash for shift light
        return (255, 0, 0)
    
    # Calculate position in gradient (0.0 to 1.0)
    position = (rpm - RPM_MIN_DISPLAY) / (RPM_MAX_DISPLAY - RPM_MIN_DISPLAY)
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

def get_active_led_count(rpm):
    """Calculate how many LEDs should be lit based on RPM."""
    if rpm < RPM_MIN_DISPLAY:
        return 0
    
    if rpm >= RPM_MAX_DISPLAY:
        return LED_COUNT
    
    # Linear mapping
    count = int(((rpm - RPM_MIN_DISPLAY) / (RPM_MAX_DISPLAY - RPM_MIN_DISPLAY)) * LED_COUNT)
    return max(0, min(LED_COUNT, count))

# ============================================================================
# Physics Simulation
# ============================================================================
def calculate_rpm_from_speed(speed_kmh, gear):
    """Calculate RPM based on vehicle speed and gear."""
    if gear == 0 or speed_kmh == 0:
        return RPM_IDLE
    
    speed_ms = speed_kmh / 3.6  # Convert to m/s
    wheel_rpm = (speed_ms * 60) / TIRE_CIRCUMFERENCE
    engine_rpm = wheel_rpm * GEAR_RATIOS[gear] * FINAL_DRIVE
    
    return max(RPM_IDLE, min(RPM_REDLINE, int(engine_rpm)))

# ============================================================================
# Main Simulator Class
# ============================================================================
class LEDSimulator:
    def __init__(self, root):
        self.root = root
        self.root.title("MX5-Telemetry LED Simulator")
        self.root.geometry("1000x700")
        self.root.configure(bg='#1a1a1a')
        self.root.resizable(False, False)
        
        # Simulation state
        self.rpm = RPM_IDLE
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
        title = tk.Label(self.root, text="MX5-Telemetry LED Simulator", 
                        font=("Arial", 24, "bold"), fg="#00ff00", bg="#1a1a1a")
        title.pack(pady=10)
        
        # Controls help
        controls_frame = tk.Frame(self.root, bg="#2a2a2a", relief=tk.RIDGE, bd=2)
        controls_frame.pack(pady=10, padx=20, fill=tk.X)
        
        tk.Label(controls_frame, text="CONTROLS", font=("Arial", 14, "bold"), 
                fg="#ffff00", bg="#2a2a2a").pack(pady=5)
        
        controls_text = [
            "↑ Up Arrow: Gas Pedal (Increase RPM)",
            "↓ Down Arrow: Brake (Decrease RPM)",
            "→ Right Arrow: Shift Up",
            "← Left Arrow: Shift Down",
            "⇧ Shift: Clutch (Hold while shifting)",
            "ESC: Quit (with confirmation)"
        ]
        
        for control in controls_text:
            tk.Label(controls_frame, text=control, font=("Courier", 10), 
                    fg="#ffffff", bg="#2a2a2a").pack(anchor=tk.W, padx=20)
        
        tk.Label(controls_frame, text="", bg="#2a2a2a").pack(pady=2)
        
        # Gauges frame
        gauges_frame = tk.Frame(self.root, bg="#1a1a1a")
        gauges_frame.pack(pady=10)
        
        # RPM Gauge
        self.rpm_canvas = tk.Canvas(gauges_frame, width=300, height=300, 
                                   bg="#1a1a1a", highlightthickness=0)
        self.rpm_canvas.pack(side=tk.LEFT, padx=20)
        
        # Speed Gauge
        self.speed_canvas = tk.Canvas(gauges_frame, width=300, height=300, 
                                     bg="#1a1a1a", highlightthickness=0)
        self.speed_canvas.pack(side=tk.LEFT, padx=20)
        
        # Gear indicator
        self.gear_frame = tk.Frame(self.root, bg="#2a2a2a", relief=tk.RIDGE, bd=3)
        self.gear_frame.pack(pady=10)
        
        tk.Label(self.gear_frame, text="GEAR", font=("Arial", 12, "bold"), 
                fg="#888888", bg="#2a2a2a").pack(pady=5)
        
        self.gear_label = tk.Label(self.gear_frame, text="1", 
                                  font=("Arial", 72, "bold"), 
                                  fg="#00ff00", bg="#2a2a2a", width=3)
        self.gear_label.pack(pady=10, padx=40)
        
        # LED Strip visualization
        led_frame = tk.Frame(self.root, bg="#2a2a2a", relief=tk.RIDGE, bd=2)
        led_frame.pack(pady=10, padx=20, fill=tk.X)
        
        tk.Label(led_frame, text="LED STRIP (WS2812B Simulation)", 
                font=("Arial", 12, "bold"), fg="#00ffff", bg="#2a2a2a").pack(pady=5)
        
        self.led_canvas = tk.Canvas(led_frame, width=940, height=60, 
                                   bg="#000000", highlightthickness=0)
        self.led_canvas.pack(pady=10, padx=10)
        
        # Status bar
        self.status_label = tk.Label(self.root, text="Ready | Press UP to accelerate", 
                                    font=("Arial", 10), fg="#00ff00", bg="#1a1a1a")
        self.status_label.pack(pady=5)
    
    def draw_gauge(self, canvas, value, max_value, label, unit, color):
        """Draw a circular gauge."""
        canvas.delete("all")
        
        # Gauge parameters
        center_x, center_y = 150, 150
        radius = 120
        
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
                             fill="#888888", font=("Arial", 10))
        
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
        canvas.create_text(center_x, center_y + 60, text=label, 
                          fill="#ffffff", font=("Arial", 14, "bold"))
        
        # Value
        canvas.create_text(center_x, center_y + 85, 
                          text=f"{int(value)} {unit}", 
                          fill=color, font=("Arial", 16, "bold"))
    
    def draw_leds(self):
        """Draw the LED strip."""
        self.led_canvas.delete("all")
        
        active_count = get_active_led_count(self.rpm)
        led_width = 30
        led_height = 50
        spacing = 2
        
        for i in range(LED_COUNT):
            x = 10 + i * (led_width + spacing)
            
            if i < active_count:
                # Shift light flash effect
                if self.rpm >= RPM_SHIFT_LIGHT and self.shift_light_flash:
                    color = "#ff0000"
                else:
                    rgb = get_rpm_color(self.rpm)
                    color = f'#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}'
            else:
                color = "#1a1a1a"  # Off
            
            # Draw LED
            self.led_canvas.create_rectangle(x, 5, x + led_width, 5 + led_height,
                                            fill=color, outline="#333333", width=1)
            
            # LED number
            if i < active_count:
                text_color = "#ffffff" if sum(get_rpm_color(self.rpm)) < 400 else "#000000"
            else:
                text_color = "#444444"
            
            self.led_canvas.create_text(x + led_width/2, 30, 
                                       text=str(i+1), 
                                       fill=text_color, 
                                       font=("Arial", 8))
    
    def update_simulation(self):
        """Main simulation loop."""
        
        # Physics simulation
        if self.clutch:
            # Clutch engaged - RPM can change independently
            if self.throttle:
                self.rpm = min(RPM_REDLINE, self.rpm + RPM_ACCEL_RATE)
            else:
                # Return to idle
                if self.rpm > RPM_IDLE:
                    self.rpm = max(RPM_IDLE, self.rpm - RPM_IDLE_RETURN_RATE)
        else:
            # Normal driving - RPM linked to speed/gear
            target_rpm = calculate_rpm_from_speed(self.speed, self.gear)
            
            if self.throttle:
                # Accelerate
                self.rpm = min(RPM_REDLINE, self.rpm + RPM_ACCEL_RATE)
                self.speed = min(200, self.speed + SPEED_ACCEL_RATE)
            elif self.brake:
                # Brake
                self.speed = max(0, self.speed - SPEED_DECEL_RATE)
                target_rpm = calculate_rpm_from_speed(self.speed, self.gear)
                self.rpm = max(target_rpm, self.rpm - RPM_DECEL_RATE)
            else:
                # Coast - RPM follows gear ratio
                if abs(self.rpm - target_rpm) > 50:
                    if self.rpm > target_rpm:
                        self.rpm = max(target_rpm, self.rpm - RPM_IDLE_RETURN_RATE)
                    else:
                        self.rpm = min(target_rpm, self.rpm + RPM_IDLE_RETURN_RATE)
                else:
                    self.rpm = target_rpm
        
        # Shift light flash effect
        self.shift_light_flash = not self.shift_light_flash
        
        # Update UI
        self.draw_gauge(self.rpm_canvas, self.rpm, RPM_REDLINE, "RPM", "rpm", 
                       "#ff0000" if self.rpm >= RPM_SHIFT_LIGHT else "#00ff00")
        
        self.draw_gauge(self.speed_canvas, self.speed, 200, "SPEED", "km/h", "#00aaff")
        
        self.gear_label.config(text=str(self.gear))
        if self.clutch:
            self.gear_label.config(fg="#ffff00")  # Yellow when clutch engaged
        else:
            self.gear_label.config(fg="#00ff00")  # Green normally
        
        self.draw_leds()
        
        # Status update
        status_parts = []
        if self.throttle:
            status_parts.append("⚡ THROTTLE")
        if self.brake:
            status_parts.append("🔴 BRAKE")
        if self.clutch:
            status_parts.append("⚙️ CLUTCH")
        if self.rpm >= RPM_SHIFT_LIGHT:
            status_parts.append("🔺 SHIFT!")
        
        status = " | ".join(status_parts) if status_parts else "Ready"
        self.status_label.config(text=status)
        
        # Schedule next frame (60 FPS)
        self.root.after(16, self.update_simulation)
    
    def on_key_press(self, event):
        """Handle key press events."""
        if event.keysym == 'Up':
            self.throttle = True
        elif event.keysym == 'Down':
            self.brake = True
        elif event.keysym == 'Shift_L' or event.keysym == 'Shift_R':
            self.clutch = True
        elif event.keysym == 'Right':
            if self.gear < 6:
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
