#!/usr/bin/env python3
"""
Combined MX5 Telemetry UI Simulator

Shows both ESP32-S3 round display and Raspberry Pi display side by side.
BOTH displays show the SAME screen and are controlled SIMULTANEOUSLY.

The ESP32 shows a compact view, while the Pi shows extended info.

Hardware Notes:
    - ESP32-S3 with 1.85" GC9A01 round LCD (360x360)
    - Built-in QMI8658 IMU (6-axis accelerometer + gyroscope) for G-Force
    - No additional hardware needed for G-Force calculation

Screens (synchronized):
    1. RPM/Speed     - Primary driving data
    2. TPMS          - Tire pressure and temps
    3. Engine        - Coolant, oil temps, fuel
    4. G-Force       - Lateral and longitudinal G
    5. Settings      - Configuration options

SWC Buttons:
    RES+/SET-   = Navigate between screens
    VOL+/VOL-   = Adjust values (in settings)
    ON/OFF      = Select / Enter settings
    CANCEL      = Exit settings / Back

Keyboard Mappings:
    ↑ / W       = RES+ (Previous screen)
    ↓ / S       = SET- (Next screen)
    → / D       = VOL+ (Increase)
    ← / A       = VOL- (Decrease)
    Enter       = ON/OFF (Select)
    Esc / B     = CANCEL (Back)
    Space       = Toggle sleep mode
    Tab         = Toggle demo mode

Requirements:
    pip install pygame
"""

import pygame
import math
import random
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Tuple

# =============================================================================
# CONSTANTS
# =============================================================================

# Display sizes
ESP32_SIZE = 360  # Round display diameter
PI_WIDTH = 800
PI_HEIGHT = 480

# Window layout
WINDOW_PADDING = 20
CONTROL_PANEL_WIDTH = 200
WINDOW_WIDTH = ESP32_SIZE + PI_WIDTH + CONTROL_PANEL_WIDTH + WINDOW_PADDING * 4
WINDOW_HEIGHT = max(ESP32_SIZE, PI_HEIGHT) + 80

# Modern Color Palette
COLOR_BG = (12, 12, 18)           # Deep dark background
COLOR_BG_DARK = (8, 8, 12)        # Even darker
COLOR_BG_CARD = (22, 22, 32)      # Card/panel background
COLOR_BG_ELEVATED = (32, 32, 45)  # Elevated elements
COLOR_WHITE = (245, 245, 250)     # Soft white
COLOR_GRAY = (140, 140, 160)      # Muted gray
COLOR_DARK_GRAY = (55, 55, 70)    # Dark elements
COLOR_RED = (255, 70, 85)         # Modern red
COLOR_GREEN = (50, 215, 130)      # Modern green (mint)
COLOR_BLUE = (65, 135, 255)       # Bright blue
COLOR_YELLOW = (255, 210, 60)     # Warm yellow
COLOR_ORANGE = (255, 140, 50)     # Vibrant orange
COLOR_CYAN = (50, 220, 255)       # Bright cyan
COLOR_ACCENT = (100, 140, 255)    # Primary accent (blue-purple)
COLOR_PURPLE = (175, 130, 255)    # Soft purple
COLOR_PINK = (255, 100, 180)      # Accent pink
COLOR_TEAL = (45, 200, 190)       # Teal accent

# =============================================================================
# ENUMS AND DATA
# =============================================================================

class ButtonEvent(Enum):
    """SWC Button events"""
    NONE = auto()
    VOL_UP = auto()
    VOL_DOWN = auto()
    ON_OFF = auto()
    CANCEL = auto()
    RES_PLUS = auto()
    SET_MINUS = auto()


class Screen(Enum):
    """Unified screens for both displays"""
    OVERVIEW = 0
    RPM_SPEED = 1
    TPMS = 2
    ENGINE = 3
    GFORCE = 4
    SETTINGS = 5


SCREEN_NAMES = {
    Screen.OVERVIEW: "Overview",
    Screen.RPM_SPEED: "RPM / Speed",
    Screen.TPMS: "Tire Pressure",
    Screen.ENGINE: "Engine",
    Screen.GFORCE: "G-Force",
    Screen.SETTINGS: "Settings",
}


@dataclass
class TelemetryData:
    rpm: int = 2500
    speed_kmh: int = 65
    gear: int = 3
    throttle_percent: int = 25
    brake_percent: int = 0
    coolant_temp_f: int = 185
    oil_temp_f: int = 210
    oil_pressure_psi: float = 45.0
    intake_temp_f: int = 95
    ambient_temp_f: int = 72
    fuel_level_percent: float = 65.0
    voltage: float = 14.2
    tire_pressure: List[float] = field(default_factory=lambda: [32.5, 31.8, 33.1, 32.9])
    tire_temp: List[float] = field(default_factory=lambda: [95.3, 94.1, 96.0, 95.8])
    g_lateral: float = 0.0
    g_longitudinal: float = 0.0
    lap_time_ms: int = 0
    best_lap_ms: int = 95400  # 1:35.4


@dataclass
class Settings:
    brightness: int = 80
    shift_rpm: int = 6500
    redline_rpm: int = 7200
    use_mph: bool = True
    tire_low_psi: float = 28.0
    tire_high_psi: float = 36.0
    coolant_warn_f: int = 220
    oil_warn_f: int = 260


# =============================================================================
# SIMULATOR
# =============================================================================

