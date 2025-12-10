#!/usr/bin/env python3
"""Generate a simple icon for MX5 Telemetry app"""
import pygame
import os

# Initialize pygame
pygame.init()

# Create a 128x128 icon
size = 128
surface = pygame.Surface((size, size), pygame.SRCALPHA)

# Colors
bg_color = (22, 22, 32)
accent_color = (100, 140, 255)
red_color = (255, 70, 85)
white_color = (245, 245, 250)

# Fill background with rounded effect
pygame.draw.rect(surface, bg_color, (0, 0, size, size))

# Draw a stylized "5" for MX5
font = pygame.font.Font(None, 90)
txt = font.render("5", True, accent_color)
surface.blit(txt, txt.get_rect(center=(size//2, size//2 - 10)))

# Draw small "MX" above
font_small = pygame.font.Font(None, 32)
txt = font_small.render("MX", True, white_color)
surface.blit(txt, txt.get_rect(center=(size//2, 25)))

# Draw RPM-style arc at bottom
import math
cx, cy = size // 2, size - 20
for i in range(0, 180, 10):
    angle = math.radians(180 + i)
    x1 = int(cx + math.cos(angle) * 45)
    y1 = int(cy + math.sin(angle) * 20)
    x2 = int(cx + math.cos(angle) * 50)
    y2 = int(cy + math.sin(angle) * 22)
    color = red_color if i > 140 else accent_color
    pygame.draw.line(surface, color, (x1, y1), (x2, y2), 3)

# Save icon
script_dir = os.path.dirname(os.path.abspath(__file__))
icon_path = os.path.join(script_dir, "icon.png")
pygame.image.save(surface, icon_path)
print(f"Icon saved to: {icon_path}")

pygame.quit()
