#!/usr/bin/env python3
"""
Raspberry Pi Display UI Simulator

Simulates the Pioneer AVH-W4500NEX display (800x480) using Pygame.
Allows testing of UI screens and SWC button navigation.

Requirements:
    pip install pygame

Controls (keyboard mappings to SWC buttons):
    M / Tab      = MODE (switch device focus Pi/ESP32)
    Enter        = ON/OFF (select)
    Escape / B   = CANCEL (back)
    Up / W       = RES+ (up)
    Down / S     = SET- (down)
    Right / D    = SEEK_UP (right/next)
    Left / A     = SEEK_DOWN (left/prev)
    + / =        = VOL_UP (increase value)
    - / _        = VOL_DOWN (decrease value)
    Space        = MUTE (sleep toggle)
"""

import pygame
import math
import sys
import random
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Callable

# Display constants (Pioneer AVH-W4500NEX)
DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 480

# Colors
COLOR_BG = (20, 20, 30)
COLOR_BG_LIGHT = (40, 40, 50)
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


# Screen IDs
SCREEN_HOME = "home"
SCREEN_MAPS = "maps"
SCREEN_MUSIC = "music"
SCREEN_TELEMETRY = "telemetry"
SCREEN_TPMS = "tpms"
SCREEN_SETTINGS = "settings"

SCREENS = [SCREEN_HOME, SCREEN_MAPS, SCREEN_MUSIC, SCREEN_TELEMETRY, SCREEN_TPMS, SCREEN_SETTINGS]

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


@dataclass
class TelemetryData:
    rpm: int = 2500
    speed_kmh: int = 65
    gear: int = 3
    throttle_percent: int = 25
    brake_active: bool = False
    coolant_temp_f: int = 185
    oil_temp_f: int = 210
    ambient_temp_f: int = 72
    fuel_level_percent: float = 65.0
    instant_mpg: float = 28.5
    average_mpg: float = 26.2
    range_miles: int = 245
    tire_pressure: List[float] = field(default_factory=lambda: [32.5, 31.8, 33.1, 32.9])
    tire_temp: List[float] = field(default_factory=lambda: [95.3, 94.1, 96.0, 95.8])
    tire_battery: List[int] = field(default_factory=lambda: [95, 92, 88, 90])
    g_lateral: float = 0.0
    g_longitudinal: float = 0.0
    steering_angle: float = 0.0
    odometer_miles: int = 45230


@dataclass
class UISettings:
    brightness: int = 80
    use_mph: bool = True
    use_fahrenheit: bool = True
    shift_rpm: int = 6500
    redline_rpm: int = 7200
    tire_low_psi: float = 28.0
    tire_high_psi: float = 36.0


@dataclass
class MusicState:
    playing: bool = True
    song_title: str = "Midnight Run"
    artist: str = "The Drivers"
    album: str = "Road Trip"
    position_sec: int = 45
    duration_sec: int = 213
    volume: int = 75


