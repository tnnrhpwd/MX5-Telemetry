# Display Module Local Libraries

This folder is for display-specific libraries.

For global shared libraries, use the root `/lib` folder.

## Recommended Libraries

The following are automatically installed via `platformio.ini`:

- **LovyanGFX** - High-performance graphics library for ESP32
- **LVGL** - Light and Versatile Graphics Library for UI
- **Adafruit FT6206** - Touch screen driver

## Custom Libraries

Place any custom display-specific libraries here:

```
lib/
├── DisplayDriver/     # Custom display driver tweaks
├── TelemetryUI/       # UI components for telemetry
└── AudioFeedback/     # Audio alert system
```
