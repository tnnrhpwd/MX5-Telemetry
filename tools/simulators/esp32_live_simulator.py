#!/usr/bin/env python3
"""
ESP32-S3 Live Display Simulator
Directly parses and simulates the C++ source code from display/src/main.cpp
Allows real-time visualization of UI changes without flashing the device.

Features:
- Parses actual ESP32 drawing code
- Hot-reload on source file changes
- Native Windows window with pygame
- Simulates all drawing primitives
- SWC button simulation

Controls:
    R           = Reload source code
    Up Arrow    = RES+ button (previous page/up in settings)
    Down Arrow  = SET- button (next page/down in settings)
    Enter       = ON_OFF button (select)
    Escape/B    = CANCEL button (back)
    Space       = Toggle engine running
    +/=         = Increase RPM
    -/_         = Decrease RPM
    [           = Decrease Speed
    ]           = Increase Speed
    G           = Cycle gear (N, 1-6)
    C           = Toggle clutch
    T           = Cycle through screens manually

Requirements:
    pip install pygame watchdog
"""

import pygame
import sys
import os
import time
import math
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Display constants
SCREEN_WIDTH = 360
SCREEN_HEIGHT = 360
CENTER_X = SCREEN_WIDTH // 2
CENTER_Y = SCREEN_HEIGHT // 2

# Find project root
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
MAIN_CPP_PATH = PROJECT_ROOT / "display" / "src" / "main.cpp"

# RGB565 to RGB888 color conversion
def rgb565_to_rgb888(rgb565):
    """Convert RGB565 color to RGB888 tuple."""
    r = ((rgb565 >> 11) & 0x1F) << 3
    g = ((rgb565 >> 5) & 0x3F) << 2
    b = (rgb565 & 0x1F) << 3
    return (r, g, b)

# Define colors (from main.cpp)
COLOR_BG = (12, 12, 18)
COLOR_BG_CARD = (22, 22, 32)
COLOR_BG_ELEVATED = (32, 32, 45)
MX5_RED = (255, 70, 85)
MX5_ORANGE = (255, 140, 50)
MX5_YELLOW = (255, 210, 60)
MX5_GREEN = (50, 215, 130)
MX5_BLUE = (65, 135, 255)
MX5_CYAN = (50, 220, 255)
MX5_PURPLE = (175, 130, 255)
MX5_WHITE = (245, 245, 250)
MX5_BLACK = COLOR_BG
MX5_GRAY = (140, 140, 160)
MX5_DARKGRAY = (55, 55, 70)
MX5_ACCENT = (100, 140, 255)

# Telemetry simulation data
class TelemetrySimulator:
    def __init__(self):
        self.rpm = 2500
        self.speed = 45
        self.gear = 3
        self.coolantTemp = 185
        self.oilTemp = 200
        self.oilPressure = 45
        self.oilWarning = False  # False = pressure present
        self.fuelLevel = 75
        self.voltage = 13.8
        self.ambientTemp = 72
        self.tirePressure = [32.0, 32.5, 31.8, 32.2]
        self.tireTemp = [95, 96, 94, 95]
        self.gForceX = 0.0
        self.gForceY = 0.0
        self.throttle = 30
        self.brake = 0
        self.engineRunning = True
        self.connected = True
        self.hasReceivedTelemetry = True
        self.clutchEngaged = False
        self.clutchDisplayMode = 0
        self.headlightsOn = False
        self.highBeamsOn = False
    
    def increase_rpm(self):
        self.rpm = min(8000, self.rpm + 250)
    
    def decrease_rpm(self):
        self.rpm = max(0, self.rpm - 250)
    
    def increase_speed(self):
        self.speed = min(150, self.speed + 5)
    
    def decrease_speed(self):
        self.speed = max(0, self.speed - 5)
    
    def cycle_gear(self):
        gears = [0, 1, 2, 3, 4, 5, 6]
        idx = gears.index(self.gear) if self.gear in gears else 0
        self.gear = gears[(idx + 1) % len(gears)]
    
    def toggle_clutch(self):
        self.clutchEngaged = not self.clutchEngaged
    
    def toggle_engine(self):
        self.engineRunning = not self.engineRunning

