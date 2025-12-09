#!/usr/bin/env python3
"""
Combined MX5 Telemetry UI Simulator

Shows both ESP32-S3 round display and Raspberry Pi display side by side.
BOTH displays show the SAME screen and are controlled SIMULTANEOUSLY.

The ESP32 shows a compact view, while the Pi shows extended info.

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

# Colors
COLOR_BG = (20, 20, 30)
COLOR_BG_DARK = (15, 15, 20)
COLOR_WHITE = (255, 255, 255)
COLOR_GRAY = (128, 128, 128)
COLOR_DARK_GRAY = (64, 64, 64)
COLOR_RED = (255, 60, 60)
COLOR_GREEN = (60, 255, 60)
COLOR_BLUE = (60, 120, 255)
COLOR_YELLOW = (255, 255, 60)
COLOR_ORANGE = (255, 165, 0)
COLOR_CYAN = (0, 255, 255)
COLOR_ACCENT = (0, 150, 255)
COLOR_PURPLE = (180, 100, 255)

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
        """Overview screen - Gear + key alerts + mini TPMS"""
        center = ESP32_SIZE // 2
        
        # Get any alerts
        alerts = self.get_alerts()
        
        # Big gear in center-top
        gear = "N" if self.telemetry.gear == 0 else str(self.telemetry.gear)
        rpm_color = self.get_rpm_color(self.telemetry.rpm)
        gear_txt = self.font_huge.render(gear, True, rpm_color)
        self.esp32_surface.blit(gear_txt, gear_txt.get_rect(center=(center, 70)))
        
        # Speed below gear
        speed = self.telemetry.speed_kmh
        if self.settings.use_mph:
            speed = int(speed * 0.621371)
        unit = "MPH" if self.settings.use_mph else "KMH"
        speed_txt = self.font_medium.render(f"{speed} {unit}", True, COLOR_WHITE)
        self.esp32_surface.blit(speed_txt, speed_txt.get_rect(center=(center, 120)))
        
        # Mini TPMS (4 small boxes)
        tire_y = 165
        tire_size = 45
        positions = [(center - 55, tire_y), (center + 55, tire_y),
                     (center - 55, tire_y + 55), (center + 55, tire_y + 55)]
        
        for i, (x, y) in enumerate(positions):
            psi = self.telemetry.tire_pressure[i]
            if psi < self.settings.tire_low_psi:
                color = COLOR_RED
            elif psi > self.settings.tire_high_psi:
                color = COLOR_YELLOW
            else:
                color = COLOR_GREEN
            
            pygame.draw.rect(self.esp32_surface, color, 
                           (x - tire_size//2, y - 15, tire_size, 30), 2, border_radius=4)
            txt = self.font_tiny.render(f"{psi:.0f}", True, color)
            self.esp32_surface.blit(txt, txt.get_rect(center=(x, y)))
        
        # Alert section at bottom
        alert_y = 280
        if alerts:
            # Show first alert (most critical)
            alert_txt, alert_color = alerts[0]
            pygame.draw.rect(self.esp32_surface, alert_color, 
                           (30, alert_y - 5, ESP32_SIZE - 60, 28), border_radius=5)
            txt = self.font_tiny.render(alert_txt, True, (0, 0, 0))
            self.esp32_surface.blit(txt, txt.get_rect(center=(center, alert_y + 8)))
            
            # Alert count if more
            if len(alerts) > 1:
                count_txt = self.font_tiny.render(f"+{len(alerts)-1} more", True, COLOR_YELLOW)
                self.esp32_surface.blit(count_txt, count_txt.get_rect(center=(center, alert_y + 30)))
        else:
            txt = self.font_tiny.render("ALL SYSTEMS OK", True, COLOR_GREEN)
            self.esp32_surface.blit(txt, txt.get_rect(center=(center, alert_y + 8)))
    
    def render_esp32_rpm_speed(self):
        center = ESP32_SIZE // 2
        
        # RPM arc
        radius = 145
        thickness = 16
        self.draw_arc(self.esp32_surface, center, center, radius, thickness, 135, 405, COLOR_DARK_GRAY)
        
        rpm_pct = self.telemetry.rpm / self.settings.redline_rpm
        rpm_angle = min(270, max(0, rpm_pct * 270))
        rpm_color = self.get_rpm_color(self.telemetry.rpm)
        self.draw_arc(self.esp32_surface, center, center, radius, thickness, 135, 135 + rpm_angle, rpm_color)
        
        # Gear in center
        gear = "N" if self.telemetry.gear == 0 else str(self.telemetry.gear)
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
        
        # RPM digits at top
        rpm_txt = self.font_small.render(f"{self.telemetry.rpm}", True, rpm_color)
        self.esp32_surface.blit(rpm_txt, rpm_txt.get_rect(center=(center, 45)))
    
    def render_esp32_tpms(self):
        center = ESP32_SIZE // 2
        
        # Title
        txt = self.font_small.render("TPMS", True, COLOR_WHITE)
        self.esp32_surface.blit(txt, txt.get_rect(center=(center, 40)))
        
        # 4 tire positions (car outline style)
        positions = [(center - 60, center - 40), (center + 60, center - 40),
                     (center - 60, center + 60), (center + 60, center + 60)]
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
            
            # Tire box
            pygame.draw.rect(self.esp32_surface, COLOR_DARK_GRAY, (x - 35, y - 25, 70, 50), border_radius=5)
            pygame.draw.rect(self.esp32_surface, color, (x - 35, y - 25, 70, 50), 2, border_radius=5)
            
            # PSI
            psi_txt = self.font_small.render(f"{psi:.1f}", True, color)
            self.esp32_surface.blit(psi_txt, psi_txt.get_rect(center=(x, y - 5)))
            
            # Label
            lbl = self.font_tiny.render(labels[i], True, COLOR_GRAY)
            self.esp32_surface.blit(lbl, lbl.get_rect(center=(x, y + 15)))
    
    def render_esp32_engine(self):
        center = ESP32_SIZE // 2
        
        # Title
        txt = self.font_small.render("ENGINE", True, COLOR_WHITE)
        self.esp32_surface.blit(txt, txt.get_rect(center=(center, 40)))
        
        # Coolant temp (left)
        coolant = self.telemetry.coolant_temp_f
        cool_color = COLOR_RED if coolant > self.settings.coolant_warn_f else COLOR_GREEN
        
        txt = self.font_tiny.render("COOLANT", True, COLOR_GRAY)
        self.esp32_surface.blit(txt, txt.get_rect(center=(center - 70, 80)))
        txt = self.font_medium.render(f"{coolant}°", True, cool_color)
        self.esp32_surface.blit(txt, txt.get_rect(center=(center - 70, 115)))
        
        # Oil temp (right)
        oil = self.telemetry.oil_temp_f
        oil_color = COLOR_RED if oil > self.settings.oil_warn_f else COLOR_GREEN
        
        txt = self.font_tiny.render("OIL", True, COLOR_GRAY)
        self.esp32_surface.blit(txt, txt.get_rect(center=(center + 70, 80)))
        txt = self.font_medium.render(f"{oil}°", True, oil_color)
        self.esp32_surface.blit(txt, txt.get_rect(center=(center + 70, 115)))
        
        # Fuel gauge (center bottom)
        fuel = self.telemetry.fuel_level_percent
        fuel_color = COLOR_RED if fuel < 15 else COLOR_WHITE
        
        txt = self.font_tiny.render("FUEL", True, COLOR_GRAY)
        self.esp32_surface.blit(txt, txt.get_rect(center=(center, 180)))
        txt = self.font_large.render(f"{int(fuel)}%", True, fuel_color)
        self.esp32_surface.blit(txt, txt.get_rect(center=(center, 220)))
        
        # Fuel bar
        bar_w = 120
        bar_h = 12
        bar_x = center - bar_w // 2
        bar_y = 250
        pygame.draw.rect(self.esp32_surface, COLOR_DARK_GRAY, (bar_x, bar_y, bar_w, bar_h), border_radius=3)
        fill_w = int(bar_w * fuel / 100)
        pygame.draw.rect(self.esp32_surface, fuel_color, (bar_x, bar_y, fill_w, bar_h), border_radius=3)
    
    def render_esp32_gforce(self):
        center = ESP32_SIZE // 2
        
        # Title
        txt = self.font_small.render("G-FORCE", True, COLOR_WHITE)
        self.esp32_surface.blit(txt, txt.get_rect(center=(center, 40)))
        
        # G-ball background
        ball_center = (center, center + 20)
        ball_radius = 100
        pygame.draw.circle(self.esp32_surface, COLOR_DARK_GRAY, ball_center, ball_radius)
        pygame.draw.circle(self.esp32_surface, COLOR_GRAY, ball_center, ball_radius, 1)
        
        # Crosshairs
        pygame.draw.line(self.esp32_surface, COLOR_GRAY, 
                        (ball_center[0] - ball_radius, ball_center[1]),
                        (ball_center[0] + ball_radius, ball_center[1]), 1)
        pygame.draw.line(self.esp32_surface, COLOR_GRAY,
                        (ball_center[0], ball_center[1] - ball_radius),
                        (ball_center[0], ball_center[1] + ball_radius), 1)
        
        # G-ball position
        g_scale = 60  # pixels per G
        gx = ball_center[0] + int(self.telemetry.g_lateral * g_scale)
        gy = ball_center[1] - int(self.telemetry.g_longitudinal * g_scale)
        
        # Clamp to circle
        dx, dy = gx - ball_center[0], gy - ball_center[1]
        dist = math.sqrt(dx*dx + dy*dy)
        if dist > ball_radius - 10:
            scale = (ball_radius - 10) / dist
            gx = ball_center[0] + int(dx * scale)
            gy = ball_center[1] + int(dy * scale)
        
        pygame.draw.circle(self.esp32_surface, COLOR_ACCENT, (gx, gy), 12)
        pygame.draw.circle(self.esp32_surface, COLOR_WHITE, (gx, gy), 12, 2)
        
        # G values
        txt = self.font_tiny.render(f"LAT: {self.telemetry.g_lateral:+.2f}G", True, COLOR_WHITE)
        self.esp32_surface.blit(txt, txt.get_rect(center=(center, ESP32_SIZE - 60)))
        txt = self.font_tiny.render(f"LON: {self.telemetry.g_longitudinal:+.2f}G", True, COLOR_WHITE)
        self.esp32_surface.blit(txt, txt.get_rect(center=(center, ESP32_SIZE - 40)))
    
    def render_esp32_settings(self):
        center = ESP32_SIZE // 2
        
        # Title
        txt = self.font_small.render("SETTINGS", True, COLOR_WHITE)
        self.esp32_surface.blit(txt, txt.get_rect(center=(center, 40)))
        
        items = self.get_settings_items()
        start_y = 75
        
        for i, (name, value, unit) in enumerate(items):
            y = start_y + i * 38
            
            # Highlight selected
            if i == self.settings_selection:
                pygame.draw.rect(self.esp32_surface, (40, 40, 60), 
                               (30, y - 5, ESP32_SIZE - 60, 32), border_radius=5)
                if self.settings_edit_mode:
                    pygame.draw.rect(self.esp32_surface, COLOR_ACCENT,
                                   (30, y - 5, ESP32_SIZE - 60, 32), 2, border_radius=5)
            
            color = COLOR_WHITE if i == self.settings_selection else COLOR_GRAY
            
            # Name on left
            txt = self.font_tiny.render(name, True, color)
            self.esp32_surface.blit(txt, (45, y))
            
            # Value on right
            if value != "":
                val_str = f"{value}{unit}"
                txt = self.font_tiny.render(val_str, True, COLOR_ACCENT if i == self.settings_selection else COLOR_WHITE)
                self.esp32_surface.blit(txt, (ESP32_SIZE - 45 - txt.get_width(), y))
    
    # -------------------------------------------------------------------------
    # PI SCREENS (Detailed)
    # -------------------------------------------------------------------------
    
    def render_pi_overview(self):
        """Overview screen with gear, TPMS, key engine data, and alerts"""
        alerts = self.get_alerts()
        
        # Left column: Gear + Speed + Key Info
        left_x = 50
        
        # Gear (large)
        rpm_color = self.get_rpm_color(self.telemetry.rpm)
        gear = "N" if self.telemetry.gear == 0 else str(self.telemetry.gear)
        txt = self.pi_font_huge.render(gear, True, rpm_color)
        self.pi_surface.blit(txt, txt.get_rect(center=(left_x + 80, 100)))
        
        # Speed below gear (convert based on setting)
        speed = self.telemetry.speed_kmh
        if self.settings.use_mph:
            speed = int(speed * 0.621371)
        unit = "MPH" if self.settings.use_mph else "KMH"
        txt = self.pi_font_large.render(f"{speed:.0f}", True, COLOR_WHITE)
        self.pi_surface.blit(txt, txt.get_rect(center=(left_x + 80, 180)))
        txt = self.font_small.render(unit, True, COLOR_GRAY)
        self.pi_surface.blit(txt, txt.get_rect(center=(left_x + 80, 210)))
        
        # RPM bar under speed
        rpm_pct = min(1.0, self.telemetry.rpm / self.settings.redline_rpm)
        bar_y = 240
        pygame.draw.rect(self.pi_surface, COLOR_DARK_GRAY, (left_x, bar_y, 160, 20), border_radius=5)
        pygame.draw.rect(self.pi_surface, rpm_color, (left_x, bar_y, int(160 * rpm_pct), 20), border_radius=5)
        txt = self.font_tiny.render(f"{self.telemetry.rpm} RPM", True, COLOR_WHITE)
        self.pi_surface.blit(txt, txt.get_rect(center=(left_x + 80, bar_y + 10)))
        
        # Key values (coolant, oil, fuel, voltage)
        values_y = 280
        value_h = 40
        values = [
            ("COOLANT", f"{self.telemetry.coolant_temp_f:.0f}°F", 
             COLOR_RED if self.telemetry.coolant_temp_f >= self.settings.coolant_warn_f else COLOR_GREEN),
            ("OIL", f"{self.telemetry.oil_temp_f:.0f}°F",
             COLOR_RED if self.telemetry.oil_temp_f >= self.settings.oil_warn_f else COLOR_GREEN),
            ("FUEL", f"{self.telemetry.fuel_level_percent:.0f}%",
             COLOR_RED if self.telemetry.fuel_level_percent < 10 else 
             COLOR_YELLOW if self.telemetry.fuel_level_percent < 20 else COLOR_GREEN),
            ("VOLTS", f"{self.telemetry.voltage:.1f}V",
             COLOR_RED if self.telemetry.voltage < 12.0 else
             COLOR_YELLOW if self.telemetry.voltage < 12.5 else COLOR_GREEN),
        ]
        for i, (label, val, color) in enumerate(values):
            y = values_y + i * value_h
            txt = self.font_tiny.render(label, True, COLOR_GRAY)
            self.pi_surface.blit(txt, (left_x, y))
            txt = self.font_small.render(val, True, color)
            self.pi_surface.blit(txt, (left_x + 80, y - 2))
        
        # Center: TPMS diagram
        tpms_cx, tpms_cy = 360, 200
        box_w, box_h = 60, 80
        gap = 80  # Gap between tires
        
        # Draw car outline (simple)
        pygame.draw.rect(self.pi_surface, COLOR_DARK_GRAY, 
                        (tpms_cx - 30, tpms_cy - 90, 60, 180), border_radius=10)
        
        # Tire positions: index, dx, dy, name
        tire_positions = [
            (0, -gap, -50, "FL"),
            (1, gap, -50, "FR"),
            (2, -gap, 50, "RL"),
            (3, gap, 50, "RR"),
        ]
        
        for idx, dx, dy, name in tire_positions:
            psi = self.telemetry.tire_pressure[idx]
            temp = self.telemetry.tire_temp[idx]
            x = tpms_cx + dx - box_w//2
            y = tpms_cy + dy - box_h//2
            
            # Color based on pressure
            if psi < self.settings.tire_low_psi:
                color = COLOR_RED
            elif psi > self.settings.tire_high_psi:
                color = COLOR_YELLOW
            else:
                color = COLOR_GREEN
            
            # Box
            pygame.draw.rect(self.pi_surface, COLOR_DARK_GRAY, (x, y, box_w, box_h), border_radius=5)
            pygame.draw.rect(self.pi_surface, color, (x, y, box_w, box_h), 2, border_radius=5)
            
            # Label
            txt = self.font_tiny.render(name, True, COLOR_GRAY)
            self.pi_surface.blit(txt, txt.get_rect(center=(x + box_w//2, y + 12)))
            
            # Pressure (large)
            txt = self.font_small.render(f"{psi:.0f}", True, color)
            self.pi_surface.blit(txt, txt.get_rect(center=(x + box_w//2, y + 35)))
            
            # Temp
            txt = self.font_tiny.render(f"{temp:.0f}°F", True, COLOR_GRAY)
            self.pi_surface.blit(txt, txt.get_rect(center=(x + box_w//2, y + 60)))
        
        # TPMS label
        txt = self.font_small.render("TPMS", True, COLOR_WHITE)
        self.pi_surface.blit(txt, txt.get_rect(center=(tpms_cx, tpms_cy + 120)))
        
        # Right column: Alerts panel
        alerts_x = 500
        alerts_y = 40
        alerts_w = 280
        alerts_h = 400
        
        # Alerts panel background
        pygame.draw.rect(self.pi_surface, COLOR_DARK_GRAY, 
                        (alerts_x, alerts_y, alerts_w, alerts_h), border_radius=10)
        
        # Header
        header_color = COLOR_RED if alerts else COLOR_GREEN
        pygame.draw.rect(self.pi_surface, header_color, 
                        (alerts_x, alerts_y, alerts_w, 40), 
                        border_top_left_radius=10, border_top_right_radius=10)
        header_text = "⚠ ALERTS" if alerts else "✓ ALL SYSTEMS OK"
        txt = self.font_medium.render(header_text, True, COLOR_WHITE)
        self.pi_surface.blit(txt, txt.get_rect(center=(alerts_x + alerts_w//2, alerts_y + 20)))
        
        if alerts:
            # Show alerts
            alert_y = alerts_y + 55
            for i, (alert_text, alert_color) in enumerate(alerts[:8]):  # Max 8 alerts
                # Alert background
                pygame.draw.rect(self.pi_surface, (40, 40, 40),
                               (alerts_x + 10, alert_y, alerts_w - 20, 35), border_radius=5)
                # Alert indicator
                pygame.draw.rect(self.pi_surface, alert_color,
                               (alerts_x + 10, alert_y, 4, 35), border_radius=2)
                # Alert text
                txt = self.font_small.render(alert_text, True, alert_color)
                self.pi_surface.blit(txt, (alerts_x + 22, alert_y + 8))
                alert_y += 42
            
            # Show count if more alerts
            if len(alerts) > 8:
                txt = self.font_tiny.render(f"+ {len(alerts) - 8} more alerts", True, COLOR_GRAY)
                self.pi_surface.blit(txt, txt.get_rect(center=(alerts_x + alerts_w//2, alert_y + 10)))
        else:
            # No alerts - show status checks
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
                symbol = "✓" if ok else "!"
                txt = self.font_small.render(f"{symbol} {label}", True, color)
                self.pi_surface.blit(txt, (alerts_x + 20, check_y))
                check_y += 35

    def render_pi_rpm_speed(self):
        # Left side: Big RPM gauge
        gauge_cx, gauge_cy = 200, 280
        gauge_r = 170
        
        # RPM arc background
        self.draw_arc(self.pi_surface, gauge_cx, gauge_cy, gauge_r, 25, 135, 405, COLOR_DARK_GRAY)
        
        # RPM arc fill
        rpm_pct = self.telemetry.rpm / self.settings.redline_rpm
        rpm_angle = min(270, rpm_pct * 270)
        rpm_color = self.get_rpm_color(self.telemetry.rpm)
        self.draw_arc(self.pi_surface, gauge_cx, gauge_cy, gauge_r, 25, 135, 135 + rpm_angle, rpm_color)
        
        # Shift light indicator
        if self.telemetry.rpm >= self.settings.shift_rpm:
            pygame.draw.circle(self.pi_surface, COLOR_RED, (gauge_cx, gauge_cy - gauge_r - 30), 15)
        
        # Center info
        pygame.draw.circle(self.pi_surface, COLOR_BG, (gauge_cx, gauge_cy), 80)
        
        # Gear
        gear = "N" if self.telemetry.gear == 0 else str(self.telemetry.gear)
        txt = self.pi_font_huge.render(gear, True, rpm_color)
        self.pi_surface.blit(txt, txt.get_rect(center=(gauge_cx, gauge_cy - 10)))
        
        # RPM digits
        txt = self.font_small.render(f"{self.telemetry.rpm} RPM", True, COLOR_WHITE)
        self.pi_surface.blit(txt, txt.get_rect(center=(gauge_cx, gauge_cy + 45)))
        
        # Right side: Speed + extras
        # Big speed
        speed = self.telemetry.speed_kmh
        if self.settings.use_mph:
            speed = int(speed * 0.621371)
        
        txt = self.pi_font_huge.render(str(speed), True, COLOR_WHITE)
        self.pi_surface.blit(txt, txt.get_rect(center=(580, 180)))
        
        unit = "MPH" if self.settings.use_mph else "KMH"
        txt = self.font_medium.render(unit, True, COLOR_GRAY)
        self.pi_surface.blit(txt, txt.get_rect(center=(580, 240)))
        
        # Throttle bar
        self.render_pi_bar(440, 300, 280, 25, "THROTTLE", 
                          self.telemetry.throttle_percent, 100, COLOR_GREEN)
        
        # Brake bar
        self.render_pi_bar(440, 350, 280, 25, "BRAKE",
                          self.telemetry.brake_percent, 100, COLOR_RED)
        
        # Lap time
        lap_ms = self.telemetry.lap_time_ms
        lap_min = lap_ms // 60000
        lap_sec = (lap_ms % 60000) / 1000
        txt = self.font_small.render(f"LAP: {lap_min}:{lap_sec:05.2f}", True, COLOR_WHITE)
        self.pi_surface.blit(txt, (440, 400))
        
        best_ms = self.telemetry.best_lap_ms
        best_min = best_ms // 60000
        best_sec = (best_ms % 60000) / 1000
        txt = self.font_small.render(f"BEST: {best_min}:{best_sec:05.2f}", True, COLOR_PURPLE)
        self.pi_surface.blit(txt, (600, 400))
    
    def render_pi_tpms(self):
        # Car outline in center
        car_cx, car_cy = PI_WIDTH // 2, PI_HEIGHT // 2 + 20
        
        # Simple car shape
        car_w, car_h = 200, 350
        pygame.draw.rect(self.pi_surface, COLOR_DARK_GRAY, 
                        (car_cx - car_w//2, car_cy - car_h//2, car_w, car_h), 
                        border_radius=30)
        
        # Tire boxes
        positions = [
            (car_cx - 160, car_cy - 100, "FL", 0),
            (car_cx + 160, car_cy - 100, "FR", 1),
            (car_cx - 160, car_cy + 100, "RL", 2),
            (car_cx + 160, car_cy + 100, "RR", 3),
        ]
        
        for x, y, label, idx in positions:
            psi = self.telemetry.tire_pressure[idx]
            temp = self.telemetry.tire_temp[idx]
            
            # Color
            if psi < self.settings.tire_low_psi:
                color = COLOR_RED
            elif psi > self.settings.tire_high_psi:
                color = COLOR_YELLOW
            else:
                color = COLOR_GREEN
            
            # Box
            box_w, box_h = 130, 100
            pygame.draw.rect(self.pi_surface, (30, 30, 45),
                           (x - box_w//2, y - box_h//2, box_w, box_h), border_radius=10)
            pygame.draw.rect(self.pi_surface, color,
                           (x - box_w//2, y - box_h//2, box_w, box_h), 3, border_radius=10)
            
            # Label
            txt = self.font_small.render(label, True, COLOR_GRAY)
            self.pi_surface.blit(txt, txt.get_rect(center=(x, y - 30)))
            
            # PSI
            txt = self.pi_font_medium.render(f"{psi:.1f}", True, color)
            self.pi_surface.blit(txt, txt.get_rect(center=(x, y + 5)))
            
            # Temp
            txt = self.font_tiny.render(f"{temp:.0f}°F", True, COLOR_GRAY)
            self.pi_surface.blit(txt, txt.get_rect(center=(x, y + 35)))
    
    def render_pi_engine(self):
        # Grid of gauges
        # Row 1: Coolant, Oil Temp, Oil Pressure
        self.render_pi_gauge(150, 180, "COOLANT", self.telemetry.coolant_temp_f, "°F",
                            180, self.settings.coolant_warn_f, 250)
        self.render_pi_gauge(400, 180, "OIL TEMP", self.telemetry.oil_temp_f, "°F",
                            150, self.settings.oil_warn_f, 280)
        self.render_pi_gauge(650, 180, "OIL PSI", self.telemetry.oil_pressure_psi, "",
                            0, 30, 80)
        
        # Row 2: Fuel, Voltage, Intake Temp
        fuel = self.telemetry.fuel_level_percent
        fuel_color = COLOR_RED if fuel < 15 else (COLOR_YELLOW if fuel < 25 else COLOR_GREEN)
        self.render_pi_gauge_bar(150, 380, "FUEL", fuel, "%", fuel_color)
        
        self.render_pi_gauge(400, 380, "VOLTAGE", self.telemetry.voltage, "V",
                            11, 13.5, 15)
        self.render_pi_gauge(650, 380, "INTAKE", self.telemetry.intake_temp_f, "°F",
                            50, 120, 180)
    
    def render_pi_gforce(self):
        # Big G-ball on left
        ball_cx, ball_cy = 250, 280
        ball_r = 180
        
        pygame.draw.circle(self.pi_surface, (25, 25, 35), (ball_cx, ball_cy), ball_r)
        pygame.draw.circle(self.pi_surface, COLOR_GRAY, (ball_cx, ball_cy), ball_r, 2)
        
        # Grid lines
        for r in [60, 120]:
            pygame.draw.circle(self.pi_surface, COLOR_DARK_GRAY, (ball_cx, ball_cy), r, 1)
        pygame.draw.line(self.pi_surface, COLOR_DARK_GRAY,
                        (ball_cx - ball_r, ball_cy), (ball_cx + ball_r, ball_cy), 1)
        pygame.draw.line(self.pi_surface, COLOR_DARK_GRAY,
                        (ball_cx, ball_cy - ball_r), (ball_cx, ball_cy + ball_r), 1)
        
        # G labels
        for g, r in [(0.5, 60), (1.0, 120)]:
            txt = self.font_tiny.render(f"{g}G", True, COLOR_DARK_GRAY)
            self.pi_surface.blit(txt, (ball_cx + r + 5, ball_cy - 10))
        
        # G-ball
        g_scale = 120
        gx = ball_cx + int(self.telemetry.g_lateral * g_scale)
        gy = ball_cy - int(self.telemetry.g_longitudinal * g_scale)
        
        # Clamp
        dx, dy = gx - ball_cx, gy - ball_cy
        dist = math.sqrt(dx*dx + dy*dy)
        if dist > ball_r - 15:
            scale = (ball_r - 15) / dist
            gx = ball_cx + int(dx * scale)
            gy = ball_cy + int(dy * scale)
        
        pygame.draw.circle(self.pi_surface, COLOR_ACCENT, (gx, gy), 18)
        pygame.draw.circle(self.pi_surface, COLOR_WHITE, (gx, gy), 18, 3)
        
        # Right side: detailed values
        # Peak G
        txt = self.font_medium.render("LATERAL", True, COLOR_GRAY)
        self.pi_surface.blit(txt, (500, 120))
        txt = self.pi_font_large.render(f"{self.telemetry.g_lateral:+.2f}G", True, COLOR_WHITE)
        self.pi_surface.blit(txt, (500, 160))
        
        txt = self.font_medium.render("LONGITUDINAL", True, COLOR_GRAY)
        self.pi_surface.blit(txt, (500, 260))
        txt = self.pi_font_large.render(f"{self.telemetry.g_longitudinal:+.2f}G", True, COLOR_WHITE)
        self.pi_surface.blit(txt, (500, 300))
        
        # Combined G
        combined = math.sqrt(self.telemetry.g_lateral**2 + self.telemetry.g_longitudinal**2)
        txt = self.font_medium.render("COMBINED", True, COLOR_GRAY)
        self.pi_surface.blit(txt, (500, 400))
        txt = self.pi_font_medium.render(f"{combined:.2f}G", True, COLOR_ACCENT)
        self.pi_surface.blit(txt, (500, 430))
    
    def render_pi_settings(self):
        items = self.get_settings_items()
        
        start_y = 90
        item_h = 55
        
        for i, (name, value, unit) in enumerate(items):
            y = start_y + i * item_h
            
            # Background
            bg_color = (40, 40, 55) if i == self.settings_selection else (25, 25, 35)
            pygame.draw.rect(self.pi_surface, bg_color, (30, y, PI_WIDTH - 60, item_h - 5), border_radius=8)
            
            if i == self.settings_selection and self.settings_edit_mode:
                pygame.draw.rect(self.pi_surface, COLOR_ACCENT, (30, y, PI_WIDTH - 60, item_h - 5), 3, border_radius=8)
            
            # Name
            color = COLOR_WHITE if i == self.settings_selection else COLOR_GRAY
            txt = self.font_medium.render(name, True, color)
            self.pi_surface.blit(txt, (50, y + 12))
            
            # Value
            if value != "":
                val_color = COLOR_ACCENT if i == self.settings_selection else COLOR_WHITE
                txt = self.font_medium.render(f"{value}{unit}", True, val_color)
                self.pi_surface.blit(txt, (PI_WIDTH - 50 - txt.get_width(), y + 12))
            
            # Edit hint
            if i == self.settings_selection and name != "Back":
                hint = "← VOL+/VOL- to adjust →" if self.settings_edit_mode else "Press ON/OFF to edit"
                txt = self.font_tiny.render(hint, True, COLOR_DARK_GRAY)
                self.pi_surface.blit(txt, txt.get_rect(center=(PI_WIDTH // 2, PI_HEIGHT - 30)))
    
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
