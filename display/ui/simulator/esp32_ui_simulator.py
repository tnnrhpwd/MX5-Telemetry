#!/usr/bin/env python3
"""
ESP32-S3 Round Display UI Simulator

Simulates the 1.85" round display (360x360) using Pygame.
Allows testing of UI screens and SWC button navigation.

Requirements:
    pip install pygame

Controls (keyboard mappings to SWC buttons):
    M / Tab      = MODE (switch screens)
    Enter        = ON/OFF (select)
    Escape / B   = CANCEL (back)
    Up / W       = RES+ (up/increase)
    Down / S     = SET- (down/decrease)
    Right / D    = SEEK_UP (next)
    Left / A     = SEEK_DOWN (prev)
    + / =        = VOL_UP (increase value)
    - / _        = VOL_DOWN (decrease value)
    Space        = MUTE (sleep toggle)
"""

import pygame
import math
import sys
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

# Display constants
DISPLAY_SIZE = 360
CENTER = DISPLAY_SIZE // 2
GAUGE_RADIUS = 150
GAUGE_THICKNESS = 20
CENTER_CIRCLE_R = 60

# Colors (RGB)
COLOR_BLACK = (0, 0, 0)
COLOR_WHITE = (255, 255, 255)
COLOR_RED = (255, 0, 0)
COLOR_GREEN = (0, 255, 0)
COLOR_BLUE = (0, 0, 255)
COLOR_YELLOW = (255, 255, 0)
COLOR_ORANGE = (255, 165, 0)
COLOR_CYAN = (0, 255, 255)
COLOR_DARK_GRAY = (64, 64, 64)
COLOR_LIGHT_GRAY = (192, 192, 192)
COLOR_MEDIUM_GRAY = (128, 128, 128)

# RPM colors
COLOR_RPM_IDLE = COLOR_BLUE
COLOR_RPM_ECO = COLOR_GREEN
COLOR_RPM_NORMAL = COLOR_YELLOW
COLOR_RPM_SPIRITED = COLOR_ORANGE
COLOR_RPM_HIGH = COLOR_RED


class ScreenID(Enum):
    RPM_GAUGE = 0
    SPEEDOMETER = 1
    TPMS = 2
    ENGINE_TEMPS = 3
    GFORCE = 4
    SETTINGS = 5


class ButtonEvent(Enum):
    NONE = auto()
    VOL_UP = auto()
    VOL_DOWN = auto()
    MODE = auto()
    SEEK_UP = auto()
    SEEK_DOWN = auto()
    MUTE = auto()
    ON_OFF = auto()
    CANCEL = auto()
    RES_PLUS = auto()
    SET_MINUS = auto()


class SettingID(Enum):
    BRIGHTNESS = 0
    SHIFT_RPM = 1
    REDLINE_RPM = 2
    UNITS = 3
    BACK = 4


SETTING_NAMES = ["Brightness", "Shift RPM", "Redline RPM", "Units", "< Back"]


@dataclass
class TelemetryData:
    rpm: int = 2500
    speed_kmh: int = 65
    gear: int = 3
    coolant_temp: int = 185
    oil_temp: int = 210
    ambient_temp: int = 72
    throttle_percent: int = 25
    brake_active: bool = False
    tire_pressure: List[float] = field(default_factory=lambda: [32.5, 31.8, 33.1, 32.9])
    tire_temp: List[float] = field(default_factory=lambda: [25.3, 24.1, 26.0, 25.8])
    tire_battery: List[int] = field(default_factory=lambda: [95, 92, 88, 90])
    g_lateral: float = 0.0
    g_longitudinal: float = 0.0


@dataclass 
class UISettings:
    brightness: int = 80
    shift_rpm: int = 6500
    redline_rpm: int = 7200
    use_mph: bool = True


