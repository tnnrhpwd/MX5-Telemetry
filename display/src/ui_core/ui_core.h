/**
 * @file ui_core.h
 * @brief Shared, hardware-agnostic UI core for the MX5 ESP32-S3 round display.
 *
 * This module owns ALL screen rendering and navigation state. The exact same
 * `ui_core.cpp` is compiled:
 *   - into the ESP32 firmware (renders through the real ST77916 driver), and
 *   - into the native desktop simulator (renders through a mock LCD backend).
 *
 * Edit `ui_core.cpp` and both the flashed device and the simulator change.
 */

#ifndef UI_CORE_H
#define UI_CORE_H

#include "ui_core_platform.h"

#ifdef UI_CORE_NATIVE
  #include "native_display.h"   // Mock LCD_* API (native simulator)
#else
  #include "Display_ST77916.h"  // Real ST77916 QSPI driver (ESP32)
#endif

#include "background_image.h"

// ============================================================================
// Screen dimensions (Waveshare 1.85" 360x360 round display)
// ============================================================================
#define SCREEN_WIDTH  360
#define SCREEN_HEIGHT 360
#define CENTER_X      (SCREEN_WIDTH / 2)
#define CENTER_Y      (SCREEN_HEIGHT / 2)

// Standard corner radius for UI elements
#define CARD_RADIUS 8
#define BAR_RADIUS 4

// ============================================================================
// Colors
//
// Every colour is a runtime value so the display can follow the phone app's
// theme (scheme + dark/light). The macros below keep every existing call site
// unchanged while reading from the active palette.
//
// Defaults are the dark "aurora" scheme, which is also what the firmware uses
// when the phone has never connected.
// ============================================================================
struct ThemePalette {
    uint16_t bg;
    uint16_t bgDark;
    uint16_t bgCard;
    uint16_t bgElevated;
    uint16_t text;
    uint16_t textDim;
    uint16_t darkGray;
    uint16_t red;
    uint16_t orange;
    uint16_t yellow;
    uint16_t green;
    uint16_t blue;
    uint16_t cyan;
    uint16_t purple;
    uint16_t accent;
};

extern ThemePalette g_theme;

// Active theme identity (mirrored from the phone app; persisted in NVS)
extern char themeScheme[16];
extern bool themeDark;

void applyTheme(const char* scheme, bool dark);
void applyDefaultTheme();

#define COLOR_BG          (g_theme.bg)
#define COLOR_BG_DARK     (g_theme.bgDark)
#define COLOR_BG_CARD     (g_theme.bgCard)
#define COLOR_BG_ELEVATED (g_theme.bgElevated)
#define MX5_RED           (g_theme.red)
#define MX5_ORANGE        (g_theme.orange)
#define MX5_YELLOW        (g_theme.yellow)
#define MX5_GREEN         (g_theme.green)
#define MX5_BLUE          (g_theme.blue)
#define MX5_CYAN          (g_theme.cyan)
#define MX5_PURPLE        (g_theme.purple)
#define MX5_WHITE         (g_theme.text)
#define MX5_BLACK         COLOR_BG
#define MX5_GRAY          (g_theme.textDim)
#define MX5_DARKGRAY      (g_theme.darkGray)
#define MX5_ACCENT        (g_theme.accent)

// Arduino LED strip matching colors (pure RGB values)
// These MUST match arduino/src/main.cpp getRPMColor() for visual consistency
#define LED_BLUE      RGB565(0, 0, 255)       // 0-1999 RPM
#define LED_GREEN     RGB565(0, 255, 0)       // 2000-2999 RPM
#define LED_YELLOW    RGB565(255, 255, 0)     // 3000-4499 RPM
#define LED_ORANGE    RGB565(255, 128, 0)     // 4500-5499 RPM
#define LED_RED       RGB565(255, 0, 0)       // 5500+ RPM