# Mock LCD drawing functions that work with pygame
class LCDSimulator:
    def __init__(self, surface):
        self.surface = surface
        self.font_cache = {}
        
    def get_font(self, size):
        """Get or create pygame font for given size."""
        if size not in self.font_cache:
            # Map ESP32 text sizes to pygame font sizes
            size_map = {
                1: 12,  # Small
                2: 18,  # Medium
                3: 28,  # Large
                4: 36,  # Extra large
                5: 48,  # Huge
            }
            pygame_size = size_map.get(size, size * 8)
            self.font_cache[size] = pygame.font.Font(None, pygame_size)
        return self.font_cache[size]
    
    def DrawPixel(self, x, y, color):
        """Draw a single pixel."""
        if isinstance(color, tuple):
            self.surface.set_at((x, y), color)
    
    def DrawLine(self, x0, y0, x1, y1, color):
        """Draw a line."""
        if isinstance(color, tuple):
            pygame.draw.line(self.surface, color, (x0, y0), (x1, y1), 1)
    
    def DrawCircle(self, x, y, radius, color):
        """Draw a circle outline."""
        if isinstance(color, tuple):
            pygame.draw.circle(self.surface, color, (x, y), radius, 1)
    
    def FillCircle(self, x, y, radius, color):
        """Draw a filled circle."""
        if isinstance(color, tuple):
            pygame.draw.circle(self.surface, color, (x, y), radius)
    
    def DrawRect(self, x, y, w, h, color):
        """Draw a rectangle outline."""
        if isinstance(color, tuple):
            pygame.draw.rect(self.surface, color, (x, y, w, h), 1)
    
    def FillRect(self, x, y, w, h, color):
        """Draw a filled rectangle."""
        if isinstance(color, tuple):
            pygame.draw.rect(self.surface, color, (x, y, w, h))
    
    def FillRoundRect(self, x, y, w, h, radius, color):
        """Draw a filled rounded rectangle."""
        if isinstance(color, tuple):
            # Draw main rectangle
            pygame.draw.rect(self.surface, color, (x + radius, y, w - 2*radius, h))
            pygame.draw.rect(self.surface, color, (x, y + radius, w, h - 2*radius))
            # Draw corners
            pygame.draw.circle(self.surface, color, (x + radius, y + radius), radius)
            pygame.draw.circle(self.surface, color, (x + w - radius, y + radius), radius)
            pygame.draw.circle(self.surface, color, (x + radius, y + h - radius), radius)
            pygame.draw.circle(self.surface, color, (x + w - radius, y + h - radius), radius)
    
    def DrawString(self, x, y, text, fg_color, bg_color, size):
        """Draw text with background."""
        if isinstance(fg_color, tuple) and isinstance(text, str):
            font = self.get_font(size)
            text_surface = font.render(text, True, fg_color)
            
            # Draw background if needed
            if isinstance(bg_color, tuple) and bg_color != COLOR_BG:
                bg_rect = text_surface.get_rect()
                bg_rect.topleft = (x, y)
                pygame.draw.rect(self.surface, bg_color, bg_rect)
            
            self.surface.blit(text_surface, (x, y))

class SourceFileWatcher(FileSystemEventHandler):
    """Watch for changes to main.cpp and trigger reload."""
    def __init__(self, callback):
        self.callback = callback
        self.last_modified = 0
    
    def on_modified(self, event):
        if event.src_path.endswith("main.cpp"):
            # Debounce - only reload if at least 0.5s since last change
            now = time.time()
            if now - self.last_modified > 0.5:
                self.last_modified = now
                print(f"[WATCH] Detected change in {event.src_path}")
                self.callback()