class ESP32Simulator:
    def __init__(self):
        pygame.init()
        
        # Create window with extra space for controls panel
        self.window_width = DISPLAY_SIZE + 250  # Extra space for control panel
        self.window_height = DISPLAY_SIZE + 100  # Extra space for status
        self.screen = pygame.display.set_mode((self.window_width, self.window_height))
        pygame.display.set_caption("ESP32-S3 Round Display Simulator")
        
        # Create circular display surface
        self.display = pygame.Surface((DISPLAY_SIZE, DISPLAY_SIZE), pygame.SRCALPHA)
        
        # State
        self.current_screen = ScreenID.RPM_GAUGE
        self.previous_screen = ScreenID.RPM_GAUGE
        self.sleeping = False
        self.menu_selection = 0
        self.in_edit_mode = False
        
        # Data
        self.telemetry = TelemetryData()
        self.settings = UISettings()
        
        # Fonts
        self.font_large = pygame.font.Font(None, 72)
        self.font_medium = pygame.font.Font(None, 48)
        self.font_small = pygame.font.Font(None, 32)
        self.font_tiny = pygame.font.Font(None, 24)
        
        # Clock for frame limiting
        self.clock = pygame.time.Clock()
        
        # Button display state
        self.last_button = ButtonEvent.NONE
        self.button_display_time = 0
        
        # Demo mode for automatic value changes
        self.demo_mode = True
        self.demo_rpm_direction = 1
        self.demo_speed_direction = 1
        
    def run(self):
        """Main loop"""
        running = True
        while running:
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    button = self.key_to_button(event.key)
                    if button != ButtonEvent.NONE:
                        self.handle_button(button)
                        self.last_button = button
                        self.button_display_time = pygame.time.get_ticks()
                    
                    # Toggle demo mode with D key
                    if event.key == pygame.K_d:
                        self.demo_mode = not self.demo_mode
            
            # Demo mode - animate values
            if self.demo_mode and not self.sleeping:
                self.update_demo_values()
            
            # Clear window
            self.screen.fill((30, 30, 40))
            
            # Render display
            self.render()
            
            # Draw control panel
            self.draw_control_panel()
            
            # Draw status bar
            self.draw_status_bar()
            
            # Update display
            pygame.display.flip()
            
            # Cap at 30 FPS
            self.clock.tick(30)
        
        pygame.quit()
    
    def key_to_button(self, key) -> ButtonEvent:
        """Map keyboard keys to SWC buttons"""
        mapping = {
            pygame.K_m: ButtonEvent.MODE,
            pygame.K_TAB: ButtonEvent.MODE,
            pygame.K_RETURN: ButtonEvent.ON_OFF,
            pygame.K_KP_ENTER: ButtonEvent.ON_OFF,
            pygame.K_ESCAPE: ButtonEvent.CANCEL,
            pygame.K_b: ButtonEvent.CANCEL,
            pygame.K_UP: ButtonEvent.RES_PLUS,
            pygame.K_w: ButtonEvent.RES_PLUS,
            pygame.K_DOWN: ButtonEvent.SET_MINUS,
            pygame.K_s: ButtonEvent.SET_MINUS,
            pygame.K_RIGHT: ButtonEvent.SEEK_UP,
            pygame.K_d: ButtonEvent.SEEK_UP,
            pygame.K_LEFT: ButtonEvent.SEEK_DOWN,
            pygame.K_a: ButtonEvent.SEEK_DOWN,
            pygame.K_EQUALS: ButtonEvent.VOL_UP,
            pygame.K_PLUS: ButtonEvent.VOL_UP,
            pygame.K_KP_PLUS: ButtonEvent.VOL_UP,
            pygame.K_MINUS: ButtonEvent.VOL_DOWN,
            pygame.K_KP_MINUS: ButtonEvent.VOL_DOWN,
            pygame.K_SPACE: ButtonEvent.MUTE,
        }
        return mapping.get(key, ButtonEvent.NONE)
    
    def handle_button(self, button: ButtonEvent):
        """Handle button press"""
        # MUTE always toggles sleep
        if button == ButtonEvent.MUTE:
            self.sleeping = not self.sleeping
            return
        
        # Wake from sleep on any button
        if self.sleeping:
            self.sleeping = False
            return
        
        # Settings screen has special handling
        if self.current_screen == ScreenID.SETTINGS:
            self.handle_settings_button(button)
            return
        
        # Normal screen navigation
        if button == ButtonEvent.MODE or button == ButtonEvent.SEEK_UP:
            self.next_screen()
        elif button == ButtonEvent.SEEK_DOWN or button == ButtonEvent.CANCEL:
            self.prev_screen()
        elif button == ButtonEvent.SET_MINUS:
            # Quick jump to settings
            self.previous_screen = self.current_screen
            self.current_screen = ScreenID.SETTINGS
            self.menu_selection = 0
    
    def handle_settings_button(self, button: ButtonEvent):
        """Handle button press in settings menu"""
        if button == ButtonEvent.RES_PLUS:
            if self.in_edit_mode:
                self.adjust_value(1)
            else:
                self.menu_selection = (self.menu_selection - 1) % len(SETTING_NAMES)
        elif button == ButtonEvent.SET_MINUS:
            if self.in_edit_mode:
                self.adjust_value(-1)
            else:
                self.menu_selection = (self.menu_selection + 1) % len(SETTING_NAMES)
        elif button == ButtonEvent.VOL_UP:
            self.adjust_value(1)
        elif button == ButtonEvent.VOL_DOWN:
            self.adjust_value(-1)
        elif button == ButtonEvent.ON_OFF:
            if self.menu_selection == SettingID.BACK.value:
                self.menu_back()
            else:
                self.in_edit_mode = not self.in_edit_mode
        elif button == ButtonEvent.CANCEL:
            if self.in_edit_mode:
                self.in_edit_mode = False
            else:
                self.menu_back()
        elif button == ButtonEvent.MODE:
            self.menu_back()
            self.next_screen()
    
    def adjust_value(self, delta: int):
        """Adjust current setting value"""
        if self.menu_selection == SettingID.BRIGHTNESS.value:
            self.settings.brightness = max(10, min(100, self.settings.brightness + delta * 5))
        elif self.menu_selection == SettingID.SHIFT_RPM.value:
            self.settings.shift_rpm = max(4000, min(7500, self.settings.shift_rpm + delta * 100))
        elif self.menu_selection == SettingID.REDLINE_RPM.value:
            self.settings.redline_rpm = max(5000, min(8000, self.settings.redline_rpm + delta * 100))
        elif self.menu_selection == SettingID.UNITS.value:
            self.settings.use_mph = not self.settings.use_mph
    
    def next_screen(self):
        """Go to next screen"""
        screens = list(ScreenID)
        idx = screens.index(self.current_screen)
        self.current_screen = screens[(idx + 1) % len(screens)]
    
    def prev_screen(self):
        """Go to previous screen"""
        screens = list(ScreenID)
        idx = screens.index(self.current_screen)
        self.current_screen = screens[(idx - 1) % len(screens)]
    
    def menu_back(self):
        """Exit settings menu"""
        self.in_edit_mode = False
        self.current_screen = self.previous_screen
        self.menu_selection = 0
    
    def update_demo_values(self):
        """Update telemetry values for demo animation"""
        # Oscillate RPM
        self.telemetry.rpm += 50 * self.demo_rpm_direction
        if self.telemetry.rpm >= 6500:
            self.demo_rpm_direction = -1
        elif self.telemetry.rpm <= 800:
            self.demo_rpm_direction = 1
        
        # Update gear based on RPM
        if self.telemetry.rpm < 1500:
            self.telemetry.gear = 1
        elif self.telemetry.rpm < 2500:
            self.telemetry.gear = 2
        elif self.telemetry.rpm < 3500:
            self.telemetry.gear = 3
        elif self.telemetry.rpm < 4500:
            self.telemetry.gear = 4
        elif self.telemetry.rpm < 5500:
            self.telemetry.gear = 5
        else:
            self.telemetry.gear = 6
        
        # Speed roughly correlates with RPM/gear
        self.telemetry.speed_kmh = int(self.telemetry.rpm * self.telemetry.gear / 100)
        
        # Simulate G-forces
        import random
        self.telemetry.g_lateral += random.uniform(-0.1, 0.1)
        self.telemetry.g_lateral = max(-1.2, min(1.2, self.telemetry.g_lateral))
        self.telemetry.g_longitudinal += random.uniform(-0.05, 0.05)
        self.telemetry.g_longitudinal = max(-0.8, min(0.8, self.telemetry.g_longitudinal))
    
    def render(self):
        """Render the current screen"""
        # Clear display surface
        self.display.fill((0, 0, 0, 0))
        
        # Draw circular background
        pygame.draw.circle(self.display, COLOR_BLACK, (CENTER, CENTER), CENTER)
        pygame.draw.circle(self.display, COLOR_DARK_GRAY, (CENTER, CENTER), CENTER, 2)
        
        if self.sleeping:
            self.render_sleep()
        else:
            # Render current screen
            render_methods = {
                ScreenID.RPM_GAUGE: self.render_rpm_gauge,
                ScreenID.SPEEDOMETER: self.render_speedometer,
                ScreenID.TPMS: self.render_tpms,
                ScreenID.ENGINE_TEMPS: self.render_engine_temps,
                ScreenID.GFORCE: self.render_gforce,
                ScreenID.SETTINGS: self.render_settings,
            }
            render_methods[self.current_screen]()
        
        # Apply circular mask
        mask = pygame.Surface((DISPLAY_SIZE, DISPLAY_SIZE), pygame.SRCALPHA)
        pygame.draw.circle(mask, (255, 255, 255, 255), (CENTER, CENTER), CENTER)
        self.display.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        
        # Blit to main screen
        self.screen.blit(self.display, (10, 10))
    
    def render_sleep(self):
        """Render sleep screen"""
        text = self.font_small.render("SLEEP", True, COLOR_DARK_GRAY)
        rect = text.get_rect(center=(CENTER, CENTER))
        self.display.blit(text, rect)
    
    def render_rpm_gauge(self):
        """Render RPM gauge screen"""
        # Draw gauge arc background
        self.draw_arc(CENTER, CENTER, GAUGE_RADIUS, GAUGE_THICKNESS, 
                      135, 405, COLOR_DARK_GRAY)
        
        # Calculate and draw RPM arc
        rpm_angle = self.rpm_to_angle(self.telemetry.rpm)
        rpm_color = self.get_rpm_color(self.telemetry.rpm)
        self.draw_arc(CENTER, CENTER, GAUGE_RADIUS, GAUGE_THICKNESS,
                      135, 135 + rpm_angle, rpm_color)
        
        # Draw redline zone
        redline_start = self.rpm_to_angle(self.settings.shift_rpm) + 135
        self.draw_arc(CENTER, CENTER, GAUGE_RADIUS, GAUGE_THICKNESS,
                      redline_start, 405, COLOR_RED, alpha=100)
        
        # Draw center circle
        pygame.draw.circle(self.display, COLOR_DARK_GRAY, (CENTER, CENTER), CENTER_CIRCLE_R)
        pygame.draw.circle(self.display, rpm_color, (CENTER, CENTER), CENTER_CIRCLE_R, 2)
        
        # Draw RPM value
        rpm_text = self.font_large.render(str(self.telemetry.rpm), True, COLOR_WHITE)
        rpm_rect = rpm_text.get_rect(center=(CENTER, CENTER - 10))
        self.display.blit(rpm_text, rpm_rect)
        
        # Draw "RPM" label
        label = self.font_tiny.render("RPM", True, COLOR_LIGHT_GRAY)
        label_rect = label.get_rect(center=(CENTER, CENTER + 25))
        self.display.blit(label, label_rect)
        
        # Draw gear indicator
        gear_text = "N" if self.telemetry.gear == 0 else str(self.telemetry.gear)
        gear_surf = self.font_large.render(gear_text, True, rpm_color)
        gear_rect = gear_surf.get_rect(center=(CENTER, DISPLAY_SIZE - 50))
        self.display.blit(gear_surf, gear_rect)
        
        # Draw tick marks
        for rpm in range(0, 8000, 1000):
            angle = math.radians(135 + self.rpm_to_angle(rpm))
            x1 = CENTER + int(math.cos(angle) * (GAUGE_RADIUS - GAUGE_THICKNESS - 5))
            y1 = CENTER + int(math.sin(angle) * (GAUGE_RADIUS - GAUGE_THICKNESS - 5))
            x2 = CENTER + int(math.cos(angle) * (GAUGE_RADIUS - GAUGE_THICKNESS - 15))
            y2 = CENTER + int(math.sin(angle) * (GAUGE_RADIUS - GAUGE_THICKNESS - 15))
            pygame.draw.line(self.display, COLOR_LIGHT_GRAY, (x1, y1), (x2, y2), 2)
    
    def render_speedometer(self):
        """Render speedometer screen"""
        # Convert speed
        speed = self.telemetry.speed_kmh
        if self.settings.use_mph:
            speed = int(speed * 0.621371)
        
        # Draw speed value
        speed_text = self.font_large.render(str(speed), True, COLOR_WHITE)
        speed_rect = speed_text.get_rect(center=(CENTER, CENTER - 30))
        self.display.blit(speed_text, speed_rect)
        
        # Draw unit
        unit = "MPH" if self.settings.use_mph else "KMH"
        unit_text = self.font_small.render(unit, True, COLOR_LIGHT_GRAY)
        unit_rect = unit_text.get_rect(center=(CENTER, CENTER + 20))
        self.display.blit(unit_text, unit_rect)
        
        # Draw gear box
        gear_text = "N" if self.telemetry.gear == 0 else str(self.telemetry.gear)
        box_rect = pygame.Rect(CENTER - 35, DISPLAY_SIZE - 90, 70, 55)
        pygame.draw.rect(self.display, COLOR_WHITE, box_rect, 2, border_radius=8)
        
        gear_surf = self.font_medium.render(gear_text, True, COLOR_GREEN)
        gear_rect = gear_surf.get_rect(center=box_rect.center)
        self.display.blit(gear_surf, gear_rect)
        
        # Draw speed bar at top
        bar_width = int((self.telemetry.speed_kmh / 200) * 280)
        bar_width = min(280, bar_width)
        pygame.draw.rect(self.display, COLOR_DARK_GRAY, (40, 30, 280, 15), border_radius=5)
        pygame.draw.rect(self.display, COLOR_CYAN, (40, 30, bar_width, 15), border_radius=5)
    
    def render_tpms(self):
        """Render TPMS screen"""
        # Title
        title = self.font_small.render("TPMS", True, COLOR_WHITE)
        title_rect = title.get_rect(center=(CENTER, 35))
        self.display.blit(title, title_rect)
        
        # Tire positions
        positions = ["FL", "FR", "RL", "RR"]
        coords = [(100, 110), (260, 110), (100, 230), (260, 230)]
        
        for i, (pos, (x, y)) in enumerate(zip(positions, coords)):
            # Get color based on pressure
            pressure = self.telemetry.tire_pressure[i]
            if pressure < 25 or pressure > 40:
                color = COLOR_RED
            elif pressure < 28 or pressure > 36:
                color = COLOR_YELLOW
            else:
                color = COLOR_GREEN
            
            # Draw box
            box = pygame.Rect(x - 45, y - 40, 90, 80)
            pygame.draw.rect(self.display, color, box, 2, border_radius=5)
            
            # Position label
            pos_text = self.font_tiny.render(pos, True, COLOR_LIGHT_GRAY)
            pos_rect = pos_text.get_rect(center=(x, y - 25))
            self.display.blit(pos_text, pos_rect)
            
            # Pressure
            psi_text = self.font_small.render(f"{pressure:.1f}", True, color)
            psi_rect = psi_text.get_rect(center=(x, y + 5))
            self.display.blit(psi_text, psi_rect)
            
            # Temp
            temp_text = self.font_tiny.render(f"{self.telemetry.tire_temp[i]:.0f}°C", True, COLOR_LIGHT_GRAY)
            temp_rect = temp_text.get_rect(center=(x, y + 28))
            self.display.blit(temp_text, temp_rect)
        
        # Draw car outline in center
        car_rect = pygame.Rect(CENTER - 25, CENTER - 45, 50, 90)
        pygame.draw.rect(self.display, COLOR_LIGHT_GRAY, car_rect, 2, border_radius=8)
    
    def render_engine_temps(self):
        """Render engine temperatures screen"""
        # Title
        title = self.font_small.render("ENGINE", True, COLOR_WHITE)
        title_rect = title.get_rect(center=(CENTER, 35))
        self.display.blit(title, title_rect)
        
        # Temperature items
        temps = [
            ("COOLANT", self.telemetry.coolant_temp, 220, 100),
            ("OIL", self.telemetry.oil_temp, 250, 180),
            ("AMBIENT", self.telemetry.ambient_temp, 999, 260)
        ]
        
        for label, temp, warn_thresh, y in temps:
            color = COLOR_RED if temp > warn_thresh else COLOR_GREEN
            if label == "AMBIENT":
                color = COLOR_CYAN
            
            # Label
            label_text = self.font_tiny.render(label, True, COLOR_LIGHT_GRAY)
            label_rect = label_text.get_rect(center=(CENTER, y))
            self.display.blit(label_text, label_rect)
            
            # Value
            temp_text = self.font_medium.render(f"{temp}°F", True, color)
            temp_rect = temp_text.get_rect(center=(CENTER, y + 30))
            self.display.blit(temp_text, temp_rect)
    
    def render_gforce(self):
        """Render G-force meter screen"""
        # Title
        title = self.font_small.render("G-FORCE", True, COLOR_WHITE)
        title_rect = title.get_rect(center=(CENTER, 35))
        self.display.blit(title, title_rect)
        
        # Draw circles
        pygame.draw.circle(self.display, COLOR_DARK_GRAY, (CENTER, CENTER), 100, 1)
        pygame.draw.circle(self.display, COLOR_DARK_GRAY, (CENTER, CENTER), 50, 1)
        
        # Draw crosshairs
        pygame.draw.line(self.display, COLOR_DARK_GRAY, (CENTER - 110, CENTER), (CENTER + 110, CENTER), 1)
        pygame.draw.line(self.display, COLOR_DARK_GRAY, (CENTER, CENTER - 110), (CENTER, CENTER + 110), 1)
        
        # Draw labels
        labels = [("1G", CENTER + 105, CENTER), ("-1G", CENTER - 120, CENTER),
                  ("1G", CENTER, CENTER - 115), ("-1G", CENTER, CENTER + 105)]
        for text, x, y in labels:
            surf = self.font_tiny.render(text, True, COLOR_DARK_GRAY)
            rect = surf.get_rect(center=(x, y))
            self.display.blit(surf, rect)
        
        # Calculate G-force position (50 pixels = 1G)
        gx = CENTER + int(self.telemetry.g_lateral * 50)
        gy = CENTER - int(self.telemetry.g_longitudinal * 50)
        gx = max(80, min(280, gx))
        gy = max(80, min(280, gy))
        
        # Draw G-force dot with trail
        pygame.draw.circle(self.display, (100, 0, 0), (gx, gy), 15)
        pygame.draw.circle(self.display, COLOR_RED, (gx, gy), 10)
        
        # Draw values
        g_text = f"L:{self.telemetry.g_lateral:+.2f}  A:{self.telemetry.g_longitudinal:+.2f}"
        values = self.font_tiny.render(g_text, True, COLOR_WHITE)
        values_rect = values.get_rect(center=(CENTER, DISPLAY_SIZE - 40))
        self.display.blit(values, values_rect)
    
    def render_settings(self):
        """Render settings menu"""
        # Title
        title = self.font_small.render("SETTINGS", True, COLOR_WHITE)
        title_rect = title.get_rect(center=(CENTER, 35))
        self.display.blit(title, title_rect)
        
        # Menu items
        start_y = 80
        item_height = 50
        
        for i, name in enumerate(SETTING_NAMES):
            y = start_y + i * item_height
            selected = (i == self.menu_selection)
            editing = selected and self.in_edit_mode
            
            # Selection highlight
            if selected:
                pygame.draw.rect(self.display, COLOR_DARK_GRAY, 
                               (40, y - 5, 280, 40), border_radius=5)
            
            # Item name
            color = COLOR_YELLOW if editing else (COLOR_WHITE if selected else COLOR_LIGHT_GRAY)
            name_text = self.font_small.render(name, True, color)
            self.display.blit(name_text, (60, y))
            
            # Value
            if i < len(SETTING_NAMES) - 1:  # Not "Back"
                if i == SettingID.BRIGHTNESS.value:
                    value = f"{self.settings.brightness}%"
                elif i == SettingID.SHIFT_RPM.value:
                    value = str(self.settings.shift_rpm)
                elif i == SettingID.REDLINE_RPM.value:
                    value = str(self.settings.redline_rpm)
                elif i == SettingID.UNITS.value:
                    value = "MPH" if self.settings.use_mph else "KMH"
                else:
                    value = ""
                
                value_text = self.font_small.render(value, True, color)
                value_rect = value_text.get_rect(right=300, top=y)
                self.display.blit(value_text, value_rect)
            
            # Edit indicator
            if editing:
                indicator = self.font_small.render(">", True, COLOR_YELLOW)
                self.display.blit(indicator, (45, y))
        
        # Navigation hint
        hint = self.font_tiny.render("UP/DN:Nav  SEL:Edit  VOL:Adj", True, COLOR_LIGHT_GRAY)
        hint_rect = hint.get_rect(center=(CENTER, DISPLAY_SIZE - 30))
        self.display.blit(hint, hint_rect)
    
    def draw_arc(self, cx: int, cy: int, radius: int, thickness: int,
                 start_angle: float, end_angle: float, color: Tuple[int, int, int],
                 alpha: int = 255):
        """Draw an arc segment"""
        # Create a surface with alpha for the arc
        arc_surface = pygame.Surface((DISPLAY_SIZE, DISPLAY_SIZE), pygame.SRCALPHA)
        
        # Draw thick arc using multiple circles
        for r in range(radius - thickness//2, radius + thickness//2):
            # Draw arc by plotting points
            for angle in range(int(start_angle), int(end_angle) + 1, 2):
                rad = math.radians(angle)
                x = cx + int(r * math.cos(rad))
                y = cy + int(r * math.sin(rad))
                if 0 <= x < DISPLAY_SIZE and 0 <= y < DISPLAY_SIZE:
                    color_with_alpha = (*color, alpha)
                    pygame.draw.circle(arc_surface, color_with_alpha, (x, y), 2)
        
        self.display.blit(arc_surface, (0, 0))
    
    def get_rpm_color(self, rpm: int) -> Tuple[int, int, int]:
        """Get color for RPM value"""
        if rpm < 2000:
            return COLOR_RPM_IDLE
        elif rpm < 3000:
            return COLOR_RPM_ECO
        elif rpm < 4500:
            return COLOR_RPM_NORMAL
        elif rpm < 5500:
            return COLOR_RPM_SPIRITED
        else:
            return COLOR_RPM_HIGH
    
    def rpm_to_angle(self, rpm: int) -> float:
        """Convert RPM to arc angle (0-270 degrees)"""
        max_rpm = self.settings.redline_rpm
        angle = (rpm / max_rpm) * 270
        return min(270, max(0, angle))
    
    def draw_control_panel(self):
        """Draw the control panel on the right side"""
        panel_x = DISPLAY_SIZE + 30
        panel_y = 20
        
        # Panel title
        title = self.font_small.render("SWC Controls", True, COLOR_WHITE)
        self.screen.blit(title, (panel_x, panel_y))
        
        # Button mappings
        controls = [
            ("M / Tab", "MODE", ButtonEvent.MODE),
            ("Enter", "SELECT", ButtonEvent.ON_OFF),
            ("Esc / B", "CANCEL", ButtonEvent.CANCEL),
            ("↑ / W", "UP", ButtonEvent.RES_PLUS),
            ("↓ / S", "DOWN", ButtonEvent.SET_MINUS),
            ("→ / D", "NEXT", ButtonEvent.SEEK_UP),
            ("← / A", "PREV", ButtonEvent.SEEK_DOWN),
            ("+ / =", "VOL+", ButtonEvent.VOL_UP),
            ("- / _", "VOL-", ButtonEvent.VOL_DOWN),
            ("Space", "MUTE", ButtonEvent.MUTE),
        ]
        
        y = panel_y + 40
        for key, action, btn in controls:
            # Highlight recently pressed button
            is_recent = (btn == self.last_button and 
                        pygame.time.get_ticks() - self.button_display_time < 500)
            
            bg_color = COLOR_YELLOW if is_recent else COLOR_DARK_GRAY
            text_color = COLOR_BLACK if is_recent else COLOR_WHITE
            
            # Draw button background
            pygame.draw.rect(self.screen, bg_color, (panel_x, y, 90, 22), border_radius=3)
            
            # Key text
            key_text = self.font_tiny.render(key, True, text_color)
            self.screen.blit(key_text, (panel_x + 5, y + 3))
            
            # Action text
            action_text = self.font_tiny.render(action, True, COLOR_LIGHT_GRAY)
            self.screen.blit(action_text, (panel_x + 100, y + 3))
            
            y += 28
        
        # Demo mode indicator
        y += 20
        demo_text = f"Demo: {'ON' if self.demo_mode else 'OFF'} (D)"
        demo_color = COLOR_GREEN if self.demo_mode else COLOR_LIGHT_GRAY
        demo_surf = self.font_tiny.render(demo_text, True, demo_color)
        self.screen.blit(demo_surf, (panel_x, y))
    
    def draw_status_bar(self):
        """Draw status bar at bottom"""
        status_y = DISPLAY_SIZE + 30
        
        # Current screen
        screen_name = self.current_screen.name.replace("_", " ")
        screen_text = self.font_small.render(f"Screen: {screen_name}", True, COLOR_WHITE)
        self.screen.blit(screen_text, (20, status_y))
        
        # Sleep state
        if self.sleeping:
            sleep_text = self.font_small.render("SLEEPING", True, COLOR_YELLOW)
            self.screen.blit(sleep_text, (20, status_y + 30))
        
        # Telemetry values
        tel_text = f"RPM:{self.telemetry.rpm}  SPD:{self.telemetry.speed_kmh}km/h  Gear:{self.telemetry.gear}"
        tel_surf = self.font_tiny.render(tel_text, True, COLOR_LIGHT_GRAY)
        self.screen.blit(tel_surf, (20, status_y + 60))


if __name__ == "__main__":
    print("ESP32-S3 Round Display UI Simulator")
    print("=" * 40)
    print("Keyboard Controls:")
    print("  M/Tab     = MODE (switch screens)")
    print("  Enter     = SELECT")
    print("  Esc/B     = CANCEL/BACK")
    print("  ↑/W       = UP")
    print("  ↓/S       = DOWN")
    print("  →/D       = NEXT")  
    print("  ←/A       = PREV")
    print("  +/=       = VOL+")
    print("  -         = VOL-")
    print("  Space     = MUTE (sleep toggle)")
    print("  D         = Toggle demo mode")
    print("=" * 40)
    
    sim = ESP32Simulator()
    sim.run()
