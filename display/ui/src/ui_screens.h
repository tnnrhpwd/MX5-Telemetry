/**
 * @file ui_screens.h
 * @brief Screen definitions for ESP32-S3 Round Display UI
 * 
 * This file defines the UI screens and their layouts for the
 * 1.85" round display (360x360 pixels).
 */

#ifndef UI_SCREENS_H
#define UI_SCREENS_H

#include <Arduino.h>

// Display dimensions
#define DISPLAY_WIDTH  360
#define DISPLAY_HEIGHT 360
#define DISPLAY_CENTER_X 180
#define DISPLAY_CENTER_Y 180

// Screen IDs
typedef enum {
    SCREEN_RPM_GAUGE = 0,
    SCREEN_SPEEDOMETER,
    SCREEN_TPMS,
    SCREEN_ENGINE_TEMPS,
    SCREEN_GFORCE,
    SCREEN_SETTINGS,
    SCREEN_COUNT  // Total number of screens
} ScreenID;

// Color definitions (RGB565)
#define COLOR_BLACK       0x0000
#define COLOR_WHITE       0xFFFF
#define COLOR_RED         0xF800
#define COLOR_GREEN       0x07E0
#define COLOR_BLUE        0x001F
#define COLOR_YELLOW      0xFFE0
#define COLOR_ORANGE      0xFD20
#define COLOR_CYAN        0x07FF
#define COLOR_MAGENTA     0xF81F
#define COLOR_DARK_GRAY   0x4208
#define COLOR_LIGHT_GRAY  0xC618

// RPM zone colors
#define COLOR_RPM_IDLE    COLOR_BLUE     // 0-1999 RPM
#define COLOR_RPM_ECO     COLOR_GREEN    // 2000-2999 RPM
#define COLOR_RPM_NORMAL  COLOR_YELLOW   // 3000-4499 RPM
#define COLOR_RPM_SPIRITED COLOR_ORANGE  // 4500-5499 RPM
#define COLOR_RPM_HIGH    COLOR_RED      // 5500+ RPM

// Screen layout constants
#define GAUGE_RADIUS      150
#define GAUGE_THICKNESS   20
#define CENTER_CIRCLE_R   60

// Settings menu items
typedef enum {
    SETTING_BRIGHTNESS = 0,
    SETTING_SHIFT_RPM,
    SETTING_REDLINE_RPM,
    SETTING_UNITS,
    SETTING_BACK,
    SETTING_COUNT
} SettingID;

// Settings menu item names
static const char* SETTING_NAMES[] = {
    "Brightness",
    "Shift RPM",
    "Redline RPM",
    "Units",
    "Back"
};

// Telemetry data structure
typedef struct {
    uint16_t rpm;
    uint16_t speed_kmh;
    uint8_t gear;
    int16_t coolant_temp;
    int16_t oil_temp;
    int16_t ambient_temp;
    uint8_t throttle_percent;
    bool brake_active;
    float tire_pressure[4];  // FL, FR, RL, RR
    float tire_temp[4];
    uint8_t tire_battery[4];
    float g_lateral;
    float g_longitudinal;
} TelemetryData;

// UI Settings structure
typedef struct {
    uint8_t brightness;      // 0-100%
    uint16_t shift_rpm;      // RPM to trigger shift light
    uint16_t redline_rpm;    // Maximum RPM
    bool use_mph;            // true = MPH, false = KMH
} UISettings;

#endif // UI_SCREENS_H