class CombinedSimulator:
    def __init__(self):
        pygame.init()
        
        self.window = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("MX5 Telemetry - Combined UI Simulator")
        
        # Display surfaces
        self.esp32_surface = pygame.Surface((ESP32_SIZE, ESP32_SIZE), pygame.SRCALPHA)
        self.pi_surface = pygame.Surface((PI_WIDTH, PI_HEIGHT))
        
        # Unified state - BOTH displays show same screen
        self.current_screen = Screen.OVERVIEW
        self.sleeping = False
        self.demo_mode = True
        self.demo_rpm_dir = 1
        
        # Settings state
        self.in_settings_menu = False
        self.settings_selection = 0
        self.settings_edit_mode = False
        
        # Data
        self.telemetry = TelemetryData()
        self.settings = Settings()
        
        # Fonts
        self.font_huge = pygame.font.Font(None, 96)
        self.font_large = pygame.font.Font(None, 72)
        self.font_medium = pygame.font.Font(None, 48)
        self.font_small = pygame.font.Font(None, 32)
        self.font_tiny = pygame.font.Font(None, 24)
        
        # Pi-specific larger fonts
        self.pi_font_huge = pygame.font.Font(None, 120)
        self.pi_font_large = pygame.font.Font(None, 80)
        self.pi_font_medium = pygame.font.Font(None, 56)
        
        # Clock and input
        self.clock = pygame.time.Clock()
        self.last_button = ButtonEvent.NONE
        self.button_time = 0
    
    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    self.handle_key(event.key)
            
            if self.demo_mode:
                self.update_demo()
            
            self.render()
            pygame.display.flip()
            self.clock.tick(30)
        
        pygame.quit()
    
    def handle_key(self, key):
        # Special keys
        if key == pygame.K_SPACE:
            self.sleeping = not self.sleeping
            return
        if key == pygame.K_TAB:
            self.demo_mode = not self.demo_mode
            return
        
        # Wake from sleep
        if self.sleeping:
            self.sleeping = False
            return
        
        # Map to button
        button = self.key_to_button(key)
        if button == ButtonEvent.NONE:
            return
        
        self.last_button = button
        self.button_time = pygame.time.get_ticks()
        
        # Handle input
        if self.current_screen == Screen.SETTINGS:
            self.handle_settings_button(button)
        else:
            self.handle_navigation_button(button)
    
    def key_to_button(self, key) -> ButtonEvent:
        mapping = {
            # VOL+/VOL- (Left/Right arrows, A/D keys)
            pygame.K_RIGHT: ButtonEvent.VOL_UP,
            pygame.K_d: ButtonEvent.VOL_UP,
            pygame.K_LEFT: ButtonEvent.VOL_DOWN,
            pygame.K_a: ButtonEvent.VOL_DOWN,
            # RES+/SET- (Up/Down arrows, W/S keys)
            pygame.K_UP: ButtonEvent.RES_PLUS,
            pygame.K_w: ButtonEvent.RES_PLUS,
            pygame.K_DOWN: ButtonEvent.SET_MINUS,
            pygame.K_s: ButtonEvent.SET_MINUS,
            # ON/OFF and CANCEL
            pygame.K_RETURN: ButtonEvent.ON_OFF,
            pygame.K_KP_ENTER: ButtonEvent.ON_OFF,
            pygame.K_ESCAPE: ButtonEvent.CANCEL,
            pygame.K_b: ButtonEvent.CANCEL,
        }
        return mapping.get(key, ButtonEvent.NONE)
    
    def handle_navigation_button(self, button: ButtonEvent):
        """Navigate between screens (non-settings)"""
        screens = list(Screen)
        idx = screens.index(self.current_screen)
        
        if button == ButtonEvent.RES_PLUS:
            self.current_screen = screens[(idx - 1) % len(screens)]
        elif button == ButtonEvent.SET_MINUS:
            self.current_screen = screens[(idx + 1) % len(screens)]
        elif button == ButtonEvent.ON_OFF:
            # Enter settings
            self.current_screen = Screen.SETTINGS
            self.settings_selection = 0
            self.settings_edit_mode = False
    
    def handle_settings_button(self, button: ButtonEvent):
        """Handle input in settings screen"""
        items = self.get_settings_items()
        
        if button == ButtonEvent.RES_PLUS:
            if self.settings_edit_mode:
                self.adjust_setting(1)
            else:
                self.settings_selection = (self.settings_selection - 1) % len(items)
        elif button == ButtonEvent.SET_MINUS:
            if self.settings_edit_mode:
                self.adjust_setting(-1)
            else:
                self.settings_selection = (self.settings_selection + 1) % len(items)
        elif button == ButtonEvent.VOL_UP:
            self.adjust_setting(1)
        elif button == ButtonEvent.VOL_DOWN:
            self.adjust_setting(-1)
        elif button == ButtonEvent.ON_OFF:
            if items[self.settings_selection][0] == "Back":
                self.current_screen = Screen.OVERVIEW
                self.settings_edit_mode = False
            else:
                self.settings_edit_mode = not self.settings_edit_mode
        elif button == ButtonEvent.CANCEL:
            if self.settings_edit_mode:
                self.settings_edit_mode = False
            else:
                self.current_screen = Screen.OVERVIEW
    
    def get_settings_items(self):
        """Return list of (name, value, unit) tuples"""
        return [
            ("Brightness", self.settings.brightness, "%"),
            ("Shift RPM", self.settings.shift_rpm, ""),
            ("Redline", self.settings.redline_rpm, ""),
            ("Units", "MPH" if self.settings.use_mph else "KMH", ""),
            ("Low Tire PSI", self.settings.tire_low_psi, ""),
            ("Coolant Warn", self.settings.coolant_warn_f, "°F"),
            ("Back", "", ""),
        ]
    
    def adjust_setting(self, delta: int):
        sel = self.settings_selection
        if sel == 0:  # Brightness
            self.settings.brightness = max(10, min(100, self.settings.brightness + delta * 5))
        elif sel == 1:  # Shift RPM
            self.settings.shift_rpm = max(4000, min(7500, self.settings.shift_rpm + delta * 100))
        elif sel == 2:  # Redline
            self.settings.redline_rpm = max(5000, min(8000, self.settings.redline_rpm + delta * 100))
        elif sel == 3:  # Units
            self.settings.use_mph = not self.settings.use_mph
        elif sel == 4:  # Low tire PSI
            self.settings.tire_low_psi = max(20, min(35, self.settings.tire_low_psi + delta * 0.5))
        elif sel == 5:  # Coolant warn
            self.settings.coolant_warn_f = max(180, min(250, self.settings.coolant_warn_f + delta * 5))
    
    def update_demo(self):
        """Animate telemetry data"""
        # RPM oscillation
        self.telemetry.rpm += 50 * self.demo_rpm_dir
        if self.telemetry.rpm >= 6800:
            self.demo_rpm_dir = -1
        elif self.telemetry.rpm <= 900:
            self.demo_rpm_dir = 1
        
        # Gear from RPM
        rpm = self.telemetry.rpm
        if rpm < 1500: self.telemetry.gear = 1
        elif rpm < 2500: self.telemetry.gear = 2
        elif rpm < 3500: self.telemetry.gear = 3
        elif rpm < 4500: self.telemetry.gear = 4
        elif rpm < 5500: self.telemetry.gear = 5
        else: self.telemetry.gear = 6
        
        # Speed from RPM & gear
        self.telemetry.speed_kmh = int(rpm * self.telemetry.gear / 95)
        self.telemetry.throttle_percent = min(100, max(0, (rpm - 800) // 55))
        
        # G-forces
        self.telemetry.g_lateral += random.uniform(-0.1, 0.1)
        self.telemetry.g_lateral = max(-1.3, min(1.3, self.telemetry.g_lateral))
        self.telemetry.g_longitudinal += random.uniform(-0.06, 0.06)
        self.telemetry.g_longitudinal = max(-1.0, min(0.6, self.telemetry.g_longitudinal))
        
        # Lap time
        self.telemetry.lap_time_ms += 33
    
    # =========================================================================
    # RENDERING
    # =========================================================================
    
    def render(self):
        self.window.fill((30, 30, 40))
        
        # Positions
        esp_x = WINDOW_PADDING
        esp_y = WINDOW_PADDING
        pi_x = ESP32_SIZE + WINDOW_PADDING * 2
        pi_y = WINDOW_PADDING
        panel_x = ESP32_SIZE + PI_WIDTH + WINDOW_PADDING * 3
        
        # Render both displays
        self.render_esp32()
        self.render_pi()
        
        # Blit to window
        self.window.blit(self.esp32_surface, (esp_x, esp_y))
        self.window.blit(self.pi_surface, (pi_x, pi_y))
        
        # Borders
        pygame.draw.circle(self.window, COLOR_ACCENT,
                          (esp_x + ESP32_SIZE//2, esp_y + ESP32_SIZE//2),
                          ESP32_SIZE//2 + 3, 3)
        pygame.draw.rect(self.window, COLOR_ACCENT,
                        (pi_x - 3, pi_y - 3, PI_WIDTH + 6, PI_HEIGHT + 6), 3)
        
        # Labels
        lbl1 = self.font_small.render("ESP32-S3 (360x360)", True, COLOR_WHITE)
        lbl2 = self.font_small.render("Raspberry Pi (800x480)", True, COLOR_WHITE)
        self.window.blit(lbl1, (esp_x, esp_y + ESP32_SIZE + 8))
        self.window.blit(lbl2, (pi_x, pi_y + PI_HEIGHT + 8))
        
        # Control panel
        self.render_control_panel(panel_x, WINDOW_PADDING)
    
    def render_esp32(self):
        """Render ESP32 round display - compact view"""
        self.esp32_surface.fill((0, 0, 0, 0))
        center = ESP32_SIZE // 2
        
        # Background circle
        pygame.draw.circle(self.esp32_surface, COLOR_BG, (center, center), center)
        
        if self.sleeping:
            txt = self.font_medium.render("SLEEP", True, COLOR_DARK_GRAY)
            self.esp32_surface.blit(txt, txt.get_rect(center=(center, center)))
            return
        
        # Render current screen
        renderers = {
            Screen.OVERVIEW: self.render_esp32_overview,
            Screen.RPM_SPEED: self.render_esp32_rpm_speed,
            Screen.TPMS: self.render_esp32_tpms,
            Screen.ENGINE: self.render_esp32_engine,
            Screen.GFORCE: self.render_esp32_gforce,
            Screen.SETTINGS: self.render_esp32_settings,
        }
        renderers[self.current_screen]()
        
        # Screen indicator dots
        self.render_screen_dots(self.esp32_surface, center, ESP32_SIZE - 22)
    
    def render_pi(self):
        """Render Pi display - detailed view"""
        self.pi_surface.fill(COLOR_BG_DARK)
        
        if self.sleeping:
            txt = self.pi_font_large.render("SLEEP MODE", True, COLOR_DARK_GRAY)
            self.pi_surface.blit(txt, txt.get_rect(center=(PI_WIDTH//2, PI_HEIGHT//2)))
            return
        
        # Render current screen
        renderers = {
            Screen.OVERVIEW: self.render_pi_overview,
            Screen.RPM_SPEED: self.render_pi_rpm_speed,
            Screen.TPMS: self.render_pi_tpms,
            Screen.ENGINE: self.render_pi_engine,
            Screen.GFORCE: self.render_pi_gforce,
            Screen.SETTINGS: self.render_pi_settings,
        }
        renderers[self.current_screen]()
        
        # Screen title bar
        pygame.draw.rect(self.pi_surface, (30, 30, 45), (0, 0, PI_WIDTH, 50))
        title = SCREEN_NAMES[self.current_screen]
        txt = self.font_medium.render(title, True, COLOR_WHITE)
        self.pi_surface.blit(txt, (20, 8))
        
        # Screen indicator in title bar
        screens = list(Screen)
        dot_x = PI_WIDTH - 20 - len(screens) * 18
        for i, scr in enumerate(screens):
            color = COLOR_ACCENT if scr == self.current_screen else COLOR_DARK_GRAY
            pygame.draw.circle(self.pi_surface, color, (dot_x + i * 18, 25), 6)
    
    def render_screen_dots(self, surface, cx, y):
        """Render screen navigation dots"""
        screens = list(Screen)
        total = len(screens) * 12
        start = cx - total // 2
        for i, scr in enumerate(screens):
            color = COLOR_WHITE if scr == self.current_screen else COLOR_DARK_GRAY
            pygame.draw.circle(surface, color, (start + i * 12, y), 4)
    
    # -------------------------------------------------------------------------
    # ESP32 SCREENS (Compact)
    # -------------------------------------------------------------------------
    
    def render_esp32_overview(self):
        """Overview screen - Gear + key alerts + mini TPMS with temps"""
        center = ESP32_SIZE // 2
        
        # Get any alerts
        alerts = self.get_alerts()
        
        # Subtle radial gradient background effect (dark center ring)
        pygame.draw.circle(self.esp32_surface, COLOR_BG_CARD, (center, center), 160)
        pygame.draw.circle(self.esp32_surface, COLOR_BG, (center, center), 100)
        
        # Big gear in center-top with glow effect
        gear = "N" if self.telemetry.gear == 0 else str(self.telemetry.gear)
        rpm_color = self.get_rpm_color(self.telemetry.rpm)
        
        # Gear glow
        glow_surf = pygame.Surface((80, 80), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (*rpm_color[:3], 40), (40, 40), 35)
        self.esp32_surface.blit(glow_surf, (center - 40, 25))
        
        gear_txt = self.font_large.render(gear, True, rpm_color)
        self.esp32_surface.blit(gear_txt, gear_txt.get_rect(center=(center, 60)))
        
        # Speed below gear with unit
        speed = self.telemetry.speed_kmh
        if self.settings.use_mph:
            speed = int(speed * 0.621371)
        unit = "MPH" if self.settings.use_mph else "KMH"
        speed_txt = self.font_small.render(f"{speed} {unit}", True, COLOR_WHITE)
        self.esp32_surface.blit(speed_txt, speed_txt.get_rect(center=(center, 105)))
        
        # Mini TPMS (4 boxes with PSI + Temp) - compact
        tire_y = 150
        box_w, box_h = 48, 38
        positions = [(center - 52, tire_y), (center + 52, tire_y),
                     (center - 52, tire_y + 45), (center + 52, tire_y + 45)]
        
        for i, (x, y) in enumerate(positions):
            psi = self.telemetry.tire_pressure[i]
            temp = self.telemetry.tire_temp[i]
            
            if psi < self.settings.tire_low_psi:
                color = COLOR_RED
            elif psi > self.settings.tire_high_psi:
                color = COLOR_YELLOW
            else:
                color = COLOR_GREEN
            
            # Modern rounded box with subtle fill
            pygame.draw.rect(self.esp32_surface, COLOR_BG_CARD, 
                           (x - box_w//2, y - box_h//2, box_w, box_h), border_radius=6)
            pygame.draw.rect(self.esp32_surface, color, 
                           (x - box_w//2, y - box_h//2, box_w, box_h), 2, border_radius=6)
            
            # PSI and Temp on same line
            txt = self.font_tiny.render(f"{psi:.0f}/{temp:.0f}°", True, color)
            self.esp32_surface.blit(txt, txt.get_rect(center=(x, y)))
        
        # Alert section at bottom - within bounds
        alert_y = 260
        if alerts:
            alert_txt, alert_color = alerts[0]
            
            pygame.draw.rect(self.esp32_surface, alert_color, 
                           (40, alert_y, ESP32_SIZE - 80, 26), border_radius=6)
            txt = self.font_tiny.render(alert_txt, True, COLOR_BG)
            self.esp32_surface.blit(txt, txt.get_rect(center=(center, alert_y + 13)))
            
            if len(alerts) > 1:
                count_txt = self.font_tiny.render(f"+{len(alerts)-1}", True, COLOR_YELLOW)
                self.esp32_surface.blit(count_txt, count_txt.get_rect(center=(center, alert_y + 38)))
        else:
            pygame.draw.rect(self.esp32_surface, COLOR_BG_CARD, 
                           (40, alert_y, ESP32_SIZE - 80, 26), border_radius=6)
            pygame.draw.rect(self.esp32_surface, COLOR_GREEN, 
                           (40, alert_y, ESP32_SIZE - 80, 26), 2, border_radius=6)
            txt = self.font_tiny.render("✓ ALL OK", True, COLOR_GREEN)
            self.esp32_surface.blit(txt, txt.get_rect(center=(center, alert_y + 13)))
    
    def render_esp32_rpm_speed(self):
        center = ESP32_SIZE // 2
        
        # Background ring effect
        pygame.draw.circle(self.esp32_surface, COLOR_BG_CARD, (center, center), 155)
        pygame.draw.circle(self.esp32_surface, COLOR_BG, (center, center), 120)
        
        # RPM arc - modern thick arc with glow
        radius = 145
        thickness = 20
        
        # Background arc
        self.draw_arc(self.esp32_surface, center, center, radius, thickness, 135, 405, COLOR_DARK_GRAY)
        
        # RPM fill arc with gradient effect
        rpm_pct = self.telemetry.rpm / self.settings.redline_rpm
        rpm_angle = min(270, max(0, rpm_pct * 270))
        rpm_color = self.get_rpm_color(self.telemetry.rpm)
        
        # Draw filled arc
        self.draw_arc(self.esp32_surface, center, center, radius, thickness, 135, 135 + rpm_angle, rpm_color)
        
        # Shift indicator ring (glowing when active)
        if self.telemetry.rpm >= self.settings.shift_rpm:
            pygame.draw.circle(self.esp32_surface, COLOR_RED, (center, 35), 12)
            # Glow effect
            glow = pygame.Surface((40, 40), pygame.SRCALPHA)
            pygame.draw.circle(glow, (255, 70, 85, 80), (20, 20), 18)
            self.esp32_surface.blit(glow, (center - 20, 15))
        
        # Gear in center with glow
        gear = "N" if self.telemetry.gear == 0 else str(self.telemetry.gear)
        
        # Gear glow
        glow_surf = pygame.Surface((90, 90), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (*rpm_color[:3], 35), (45, 45), 40)
        self.esp32_surface.blit(glow_surf, (center - 45, center - 60))
        
        gear_txt = self.font_huge.render(gear, True, rpm_color)
        self.esp32_surface.blit(gear_txt, gear_txt.get_rect(center=(center, center - 15)))
        
        # Speed below gear
        speed = self.telemetry.speed_kmh
        if self.settings.use_mph:
            speed = int(speed * 0.621371)
        speed_txt = self.font_medium.render(str(speed), True, COLOR_WHITE)
        self.esp32_surface.blit(speed_txt, speed_txt.get_rect(center=(center, center + 40)))
        
        unit = "MPH" if self.settings.use_mph else "KMH"
        unit_txt = self.font_tiny.render(unit, True, COLOR_GRAY)
        self.esp32_surface.blit(unit_txt, unit_txt.get_rect(center=(center, center + 65)))
        
        # RPM digits at bottom of arc
        rpm_txt = self.font_small.render(f"{self.telemetry.rpm} RPM", True, COLOR_GRAY)
        self.esp32_surface.blit(rpm_txt, rpm_txt.get_rect(center=(center, ESP32_SIZE - 45)))
    
    def render_esp32_tpms(self):
        center = ESP32_SIZE // 2
        
        # Modern title with accent line
        txt = self.font_small.render("TPMS", True, COLOR_WHITE)
        self.esp32_surface.blit(txt, txt.get_rect(center=(center, 35)))
        pygame.draw.line(self.esp32_surface, COLOR_ACCENT, (center - 40, 52), (center + 40, 52), 2)
        
        # Car outline (modern minimal)
        car_w, car_h = 70, 120
        car_rect = pygame.Rect(center - car_w//2, center - car_h//2 + 10, car_w, car_h)
        pygame.draw.rect(self.esp32_surface, COLOR_BG_CARD, car_rect, border_radius=12)
        pygame.draw.rect(self.esp32_surface, COLOR_DARK_GRAY, car_rect, 2, border_radius=12)
        
        # 4 tire positions (car outline style)
        positions = [(center - 70, center - 35), (center + 70, center - 35),
                     (center - 70, center + 65), (center + 70, center + 65)]
        labels = ["FL", "FR", "RL", "RR"]
        
        for i, (x, y) in enumerate(positions):
            psi = self.telemetry.tire_pressure[i]
            temp = self.telemetry.tire_temp[i]
            
            # Color based on pressure
            if psi < self.settings.tire_low_psi:
                color = COLOR_RED
            elif psi > self.settings.tire_high_psi:
                color = COLOR_YELLOW
            else:
                color = COLOR_GREEN
            
            # Modern tire card
            box_w, box_h = 68, 58
            pygame.draw.rect(self.esp32_surface, COLOR_BG_CARD, 
                           (x - box_w//2, y - box_h//2, box_w, box_h), border_radius=10)
            
            # Colored accent bar on left
            pygame.draw.rect(self.esp32_surface, color, 
                           (x - box_w//2, y - box_h//2, 4, box_h), 
                           border_top_left_radius=10, border_bottom_left_radius=10)
            
            # Label (small, top)
            lbl = self.font_tiny.render(labels[i], True, COLOR_GRAY)
            self.esp32_surface.blit(lbl, lbl.get_rect(center=(x + 2, y - 18)))
            
            # PSI (large)
            psi_txt = self.font_small.render(f"{psi:.1f}", True, color)
            self.esp32_surface.blit(psi_txt, psi_txt.get_rect(center=(x + 2, y + 2)))
            
            # Temp (small)
            temp_txt = self.font_tiny.render(f"{temp:.0f}°F", True, COLOR_GRAY)
            self.esp32_surface.blit(temp_txt, temp_txt.get_rect(center=(x + 2, y + 20)))
    
    def render_esp32_engine(self):
        center = ESP32_SIZE // 2
        
        # Modern title with accent line
        txt = self.font_small.render("ENGINE", True, COLOR_WHITE)
        self.esp32_surface.blit(txt, txt.get_rect(center=(center, 35)))
        pygame.draw.line(self.esp32_surface, COLOR_ACCENT, (center - 50, 52), (center + 50, 52), 2)
        
        # Coolant (left card)
        coolant = self.telemetry.coolant_temp_f
        cool_color = COLOR_RED if coolant > self.settings.coolant_warn_f else COLOR_TEAL
        
        # Card background
        pygame.draw.rect(self.esp32_surface, COLOR_BG_CARD, (30, 70, 100, 75), border_radius=12)
        pygame.draw.rect(self.esp32_surface, cool_color, (30, 70, 4, 75), 
                        border_top_left_radius=12, border_bottom_left_radius=12)
        
        txt = self.font_tiny.render("COOLANT", True, COLOR_GRAY)
        self.esp32_surface.blit(txt, txt.get_rect(center=(80, 85)))
        txt = self.font_medium.render(f"{coolant}°", True, cool_color)
        self.esp32_surface.blit(txt, txt.get_rect(center=(80, 118)))
        
        # Oil (right card)
        oil = self.telemetry.oil_temp_f
        oil_color = COLOR_RED if oil > self.settings.oil_warn_f else COLOR_GREEN
        
        pygame.draw.rect(self.esp32_surface, COLOR_BG_CARD, (ESP32_SIZE - 130, 70, 100, 75), border_radius=12)
        pygame.draw.rect(self.esp32_surface, oil_color, (ESP32_SIZE - 130, 70, 4, 75),
                        border_top_left_radius=12, border_bottom_left_radius=12)
        
        txt = self.font_tiny.render("OIL", True, COLOR_GRAY)
        self.esp32_surface.blit(txt, txt.get_rect(center=(ESP32_SIZE - 80, 85)))
        txt = self.font_medium.render(f"{oil}°", True, oil_color)
        self.esp32_surface.blit(txt, txt.get_rect(center=(ESP32_SIZE - 80, 118)))
        
        # Fuel gauge (center - circular progress)
        fuel = self.telemetry.fuel_level_percent
        fuel_color = COLOR_RED if fuel < 15 else (COLOR_YELLOW if fuel < 25 else COLOR_GREEN)
        
        fuel_cx, fuel_cy = center, 210
        fuel_r = 55
        
        # Background circle
        pygame.draw.circle(self.esp32_surface, COLOR_BG_CARD, (fuel_cx, fuel_cy), fuel_r)
        pygame.draw.circle(self.esp32_surface, COLOR_DARK_GRAY, (fuel_cx, fuel_cy), fuel_r, 3)
        
        # Fuel arc
        fuel_angle = int(360 * fuel / 100)
        self.draw_arc(self.esp32_surface, fuel_cx, fuel_cy, fuel_r - 5, 8, -90, -90 + fuel_angle, fuel_color)
        
        # Fuel percentage in center
        txt = self.font_medium.render(f"{int(fuel)}%", True, fuel_color)
        self.esp32_surface.blit(txt, txt.get_rect(center=(fuel_cx, fuel_cy - 5)))
        txt = self.font_tiny.render("FUEL", True, COLOR_GRAY)
        self.esp32_surface.blit(txt, txt.get_rect(center=(fuel_cx, fuel_cy + 20)))
        
        # Voltage at bottom
        voltage = self.telemetry.voltage
        volt_color = COLOR_RED if voltage < 12.0 else (COLOR_YELLOW if voltage < 13.0 else COLOR_GREEN)
        
        pygame.draw.rect(self.esp32_surface, COLOR_BG_CARD, (center - 60, 280, 120, 35), border_radius=8)
        txt = self.font_tiny.render(f"⚡ {voltage:.1f}V", True, volt_color)
        self.esp32_surface.blit(txt, txt.get_rect(center=(center, 297)))
    
    def render_esp32_gforce(self):
        center = ESP32_SIZE // 2
        
        # Modern title with accent line
        txt = self.font_small.render("G-FORCE", True, COLOR_WHITE)
        self.esp32_surface.blit(txt, txt.get_rect(center=(center, 35)))
        pygame.draw.line(self.esp32_surface, COLOR_ACCENT, (center - 55, 52), (center + 55, 52), 2)
        
        # G-ball background with modern gradient rings
        ball_center = (center, center + 15)
        ball_radius = 105
        
        # Outer glow ring
        pygame.draw.circle(self.esp32_surface, COLOR_BG_CARD, ball_center, ball_radius + 8)
        pygame.draw.circle(self.esp32_surface, COLOR_BG, ball_center, ball_radius)
        
        # Grid circles (0.5G, 1G, 1.5G)
        for g, alpha in [(0.5, 40), (1.0, 60), (1.5, 80)]:
            r = int(g * 60)
            pygame.draw.circle(self.esp32_surface, COLOR_DARK_GRAY, ball_center, r, 1)
        
        # Crosshairs
        pygame.draw.line(self.esp32_surface, COLOR_DARK_GRAY, 
                        (ball_center[0] - ball_radius, ball_center[1]),
                        (ball_center[0] + ball_radius, ball_center[1]), 1)
        pygame.draw.line(self.esp32_surface, COLOR_DARK_GRAY,
                        (ball_center[0], ball_center[1] - ball_radius),
                        (ball_center[0], ball_center[1] + ball_radius), 1)
        
        # G-ball position - negate lateral so ball moves in direction of turn
        g_scale = 60  # pixels per G
        gx = ball_center[0] - int(self.telemetry.g_lateral * g_scale)
        gy = ball_center[1] - int(self.telemetry.g_longitudinal * g_scale)
        
        # Clamp to circle
        dx, dy = gx - ball_center[0], gy - ball_center[1]
        dist = math.sqrt(dx*dx + dy*dy)
        if dist > ball_radius - 12:
            scale = (ball_radius - 12) / dist
            gx = ball_center[0] + int(dx * scale)
            gy = ball_center[1] + int(dy * scale)
        
        # G-ball with glow
        glow = pygame.Surface((50, 50), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*COLOR_ACCENT[:3], 80), (25, 25), 20)
        self.esp32_surface.blit(glow, (gx - 25, gy - 25))
        
        pygame.draw.circle(self.esp32_surface, COLOR_ACCENT, (gx, gy), 12)
        pygame.draw.circle(self.esp32_surface, COLOR_WHITE, (gx, gy), 12, 2)
        
        # Combined G value (bottom)
        combined = math.sqrt(self.telemetry.g_lateral**2 + self.telemetry.g_longitudinal**2)
        
        # G readout cards at bottom - fit within circle
        y = ESP32_SIZE - 80
        card_w = 85
        
        # Lateral
        pygame.draw.rect(self.esp32_surface, COLOR_BG_CARD, (35, y, card_w, 35), border_radius=6)
        txt = self.font_tiny.render(f"LAT {self.telemetry.g_lateral:+.1f}", True, COLOR_CYAN)
        self.esp32_surface.blit(txt, txt.get_rect(center=(35 + card_w//2, y + 17)))
        
        # Longitudinal
        pygame.draw.rect(self.esp32_surface, COLOR_BG_CARD, (center - card_w//2, y, card_w, 35), border_radius=6)
        txt = self.font_tiny.render(f"LON {self.telemetry.g_longitudinal:+.1f}", True, COLOR_PURPLE)
        self.esp32_surface.blit(txt, txt.get_rect(center=(center, y + 17)))
        
        # Combined (right)
        pygame.draw.rect(self.esp32_surface, COLOR_BG_CARD, (ESP32_SIZE - 35 - card_w, y, card_w, 35), border_radius=6)
        txt = self.font_tiny.render(f"{combined:.1f}G", True, COLOR_ACCENT)
        self.esp32_surface.blit(txt, txt.get_rect(center=(ESP32_SIZE - 35 - card_w//2, y + 17)))
    
    def render_esp32_settings(self):
        center = ESP32_SIZE // 2
        
        # Modern title with accent line
        txt = self.font_small.render("SETTINGS", True, COLOR_WHITE)
        self.esp32_surface.blit(txt, txt.get_rect(center=(center, 50)))
        pygame.draw.line(self.esp32_surface, COLOR_ACCENT, (center - 60, 68), (center + 60, 68), 2)
        
        items = self.get_settings_items()
        sel = self.settings_selection
        
        # Show only: previous, selected, next (3 visible items max)
        # This fits better in the circular display
        visible_indices = []
        if sel > 0:
            visible_indices.append(sel - 1)
        visible_indices.append(sel)
        if sel < len(items) - 1:
            visible_indices.append(sel + 1)
        
        # Position indicators (arrows showing more items above/below)
        if sel > 0:
            txt = self.font_tiny.render("▲", True, COLOR_GRAY)
            self.esp32_surface.blit(txt, txt.get_rect(center=(center, 85)))
        
        # Calculate vertical positions - center the visible items
        item_h = 50
        total_h = len(visible_indices) * item_h
        start_y = center - total_h // 2 + 20
        
        for slot, idx in enumerate(visible_indices):
            name, value, unit = items[idx]
            y = start_y + slot * item_h
            is_selected = idx == sel
            
            # Card background - wider for selected
            card_margin = 45 if is_selected else 55
            bg_color = COLOR_BG_ELEVATED if is_selected else COLOR_BG_CARD
            card_h = 42 if is_selected else 36
            
            pygame.draw.rect(self.esp32_surface, bg_color, 
                           (card_margin, y, ESP32_SIZE - card_margin * 2, card_h), border_radius=10)
            
            if is_selected:
                # Selection indicator bar
                pygame.draw.rect(self.esp32_surface, COLOR_ACCENT, 
                               (card_margin, y, 4, card_h), 
                               border_top_left_radius=10, border_bottom_left_radius=10)
                if self.settings_edit_mode:
                    # Edit mode glow
                    pygame.draw.rect(self.esp32_surface, COLOR_ACCENT,
                                   (card_margin, y, ESP32_SIZE - card_margin * 2, card_h), 2, border_radius=10)
            
            color = COLOR_WHITE if is_selected else COLOR_GRAY
            font = self.font_small if is_selected else self.font_tiny
            
            # Name on left
            txt = font.render(name, True, color)
            self.esp32_surface.blit(txt, (card_margin + 12, y + (card_h - txt.get_height()) // 2))
            
            # Value on right
            if value != "":
                val_str = f"{value}{unit}"
                val_color = COLOR_ACCENT if is_selected else COLOR_WHITE
                txt = font.render(val_str, True, val_color)
                self.esp32_surface.blit(txt, (ESP32_SIZE - card_margin - 12 - txt.get_width(), y + (card_h - txt.get_height()) // 2))
        
        # Down arrow if more items below
        if sel < len(items) - 1:
            txt = self.font_tiny.render("▼", True, COLOR_GRAY)
            self.esp32_surface.blit(txt, txt.get_rect(center=(center, ESP32_SIZE - 85)))
        
        # Item counter
        txt = self.font_tiny.render(f"{sel + 1}/{len(items)}", True, COLOR_DARK_GRAY)
        self.esp32_surface.blit(txt, txt.get_rect(center=(center, ESP32_SIZE - 60)))
    
    # -------------------------------------------------------------------------
    # PI SCREENS (Detailed)
    # -------------------------------------------------------------------------
    
    def render_pi_overview(self):
        """Overview screen with gear, TPMS, key engine data, and alerts - Modern UI"""
        # Note: Title bar is 50px, content area is y=55 to y=480 (425px available)
        alerts = self.get_alerts()
        TOP = 55  # Below title bar
        
        # Left panel: Gear + Speed + RPM
        left_panel_x = 20
        left_panel_w = 180
        
        # Gear card with glow
        pygame.draw.rect(self.pi_surface, COLOR_BG_CARD, 
                        (left_panel_x, TOP, left_panel_w, 150), border_radius=14)
        
        rpm_color = self.get_rpm_color(self.telemetry.rpm)
        gear = "N" if self.telemetry.gear == 0 else str(self.telemetry.gear)
        
        # Gear glow effect
        glow = pygame.Surface((90, 90), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*rpm_color[:3], 50), (45, 45), 40)
        self.pi_surface.blit(glow, (left_panel_x + left_panel_w//2 - 45, TOP + 5))
        
        txt = self.pi_font_large.render(gear, True, rpm_color)
        self.pi_surface.blit(txt, txt.get_rect(center=(left_panel_x + left_panel_w//2, TOP + 55)))
        
        # Speed below gear
        speed = self.telemetry.speed_kmh
        if self.settings.use_mph:
            speed = int(speed * 0.621371)
        unit = "MPH" if self.settings.use_mph else "KMH"
        txt = self.font_medium.render(f"{speed:.0f} {unit}", True, COLOR_WHITE)
        self.pi_surface.blit(txt, txt.get_rect(center=(left_panel_x + left_panel_w//2, TOP + 120)))
        
        # RPM bar card
        pygame.draw.rect(self.pi_surface, COLOR_BG_CARD, 
                        (left_panel_x, TOP + 160, left_panel_w, 40), border_radius=10)
        rpm_pct = min(1.0, self.telemetry.rpm / self.settings.redline_rpm)
        bar_x, bar_y = left_panel_x + 12, TOP + 172
        bar_w = left_panel_w - 24
        pygame.draw.rect(self.pi_surface, COLOR_DARK_GRAY, (bar_x, bar_y, bar_w, 12), border_radius=6)
        pygame.draw.rect(self.pi_surface, rpm_color, (bar_x, bar_y, int(bar_w * rpm_pct), 12), border_radius=6)
        txt = self.font_tiny.render(f"{self.telemetry.rpm} RPM", True, COLOR_GRAY)
        self.pi_surface.blit(txt, txt.get_rect(center=(left_panel_x + left_panel_w//2, TOP + 188)))
        
        # Key values grid (2x2) - compact
        values = [
            ("COOL", f"{self.telemetry.coolant_temp_f:.0f}°", 
             COLOR_RED if self.telemetry.coolant_temp_f >= self.settings.coolant_warn_f else COLOR_TEAL),
            ("OIL", f"{self.telemetry.oil_temp_f:.0f}°",
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
            
            pygame.draw.rect(self.pi_surface, COLOR_BG_CARD, (x, y, card_w, card_h), border_radius=8)
            pygame.draw.rect(self.pi_surface, color, (x, y, 3, card_h), 
                           border_top_left_radius=8, border_bottom_left_radius=8)
            
            txt = self.font_tiny.render(label, True, COLOR_GRAY)
            self.pi_surface.blit(txt, (x + 10, y + 5))
            txt = self.font_small.render(val, True, color)
            self.pi_surface.blit(txt, (x + 10, y + 22))
        
        # Center: TPMS diagram with modern styling
        tpms_cx, tpms_cy = 340, TOP + 160
        
        # Modern car outline
        car_w, car_h = 55, 100
        pygame.draw.rect(self.pi_surface, COLOR_BG_CARD, 
                        (tpms_cx - car_w//2, tpms_cy - car_h//2, car_w, car_h), border_radius=12)
        
        # Tire cards - compact
        box_w, box_h = 60, 65
        gap = 70
        tire_positions = [
            (0, -gap, -30, "FL"),
            (1, gap, -30, "FR"),
            (2, -gap, 50, "RL"),
            (3, gap, 50, "RR"),
        ]
        
        for idx, dx, dy, name in tire_positions:
            psi = self.telemetry.tire_pressure[idx]
            temp = self.telemetry.tire_temp[idx]
            x = tpms_cx + dx - box_w//2
            y = tpms_cy + dy - box_h//2
            
            if psi < self.settings.tire_low_psi:
                color = COLOR_RED
            elif psi > self.settings.tire_high_psi:
                color = COLOR_YELLOW
            else:
                color = COLOR_GREEN
            
            # Tire card
            pygame.draw.rect(self.pi_surface, COLOR_BG_CARD, (x, y, box_w, box_h), border_radius=10)
            pygame.draw.rect(self.pi_surface, color, (x, y, 3, box_h), 
                           border_top_left_radius=10, border_bottom_left_radius=10)
            
            txt = self.font_tiny.render(name, True, COLOR_GRAY)
            self.pi_surface.blit(txt, txt.get_rect(center=(x + box_w//2, y + 10)))
            
            txt = self.font_small.render(f"{psi:.0f}", True, color)
            self.pi_surface.blit(txt, txt.get_rect(center=(x + box_w//2, y + 32)))
            
            txt = self.font_tiny.render(f"{temp:.0f}°", True, COLOR_GRAY)
            self.pi_surface.blit(txt, txt.get_rect(center=(x + box_w//2, y + 52)))
        
        # Right panel: Alerts
        alerts_x = 490
        alerts_y = TOP
        alerts_w = 290
        alerts_h = PI_HEIGHT - TOP - 10
        
        # Panel background
        pygame.draw.rect(self.pi_surface, COLOR_BG_CARD, 
                        (alerts_x, alerts_y, alerts_w, alerts_h), border_radius=14)
        
        # Header
        header_color = COLOR_RED if alerts else COLOR_GREEN
        pygame.draw.rect(self.pi_surface, header_color, 
                        (alerts_x, alerts_y, alerts_w, 45), 
                        border_top_left_radius=14, border_top_right_radius=14)
        header_text = "⚠ ALERTS" if alerts else "✓ ALL OK"
        txt = self.font_medium.render(header_text, True, COLOR_WHITE)
        self.pi_surface.blit(txt, txt.get_rect(center=(alerts_x + alerts_w//2, alerts_y + 22)))
        
        if alerts:
            alert_y = alerts_y + 55
            for i, (alert_text, alert_color) in enumerate(alerts[:8]):
                pygame.draw.rect(self.pi_surface, COLOR_BG_ELEVATED,
                               (alerts_x + 10, alert_y, alerts_w - 20, 38), border_radius=6)
                pygame.draw.rect(self.pi_surface, alert_color,
                               (alerts_x + 10, alert_y, 3, 38), border_radius=2)
                txt = self.font_small.render(alert_text, True, alert_color)
                self.pi_surface.blit(txt, (alerts_x + 20, alert_y + 10))
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
                pygame.draw.rect(self.pi_surface, COLOR_BG_ELEVATED,
                               (alerts_x + 10, check_y, alerts_w - 20, 38), border_radius=6)
                symbol = "✓" if ok else "!"
                txt = self.font_small.render(f"{symbol}  {label}", True, color)
                self.pi_surface.blit(txt, (alerts_x + 20, check_y + 10))
                check_y += 45

    def render_pi_rpm_speed(self):
        TOP = 55  # Below title bar
        
        # Left side: Big RPM gauge with modern styling
        gauge_cx, gauge_cy = 220, 275
        gauge_r = 160
        
        # Outer glow ring
        pygame.draw.circle(self.pi_surface, COLOR_BG_CARD, (gauge_cx, gauge_cy), gauge_r + 12)
        pygame.draw.circle(self.pi_surface, COLOR_BG, (gauge_cx, gauge_cy), gauge_r - 5)
        
        # RPM arc background
        self.draw_arc(self.pi_surface, gauge_cx, gauge_cy, gauge_r, 24, 135, 405, COLOR_DARK_GRAY)
        
        # RPM arc fill
        rpm_pct = self.telemetry.rpm / self.settings.redline_rpm
        rpm_angle = min(270, rpm_pct * 270)
        rpm_color = self.get_rpm_color(self.telemetry.rpm)
        self.draw_arc(self.pi_surface, gauge_cx, gauge_cy, gauge_r, 24, 135, 135 + rpm_angle, rpm_color)
        
        # Shift light indicator with glow
        if self.telemetry.rpm >= self.settings.shift_rpm:
            glow = pygame.Surface((40, 40), pygame.SRCALPHA)
            pygame.draw.circle(glow, (255, 70, 85, 100), (20, 20), 18)
            self.pi_surface.blit(glow, (gauge_cx - 20, gauge_cy - gauge_r - 40))
            pygame.draw.circle(self.pi_surface, COLOR_RED, (gauge_cx, gauge_cy - gauge_r - 20), 14)
        
        # Center circle with gear
        pygame.draw.circle(self.pi_surface, COLOR_BG_CARD, (gauge_cx, gauge_cy), 70)
        
        # Gear glow
        gear = "N" if self.telemetry.gear == 0 else str(self.telemetry.gear)
        glow = pygame.Surface((80, 80), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*rpm_color[:3], 40), (40, 40), 35)
        self.pi_surface.blit(glow, (gauge_cx - 40, gauge_cy - 50))
        
        txt = self.pi_font_large.render(gear, True, rpm_color)
        self.pi_surface.blit(txt, txt.get_rect(center=(gauge_cx, gauge_cy - 10)))
        
        # RPM digits
        txt = self.font_small.render(f"{self.telemetry.rpm} RPM", True, COLOR_GRAY)
        self.pi_surface.blit(txt, txt.get_rect(center=(gauge_cx, gauge_cy + 35)))
        
        # Right side panel
        right_x = 440
        
        # Speed card
        pygame.draw.rect(self.pi_surface, COLOR_BG_CARD, (right_x, TOP, 340, 150), border_radius=14)
        
        speed = self.telemetry.speed_kmh
        if self.settings.use_mph:
            speed = int(speed * 0.621371)
        
        txt = self.pi_font_huge.render(str(speed), True, COLOR_WHITE)
        self.pi_surface.blit(txt, txt.get_rect(center=(right_x + 170, TOP + 60)))
        
        unit = "MPH" if self.settings.use_mph else "KMH"
        txt = self.font_medium.render(unit, True, COLOR_GRAY)
        self.pi_surface.blit(txt, txt.get_rect(center=(right_x + 170, TOP + 120)))
        
        # Throttle/Brake cards
        pygame.draw.rect(self.pi_surface, COLOR_BG_CARD, (right_x, TOP + 165, 165, 80), border_radius=12)
        txt = self.font_tiny.render("THROTTLE", True, COLOR_GRAY)
        self.pi_surface.blit(txt, (right_x + 15, TOP + 172))
        pygame.draw.rect(self.pi_surface, COLOR_DARK_GRAY, (right_x + 15, TOP + 195, 135, 14), border_radius=7)
        throttle_w = int(135 * self.telemetry.throttle_percent / 100)
        pygame.draw.rect(self.pi_surface, COLOR_GREEN, (right_x + 15, TOP + 195, throttle_w, 14), border_radius=7)
        txt = self.font_small.render(f"{self.telemetry.throttle_percent}%", True, COLOR_GREEN)
        self.pi_surface.blit(txt, (right_x + 15, TOP + 215))
        
        pygame.draw.rect(self.pi_surface, COLOR_BG_CARD, (right_x + 175, TOP + 165, 165, 80), border_radius=12)
        txt = self.font_tiny.render("BRAKE", True, COLOR_GRAY)
        self.pi_surface.blit(txt, (right_x + 190, TOP + 172))
        pygame.draw.rect(self.pi_surface, COLOR_DARK_GRAY, (right_x + 190, TOP + 195, 135, 14), border_radius=7)
        brake_w = int(135 * self.telemetry.brake_percent / 100)
        pygame.draw.rect(self.pi_surface, COLOR_RED, (right_x + 190, TOP + 195, brake_w, 14), border_radius=7)
        txt = self.font_small.render(f"{self.telemetry.brake_percent}%", True, COLOR_RED)
        self.pi_surface.blit(txt, (right_x + 190, TOP + 215))
        
        # Lap times card
        pygame.draw.rect(self.pi_surface, COLOR_BG_CARD, (right_x, TOP + 260, 340, 90), border_radius=12)
        
        lap_ms = self.telemetry.lap_time_ms
        lap_min = lap_ms // 60000
        lap_sec = (lap_ms % 60000) / 1000
        
        txt = self.font_tiny.render("CURRENT LAP", True, COLOR_GRAY)
        self.pi_surface.blit(txt, (right_x + 20, TOP + 270))
        txt = self.pi_font_medium.render(f"{lap_min}:{lap_sec:05.2f}", True, COLOR_WHITE)
        self.pi_surface.blit(txt, (right_x + 20, TOP + 290))
        
        best_ms = self.telemetry.best_lap_ms
        best_min = best_ms // 60000
        best_sec = (best_ms % 60000) / 1000
        
        txt = self.font_tiny.render("BEST", True, COLOR_GRAY)
        self.pi_surface.blit(txt, (right_x + 220, TOP + 270))
        txt = self.font_medium.render(f"{best_min}:{best_sec:05.2f}", True, COLOR_PURPLE)
        self.pi_surface.blit(txt, (right_x + 190, TOP + 295))
    
    def render_pi_tpms(self):
        TOP = 55  # Below title bar
        
        # Car outline in center (modern) - adjusted to fit below title bar
        car_cx, car_cy = PI_WIDTH // 2, TOP + (PI_HEIGHT - TOP) // 2
        car_w, car_h = 150, 250
        
        pygame.draw.rect(self.pi_surface, COLOR_BG_CARD, 
                        (car_cx - car_w//2, car_cy - car_h//2, car_w, car_h), 
                        border_radius=22)
        pygame.draw.rect(self.pi_surface, COLOR_DARK_GRAY, 
                        (car_cx - car_w//2, car_cy - car_h//2, car_w, car_h), 
                        2, border_radius=22)
        
        # Tire cards (modern style) - compact to fit
        positions = [
            (car_cx - 165, car_cy - 75, "FL", 0),
            (car_cx + 165, car_cy - 75, "FR", 1),
            (car_cx - 165, car_cy + 75, "RL", 2),
            (car_cx + 165, car_cy + 75, "RR", 3),
        ]
        
        for x, y, label, idx in positions:
            psi = self.telemetry.tire_pressure[idx]
            temp = self.telemetry.tire_temp[idx]
            
            if psi < self.settings.tire_low_psi:
                color = COLOR_RED
            elif psi > self.settings.tire_high_psi:
                color = COLOR_YELLOW
            else:
                color = COLOR_GREEN
            
            # Modern card - compact
            box_w, box_h = 125, 95
            pygame.draw.rect(self.pi_surface, COLOR_BG_CARD,
                           (x - box_w//2, y - box_h//2, box_w, box_h), border_radius=14)
            
            # Color accent bar
            pygame.draw.rect(self.pi_surface, color,
                           (x - box_w//2, y - box_h//2, 5, box_h), 
                           border_top_left_radius=14, border_bottom_left_radius=14)
            
            # Label
            txt = self.font_small.render(label, True, COLOR_GRAY)
            self.pi_surface.blit(txt, txt.get_rect(center=(x + 5, y - 28)))
            
            # PSI (large)
            txt = self.pi_font_medium.render(f"{psi:.1f}", True, color)
            self.pi_surface.blit(txt, txt.get_rect(center=(x + 5, y + 5)))
            
            # PSI label + Temp on same line
            txt = self.font_tiny.render(f"PSI  |  {temp:.0f}°F", True, COLOR_GRAY)
            self.pi_surface.blit(txt, txt.get_rect(center=(x + 5, y + 35)))
    
    def render_pi_engine(self):
        TOP = 55  # Below title bar
        row1_y = TOP + 110
        row2_y = TOP + 290
        
        # Row 1: Coolant, Oil Temp, Oil Pressure
        self.render_pi_gauge(150, row1_y, "COOLANT", self.telemetry.coolant_temp_f, "°F",
                            180, self.settings.coolant_warn_f, 250)
        self.render_pi_gauge(400, row1_y, "OIL TEMP", self.telemetry.oil_temp_f, "°F",
                            150, self.settings.oil_warn_f, 280)
        self.render_pi_gauge(650, row1_y, "OIL PSI", self.telemetry.oil_pressure_psi, "",
                            0, 30, 80)
        
        # Row 2: Fuel, Voltage, Intake Temp
        fuel = self.telemetry.fuel_level_percent
        fuel_color = COLOR_RED if fuel < 15 else (COLOR_YELLOW if fuel < 25 else COLOR_GREEN)
        self.render_pi_gauge_bar(150, row2_y, "FUEL", fuel, "%", fuel_color)
        
        self.render_pi_gauge(400, row2_y, "VOLTAGE", self.telemetry.voltage, "V",
                            11, 13.5, 15)
        self.render_pi_gauge(650, row2_y, "INTAKE", self.telemetry.intake_temp_f, "°F",
                            50, 120, 180)
    
    def render_pi_gforce(self):
        TOP = 55  # Below title bar
        
        # Big G-ball on left with modern styling
        ball_cx, ball_cy = 230, TOP + 180
        ball_r = 155
        
        # Outer glow
        pygame.draw.circle(self.pi_surface, COLOR_BG_CARD, (ball_cx, ball_cy), ball_r + 8)
        pygame.draw.circle(self.pi_surface, COLOR_BG, (ball_cx, ball_cy), ball_r)
        
        # Grid circles
        for g in [0.5, 1.0, 1.5]:
            r = int(g * 85)
            pygame.draw.circle(self.pi_surface, COLOR_DARK_GRAY, (ball_cx, ball_cy), r, 1)
        
        # Crosshairs
        pygame.draw.line(self.pi_surface, COLOR_DARK_GRAY,
                        (ball_cx - ball_r, ball_cy), (ball_cx + ball_r, ball_cy), 1)
        pygame.draw.line(self.pi_surface, COLOR_DARK_GRAY,
                        (ball_cx, ball_cy - ball_r), (ball_cx, ball_cy + ball_r), 1)
        
        # G labels
        for g in [0.5, 1.0, 1.5]:
            r = int(g * 85)
            txt = self.font_tiny.render(f"{g}", True, COLOR_DARK_GRAY)
            self.pi_surface.blit(txt, (ball_cx + r + 5, ball_cy - 8))
        
        # G-ball - negate lateral so ball moves in direction of turn
        g_scale = 85
        gx = ball_cx - int(self.telemetry.g_lateral * g_scale)
        gy = ball_cy - int(self.telemetry.g_longitudinal * g_scale)
        
        # Clamp
        dx, dy = gx - ball_cx, gy - ball_cy
        dist = math.sqrt(dx*dx + dy*dy)
        if dist > ball_r - 16:
            scale = (ball_r - 16) / dist
            gx = ball_cx + int(dx * scale)
            gy = ball_cy + int(dy * scale)
        
        # G-ball with glow
        glow = pygame.Surface((50, 50), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*COLOR_ACCENT[:3], 100), (25, 25), 20)
        self.pi_surface.blit(glow, (gx - 25, gy - 25))
        
        pygame.draw.circle(self.pi_surface, COLOR_ACCENT, (gx, gy), 15)
        pygame.draw.circle(self.pi_surface, COLOR_WHITE, (gx, gy), 15, 2)
        
        # Right panel with modern cards
        right_x = 440
        card_w = 340
        card_h = 95
        
        # Lateral card
        pygame.draw.rect(self.pi_surface, COLOR_BG_CARD, (right_x, TOP, card_w, card_h), border_radius=14)
        pygame.draw.rect(self.pi_surface, COLOR_CYAN, (right_x, TOP, 5, card_h), 
                        border_top_left_radius=14, border_bottom_left_radius=14)
        txt = self.font_small.render("LATERAL", True, COLOR_GRAY)
        self.pi_surface.blit(txt, (right_x + 20, TOP + 12))
        txt = self.pi_font_large.render(f"{self.telemetry.g_lateral:+.2f}G", True, COLOR_CYAN)
        self.pi_surface.blit(txt, (right_x + 20, TOP + 40))
        
        # Longitudinal card
        pygame.draw.rect(self.pi_surface, COLOR_BG_CARD, (right_x, TOP + card_h + 15, card_w, card_h), border_radius=14)
        pygame.draw.rect(self.pi_surface, COLOR_PURPLE, (right_x, TOP + card_h + 15, 5, card_h), 
                        border_top_left_radius=14, border_bottom_left_radius=14)
        txt = self.font_small.render("LONGITUDINAL", True, COLOR_GRAY)
        self.pi_surface.blit(txt, (right_x + 20, TOP + card_h + 27))
        txt = self.pi_font_large.render(f"{self.telemetry.g_longitudinal:+.2f}G", True, COLOR_PURPLE)
        self.pi_surface.blit(txt, (right_x + 20, TOP + card_h + 55))
        
        # Combined card
        combined = math.sqrt(self.telemetry.g_lateral**2 + self.telemetry.g_longitudinal**2)
        pygame.draw.rect(self.pi_surface, COLOR_BG_CARD, (right_x, TOP + 2*(card_h + 15), card_w, card_h), border_radius=14)
        pygame.draw.rect(self.pi_surface, COLOR_ACCENT, (right_x, TOP + 2*(card_h + 15), 5, card_h), 
                        border_top_left_radius=14, border_bottom_left_radius=14)
        txt = self.font_small.render("COMBINED", True, COLOR_GRAY)
        self.pi_surface.blit(txt, (right_x + 20, TOP + 2*(card_h + 15) + 12))
        txt = self.pi_font_large.render(f"{combined:.2f}G", True, COLOR_ACCENT)
        self.pi_surface.blit(txt, (right_x + 20, TOP + 2*(card_h + 15) + 40))
        
        # IMU source note
        txt = self.font_tiny.render("Source: QMI8658 IMU", True, COLOR_DARK_GRAY)
        self.pi_surface.blit(txt, txt.get_rect(center=(ball_cx, PI_HEIGHT - 15)))
    
    def render_pi_settings(self):
        TOP = 55  # Below title bar
        
        items = self.get_settings_items()
        item_h = 50
        
        for i, (name, value, unit) in enumerate(items):
            y = TOP + i * item_h
            is_selected = i == self.settings_selection
            
            # Card background
            bg_color = COLOR_BG_ELEVATED if is_selected else COLOR_BG_CARD
            pygame.draw.rect(self.pi_surface, bg_color, (40, y, PI_WIDTH - 80, item_h - 5), border_radius=10)
            
            # Selection indicator
            if is_selected:
                pygame.draw.rect(self.pi_surface, COLOR_ACCENT, 
                               (40, y, 5, item_h - 5), 
                               border_top_left_radius=10, border_bottom_left_radius=10)
                if self.settings_edit_mode:
                    pygame.draw.rect(self.pi_surface, COLOR_ACCENT, 
                                   (40, y, PI_WIDTH - 80, item_h - 5), 2, border_radius=10)
            
            # Name
            color = COLOR_WHITE if is_selected else COLOR_GRAY
            txt = self.font_small.render(name, True, color)
            self.pi_surface.blit(txt, (60, y + 12))
            
            # Value
            if value != "":
                val_color = COLOR_ACCENT if is_selected else COLOR_WHITE
                txt = self.font_small.render(f"{value}{unit}", True, val_color)
                self.pi_surface.blit(txt, (PI_WIDTH - 60 - txt.get_width(), y + 12))
            
            # Edit hint
            if is_selected and name != "Back":
                hint = "← VOL+/VOL- to adjust →" if self.settings_edit_mode else "Press ON/OFF to edit"
                txt = self.font_tiny.render(hint, True, COLOR_DARK_GRAY)
                self.pi_surface.blit(txt, txt.get_rect(center=(PI_WIDTH // 2, PI_HEIGHT - 15)))
    
    # -------------------------------------------------------------------------
    # PI HELPERS
    # -------------------------------------------------------------------------
    
    def render_pi_bar(self, x, y, w, h, label, value, max_val, color):
        """Render a horizontal bar with label"""
        txt = self.font_tiny.render(label, True, COLOR_GRAY)
        self.pi_surface.blit(txt, (x, y - 20))
        
        pygame.draw.rect(self.pi_surface, COLOR_DARK_GRAY, (x, y, w, h), border_radius=4)
        fill_w = int(w * value / max_val)
        if fill_w > 0:
            pygame.draw.rect(self.pi_surface, color, (x, y, fill_w, h), border_radius=4)
        
        txt = self.font_small.render(f"{int(value)}%", True, COLOR_WHITE)
        self.pi_surface.blit(txt, (x + w + 10, y))
    
    def render_pi_gauge(self, cx, cy, label, value, unit, min_v, warn_v, max_v):
        """Render a circular gauge"""
        r = 70
        
        # Background
        pygame.draw.circle(self.pi_surface, (25, 25, 35), (cx, cy), r)
        
        # Determine color
        if value < warn_v:
            color = COLOR_GREEN
        elif value < max_v * 0.9:
            color = COLOR_YELLOW
        else:
            color = COLOR_RED
        
        # Arc
        pct = (value - min_v) / (max_v - min_v)
        pct = max(0, min(1, pct))
        self.draw_arc(self.pi_surface, cx, cy, r - 5, 10, 135, 135 + pct * 270, color)
        
        # Value
        txt = self.font_medium.render(f"{value:.1f}" if isinstance(value, float) else str(int(value)), True, color)
        self.pi_surface.blit(txt, txt.get_rect(center=(cx, cy)))
        
        # Label
        txt = self.font_tiny.render(label, True, COLOR_GRAY)
        self.pi_surface.blit(txt, txt.get_rect(center=(cx, cy - r - 15)))
        
        # Unit
        if unit:
            txt = self.font_tiny.render(unit, True, COLOR_GRAY)
            self.pi_surface.blit(txt, txt.get_rect(center=(cx, cy + 25)))
    
    def render_pi_gauge_bar(self, cx, cy, label, value, unit, color):
        """Render a vertical bar gauge"""
        bar_w, bar_h = 80, 120
        
        # Label
        txt = self.font_tiny.render(label, True, COLOR_GRAY)
        self.pi_surface.blit(txt, txt.get_rect(center=(cx, cy - bar_h//2 - 20)))
        
        # Background
        pygame.draw.rect(self.pi_surface, COLOR_DARK_GRAY, 
                        (cx - bar_w//2, cy - bar_h//2, bar_w, bar_h), border_radius=5)
        
        # Fill
        fill_h = int(bar_h * value / 100)
        if fill_h > 0:
            pygame.draw.rect(self.pi_surface, color,
                           (cx - bar_w//2, cy + bar_h//2 - fill_h, bar_w, fill_h), border_radius=5)
        
        # Value
        txt = self.font_medium.render(f"{int(value)}{unit}", True, COLOR_WHITE)
        self.pi_surface.blit(txt, txt.get_rect(center=(cx, cy)))
    
    # -------------------------------------------------------------------------
    # CONTROL PANEL
    # -------------------------------------------------------------------------
    
    def render_control_panel(self, x, y):
        # Title
        txt = self.font_small.render("SWC Controls", True, COLOR_WHITE)
        self.window.blit(txt, (x, y))
        
        # Current screen
        txt = self.font_tiny.render(f"Screen: {SCREEN_NAMES[self.current_screen]}", True, COLOR_ACCENT)
        self.window.blit(txt, (x, y + 30))
        
        # Buttons
        buttons = [
            ("↑/W", "RES+", ButtonEvent.RES_PLUS),
            ("↓/S", "SET-", ButtonEvent.SET_MINUS),
            ("→/D", "VOL+", ButtonEvent.VOL_UP),
            ("←/A", "VOL-", ButtonEvent.VOL_DOWN),
            ("Enter", "ON/OFF", ButtonEvent.ON_OFF),
            ("Esc/B", "CANCEL", ButtonEvent.CANCEL),
        ]
        
        by = y + 60
        for key, name, btn in buttons:
            is_active = (btn == self.last_button and 
                        pygame.time.get_ticks() - self.button_time < 400)
            
            bg = COLOR_YELLOW if is_active else COLOR_DARK_GRAY
            fg = (0, 0, 0) if is_active else COLOR_WHITE
            
            pygame.draw.rect(self.window, bg, (x, by, 65, 22), border_radius=3)
            txt = self.font_tiny.render(key, True, fg)
            self.window.blit(txt, (x + 5, by + 3))
            
            txt = self.font_tiny.render(name, True, COLOR_GRAY)
            self.window.blit(txt, (x + 75, by + 3))
            
            by += 28
        
        # Separator
        by += 10
        pygame.draw.line(self.window, COLOR_DARK_GRAY, (x, by), (x + 180, by), 1)
        by += 15
        
        # Special keys
        txt = self.font_tiny.render("Space = Sleep", True, COLOR_DARK_GRAY)
        self.window.blit(txt, (x, by))
        by += 20
        txt = self.font_tiny.render("Tab = Demo Mode", True, COLOR_DARK_GRAY)
        self.window.blit(txt, (x, by))
        
        # Status
        by += 35
        demo_txt = f"Demo: {'ON' if self.demo_mode else 'OFF'}"
        demo_color = COLOR_GREEN if self.demo_mode else COLOR_GRAY
        self.window.blit(self.font_tiny.render(demo_txt, True, demo_color), (x, by))
        
        by += 22
        self.window.blit(self.font_tiny.render("Screens synced", True, COLOR_ACCENT), (x, by))
    
    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------
    
    def get_rpm_color(self, rpm: int):
        if rpm < 2000: return COLOR_BLUE
        if rpm < 3500: return COLOR_GREEN
        if rpm < 5000: return COLOR_YELLOW
        if rpm < 6000: return COLOR_ORANGE
        return COLOR_RED
    
    def get_alerts(self):
        """Check telemetry values and return list of (alert_text, color) tuples"""
        alerts = []
        
        # Tire pressure alerts (check each tire)
        tire_names = ['FL', 'FR', 'RL', 'RR']
        for i, name in enumerate(tire_names):
            psi = self.telemetry.tire_pressure[i]
            if psi < self.settings.tire_low_psi:
                alerts.append((f"LOW TIRE {name}: {psi:.0f} PSI", COLOR_RED))
            elif psi > self.settings.tire_high_psi:
                alerts.append((f"HIGH TIRE {name}: {psi:.0f} PSI", COLOR_YELLOW))
        
        # Coolant temperature
        if self.telemetry.coolant_temp_f >= self.settings.coolant_warn_f:
            alerts.append((f"COOLANT HIGH: {self.telemetry.coolant_temp_f:.0f}°F", COLOR_RED))
        
        # Oil temperature
        if self.telemetry.oil_temp_f >= self.settings.oil_warn_f:
            alerts.append((f"OIL TEMP HIGH: {self.telemetry.oil_temp_f:.0f}°F", COLOR_RED))
        
        # Fuel level
        if self.telemetry.fuel_level_percent < 15:
            alerts.append((f"LOW FUEL: {self.telemetry.fuel_level_percent:.0f}%", COLOR_YELLOW))
        
        # Voltage
        if self.telemetry.voltage < 12.0:
            alerts.append((f"LOW VOLTAGE: {self.telemetry.voltage:.1f}V", COLOR_RED))
        elif self.telemetry.voltage < 12.5:
            alerts.append((f"VOLTAGE WARN: {self.telemetry.voltage:.1f}V", COLOR_YELLOW))
        
        return alerts
    
    def draw_arc(self, surface, cx, cy, radius, thickness, start_angle, end_angle, color):
        """Draw an arc using pixel plotting"""
        for angle in range(int(start_angle), int(end_angle) + 1, 2):
            rad = math.radians(angle)
            for r in range(radius - thickness//2, radius + thickness//2):
                px = cx + int(r * math.cos(rad))
                py = cy + int(r * math.sin(rad))
                if 0 <= px < surface.get_width() and 0 <= py < surface.get_height():
                    surface.set_at((px, py), color)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("MX5 Telemetry - Combined UI Simulator")
    print("=" * 60)
    print()
    print("BOTH displays show the SAME screen - synchronized!")
    print()
    print("Screens: Overview → RPM/Speed → TPMS → Engine → G-Force → Settings")
    print()
    print("Navigation:")
    print("  ↑ / W     = Previous screen (RES+)")
    print("  ↓ / S     = Next screen (SET-)")
    print("  → / D     = Increase value (VOL+)")
    print("  ← / A     = Decrease value (VOL-)")
    print("  Enter     = Select / Edit (ON/OFF)")
    print("  Esc / B   = Back / Exit (CANCEL)")
    print()
    print("Special:")
    print("  Space     = Toggle sleep mode")
    print("  Tab       = Toggle demo mode")
    print()
    print("=" * 60)
    
    sim = CombinedSimulator()
    sim.run()