// ============================================================================
// Telemetry data structure
// ============================================================================
struct TelemetryData {
    float rpm;
    float speed;
    int gear;
    float throttle;
    float brake;
    float coolantTemp;
    float oilTemp;
    float oilPressure;
    float fuelLevel;
    float ambientTemp;
    float tirePressure[4];  // FL, FR, RL, RR
    float tireTemp[4];      // FL, FR, RL, RR
    float gForceX;          // Lateral (left/right) - raw accelerometer
    float gForceY;          // Longitudinal (accel/brake) - raw accelerometer
    float gForceZ;          // Vertical - raw accelerometer
    float linearAccelX;     // Lateral pure acceleration (gravity removed)
    float linearAccelY;     // Longitudinal pure acceleration (gravity removed)
    // MPG and range data (calculated on Pi)
    float averageMPG;       // Average fuel efficiency (miles per gallon)
    float instantMPG;       // Instantaneous fuel efficiency from MAF (miles per gallon)
    int rangeMiles;         // Estimated range remaining (miles)
    bool engineRunning;
    bool connected;           // Serial connection to Pi is active
    bool hasDiagnosticData;   // Received actual diagnostic data from Pi
    bool hasReceivedTelemetry; // Flag to track if we've ever received TEL: data
    // Gear estimation (for vehicles without gear sensor)
    bool gearEstimated;       // True if gear was estimated from speed/RPM
    bool clutchEngaged;       // True if clutch appears to be pressed
    int gearColor;            // Gear color from Pi: 0=green, 1=red, 2=blue, 3=yellow, 4=cyan
    // Reverse comes from the Pi as an explicit flag. It is never inferred from the
    // speed sign: a small negative speed serialises as "-0", which compares false
    // against zero on this side.
    bool isInReverse;
    // True when the Pi has a real instantaneous MPG reading. A false value is
    // "unknown" (show --), which is not the same as 0 mpg.
    bool instantMPGValid;
    // Diagnostics
    bool checkEngine;
    bool absWarning;
    bool oilWarning;
    bool batteryWarning;
    // Headlight indicators
    bool headlightsOn;       // Low beams active
    bool highBeamsOn;        // High beams active
    // 12V source voltage from ADS1115 (via Pi)
    float batteryVoltage;    // 12V source voltage (0 = no data)
};

extern TelemetryData telemetry;

// Settings from Pi
extern int clutchDisplayMode;  // 0=Gear#(colored), 1='C', 2='S', 3='-'

// ============================================================================
// Previous telemetry values for partial update optimization
// Only redraw values that have actually changed
// ============================================================================
struct CachedTelemetry {
    float rpm;
    float speed;
    int gear;
    int gearColor;           // Cached gear color from Pi
    float coolantTemp;
    float fuelLevel;
    float ambientTemp;
    float throttle;          // Cached throttle position (RPM screen)
    float brake;             // Cached brake position (RPM screen)
    float tirePressure[4];
    float averageMPG;       // Cached MPG value
    float instantMPG;       // Cached instantaneous MPG value
    int rangeMiles;         // Cached range value
    bool engineRunning;
    bool reverse;            // Cached reverse flag (from the Pi, not the speed sign)
    bool instantMPGValid;    // Cached "instant MPG is a real reading" flag
    // RPM/Speed digit optimization - only redraw changed digits
    char rpmStr[8];          // Cached RPM string for per-digit comparison
    char speedStr[8];        // Cached Speed string for per-digit comparison
    int rpmDigitCount;       // Number of digits in cached RPM
    int speedDigitCount;     // Number of digits in cached speed
    // RPM arc optimization - cache the arc state to enable incremental updates
    float arcEndAngle;       // Last drawn arc end angle (in degrees)
    uint16_t arcColor;       // Last arc color used
    bool connected;
    bool oilWarning;
    bool headlightsOn;
    bool highBeamsOn;
    float batteryVoltage;    // Cached 12V source voltage
    bool initialized;        // Set to true after first full draw
};
extern CachedTelemetry prevTelemetry;

// ============================================================================
// LED Sequence modes (must match Arduino enum)
// ============================================================================
enum LEDSequence {
    SEQ_CENTER_OUT = 1,     // Default: Fill from edges toward center (mirrored)
    SEQ_LEFT_TO_RIGHT = 2,  // Fill left to right (double resolution)
    SEQ_RIGHT_TO_LEFT = 3,  // Fill right to left
    SEQ_CENTER_IN = 4,      // Fill from center outward to edges
    SEQ_COUNT = 4           // Total number of sequences
};

