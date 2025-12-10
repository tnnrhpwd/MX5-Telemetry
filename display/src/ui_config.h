/*
 * ============================================================================
 * MX5-Telemetry Display UI Configuration
 * ============================================================================
 * Shared color definitions and constants matching the Python simulator
 * ============================================================================
 */

#ifndef UI_CONFIG_H
#define UI_CONFIG_H

#include <stdint.h>

// =============================================================================
// Display Size
// =============================================================================
#define DISPLAY_SIZE 360
#define CENTER (DISPLAY_SIZE / 2)

// =============================================================================
// Modern Color Palette (RGB565 format for LovyanGFX)
// =============================================================================
// Helper macro to convert RGB888 to RGB565
#define RGB565(r, g, b) ((((r) & 0xF8) << 8) | (((g) & 0xFC) << 3) | ((b) >> 3))

// Background colors
#define COLOR_BG            RGB565(12, 12, 18)       // Deep dark background
#define COLOR_BG_DARK       RGB565(8, 8, 12)         // Even darker
#define COLOR_BG_CARD       RGB565(22, 22, 32)       // Card/panel background
#define COLOR_BG_ELEVATED   RGB565(32, 32, 45)       // Elevated elements

// Text colors
#define COLOR_WHITE         RGB565(245, 245, 250)    // Soft white
#define COLOR_GRAY          RGB565(140, 140, 160)    // Muted gray
#define COLOR_DARK_GRAY     RGB565(55, 55, 70)       // Dark elements

// Accent colors
#define COLOR_RED           RGB565(255, 70, 85)      // Modern red
#define COLOR_GREEN         RGB565(50, 215, 130)     // Modern green (mint)
#define COLOR_BLUE          RGB565(65, 135, 255)     // Bright blue
#define COLOR_YELLOW        RGB565(255, 210, 60)     // Warm yellow
#define COLOR_ORANGE        RGB565(255, 140, 50)     // Vibrant orange
#define COLOR_CYAN          RGB565(50, 220, 255)     // Bright cyan
#define COLOR_ACCENT        RGB565(100, 140, 255)    // Primary accent (blue-purple)
#define COLOR_PURPLE        RGB565(175, 130, 255)    // Soft purple
#define COLOR_PINK          RGB565(255, 100, 180)    // Accent pink
#define COLOR_TEAL          RGB565(45, 200, 190)     // Teal accent

// =============================================================================
// Screen Enumeration
// =============================================================================
enum Screen {
    SCREEN_OVERVIEW = 0,
    SCREEN_RPM_SPEED = 1,
    SCREEN_TPMS = 2,
    SCREEN_ENGINE = 3,
    SCREEN_GFORCE = 4,
    SCREEN_DIAGNOSTICS = 5,
    SCREEN_SYSTEM = 6,
    SCREEN_SETTINGS = 7,
    SCREEN_COUNT = 8
};

// =============================================================================
// Button Events (SWC Steering Wheel Controls)
// =============================================================================
enum ButtonEvent {
    BTN_NONE = 0,
    BTN_VOL_UP,
    BTN_VOL_DOWN,
    BTN_ON_OFF,
    BTN_CANCEL,
    BTN_RES_PLUS,
    BTN_SET_MINUS
};

// =============================================================================
// Telemetry Data Structure
// =============================================================================
struct TelemetryData {
    uint16_t rpm = 0;
    uint16_t speed_kmh = 0;
    uint8_t gear = 0;
    uint8_t throttle_percent = 0;
    uint8_t brake_percent = 0;
    int16_t coolant_temp_f = 0;
    int16_t oil_temp_f = 0;
    float oil_pressure_psi = 0.0f;
    int16_t intake_temp_f = 0;
    int16_t ambient_temp_f = 0;
    float fuel_level_percent = 0.0f;
    float voltage = 0.0f;
    float tire_pressure[4] = {0.0f, 0.0f, 0.0f, 0.0f};
    float tire_temp[4] = {0.0f, 0.0f, 0.0f, 0.0f};
    float g_lateral = 0.0f;
    float g_longitudinal = 0.0f;
    uint32_t lap_time_ms = 0;
    uint32_t best_lap_ms = 0;
    
    // Diagnostics data
    bool check_engine_light = false;
    bool abs_warning = false;
    bool traction_control_off = false;
    bool traction_control_active = false;
    bool oil_pressure_warning = false;
    bool battery_warning = false;
    bool door_ajar = false;
    bool seatbelt_warning = false;
    bool airbag_warning = false;
    bool brake_warning = false;
    bool high_beam_on = false;
    bool fog_light_on = false;
    
    // DTC codes (up to 8)
    char dtc_codes[8][6] = {"", "", "", "", "", "", "", ""};  // e.g. "P0301"
    uint8_t dtc_count = 0;
    
    // Wheel slip (for traction display)
    float wheel_slip[4] = {0.0f, 0.0f, 0.0f, 0.0f};  // FL, FR, RL, RR as % slip
};

// =============================================================================
// Settings Structure
// =============================================================================
struct DisplaySettings {
    uint8_t brightness = 80;
    uint16_t shift_rpm = 6500;
    uint16_t redline_rpm = 7200;
    bool use_mph = true;
    float tire_low_psi = 28.0f;
    float tire_high_psi = 36.0f;
    int16_t coolant_warn_f = 220;
    int16_t oil_warn_f = 260;
};

// =============================================================================
// Screen Names
// =============================================================================
const char* const SCREEN_NAMES[] = {
    "Overview",
    "RPM / Speed",
    "TPMS",
    "Engine",
    "G-Force",
    "Diagnostics",
    "System",
    "Settings"
};

#endif // UI_CONFIG_H
