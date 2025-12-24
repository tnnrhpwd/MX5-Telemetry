"""
Screen Base Class

Base class for all UI screens with common functionality.
"""

from abc import ABC, abstractmethod
import pygame
from typing import Optional, Tuple

# Import will be relative when used
# from ..swc_handler import ButtonEvent
# from ..telemetry_data import TelemetryData, UISettings


class BaseScreen(ABC):
    """Abstract base class for all screens"""
    
    # Display dimensions - will be set from actual screen size
    # These are defaults, updated in __init__ from screen.get_size()
    WIDTH = 800
    HEIGHT = 480
    
    # Common colors
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
    
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        # Get actual screen dimensions
        self.WIDTH, self.HEIGHT = screen.get_size()
        self.font_large = pygame.font.Font(None, 72)
        self.font_medium = pygame.font.Font(None, 48)
        self.font_small = pygame.font.Font(None, 32)
        self.font_tiny = pygame.font.Font(None, 24)
    
    @abstractmethod
    def render(self, telemetry, settings):
        """Render the screen"""
        pass
    
    @abstractmethod
    def handle_button(self, button) -> Optional[str]:
        """
        Handle button press.
        Returns: New screen name to navigate to, or None to stay on current screen
        """
        pass
    
    def draw_header(self, title: str, show_back: bool = True):
        """Draw common header bar"""
        # Header background
        pygame.draw.rect(self.screen, self.COLOR_BG_LIGHT, (0, 0, self.WIDTH, 50))
        
        # Title
        title_surf = self.font_medium.render(title, True, self.COLOR_WHITE)
        title_rect = title_surf.get_rect(center=(self.WIDTH // 2, 25))
        self.screen.blit(title_surf, title_rect)
        
        # Back indicator
        if show_back:
            back_surf = self.font_small.render("◀ CANCEL", True, self.COLOR_GRAY)
            self.screen.blit(back_surf, (self.WIDTH - 120, 15))
    
    def draw_nav_hint(self, hints: str):
        """Draw navigation hints at bottom"""
        pygame.draw.rect(self.screen, self.COLOR_BG_LIGHT, (0, self.HEIGHT - 40, self.WIDTH, 40))
        hint_surf = self.font_tiny.render(hints, True, self.COLOR_GRAY)
        hint_rect = hint_surf.get_rect(center=(self.WIDTH // 2, self.HEIGHT - 20))
        self.screen.blit(hint_surf, hint_rect)
    
    def draw_value_box(self, x: int, y: int, width: int, height: int,
                       label: str, value: str, unit: str = "",
                       color: Tuple[int, int, int] = None):
        """Draw a value display box"""
        if color is None:
            color = self.COLOR_WHITE
        
        # Box background
        pygame.draw.rect(self.screen, self.COLOR_BG_LIGHT, (x, y, width, height), border_radius=8)
        pygame.draw.rect(self.screen, self.COLOR_DARK_GRAY, (x, y, width, height), 2, border_radius=8)
        
        # Label
        label_surf = self.font_tiny.render(label, True, self.COLOR_GRAY)
        label_rect = label_surf.get_rect(center=(x + width // 2, y + 20))
        self.screen.blit(label_surf, label_rect)
        
        # Value
        value_surf = self.font_medium.render(value, True, color)
        value_rect = value_surf.get_rect(center=(x + width // 2, y + height // 2 + 5))
        self.screen.blit(value_surf, value_rect)
        
        # Unit
        if unit:
            unit_surf = self.font_tiny.render(unit, True, self.COLOR_GRAY)
            unit_rect = unit_surf.get_rect(center=(x + width // 2, y + height - 15))
            self.screen.blit(unit_surf, unit_rect)
    
    def draw_progress_bar(self, x: int, y: int, width: int, height: int,
                          value: float, max_value: float,
                          color: Tuple[int, int, int] = None,
                          bg_color: Tuple[int, int, int] = None):
        """Draw a horizontal progress bar"""
        if color is None:
            color = self.COLOR_ACCENT
        if bg_color is None:
            bg_color = self.COLOR_DARK_GRAY
        
        # Background
        pygame.draw.rect(self.screen, bg_color, (x, y, width, height), border_radius=4)
        
        # Fill
        fill_width = int((value / max_value) * width) if max_value > 0 else 0
        fill_width = max(0, min(width, fill_width))
        if fill_width > 0:
            pygame.draw.rect(self.screen, color, (x, y, fill_width, height), border_radius=4)
    
    def draw_gauge_arc(self, cx: int, cy: int, radius: int, thickness: int,
                       start_angle: float, end_angle: float, value_angle: float,
                       bg_color: Tuple[int, int, int] = None,
                       fg_color: Tuple[int, int, int] = None):
        """Draw an arc gauge"""
        import math
        
        if bg_color is None:
            bg_color = self.COLOR_DARK_GRAY
        if fg_color is None:
            fg_color = self.COLOR_ACCENT
        
        # Draw background arc
        for angle in range(int(start_angle), int(end_angle) + 1, 2):
            rad = math.radians(angle)
            for r in range(radius - thickness // 2, radius + thickness // 2):
                x = cx + int(r * math.cos(rad))
                y = cy + int(r * math.sin(rad))
                if 0 <= x < self.WIDTH and 0 <= y < self.HEIGHT:
                    self.screen.set_at((x, y), bg_color)
        
        # Draw value arc
        for angle in range(int(start_angle), int(min(value_angle, end_angle)) + 1, 2):
            rad = math.radians(angle)
            for r in range(radius - thickness // 2, radius + thickness // 2):
                x = cx + int(r * math.cos(rad))
                y = cy + int(r * math.sin(rad))
                if 0 <= x < self.WIDTH and 0 <= y < self.HEIGHT:
                    self.screen.set_at((x, y), fg_color)
