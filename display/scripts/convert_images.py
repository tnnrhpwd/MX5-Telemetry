#!/usr/bin/env python3
"""
Convert images to C header files for ESP32-S3 display (RGB565 BIG endian format)
Display: 360x360 pixels, round
"""

from PIL import Image
import os
import sys

def rgb888_to_rgb565_be(r, g, b):
    """Convert RGB888 to RGB565 Big Endian (for ST77916 display)"""
    # Convert to RGB565
    r5 = (r >> 3) & 0x1F
    g6 = (g >> 2) & 0x3F
    b5 = (b >> 3) & 0x1F
    rgb565 = (r5 << 11) | (g6 << 5) | b5
    # Swap bytes for Big Endian
    return ((rgb565 & 0xFF) << 8) | ((rgb565 >> 8) & 0xFF)

def create_circular_mask(size):
    """Create a circular mask for round display"""
    from PIL import ImageDraw
    mask = Image.new('L', (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size-1, size-1), fill=255)
    return mask

def convert_image_to_header(input_path, output_path, var_name, target_size=360, apply_circular_mask=False):
    """Convert image to C header file with RGB565 BE format"""
    
    print(f"Converting: {input_path}")
    print(f"Output: {output_path}")
    
    # Open and resize image
    img = Image.open(input_path)
    
    # Convert to RGB if necessary
    if img.mode != 'RGB':
        img = img.convert('RGB')
    
    # Calculate crop to make it square (center crop)
    width, height = img.size
    min_dim = min(width, height)
    left = (width - min_dim) // 2
    top = (height - min_dim) // 2
    right = left + min_dim
    bottom = top + min_dim
    img = img.crop((left, top, right, bottom))
    
    # Resize to target size
    img = img.resize((target_size, target_size), Image.Resampling.LANCZOS)
    
    # Apply circular mask if requested (for round display)
    if apply_circular_mask:
        mask = create_circular_mask(target_size)
        # Create black background
        background = Image.new('RGB', (target_size, target_size), (0, 0, 0))
        background.paste(img, mask=mask)
        img = background
    
    # Get pixel data
    pixels = list(img.getdata())
    
    # Convert to RGB565 BE
    rgb565_data = []
    for r, g, b in pixels:
        rgb565_data.append(rgb888_to_rgb565_be(r, g, b))
    
    # Generate C header file
    with open(output_path, 'w') as f:
        f.write(f"// Auto-generated image data for ESP32-S3 display\n")
        f.write(f"// Source: {os.path.basename(input_path)}\n")
        f.write(f"// Size: {target_size}x{target_size} pixels\n")
        f.write(f"// Format: RGB565 Big Endian\n")
        f.write(f"#pragma once\n\n")
        f.write(f"#include <stdint.h>\n\n")
        f.write(f"#define {var_name.upper()}_WIDTH {target_size}\n")
        f.write(f"#define {var_name.upper()}_HEIGHT {target_size}\n\n")
        f.write(f"const uint16_t {var_name}[{target_size * target_size}] PROGMEM = {{\n")
        
        # Write data in rows for readability
        for row in range(target_size):
            f.write("    ")
            for col in range(target_size):
                idx = row * target_size + col
                f.write(f"0x{rgb565_data[idx]:04X}")
                if idx < len(rgb565_data) - 1:
                    f.write(", ")
            f.write("\n")
        
        f.write("};\n")
    
    print(f"Generated {var_name}: {target_size}x{target_size} = {len(rgb565_data)} pixels")
    file_size = os.path.getsize(output_path)
    print(f"Header file size: {file_size / 1024:.1f} KB")
    data_size = len(rgb565_data) * 2
    print(f"Image data size: {data_size / 1024:.1f} KB")

def main():
    # Paths
    boot_logo_src = r"C:\Users\tanne\OneDrive\Pictures\HD-wallpaper-mazda-mx-5-carbon-badge-emblem-logo-miata2.jpg"
    background_src = r"C:\Users\tanne\OneDrive\Pictures\Gemini_Generated_Image_m06fjfm06fjfm06f (2) - Copy.jpg"
    
    output_dir = r"c:\Users\tanne\Documents\Github\MX5-Telemetry\display\include"
    
    # Convert boot logo (smaller size for faster loading during startup)
    convert_image_to_header(
        boot_logo_src,
        os.path.join(output_dir, "boot_logo.h"),
        "boot_logo_data",
        target_size=200,  # Smaller for boot logo
        apply_circular_mask=True
    )
    
    # Convert background (full size for display)
    convert_image_to_header(
        background_src,
        os.path.join(output_dir, "background_image.h"),
        "background_data",
        target_size=360,  # Full display size
        apply_circular_mask=True
    )
    
    print("\nConversion complete!")
    print("Include these headers in your project and use LCD_DrawImage() to display them.")

if __name__ == "__main__":
    main()