// ============================================================================
// Settings structure (synced with Pi display)
// ============================================================================
struct DisplaySettings {
    int brightness = 80;          // 0-100%
    int volume = 70;              // 0-100% (audio feedback)
    int shiftRPM = 6500;          // Shift light RPM
    int redlineRPM = 7200;        // Redline RPM
    bool useMPH = true;           // true = MPH, false = KMH
    float tireLowPSI = 28.0;      // Low tire pressure warning
    int coolantWarnF = 220;       // Coolant warning temp (F)
    bool demoMode = false;        // Demo mode toggle
    int screenTimeout = 30;       // Screen dim timeout (seconds)
    int ledSequence = SEQ_CENTER_OUT;  // LED sequence mode (1-4)
};
extern DisplaySettings settings;

// IMU availability (set by main.cpp hardware init; used by System screen)
extern bool imuAvailable;

// Orientation used by the G-Force screen (updated by main.cpp's IMU code)
extern float orientationPitch;
extern float orientationRoll;

// ============================================================================
// Display state - 8 screens to match Pi
// ============================================================================
enum ScreenMode {
    SCREEN_OVERVIEW = 0,
    SCREEN_RPM = 1,
    SCREEN_TPMS = 2,
    SCREEN_ENGINE = 3,
    SCREEN_GFORCE = 4,
    SCREEN_DIAGNOSTICS = 5,
    SCREEN_SYSTEM = 6,
    SCREEN_SETTINGS = 7,
    SCREEN_COUNT = 8
};

extern const char* SCREEN_NAMES[];

extern ScreenMode currentScreen;
extern bool needsRedraw;
extern bool needsFullRedraw;  // Set to true on screen change to redraw background
extern bool navLocked;        // Navigation lock state (from Pi SWC handler)

// ============================================================================
// Boot countdown - Pi takes ~37 seconds to boot and send data
// ============================================================================
const int PI_BOOT_COUNTDOWN = 30;  // Seconds to countdown from
extern unsigned long bootStartTime;   // Set in setup()
extern bool piDataReceived;           // Set true when first valid telemetry data arrives
extern int lastBootCountdown;         // Track countdown for redraw detection
extern int currentLoadingMessage;
extern unsigned long lastMessageChange;
const int NUM_LOADING_MESSAGES = 20;

// ============================================================================
// Page transition animation state
// ============================================================================
enum TransitionType {
    TRANSITION_NONE = 0,
    TRANSITION_SLIDE_LEFT,   // Going to next screen
    TRANSITION_SLIDE_RIGHT,  // Going to previous screen
    TRANSITION_FADE,         // Fade transition
    TRANSITION_ZOOM_IN,      // Zoom in effect
    TRANSITION_ZOOM_OUT      // Zoom out effect
};

extern TransitionType currentTransition;
extern unsigned long transitionStartTime;
extern unsigned long lastTransitionEndTime;  // Debounce duplicate SCREEN commands
extern int transitionDuration;               // milliseconds
extern float transitionProgress;
extern ScreenMode transitionFromScreen;
extern ScreenMode transitionToScreen;

// ============================================================================
// Settings menu state
// ============================================================================
extern int settingsSelection;
extern int settingsScrollOffset;  // For scrolling - which item is at top of visible area
const int SETTINGS_COUNT = 9;     // Number of settings items (added LED Sequence)
const int SETTINGS_VISIBLE = 4;   // How many items fit on round screen

// TPMS per-tire timestamps (shared with NVS/serial code in main.cpp)
extern char tpmsLastUpdateStr[4][12];

// ============================================================================
// Function declarations
// ============================================================================
void drawBackground();
void drawPageIndicator();
void drawCard(int x, int y, int w, int h, uint16_t borderColor);
void drawProgressBar(int x, int y, int w, int h, float percent, uint16_t color);
void drawLargeGear(int centerX, int centerY, const char* str, uint16_t color, uint16_t bgColor);
void drawOverviewScreen();
void drawRPMScreen();
void drawTPMSScreen();
void drawEngineScreen();
void drawGForceScreen();
void drawDiagnosticsScreen();
void drawSystemScreen();
void drawSettingsScreen();
void drawSettingsItem(int index, int screenY, int itemW, int startX, bool isSelected);
void handleSettingsTouch(int x, int y);

// Page transition animation
void startTransition(ScreenMode toScreen, TransitionType type);
void updateTransition();
void drawTransition();
bool isTransitioning();

// Settings -> Pi serial bridge
void sendSettingToPI(const char* name, int value);
void sendSettingToPI(const char* name, float value);
void sendSettingToPI(const char* name, bool value);

#endif // UI_CORE_H