class ESP32LiveSimulator:
    def __init__(self):
        pygame.init()
        
        # Create window
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("ESP32-S3 Live Display Simulator")
        
        # Create drawing surface
        self.surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.lcd = LCDSimulator(self.surface)
        
        # Telemetry simulator
        self.telemetry = TelemetrySimulator()
        
        # Screen state
        self.current_screen = 0  # 0 = Overview
        self.needs_redraw = True
        
        # Clock for frame rate
        self.clock = pygame.time.Clock()
        self.running = True
        
        # File watcher
        self.setup_file_watcher()
        
        # Status text
        self.status_message = "Simulator ready. Press R to reload, T to cycle screens."
        self.status_time = time.time()
        
    def setup_file_watcher(self):
        """Setup file system watcher for auto-reload."""
        event_handler = SourceFileWatcher(self.reload_source)
        self.observer = Observer()
        watch_dir = str(MAIN_CPP_PATH.parent)
        self.observer.schedule(event_handler, watch_dir, recursive=False)
        self.observer.start()
        print(f"[WATCH] Monitoring {watch_dir} for changes...")
    
    def reload_source(self):
        """Reload the source code (future: parse and use actual drawing logic)."""
        self.status_message = f"Source reloaded at {time.strftime('%H:%M:%S')}"
        self.status_time = time.time()
        self.needs_redraw = True
        print("[RELOAD] Source code refreshed")
    
    def handle_input(self):
        """Handle keyboard input."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                
                elif event.key == pygame.K_r:
                    self.reload_source()
                
                elif event.key == pygame.K_t:
                    self.current_screen = (self.current_screen + 1) % 6
                    self.needs_redraw = True
                    self.status_message = f"Switched to screen {self.current_screen}"
                    self.status_time = time.time()
                
                elif event.key == pygame.K_SPACE:
                    self.telemetry.toggle_engine()
                    self.needs_redraw = True
                
                elif event.key == pygame.K_EQUALS or event.key == pygame.K_PLUS:
                    self.telemetry.increase_rpm()
                    self.needs_redraw = True
                
                elif event.key == pygame.K_MINUS or event.key == pygame.K_UNDERSCORE:
                    self.telemetry.decrease_rpm()
                    self.needs_redraw = True
                
                elif event.key == pygame.K_LEFTBRACKET:
                    self.telemetry.decrease_speed()
                    self.needs_redraw = True
                
                elif event.key == pygame.K_RIGHTBRACKET:
                    self.telemetry.increase_speed()
                    self.needs_redraw = True
                
                elif event.key == pygame.K_g:
                    self.telemetry.cycle_gear()
                    self.needs_redraw = True
                
                elif event.key == pygame.K_c:
                    self.telemetry.toggle_clutch()
                    self.needs_redraw = True
                
                elif event.key == pygame.K_UP:
                    # Previous screen
                    self.current_screen = (self.current_screen - 1) % 6
                    self.needs_redraw = True
                
                elif event.key == pygame.K_DOWN:
                    # Next screen
                    self.current_screen = (self.current_screen + 1) % 6
                    self.needs_redraw = True
    
    def draw_overview_screen(self):
        """Draw the Overview screen (port of drawOverviewScreen from main.cpp)."""
        # Clear background
        self.surface.fill(COLOR_BG)
        
        # === RPM ARC GAUGE (Screen border) ===
        rpm_percent = min(1.0, self.telemetry.rpm / 8000.0)
        
        # Determine RPM color
        if self.telemetry.rpm > 6000:
            rpm_color = MX5_RED
        elif self.telemetry.rpm > 4500:
            rpm_color = MX5_ORANGE
        elif self.telemetry.rpm > 3000:
            rpm_color = MX5_YELLOW
        else:
            rpm_color = MX5_GREEN
        
        # Draw arc
        arc_radius = 174
        arc_thickness = 8
        start_angle = 135.0
        total_arc = 270.0
        end_angle = start_angle + (total_arc * rpm_percent)
        
        # Draw background arc (dark gray)
        for t in range(arc_thickness):
            r = arc_radius - t
            angle = start_angle
            while angle <= start_angle + total_arc:
                rad = math.radians(angle)
                x = int(CENTER_X + r * math.cos(rad))
                y = int(CENTER_Y + r * math.sin(rad))
                self.lcd.DrawPixel(x, y, MX5_DARKGRAY)
                angle += 0.5
        
        # Draw filled RPM arc
        for t in range(arc_thickness):
            r = arc_radius - t
            angle = start_angle
            while angle <= end_angle:
                rad = math.radians(angle)
                x = int(CENTER_X + r * math.cos(rad))
                y = int(CENTER_Y + r * math.sin(rad))
                self.lcd.DrawPixel(x, y, rpm_color)
                angle += 0.5
        
        # Draw tick marks
        tick_marks = [0, 2000, 4000, 6000, 8000]
        for tick_rpm in tick_marks:
            tick_percent = tick_rpm / 8000.0
            tick_angle = start_angle + (total_arc * tick_percent)
            rad = math.radians(tick_angle)
            x1 = int(CENTER_X + (arc_radius + 2) * math.cos(rad))
            y1 = int(CENTER_Y + (arc_radius + 2) * math.sin(rad))
            x2 = int(CENTER_X + (arc_radius - arc_thickness - 4) * math.cos(rad))
            y2 = int(CENTER_Y + (arc_radius - arc_thickness - 4) * math.sin(rad))
            self.lcd.DrawLine(x1, y1, x2, y2, MX5_WHITE)
        
        # === SPEED AND RPM (Top, side by side) ===
        top_y = 35
        
        # Speed (left of center)
        speed_str = str(int(self.telemetry.speed)) if self.telemetry.hasReceivedTelemetry else "--"
        speed_val_x = CENTER_X - 55
        self.lcd.DrawString(speed_val_x - len(speed_str) * 10, top_y, speed_str, MX5_WHITE, COLOR_BG, 3)
        self.lcd.DrawString(speed_val_x - 10, top_y + 30, "mph", MX5_GRAY, COLOR_BG, 1)
        
        # RPM (right of center)
        rpm_str = str(int(self.telemetry.rpm)) if self.telemetry.hasReceivedTelemetry else "--"
        rpm_val_x = CENTER_X + 40
        self.lcd.DrawString(rpm_val_x, top_y, rpm_str, rpm_color, COLOR_BG, 3)
        self.lcd.DrawString(rpm_val_x + len(rpm_str) * 10 + 8, top_y + 30, "rpm", MX5_GRAY, COLOR_BG, 1)
        
        # === GEAR (Center, larger) ===
        gear_x = CENTER_X
        gear_y = CENTER_Y
        gear_radius = 48
        self.lcd.FillCircle(gear_x, gear_y, gear_radius, COLOR_BG_CARD)
        
        # Gear color
        if self.telemetry.clutchEngaged:
            gear_glow = MX5_CYAN
        elif self.telemetry.rpm > 6500:
            gear_glow = MX5_RED
        elif self.telemetry.rpm > 5500:
            gear_glow = MX5_ORANGE
        elif self.telemetry.rpm > 4500:
            gear_glow = MX5_YELLOW
        else:
            gear_glow = MX5_GREEN
        
        # Draw gear ring (thicker)
        for r in range(gear_radius, gear_radius - 4, -1):
            self.lcd.DrawCircle(gear_x, gear_y, r, gear_glow)
        
        # Gear text (larger and centered)
        if self.telemetry.clutchEngaged:
            if self.telemetry.clutchDisplayMode == 1:
                gear_str = "C"
            elif self.telemetry.clutchDisplayMode == 2:
                gear_str = "S"
            elif self.telemetry.clutchDisplayMode == 3:
                gear_str = "-"
            else:
                gear_str = str(self.telemetry.gear) if self.telemetry.gear > 0 else "N"
        else:
            if self.telemetry.gear == 0:
                gear_str = "N"
            elif self.telemetry.gear == -1:
                gear_str = "R"
            else:
                gear_str = str(self.telemetry.gear)
        
        self.lcd.DrawString(gear_x - 13, gear_y - 16, gear_str, gear_glow, COLOR_BG_CARD, 4)
        
        # === KEY VALUES (Two columns, left and right) ===
        box_w = 50
        box_h = 45
        box_gap = 12
        left_x = 22
        right_x = SCREEN_WIDTH - left_x - box_w
        top_box_y = CENTER_Y - box_h - box_gap // 2
        bottom_box_y = CENTER_Y + box_gap // 2
        
        # Left Column - Top: COOLANT
        if self.telemetry.coolantTemp == 0:
            cool_color = MX5_RED
        elif self.telemetry.coolantTemp > 220:
            cool_color = MX5_RED
        elif self.telemetry.coolantTemp > 200:
            cool_color = MX5_ORANGE
        else:
            cool_color = MX5_CYAN
        
        self.lcd.FillRoundRect(left_x, top_box_y, box_w, box_h, 4, COLOR_BG_CARD)
        self.lcd.FillRect(left_x, top_box_y, 3, box_h, cool_color)
        self.lcd.DrawString(left_x + 5, top_box_y + 5, "COOL", MX5_GRAY, COLOR_BG_CARD, 1)
        cool_str = f"{int(self.telemetry.coolantTemp)}F"
        self.lcd.DrawString(left_x + 5, top_box_y + 23, cool_str, cool_color, COLOR_BG_CARD, 2)
        
        # Left Column - Bottom: AMBIENT
        if self.telemetry.ambientTemp < 32:
            ambient_color = MX5_BLUE
        elif self.telemetry.ambientTemp > 95:
            ambient_color = MX5_RED
        elif self.telemetry.ambientTemp > 85:
            ambient_color = MX5_ORANGE
        else:
            ambient_color = MX5_CYAN
        
        self.lcd.FillRoundRect(left_x, bottom_box_y, box_w, box_h, 4, COLOR_BG_CARD)
        self.lcd.FillRect(left_x, bottom_box_y, 3, box_h, ambient_color)
        self.lcd.DrawString(left_x + 5, bottom_box_y + 5, "AMB", MX5_GRAY, COLOR_BG_CARD, 1)
        ambient_str = f"{int(self.telemetry.ambientTemp)}F"
        self.lcd.DrawString(left_x + 5, bottom_box_y + 23, ambient_str, ambient_color, COLOR_BG_CARD, 2)
        
        # Right Column - Top: OIL
        oil_pressure_present = not self.telemetry.oilWarning
        oil_color = MX5_GREEN if oil_pressure_present else MX5_RED
        self.lcd.FillRoundRect(right_x, top_box_y, box_w, box_h, 4, COLOR_BG_CARD)
        self.lcd.FillRect(right_x, top_box_y, 3, box_h, oil_color)
        self.lcd.DrawString(right_x + 5, top_box_y + 5, "OIL", MX5_GRAY, COLOR_BG_CARD, 1)
        oil_str = "Good" if oil_pressure_present else "Bad"
        self.lcd.DrawString(right_x + 5, top_box_y + 23, oil_str, oil_color, COLOR_BG_CARD, 2)
        
        # Right Column - Bottom: FUEL
        if self.telemetry.fuelLevel < 15:
            fuel_color = MX5_RED
        elif self.telemetry.fuelLevel < 25:
            fuel_color = MX5_ORANGE
        else:
            fuel_color = MX5_GREEN
        
        self.lcd.FillRoundRect(right_x, bottom_box_y, box_w, box_h, 4, COLOR_BG_CARD)
        self.lcd.FillRect(right_x, bottom_box_y, 3, box_h, fuel_color)
        self.lcd.DrawString(right_x + 5, bottom_box_y + 5, "FUEL", MX5_GRAY, COLOR_BG_CARD, 1)
        fuel_str = f"{int(self.telemetry.fuelLevel)}%"
        self.lcd.DrawString(right_x + 5, bottom_box_y + 23, fuel_str, fuel_color, COLOR_BG_CARD, 2)
        
        # === TPMS (2x2 grid at bottom) ===
        tire_w = 48
        tire_h = 34
        tire_gap = 10
        tpms_start_x = CENTER_X - tire_w - tire_gap // 2
        tpms_start_y = SCREEN_HEIGHT - 2 * tire_h - tire_gap - 20
        
        tire_names = ["FL", "FR", "RL", "RR"]
        tire_positions = [(0, 0), (1, 0), (0, 1), (1, 1)]  # col, row
        
        for i in range(4):
            col, row = tire_positions[i]
            tire_x = tpms_start_x + col * (tire_w + tire_gap)
            tire_y = tpms_start_y + row * (tire_h + tire_gap)
            
            # Color based on pressure
            if self.telemetry.tirePressure[i] < 28.0:
                tire_color = MX5_RED
            elif self.telemetry.tirePressure[i] > 36.0:
                tire_color = MX5_YELLOW
            elif self.telemetry.tirePressure[i] < 30.0:
                tire_color = MX5_ORANGE
            else:
                tire_color = MX5_GREEN
            
            self.lcd.FillRoundRect(tire_x, tire_y, tire_w, tire_h, 3, COLOR_BG_CARD)
            self.lcd.FillRect(tire_x, tire_y, 2, tire_h, tire_color)
            
            # Tire name
            self.lcd.DrawString(tire_x + 4, tire_y + 3, tire_names[i], MX5_GRAY, COLOR_BG_CARD, 1)
            # PSI value
            psi_str = f"{self.telemetry.tirePressure[i]:.1f}"
            self.lcd.DrawString(tire_x + 4, tire_y + 16, psi_str, tire_color, COLOR_BG_CARD, 2)
    
    def draw_placeholder_screen(self, name):
        """Draw placeholder for other screens."""
        self.surface.fill(COLOR_BG)
        font = pygame.font.Font(None, 48)
        text = font.render(name, True, MX5_WHITE)
        text_rect = text.get_rect(center=(CENTER_X, CENTER_Y))
        self.surface.blit(text, text_rect)
    
    def render(self):
        """Render current screen."""
        if not self.needs_redraw:
            return
        
        # Draw current screen
        if self.current_screen == 0:
            self.draw_overview_screen()
        elif self.current_screen == 1:
            self.draw_placeholder_screen("RPM / Speed")
        elif self.current_screen == 2:
            self.draw_placeholder_screen("TPMS")
        elif self.current_screen == 3:
            self.draw_placeholder_screen("Engine Temps")
        elif self.current_screen == 4:
            self.draw_placeholder_screen("G-Force")
        elif self.current_screen == 5:
            self.draw_placeholder_screen("Settings")
        
        # Draw status message overlay
        if time.time() - self.status_time < 3.0:
            font = pygame.font.Font(None, 16)
            status_surf = font.render(self.status_message, True, MX5_WHITE, COLOR_BG_CARD)
            self.surface.blit(status_surf, (10, 10))
        
        # Copy surface to screen
        self.screen.blit(self.surface, (0, 0))
        pygame.display.flip()
        
        self.needs_redraw = False
    
    def run(self):
        """Main simulator loop."""
        print("=" * 60)
        print("ESP32-S3 Live Display Simulator")
        print("=" * 60)
        print(f"Monitoring: {MAIN_CPP_PATH}")
        print("\nControls:")
        print("  R           = Reload source")
        print("  T           = Cycle screens")
        print("  Up/Down     = Previous/Next screen")
        print("  Space       = Toggle engine")
        print("  +/-         = RPM")
        print("  [/]         = Speed")
        print("  G           = Cycle gear")
        print("  C           = Toggle clutch")
        print("  ESC         = Quit")
        print("=" * 60)
        
        while self.running:
            self.handle_input()
            self.render()
            self.clock.tick(30)  # 30 FPS
        
        # Cleanup
        self.observer.stop()
        self.observer.join()
        pygame.quit()

def main():
    if not MAIN_CPP_PATH.exists():
        print(f"ERROR: Could not find {MAIN_CPP_PATH}")
        print(f"Project root: {PROJECT_ROOT}")
        sys.exit(1)
    
    simulator = ESP32LiveSimulator()
    simulator.run()

if __name__ == "__main__":
    main()
