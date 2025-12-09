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
    python3 main.py              # Normal mode
    python3 main.py --demo       # Demo mode with simulated data
    python3 main.py --fullscreen # Fullscreen mode for production

Requirements:
    pip install pygame
"""

import pygame
import math
import sys
import argparse
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

# =============================================================================
# CONSTANTS
# =============================================================================

# Display size (800x480 for Pi display)
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
    NONE = auto()
    VOL_UP = auto()
    VOL_DOWN = auto()
    ON_OFF = auto()
    CANCEL = auto()
    RES_PLUS = auto()
    SET_MINUS = auto()


class Screen(Enum):
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
    best_lap_ms: int = 95400


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
# MAIN APPLICATION
# =============================================================================

class PiDisplayApp:
    def __init__(self, fullscreen: bool = False, demo_mode: bool = True):
        pygame.init()
        
        # Display setup
        flags = pygame.FULLSCREEN if fullscreen else 0
        self.screen = pygame.display.set_mode((PI_WIDTH, PI_HEIGHT), flags)
        pygame.display.set_caption("MX5 Telemetry Display")
        
        # State
        self.current_screen = Screen.OVERVIEW
        self.sleeping = False
        self.demo_mode = demo_mode
        self.demo_rpm_dir = 1
        
        # Settings navigation
        self.settings_selection = 0
        self.settings_edit_mode = False
        
        # Data
        self.telemetry = TelemetryData()
        self.settings = Settings()
        
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
    
    def run(self):
        """Main application loop"""
        running = True
        
        print("=" * 60)
        print("MX5 Telemetry - Raspberry Pi Display")
        print("=" * 60)
        print(f"Resolution: {PI_WIDTH}x{PI_HEIGHT}")
        print(f"Demo Mode: {self.demo_mode}")
        print()
        print("Controls:")
        print("  ↑ / W     = Previous screen (RES+)")
        print("  ↓ / S     = Next screen (SET-)")
        print("  → / D     = Increase value (VOL+)")
        print("  ← / A     = Decrease value (VOL-)")
        print("  Enter     = Select / Edit (ON/OFF)")
        print("  Esc / B   = Back / Exit (CANCEL)")
        print("  Space     = Toggle sleep mode")
        print("  Q         = Quit")
        print("=" * 60)
        
        while running:
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    button = self._key_to_button(event.key)
                    if button == ButtonEvent.NONE:
                        if event.key == pygame.K_q:
                            running = False
                        elif event.key == pygame.K_SPACE:
                            self.sleeping = not self.sleeping
                    else:
                        self._handle_button(button)
            
            # Update demo mode
            if self.demo_mode and not self.sleeping:
                self._update_demo()
            
            # Render
            self._render()
            
            pygame.display.flip()
            self.clock.tick(30)
        
        pygame.quit()
    
    def _key_to_button(self, key) -> ButtonEvent:
        """Map keyboard to SWC buttons"""
        mapping = {
            pygame.K_UP: ButtonEvent.RES_PLUS,
            pygame.K_w: ButtonEvent.RES_PLUS,
            pygame.K_DOWN: ButtonEvent.SET_MINUS,
            pygame.K_s: ButtonEvent.SET_MINUS,
            pygame.K_RIGHT: ButtonEvent.VOL_UP,
            pygame.K_d: ButtonEvent.VOL_UP,
            pygame.K_LEFT: ButtonEvent.VOL_DOWN,
            pygame.K_a: ButtonEvent.VOL_DOWN,
            pygame.K_RETURN: ButtonEvent.ON_OFF,
            pygame.K_ESCAPE: ButtonEvent.CANCEL,
            pygame.K_b: ButtonEvent.CANCEL,
        }
        return mapping.get(key, ButtonEvent.NONE)
    
    def _handle_button(self, button: ButtonEvent):
        """Handle button press"""
        if self.current_screen == Screen.SETTINGS:
            self._handle_settings_button(button)
        else:
            self._handle_navigation_button(button)
    
    def _handle_navigation_button(self, button: ButtonEvent):
        """Handle normal screen navigation"""
        screens = list(Screen)
        idx = screens.index(self.current_screen)
        
        if button == ButtonEvent.RES_PLUS:
            idx = (idx - 1) % len(screens)
            self.current_screen = screens[idx]
        elif button == ButtonEvent.SET_MINUS:
            idx = (idx + 1) % len(screens)
            self.current_screen = screens[idx]
    
    def _handle_settings_button(self, button: ButtonEvent):
        """Handle settings screen navigation"""
        items = self._get_settings_items()
        
        if button == ButtonEvent.RES_PLUS and not self.settings_edit_mode:
            self.settings_selection = max(0, self.settings_selection - 1)
        elif button == ButtonEvent.SET_MINUS and not self.settings_edit_mode:
            self.settings_selection = min(len(items) - 1, self.settings_selection + 1)
        elif button == ButtonEvent.ON_OFF:
            if self.settings_selection == len(items) - 1:  # Back
                self.current_screen = Screen.OVERVIEW
                self.settings_selection = 0
            else:
                self.settings_edit_mode = not self.settings_edit_mode
        elif button == ButtonEvent.CANCEL:
            if self.settings_edit_mode:
                self.settings_edit_mode = False
            else:
                self.current_screen = Screen.OVERVIEW
                self.settings_selection = 0
        elif self.settings_edit_mode:
            delta = 1 if button == ButtonEvent.VOL_UP else (-1 if button == ButtonEvent.VOL_DOWN else 0)
            self._adjust_setting(delta)
    
    def _adjust_setting(self, delta: int):
        """Adjust currently selected setting"""
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
    
    def _get_settings_items(self):
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
    
    def _update_demo(self):
        """Update demo animation"""
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
        
        # Speed approximation
        self.telemetry.speed_kmh = self.telemetry.rpm * self.telemetry.gear // 100
        
        # G-force simulation
        import time
        t = time.time()
        self.telemetry.g_lateral = math.sin(t) * 0.8
        self.telemetry.g_longitudinal = math.cos(t * 1.5) * 0.5
        
        # Throttle/brake simulation
        self.telemetry.throttle_percent = int(50 + math.sin(t * 2) * 50)
        self.telemetry.brake_percent = int(max(0, -math.sin(t * 2) * 30))
        
        # Lap time
        self.telemetry.lap_time_ms += 33
        if self.telemetry.lap_time_ms > 120000:
            self.telemetry.lap_time_ms = 0
    
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
            alerts.append((f"COOLANT: {self.telemetry.coolant_temp_f}°F", COLOR_RED))
        if self.telemetry.oil_temp_f >= self.settings.oil_warn_f:
            alerts.append((f"OIL TEMP: {self.telemetry.oil_temp_f}°F", COLOR_RED))
        
        # Check voltage
        if self.telemetry.voltage < 12.0:
            alerts.append((f"LOW VOLTAGE: {self.telemetry.voltage:.1f}V", COLOR_YELLOW))
        
        # Check fuel
        if self.telemetry.fuel_level_percent < 15:
            alerts.append((f"LOW FUEL: {self.telemetry.fuel_level_percent:.0f}%", COLOR_YELLOW))
        
        return alerts
    
    def _draw_arc(self, surface, cx, cy, radius, thickness, start_angle, end_angle, color):
        """Draw a thick arc"""
        import math
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
        else:
            renderers = {
                Screen.OVERVIEW: self._render_overview,
                Screen.RPM_SPEED: self._render_rpm_speed,
                Screen.TPMS: self._render_tpms,
                Screen.ENGINE: self._render_engine,
                Screen.GFORCE: self._render_gforce,
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
    
    def _render_sleep(self):
        """Render sleep screen"""
        txt = self.font_large.render("SLEEP MODE", True, COLOR_DARK_GRAY)
        self.screen.blit(txt, txt.get_rect(center=(PI_WIDTH // 2, PI_HEIGHT // 2)))
    
    def _render_overview(self):
        """Overview screen - matches simulator exactly"""
        alerts = self._get_alerts()
        TOP = 55
        
        left_panel_x = 20
        left_panel_w = 180
        
        # Gear card with glow
        pygame.draw.rect(self.screen, COLOR_BG_CARD, 
                        (left_panel_x, TOP, left_panel_w, 150), border_radius=14)
        
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
        pygame.draw.rect(self.screen, COLOR_BG_CARD, 
                        (left_panel_x, TOP + 160, left_panel_w, 40), border_radius=10)
        rpm_pct = min(1.0, self.telemetry.rpm / self.settings.redline_rpm)
        bar_x, bar_y = left_panel_x + 12, TOP + 172
        bar_w = left_panel_w - 24
        pygame.draw.rect(self.screen, COLOR_DARK_GRAY, (bar_x, bar_y, bar_w, 12), border_radius=6)
        pygame.draw.rect(self.screen, rpm_color, (bar_x, bar_y, int(bar_w * rpm_pct), 12), border_radius=6)
        txt = self.font_tiny.render(f"{self.telemetry.rpm} RPM", True, COLOR_GRAY)
        self.screen.blit(txt, txt.get_rect(center=(left_panel_x + left_panel_w//2, TOP + 188)))
        
        # Key values grid
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
            
            pygame.draw.rect(self.screen, COLOR_BG_CARD, (x, y, card_w, card_h), border_radius=8)
            pygame.draw.rect(self.screen, color, (x, y, 3, card_h), 
                           border_top_left_radius=8, border_bottom_left_radius=8)
            
            txt = self.font_tiny.render(label, True, COLOR_GRAY)
            self.screen.blit(txt, (x + 10, y + 5))
            txt = self.font_small.render(val, True, color)
            self.screen.blit(txt, (x + 10, y + 22))
        
        # Center: TPMS diagram
        tpms_cx, tpms_cy = 340, TOP + 160
        
        car_w, car_h = 55, 100
        pygame.draw.rect(self.screen, COLOR_BG_CARD, 
                        (tpms_cx - car_w//2, tpms_cy - car_h//2, car_w, car_h), border_radius=12)
        
        box_w, box_h = 60, 65
        gap = 70
        tire_positions = [
            (0, -gap, -30, "FL"), (1, gap, -30, "FR"),
            (2, -gap, 50, "RL"), (3, gap, 50, "RR"),
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
            
            pygame.draw.rect(self.screen, COLOR_BG_CARD, (x, y, box_w, box_h), border_radius=10)
            pygame.draw.rect(self.screen, color, (x, y, 3, box_h), 
                           border_top_left_radius=10, border_bottom_left_radius=10)
            
            txt = self.font_tiny.render(name, True, COLOR_GRAY)
            self.screen.blit(txt, txt.get_rect(center=(x + box_w//2, y + 10)))
            txt = self.font_small.render(f"{psi:.0f}", True, color)
            self.screen.blit(txt, txt.get_rect(center=(x + box_w//2, y + 32)))
            txt = self.font_tiny.render(f"{temp:.0f}°", True, COLOR_GRAY)
            self.screen.blit(txt, txt.get_rect(center=(x + box_w//2, y + 52)))
        
        # Right panel: Alerts
        alerts_x = 490
        alerts_y = TOP
        alerts_w = 290
        alerts_h = PI_HEIGHT - TOP - 10
        
        pygame.draw.rect(self.screen, COLOR_BG_CARD, 
                        (alerts_x, alerts_y, alerts_w, alerts_h), border_radius=14)
        
        header_color = COLOR_RED if alerts else COLOR_GREEN
        pygame.draw.rect(self.screen, header_color, 
                        (alerts_x, alerts_y, alerts_w, 45), 
                        border_top_left_radius=14, border_top_right_radius=14)
        header_text = "⚠ ALERTS" if alerts else "✓ ALL OK"
        txt = self.font_medium.render(header_text, True, COLOR_WHITE)
        self.screen.blit(txt, txt.get_rect(center=(alerts_x + alerts_w//2, alerts_y + 22)))
        
        if alerts:
            alert_y = alerts_y + 55
            for i, (alert_text, alert_color) in enumerate(alerts[:8]):
                pygame.draw.rect(self.screen, COLOR_BG_ELEVATED,
                               (alerts_x + 10, alert_y, alerts_w - 20, 38), border_radius=6)
                pygame.draw.rect(self.screen, alert_color,
                               (alerts_x + 10, alert_y, 3, 38), border_radius=2)
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
                               (alerts_x + 10, check_y, alerts_w - 20, 38), border_radius=6)
                symbol = "✓" if ok else "!"
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
        pygame.draw.rect(self.screen, COLOR_BG_CARD, (right_x, TOP, 340, 150), border_radius=14)
        
        speed = self.telemetry.speed_kmh
        if self.settings.use_mph:
            speed = int(speed * 0.621371)
        
        txt = self.font_huge.render(str(speed), True, COLOR_WHITE)
        self.screen.blit(txt, txt.get_rect(center=(right_x + 170, TOP + 60)))
        
        unit = "MPH" if self.settings.use_mph else "KMH"
        txt = self.font_medium.render(unit, True, COLOR_GRAY)
        self.screen.blit(txt, txt.get_rect(center=(right_x + 170, TOP + 120)))
        
        # Throttle/Brake
        pygame.draw.rect(self.screen, COLOR_BG_CARD, (right_x, TOP + 165, 165, 80), border_radius=12)
        txt = self.font_tiny.render("THROTTLE", True, COLOR_GRAY)
        self.screen.blit(txt, (right_x + 15, TOP + 172))
        pygame.draw.rect(self.screen, COLOR_DARK_GRAY, (right_x + 15, TOP + 195, 135, 14), border_radius=7)
        throttle_w = int(135 * self.telemetry.throttle_percent / 100)
        pygame.draw.rect(self.screen, COLOR_GREEN, (right_x + 15, TOP + 195, throttle_w, 14), border_radius=7)
        txt = self.font_small.render(f"{self.telemetry.throttle_percent}%", True, COLOR_GREEN)
        self.screen.blit(txt, (right_x + 15, TOP + 215))
        
        pygame.draw.rect(self.screen, COLOR_BG_CARD, (right_x + 175, TOP + 165, 165, 80), border_radius=12)
        txt = self.font_tiny.render("BRAKE", True, COLOR_GRAY)
        self.screen.blit(txt, (right_x + 190, TOP + 172))
        pygame.draw.rect(self.screen, COLOR_DARK_GRAY, (right_x + 190, TOP + 195, 135, 14), border_radius=7)
        brake_w = int(135 * self.telemetry.brake_percent / 100)
        pygame.draw.rect(self.screen, COLOR_RED, (right_x + 190, TOP + 195, brake_w, 14), border_radius=7)
        txt = self.font_small.render(f"{self.telemetry.brake_percent}%", True, COLOR_RED)
        self.screen.blit(txt, (right_x + 190, TOP + 215))
        
        # Lap times
        pygame.draw.rect(self.screen, COLOR_BG_CARD, (right_x, TOP + 260, 340, 90), border_radius=12)
        
        lap_ms = self.telemetry.lap_time_ms
        lap_min = lap_ms // 60000
        lap_sec = (lap_ms % 60000) / 1000
        
        txt = self.font_tiny.render("CURRENT LAP", True, COLOR_GRAY)
        self.screen.blit(txt, (right_x + 20, TOP + 270))
        txt = self.font_medium.render(f"{lap_min}:{lap_sec:05.2f}", True, COLOR_WHITE)
        self.screen.blit(txt, (right_x + 20, TOP + 290))
        
        best_ms = self.telemetry.best_lap_ms
        best_min = best_ms // 60000
        best_sec = (best_ms % 60000) / 1000
        
        txt = self.font_tiny.render("BEST", True, COLOR_GRAY)
        self.screen.blit(txt, (right_x + 220, TOP + 270))
        txt = self.font_medium.render(f"{best_min}:{best_sec:05.2f}", True, COLOR_PURPLE)
        self.screen.blit(txt, (right_x + 190, TOP + 295))
    
    def _render_tpms(self):
        """TPMS screen"""
        TOP = 55
        
        car_cx, car_cy = PI_WIDTH // 2, TOP + (PI_HEIGHT - TOP) // 2
        car_w, car_h = 150, 250
        
        pygame.draw.rect(self.screen, COLOR_BG_CARD, 
                        (car_cx - car_w//2, car_cy - car_h//2, car_w, car_h), border_radius=22)
        pygame.draw.rect(self.screen, COLOR_DARK_GRAY, 
                        (car_cx - car_w//2, car_cy - car_h//2, car_w, car_h), 2, border_radius=22)
        
        positions = [
            (car_cx - 165, car_cy - 75, "FL", 0),
            (car_cx + 165, car_cy - 75, "FR", 1),
            (car_cx - 165, car_cy + 75, "RL", 2),
            (car_cx + 165, car_cy + 75, "RR", 3),
        ]
        
        box_w, box_h = 125, 95
        
        for x, y, label, idx in positions:
            psi = self.telemetry.tire_pressure[idx]
            temp = self.telemetry.tire_temp[idx]
            
            if psi < self.settings.tire_low_psi:
                color = COLOR_RED
            elif psi > self.settings.tire_high_psi:
                color = COLOR_YELLOW
            else:
                color = COLOR_GREEN
            
            pygame.draw.rect(self.screen, COLOR_BG_CARD,
                           (x - box_w//2, y - box_h//2, box_w, box_h), border_radius=14)
            pygame.draw.rect(self.screen, color,
                           (x - box_w//2, y - box_h//2, 5, box_h), 
                           border_top_left_radius=14, border_bottom_left_radius=14)
            
            txt = self.font_small.render(label, True, COLOR_GRAY)
            self.screen.blit(txt, txt.get_rect(center=(x + 5, y - 28)))
            
            txt = self.font_medium.render(f"{psi:.1f}", True, color)
            self.screen.blit(txt, txt.get_rect(center=(x + 5, y + 5)))
            
            txt = self.font_tiny.render(f"PSI  |  {temp:.0f}°F", True, COLOR_GRAY)
            self.screen.blit(txt, txt.get_rect(center=(x + 5, y + 35)))
    
    def _render_engine(self):
        """Engine screen"""
        TOP = 55
        row1_y = TOP + 110
        row2_y = TOP + 290
        
        # Coolant
        cool = self.telemetry.coolant_temp_f
        cool_color = COLOR_RED if cool >= self.settings.coolant_warn_f else COLOR_TEAL
        self._render_gauge(150, row1_y, "COOLANT", cool, "°F", 180, self.settings.coolant_warn_f, 250, cool_color)
        
        # Oil Temp
        oil = self.telemetry.oil_temp_f
        oil_color = COLOR_RED if oil >= self.settings.oil_warn_f else COLOR_GREEN
        self._render_gauge(400, row1_y, "OIL TEMP", oil, "°F", 150, self.settings.oil_warn_f, 280, oil_color)
        
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
        self._render_gauge(650, row2_y, "INTAKE", self.telemetry.intake_temp_f, "°F", 50, 120, 180, COLOR_CYAN)
    
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
        
        pygame.draw.rect(self.screen, COLOR_BG_CARD, (cx - 70, cy - 40, 140, 80), border_radius=12)
        
        txt = self.font_tiny.render(label, True, COLOR_GRAY)
        self.screen.blit(txt, txt.get_rect(center=(cx, cy - 25)))
        
        pygame.draw.rect(self.screen, COLOR_DARK_GRAY, (cx - bar_w//2, cy - 5, bar_w, bar_h), border_radius=5)
        fill_w = int(bar_w * value / 100)
        if fill_w > 0:
            pygame.draw.rect(self.screen, color, (cx - bar_w//2, cy - 5, fill_w, bar_h), border_radius=5)
        
        txt = self.font_small.render(f"{value:.0f}{unit}", True, color)
        self.screen.blit(txt, txt.get_rect(center=(cx, cy + 25)))
    
    def _render_gforce(self):
        """G-Force screen"""
        TOP = 55
        
        ball_cx, ball_cy = 230, TOP + 180
        ball_r = 155
        
        pygame.draw.circle(self.screen, COLOR_BG_CARD, (ball_cx, ball_cy), ball_r + 8)
        pygame.draw.circle(self.screen, COLOR_BG, (ball_cx, ball_cy), ball_r)
        
        for g in [0.5, 1.0, 1.5]:
            r = int(g * 85)
            pygame.draw.circle(self.screen, COLOR_DARK_GRAY, (ball_cx, ball_cy), r, 1)
        
        pygame.draw.line(self.screen, COLOR_DARK_GRAY,
                        (ball_cx - ball_r, ball_cy), (ball_cx + ball_r, ball_cy), 1)
        pygame.draw.line(self.screen, COLOR_DARK_GRAY,
                        (ball_cx, ball_cy - ball_r), (ball_cx, ball_cy + ball_r), 1)
        
        # G labels
        for g in [0.5, 1.0, 1.5]:
            r = int(g * 85)
            txt = self.font_tiny.render(f"{g}", True, COLOR_DARK_GRAY)
            self.screen.blit(txt, (ball_cx + r + 5, ball_cy - 8))
        
        # G-ball
        g_scale = 85
        gx = ball_cx + int(self.telemetry.g_lateral * g_scale)
        gy = ball_cy - int(self.telemetry.g_longitudinal * g_scale)
        
        dx, dy = gx - ball_cx, gy - ball_cy
        dist = math.sqrt(dx*dx + dy*dy)
        if dist > ball_r - 16:
            scale = (ball_r - 16) / dist
            gx = ball_cx + int(dx * scale)
            gy = ball_cy + int(dy * scale)
        
        glow = pygame.Surface((50, 50), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*COLOR_ACCENT[:3], 100), (25, 25), 20)
        self.screen.blit(glow, (gx - 25, gy - 25))
        
        pygame.draw.circle(self.screen, COLOR_ACCENT, (gx, gy), 15)
        pygame.draw.circle(self.screen, COLOR_WHITE, (gx, gy), 15, 2)
        
        # Right panel cards
        right_x = 440
        card_w = 340
        card_h = 95
        
        # Lateral
        pygame.draw.rect(self.screen, COLOR_BG_CARD, (right_x, TOP, card_w, card_h), border_radius=14)
        pygame.draw.rect(self.screen, COLOR_CYAN, (right_x, TOP, 5, card_h), 
                        border_top_left_radius=14, border_bottom_left_radius=14)
        txt = self.font_small.render("LATERAL", True, COLOR_GRAY)
        self.screen.blit(txt, (right_x + 20, TOP + 12))
        txt = self.font_large.render(f"{self.telemetry.g_lateral:+.2f}G", True, COLOR_CYAN)
        self.screen.blit(txt, (right_x + 20, TOP + 40))
        
        # Longitudinal
        pygame.draw.rect(self.screen, COLOR_BG_CARD, (right_x, TOP + card_h + 15, card_w, card_h), border_radius=14)
        pygame.draw.rect(self.screen, COLOR_PURPLE, (right_x, TOP + card_h + 15, 5, card_h), 
                        border_top_left_radius=14, border_bottom_left_radius=14)
        txt = self.font_small.render("LONGITUDINAL", True, COLOR_GRAY)
        self.screen.blit(txt, (right_x + 20, TOP + card_h + 27))
        txt = self.font_large.render(f"{self.telemetry.g_longitudinal:+.2f}G", True, COLOR_PURPLE)
        self.screen.blit(txt, (right_x + 20, TOP + card_h + 55))
        
        # Combined
        combined = math.sqrt(self.telemetry.g_lateral**2 + self.telemetry.g_longitudinal**2)
        pygame.draw.rect(self.screen, COLOR_BG_CARD, (right_x, TOP + 2*(card_h + 15), card_w, card_h), border_radius=14)
        pygame.draw.rect(self.screen, COLOR_ACCENT, (right_x, TOP + 2*(card_h + 15), 5, card_h), 
                        border_top_left_radius=14, border_bottom_left_radius=14)
        txt = self.font_small.render("COMBINED", True, COLOR_GRAY)
        self.screen.blit(txt, (right_x + 20, TOP + 2*(card_h + 15) + 12))
        txt = self.font_large.render(f"{combined:.2f}G", True, COLOR_ACCENT)
        self.screen.blit(txt, (right_x + 20, TOP + 2*(card_h + 15) + 40))
        
        # IMU source
        txt = self.font_tiny.render("Source: QMI8658 IMU", True, COLOR_DARK_GRAY)
        self.screen.blit(txt, txt.get_rect(center=(ball_cx, PI_HEIGHT - 15)))
    
    def _render_settings(self):
        """Settings screen"""
        TOP = 55
        
        items = self._get_settings_items()
        item_h = 50
        
        for i, (name, value, unit) in enumerate(items):
            y = TOP + i * item_h
            is_selected = i == self.settings_selection
            
            bg_color = COLOR_BG_ELEVATED if is_selected else COLOR_BG_CARD
            pygame.draw.rect(self.screen, bg_color, (40, y, PI_WIDTH - 80, item_h - 5), border_radius=10)
            
            if is_selected:
                pygame.draw.rect(self.screen, COLOR_ACCENT, 
                               (40, y, 5, item_h - 5), 
                               border_top_left_radius=10, border_bottom_left_radius=10)
                if self.settings_edit_mode:
                    pygame.draw.rect(self.screen, COLOR_ACCENT, 
                                   (40, y, PI_WIDTH - 80, item_h - 5), 2, border_radius=10)
            
            color = COLOR_WHITE if is_selected else COLOR_GRAY
            txt = self.font_small.render(name, True, color)
            self.screen.blit(txt, (60, y + 12))
            
            if value != "":
                val_color = COLOR_ACCENT if is_selected else COLOR_WHITE
                txt = self.font_small.render(f"{value}{unit}", True, val_color)
                self.screen.blit(txt, (PI_WIDTH - 60 - txt.get_width(), y + 12))
            
            if is_selected and name != "Back":
                hint = "← VOL+/VOL- to adjust →" if self.settings_edit_mode else "Press ON/OFF to edit"
                txt = self.font_tiny.render(hint, True, COLOR_DARK_GRAY)
                self.screen.blit(txt, txt.get_rect(center=(PI_WIDTH // 2, PI_HEIGHT - 15)))


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="MX5 Telemetry Pi Display")
    parser.add_argument("--fullscreen", "-f", action="store_true", help="Run in fullscreen mode")
    parser.add_argument("--demo", "-d", action="store_true", default=True, help="Run in demo mode")
    parser.add_argument("--no-demo", action="store_true", help="Disable demo mode")
    args = parser.parse_args()
    
    demo_mode = args.demo and not args.no_demo
    
    app = PiDisplayApp(fullscreen=args.fullscreen, demo_mode=demo_mode)
    app.run()


if __name__ == "__main__":
    main()