class PiSimulator:
    def __init__(self):
        pygame.init()
        
        # Window with control panel
        self.window_width = DISPLAY_WIDTH + 200
        self.window_height = DISPLAY_HEIGHT + 60
        self.screen = pygame.display.set_mode((self.window_width, self.window_height))
        pygame.display.set_caption("Raspberry Pi Display Simulator (800x480)")
        
        # Create display surface
        self.display = pygame.Surface((DISPLAY_WIDTH, DISPLAY_HEIGHT))
        
        # State
        self.current_screen = SCREEN_HOME
        self.previous_screen = SCREEN_HOME
        self.sleeping = False
        self.device_focus = "pi"  # "pi" or "esp32"
        
        # Home screen state
        self.home_selection = 0
        self.home_apps = [SCREEN_MAPS, SCREEN_MUSIC, SCREEN_TELEMETRY, SCREEN_TPMS, SCREEN_SETTINGS]
        
        # Settings state
        self.settings_selection = 0
        self.settings_edit_mode = False
        self.settings_items = ["Brightness", "Shift RPM", "Redline RPM", "Units (MPH/KMH)", "Tire Low PSI", "Back"]
        
        # Data
        self.telemetry = TelemetryData()
        self.settings = UISettings()
        self.music = MusicState()
        
        # Fonts
        self.font_large = pygame.font.Font(None, 72)
        self.font_medium = pygame.font.Font(None, 48)
        self.font_small = pygame.font.Font(None, 32)
        self.font_tiny = pygame.font.Font(None, 24)
        self.font_icon = pygame.font.Font(None, 64)
        
        # Clock
        self.clock = pygame.time.Clock()
        
        # Button display
        self.last_button = ButtonEvent.NONE
        self.button_display_time = 0
        
        # Demo mode
        self.demo_mode = True
        self.demo_rpm_dir = 1
    
    def run(self):
        """Main loop"""
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    button = self.key_to_button(event.key)
                    if button != ButtonEvent.NONE:
                        self.handle_button(button)
                        self.last_button = button
                        self.button_display_time = pygame.time.get_ticks()
                    
                    if event.key == pygame.K_t:
                        self.demo_mode = not self.demo_mode
            
            # Demo mode updates
            if self.demo_mode:
                self.update_demo()
            
            # Clear window
            self.screen.fill((30, 30, 40))
            
            # Render display
            self.render()
            
            # Draw control panel
            self.draw_control_panel()
            
            # Draw status bar
            self.draw_status_bar()
            
            # Update
            pygame.display.flip()
            self.clock.tick(30)
        
        pygame.quit()
    
    def key_to_button(self, key) -> ButtonEvent:
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
        # MODE switches device focus
        if button == ButtonEvent.MODE:
            self.device_focus = "esp32" if self.device_focus == "pi" else "pi"
            return
        
        # If ESP32 has focus, don't process buttons (they go to ESP32)
        if self.device_focus == "esp32":
            return
        
        # MUTE toggles sleep
        if button == ButtonEvent.MUTE:
            self.sleeping = not self.sleeping
            return
        
        # Wake from sleep
        if self.sleeping:
            self.sleeping = False
            return
        
        # Screen-specific handling
        handlers = {
            SCREEN_HOME: self.handle_home_button,
            SCREEN_MAPS: self.handle_maps_button,
            SCREEN_MUSIC: self.handle_music_button,
            SCREEN_TELEMETRY: self.handle_telemetry_button,
            SCREEN_TPMS: self.handle_tpms_button,
            SCREEN_SETTINGS: self.handle_settings_button,
        }
        handler = handlers.get(self.current_screen)
        if handler:
            handler(button)
    
    def handle_home_button(self, button: ButtonEvent):
        if button == ButtonEvent.SEEK_UP:
            self.home_selection = (self.home_selection + 1) % len(self.home_apps)
        elif button == ButtonEvent.SEEK_DOWN:
            self.home_selection = (self.home_selection - 1) % len(self.home_apps)
        elif button == ButtonEvent.RES_PLUS:
            # Move up a row (3 items per row)
            self.home_selection = (self.home_selection - 3) % len(self.home_apps)
        elif button == ButtonEvent.SET_MINUS:
            # Move down a row
            self.home_selection = (self.home_selection + 3) % len(self.home_apps)
        elif button == ButtonEvent.ON_OFF:
            self.previous_screen = SCREEN_HOME
            self.current_screen = self.home_apps[self.home_selection]
    
    def handle_maps_button(self, button: ButtonEvent):
        if button == ButtonEvent.CANCEL:
            self.current_screen = SCREEN_HOME
    
    def handle_music_button(self, button: ButtonEvent):
        if button == ButtonEvent.CANCEL:
            self.current_screen = SCREEN_HOME
        elif button == ButtonEvent.ON_OFF:
            self.music.playing = not self.music.playing
        elif button == ButtonEvent.SEEK_UP:
            self.music.position_sec = min(self.music.duration_sec, self.music.position_sec + 10)
        elif button == ButtonEvent.SEEK_DOWN:
            self.music.position_sec = max(0, self.music.position_sec - 10)
        elif button == ButtonEvent.VOL_UP:
            self.music.volume = min(100, self.music.volume + 5)
        elif button == ButtonEvent.VOL_DOWN:
            self.music.volume = max(0, self.music.volume - 5)
    
    def handle_telemetry_button(self, button: ButtonEvent):
        if button == ButtonEvent.CANCEL:
            self.current_screen = SCREEN_HOME
    
    def handle_tpms_button(self, button: ButtonEvent):
        if button == ButtonEvent.CANCEL:
            self.current_screen = SCREEN_HOME
    
    def handle_settings_button(self, button: ButtonEvent):
        if button == ButtonEvent.RES_PLUS:
            if self.settings_edit_mode:
                self.adjust_setting(1)
            else:
                self.settings_selection = (self.settings_selection - 1) % len(self.settings_items)
        elif button == ButtonEvent.SET_MINUS:
            if self.settings_edit_mode:
                self.adjust_setting(-1)
            else:
                self.settings_selection = (self.settings_selection + 1) % len(self.settings_items)
        elif button == ButtonEvent.VOL_UP:
            self.adjust_setting(1)
        elif button == ButtonEvent.VOL_DOWN:
            self.adjust_setting(-1)
        elif button == ButtonEvent.ON_OFF:
            if self.settings_selection == len(self.settings_items) - 1:  # Back
                self.current_screen = SCREEN_HOME
            else:
                self.settings_edit_mode = not self.settings_edit_mode
        elif button == ButtonEvent.CANCEL:
            if self.settings_edit_mode:
                self.settings_edit_mode = False
            else:
                self.current_screen = SCREEN_HOME
    
    def adjust_setting(self, delta: int):
        if self.settings_selection == 0:  # Brightness
            self.settings.brightness = max(10, min(100, self.settings.brightness + delta * 5))
        elif self.settings_selection == 1:  # Shift RPM
            self.settings.shift_rpm = max(4000, min(7500, self.settings.shift_rpm + delta * 100))
        elif self.settings_selection == 2:  # Redline RPM
            self.settings.redline_rpm = max(5000, min(8000, self.settings.redline_rpm + delta * 100))
        elif self.settings_selection == 3:  # Units
            self.settings.use_mph = not self.settings.use_mph
        elif self.settings_selection == 4:  # Tire Low PSI
            self.settings.tire_low_psi = max(20, min(35, self.settings.tire_low_psi + delta * 0.5))
    
    def update_demo(self):
        # RPM oscillation
        self.telemetry.rpm += 40 * self.demo_rpm_dir
        if self.telemetry.rpm >= 6500:
            self.demo_rpm_dir = -1
        elif self.telemetry.rpm <= 800:
            self.demo_rpm_dir = 1
        
        # Gear based on RPM
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
        
        self.telemetry.speed_kmh = int(self.telemetry.rpm * self.telemetry.gear / 100)
        self.telemetry.throttle_percent = min(100, max(0, (self.telemetry.rpm - 800) // 50))
        
        # G-forces
        self.telemetry.g_lateral += random.uniform(-0.08, 0.08)
        self.telemetry.g_lateral = max(-1.2, min(1.2, self.telemetry.g_lateral))
        self.telemetry.g_longitudinal += random.uniform(-0.04, 0.04)
        self.telemetry.g_longitudinal = max(-0.8, min(0.8, self.telemetry.g_longitudinal))
        
        # Music progress
        if self.music.playing:
            self.music.position_sec = (self.music.position_sec + 1) % self.music.duration_sec
    
    def render(self):
        self.display.fill(COLOR_BG)
        
        if self.sleeping:
            self.render_sleep()
        else:
            renderers = {
                SCREEN_HOME: self.render_home,
                SCREEN_MAPS: self.render_maps,
                SCREEN_MUSIC: self.render_music,
                SCREEN_TELEMETRY: self.render_telemetry,
                SCREEN_TPMS: self.render_tpms,
                SCREEN_SETTINGS: self.render_settings,
            }
            renderer = renderers.get(self.current_screen, self.render_home)
            renderer()
        
        # Device focus indicator
        focus_text = f"{'📺 PI ACTIVE' if self.device_focus == 'pi' else '🔘 ESP32 ACTIVE'}"
        focus_color = COLOR_GREEN if self.device_focus == "pi" else COLOR_ORANGE
        focus_surf = self.font_tiny.render(focus_text, True, focus_color)
        self.display.blit(focus_surf, (10, 5))
        
        # Time
        import datetime
        time_str = datetime.datetime.now().strftime("%I:%M %p")
        time_surf = self.font_tiny.render(time_str, True, COLOR_WHITE)
        self.display.blit(time_surf, (DISPLAY_WIDTH - 80, 5))
        
        # Blit to main window
        self.screen.blit(self.display, (0, 0))
    
    def render_sleep(self):
        text = self.font_medium.render("DISPLAY OFF", True, COLOR_DARK_GRAY)
        rect = text.get_rect(center=(DISPLAY_WIDTH // 2, DISPLAY_HEIGHT // 2))
        self.display.blit(text, rect)
        
        hint = self.font_tiny.render("Press any button to wake", True, COLOR_DARK_GRAY)
        hint_rect = hint.get_rect(center=(DISPLAY_WIDTH // 2, DISPLAY_HEIGHT // 2 + 50))
        self.display.blit(hint, hint_rect)
    
    def render_home(self):
        # Title
        title = self.font_medium.render("MX5 TELEMETRY", True, COLOR_WHITE)
        title_rect = title.get_rect(center=(DISPLAY_WIDTH // 2, 60))
        self.display.blit(title, title_rect)
        
        # App grid
        app_width = 150
        app_height = 120
        start_x = (DISPLAY_WIDTH - (app_width * 3 + 40)) // 2
        start_y = 120
        
        for i, app in enumerate(self.home_apps):
            col = i % 3
            row = i // 3
            x = start_x + col * (app_width + 20)
            y = start_y + row * (app_height + 20)
            
            selected = (i == self.home_selection)
            
            # Box
            box_color = COLOR_ACCENT if selected else COLOR_BG_LIGHT
            pygame.draw.rect(self.display, box_color, (x, y, app_width, app_height), border_radius=15)
            if selected:
                pygame.draw.rect(self.display, COLOR_WHITE, (x, y, app_width, app_height), 3, border_radius=15)
            
            # Icon (using emoji placeholder)
            icon = SCREEN_ICONS.get(app, "❓")
            icon_surf = self.font_icon.render(icon, True, COLOR_WHITE)
            icon_rect = icon_surf.get_rect(center=(x + app_width // 2, y + 45))
            self.display.blit(icon_surf, icon_rect)
            
            # Name
            name = SCREEN_NAMES.get(app, app)
            name_surf = self.font_small.render(name, True, COLOR_WHITE)
            name_rect = name_surf.get_rect(center=(x + app_width // 2, y + 95))
            self.display.blit(name_surf, name_rect)
        
        # Navigation hint
        self.draw_nav_hint("◀ SEEK    ▲RES+    ●SELECT    ▼SET-    SEEK▶")
    
    def render_maps(self):
        self.draw_header("🗺️ MAPS")
        
        # Placeholder map
        map_rect = pygame.Rect(50, 70, DISPLAY_WIDTH - 100, DISPLAY_HEIGHT - 140)
        pygame.draw.rect(self.display, COLOR_BG_LIGHT, map_rect, border_radius=10)
        
        # Grid lines
        for i in range(1, 8):
            x = map_rect.x + i * map_rect.width // 8
            pygame.draw.line(self.display, COLOR_DARK_GRAY, (x, map_rect.y), (x, map_rect.bottom))
        for i in range(1, 5):
            y = map_rect.y + i * map_rect.height // 5
            pygame.draw.line(self.display, COLOR_DARK_GRAY, (map_rect.x, y), (map_rect.right, y))
        
        # Car marker
        car_x = map_rect.centerx
        car_y = map_rect.centery
        pygame.draw.circle(self.display, COLOR_RED, (car_x, car_y), 15)
        pygame.draw.circle(self.display, COLOR_WHITE, (car_x, car_y), 10)
        
        # Direction indicator
        angle = math.radians(self.telemetry.steering_angle)
        dx = int(30 * math.sin(angle))
        dy = int(-30 * math.cos(angle))
        pygame.draw.line(self.display, COLOR_RED, (car_x, car_y), (car_x + dx, car_y + dy), 3)
        
        # Info overlay
        speed = self.telemetry.speed_kmh
        if self.settings.use_mph:
            speed = int(speed * 0.621371)
        speed_text = f"{speed} {'MPH' if self.settings.use_mph else 'KMH'}"
        speed_surf = self.font_medium.render(speed_text, True, COLOR_WHITE)
        self.display.blit(speed_surf, (60, DISPLAY_HEIGHT - 120))
        
        self.draw_nav_hint("RES+/SET- = Zoom    SEEK = Pan    CANCEL = Back")
    
    def render_music(self):
        self.draw_header("🎵 MUSIC")
        
        # Album art placeholder
        art_size = 180
        art_x = 100
        art_y = (DISPLAY_HEIGHT - art_size) // 2
        pygame.draw.rect(self.display, COLOR_BG_LIGHT, (art_x, art_y, art_size, art_size), border_radius=15)
        pygame.draw.rect(self.display, COLOR_ACCENT, (art_x, art_y, art_size, art_size), 3, border_radius=15)
        
        # Vinyl record graphic
        pygame.draw.circle(self.display, COLOR_DARK_GRAY, (art_x + art_size // 2, art_y + art_size // 2), 70)
        pygame.draw.circle(self.display, COLOR_BG_LIGHT, (art_x + art_size // 2, art_y + art_size // 2), 20)
        pygame.draw.circle(self.display, COLOR_ACCENT, (art_x + art_size // 2, art_y + art_size // 2), 5)
        
        # Song info
        info_x = 320
        title_surf = self.font_medium.render(self.music.song_title, True, COLOR_WHITE)
        self.display.blit(title_surf, (info_x, 100))
        
        artist_surf = self.font_small.render(self.music.artist, True, COLOR_GRAY)
        self.display.blit(artist_surf, (info_x, 150))
        
        album_surf = self.font_tiny.render(self.music.album, True, COLOR_DARK_GRAY)
        self.display.blit(album_surf, (info_x, 185))
        
        # Playback controls
        ctrl_y = 250
        ctrl_x = info_x
        
        # Previous
        pygame.draw.polygon(self.display, COLOR_GRAY, [(ctrl_x, ctrl_y + 20), (ctrl_x + 20, ctrl_y), (ctrl_x + 20, ctrl_y + 40)])
        pygame.draw.rect(self.display, COLOR_GRAY, (ctrl_x - 5, ctrl_y, 5, 40))
        
        # Play/Pause
        if self.music.playing:
            pygame.draw.rect(self.display, COLOR_WHITE, (ctrl_x + 60, ctrl_y, 12, 40))
            pygame.draw.rect(self.display, COLOR_WHITE, (ctrl_x + 82, ctrl_y, 12, 40))
        else:
            pygame.draw.polygon(self.display, COLOR_WHITE, [(ctrl_x + 60, ctrl_y), (ctrl_x + 100, ctrl_y + 20), (ctrl_x + 60, ctrl_y + 40)])
        
        # Next
        pygame.draw.polygon(self.display, COLOR_GRAY, [(ctrl_x + 140, ctrl_y), (ctrl_x + 160, ctrl_y + 20), (ctrl_x + 140, ctrl_y + 40)])
        pygame.draw.rect(self.display, COLOR_GRAY, (ctrl_x + 160, ctrl_y, 5, 40))
        
        # Progress bar
        prog_y = 320
        prog_width = 400
        pygame.draw.rect(self.display, COLOR_DARK_GRAY, (info_x, prog_y, prog_width, 8), border_radius=4)
        progress = self.music.position_sec / self.music.duration_sec if self.music.duration_sec > 0 else 0
        pygame.draw.rect(self.display, COLOR_ACCENT, (info_x, prog_y, int(prog_width * progress), 8), border_radius=4)
        
        # Time
        pos_min, pos_sec = divmod(self.music.position_sec, 60)
        dur_min, dur_sec = divmod(self.music.duration_sec, 60)
        time_text = f"{pos_min}:{pos_sec:02d} / {dur_min}:{dur_sec:02d}"
        time_surf = self.font_tiny.render(time_text, True, COLOR_GRAY)
        self.display.blit(time_surf, (info_x, prog_y + 15))
        
        # Volume
        vol_text = f"Volume: {self.music.volume}%"
        vol_surf = self.font_tiny.render(vol_text, True, COLOR_GRAY)
        self.display.blit(vol_surf, (info_x + 280, prog_y + 15))
        
        self.draw_nav_hint("VOL+/- = Volume    SEEK = Track    SELECT = Play/Pause    CANCEL = Back")
    
    def render_telemetry(self):
        self.draw_header("📊 TELEMETRY")
        
        # Layout: 2 rows of 4 boxes
        box_width = 180
        box_height = 90
        margin = 15
        start_x = (DISPLAY_WIDTH - (4 * box_width + 3 * margin)) // 2
        start_y = 70
        
        # Convert units
        speed = self.telemetry.speed_kmh
        if self.settings.use_mph:
            speed = int(speed * 0.621371)
        speed_unit = "MPH" if self.settings.use_mph else "KMH"
        
        coolant = self.telemetry.coolant_temp_f
        oil = self.telemetry.oil_temp_f
        temp_unit = "°F" if self.settings.use_fahrenheit else "°C"
        if not self.settings.use_fahrenheit:
            coolant = int((coolant - 32) * 5 / 9)
            oil = int((oil - 32) * 5 / 9)
        
        # RPM color
        rpm_color = COLOR_GREEN
        if self.telemetry.rpm > self.settings.shift_rpm:
            rpm_color = COLOR_RED
        elif self.telemetry.rpm > 4500:
            rpm_color = COLOR_ORANGE
        elif self.telemetry.rpm > 3000:
            rpm_color = COLOR_YELLOW
        
        # Data boxes
        data = [
            ("RPM", str(self.telemetry.rpm), "", rpm_color),
            ("SPEED", str(speed), speed_unit, COLOR_WHITE),
            ("GEAR", "N" if self.telemetry.gear == 0 else str(self.telemetry.gear), "", COLOR_GREEN),
            ("THROTTLE", f"{self.telemetry.throttle_percent}%", "", COLOR_CYAN),
            ("COOLANT", str(coolant), temp_unit, COLOR_RED if coolant > 220 else COLOR_GREEN),
            ("OIL", str(oil), temp_unit, COLOR_RED if oil > 250 else COLOR_GREEN),
            ("FUEL", f"{self.telemetry.fuel_level_percent:.0f}%", "", COLOR_YELLOW),
            ("RANGE", str(self.telemetry.range_miles), "mi", COLOR_WHITE),
        ]
        
        for i, (label, value, unit, color) in enumerate(data):
            col = i % 4
            row = i // 4
            x = start_x + col * (box_width + margin)
            y = start_y + row * (box_height + margin)
            
            self.draw_value_box(x, y, box_width, box_height, label, value, unit, color)
        
        # RPM bar at bottom
        bar_y = DISPLAY_HEIGHT - 100
        bar_height = 25
        bar_x = 50
        bar_width = DISPLAY_WIDTH - 100
        
        pygame.draw.rect(self.display, COLOR_DARK_GRAY, (bar_x, bar_y, bar_width, bar_height), border_radius=5)
        rpm_width = int((self.telemetry.rpm / self.settings.redline_rpm) * bar_width)
        rpm_width = min(bar_width, rpm_width)
        pygame.draw.rect(self.display, rpm_color, (bar_x, bar_y, rpm_width, bar_height), border_radius=5)
        
        # Shift marker
        shift_x = bar_x + int((self.settings.shift_rpm / self.settings.redline_rpm) * bar_width)
        pygame.draw.line(self.display, COLOR_WHITE, (shift_x, bar_y - 5), (shift_x, bar_y + bar_height + 5), 2)
        
        self.draw_nav_hint("CANCEL = Back")
    
    def render_tpms(self):
        self.draw_header("🔧 TIRE PRESSURE (TPMS)")
        
        # Car outline in center
        car_width = 200
        car_height = 350
        car_x = (DISPLAY_WIDTH - car_width) // 2
        car_y = 80
        
        pygame.draw.rect(self.display, COLOR_BG_LIGHT, (car_x, car_y, car_width, car_height), border_radius=30)
        pygame.draw.rect(self.display, COLOR_DARK_GRAY, (car_x, car_y, car_width, car_height), 3, border_radius=30)
        
        # Windows
        pygame.draw.rect(self.display, COLOR_DARK_GRAY, (car_x + 30, car_y + 40, car_width - 60, 80), border_radius=10)
        pygame.draw.rect(self.display, COLOR_DARK_GRAY, (car_x + 30, car_y + 220, car_width - 60, 80), border_radius=10)
        
        # Tire positions
        positions = [
            ("FL", car_x - 120, car_y + 30, 0),
            ("FR", car_x + car_width + 20, car_y + 30, 1),
            ("RL", car_x - 120, car_y + 220, 2),
            ("RR", car_x + car_width + 20, car_y + 220, 3),
        ]
        
        for label, x, y, idx in positions:
            pressure = self.telemetry.tire_pressure[idx]
            temp = self.telemetry.tire_temp[idx]
            battery = self.telemetry.tire_battery[idx]
            
            # Color based on pressure
            if pressure < self.settings.tire_low_psi - 3 or pressure > self.settings.tire_high_psi + 3:
                color = COLOR_RED
            elif pressure < self.settings.tire_low_psi or pressure > self.settings.tire_high_psi:
                color = COLOR_YELLOW
            else:
                color = COLOR_GREEN
            
            # Tire box
            box_width = 100
            box_height = 100
            pygame.draw.rect(self.display, COLOR_BG_LIGHT, (x, y, box_width, box_height), border_radius=10)
            pygame.draw.rect(self.display, color, (x, y, box_width, box_height), 3, border_radius=10)
            
            # Label
            label_surf = self.font_tiny.render(label, True, COLOR_GRAY)
            label_rect = label_surf.get_rect(center=(x + box_width // 2, y + 15))
            self.display.blit(label_surf, label_rect)
            
            # Pressure
            psi_surf = self.font_medium.render(f"{pressure:.1f}", True, color)
            psi_rect = psi_surf.get_rect(center=(x + box_width // 2, y + 45))
            self.display.blit(psi_surf, psi_rect)
            
            psi_unit = self.font_tiny.render("PSI", True, COLOR_GRAY)
            self.display.blit(psi_unit, (x + box_width // 2 - 12, y + 62))
            
            # Temp
            temp_surf = self.font_tiny.render(f"{temp:.0f}°F", True, COLOR_GRAY)
            temp_rect = temp_surf.get_rect(center=(x + box_width // 2, y + 85))
            self.display.blit(temp_surf, temp_rect)
        
        self.draw_nav_hint("CANCEL = Back")
    
    def render_settings(self):
        self.draw_header("⚙️ SETTINGS")
        
        start_y = 80
        item_height = 55
        
        for i, item in enumerate(self.settings_items):
            y = start_y + i * item_height
            selected = (i == self.settings_selection)
            editing = selected and self.settings_edit_mode
            
            # Selection background
            if selected:
                pygame.draw.rect(self.display, COLOR_BG_LIGHT, (50, y - 5, DISPLAY_WIDTH - 100, 45), border_radius=8)
            
            # Item name
            color = COLOR_YELLOW if editing else (COLOR_WHITE if selected else COLOR_GRAY)
            name_surf = self.font_small.render(item, True, color)
            self.display.blit(name_surf, (80, y + 5))
            
            # Value
            value = ""
            if i == 0:
                value = f"{self.settings.brightness}%"
            elif i == 1:
                value = str(self.settings.shift_rpm)
            elif i == 2:
                value = str(self.settings.redline_rpm)
            elif i == 3:
                value = "MPH" if self.settings.use_mph else "KMH"
            elif i == 4:
                value = f"{self.settings.tire_low_psi:.1f}"
            
            if value:
                value_surf = self.font_small.render(value, True, color)
                value_rect = value_surf.get_rect(right=DISPLAY_WIDTH - 80, top=y + 5)
                self.display.blit(value_surf, value_rect)
            
            # Edit indicator
            if editing:
                indicator = self.font_small.render("◄►", True, COLOR_YELLOW)
                self.display.blit(indicator, (60, y + 5))
        
        self.draw_nav_hint("UP/DN = Navigate    SELECT = Edit    VOL+/- = Adjust    CANCEL = Back")
    
    def draw_header(self, title: str):
        pygame.draw.rect(self.display, COLOR_BG_LIGHT, (0, 25, DISPLAY_WIDTH, 40))
        title_surf = self.font_small.render(title, True, COLOR_WHITE)
        title_rect = title_surf.get_rect(center=(DISPLAY_WIDTH // 2, 45))
        self.display.blit(title_surf, title_rect)
        
        back_surf = self.font_tiny.render("◀ CANCEL", True, COLOR_GRAY)
        self.display.blit(back_surf, (DISPLAY_WIDTH - 100, 35))
    
    def draw_nav_hint(self, text: str):
        pygame.draw.rect(self.display, COLOR_BG_LIGHT, (0, DISPLAY_HEIGHT - 35, DISPLAY_WIDTH, 35))
        hint_surf = self.font_tiny.render(text, True, COLOR_GRAY)
        hint_rect = hint_surf.get_rect(center=(DISPLAY_WIDTH // 2, DISPLAY_HEIGHT - 17))
        self.display.blit(hint_surf, hint_rect)
    
    def draw_value_box(self, x, y, width, height, label, value, unit, color):
        pygame.draw.rect(self.display, COLOR_BG_LIGHT, (x, y, width, height), border_radius=10)
        pygame.draw.rect(self.display, COLOR_DARK_GRAY, (x, y, width, height), 2, border_radius=10)
        
        label_surf = self.font_tiny.render(label, True, COLOR_GRAY)
        label_rect = label_surf.get_rect(center=(x + width // 2, y + 18))
        self.display.blit(label_surf, label_rect)
        
        value_surf = self.font_medium.render(value, True, color)
        value_rect = value_surf.get_rect(center=(x + width // 2, y + height // 2 + 10))
        self.display.blit(value_surf, value_rect)
        
        if unit:
            unit_surf = self.font_tiny.render(unit, True, COLOR_GRAY)
            unit_rect = unit_surf.get_rect(center=(x + width // 2, y + height - 12))
            self.display.blit(unit_surf, unit_rect)
    
    def draw_control_panel(self):
        panel_x = DISPLAY_WIDTH + 10
        panel_y = 10
        
        title = self.font_small.render("SWC Controls", True, COLOR_WHITE)
        self.screen.blit(title, (panel_x, panel_y))
        
        controls = [
            ("M/Tab", "MODE", ButtonEvent.MODE),
            ("Enter", "SELECT", ButtonEvent.ON_OFF),
            ("Esc/B", "BACK", ButtonEvent.CANCEL),
            ("↑/W", "UP", ButtonEvent.RES_PLUS),
            ("↓/S", "DOWN", ButtonEvent.SET_MINUS),
            ("→/D", "RIGHT", ButtonEvent.SEEK_UP),
            ("←/A", "LEFT", ButtonEvent.SEEK_DOWN),
            ("+/=", "VOL+", ButtonEvent.VOL_UP),
            ("-", "VOL-", ButtonEvent.VOL_DOWN),
            ("Space", "MUTE", ButtonEvent.MUTE),
        ]
        
        y = panel_y + 35
        for key, action, btn in controls:
            is_recent = (btn == self.last_button and 
                        pygame.time.get_ticks() - self.button_display_time < 500)
            
            bg_color = COLOR_YELLOW if is_recent else COLOR_DARK_GRAY
            text_color = (0, 0, 0) if is_recent else COLOR_WHITE
            
            pygame.draw.rect(self.screen, bg_color, (panel_x, y, 80, 20), border_radius=3)
            
            key_text = self.font_tiny.render(key, True, text_color)
            self.screen.blit(key_text, (panel_x + 5, y + 2))
            
            action_text = self.font_tiny.render(action, True, COLOR_GRAY)
            self.screen.blit(action_text, (panel_x + 90, y + 2))
            
            y += 25
        
        # Demo mode
        y += 15
        demo_text = f"Demo: {'ON' if self.demo_mode else 'OFF'} (T)"
        demo_color = COLOR_GREEN if self.demo_mode else COLOR_GRAY
        demo_surf = self.font_tiny.render(demo_text, True, demo_color)
        self.screen.blit(demo_surf, (panel_x, y))
        
        # Focus indicator
        y += 30
        focus_text = f"Focus: {self.device_focus.upper()}"
        focus_color = COLOR_GREEN if self.device_focus == "pi" else COLOR_ORANGE
        focus_surf = self.font_tiny.render(focus_text, True, focus_color)
        self.screen.blit(focus_surf, (panel_x, y))
    
    def draw_status_bar(self):
        status_y = DISPLAY_HEIGHT + 10
        
        screen_name = SCREEN_NAMES.get(self.current_screen, self.current_screen)
        screen_text = self.font_small.render(f"Screen: {screen_name}", True, COLOR_WHITE)
        self.screen.blit(screen_text, (10, status_y))
        
        if self.sleeping:
            sleep_text = self.font_small.render("SLEEPING", True, COLOR_YELLOW)
            self.screen.blit(sleep_text, (250, status_y))
        
        tel_text = f"RPM:{self.telemetry.rpm}  SPD:{self.telemetry.speed_kmh}km/h  Gear:{self.telemetry.gear}"
        tel_surf = self.font_tiny.render(tel_text, True, COLOR_GRAY)
        self.screen.blit(tel_surf, (10, status_y + 30))


if __name__ == "__main__":
    print("Raspberry Pi Display UI Simulator")
    print("=" * 45)
    print("Keyboard Controls (SWC Buttons):")
    print("  M/Tab     = MODE (switch Pi/ESP32 focus)")
    print("  Enter     = SELECT")
    print("  Esc/B     = CANCEL/BACK")
    print("  ↑/W       = UP")
    print("  ↓/S       = DOWN")
    print("  →/D       = RIGHT/NEXT")
    print("  ←/A       = LEFT/PREV")
    print("  +/=       = VOL+")
    print("  -         = VOL-")
    print("  Space     = MUTE (sleep toggle)")
    print("  T         = Toggle demo mode")
    print("=" * 45)
    
    sim = PiSimulator()
    sim.run()
