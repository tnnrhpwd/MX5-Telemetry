/*
 * MX5 Telemetry Display - ESP32-S3 Round LCD
 * Waveshare ESP32-S3-Touch-LCD-1.85 (360x360)
 * 
 * This display shows real-time telemetry data from the Raspberry Pi
 * connected via serial communication.
 * 
 * NAVIGATION SCHEME (Cruise Control Buttons Only):
 * ================================================
 * Only cruise control buttons are readable on the MS-CAN bus.
 * Audio/volume buttons (VOL+, VOL-, MODE, SEEK, MUTE) are NOT available.
 * 
 * Buttons:
 * - RES_PLUS (UP):    Previous page / Navigate up in settings / Increase value
 * - SET_MINUS (DOWN): Next page / Navigate down in settings / Decrease value
 * - ON_OFF (SELECT):  Select setting to edit / Confirm edit
 * - CANCEL (BACK):    Exit edit mode / Go back to Overview
 * 
 * Touch Gestures (ESP32 only):
 * - SWIPE_UP:    Previous page (matches UP button)
 * - SWIPE_DOWN:  Next page (matches DOWN button)
 * - SWIPE_LEFT:  Next page (alternative)
 * - SWIPE_RIGHT: Previous page (alternative)
 * - SINGLE_CLICK: Select (on settings screen)
 * 
 * Settings Screen Special Behavior:
 * - When NOT editing: UP/DOWN moves through settings, wraps to prev/next page at boundaries
 * - Press SELECT (ON_OFF) to enter edit mode
 * - When editing: UP increases value, DOWN decreases value
 * - Press SELECT or CANCEL to exit edit mode
 */

#include <Arduino.h>
#include <Wire.h>
#include <NimBLEDevice.h>
#include <Preferences.h>
#include <driver/temperature_sensor.h>
#include "Display_ST77916.h"
#include "Touch_CST816.h"
#include "QMI8658.h"
#include "boot_logo.h"
#include "background_image.h"
#include "car_image.h"

// Screen dimensions
#define SCREEN_WIDTH  360
#define SCREEN_HEIGHT 360
#define CENTER_X      (SCREEN_WIDTH / 2)
#define CENTER_Y      (SCREEN_HEIGHT / 2)

// I2C pins for IMU (QMI8658)
#define IMU_SDA 11
#define IMU_SCL 10

// Colors - Modern dark theme
#define COLOR_BG          RGB565(12, 12, 18)
#define COLOR_BG_CARD     RGB565(22, 22, 32)
#define COLOR_BG_ELEVATED RGB565(32, 32, 45)
#define MX5_RED       RGB565(255, 70, 85)
#define MX5_ORANGE    RGB565(255, 140, 50)
#define MX5_YELLOW    RGB565(255, 210, 60)
#define MX5_GREEN     RGB565(50, 215, 130)
#define MX5_BLUE      RGB565(65, 135, 255)
#define MX5_CYAN      RGB565(50, 220, 255)
#define MX5_PURPLE    RGB565(175, 130, 255)
#define MX5_WHITE     RGB565(245, 245, 250)
#define MX5_BLACK     COLOR_BG
#define MX5_GRAY      RGB565(140, 140, 160)
#define MX5_DARKGRAY  RGB565(55, 55, 70)
#define MX5_ACCENT    RGB565(100, 140, 255)

// Standard corner radius for UI elements
#define CARD_RADIUS 8
#define BAR_RADIUS 4

// Telemetry data structure
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
    int rangeMiles;         // Estimated range remaining (miles)
    bool engineRunning;
    bool connected;           // Serial connection to Pi is active
    bool hasDiagnosticData;   // Received actual diagnostic data from Pi
    bool hasReceivedTelemetry; // Flag to track if we've ever received TEL: data
    // Gear estimation (for vehicles without gear sensor)
    bool gearEstimated;       // True if gear was estimated from speed/RPM
    bool clutchEngaged;       // True if clutch appears to be pressed
    // Diagnostics
    bool checkEngine;
    bool absWarning;
    bool oilWarning;
    bool batteryWarning;
    // Headlight indicators
    bool headlightsOn;       // Low beams active
    bool highBeamsOn;        // High beams active
};

TelemetryData telemetry = {0};

// ESP32 internal temperature sensor for ambient temp fallback
temperature_sensor_handle_t temp_sensor = NULL;

// Settings from Pi
int clutchDisplayMode = 0;  // 0=Gear#(colored), 1='C', 2='S', 3='-'

// Previous telemetry values for partial update optimization
// Only redraw values that have actually changed
struct CachedTelemetry {
    float rpm;
    float speed;
    int gear;
    float coolantTemp;
    float fuelLevel;
    float ambientTemp;
    float tirePressure[4];
    float averageMPG;       // Cached MPG value
    int rangeMiles;         // Cached range value
    bool engineRunning;
    // RPM arc optimization - cache the arc state to enable incremental updates
    float arcEndAngle;       // Last drawn arc end angle (in degrees)
    uint16_t arcColor;       // Last arc color used
    bool connected;
    bool oilWarning;
    bool headlightsOn;
    bool highBeamsOn;
    bool initialized;  // Set to true after first full draw
};
CachedTelemetry prevTelemetry = {0};

// LED Sequence modes (must match Arduino enum)
enum LEDSequence {
    SEQ_CENTER_OUT = 1,     // Default: Fill from edges toward center (mirrored)
    SEQ_LEFT_TO_RIGHT = 2,  // Fill left to right (double resolution)
    SEQ_RIGHT_TO_LEFT = 3,  // Fill right to left
    SEQ_CENTER_IN = 4,      // Fill from center outward to edges
    SEQ_COUNT = 4           // Total number of sequences
};

const char* LED_SEQUENCE_NAMES[] = {
    "",                     // Index 0 unused (sequences start at 1)
    "Center-Out",           // 1: Default mirrored
    "Left-Right",           // 2: Double resolution L->R
    "Right-Left",           // 3: Double resolution R->L
    "Center-In"             // 4: From center outward
};

// Settings structure (synced with Pi display)
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

DisplaySettings settings;

// IMU instance
QMI8658 imu;
bool imuAvailable = false;

// ============================================================================
// BLE TPMS Scanner Configuration
// ============================================================================
// TPMS sensor MAC addresses - DIRECTLY MAPPED TO TIRE POSITIONS
// Index 0 = Front Left (FL), Index 1 = Front Right (FR)
// Index 2 = Rear Left (RL),  Index 3 = Rear Right (RR)
// 
// Calibrated 2025-12-15: Based on temperature patterns (front ~64°F, rear ~62°F)
// TPMS MAC addresses mapped by physical tire position
// Calibrated against manufacturer app on 2025-12-16:
// - App FL (29.6 PSI, 69.8°F) = highest pressure/temp = MAC 14:26:6d
// - App FR (28.7 PSI, 66.2°F) = MAC 14:13:1f  
// - App RL (28.7 PSI, 64.4°F) = MAC 14:10:50
// - App RR (28.7 PSI, 64.4°F) = MAC 14:27:4b
const char* TPMS_MAC_FL = "14:26:6d:11:11:11";  // Front Left tire (was RR, has highest pressure)
const char* TPMS_MAC_FR = "14:13:1f:11:11:11";  // Front Right tire
const char* TPMS_MAC_RL = "14:10:50:11:11:11";  // Rear Left tire
const char* TPMS_MAC_RR = "14:27:4b:11:11:11";  // Rear Right tire (was FL)

const char* TPMS_MAC_ADDRESSES[] = {
    TPMS_MAC_FL,  // Index 0 = FL
    TPMS_MAC_FR,  // Index 1 = FR
    TPMS_MAC_RL,  // Index 2 = RL
    TPMS_MAC_RR   // Index 3 = RR
};
const int TPMS_SENSOR_COUNT = 4;
const char* TPMS_POSITION_NAMES[] = {"FL", "FR", "RL", "RR"};

// TPMS data structure for each sensor
struct TPMSSensorData {
    bool valid;           // Data has been received
    float pressurePSI;    // Tire pressure in PSI
    float temperatureF;   // Temperature in Fahrenheit
    unsigned long lastUpdate;  // millis() of last update
    int8_t rssi;          // Signal strength
};
TPMSSensorData tpmsSensors[4] = {0};

// BLE scan state
NimBLEScan* pBLEScan = nullptr;
bool bleInitialized = false;
bool bleScanRunning = false;  // Track if continuous scan is active
unsigned long lastBLEScanStart = 0;  // Track when last scan started
const unsigned long BLE_SCAN_COOLDOWN = 3000;  // Wait 3 seconds between scans
const unsigned long TPMS_DATA_TIMEOUT = 30000; // Data valid for 30 seconds

// TPMS persistence storage
Preferences tpmsPrefs;
Preferences imuPrefs;
char tpmsLastUpdateStr[4][12] = {"--:--:--", "--:--:--", "--:--:--", "--:--:--"};  // HH:MM:SS per tire
bool tpmsDataFromCache = false;  // True if current data was loaded from NVS cache

// Display state - 8 screens to match Pi
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

const char* SCREEN_NAMES[] = {
    "Overview", "RPM/Speed", "TPMS", "Engine",
    "G-Force", "Diagnostics", "System", "Settings"
};

ScreenMode currentScreen = SCREEN_OVERVIEW;
unsigned long lastUpdate = 0;
unsigned long lastTouchTime = 0;
unsigned long lastImuUpdate = 0;
unsigned long lastSerialSend = 0;
bool needsRedraw = true;
bool needsFullRedraw = true;  // Set to true on screen change to redraw background
bool navLocked = false;       // Navigation lock state (from Pi SWC handler)

// Boot countdown - Pi takes ~37 seconds to boot and send data
const int PI_BOOT_COUNTDOWN = 37;  // Seconds to countdown from
unsigned long bootStartTime = 0;   // Set in setup()
bool piDataReceived = false;       // Set true when first valid telemetry data arrives
int lastBootCountdown = -1;        // Track countdown for redraw detection

// Page transition animation state
enum TransitionType {
    TRANSITION_NONE = 0,
    TRANSITION_SLIDE_LEFT,   // Going to next screen
    TRANSITION_SLIDE_RIGHT,  // Going to previous screen
    TRANSITION_FADE,         // Fade transition
    TRANSITION_ZOOM_IN,      // Zoom in effect
    TRANSITION_ZOOM_OUT      // Zoom out effect
};

TransitionType currentTransition = TRANSITION_NONE;
unsigned long transitionStartTime = 0;
unsigned long lastTransitionEndTime = 0;  // Debounce duplicate SCREEN commands
int transitionDuration = 200;  // milliseconds
float transitionProgress = 0.0;
ScreenMode transitionFromScreen = SCREEN_OVERVIEW;
ScreenMode transitionToScreen = SCREEN_OVERVIEW;

// Function prototypes
void drawBackground();
void drawPageIndicator();
void drawCard(int x, int y, int w, int h, uint16_t borderColor);
void drawProgressBar(int x, int y, int w, int h, float percent, uint16_t color);
void drawOverviewScreen();
void drawRPMScreen();
void drawTPMSScreen();
void drawEngineScreen();
void drawGForceScreen();
void drawDiagnosticsScreen();
void drawSystemScreen();
void drawSettingsScreen();
void handleTouch();
void handleSettingsTouch(int x, int y);
void handleSerialCommands();
void parseCommand(String cmd);
void parseSettingsCommand(String data);
void sendSettingToPI(const char* name, int value);
void sendSettingToPI(const char* name, float value);
void sendSettingToPI(const char* name, bool value);
void sendAllSettingsToPI();
void startTransition(ScreenMode toScreen, TransitionType type);
void updateTransition();
void drawTransition();
bool isTransitioning();
void updateIMU();
void sendIMUData();
void initBLETPMS();
void startContinuousBLEScan();
void stopBLEScan();
void decodeTPMSData(NimBLEAdvertisedDevice* device, int sensorIndex);
void sendTPMSDataToPi();
void formatTimestamp(unsigned long millis_time, char* buf, size_t bufSize);
void saveTPMSToNVS();
void loadTPMSFromNVS();
void saveIMUCalibrationToNVS();
void loadIMUCalibrationFromNVS();

// Settings menu state
int settingsSelection = 0;
int settingsScrollOffset = 0;  // For scrolling - which item is at top of visible area
bool settingsEditMode = false;
const int SETTINGS_COUNT = 9;  // Number of settings items (added LED Sequence)
const int SETTINGS_VISIBLE = 4;  // How many items fit on round screen (reduced from 5 to avoid edge clipping)

// Settings item types for drawing
enum SettingType {
    SETTING_BACK,
    SETTING_TOGGLE,
    SETTING_SLIDER,
    SETTING_VALUE,
    SETTING_SELECTOR  // New: multi-option selector (like LED sequence)
};

// Format a millis timestamp as HH:MM:SS (time since boot when data was received)
void formatTimestamp(unsigned long millis_time, char* buf, size_t bufSize) {
    if (millis_time == 0) {
        snprintf(buf, bufSize, "--:--:--");
        return;
    }
    unsigned long totalSecs = millis_time / 1000;
    unsigned long hours = totalSecs / 3600;
    unsigned long mins = (totalSecs % 3600) / 60;
    unsigned long secs = totalSecs % 60;
    snprintf(buf, bufSize, "%02lu:%02lu:%02lu", hours, mins, secs);
}

// Draw the background image (called on full redraw)
void drawBackground() {
    LCD_DrawImage(0, 0, BACKGROUND_DATA_WIDTH, BACKGROUND_DATA_HEIGHT, background_data);
}

// === PAGE TRANSITION ANIMATION FUNCTIONS ===

// Easing function - ease out cubic for smooth deceleration
float easeOutCubic(float t) {
    return 1.0 - pow(1.0 - t, 3);
}

// Easing function - ease in out for smoother transitions
float easeInOutQuad(float t) {
    return t < 0.5 ? 2 * t * t : 1 - pow(-2 * t + 2, 2) / 2;
}

bool isTransitioning() {
    return currentTransition != TRANSITION_NONE;
}

void startTransition(ScreenMode toScreen, TransitionType type) {
    if (toScreen == currentScreen) return;  // No transition needed
    
    transitionFromScreen = currentScreen;
    transitionToScreen = toScreen;
    currentTransition = type;
    transitionStartTime = millis();
    transitionProgress = 0.0;
    
    // Reset cached telemetry so new screen draws fully
    prevTelemetry.initialized = false;
    
    Serial.printf("Starting transition: %s -> %s (type %d)\n", 
                  SCREEN_NAMES[transitionFromScreen], 
                  SCREEN_NAMES[transitionToScreen], type);
}

void updateTransition() {
    if (currentTransition == TRANSITION_NONE) return;
    
    unsigned long elapsed = millis() - transitionStartTime;
    transitionProgress = (float)elapsed / transitionDuration;
    
    if (transitionProgress >= 1.0) {
        // Transition complete
        transitionProgress = 1.0;
        currentScreen = transitionToScreen;
        currentTransition = TRANSITION_NONE;
        lastTransitionEndTime = millis();  // Track when transition ended for debounce
        // Don't set needsFullRedraw - the screen was already drawn during transition
        // Just need one more draw to clear any transition overlay artifacts
        needsRedraw = true;
        Serial.printf("Transition complete, now on screen: %s\n", SCREEN_NAMES[currentScreen]);
    }
}

void drawTransitionSlide(bool slideLeft) {
    // Calculate offset based on progress with easing
    float easedProgress = easeOutCubic(transitionProgress);
    int offset = (int)(SCREEN_WIDTH * easedProgress);
    
    if (slideLeft) {
        // Old screen slides left (out), new screen slides in from right
        // Draw a simple wipe effect with accent color divider
        
        // Clear and draw new screen position hint
        int dividerX = SCREEN_WIDTH - offset;
        
        // Draw accent line at transition edge (use LCD_DrawLine for vertical line)
        for (int i = 0; i < 4; i++) {
            LCD_DrawLine(dividerX + i - 2, 0, dividerX + i - 2, SCREEN_HEIGHT - 1, MX5_ACCENT);
        }
        
        // Fill the revealed area with a gradient hint
        if (offset > 10) {
            // Create a sweep effect - darker on left transitioning to normal
            for (int x = dividerX; x < SCREEN_WIDTH; x++) {
                float brightness = (float)(x - dividerX) / offset;
                brightness = brightness * brightness; // Quadratic for softer gradient
                uint16_t col = RGB565((int)(12 + 10 * brightness), 
                                      (int)(12 + 10 * brightness), 
                                      (int)(18 + 14 * brightness));
                LCD_DrawLine(x, 0, x, SCREEN_HEIGHT - 1, col);
            }
        }
    } else {
        // Old screen slides right (out), new screen slides in from left
        int dividerX = offset;
        
        // Draw accent line at transition edge
        for (int i = 0; i < 4; i++) {
            LCD_DrawLine(dividerX + i - 2, 0, dividerX + i - 2, SCREEN_HEIGHT - 1, MX5_ACCENT);
        }
        
        // Fill the revealed area
        if (offset > 10) {
            for (int x = 0; x < dividerX; x++) {
                float brightness = (float)(dividerX - x) / offset;
                brightness = brightness * brightness;
                uint16_t col = RGB565((int)(12 + 10 * brightness), 
                                      (int)(12 + 10 * brightness), 
                                      (int)(18 + 14 * brightness));
                LCD_DrawLine(x, 0, x, SCREEN_HEIGHT - 1, col);
            }
        }
    }
}

void drawTransitionFade() {
    // Simple fade effect using concentric circles from center
    float easedProgress = easeInOutQuad(transitionProgress);
    int maxRadius = (int)(sqrt(CENTER_X * CENTER_X + CENTER_Y * CENTER_Y) + 20);
    int currentRadius = (int)(maxRadius * easedProgress);
    
    // Draw expanding circle
    for (int r = currentRadius - 20; r <= currentRadius; r++) {
        if (r > 0) {
            uint16_t col = MX5_ACCENT;
            // Fade the circle edge
            float fade = (float)(r - (currentRadius - 20)) / 20.0;
            if (fade < 0.3) col = RGB565((int)(100 * fade / 0.3), (int)(140 * fade / 0.3), (int)(255 * fade / 0.3));
            LCD_DrawCircle(CENTER_X, CENTER_Y, r, col);
        }
    }
}

void drawTransitionZoom() {
    // Zoom effect with scaling rectangles
    float easedProgress = easeOutCubic(transitionProgress);
    
    // Draw shrinking/growing rectangle
    int rectW = (int)(SCREEN_WIDTH * (1.0 - easedProgress));
    int rectH = (int)(SCREEN_HEIGHT * (1.0 - easedProgress));
    int rectX = (SCREEN_WIDTH - rectW) / 2;
    int rectY = (SCREEN_HEIGHT - rectH) / 2;
    
    if (rectW > 10 && rectH > 10) {
        // Draw border
        LCD_DrawRect(rectX, rectY, rectW, rectH, MX5_ACCENT);
        LCD_DrawRect(rectX + 1, rectY + 1, rectW - 2, rectH - 2, MX5_BLUE);
    }
    
    // Fill outside with dark color
    if (easedProgress > 0.1) {
        // Top
        LCD_FillRect(0, 0, SCREEN_WIDTH, rectY, COLOR_BG);
        // Bottom
        LCD_FillRect(0, rectY + rectH, SCREEN_WIDTH, SCREEN_HEIGHT - rectY - rectH, COLOR_BG);
        // Left
        LCD_FillRect(0, rectY, rectX, rectH, COLOR_BG);
        // Right
        LCD_FillRect(rectX + rectW, rectY, SCREEN_WIDTH - rectX - rectW, rectH, COLOR_BG);
    }
}

void drawTransition() {
    if (currentTransition == TRANSITION_NONE) return;
    
    switch (currentTransition) {
        case TRANSITION_SLIDE_LEFT:
            drawTransitionSlide(true);
            break;
        case TRANSITION_SLIDE_RIGHT:
            drawTransitionSlide(false);
            break;
        case TRANSITION_FADE:
            drawTransitionFade();
            break;
        case TRANSITION_ZOOM_IN:
        case TRANSITION_ZOOM_OUT:
            drawTransitionZoom();
            break;
        default:
            break;
    }
}

// === END TRANSITION FUNCTIONS ===

void setup() {
    Serial.begin(115200);
    delay(100);
    
    Serial.println("MX5 Telemetry Display Starting...");
    
    // Initialize I2C for IMU
    Wire.begin(IMU_SDA, IMU_SCL);
    Wire.setClock(400000);  // 400kHz
    
    // Initialize IMU
    Serial.println("Initializing QMI8658 IMU...");
    imuAvailable = imu.begin(Wire, 0x6B);
    if (!imuAvailable) {
        Serial.println("QMI8658 not found at 0x6B, trying 0x6A...");
        imuAvailable = imu.begin(Wire, 0x6A);
    }
    
    if (imuAvailable) {
        Serial.println("IMU initialized - real G-force data enabled!");
    } else {
        Serial.println("IMU not available - using demo/serial data");
    }
    
    // Initialize display and touch
    Serial.println("Initializing LCD...");
    LCD_Init();
    Serial.println("Display initialized!");
    
    // Draw startup screen with boot logo - scaled to fill the entire screen
    LCD_Clear(COLOR_BG);
    LCD_DrawImageScaled(BOOT_LOGO_DATA_WIDTH, BOOT_LOGO_DATA_HEIGHT, boot_logo_data,
                        0, 0, SCREEN_WIDTH, SCREEN_HEIGHT);
    delay(1500);  // Show logo for 1.5 seconds
    
    // Initialize telemetry to zeros - will be populated by Pi
    telemetry.rpm = 0;
    telemetry.speed = 0;
    telemetry.gear = 0;
    telemetry.throttle = 0;
    telemetry.brake = 0;
    telemetry.coolantTemp = 0;
    telemetry.oilTemp = 0;
    telemetry.oilPressure = 0;
    telemetry.oilWarning = true;  // Default: no oil pressure
    telemetry.fuelLevel = 0;
    telemetry.ambientTemp = 0;
    
    // Initialize internal temperature sensor for ambient temp fallback
    temperature_sensor_config_t temp_sensor_config = TEMPERATURE_SENSOR_CONFIG_DEFAULT(-10, 80);
    temperature_sensor_install(&temp_sensor_config, &temp_sensor);
    temperature_sensor_enable(temp_sensor);
    telemetry.tirePressure[0] = 0; telemetry.tirePressure[1] = 0;
    telemetry.tirePressure[2] = 0; telemetry.tirePressure[3] = 0;
    telemetry.tireTemp[0] = 0; telemetry.tireTemp[1] = 0;
    telemetry.tireTemp[2] = 0; telemetry.tireTemp[3] = 0;
    telemetry.gForceX = 0;
    telemetry.gForceY = 0;
    telemetry.engineRunning = false;
    telemetry.connected = false;  // Will be set true when Pi sends data
    telemetry.hasReceivedTelemetry = false;  // Will be set true when first TEL: data received
    
    needsRedraw = true;
    needsFullRedraw = true;
    
    // Start boot countdown timer
    bootStartTime = millis();
    piDataReceived = false;
    
    Serial.println("Setup complete!");
    
    // Initialize BLE TPMS scanner (after display is ready)
    initBLETPMS();
    
    // Load cached TPMS data from NVS
    loadTPMSFromNVS();
    
    // Load IMU calibration from NVS
    loadIMUCalibrationFromNVS();
}

void loop() {
    static unsigned long loopCount = 0;
    static unsigned long lastPerfReport = 0;
    static unsigned long maxLoopTime = 0;
    unsigned long loopStart = millis();
    
    // Update ambient temp from ESP32 internal sensor (every 5 seconds)
    static unsigned long lastTempUpdate = 0;
    if (millis() - lastTempUpdate > 5000) {
        lastTempUpdate = millis();
        if (temp_sensor != NULL) {
            float tsens_celsius;
            if (temperature_sensor_get_celsius(temp_sensor, &tsens_celsius) == ESP_OK) {
                // ESP32 die temp runs significantly hotter than ambient
                // Calibrated offset: ~53°F correction for cabin temperature
                telemetry.ambientTemp = (tsens_celsius * 9.0 / 5.0 + 32.0) - 53.0;
            }
        }
    }
    
    // Handle serial commands FIRST - highest priority for Pi sync
    handleSerialCommands();
    
    // Handle touch input
    Touch_Loop();
    handleTouch();
    
    // BLE TPMS scanning - short scans when on TPMS or Overview screen
    if (currentScreen == SCREEN_TPMS || currentScreen == SCREEN_OVERVIEW) {
        // Start scan if not already scanning (will auto-restart after each scan)
        if (bleInitialized) {
            startContinuousBLEScan();  // Only starts if not already scanning
        }
        
        // Send TPMS data to Pi every 5 seconds
        static unsigned long lastTPMSSend = 0;
        if (millis() - lastTPMSSend > 5000) {
            lastTPMSSend = millis();
            sendTPMSDataToPi();
        }
    } else {
        // Stop scanning when not on TPMS/Overview screens to save power
        if (bleScanRunning) {
            stopBLEScan();
        }
    }
    
    // IMU updates - only when on G-Force screen to avoid conflicts with BLE
    if (currentScreen == SCREEN_GFORCE) {
        // Update IMU at 100Hz for smooth G-force tracking
        if (imuAvailable && millis() - lastImuUpdate > 10) {
            lastImuUpdate = millis();
            updateIMU();
        }
        
        // Send IMU data to Pi at 30Hz for responsive G-force display
        if (imuAvailable && millis() - lastSerialSend > 33) {
            lastSerialSend = millis();
            sendIMUData();
        }
    }
    
    // Update display at ~60Hz for smooth G-force ball movement
    // Note: Other screens redraw immediately on data change (event-driven)
    if (millis() - lastUpdate > 16) {
        lastUpdate = millis();
        
        // Only G-Force screen needs frequent periodic updates (smooth ball movement)
        // All other screens redraw immediately when new telemetry arrives
        if (currentScreen == SCREEN_GFORCE) {
            needsRedraw = true;
            // G-Force handles its own partial redraw, no needsFullRedraw
        }
    }
    
    // Update page transition animation
    if (isTransitioning()) {
        updateTransition();
        needsRedraw = true;  // Keep redrawing during transition
    }
    
    // Redraw screen if needed (triggers immediately when telemetry arrives)
    if (needsRedraw) {
        needsRedraw = false;
        
        // If transitioning, draw transition effect
        if (isTransitioning()) {
            // First draw the destination screen (it will be revealed by the wipe)
            ScreenMode savedScreen = currentScreen;
            currentScreen = transitionToScreen;
            needsFullRedraw = true;
            
            switch (currentScreen) {
                case SCREEN_OVERVIEW:     drawOverviewScreen(); break;
                case SCREEN_RPM:          drawRPMScreen(); break;
                case SCREEN_TPMS:         drawTPMSScreen(); break;
                case SCREEN_ENGINE:       drawEngineScreen(); break;
                case SCREEN_GFORCE:       drawGForceScreen(); break;
                case SCREEN_DIAGNOSTICS:  drawDiagnosticsScreen(); break;
                case SCREEN_SYSTEM:       drawSystemScreen(); break;
                case SCREEN_SETTINGS:     drawSettingsScreen(); break;
            }
            
            currentScreen = savedScreen;
            
            // Draw transition wipe overlay effect on top
            drawTransition();
            needsFullRedraw = false;
        } else {
            // Normal screen draw
            switch (currentScreen) {
                case SCREEN_OVERVIEW:     drawOverviewScreen(); break;
                case SCREEN_RPM:          drawRPMScreen(); break;
                case SCREEN_TPMS:         drawTPMSScreen(); break;
                case SCREEN_ENGINE:       drawEngineScreen(); break;
                case SCREEN_GFORCE:       drawGForceScreen(); break;
                case SCREEN_DIAGNOSTICS:  drawDiagnosticsScreen(); break;
                case SCREEN_SYSTEM:       drawSystemScreen(); break;
                case SCREEN_SETTINGS:     drawSettingsScreen(); break;
            }
            
            // Clear fullRedraw flag after drawing
            needsFullRedraw = false;
        }
        
        // Process serial again after drawing in case commands arrived
        handleSerialCommands();
    }
    
    // Performance monitoring
    loopCount++;
    unsigned long loopTime = millis() - loopStart;
    if (loopTime > maxLoopTime) maxLoopTime = loopTime;
    
    // Report performance every 2 seconds
    if (millis() - lastPerfReport > 2000) {
        float avgHz = loopCount * 1000.0 / (millis() - lastPerfReport);
        Serial.printf("PERF: Screen=%d (%s) LoopHz=%.0f MaxMs=%lu\n", 
                      currentScreen, SCREEN_NAMES[currentScreen], avgHz, maxLoopTime);
        lastPerfReport = millis();
        loopCount = 0;
        maxLoopTime = 0;
    }
    
    delay(5);  // ~200Hz loop rate for responsive touch
}

// ============================================================================
// IMU Functions
// ============================================================================

// Orientation tracking - primarily accelerometer-based with gyro smoothing
static float orientationPitch = 0;  // Pitch angle in degrees (nose up/down)
static float orientationRoll = 0;   // Roll angle in degrees (left/right tilt)
static unsigned long lastIMUUpdate = 0;
static bool imuInitialized = false;

// IMU Calibration offsets (set by user via CAL_IMU command)
static float imuCalibrationPitch = 0;  // Pitch offset to subtract
static float imuCalibrationRoll = 0;   // Roll offset to subtract
static float imuCalibrationAccelX = 0; // Accel X offset
static float imuCalibrationAccelY = 0; // Accel Y offset
static float imuCalibrationAccelZ = 0; // Accel Z offset

void calibrateIMU() {
    // Capture current IMU readings as the zero point
    // This allows user to set any orientation as the default
    imu.update();
    
    // Store current orientation as offset
    imuCalibrationPitch = orientationPitch;
    imuCalibrationRoll = orientationRoll;
    
    // Store current raw accelerometer readings as offset
    imuCalibrationAccelX = imu.ax;
    imuCalibrationAccelY = imu.ay - 1.0; // Subtract 1G since we want level to read 1G up
    imuCalibrationAccelZ = imu.az;
    
    Serial.println("IMU: Calibrated to current position as zero");
    Serial.printf("IMU: Offsets - Pitch:%.2f Roll:%.2f AccelX:%.3f AccelY:%.3f AccelZ:%.3f\n",
                  imuCalibrationPitch, imuCalibrationRoll, 
                  imuCalibrationAccelX, imuCalibrationAccelY, imuCalibrationAccelZ);
    
    // Save calibration to NVS for persistence
    saveIMUCalibrationToNVS();
    
    // Send confirmation back to Pi
    Serial.println("OK:CAL_IMU");
}

void updateIMU() {
    imu.update();
    
    // Calculate dt for gyroscope integration
    unsigned long now = millis();
    float dt = (lastIMUUpdate > 0) ? (now - lastIMUUpdate) / 1000.0f : 0.02f;
    lastIMUUpdate = now;
    
    // ==========================================================================
    // AXIS MAPPING for ESP32-S3 mounted VERTICALLY in oil gauge hole
    // Screen faces driver (back of car), USB port points down, top of display points UP
    // ==========================================================================
    // 
    // Physical setup (view from driver's seat looking at the screen):
    //   - ESP32 is VERTICAL (standing up in oil gauge hole)
    //   - Screen faces toward driver (back of car)
    //   - USB port points DOWN (toward floor)
    //   - Top of display points UP (toward roof)
    //
    // QMI8658 IMU chip axes (relative to screen when looking at it):
    //   - IMU X-axis: points RIGHT across the screen
    //   - IMU Y-axis: points UP along the screen  
    //   - IMU Z-axis: points OUT of screen toward you (the driver)
    //
    // Car coordinate system:
    //   - Car X-axis: positive = RIGHT (passenger side)
    //   - Car Y-axis: positive = FORWARD (direction car drives)
    //   - Car Z-axis: positive = UP (toward sky)
    //
    // Mapping (what each IMU axis measures in car coordinates):
    //   - imu.ax → Car lateral (X): positive = right
    //   - imu.ay → Car vertical (Z): positive = up, measures gravity when level (~1G)
    //   - imu.az → Car -forward (-Y): positive = backward (toward driver)
    //
    // When car is LEVEL and STATIONARY:
    //   - imu.ax ≈ 0G (no lateral tilt)
    //   - imu.ay ≈ +1G (gravity pointing down, sensor reads "up")
    //   - imu.az ≈ 0G (no fore/aft tilt)
    //   - orientationPitch = 0° (level)
    //   - orientationRoll = 0° (level)
    // ==========================================================================
    
    // Raw accelerometer in G units (already mapped to car coordinates conceptually)
    // Apply calibration offsets
    float accelLateral = imu.ax - imuCalibrationAccelX;     // Positive = tilted right (gravity pulls left)
    float accelVertical = imu.ay - imuCalibrationAccelY;    // Positive = up, ~1G when level
    float accelBackward = imu.az - imuCalibrationAccelZ;    // Positive = nose up (gravity pulls backward)
    
    // ==========================================================================
    // ORIENTATION FROM ACCELEROMETER (Primary source - always stable)
    // ==========================================================================
    // When stationary, accelerometer measures gravity direction
    // Pitch: atan2(backward_component, vertical_component)
    //   - Nose DOWN → gravity has forward component → accelBackward < 0 → pitch < 0
    //   - Nose UP   → gravity has backward component → accelBackward > 0 → pitch > 0
    // Roll: atan2(lateral_component, vertical_component)  
    //   - Roll LEFT  → gravity pulls right → accelLateral > 0 → but we want roll < 0
    //   - Roll RIGHT → gravity pulls left  → accelLateral < 0 → but we want roll > 0
    
    float accelPitch = atan2(accelBackward, accelVertical) * RAD_TO_DEG;
    float accelRoll = atan2(-accelLateral, accelVertical) * RAD_TO_DEG;  // Negate for correct sign
    
    // Initialize orientation from accelerometer on first read
    if (!imuInitialized) {
        orientationPitch = accelPitch;
        orientationRoll = accelRoll;
        imuInitialized = true;
    }
    
    // ==========================================================================
    // COMPLEMENTARY FILTER: Accel (stable) + Gyro (smooth)
    // ==========================================================================
    // Use high alpha (favor accelerometer) since we want accurate tilt, not fast response
    // When sitting still: accelerometer is truth, gyro just smooths noise
    // When moving: gyro helps during brief dynamic moments, accel corrects quickly
    
    float totalAccel = sqrt(accelLateral*accelLateral + 
                           accelBackward*accelBackward + 
                           accelVertical*accelVertical);
    
    // Gyroscope rates mapped to car coordinates (degrees/sec)
    // gx = rotation around IMU X-axis = pitch rate
    // gz = rotation around IMU Z-axis (pointing backward) = roll rate  
    float gyroPitchRate = imu.gx;   // Positive = nose going up
    float gyroRollRate = -imu.gz;   // Negative because Z points backward
    
    // Apply gyro for smoothing (integrate rotation rate)
    float gyroPitch = orientationPitch + gyroPitchRate * dt;
    float gyroRoll = orientationRoll + gyroRollRate * dt;
    
    // Choose alpha based on how close we are to pure gravity (1G)
    // High alpha = trust accelerometer more (stable but includes real acceleration)
    // Low alpha = trust gyro more (smooth but drifts)
    float alpha;
    if (totalAccel > 0.9 && totalAccel < 1.1) {
        // Very close to 1G - strongly trust accelerometer (stationary or slow movement)
        alpha = 0.15;
    } else if (totalAccel > 0.7 && totalAccel < 1.3) {
        // Moderate acceleration - blend more evenly
        alpha = 0.08;
    } else {
        // High acceleration - rely more on gyro (but still correct drift)
        alpha = 0.03;
    }
    
    // Complementary filter: blend gyro-integrated value with accelerometer
    orientationPitch = (1.0 - alpha) * gyroPitch + alpha * accelPitch;
    orientationRoll = (1.0 - alpha) * gyroRoll + alpha * accelRoll;
    
    // Apply user calibration offsets (subtract to make calibration point = zero)
    orientationPitch -= imuCalibrationPitch;
    orientationRoll -= imuCalibrationRoll;
    
    // Clamp to reasonable range
    orientationPitch = constrain(orientationPitch, -30.0f, 30.0f);
    orientationRoll = constrain(orientationRoll, -30.0f, 30.0f);
    
    // ==========================================================================
    // STORE VALUES FOR DISPLAY
    // ==========================================================================
    // Map to car coordinate names for clarity
    telemetry.gForceX = accelLateral;    // Lateral G (positive = right)
    telemetry.gForceY = -accelBackward;  // Forward G (positive = forward, so negate backward)
    telemetry.gForceZ = accelVertical;   // Vertical G (positive = up)
    
    // ==========================================================================
    // LINEAR ACCELERATION (Gravity removed) for ball sizing
    // ==========================================================================
    // Remove gravity component based on current orientation
    // Gravity vector in car frame when tilted:
    //   - Pitch up → gravity has backward component = +sin(pitch) in backward axis
    //   - Roll right → gravity has left component = -sin(roll) in lateral axis
    float gravityBackward = sin(orientationPitch * DEG_TO_RAD);
    float gravityLateral = -sin(orientationRoll * DEG_TO_RAD);
    
    // Linear acceleration = measured - gravity component
    telemetry.linearAccelX = accelLateral - gravityLateral;
    telemetry.linearAccelY = -accelBackward - (-gravityBackward);  // Forward = -backward
    
    // Only trigger redraw on G-Force screen
    if (currentScreen == SCREEN_GFORCE) {
        needsRedraw = true;
    }
}

void sendIMUData() {
    // Send full IMU data to Pi for display sync
    // Format: IMU:accelX,accelY,accelZ,gyroX,gyroY,gyroZ,linearX,linearY,pitch,roll
    Serial.printf("IMU:%.3f,%.3f,%.3f,%.2f,%.2f,%.2f,%.3f,%.3f,%.1f,%.1f\n",
                  telemetry.gForceX, telemetry.gForceY, telemetry.gForceZ,
                  imu.gx, imu.gy, imu.gz,
                  telemetry.linearAccelX, telemetry.linearAccelY,
                  orientationPitch, orientationRoll);
}

void handleTouch() {
    // Touch Navigation Scheme (matches cruise control buttons):
    // - SWIPE_UP: Previous page (matches RES_PLUS / UP button)
    // - SWIPE_DOWN: Next page (matches SET_MINUS / DOWN button)
    // - SINGLE_CLICK: Select (matches ON_OFF button)
    // - SWIPE_LEFT/RIGHT: Also navigate pages (alternative)
    
    // When navigation is locked, ignore all touch input
    if (navLocked) {
        touch_data.gesture = NONE;  // Clear any pending gestures
        return;
    }
    
    // Debug: Print any touch activity
    static unsigned long lastTouchDebug = 0;
    if (touch_data.points > 0 || touch_data.gesture != NONE) {
        if (millis() - lastTouchDebug > 100) {
            Serial.printf("Touch: x=%d y=%d pts=%d gesture=%d\n", 
                          touch_data.x, touch_data.y, touch_data.points, touch_data.gesture);
            lastTouchDebug = millis();
        }
    }
    
    // Handle gestures with debounce (ignore gestures during transition)
    if (touch_data.gesture != NONE && millis() - lastTouchTime > 200 && !isTransitioning()) {
        lastTouchTime = millis();
        GESTURE handled_gesture = touch_data.gesture;
        touch_data.gesture = NONE;  // Clear gesture immediately to prevent double-processing
        Serial.printf("Gesture detected: %d\n", handled_gesture);
        
        switch (handled_gesture) {
            case SWIPE_UP: {
                // Swipe up = go to PREVIOUS screen (matches RES_PLUS / UP button)
                ScreenMode prevScreen = (ScreenMode)((currentScreen - 1 + SCREEN_COUNT) % SCREEN_COUNT);
                startTransition(prevScreen, TRANSITION_SLIDE_RIGHT);
                Serial.printf("Screen: %d (swipe up -> prev)\n", prevScreen);
                // Notify Pi of screen change for sync
                Serial.printf("SCREEN_CHANGED:%d\n", prevScreen);
                break;
            }
            case SWIPE_DOWN: {
                // Swipe down = go to NEXT screen (matches SET_MINUS / DOWN button)
                ScreenMode nextScreen = (ScreenMode)((currentScreen + 1) % SCREEN_COUNT);
                startTransition(nextScreen, TRANSITION_SLIDE_LEFT);
                Serial.printf("Screen: %d (swipe down -> next)\n", nextScreen);
                // Notify Pi of screen change for sync
                Serial.printf("SCREEN_CHANGED:%d\n", nextScreen);
                break;
            }
            case SWIPE_LEFT: {
                // Swipe left = also go to NEXT screen (alternative gesture)
                ScreenMode nextScreen = (ScreenMode)((currentScreen + 1) % SCREEN_COUNT);
                startTransition(nextScreen, TRANSITION_SLIDE_LEFT);
                Serial.printf("Screen: %d (swipe left -> next)\n", nextScreen);
                // Notify Pi of screen change for sync
                Serial.printf("SCREEN_CHANGED:%d\n", nextScreen);
                break;
            }
            case SWIPE_RIGHT: {
                // Swipe right = also go to PREVIOUS screen (alternative gesture)
                ScreenMode prevScreen = (ScreenMode)((currentScreen - 1 + SCREEN_COUNT) % SCREEN_COUNT);
                startTransition(prevScreen, TRANSITION_SLIDE_RIGHT);
                Serial.printf("Screen: %d (swipe right -> prev)\n", prevScreen);
                // Notify Pi of screen change for sync
                Serial.printf("SCREEN_CHANGED:%d\n", prevScreen);
                break;
            }
            case SINGLE_CLICK:
                Serial.println("Single click detected");
                // Handle settings touch if on settings screen
                if (currentScreen == SCREEN_SETTINGS) {
                    handleSettingsTouch(touch_data.x, touch_data.y);
                }
                break;
            case DOUBLE_CLICK:
                Serial.println("Double click detected");
                // Could be used for quick action in future
                break;
            case LONG_PRESS:
                Serial.println("Long press detected");
                // Could go to Overview/home screen
                break;
            default:
                Serial.printf("Unknown gesture: %d\n", touch_data.gesture);
                break;
        }
        
        // Clear gesture after handling
        touch_data.gesture = NONE;
    }
}

// Draw large gear indicator character (4x bigger than font size 8)
// Uses filled rectangles for proper letter shapes
// Character size: ~50x70 pixels (fits in 50px radius circle)
void drawLargeGear(int centerX, int centerY, const char* str, uint16_t color, uint16_t bgColor) {
    int w = 10;     // Stroke width
    int charW = 44; // Character width
    int charH = 64; // Character height
    
    // Center position (top-left corner)
    int x = centerX - charW / 2;
    int y = centerY - charH / 2;
    
    char c = str[0];
    
    switch (c) {
        case '1':
            // Vertical bar, slightly right of center
            LCD_FillRect(x + charW/2 - w/2, y, w, charH, color);
            // Small serif at top left
            LCD_FillRect(x + charW/2 - w/2 - w, y, w, w, color);
            break;
            
        case '2':
            LCD_FillRect(x, y, charW, w, color);           // Top
            LCD_FillRect(x + charW - w, y, w, charH/2, color);  // Top right vertical
            LCD_FillRect(x, y + charH/2 - w/2, charW, w, color); // Middle
            LCD_FillRect(x, y + charH/2, w, charH/2, color);    // Bottom left vertical
            LCD_FillRect(x, y + charH - w, charW, w, color);    // Bottom
            break;
            
        case '3':
            LCD_FillRect(x, y, charW, w, color);                 // Top
            LCD_FillRect(x + charW - w, y, w, charH, color);     // Right vertical
            LCD_FillRect(x, y + charH/2 - w/2, charW, w, color); // Middle
            LCD_FillRect(x, y + charH - w, charW, w, color);     // Bottom
            break;
            
        case '4':
            LCD_FillRect(x, y, w, charH/2 + w, color);           // Left top vertical
            LCD_FillRect(x, y + charH/2 - w/2, charW, w, color); // Middle horizontal
            LCD_FillRect(x + charW - w, y, w, charH, color);     // Right full vertical
            break;
            
        case '5':
            LCD_FillRect(x, y, charW, w, color);                 // Top
            LCD_FillRect(x, y, w, charH/2, color);               // Top left vertical
            LCD_FillRect(x, y + charH/2 - w/2, charW, w, color); // Middle
            LCD_FillRect(x + charW - w, y + charH/2, w, charH/2, color); // Bottom right
            LCD_FillRect(x, y + charH - w, charW, w, color);     // Bottom
            break;
            
        case '6':
            LCD_FillRect(x, y, charW, w, color);                 // Top
            LCD_FillRect(x, y, w, charH, color);                 // Left vertical
            LCD_FillRect(x, y + charH/2 - w/2, charW, w, color); // Middle
            LCD_FillRect(x + charW - w, y + charH/2, w, charH/2, color); // Bottom right
            LCD_FillRect(x, y + charH - w, charW, w, color);     // Bottom
            break;
            
        case 'N':
            // Left vertical
            LCD_FillRect(x, y, w, charH, color);
            // Right vertical
            LCD_FillRect(x + charW - w, y, w, charH, color);
            // Diagonal - draw as series of small rectangles
            for (int i = 0; i < charH; i += 4) {
                int dx = (i * (charW - w)) / charH;
                LCD_FillRect(x + dx, y + i, w + 2, 6, color);
            }
            break;
            
        case 'R':
            LCD_FillRect(x, y, w, charH, color);                 // Left vertical
            LCD_FillRect(x, y, charW - w/2, w, color);           // Top
            LCD_FillRect(x + charW - w, y, w, charH/2, color);   // Top right vertical
            LCD_FillRect(x, y + charH/2 - w/2, charW - w/2, w, color); // Middle
            // Diagonal leg
            for (int i = 0; i < charH/2; i += 4) {
                int dx = (i * (charW - w)) / (charH/2);
                LCD_FillRect(x + charW/3 + dx, y + charH/2 + i, w + 2, 6, color);
            }
            break;
            
        case 'C':
            LCD_FillRect(x, y, charW, w, color);                 // Top
            LCD_FillRect(x, y, w, charH, color);                 // Left vertical
            LCD_FillRect(x, y + charH - w, charW, w, color);     // Bottom
            break;
            
        case 'G':
            // G shape - C with a horizontal bar coming in from right
            LCD_FillRect(x, y, charW, w, color);                 // Top
            LCD_FillRect(x, y, w, charH, color);                 // Left vertical
            LCD_FillRect(x, y + charH - w, charW, w, color);     // Bottom
            LCD_FillRect(x + charW - w, y + charH/2, w, charH/2, color); // Right bottom vertical
            LCD_FillRect(x + charW/2, y + charH/2 - w/2, charW/2, w, color); // Middle bar from center to right
            break;
            
        case '0':
            LCD_FillRect(x, y, charW, w, color);                 // Top
            LCD_FillRect(x, y, w, charH, color);                 // Left
            LCD_FillRect(x + charW - w, y, w, charH, color);     // Right
            LCD_FillRect(x, y + charH - w, charW, w, color);     // Bottom
            break;
            
        case '-':
            // Just a horizontal bar in the middle
            LCD_FillRect(x + 4, y + charH/2 - w/2, charW - 8, w, color);
            break;
            
        default:
            // Default to dash
            LCD_FillRect(x + 4, y + charH/2 - w/2, charW - 8, w, color);
            break;
    }
}

void drawOverviewScreen() {
    // GRANULAR CHANGE DETECTION - only redraw specific elements that changed
    // This dramatically reduces draw time by avoiding full-screen redraws
    bool rpmChanged = !prevTelemetry.initialized || (int)telemetry.rpm != (int)prevTelemetry.rpm;
    bool speedChanged = !prevTelemetry.initialized || (int)telemetry.speed != (int)prevTelemetry.speed;
    bool gearChanged = !prevTelemetry.initialized || telemetry.gear != prevTelemetry.gear;
    bool coolantChanged = !prevTelemetry.initialized || (int)telemetry.coolantTemp != (int)prevTelemetry.coolantTemp;
    bool fuelChanged = !prevTelemetry.initialized || (int)telemetry.fuelLevel != (int)prevTelemetry.fuelLevel;
    bool ambientChanged = !prevTelemetry.initialized || (int)telemetry.ambientTemp != (int)prevTelemetry.ambientTemp;
    bool oilChanged = !prevTelemetry.initialized || telemetry.oilWarning != prevTelemetry.oilWarning;
    // MPG and range change detection
    bool mpgChanged = !prevTelemetry.initialized || 
                      fabsf(telemetry.averageMPG - prevTelemetry.averageMPG) >= 0.1f;
    bool rangeChanged = !prevTelemetry.initialized || 
                        telemetry.rangeMiles != prevTelemetry.rangeMiles;
    
    // Boot countdown change detection
    int currentBootCountdown = PI_BOOT_COUNTDOWN - ((millis() - bootStartTime) / 1000);
    if (currentBootCountdown < 0) currentBootCountdown = 0;
    bool bootCountdownChanged = (!piDataReceived && currentBootCountdown > 0 && currentBootCountdown != lastBootCountdown);
    
    bool tpmsChanged = false;
    for (int i = 0; i < 4; i++) {
        if (fabsf(telemetry.tirePressure[i] - prevTelemetry.tirePressure[i]) > 0.05f) {
            tpmsChanged = true;
            break;
        }
    }
    
    // Calculate arc angle early to check if it changed (more precise than integer RPM)
    float rpmPercent = telemetry.rpm / 8000.0;
    if (rpmPercent > 1.0) rpmPercent = 1.0;
    float startAngle = 135.0;  // Bottom-left
    float totalArc = 270.0;    // Sweep to bottom-right
    float endAngle = startAngle + (totalArc * rpmPercent);
    
    // Arc changed if angle moved by at least 1 degree (matches angleStep)
    bool arcChanged = !prevTelemetry.initialized || 
                      fabsf(endAngle - prevTelemetry.arcEndAngle) >= 1.0;
    
    // Check if anything at all changed
    bool anyChange = needsFullRedraw || rpmChanged || speedChanged || gearChanged || 
        coolantChanged || fuelChanged || ambientChanged || oilChanged || tpmsChanged || 
        arcChanged || mpgChanged || rangeChanged || bootCountdownChanged;
    
    // Skip if nothing changed
    if (!anyChange) return;
    
    // If full redraw needed, draw background and reset caches
    if (needsFullRedraw) {
        drawBackground();
        // Reset arc cache so full arc is redrawn
        prevTelemetry.arcEndAngle = 135.0;  // Start angle
        prevTelemetry.arcColor = MX5_DARKGRAY;
    }
    
    // === RPM ARC GAUGE (Screen border) - SEGMENT-BASED INCREMENTAL UPDATE ===
    // Arc goes around the edge of the circular display
    // Uses Arduino LED color ranges: Blue < 2000 < Green < 3000 < Yellow < 4500 < Orange < 5500 < Red
    //
    // SOLUTION TO GHOSTING: Use discrete segments instead of continuous angles.
    // Each segment represents a fixed portion of the arc. When RPM changes, we only
    // update the segments that changed state (colored <-> gray). This ensures
    // pixel-perfect coverage with no gaps or missed pixels.
    
    uint16_t rpmColor = MX5_BLUE;
    if (telemetry.rpm >= 5500) rpmColor = MX5_RED;
    else if (telemetry.rpm >= 4500) rpmColor = MX5_ORANGE;
    else if (telemetry.rpm >= 3000) rpmColor = MX5_YELLOW;
    else if (telemetry.rpm >= 2000) rpmColor = MX5_GREEN;
    
    // Arc parameters
    int arcRadius = 174;  // Just inside the 360px circle edge
    int arcThickness = 14;  // Thicker modern gauge
    
    // Segment-based approach: divide arc into discrete segments
    // Total arc = 270 degrees, use 135 segments (2 degrees each) for faster updates
    // Reduced from 270 segments to cut update time in half while maintaining visual quality
    const int NUM_SEGMENTS = 135;
    const float DEGREES_PER_SEGMENT = 2.0f;
    
    // Calculate which segment the current RPM ends at (0 to NUM_SEGMENTS)
    // Reuse rpmPercent calculated earlier
    int currentSegment = (int)(rpmPercent * NUM_SEGMENTS);
    
    // Calculate previous segment from cached angle
    float prevRpmPercent = (prevTelemetry.arcEndAngle - startAngle) / totalArc;
    if (prevRpmPercent < 0) prevRpmPercent = 0;
    if (prevRpmPercent > 1.0f) prevRpmPercent = 1.0f;
    int prevSegment = (int)(prevRpmPercent * NUM_SEGMENTS);
    
    bool colorChanged = (rpmColor != prevTelemetry.arcColor);
    
    // Helper lambda to draw a single segment (all pixels for one degree of arc)
    auto drawSegment = [&](int segmentIndex, uint16_t color) {
        float segStartAngle = startAngle + (segmentIndex * DEGREES_PER_SEGMENT);
        float segEndAngle = segStartAngle + DEGREES_PER_SEGMENT;
        
        // Draw all pixels in this segment with finer step to ensure full coverage
        for (int t = 0; t < arcThickness; t++) {
            int r = arcRadius - t;
            // Use 0.3 degree step within segment to ensure no gaps
            for (float angle = segStartAngle; angle <= segEndAngle; angle += 0.3f) {
                float rad = angle * 3.14159f / 180.0f;
                int x = CENTER_X + (int)(r * cosf(rad));
                int y = CENTER_Y + (int)(r * sinf(rad));
                LCD_DrawPixel(x, y, color);
            }
        }
    };
    
    if (needsFullRedraw || prevSegment < 0) {
        // Full redraw: draw all gray segments first, then colored segments
        for (int seg = 0; seg < NUM_SEGMENTS; seg++) {
            drawSegment(seg, MX5_DARKGRAY);
        }
        for (int seg = 0; seg < currentSegment; seg++) {
            drawSegment(seg, rpmColor);
        }
    } else if (currentSegment > prevSegment) {
        // RPM increased - draw new colored segments
        for (int seg = prevSegment; seg < currentSegment; seg++) {
            drawSegment(seg, rpmColor);
        }
        // If color changed, also redraw existing colored portion
        if (colorChanged) {
            for (int seg = 0; seg < prevSegment; seg++) {
                drawSegment(seg, rpmColor);
            }
        }
    } else if (currentSegment < prevSegment) {
        // RPM decreased - erase segments that are no longer colored (draw gray)
        for (int seg = currentSegment; seg < prevSegment; seg++) {
            drawSegment(seg, MX5_DARKGRAY);
        }
        // If color changed, also redraw remaining colored portion
        if (colorChanged && currentSegment > 0) {
            for (int seg = 0; seg < currentSegment; seg++) {
                drawSegment(seg, rpmColor);
            }
        }
    } else if (colorChanged && currentSegment > 0) {
        // Same segment count but color changed - redraw colored portion
        for (int seg = 0; seg < currentSegment; seg++) {
            drawSegment(seg, rpmColor);
        }
    }
    
    // Cache current state for next frame
    prevTelemetry.arcEndAngle = startAngle + (currentSegment * DEGREES_PER_SEGMENT);
    prevTelemetry.arcColor = rpmColor;
    
    // Draw tick marks matching NC GT tachometer (0-7500 with 1000 RPM intervals)
    // Marks at: 0, 1000, 2000, 3000, 4000, 5000, 6000, 7000
    // Only redraw on full redraw (they don't change)
    if (needsFullRedraw) {
        int tickMarks[] = {0, 1000, 2000, 3000, 4000, 5000, 6000, 7000};
        for (int i = 0; i < 8; i++) {
            float tickPercent = tickMarks[i] / 8000.0;
            float tickAngle = startAngle + (totalArc * tickPercent);
            float rad = tickAngle * 3.14159 / 180.0;
            int x1 = CENTER_X + (int)((arcRadius + 2) * cos(rad));
            int y1 = CENTER_Y + (int)((arcRadius + 2) * sin(rad));
            int x2 = CENTER_X + (int)((arcRadius - arcThickness - 4) * cos(rad));
            int y2 = CENTER_Y + (int)((arcRadius - arcThickness - 4) * sin(rad));
            LCD_DrawLine(x1, y1, x2, y2, MX5_WHITE);
        }
    }
    
    // Calculate boot countdown early for hiding elements
    int earlyBootCountdown = PI_BOOT_COUNTDOWN - ((millis() - bootStartTime) / 1000);
    if (earlyBootCountdown < 0) earlyBootCountdown = 0;
    bool hideTopDuringBoot = !piDataReceived && earlyBootCountdown > 0;
    
    // === MPH and RPM at top ===
    // Hidden during Pi boot countdown
    if (!hideTopDuringBoot) {
    // MPH on left side - moved down by 30px for better layout
    if (needsFullRedraw || speedChanged) {
        char speedStr[8];
        if (!telemetry.hasReceivedTelemetry) {
            snprintf(speedStr, sizeof(speedStr), "--");
        } else {
            snprintf(speedStr, sizeof(speedStr), "%d", (int)telemetry.speed);
        }
        int speedX = 110;
        int speedY = 65;  // Moved down 30px from 35
        // Clear area (matches RPM width)
        LCD_FillRect(speedX - 10, speedY - 5, 100, 35, COLOR_BG);
        // Draw label
        LCD_DrawString(speedX, speedY, "mph", MX5_GRAY, COLOR_BG, 1);
        // Draw value
        LCD_DrawString(speedX, speedY + 12, speedStr, MX5_WHITE, COLOR_BG, 3);
    }
    
    // RPM on right side - moved down to match speed
    if (needsFullRedraw || rpmChanged) {
        char rpmStr[8];
        if (!telemetry.hasReceivedTelemetry) {
            snprintf(rpmStr, sizeof(rpmStr), "--");
        } else {
            snprintf(rpmStr, sizeof(rpmStr), "%d", (int)telemetry.rpm);
        }
        int rpmX = SCREEN_WIDTH - 160;
        int rpmY = 65;  // Moved down 30px from 35
        // Clear area (matches MPH width)
        LCD_FillRect(rpmX - 10, rpmY - 5, 100, 35, COLOR_BG);
        // Draw label
        LCD_DrawString(rpmX, rpmY, "rpm", MX5_GRAY, COLOR_BG, 1);
        // Draw value (right-aligned look)
        int rpmLen = strlen(rpmStr);
        LCD_DrawString(rpmX + 50 - rpmLen * 9, rpmY + 12, rpmStr, rpmColor, COLOR_BG, 3);
    }
    }  // End hideTopDuringBoot check
    
    // === LARGE GEAR INDICATOR (Center) === 
    // Determine gear ring color based on RPM thresholds (used for rev-matching during shifts)
    // When clutch is engaged with speed > 0, use RPM colors to help driver match revs
    uint16_t gearGlow = MX5_GREEN;
    if (telemetry.rpm > 6500) {
        gearGlow = MX5_RED;
    } else if (telemetry.rpm > 5500) {
        gearGlow = MX5_ORANGE;
    } else if (telemetry.rpm > 4500) {
        gearGlow = MX5_YELLOW;
    } else if (telemetry.rpm > 3000) {
        gearGlow = MX5_GREEN;
    } else if (telemetry.rpm > 2000) {
        gearGlow = MX5_CYAN;  // Lower RPM range - cyan indicates "safe" rev range
    } else {
        gearGlow = MX5_BLUE;  // Very low RPM - blue indicates might stall/lug
    }
    
    // Cache previous gear glow to detect color threshold crossings
    static uint16_t prevGearGlow = 0;
    bool gearGlowChanged = (gearGlow != prevGearGlow);
    
    // Only redraw gear indicator when gear changed, color changed, or countdown changed
    if (needsFullRedraw || gearChanged || gearGlowChanged || bootCountdownChanged) {
        int gearX = 180;  // Exact center of 360px display
        int gearY = 180;  // Exact center of 360px display
        int gearRadius = 50;  // Reduced gear circle radius for better fit
        LCD_FillCircle(gearX, gearY, gearRadius, COLOR_BG_CARD);
        
        // Draw gear ring (thicker)
        for (int r = gearRadius; r > gearRadius - 5; r--) {
            LCD_DrawCircle(gearX, gearY, r, gearGlow);
        }
        
        // Gear text - display based on boot state, engine state and clutch
        char gearStr[4];
        
        // Calculate boot countdown
        int bootCountdown = PI_BOOT_COUNTDOWN - ((millis() - bootStartTime) / 1000);
        if (bootCountdown < 0) bootCountdown = 0;
        bool showBootCountdown = !piDataReceived && bootCountdown > 0;
        
        if (showBootCountdown) {
            // Show countdown during Pi boot
            snprintf(gearStr, sizeof(gearStr), "%d", bootCountdown);
        } else if (!telemetry.engineRunning) {
            // When engine is off, show gear if known from CAN (neutral/reverse), else 'G'
            if (telemetry.gear == 0) snprintf(gearStr, sizeof(gearStr), "N");
            else if (telemetry.gear == -1) snprintf(gearStr, sizeof(gearStr), "R");
            else snprintf(gearStr, sizeof(gearStr), "G");  // Unknown gear when engine off
        } else if (telemetry.clutchEngaged) {
            // Clutch is engaged - show per user preference
            switch (clutchDisplayMode) {
                case 0:  // Gear# (colored) - show estimated gear for rev-matching
                    if (telemetry.gear == 0) snprintf(gearStr, sizeof(gearStr), "N");
                    else if (telemetry.gear == -1) snprintf(gearStr, sizeof(gearStr), "R");
                    else snprintf(gearStr, sizeof(gearStr), "%d", telemetry.gear);
                    break;
                case 1:  // 'C' for clutch
                    snprintf(gearStr, sizeof(gearStr), "C");
                    break;
                case 2:  // 'S' for shifting
                    snprintf(gearStr, sizeof(gearStr), "S");
                    break;
                case 3:  // '-' for unknown
                    snprintf(gearStr, sizeof(gearStr), "-");
                    break;
                default:
                    snprintf(gearStr, sizeof(gearStr), "-");
                    break;
            }
        } else {
            // Normal display - show detected/estimated gear
            if (telemetry.gear == 0) snprintf(gearStr, sizeof(gearStr), "N");
            else if (telemetry.gear == -1) snprintf(gearStr, sizeof(gearStr), "R");
            else snprintf(gearStr, sizeof(gearStr), "%d", telemetry.gear);
        }
        // Draw gear text centered in the gear circle using custom large font
        // 7-segment style digits scaled to fill the gear circle (~70px tall)
        drawLargeGear(180, 180, gearStr, gearGlow, COLOR_BG_CARD);
        
        // Update cached gear glow
        prevGearGlow = gearGlow;
        
        // Track boot countdown for redraw detection
        lastBootCountdown = showBootCountdown ? bootCountdown : -1;
    }
    
    // Calculate boot countdown for hiding elements
    int bootCountdownCheck = PI_BOOT_COUNTDOWN - ((millis() - bootStartTime) / 1000);
    if (bootCountdownCheck < 0) bootCountdownCheck = 0;
    bool hideDuringBoot = !piDataReceived && bootCountdownCheck > 0;
    
    // === SIDE INDICATORS: Coolant/Oil (left), Gas (right) ===
    // Hidden during Pi boot countdown
    if (hideDuringBoot) {
        // Don't draw side indicators during boot - they're hidden
        // Just clear the areas if needed on full redraw
        if (needsFullRedraw) {
            int sideBoxY = CENTER_Y - 36;
            int sideBoxH = 72;
            LCD_FillRoundRect(50, sideBoxY, 70, sideBoxH, 4, COLOR_BG);  // Left side
            LCD_FillRoundRect(SCREEN_WIDTH - 98, sideBoxY, 70, sideBoxH, 4, COLOR_BG);  // Right side
        }
    } else {
    // === SIDE INDICATORS: Coolant/Oil (left), Gas (right) ===
    // Both boxes aligned to same Y position and height for visual balance
    int sideBoxY = CENTER_Y - 36;  // Common Y for all side indicators
    int sideBoxH = 72;  // Common height for all side indicators
    
    // COOLANT + OIL COMBINED (left side) - matches gas box height
    int leftBoxX = 50;
    int leftBoxW = 70;
    if (needsFullRedraw || coolantChanged || oilChanged) {
        // Use coolant color for main accent (more critical indicator)
        uint16_t coolColor = MX5_CYAN;
        if (telemetry.coolantTemp == 0) coolColor = MX5_RED;  // No data received
        else if (telemetry.coolantTemp > 220) coolColor = MX5_RED;
        else if (telemetry.coolantTemp > 200) coolColor = MX5_ORANGE;
        
        // Draw combined box background
        LCD_FillRoundRect(leftBoxX, sideBoxY, leftBoxW, sideBoxH, 4, COLOR_BG_CARD);
        LCD_FillRect(leftBoxX, sideBoxY, 3, sideBoxH, coolColor);  // Left accent bar
        
        // COOLANT section (top)
        LCD_DrawString(leftBoxX + 6, sideBoxY + 3, "COOL", MX5_GRAY, COLOR_BG_CARD, 1);
        char coolStr[8];
        snprintf(coolStr, sizeof(coolStr), "%dF", (int)telemetry.coolantTemp);
        LCD_DrawString(leftBoxX + 6, sideBoxY + 16, coolStr, coolColor, COLOR_BG_CARD, 2);
        
        // OIL section (bottom) - status text below label
        uint16_t oilColor = telemetry.oilWarning ? MX5_RED : MX5_GREEN;
        LCD_DrawString(leftBoxX + 6, sideBoxY + 42, "OIL", MX5_GRAY, COLOR_BG_CARD, 1);
        const char* oilStatus = telemetry.oilWarning ? "LOW" : "OK";
        LCD_DrawString(leftBoxX + 6, sideBoxY + 56, oilStatus, oilColor, COLOR_BG_CARD, 2);
    }
    
    // GAS (right side) - shows MPG, tank %, and estimated range
    int gasBoxX = SCREEN_WIDTH - 98;
    int gasBoxW = 70;
    
    if (needsFullRedraw || mpgChanged || rangeChanged || fuelChanged) {
        // Determine accent color based on fuel level (most urgent indicator)
        uint16_t accentColor = MX5_GREEN;
        if (telemetry.fuelLevel < 15) accentColor = MX5_RED;
        else if (telemetry.fuelLevel < 25) accentColor = MX5_ORANGE;
        else if (telemetry.fuelLevel < 40) accentColor = MX5_YELLOW;
        
        // MPG color
        uint16_t mpgColor = MX5_GREEN;
        float displayMPG = telemetry.averageMPG > 0 ? telemetry.averageMPG : 26.0f;
        if (displayMPG < 15) mpgColor = MX5_RED;
        else if (displayMPG < 20) mpgColor = MX5_ORANGE;
        else if (displayMPG > 30) mpgColor = MX5_CYAN;
        
        // Tank % color
        uint16_t tankColor = MX5_GREEN;
        if (telemetry.fuelLevel < 15) tankColor = MX5_RED;
        else if (telemetry.fuelLevel < 25) tankColor = MX5_ORANGE;
        else if (telemetry.fuelLevel < 40) tankColor = MX5_YELLOW;
        
        // Calculate display range first (may need fallback calculation)
        int displayRange = telemetry.rangeMiles;
        if (displayRange <= 0 && telemetry.fuelLevel > 0) {
            // Calculate range from fuel level: fuel% * 12.7gal tank * 26mpg EPA / 100
            float mpgForCalc = telemetry.averageMPG > 0 ? telemetry.averageMPG : 26.0f;
            displayRange = (int)(telemetry.fuelLevel * 12.7f * mpgForCalc / 100.0f);
        }
        
        // Range color (based on actual display value)
        uint16_t rangeColor = MX5_GREEN;
        if (displayRange < 30) rangeColor = MX5_RED;
        else if (displayRange < 60) rangeColor = MX5_ORANGE;
        else if (displayRange < 100) rangeColor = MX5_YELLOW;
        
        // Draw box background
        LCD_FillRoundRect(gasBoxX, sideBoxY, gasBoxW, sideBoxH, 4, COLOR_BG_CARD);
        LCD_FillRect(gasBoxX, sideBoxY, 3, sideBoxH, accentColor);  // Left accent bar
        
        // "GAS" label (grey)
        LCD_DrawString(gasBoxX + 6, sideBoxY + 3, "GAS", MX5_GRAY, COLOR_BG_CARD, 1);
        
        // MPG value (row 1) - size 2 to match tank% and range
        char mpgStr[10];
        // Always show MPG - defaults to EPA average (26) if no data yet
        snprintf(mpgStr, sizeof(mpgStr), "%.0fmpg", telemetry.averageMPG > 0 ? telemetry.averageMPG : 26.0f);
        LCD_DrawString(gasBoxX + 6, sideBoxY + 16, mpgStr, mpgColor, COLOR_BG_CARD, 2);
        
        // Tank % (row 2)
        char tankStr[10];
        snprintf(tankStr, sizeof(tankStr), "%d%%", (int)telemetry.fuelLevel);
        LCD_DrawString(gasBoxX + 6, sideBoxY + 36, tankStr, tankColor, COLOR_BG_CARD, 2);
        
        // Range miles (row 3) - displayRange already calculated above
        char rangeStr[10];
        if (displayRange > 0) {
            snprintf(rangeStr, sizeof(rangeStr), "%dmi", displayRange);
        } else {
            snprintf(rangeStr, sizeof(rangeStr), "--mi");
        }
        LCD_DrawString(gasBoxX + 6, sideBoxY + 56, rangeStr, rangeColor, COLOR_BG_CARD, 2);
    }
    }  // End of hideDuringBoot else block
    
    // Navigation Lock indicator (bottom right when locked) - static, only on full redraw
    if (needsFullRedraw && navLocked) {
        int lockX = SCREEN_WIDTH - 35;
        int lockY = SCREEN_HEIGHT - 50;
        // Draw lock icon (small padlock shape)
        uint16_t lockColor = MX5_ORANGE;
        // Lock body (rounded rectangle)
        LCD_FillRoundRect(lockX - 6, lockY, 12, 10, 2, lockColor);
        // Lock shackle (arc above body)
        LCD_DrawCircle(lockX, lockY - 2, 5, lockColor);
        LCD_DrawCircle(lockX, lockY - 2, 4, lockColor);
        // Clear inside of shackle
        LCD_FillRect(lockX - 3, lockY - 2, 6, 4, COLOR_BG);
        LCD_DrawString(lockX - 9, lockY + 13, "LCK", MX5_ORANGE, COLOR_BG, 1);
    }
    
    // === TPMS (2x2 grid at bottom) - only redraw when TPMS changed ===
    if (needsFullRedraw || tpmsChanged) {
        int tireW = 55;
        int tireH = 38;
        int tireGap = 6;
        int tpmsStartX = CENTER_X - tireW - tireGap/2;
        int tpmsStartY = SCREEN_HEIGHT - 110;  // Fixed position at bottom
        
        const char* tireNames[] = {"FL", "FR", "RL", "RR"};
        int tirePositions[4][2] = {{0, 0}, {1, 0}, {0, 1}, {1, 1}}; // col, row
        
        for (int i = 0; i < 4; i++) {
            int col = tirePositions[i][0];
            int row = tirePositions[i][1];
            int tireX = tpmsStartX + col * (tireW + tireGap);
            int tireY = tpmsStartY + row * (tireH + tireGap);
            
            // Color based on pressure (PSI thresholds)
            // Green: 27-32 PSI (normal), Yellow: 25-26 or 36-38 PSI (caution), Red: <25 or >38 PSI (danger)
            uint16_t tireColor = MX5_GREEN;
            if (telemetry.tirePressure[i] < 25.0) tireColor = MX5_RED;          // Danger: < 25 PSI
            else if (telemetry.tirePressure[i] < 27.0) tireColor = MX5_YELLOW;  // Caution: 25-26 PSI
            else if (telemetry.tirePressure[i] > 38.0) tireColor = MX5_RED;     // Danger: > 38 PSI
            else if (telemetry.tirePressure[i] > 32.0) tireColor = MX5_YELLOW;  // Caution: 33-38 PSI
            
            LCD_FillRoundRect(tireX, tireY, tireW, tireH, 3, COLOR_BG_CARD);
            LCD_FillRect(tireX, tireY, 2, tireH, tireColor);
            
            // Tire name + PSI on same line
            LCD_DrawString(tireX + 5, tireY + 4, tireNames[i], MX5_GRAY, COLOR_BG_CARD, 1);
            char psiStr[8];
            snprintf(psiStr, sizeof(psiStr), "%.1f", telemetry.tirePressure[i]);
            LCD_DrawString(tireX + 5, tireY + 18, psiStr, tireColor, COLOR_BG_CARD, 2);
        }
    }
    
    // Page indicator only needs redraw on full redraw (it's static)
    if (needsFullRedraw) {
        drawPageIndicator();
    }
    
    // Update cached values for next comparison
    prevTelemetry.rpm = telemetry.rpm;
    prevTelemetry.speed = telemetry.speed;
    prevTelemetry.gear = telemetry.gear;
    prevTelemetry.coolantTemp = telemetry.coolantTemp;
    prevTelemetry.fuelLevel = telemetry.fuelLevel;
    prevTelemetry.ambientTemp = telemetry.ambientTemp;
    prevTelemetry.averageMPG = telemetry.averageMPG;
    prevTelemetry.rangeMiles = telemetry.rangeMiles;
    prevTelemetry.engineRunning = telemetry.engineRunning;
    prevTelemetry.connected = telemetry.connected;
    prevTelemetry.oilWarning = telemetry.oilWarning;
    prevTelemetry.headlightsOn = telemetry.headlightsOn;
    prevTelemetry.highBeamsOn = telemetry.highBeamsOn;
    for (int i = 0; i < 4; i++) {
        prevTelemetry.tirePressure[i] = telemetry.tirePressure[i];
    }
    prevTelemetry.initialized = true;
}

void drawRPMScreen() {
    // Check if any displayed values have changed
    bool valuesChanged = !prevTelemetry.initialized ||
        (int)telemetry.rpm != (int)prevTelemetry.rpm ||
        (int)telemetry.speed != (int)prevTelemetry.speed ||
        telemetry.gear != prevTelemetry.gear;
    
    // Skip if nothing changed and not a full redraw
    if (!needsFullRedraw && !valuesChanged) return;
    
    // If full redraw needed, draw background
    if (needsFullRedraw) {
        drawBackground();
    }
    
    // === LARGE GEAR INDICATOR (Top) ===
    int gearY = 55;
    
    // Gear color based on RPM
    uint16_t gearColor = MX5_GREEN;
    if (telemetry.rpm > 6500) gearColor = MX5_RED;
    else if (telemetry.rpm > 5500) gearColor = MX5_ORANGE;
    else if (telemetry.rpm > 4500) gearColor = MX5_YELLOW;
    
    // Large gear number
    char gearStr[4];
    if (telemetry.gear == 0) snprintf(gearStr, sizeof(gearStr), "N");
    else if (telemetry.gear == -1) snprintf(gearStr, sizeof(gearStr), "R");
    else snprintf(gearStr, sizeof(gearStr), "%d", telemetry.gear);
    
    // Draw gear in large font (size 4 = 28px wide per char)
    int gearStrLen = strlen(gearStr);
    LCD_DrawString(CENTER_X - gearStrLen * 14, gearY, gearStr, gearColor, COLOR_BG, 4);
    LCD_DrawString(CENTER_X - 18, gearY + 38, "GEAR", MX5_GRAY, COLOR_BG, 1);
    
    // === RPM ARC GAUGE (Center) ===
    float rpmPercent = constrain(telemetry.rpm / 8000.0, 0, 1);
    int gaugeRadius = 95;
    int gaugeY = CENTER_Y + 25;
    
    // Track which segment was last active to minimize redraws
    static int prevActiveSegment = -1;
    int numSegments = 20;
    int currentActiveSegment = (int)(rpmPercent * numSegments);
    if (currentActiveSegment > numSegments) currentActiveSegment = numSegments;
    
    // Only redraw segments that changed state (or all on full redraw)
    for (int i = 0; i < numSegments; i++) {
        bool wasActive = (i < prevActiveSegment);
        bool isActive = (i < currentActiveSegment);
        
        // Skip if segment state unchanged and not full redraw
        if (!needsFullRedraw && wasActive == isActive) continue;
        
        float segStart = i / (float)numSegments;
        
        // Determine segment color - inactive segments get dark gray
        uint16_t segColor;
        if (isActive) {
            float rpmAt = segStart * 8000;
            if (rpmAt >= 6400) segColor = MX5_RED;
            else if (rpmAt >= 5600) segColor = MX5_ORANGE;
            else if (rpmAt >= 4000) segColor = MX5_YELLOW;
            else segColor = MX5_GREEN;
        } else {
            segColor = MX5_DARKGRAY;
        }
        
        // Arc from -150° to +150° (300° total, open at top)
        float startAngle = (120 + i * 15) * PI / 180.0;
        float endAngle = (120 + (i + 1) * 15) * PI / 180.0;
        
        // Draw thick arc segment
        for (float a = startAngle; a < endAngle; a += 0.02) {
            int px = CENTER_X + cos(a) * gaugeRadius;
            int py = gaugeY + sin(a) * gaugeRadius;
            LCD_FillCircle(px, py, 8, segColor);
        }
    }
    prevActiveSegment = currentActiveSegment;
    
    // RPM tick labels (0, 2, 4, 6, 8)
    const char* rpmLabels[] = {"0", "2", "4", "6", "8"};
    for (int i = 0; i < 5; i++) {
        float angle = (120 + i * 75) * PI / 180.0;
        int lx = CENTER_X + cos(angle) * (gaugeRadius + 22) - 4;
        int ly = gaugeY + sin(angle) * (gaugeRadius + 22) - 4;
        LCD_DrawString(lx, ly, rpmLabels[i], MX5_GRAY, COLOR_BG, 1);
    }
    
    // === RPM VALUE (Center of gauge) ===
    char rpmStr[8];
    snprintf(rpmStr, sizeof(rpmStr), "%d", (int)telemetry.rpm);
    int rpmLen = strlen(rpmStr);
    LCD_DrawString(CENTER_X - rpmLen * 10, gaugeY + 5, rpmStr, MX5_WHITE, COLOR_BG, 3);
    LCD_DrawString(CENTER_X - 12, gaugeY + 35, "RPM", MX5_GRAY, COLOR_BG, 1);
    
    // === SPEED (Bottom) ===
    int speedY = SCREEN_HEIGHT - 50;
    char speedStr[8];
    snprintf(speedStr, sizeof(speedStr), "%d", (int)telemetry.speed);
    int speedLen = strlen(speedStr);
    LCD_DrawString(CENTER_X - speedLen * 10, speedY, speedStr, MX5_CYAN, COLOR_BG, 3);
    LCD_DrawString(CENTER_X - 12, speedY + 28, "MPH", MX5_GRAY, COLOR_BG, 1);
    
    // === THROTTLE BAR (Right side) ===
    int barW = 16, barH = 80;
    int barY = CENTER_Y - 10;
    int throttleX = CENTER_X + 115;
    
    LCD_DrawString(throttleX - 4, barY - 14, "THR", MX5_GRAY, COLOR_BG, 1);
    LCD_FillRoundRect(throttleX, barY, barW, barH, 5, MX5_DARKGRAY);
    int throttleFill = (int)(barH * telemetry.throttle / 100.0);
    if (throttleFill > 10) {
        LCD_FillRoundRect(throttleX, barY + barH - throttleFill, barW, throttleFill, 5, MX5_GREEN);
    } else if (throttleFill > 0) {
        LCD_FillRect(throttleX, barY + barH - throttleFill, barW, throttleFill, MX5_GREEN);
    }
    LCD_DrawRoundRect(throttleX, barY, barW, barH, 5, MX5_GRAY);
    
    // Throttle percentage
    char thrPct[8];
    snprintf(thrPct, sizeof(thrPct), "%d%%", (int)telemetry.throttle);
    LCD_DrawString(throttleX - 2, barY + barH + 5, thrPct, MX5_GREEN, COLOR_BG, 1);
    
    // === BRAKE BAR (Left side) ===
    int brakeX = CENTER_X - 115 - barW;
    LCD_DrawString(brakeX, barY - 14, "BRK", MX5_GRAY, COLOR_BG, 1);
    LCD_FillRoundRect(brakeX, barY, barW, barH, 5, MX5_DARKGRAY);
    int brakeFill = (int)(barH * telemetry.brake / 100.0);
    if (brakeFill > 10) {
        LCD_FillRoundRect(brakeX, barY + barH - brakeFill, barW, brakeFill, 5, MX5_RED);
    } else if (brakeFill > 0) {
        LCD_FillRect(brakeX, barY + barH - brakeFill, barW, brakeFill, MX5_RED);
    }
    LCD_DrawRoundRect(brakeX, barY, barW, barH, 5, MX5_GRAY);
    
    // Brake percentage
    char brkPct[8];
    snprintf(brkPct, sizeof(brkPct), "%d%%", (int)telemetry.brake);
    LCD_DrawString(brakeX, barY + barH + 5, brkPct, MX5_RED, COLOR_BG, 1);
    
    drawPageIndicator();
    
    // Update cache for RPM screen values
    prevTelemetry.rpm = telemetry.rpm;
    prevTelemetry.speed = telemetry.speed;
    prevTelemetry.gear = telemetry.gear;
    prevTelemetry.initialized = true;
}

void drawTPMSScreen() {
    // Only draw on full redraw to prevent flickering overlaps
    if (!needsFullRedraw) return;
    
    drawBackground();
    
    // === TITLE ===
    LCD_DrawString(CENTER_X - 24, 25, "TPMS", MX5_WHITE, COLOR_BG, 2);
    
    // === CAR BODY OUTLINE (programmatic, clean look) ===
    int carW = 60, carH = 110;
    int carX = CENTER_X - carW/2;
    int carY = CENTER_Y - carH/2;
    
    // Main body (rounded for car shape)
    LCD_FillRoundRect(carX, carY, carW, carH, 12, COLOR_BG_CARD);
    LCD_DrawRoundRect(carX, carY, carW, carH, 12, MX5_GRAY);
    
    // Windshield (front, top of car)
    LCD_DrawLine(carX + 8, carY + 15, carX + carW - 8, carY + 15, MX5_ACCENT);
    LCD_DrawLine(carX + 5, carY + 25, carX + carW - 5, carY + 25, MX5_ACCENT);
    
    // Rear window
    LCD_DrawLine(carX + 8, carY + carH - 15, carX + carW - 8, carY + carH - 15, MX5_ACCENT);
    LCD_DrawLine(carX + 5, carY + carH - 25, carX + carW - 5, carY + carH - 25, MX5_ACCENT);
    
    // Center line
    LCD_DrawLine(carX + carW/2, carY + 30, carX + carW/2, carY + carH - 30, MX5_DARKGRAY);
    
    // === TIRE PRESSURE INDICATORS ===
    const int tireW = 26, tireH = 40;
    const int tireOffsetX = 55, tireOffsetY = 38;
    
    // Helper lambda for tire color based on pressure (PSI)
    // Green: 27-32 PSI (normal), Yellow: 25-26 or 36-38 PSI (caution), Red: <25 or >38 PSI (danger)
    auto getTireColor = [](float psi) -> uint16_t {
        if (psi < 25.0) return MX5_RED;      // Danger: Risk of sidewall damage
        if (psi < 27.0) return MX5_YELLOW;   // Caution: Check for slow leak
        if (psi > 38.0) return MX5_RED;      // Danger: Risk of overheating
        if (psi > 32.0) return MX5_YELLOW;   // Caution: Slightly overinflated
        return MX5_GREEN;                    // Normal: 27-32 PSI
    };
    
    // Helper to draw tire with tread pattern (rounded)
    auto drawTire = [&](int x, int y, uint16_t color) {
        LCD_FillRoundRect(x, y, tireW, tireH, 6, color);
        LCD_DrawRoundRect(x, y, tireW, tireH, 6, MX5_WHITE);
        // Tread pattern
        for (int i = 8; i < tireH - 8; i += 8) {
            LCD_FillRoundRect(x + 4, y + i, tireW - 8, 3, 1, COLOR_BG_CARD);
        }
    };
    
    // Front Left tire
    uint16_t flColor = getTireColor(telemetry.tirePressure[0]);
    int flX = CENTER_X - tireOffsetX - tireW/2;
    int flY = CENTER_Y - tireOffsetY - tireH/2;
    drawTire(flX, flY, flColor);
    
    // Front Right tire
    uint16_t frColor = getTireColor(telemetry.tirePressure[1]);
    int frX = CENTER_X + tireOffsetX - tireW/2;
    int frY = CENTER_Y - tireOffsetY - tireH/2;
    drawTire(frX, frY, frColor);
    
    // Rear Left tire
    uint16_t rlColor = getTireColor(telemetry.tirePressure[2]);
    int rlX = CENTER_X - tireOffsetX - tireW/2;
    int rlY = CENTER_Y + tireOffsetY - tireH/2;
    drawTire(rlX, rlY, rlColor);
    
    // Rear Right tire
    uint16_t rrColor = getTireColor(telemetry.tirePressure[3]);
    int rrX = CENTER_X + tireOffsetX - tireW/2;
    int rrY = CENTER_Y + tireOffsetY - tireH/2;
    drawTire(rrX, rrY, rrColor);
    
    // === PRESSURE, TEMPERATURE, AND TIMESTAMP LABELS ===
    char psiStr[8];
    char tempStr[8];
    
    // Front Left - use per-tire timestamp from Pi
    snprintf(psiStr, sizeof(psiStr), "%.1f", telemetry.tirePressure[0]);
    snprintf(tempStr, sizeof(tempStr), "%.1fF", telemetry.tireTemp[0]);
    uint16_t fl_time_color = (tpmsLastUpdateStr[0][0] != '-') ? MX5_GREEN : MX5_DARKGRAY;
    LCD_DrawString(flX - 50, flY + 2, psiStr, flColor, COLOR_BG, 2);
    LCD_DrawString(flX - 50, flY + 20, "PSI", MX5_GRAY, COLOR_BG, 1);
    LCD_DrawString(flX - 50, flY + 32, tempStr, MX5_ACCENT, COLOR_BG, 1);
    LCD_DrawString(flX - 66, flY - 14, "FL", MX5_GRAY, COLOR_BG, 1);
    LCD_DrawString(flX - 50, flY - 14, tpmsLastUpdateStr[0], fl_time_color, COLOR_BG, 1);
    
    // Front Right - use per-tire timestamp from Pi
    snprintf(psiStr, sizeof(psiStr), "%.1f", telemetry.tirePressure[1]);
    snprintf(tempStr, sizeof(tempStr), "%.1fF", telemetry.tireTemp[1]);
    uint16_t fr_time_color = (tpmsLastUpdateStr[1][0] != '-') ? MX5_GREEN : MX5_DARKGRAY;
    LCD_DrawString(frX + tireW + 8, frY + 2, psiStr, frColor, COLOR_BG, 2);
    LCD_DrawString(frX + tireW + 8, frY + 20, "PSI", MX5_GRAY, COLOR_BG, 1);
    LCD_DrawString(frX + tireW + 8, frY + 32, tempStr, MX5_ACCENT, COLOR_BG, 1);
    LCD_DrawString(frX + 6, frY - 14, "FR", MX5_GRAY, COLOR_BG, 1);
    LCD_DrawString(frX + 24, frY - 14, tpmsLastUpdateStr[1], fr_time_color, COLOR_BG, 1);
    
    // Rear Left - use per-tire timestamp from Pi
    snprintf(psiStr, sizeof(psiStr), "%.1f", telemetry.tirePressure[2]);
    snprintf(tempStr, sizeof(tempStr), "%.1fF", telemetry.tireTemp[2]);
    uint16_t rl_time_color = (tpmsLastUpdateStr[2][0] != '-') ? MX5_GREEN : MX5_DARKGRAY;
    LCD_DrawString(rlX - 50, rlY + 2, psiStr, rlColor, COLOR_BG, 2);
    LCD_DrawString(rlX - 50, rlY + 20, "PSI", MX5_GRAY, COLOR_BG, 1);
    LCD_DrawString(rlX - 50, rlY + 32, tempStr, MX5_ACCENT, COLOR_BG, 1);
    LCD_DrawString(rlX - 66, rlY + tireH + 4, "RL", MX5_GRAY, COLOR_BG, 1);
    LCD_DrawString(rlX - 50, rlY + tireH + 4, tpmsLastUpdateStr[2], rl_time_color, COLOR_BG, 1);
    
    // Rear Right - use per-tire timestamp from Pi
    snprintf(psiStr, sizeof(psiStr), "%.1f", telemetry.tirePressure[3]);
    snprintf(tempStr, sizeof(tempStr), "%.1fF", telemetry.tireTemp[3]);
    uint16_t rr_time_color = (tpmsLastUpdateStr[3][0] != '-') ? MX5_GREEN : MX5_DARKGRAY;
    LCD_DrawString(rrX + tireW + 8, rrY + 2, psiStr, rrColor, COLOR_BG, 2);
    LCD_DrawString(rrX + tireW + 8, rrY + 20, "PSI", MX5_GRAY, COLOR_BG, 1);
    LCD_DrawString(rrX + tireW + 8, rrY + 32, tempStr, MX5_ACCENT, COLOR_BG, 1);
    LCD_DrawString(rrX + 6, rrY + tireH + 4, "RR", MX5_GRAY, COLOR_BG, 1);
    LCD_DrawString(rrX + 24, rrY + tireH + 4, tpmsLastUpdateStr[3], rr_time_color, COLOR_BG, 1);
    
    // === STATUS BAR ===
    bool allGood = (flColor == MX5_GREEN && frColor == MX5_GREEN && 
                   rlColor == MX5_GREEN && rrColor == MX5_GREEN);
    const char* statusText = allGood ? "ALL TIRES OK" : "CHECK PRESSURE";
    uint16_t statusColor = allGood ? MX5_GREEN : MX5_ORANGE;
    LCD_DrawString(CENTER_X - 54, SCREEN_HEIGHT - 50, statusText, statusColor, COLOR_BG, 1);
    
    drawPageIndicator();
}

void drawEngineScreen() {
    // Only draw on full redraw to prevent flickering overlaps
    if (!needsFullRedraw) return;
    
    drawBackground();
    
    // === TITLE ===
    LCD_DrawString(CENTER_X - 36, 20, "ENGINE", MX5_WHITE, COLOR_BG, 2);
    
    int cardW = 140, cardH = 70;
    int gap = 12;
    int startX = CENTER_X - cardW - gap/2;
    int startY = CENTER_Y - cardH - gap/2 - 5;
    
    // === COOLANT TEMP (Top Left) ===
    uint16_t coolantColor = MX5_BLUE;
    if (telemetry.coolantTemp > 230) coolantColor = MX5_RED;
    else if (telemetry.coolantTemp > 215) coolantColor = MX5_ORANGE;
    
    LCD_FillRoundRect(startX, startY, cardW, cardH, CARD_RADIUS, COLOR_BG_CARD);
    LCD_DrawRoundRect(startX, startY, cardW, cardH, CARD_RADIUS, coolantColor);
    
    // Label
    LCD_DrawString(startX + 10, startY + 8, "COOLANT", MX5_GRAY, COLOR_BG_CARD, 1);
    
    // Temperature value
    char tempStr[12];
    snprintf(tempStr, sizeof(tempStr), "%d F", (int)telemetry.coolantTemp);
    LCD_DrawString(startX + 10, startY + 24, tempStr, coolantColor, COLOR_BG_CARD, 2);
    
    // Progress bar (rounded)
    float coolantPct = constrain((telemetry.coolantTemp - 100) / 150.0, 0, 1);
    LCD_FillRoundRect(startX + 10, startY + cardH - 20, cardW - 20, 12, 4, MX5_DARKGRAY);
    int coolFillW = (int)((cardW - 20) * coolantPct);
    if (coolFillW > 8) {
        LCD_FillRoundRect(startX + 10, startY + cardH - 20, coolFillW, 12, 4, coolantColor);
    }
    
    // === OIL TEMP (Top Right) ===
    uint16_t oilColor = MX5_ORANGE;
    if (telemetry.oilTemp > 260) oilColor = MX5_RED;
    else if (telemetry.oilTemp < 180) oilColor = MX5_BLUE;
    
    int rightX = startX + cardW + gap;
    LCD_FillRoundRect(rightX, startY, cardW, cardH, CARD_RADIUS, COLOR_BG_CARD);
    LCD_DrawRoundRect(rightX, startY, cardW, cardH, CARD_RADIUS, oilColor);
    
    // Label
    LCD_DrawString(rightX + 10, startY + 8, "OIL TEMP", MX5_GRAY, COLOR_BG_CARD, 1);
    
    // Temperature value
    snprintf(tempStr, sizeof(tempStr), "%d F", (int)telemetry.oilTemp);
    LCD_DrawString(rightX + 10, startY + 24, tempStr, oilColor, COLOR_BG_CARD, 2);
    
    // Progress bar (rounded)
    float oilPct = constrain((telemetry.oilTemp - 150) / 150.0, 0, 1);
    LCD_FillRoundRect(rightX + 10, startY + cardH - 20, cardW - 20, 12, 4, MX5_DARKGRAY);
    int oilFillW = (int)((cardW - 20) * oilPct);
    if (oilFillW > 8) {
        LCD_FillRoundRect(rightX + 10, startY + cardH - 20, oilFillW, 12, 4, oilColor);
    }
    
    // === FUEL LEVEL (Bottom Left) ===
    uint16_t fuelColor = MX5_YELLOW;
    if (telemetry.fuelLevel < 15) fuelColor = MX5_RED;
    else if (telemetry.fuelLevel < 25) fuelColor = MX5_ORANGE;
    
    int bottomY = CENTER_Y + gap/2 - 5;
    LCD_FillRoundRect(startX, bottomY, cardW, cardH, CARD_RADIUS, COLOR_BG_CARD);
    LCD_DrawRoundRect(startX, bottomY, cardW, cardH, CARD_RADIUS, fuelColor);
    
    // Label
    LCD_DrawString(startX + 10, bottomY + 8, "FUEL", MX5_GRAY, COLOR_BG_CARD, 1);
    
    // Fuel value
    char fuelStr[12];
    snprintf(fuelStr, sizeof(fuelStr), "%d%%", (int)telemetry.fuelLevel);
    LCD_DrawString(startX + 10, bottomY + 24, fuelStr, fuelColor, COLOR_BG_CARD, 2);
    
    // Progress bar (rounded)
    LCD_FillRoundRect(startX + 10, bottomY + cardH - 20, cardW - 20, 12, 4, MX5_DARKGRAY);
    int fuelFillW = (int)((cardW - 20) * telemetry.fuelLevel / 100.0);
    if (fuelFillW > 8) {
        LCD_FillRoundRect(startX + 10, bottomY + cardH - 20, fuelFillW, 12, 4, fuelColor);
    }
    
    // === AMBIENT TEMP (Bottom Right) ===
    uint16_t ambientColor = MX5_GREEN;
    if (telemetry.ambientTemp < 32) ambientColor = MX5_CYAN;  // Freezing
    else if (telemetry.ambientTemp > 95) ambientColor = MX5_RED;  // Hot
    else if (telemetry.ambientTemp > 85) ambientColor = MX5_ORANGE;  // Warm
    
    LCD_FillRoundRect(rightX, bottomY, cardW, cardH, CARD_RADIUS, COLOR_BG_CARD);
    LCD_DrawRoundRect(rightX, bottomY, cardW, cardH, CARD_RADIUS, ambientColor);
    
    // Label
    LCD_DrawString(rightX + 10, bottomY + 8, "AMBIENT", MX5_GRAY, COLOR_BG_CARD, 1);
    
    // Temperature value
    char ambStr[12];
    snprintf(ambStr, sizeof(ambStr), "%.0f°F", telemetry.ambientTemp);
    LCD_DrawString(rightX + 10, bottomY + 24, ambStr, ambientColor, COLOR_BG_CARD, 2);
    
    drawPageIndicator();
}

void drawGForceScreen() {
    // Static variables to track previous state for partial redraw
    static int prevGX = CENTER_X;
    static int prevGY = CENTER_Y;
    static int prevBallRadius = 14;
    static float prevPitch = 0;
    static float prevRoll = 0;
    static float prevForwardAccel = 0;
    static bool firstDraw = true;
    
    // ==========================================================================
    // G-FORCE DISPLAY LOGIC (ESP32-S3 mounted vertically in oil gauge hole)
    // ==========================================================================
    // 
    // CIRCLE POSITION = Car orientation (tilt from gyroscope + accelerometer)
    //   - Nose DOWN  → circle moves UP (top of screen)
    //   - Nose UP    → circle moves DOWN (bottom of screen)
    //   - Roll LEFT  → circle moves LEFT
    //   - Roll RIGHT → circle moves RIGHT
    //   - 10 degrees tilt = circle at outer ring edge (2.5°, 5°, 10° grid)
    //
    // CIRCLE SIZE = Forward acceleration (linear accel, gravity-subtracted)
    //   - Zero acceleration → normal size (14px radius)
    //   - Acceleration (speeding up) → circle GROWS (up to 24px)
    //   - Deceleration (braking) → circle SHRINKS (down to 6px)
    // ==========================================================================
    
    // Ball POSITION based on orientation (pitch/roll in degrees)
    // Grid: 2.5° = 30px, 5° = 60px, 10° = 120px (outer ring)
    float maxDegrees = 10.0;
    int maxRadius = 120;
    float pixelsPerDegree = maxRadius / maxDegrees;  // 12 px per degree
    
    // Position mapping:
    // - orientationPitch: positive = nose UP, negative = nose DOWN
    // - orientationRoll: positive = roll RIGHT, negative = roll LEFT
    // - Screen Y: positive = down, negative = up
    // So: nose DOWN (negative pitch) → ball UP (negative Y offset) → use +pitch
    //     nose UP (positive pitch) → ball DOWN (positive Y offset) → use +pitch
    //     roll LEFT (negative roll) → ball LEFT → use roll directly
    //     roll RIGHT (positive roll) → ball RIGHT → use roll directly
    int gX = CENTER_X + (int)(orientationRoll * pixelsPerDegree);
    int gY = CENTER_Y + (int)(orientationPitch * pixelsPerDegree);  // Nose up = ball down
    
    // Ball SIZE based on FORWARD acceleration only (not total magnitude)
    // linearAccelY = forward acceleration with gravity subtracted
    // Positive = accelerating forward, Negative = braking
    float forwardAccel = telemetry.linearAccelY;  // In G units
    // Base radius 14, grows with accel (+10 at 1G), shrinks with decel (-8 at -1G)
    int ballRadius = 14 + (int)(forwardAccel * 10);
    ballRadius = max(6, min(24, ballRadius));
    
    // Clamp to circle
    float dist = sqrt(pow(gX - CENTER_X, 2) + pow(gY - CENTER_Y, 2));
    if (dist > maxRadius) {
        float scale = maxRadius / dist;
        gX = CENTER_X + (int)((gX - CENTER_X) * scale);
        gY = CENTER_Y + (int)((gY - CENTER_Y) * scale);
    }
    
    // Color based on forward acceleration (green=neutral, red=hard accel, blue=hard brake)
    uint16_t dotColor = MX5_GREEN;
    if (forwardAccel > 0.5) dotColor = MX5_RED;        // Hard acceleration
    else if (forwardAccel > 0.2) dotColor = MX5_ORANGE;
    else if (forwardAccel < -0.5) dotColor = MX5_CYAN; // Hard braking
    else if (forwardAccel < -0.2) dotColor = MX5_YELLOW;
    
    if (needsFullRedraw || firstDraw) {
        firstDraw = false;
        // Full redraw - draw everything
        drawBackground();
        
        // === TITLE ===
        LCD_DrawString(CENTER_X - 24, 20, "TILT", MX5_WHITE, COLOR_BG, 2);
        
        // Draw grid circles for tilt degrees (2.5°, 5°, 10°)
        LCD_DrawCircle(CENTER_X, CENTER_Y, 30, MX5_DARKGRAY);   // 2.5°
        LCD_DrawCircle(CENTER_X, CENTER_Y, 60, MX5_DARKGRAY);   // 5°
        LCD_DrawCircle(CENTER_X, CENTER_Y, 120, MX5_DARKGRAY);  // 10°
        
        // Draw crosshairs
        LCD_DrawLine(CENTER_X - 130, CENTER_Y, CENTER_X + 130, CENTER_Y, MX5_DARKGRAY);
        LCD_DrawLine(CENTER_X, CENTER_Y - 130, CENTER_X, CENTER_Y + 130, MX5_DARKGRAY);
        
        // Degree labels on right side of rings (degrees of tilt)
        LCD_DrawString(CENTER_X + 33, CENTER_Y - 6, "2.5\xF8", MX5_GRAY, COLOR_BG, 1);  // \xF8 = degree symbol
        LCD_DrawString(CENTER_X + 63, CENTER_Y - 6, "5\xF8", MX5_GRAY, COLOR_BG, 1);
        LCD_DrawString(CENTER_X + 123, CENTER_Y - 6, "10\xF8", MX5_GRAY, COLOR_BG, 1);
        
        // Fixed center reference point
        LCD_FillCircle(CENTER_X, CENTER_Y, 3, MX5_WHITE);
        
        // Draw G-force indicator ball (size based on forward acceleration)
        LCD_FillCircle(gX, gY, ballRadius, dotColor);
        LCD_DrawCircle(gX, gY, ballRadius, MX5_WHITE);
        LCD_DrawCircle(gX, gY, ballRadius + 1, MX5_WHITE);
        
        // === INFO BOX (Bottom) - show forward accel and tilt ===
        int infoY = SCREEN_HEIGHT - 55;
        LCD_FillRoundRect(CENTER_X - 100, infoY, 200, 50, 10, COLOR_BG_CARD);
        LCD_DrawRoundRect(CENTER_X - 100, infoY, 200, 50, 10, MX5_ACCENT);
        
        // Show pitch/roll orientation (degrees) and forward acceleration
        char gStr[20];
        snprintf(gStr, sizeof(gStr), "Pitch:%+.1f\xF8", orientationPitch);  // \xF8 = degree symbol
        LCD_DrawString(CENTER_X - 90, infoY + 6, gStr, MX5_CYAN, COLOR_BG_CARD, 1);
        
        snprintf(gStr, sizeof(gStr), "Roll:%+.1f\xF8", orientationRoll);
        LCD_DrawString(CENTER_X - 90, infoY + 20, gStr, MX5_GREEN, COLOR_BG_CARD, 1);
        
        snprintf(gStr, sizeof(gStr), "Fwd:%+.2fG", forwardAccel);
        LCD_DrawString(CENTER_X - 90, infoY + 34, gStr, dotColor, COLOR_BG_CARD, 1);
        
        // Large forward accel display on right side
        snprintf(gStr, sizeof(gStr), "%+.1fG", forwardAccel);
        LCD_DrawString(CENTER_X + 30, infoY + 16, gStr, dotColor, COLOR_BG_CARD, 2);
        
        drawPageIndicator();
        
        // Save current state
        prevGX = gX;
        prevGY = gY;
        prevPitch = orientationPitch;
        prevRoll = orientationRoll;
        prevForwardAccel = forwardAccel;
        prevBallRadius = ballRadius;
    } else {
        // Partial redraw - only update if position or size changed significantly
        // Increase thresholds to reduce redraw frequency
        bool ballMoved = (abs(gX - prevGX) > 2 || abs(gY - prevGY) > 2);
        bool ballSizeChanged = (abs(ballRadius - prevBallRadius) > 2);
        
        // Only update text values every 100ms (10 Hz) to reduce flickering
        static unsigned long lastValueUpdate = 0;
        bool valuesChanged = (millis() - lastValueUpdate > 100) && 
                             (abs(orientationPitch - prevPitch) > 0.3 || 
                              abs(orientationRoll - prevRoll) > 0.3 ||
                              abs(forwardAccel - prevForwardAccel) > 0.05);
        
        if (ballMoved || ballSizeChanged) {
            // Erase old ball - use a simple rectangle instead of circle for speed
            int eraseSize = prevBallRadius + 3;
            LCD_FillRect(prevGX - eraseSize, prevGY - eraseSize, 
                        eraseSize * 2, eraseSize * 2, COLOR_BG);
            
            // Only redraw grid elements if ball was near them
            // Check crosshairs
            if (abs(prevGY - CENTER_Y) < eraseSize + 2) {
                // Horizontal line segment
                LCD_DrawLine(prevGX - eraseSize - 5, CENTER_Y, 
                            prevGX + eraseSize + 5, CENTER_Y, MX5_DARKGRAY);
            }
            if (abs(prevGX - CENTER_X) < eraseSize + 2) {
                // Vertical line segment
                LCD_DrawLine(CENTER_X, prevGY - eraseSize - 5, 
                            CENTER_X, prevGY + eraseSize + 5, MX5_DARKGRAY);
            }
            
            // Only redraw grid circles if ball was near them
            float prevDist = sqrt(pow(prevGX - CENTER_X, 2) + pow(prevGY - CENTER_Y, 2));
            int gridRadii[3] = {30, 60, 120};
            for (int g = 0; g < 3; g++) {
                if (abs(prevDist - gridRadii[g]) < eraseSize + 5) {
                    LCD_DrawCircle(CENTER_X, CENTER_Y, gridRadii[g], MX5_DARKGRAY);
                }
            }
            
            // Redraw center reference if it was covered
            if (prevDist < eraseSize + 5) {
                LCD_FillCircle(CENTER_X, CENTER_Y, 3, MX5_WHITE);
            }
            
            // Draw new ball position
            LCD_FillCircle(gX, gY, ballRadius, dotColor);
            LCD_DrawCircle(gX, gY, ballRadius, MX5_WHITE);
            
            prevGX = gX;
            prevGY = gY;
            prevBallRadius = ballRadius;
        }
        
        if (valuesChanged) {
            lastValueUpdate = millis();
            // Only update the value text, not the whole box
            int infoY = SCREEN_HEIGHT - 55;
            
            // Clear value areas
            LCD_FillRect(CENTER_X - 92, infoY + 4, 80, 44, COLOR_BG_CARD);  // Pitch/Roll/Fwd area
            LCD_FillRect(CENTER_X + 28, infoY + 14, 65, 24, COLOR_BG_CARD); // Fwd G area
            
            // Redraw values - pitch, roll (degrees), and forward acceleration
            char gStr[20];
            snprintf(gStr, sizeof(gStr), "Pitch:%+.1f\xF8", orientationPitch);  // \xF8 = degree symbol
            LCD_DrawString(CENTER_X - 90, infoY + 6, gStr, MX5_CYAN, COLOR_BG_CARD, 1);
            
            snprintf(gStr, sizeof(gStr), "Roll:%+.1f\xF8", orientationRoll);
            LCD_DrawString(CENTER_X - 90, infoY + 20, gStr, MX5_GREEN, COLOR_BG_CARD, 1);
            
            snprintf(gStr, sizeof(gStr), "Fwd:%+.2fG", forwardAccel);
            LCD_DrawString(CENTER_X - 90, infoY + 34, gStr, dotColor, COLOR_BG_CARD, 1);
            
            snprintf(gStr, sizeof(gStr), "%+.1fG", forwardAccel);
            LCD_DrawString(CENTER_X + 30, infoY + 16, gStr, dotColor, COLOR_BG_CARD, 2);
            
            prevPitch = orientationPitch;
            prevRoll = orientationRoll;
            prevForwardAccel = forwardAccel;
        }
    }
}

// ============================================================================
// Helper Drawing Functions
// ============================================================================

void drawPageIndicator() {
    int dotSpacing = 12;
    int startX = CENTER_X - (SCREEN_COUNT * dotSpacing) / 2;
    int y = SCREEN_HEIGHT - 18;
    
    for (int i = 0; i < SCREEN_COUNT; i++) {
        uint16_t dotColor = (i == currentScreen) ? MX5_WHITE : MX5_DARKGRAY;
        int radius = (i == currentScreen) ? 4 : 3;
        LCD_FillCircle(startX + i * dotSpacing + 6, y, radius, dotColor);
    }
}

void drawCard(int x, int y, int w, int h, uint16_t borderColor) {
    LCD_FillRoundRect(x, y, w, h, CARD_RADIUS, COLOR_BG_CARD);
    LCD_DrawRoundRect(x, y, w, h, CARD_RADIUS, borderColor);
}

void drawProgressBar(int x, int y, int w, int h, float percent, uint16_t color) {
    percent = constrain(percent, 0, 100);
    LCD_FillRoundRect(x, y, w, h, BAR_RADIUS, MX5_DARKGRAY);
    int fillW = (int)(w * percent / 100.0);
    if (fillW > BAR_RADIUS * 2) {
        LCD_FillRoundRect(x, y, fillW, h, BAR_RADIUS, color);
    } else if (fillW > 0) {
        LCD_FillRect(x, y, fillW, h, color);
    }
    LCD_DrawRoundRect(x, y, w, h, BAR_RADIUS, MX5_GRAY);
}

// ============================================================================
// New Screen Functions (Diagnostics, System, Settings)
// ============================================================================

void drawDiagnosticsScreen() {
    // Only draw on full redraw to prevent flickering overlaps
    if (!needsFullRedraw) return;
    
    drawBackground();
    
    int startY = 40;
    int itemH = 42;
    int itemGap = 6;
    int itemW = 280;
    int startX = CENTER_X - itemW/2;
    
    // Warning indicator items
    // When not connected, show "NO DATA" in gray instead of false "OK"
    struct DiagItem {
        const char* name;
        bool isWarning;
        bool hasData;  // false when not connected (show gray "NO DATA")
        uint16_t colorOk;
        uint16_t colorWarn;
    };
    
    DiagItem items[] = {
        {"CHECK ENGINE", telemetry.checkEngine, telemetry.hasDiagnosticData, MX5_GREEN, MX5_RED},
        {"ABS SYSTEM", telemetry.absWarning, telemetry.hasDiagnosticData, MX5_GREEN, MX5_ORANGE},
        {"OIL PRESSURE", telemetry.oilWarning, telemetry.hasDiagnosticData, MX5_GREEN, MX5_RED},
        {"BATTERY", telemetry.batteryWarning, telemetry.hasDiagnosticData, MX5_GREEN, MX5_YELLOW},
        {"ENGINE RUN", !telemetry.engineRunning, telemetry.hasDiagnosticData, MX5_GREEN, MX5_RED},
        {"CONNECTION", !telemetry.connected, true, MX5_GREEN, MX5_ORANGE},  // Always has data
    };
    
    for (int i = 0; i < 6; i++) {
        int y = startY + i * (itemH + itemGap);
        
        // Determine status color and text based on connection state
        uint16_t statusColor;
        const char* statusText;
        
        if (!items[i].hasData) {
            // No data - show gray "NO DATA"
            statusColor = MX5_GRAY;
            statusText = "NO DATA";
        } else if (items[i].isWarning) {
            statusColor = items[i].colorWarn;
            statusText = "WARN";
        } else {
            statusColor = items[i].colorOk;
            statusText = "OK";
        }
        
        // Item background card (rounded)
        LCD_FillRoundRect(startX, y, itemW, itemH, CARD_RADIUS, COLOR_BG_CARD);
        
        // Left status indicator
        if (!items[i].hasData) {
            // Question mark for no data
            LCD_DrawString(startX + 18, y + 12, "?", MX5_GRAY, COLOR_BG_CARD, 2);
        } else if (items[i].isWarning) {
            // X shape for warning
            LCD_DrawLine(startX + 15, y + 13, startX + 30, y + itemH - 13, statusColor);
            LCD_DrawLine(startX + 16, y + 13, startX + 31, y + itemH - 13, statusColor);
            LCD_DrawLine(startX + 30, y + 13, startX + 15, y + itemH - 13, statusColor);
            LCD_DrawLine(startX + 31, y + 13, startX + 16, y + itemH - 13, statusColor);
        } else {
            // Checkmark shape for OK
            LCD_DrawLine(startX + 15, y + itemH/2, startX + 22, y + itemH - 12, statusColor);
            LCD_DrawLine(startX + 16, y + itemH/2, startX + 23, y + itemH - 12, statusColor);
            LCD_DrawLine(startX + 22, y + itemH - 12, startX + 35, y + 12, statusColor);
            LCD_DrawLine(startX + 23, y + itemH - 12, startX + 36, y + 12, statusColor);
        }
        
        // TEXT LABEL - draw the item name
        LCD_DrawString(startX + 50, y + 12, items[i].name, MX5_WHITE, COLOR_BG_CARD, 2);
        
        // Status text
        LCD_DrawString(startX + 50, y + itemH - 20, statusText, statusColor, COLOR_BG_CARD, 1);
        
        // Status circle on right
        int circleX = startX + itemW - 25;
        int circleY = y + itemH/2;
        LCD_FillCircle(circleX, circleY, 12, statusColor);
        LCD_DrawCircle(circleX, circleY, 12, MX5_WHITE);
        
        // Inner indicator (only for OK state with data)
        if (items[i].hasData && !items[i].isWarning) {
            LCD_FillCircle(circleX, circleY, 5, MX5_WHITE);
        }
        
        // Border with status color (rounded)
        LCD_DrawRoundRect(startX, y, itemW, itemH, CARD_RADIUS, statusColor);
    }
    
    drawPageIndicator();
}

void drawSystemScreen() {
    // Only draw on full redraw to prevent flickering overlaps
    if (!needsFullRedraw) return;
    
    drawBackground();
    
    int startY = 40;
    int itemH = 50;
    int itemGap = 8;
    int itemW = 290;
    int startX = CENTER_X - itemW/2;
    
    // === IMU STATUS ===
    uint16_t imuColor = imuAvailable ? MX5_GREEN : MX5_RED;
    LCD_FillRoundRect(startX, startY, itemW, itemH, CARD_RADIUS, COLOR_BG_CARD);
    LCD_DrawRoundRect(startX, startY, itemW, itemH, CARD_RADIUS, imuColor);
    
    // IMU icon (accelerometer shape)
    int iconX = startX + 30;
    int iconY = startY + itemH/2;
    LCD_DrawRect(iconX - 10, iconY - 10, 20, 20, imuColor);
    LCD_DrawLine(iconX, iconY - 15, iconX, iconY + 15, imuColor);
    LCD_DrawLine(iconX - 15, iconY, iconX + 15, iconY, imuColor);
    LCD_FillCircle(iconX, iconY, 4, imuColor);
    
    // Text label
    LCD_DrawString(startX + 55, startY + 10, "IMU SENSOR", MX5_WHITE, COLOR_BG_CARD, 2);
    const char* imuStatus = imuAvailable ? "READY" : "OFFLINE";
    LCD_DrawString(startX + 55, startY + 32, imuStatus, imuColor, COLOR_BG_CARD, 1);
    
    // Status indicator
    LCD_FillCircle(startX + itemW - 30, iconY, 10, imuColor);
    
    startY += itemH + itemGap;
    
    // === SERIAL STATUS ===
    uint16_t serialColor = telemetry.connected ? MX5_GREEN : MX5_ORANGE;
    LCD_FillRoundRect(startX, startY, itemW, itemH, CARD_RADIUS, COLOR_BG_CARD);
    LCD_DrawRoundRect(startX, startY, itemW, itemH, CARD_RADIUS, serialColor);
    
    // Serial/USB icon
    iconY = startY + itemH/2;
    LCD_FillRect(iconX - 8, iconY - 6, 16, 12, serialColor);
    LCD_FillRect(iconX - 4, iconY + 6, 8, 4, serialColor);
    LCD_FillRect(iconX - 2, iconY - 10, 4, 4, serialColor);
    
    // Text label
    LCD_DrawString(startX + 55, startY + 10, "PI SERIAL", MX5_WHITE, COLOR_BG_CARD, 2);
    const char* serialStatus = telemetry.connected ? "CONNECTED" : "WAITING";
    LCD_DrawString(startX + 55, startY + 32, serialStatus, serialColor, COLOR_BG_CARD, 1);
    
    LCD_FillCircle(startX + itemW - 30, iconY, 10, serialColor);
    
    startY += itemH + itemGap;
    
    // === DISPLAY INFO ===
    LCD_FillRoundRect(startX, startY, itemW, itemH, CARD_RADIUS, COLOR_BG_CARD);
    LCD_DrawRoundRect(startX, startY, itemW, itemH, CARD_RADIUS, MX5_ACCENT);
    
    // Display icon
    iconY = startY + itemH/2;
    LCD_DrawRect(iconX - 12, iconY - 8, 24, 16, MX5_ACCENT);
    LCD_FillRect(iconX - 10, iconY - 6, 20, 12, MX5_ACCENT);
    LCD_FillRect(iconX - 4, iconY + 8, 8, 3, MX5_ACCENT);
    LCD_FillRect(iconX - 8, iconY + 11, 16, 2, MX5_ACCENT);
    
    // Text label
    LCD_DrawString(startX + 55, startY + 10, "DISPLAY", MX5_WHITE, COLOR_BG_CARD, 2);
    LCD_DrawString(startX + 55, startY + 32, "360x360 ST77916", MX5_ACCENT, COLOR_BG_CARD, 1);
    
    // Info circle
    LCD_FillCircle(startX + itemW - 30, iconY, 10, MX5_ACCENT);
    
    startY += itemH + itemGap;
    
    // === MEMORY ===
    LCD_FillRoundRect(startX, startY, itemW, itemH, CARD_RADIUS, COLOR_BG_CARD);
    LCD_DrawRoundRect(startX, startY, itemW, itemH, CARD_RADIUS, MX5_PURPLE);
    
    // Memory chip icon
    iconY = startY + itemH/2;
    LCD_FillRect(iconX - 8, iconY - 10, 16, 20, MX5_PURPLE);
    for (int p = 0; p < 4; p++) {
        LCD_FillRect(iconX - 12, iconY - 8 + p * 5, 4, 3, MX5_PURPLE);
        LCD_FillRect(iconX + 8, iconY - 8 + p * 5, 4, 3, MX5_PURPLE);
    }
    
    // Text label
    LCD_DrawString(startX + 55, startY + 10, "FREE MEMORY", MX5_WHITE, COLOR_BG_CARD, 2);
    char memStr[16];
    snprintf(memStr, sizeof(memStr), "%d KB", ESP.getFreeHeap() / 1024);
    LCD_DrawString(startX + 55, startY + 32, memStr, MX5_PURPLE, COLOR_BG_CARD, 1);
    
    LCD_FillCircle(startX + itemW - 30, iconY, 10, MX5_PURPLE);
    
    startY += itemH + itemGap;
    
    // === UPTIME ===
    LCD_FillRoundRect(startX, startY, itemW, itemH, CARD_RADIUS, COLOR_BG_CARD);
    LCD_DrawRoundRect(startX, startY, itemW, itemH, CARD_RADIUS, MX5_CYAN);
    
    // Clock icon
    iconY = startY + itemH/2;
    LCD_DrawCircle(iconX, iconY, 10, MX5_CYAN);
    LCD_DrawCircle(iconX, iconY, 11, MX5_CYAN);
    LCD_DrawLine(iconX, iconY, iconX, iconY - 6, MX5_CYAN);
    LCD_DrawLine(iconX, iconY, iconX + 5, iconY + 2, MX5_CYAN);
    LCD_FillCircle(iconX, iconY, 2, MX5_CYAN);
    
    // Text label
    LCD_DrawString(startX + 55, startY + 10, "UPTIME", MX5_WHITE, COLOR_BG_CARD, 2);
    unsigned long uptimeSec = millis() / 1000;
    int hrs = uptimeSec / 3600;
    int mins = (uptimeSec % 3600) / 60;
    int secs = uptimeSec % 60;
    char uptimeStr[16];
    snprintf(uptimeStr, sizeof(uptimeStr), "%02d:%02d:%02d", hrs, mins, secs);
    LCD_DrawString(startX + 55, startY + 32, uptimeStr, MX5_CYAN, COLOR_BG_CARD, 1);
    
    LCD_FillCircle(startX + itemW - 30, iconY, 10, MX5_CYAN);
    
    drawPageIndicator();
}

// Old drawSettingsScreen removed - using new scrollable version below

// Helper to draw a single settings item
void drawSettingsItem(int index, int screenY, int itemW, int startX, bool isSelected) {
    int itemH = 52;
    int toggleW = 50;
    int toggleH = 24;
    int iconX = startX + 30;
    int iconY = screenY + itemH/2;
    
    // Colors for each item type (no Back button)
    uint16_t borderColors[] = {
        MX5_PURPLE,  // 0: Data Source (Demo)
        MX5_YELLOW,  // 1: Brightness
        MX5_CYAN,    // 2: Volume
        MX5_RED,     // 3: Shift RPM
        MX5_ORANGE,  // 4: Redline
        MX5_ACCENT,  // 5: Units
        MX5_GREEN,   // 6: Low Tire PSI
        MX5_BLUE,    // 7: Coolant Warn
        MX5_PURPLE,  // 8: LED Sequence
    };
    
    uint16_t borderColor = borderColors[index];
    // Use a tinted background when selected for better visibility
    uint16_t bgColor;
    if (isSelected) {
        // Create a darker version of the border color for the background
        // Extract RGB from border color and dim it significantly
        uint8_t r = ((borderColor >> 11) & 0x1F) * 2;  // Scale from 5-bit to ~6-bit
        uint8_t g = ((borderColor >> 5) & 0x3F);        // Already 6-bit
        uint8_t b = (borderColor & 0x1F) * 2;           // Scale from 5-bit to ~6-bit
        bgColor = RGB565(r + 20, g/4 + 20, b + 20);     // Dim tint of the accent color
    } else {
        bgColor = COLOR_BG_CARD;
    }
    
    // Draw card background
    LCD_FillRoundRect(startX, screenY, itemW, itemH, CARD_RADIUS, bgColor);
    LCD_DrawRoundRect(startX, screenY, itemW, itemH, CARD_RADIUS, borderColor);
    if (isSelected) {
        // Double border when selected
        LCD_DrawRoundRect(startX + 1, screenY + 1, itemW - 2, itemH - 2, CARD_RADIUS - 1, borderColor);
        LCD_DrawRoundRect(startX + 2, screenY + 2, itemW - 4, itemH - 4, CARD_RADIUS - 2, borderColor);
    }
    
    char valueStr[16];
    int valueX = startX + itemW - 70;
    int toggleX = startX + itemW - 70;
    
    switch (index) {
        case 0:  // Data Source (Demo Mode)
            LCD_FillRoundRect(iconX - 10, iconY - 10, 20, 20, 4, MX5_PURPLE);
            LCD_DrawLine(iconX - 4, iconY - 6, iconX - 4, iconY + 6, bgColor);
            LCD_DrawLine(iconX - 4, iconY - 6, iconX + 6, iconY, bgColor);
            LCD_DrawLine(iconX - 4, iconY + 6, iconX + 6, iconY, bgColor);
            LCD_DrawString(startX + 55, screenY + 10, "DATA SOURCE", MX5_WHITE, bgColor, 2);
            LCD_DrawString(startX + 55, screenY + 32, settings.demoMode ? "DEMO" : "CAN BUS", MX5_PURPLE, bgColor, 1);
            // Toggle switch
            if (settings.demoMode) {
                LCD_FillRoundRect(toggleX, iconY - toggleH/2, toggleW, toggleH, 12, MX5_GREEN);
                LCD_FillCircle(toggleX + toggleW - 12, iconY, 9, MX5_WHITE);
            } else {
                LCD_FillRoundRect(toggleX, iconY - toggleH/2, toggleW, toggleH, 12, MX5_DARKGRAY);
                LCD_FillCircle(toggleX + 12, iconY, 9, MX5_WHITE);
            }
            break;
            
        case 1:  // Brightness
            LCD_FillCircle(iconX, screenY + 18, 8, MX5_YELLOW);
            for (int r = 0; r < 8; r++) {
                float angle = r * 3.14159 / 4;
                LCD_DrawLine(iconX + cos(angle) * 11, screenY + 18 + sin(angle) * 11,
                           iconX + cos(angle) * 15, screenY + 18 + sin(angle) * 15, MX5_YELLOW);
            }
            LCD_DrawString(startX + 55, screenY + 8, "BRIGHTNESS", MX5_WHITE, bgColor, 2);
            {
                int sliderX = startX + 55;
                int sliderW = 150;
                int sliderY = screenY + 40;
                float pct = settings.brightness / 100.0;
                LCD_FillRoundRect(sliderX, sliderY - 4, sliderW, 8, 4, MX5_DARKGRAY);
                LCD_FillRoundRect(sliderX, sliderY - 4, (int)(sliderW * pct), 8, 4, MX5_YELLOW);
                LCD_FillCircle(sliderX + (int)(sliderW * pct), sliderY, 6, MX5_WHITE);
            }
            snprintf(valueStr, sizeof(valueStr), "%d%%", settings.brightness);
            LCD_DrawString(startX + itemW - 45, screenY + 32, valueStr, MX5_YELLOW, bgColor, 1);
            break;
            
        case 2:  // Volume
            LCD_DrawCircle(iconX, iconY, 10, MX5_CYAN);
            LCD_DrawLine(iconX - 3, iconY - 5, iconX - 3, iconY + 5, MX5_CYAN);
            LCD_DrawLine(iconX - 3, iconY - 5, iconX + 5, iconY - 8, MX5_CYAN);
            LCD_DrawLine(iconX - 3, iconY + 5, iconX + 5, iconY + 8, MX5_CYAN);
            LCD_DrawString(startX + 55, screenY + 10, "VOLUME", MX5_WHITE, bgColor, 2);
            {
                int sliderX = startX + 55;
                int sliderW = 150;
                int sliderY = screenY + 40;
                float pct = settings.volume / 100.0;
                LCD_FillRoundRect(sliderX, sliderY - 4, sliderW, 8, 4, MX5_DARKGRAY);
                LCD_FillRoundRect(sliderX, sliderY - 4, (int)(sliderW * pct), 8, 4, MX5_CYAN);
                LCD_FillCircle(sliderX + (int)(sliderW * pct), sliderY, 6, MX5_WHITE);
            }
            snprintf(valueStr, sizeof(valueStr), "%d%%", settings.volume);
            LCD_DrawString(startX + itemW - 45, screenY + 32, valueStr, MX5_CYAN, bgColor, 1);
            break;
            
        case 3:  // Shift RPM
            LCD_FillCircle(iconX, iconY, 10, MX5_RED);
            LCD_FillCircle(iconX, iconY, 6, bgColor);
            LCD_FillCircle(iconX, iconY, 3, MX5_RED);
            LCD_DrawString(startX + 55, screenY + 10, "SHIFT RPM", MX5_WHITE, bgColor, 2);
            snprintf(valueStr, sizeof(valueStr), "%d", settings.shiftRPM);
            LCD_DrawString(valueX, screenY + 18, valueStr, MX5_WHITE, bgColor, 2);
            break;
            
        case 4:  // Redline
            LCD_FillCircle(iconX, iconY, 10, MX5_ORANGE);
            LCD_DrawLine(iconX - 6, iconY, iconX + 6, iconY, bgColor);
            LCD_DrawLine(iconX, iconY - 6, iconX, iconY + 6, bgColor);
            LCD_DrawString(startX + 55, screenY + 10, "REDLINE", MX5_WHITE, bgColor, 2);
            snprintf(valueStr, sizeof(valueStr), "%d", settings.redlineRPM);
            LCD_DrawString(valueX, screenY + 18, valueStr, MX5_WHITE, bgColor, 2);
            break;
            
        case 5:  // Units
            LCD_DrawCircle(iconX, iconY, 10, MX5_ACCENT);
            LCD_DrawLine(iconX, iconY, iconX + 6, iconY - 6, MX5_ACCENT);
            LCD_DrawString(startX + 55, screenY + 10, "UNITS", MX5_WHITE, bgColor, 2);
            LCD_DrawString(startX + 55, screenY + 32, settings.useMPH ? "MPH" : "KMH", MX5_ACCENT, bgColor, 1);
            if (settings.useMPH) {
                LCD_FillRoundRect(toggleX, iconY - toggleH/2, toggleW, toggleH, 12, MX5_GREEN);
                LCD_FillCircle(toggleX + toggleW - 12, iconY, 9, MX5_WHITE);
            } else {
                LCD_FillRoundRect(toggleX, iconY - toggleH/2, toggleW, toggleH, 12, MX5_DARKGRAY);
                LCD_FillCircle(toggleX + 12, iconY, 9, MX5_WHITE);
            }
            break;
            
        case 6:  // Low Tire PSI
            LCD_DrawCircle(iconX, iconY, 10, MX5_GREEN);
            LCD_DrawCircle(iconX, iconY, 6, MX5_GREEN);
            LCD_DrawString(startX + 55, screenY + 10, "LOW TIRE PSI", MX5_WHITE, bgColor, 2);
            snprintf(valueStr, sizeof(valueStr), "%.1f", settings.tireLowPSI);
            LCD_DrawString(valueX, screenY + 18, valueStr, MX5_WHITE, bgColor, 2);
            break;
            
        case 7:  // Coolant Warn
            LCD_FillCircle(iconX, iconY, 10, MX5_BLUE);
            LCD_DrawLine(iconX - 4, iconY + 4, iconX, iconY - 6, MX5_WHITE);
            LCD_DrawLine(iconX, iconY - 6, iconX + 4, iconY + 4, MX5_WHITE);
            LCD_DrawString(startX + 55, screenY + 10, "COOLANT WARN", MX5_WHITE, bgColor, 2);
            snprintf(valueStr, sizeof(valueStr), "%dF", settings.coolantWarnF);
            LCD_DrawString(valueX, screenY + 18, valueStr, MX5_WHITE, bgColor, 2);
            break;
            
        case 8:  // LED Sequence
            // Draw LED strip icon
            for (int led = 0; led < 5; led++) {
                int ledX = iconX - 8 + led * 4;
                LCD_FillRect(ledX, iconY - 6, 3, 12, (led < 3) ? MX5_GREEN : MX5_DARKGRAY);
            }
            LCD_DrawString(startX + 55, screenY + 10, "LED SEQUENCE", MX5_WHITE, bgColor, 2);
            // Display current sequence name
            if (settings.ledSequence >= 1 && settings.ledSequence <= SEQ_COUNT) {
                LCD_DrawString(startX + 55, screenY + 32, LED_SEQUENCE_NAMES[settings.ledSequence], MX5_PURPLE, bgColor, 1);
            }
            // Draw sequence number indicator
            snprintf(valueStr, sizeof(valueStr), "%d/%d", settings.ledSequence, SEQ_COUNT);
            LCD_DrawString(valueX + 20, screenY + 18, valueStr, MX5_WHITE, bgColor, 2);
            break;
    }
}

void drawSettingsScreen() {
    if (!needsFullRedraw) return;
    
    drawBackground();
    
    int startY = 55;   // Pushed down to avoid round display top edge
    int itemH = 52;
    int itemGap = 8;
    int itemW = 270;   // Slightly narrower to fit round display
    int startX = CENTER_X - itemW/2;
    
    // Draw scroll indicator if needed (using lines to draw arrows)
    if (settingsScrollOffset > 0) {
        // Draw up arrow indicator using lines
        LCD_DrawLine(CENTER_X - 10, 18, CENTER_X, 8, MX5_WHITE);
        LCD_DrawLine(CENTER_X + 10, 18, CENTER_X, 8, MX5_WHITE);
        LCD_DrawLine(CENTER_X - 10, 18, CENTER_X + 10, 18, MX5_WHITE);
    }
    if (settingsScrollOffset + SETTINGS_VISIBLE < SETTINGS_COUNT) {
        // Draw down arrow indicator using lines
        int baseY = SCREEN_HEIGHT - 28;
        int tipY = SCREEN_HEIGHT - 18;
        LCD_DrawLine(CENTER_X - 10, baseY, CENTER_X, tipY, MX5_WHITE);
        LCD_DrawLine(CENTER_X + 10, baseY, CENTER_X, tipY, MX5_WHITE);
        LCD_DrawLine(CENTER_X - 10, baseY, CENTER_X + 10, baseY, MX5_WHITE);
    }
    
    // Draw visible settings items
    for (int i = 0; i < SETTINGS_VISIBLE && (settingsScrollOffset + i) < SETTINGS_COUNT; i++) {
        int itemIndex = settingsScrollOffset + i;
        int screenY = startY + i * (itemH + itemGap);
        bool isSelected = (itemIndex == settingsSelection);
        drawSettingsItem(itemIndex, screenY, itemW, startX, isSelected);
    }
    
    // Draw scroll position indicator (dots on the right side)
    int dotStartY = CENTER_Y - (SETTINGS_COUNT * 6);
    for (int i = 0; i < SETTINGS_COUNT; i++) {
        int dotY = dotStartY + i * 12;
        if (i == settingsSelection) {
            LCD_FillCircle(SCREEN_WIDTH - 15, dotY, 4, MX5_WHITE);
        } else {
            LCD_FillCircle(SCREEN_WIDTH - 15, dotY, 2, MX5_GRAY);
        }
    }
}

// Handle touch on settings screen with scrolling
void handleSettingsTouch(int x, int y) {
    int startY = 55;   // Match drawing layout
    int itemH = 52;
    int itemGap = 8;
    int itemW = 270;
    int startX = CENTER_X - itemW/2;
    
    // Check for up/down scroll areas
    if (y < 50 && settingsScrollOffset > 0) {
        settingsScrollOffset--;
        if (settingsSelection > settingsScrollOffset + SETTINGS_VISIBLE - 1) {
            settingsSelection = settingsScrollOffset + SETTINGS_VISIBLE - 1;
            Serial.printf("SELECTION:%d\n", settingsSelection);  // Sync to Pi
        }
        needsRedraw = true;
        needsFullRedraw = true;
        return;
    }
    if (y > SCREEN_HEIGHT - 35 && settingsScrollOffset + SETTINGS_VISIBLE < SETTINGS_COUNT) {
        settingsScrollOffset++;
        if (settingsSelection < settingsScrollOffset) {
            settingsSelection = settingsScrollOffset;
            Serial.printf("SELECTION:%d\n", settingsSelection);  // Sync to Pi
        }
        needsRedraw = true;
        needsFullRedraw = true;
        return;
    }
    
    // Check which visible setting item was touched
    for (int i = 0; i < SETTINGS_VISIBLE && (settingsScrollOffset + i) < SETTINGS_COUNT; i++) {
        int itemIndex = settingsScrollOffset + i;
        int itemY = startY + i * (itemH + itemGap);
        
        if (x >= startX && x <= startX + itemW && y >= itemY && y <= itemY + itemH) {
            int prevSelection = settingsSelection;
            settingsSelection = itemIndex;
            
            // Send selection sync to Pi
            if (settingsSelection != prevSelection) {
                Serial.printf("SELECTION:%d\n", settingsSelection);
            }
            
            bool changed = false;
            
            switch (itemIndex) {
                case 0:  // Data Source (Demo Mode)
                    settings.demoMode = !settings.demoMode;
                    telemetry.connected = !settings.demoMode;
                    sendSettingToPI("demo_mode", settings.demoMode);
                    changed = true;
                    break;
                    
                case 1:  // Brightness
                    {
                        int sliderX = startX + 55;
                        int sliderW = 150;
                        if (x >= sliderX && x <= sliderX + sliderW) {
                            int newBrightness = ((x - sliderX) * 100) / sliderW;
                            settings.brightness = constrain(newBrightness, 10, 100);
                        } else {
                            if (settings.brightness < 37) settings.brightness = 50;
                            else if (settings.brightness < 62) settings.brightness = 75;
                            else if (settings.brightness < 87) settings.brightness = 100;
                            else settings.brightness = 25;
                        }
                        sendSettingToPI("brightness", settings.brightness);
                        changed = true;
                    }
                    break;
                    
                case 2:  // Volume
                    {
                        int sliderX = startX + 55;
                        int sliderW = 150;
                        if (x >= sliderX && x <= sliderX + sliderW) {
                            int newVolume = ((x - sliderX) * 100) / sliderW;
                            settings.volume = constrain(newVolume, 0, 100);
                        } else {
                            if (settings.volume < 37) settings.volume = 50;
                            else if (settings.volume < 62) settings.volume = 75;
                            else if (settings.volume < 87) settings.volume = 100;
                            else settings.volume = 25;
                        }
                        sendSettingToPI("volume", settings.volume);
                        changed = true;
                    }
                    break;
                    
                case 3:  // Shift RPM
                    if (settings.shiftRPM < 5500) settings.shiftRPM = 5500;
                    else if (settings.shiftRPM < 6000) settings.shiftRPM = 6000;
                    else if (settings.shiftRPM < 6500) settings.shiftRPM = 6500;
                    else if (settings.shiftRPM < 7000) settings.shiftRPM = 7000;
                    else settings.shiftRPM = 5000;
                    sendSettingToPI("shift_rpm", settings.shiftRPM);
                    changed = true;
                    break;
                    
                case 4:  // Redline
                    if (settings.redlineRPM < 6500) settings.redlineRPM = 6500;
                    else if (settings.redlineRPM < 7000) settings.redlineRPM = 7000;
                    else if (settings.redlineRPM < 7500) settings.redlineRPM = 7500;
                    else if (settings.redlineRPM < 8000) settings.redlineRPM = 8000;
                    else settings.redlineRPM = 6000;
                    sendSettingToPI("redline_rpm", settings.redlineRPM);
                    changed = true;
                    break;
                    
                case 5:  // Units
                    settings.useMPH = !settings.useMPH;
                    sendSettingToPI("use_mph", settings.useMPH);
                    changed = true;
                    break;
                    
                case 6:  // Low Tire PSI
                    settings.tireLowPSI += 0.5;
                    if (settings.tireLowPSI > 35.0) settings.tireLowPSI = 25.0;
                    sendSettingToPI("tire_low_psi", settings.tireLowPSI);
                    changed = true;
                    break;
                    
                case 7:  // Coolant Warn
                    settings.coolantWarnF += 5;
                    if (settings.coolantWarnF > 250) settings.coolantWarnF = 200;
                    sendSettingToPI("coolant_warn", settings.coolantWarnF);
                    changed = true;
                    break;
                    
                case 8:  // LED Sequence
                    settings.ledSequence++;
                    if (settings.ledSequence > SEQ_COUNT) settings.ledSequence = 1;
                    sendSettingToPI("led_sequence", settings.ledSequence);
                    changed = true;
                    break;
            }
            
            needsRedraw = true;
            needsFullRedraw = true;
            break;
        }
    }
}

// Serial command buffer
static String serialBuffer = "";

void handleSerialCommands() {
    while (Serial.available()) {
        char c = Serial.read();
        if (c == '\n' || c == '\r') {
            if (serialBuffer.length() > 0) {
                parseCommand(serialBuffer);
                serialBuffer = "";
            }
        } else {
            serialBuffer += c;
        }
    }
}

void parseCommand(String cmd) {
    cmd.trim();
    
    // Only log screen-related commands for debugging
    if (cmd.startsWith("SCREEN") || cmd == "LEFT" || cmd == "RIGHT" || cmd == "UP" || cmd == "DOWN") {
        Serial.printf("CMD: '%s'\n", cmd.c_str());
    }
    
    // Navigation commands - cruise control scheme:
    // UP = Previous screen (matches RES_PLUS)
    // DOWN = Next screen (matches SET_MINUS)
    // LEFT/RIGHT also supported as alternatives
    if (cmd == "UP" || cmd == "up") {
        // UP - Previous screen (matches RES_PLUS button)
        if (navLocked) {
            Serial.println("NAV_LOCKED:Ignored UP");
            return;
        }
        if (isTransitioning()) {
            currentScreen = transitionToScreen;
            currentTransition = TRANSITION_NONE;
        }
        ScreenMode prevScreen = (ScreenMode)((currentScreen - 1 + SCREEN_COUNT) % SCREEN_COUNT);
        currentScreen = prevScreen;
        needsRedraw = true;
        needsFullRedraw = true;
        telemetry.connected = true;
        Serial.println("OK:SCREEN_PREV");
    }
    else if (cmd == "DOWN" || cmd == "down") {
        // DOWN - Next screen (matches SET_MINUS button)
        if (navLocked) {
            Serial.println("NAV_LOCKED:Ignored DOWN");
            return;
        }
        if (isTransitioning()) {
            currentScreen = transitionToScreen;
            currentTransition = TRANSITION_NONE;
        }
        ScreenMode nextScreen = (ScreenMode)((currentScreen + 1) % SCREEN_COUNT);
        currentScreen = nextScreen;
        needsRedraw = true;
        needsFullRedraw = true;
        telemetry.connected = true;
        Serial.println("OK:SCREEN_NEXT");
    }
    else if (cmd == "LEFT" || cmd == "left" || cmd == "l") {
        // LEFT - DISABLED (not a cruise control button)
        Serial.println("IGNORED:LEFT command disabled (not cruise control)");
        return;
    }
    else if (cmd == "RIGHT" || cmd == "right" || cmd == "r") {
        // RIGHT - DISABLED (not a cruise control button)
        Serial.println("IGNORED:RIGHT command disabled (not cruise control)");
        return;
    }
    else if (cmd == "SELECT" || cmd == "select" || cmd == "CLICK" || cmd == "click" || cmd == "c") {
        // SELECT/CLICK - Confirm action (matches ON_OFF button)
        if (navLocked) {
            Serial.println("NAV_LOCKED:Ignored SELECT");
            return;
        }
        telemetry.connected = true;
        Serial.println("OK:SELECT");
    }
    else if (cmd == "BACK" || cmd == "back") {
        // BACK - DISABLED (not a cruise control button)
        Serial.println("IGNORED:BACK command disabled (not cruise control)");
        return;
    }
    // Direct screen selection - immediate change (no transition for serial commands)
    else if (cmd.startsWith("SCREEN:") || cmd.startsWith("screen:")) {
        int screenNum = cmd.substring(7).toInt();
        Serial.printf("SCREEN CMD received: %d (current=%d)\n", screenNum, currentScreen);
        
        if (screenNum >= 0 && screenNum < SCREEN_COUNT) {
            ScreenMode targetScreen = (ScreenMode)screenNum;
            
            // ALWAYS cancel any transition - even if same screen
            currentTransition = TRANSITION_NONE;
            
            // Change to target screen immediately
            if (targetScreen != currentScreen) {
                currentScreen = targetScreen;
                needsRedraw = true;
                needsFullRedraw = true;
                Serial.printf("Screen CHANGED to: %s (%d)\n", SCREEN_NAMES[currentScreen], currentScreen);
            } else {
                Serial.printf("Screen already at: %s (%d)\n", SCREEN_NAMES[currentScreen], currentScreen);
            }
            telemetry.connected = true;
        } else {
            Serial.printf("Invalid screen number: %d\n", screenNum);
        }
    }
    // Telemetry data updates from Pi (format: KEY:VALUE)
    else if (cmd.startsWith("RPM:")) {
        telemetry.rpm = cmd.substring(4).toFloat();
        telemetry.connected = true;
        piDataReceived = true;  // Pi is sending data, end boot countdown
        needsFullRedraw = true;  // Redraw to show indicators
    }
    else if (cmd.startsWith("SPEED:")) {
        telemetry.speed = cmd.substring(6).toFloat();
        telemetry.connected = true;
        piDataReceived = true;
    }
    else if (cmd.startsWith("GEAR:")) {
        telemetry.gear = cmd.substring(5).toInt();
        telemetry.connected = true;
        piDataReceived = true;
    }
    else if (cmd.startsWith("COOLANT:")) {
        telemetry.coolantTemp = cmd.substring(8).toFloat();
        telemetry.connected = true;
    }
    else if (cmd.startsWith("OIL:")) {
        telemetry.oilTemp = cmd.substring(4).toFloat();
        telemetry.connected = true;
    }
    else if (cmd.startsWith("FUEL:")) {
        telemetry.fuelLevel = cmd.substring(5).toFloat();
        telemetry.connected = true;
    }
    else if (cmd.startsWith("AMBT:")) {
        telemetry.ambientTemp = cmd.substring(5).toFloat();
        telemetry.connected = true;
    }
    else if (cmd.startsWith("TIRE:")) {
        // Format: TIRE:FL,FR,RL,RR
        String tireData = cmd.substring(5);
        int idx = 0;
        int start = 0;
        for (int i = 0; i <= tireData.length() && idx < 4; i++) {
            if (i == tireData.length() || tireData[i] == ',') {
                telemetry.tirePressure[idx++] = tireData.substring(start, i).toFloat();
                start = i + 1;
            }
        }
        telemetry.connected = true;
    }
    // Per-tire temperatures from Pi (format: TIRE_TEMP:FL,FR,RL,RR in Fahrenheit)
    else if (cmd.startsWith("TIRE_TEMP:")) {
        String tempData = cmd.substring(10);
        int idx = 0;
        int start = 0;
        for (int i = 0; i <= tempData.length() && idx < 4; i++) {
            if (i == tempData.length() || tempData[i] == ',') {
                telemetry.tireTemp[idx++] = tempData.substring(start, i).toFloat();
                start = i + 1;
            }
        }
        telemetry.connected = true;
    }
    // Per-tire timestamps from Pi (format: TIRE_TIME:HH:MM:SS,HH:MM:SS,HH:MM:SS,HH:MM:SS)
    else if (cmd.startsWith("TIRE_TIME:")) {
        String timeData = cmd.substring(10);
        int idx = 0;
        int start = 0;
        for (int i = 0; i <= timeData.length() && idx < 4; i++) {
            if (i == timeData.length() || timeData[i] == ',') {
                String timestamp = timeData.substring(start, i);
                strncpy(tpmsLastUpdateStr[idx], timestamp.c_str(), sizeof(tpmsLastUpdateStr[idx]) - 1);
                tpmsLastUpdateStr[idx][sizeof(tpmsLastUpdateStr[idx]) - 1] = '\0';
                idx++;
                start = i + 1;
            }
        }
        tpmsDataFromCache = false;  // Data is fresh from Pi
        // Save to NVS
        saveTPMSToNVS();
    }
    else if (cmd.startsWith("GFORCE:")) {
        // Format: GFORCE:X,Y
        String gData = cmd.substring(7);
        int commaPos = gData.indexOf(',');
        if (commaPos > 0) {
            telemetry.gForceX = gData.substring(0, commaPos).toFloat();
            telemetry.gForceY = gData.substring(commaPos + 1).toFloat();
        }
        telemetry.connected = true;
    }
    else if (cmd.startsWith("ENGINE:")) {
        telemetry.engineRunning = (cmd.substring(7).toInt() == 1);
        telemetry.connected = true;
    }
    // Diagnostics update from Pi (format: DIAG:checkEngine,abs,oilWarn,battery,headlights,highBeams)
    else if (cmd.startsWith("DIAG:")) {
        String data = cmd.substring(5);
        int idx = 0;
        int values[6] = {0};  // Extended to 6 values for headlight indicators
        int start = 0;
        for (int i = 0; i <= data.length() && idx < 6; i++) {
            if (i == data.length() || data[i] == ',') {
                values[idx++] = data.substring(start, i).toInt();
                start = i + 1;
            }
        }
        if (idx >= 4) {  // At least 4 fields required (original protocol)
            telemetry.checkEngine = values[0] != 0;
            telemetry.absWarning = values[1] != 0;
            telemetry.oilWarning = values[2] != 0;
            telemetry.batteryWarning = values[3] != 0;
            // New headlight indicators (backwards compatible)
            if (idx >= 6) {
                telemetry.headlightsOn = values[4] != 0;
                telemetry.highBeamsOn = values[5] != 0;
            }
            telemetry.connected = true;
            telemetry.hasDiagnosticData = true;  // Mark that we have real diagnostic data
            needsRedraw = true;
        }
    }
    // Oil pressure update from Pi
    else if (cmd.startsWith("OILPSI:")) {
        telemetry.oilPressure = cmd.substring(7).toFloat();
        telemetry.connected = true;
    }
    // Bulk telemetry update from Pi (format: TEL:rpm,speed,gear,throttle,coolant,oil,fuel,engine,gear_est,clutch,avg_mpg,range_miles)
    else if (cmd.startsWith("TEL:")) {
        String data = cmd.substring(4);
        int idx = 0;
        float values[12] = {0};  // 12 fields including MPG data
        int start = 0;
        for (int i = 0; i <= data.length() && idx < 12; i++) {
            if (i == data.length() || data[i] == ',') {
                String field = data.substring(start, i);
                values[idx] = field.toFloat();
                idx++;
                start = i + 1;
            }
        }
        
        if (idx >= 6) {  // At least 6 fields required for basic telemetry
            telemetry.rpm = values[0];
            telemetry.speed = values[1];
            telemetry.gear = (int)values[2];
            telemetry.throttle = values[3];
            telemetry.coolantTemp = values[4];
            telemetry.oilTemp = values[5];  // This is oil status (0 or 1)
            // ambient_temp now from ESP32 sensor only
            // Extended fields (if present)
            if (idx >= 7) telemetry.fuelLevel = values[6];
            if (idx >= 8) telemetry.engineRunning = (values[7] > 0);
            if (idx >= 9) telemetry.gearEstimated = (values[8] > 0);
            if (idx >= 10) telemetry.clutchEngaged = (values[9] > 0);
            // MPG data fields (new)
            if (idx >= 11) telemetry.averageMPG = values[10];
            if (idx >= 12) telemetry.rangeMiles = (int)values[11];
            telemetry.connected = true;
            telemetry.hasReceivedTelemetry = true;  // Mark that we've received data
            needsRedraw = true;  // Update display with new data
        } else {
            Serial.printf("TEL: ERROR - Not enough fields (got %d, need 6)\n", idx);
        }
    }
    else if (cmd == "PING") {
        telemetry.connected = true;
        Serial.println("PONG");
    }
    else if (cmd == "CAL_IMU") {
        // Calibrate IMU to current position as zero point
        calibrateIMU();
    }
    else if (cmd == "STATUS") {
        Serial.printf("SCREEN:%d,RPM:%.0f,SPEED:%.0f,GEAR:%d,CONNECTED:%d\n",
                      currentScreen, telemetry.rpm, telemetry.speed, 
                      telemetry.gear, telemetry.connected ? 1 : 0);
    }
    else if (cmd == "DEMO:ON") {
        telemetry.connected = false;  // Enable demo mode
        settings.demoMode = true;
        needsRedraw = true;
        needsFullRedraw = true;
        Serial.println("OK:DEMO_ON");
    }
    else if (cmd == "DEMO:OFF") {
        telemetry.connected = true;   // Disable demo mode
        settings.demoMode = false;
        needsRedraw = true;
        needsFullRedraw = true;
        Serial.println("OK:DEMO_OFF");
    }
    // Settings synchronization from Pi
    else if (cmd.startsWith("SET:")) {
        parseSettingsCommand(cmd.substring(4));
    }
    else if (cmd == "GET_SETTINGS") {
        sendAllSettingsToPI();
    }
    // Clear TPMS cache command (useful when formula changes)
    else if (cmd == "CLEAR_TPMS") {
        tpmsPrefs.begin("tpms", false);
        tpmsPrefs.clear();
        tpmsPrefs.end();
        // Reset all TPMS data
        for (int i = 0; i < 4; i++) {
            tpmsSensors[i].valid = false;
            tpmsSensors[i].pressurePSI = 0;
            tpmsSensors[i].temperatureF = 0;
            telemetry.tirePressure[i] = 0;
            telemetry.tireTemp[i] = 0;
            strncpy(tpmsLastUpdateStr[i], "--:--:--", sizeof(tpmsLastUpdateStr[i]));
        }
        tpmsDataFromCache = false;
        needsRedraw = true;
        needsFullRedraw = true;
        Serial.println("OK:TPMS_CACHE_CLEARED");
    }
    // Settings selection sync from Pi
    else if (cmd.startsWith("SELECTION:")) {
        int newSelection = cmd.substring(10).toInt();
        if (newSelection >= 0 && newSelection < SETTINGS_COUNT) {
            settingsSelection = newSelection;
            // Auto-scroll to keep selection visible
            if (settingsSelection < settingsScrollOffset) {
                settingsScrollOffset = settingsSelection;
            } else if (settingsSelection >= settingsScrollOffset + SETTINGS_VISIBLE) {
                settingsScrollOffset = settingsSelection - SETTINGS_VISIBLE + 1;
            }
            if (currentScreen == SCREEN_SETTINGS) {
                needsRedraw = true;
                needsFullRedraw = true;
            }
            Serial.printf("OK:SELECTION:%d\n", newSelection);
        }
    }
    // Navigation lock state from Pi (prevents accidental button presses while driving)
    else if (cmd.startsWith("NAVLOCK:")) {
        bool newLockState = (cmd.substring(8).toInt() == 1);
        if (newLockState != navLocked) {
            navLocked = newLockState;
            needsRedraw = true;
            needsFullRedraw = true;
            Serial.printf("OK:NAVLOCK:%d\n", navLocked ? 1 : 0);
        }
    }
}

// Parse incoming settings command (format: name=value)
void parseSettingsCommand(String data) {
    int eqPos = data.indexOf('=');
    if (eqPos <= 0) return;
    
    String name = data.substring(0, eqPos);
    String value = data.substring(eqPos + 1);
    
    bool changed = false;
    
    if (name == "brightness") {
        settings.brightness = value.toInt();
        changed = true;
    }
    else if (name == "volume") {
        settings.volume = value.toInt();
        changed = true;
    }
    else if (name == "shift_rpm") {
        settings.shiftRPM = value.toInt();
        changed = true;
    }
    else if (name == "redline_rpm") {
        settings.redlineRPM = value.toInt();
        changed = true;
    }
    else if (name == "use_mph") {
        settings.useMPH = (value == "1" || value == "true");
        changed = true;
    }
    else if (name == "tire_low_psi") {
        settings.tireLowPSI = value.toFloat();
        changed = true;
    }
    else if (name == "coolant_warn") {
        settings.coolantWarnF = value.toInt();
        changed = true;
    }
    else if (name == "demo_mode") {
        settings.demoMode = (value == "1" || value == "true");
        telemetry.connected = !settings.demoMode;
        changed = true;
    }
    else if (name == "timeout") {
        settings.screenTimeout = value.toInt();
        changed = true;
    }
    else if (name == "led_sequence") {
        int seq = value.toInt();
        if (seq >= 1 && seq <= SEQ_COUNT) {
            settings.ledSequence = seq;
            changed = true;
        }
    }
    else if (name == "clutch_display_mode") {
        int mode = value.toInt();
        if (mode >= 0 && mode <= 3) {
            clutchDisplayMode = mode;
            changed = true;
        }
    }
    
    if (changed) {
        Serial.printf("OK:SET:%s=%s\n", name.c_str(), value.c_str());
        // Redraw settings screen if we're on it
        if (currentScreen == SCREEN_SETTINGS) {
            needsRedraw = true;
            needsFullRedraw = true;
        }
    }
}

// Send a single setting to Pi
void sendSettingToPI(const char* name, int value) {
    Serial.printf("SETTING:%s=%d\n", name, value);
}

void sendSettingToPI(const char* name, float value) {
    Serial.printf("SETTING:%s=%.1f\n", name, value);
}

void sendSettingToPI(const char* name, bool value) {
    Serial.printf("SETTING:%s=%d\n", name, value ? 1 : 0);
}

// Send all current settings to Pi (for initial sync)
void sendAllSettingsToPI() {
    Serial.printf("SETTINGS:brightness=%d,volume=%d,shift_rpm=%d,redline_rpm=%d,use_mph=%d,tire_low_psi=%.1f,coolant_warn=%d,demo_mode=%d,timeout=%d,led_sequence=%d\n",
                  settings.brightness, settings.volume, settings.shiftRPM, settings.redlineRPM,
                  settings.useMPH ? 1 : 0, settings.tireLowPSI, settings.coolantWarnF,
                  settings.demoMode ? 1 : 0, settings.screenTimeout, settings.ledSequence);
}

// ============================================================================
// BLE TPMS Sensor Functions
// ============================================================================

// Callback class for BLE scan results
class TPMSScanCallbacks : public NimBLEAdvertisedDeviceCallbacks {
    void onResult(NimBLEAdvertisedDevice* advertisedDevice) {
        // Get the MAC address
        std::string macStr = advertisedDevice->getAddress().toString();
        
        // Check if this is one of our TPMS sensors
        for (int i = 0; i < TPMS_SENSOR_COUNT; i++) {
            if (strcasecmp(macStr.c_str(), TPMS_MAC_ADDRESSES[i]) == 0) {
                // Found a TPMS sensor - decode its data
                decodeTPMSData(advertisedDevice, i);
                break;
            }
        }
    }
};

// Initialize BLE for TPMS scanning
void initBLETPMS() {
    Serial.println("Initializing BLE for TPMS scanning...");
    
    // Initialize NimBLE
    NimBLEDevice::init("MX5-Display");
    
    // Get the scanner
    pBLEScan = NimBLEDevice::getScan();
    
    // Set scan callbacks
    pBLEScan->setAdvertisedDeviceCallbacks(new TPMSScanCallbacks(), false);
    
    // Active scan uses more power but gets scan response data
    pBLEScan->setActiveScan(false);  // Passive scan is fine for TPMS
    
    // Scan parameters
    pBLEScan->setInterval(100);  // How often to scan (in 0.625ms units) = 62.5ms
    pBLEScan->setWindow(99);     // How long to scan during interval = 61.875ms
    
    bleInitialized = true;
    Serial.println("BLE TPMS scanner initialized!");
    Serial.println("TPMS MAC addresses:");
    for (int i = 0; i < TPMS_SENSOR_COUNT; i++) {
        Serial.printf("  Sensor %d: %s\n", i, TPMS_MAC_ADDRESSES[i]);
    }
}

// Decode TPMS data from advertising packet
void decodeTPMSData(NimBLEAdvertisedDevice* device, int sensorIndex) {
    // Get manufacturer data (Type 0xFF)
    if (!device->haveManufacturerData()) {
        return;
    }
    
    std::string mfgData = device->getManufacturerData();
    
    // Expected manufacturer data format (17+ bytes):
    // AC 00 85 3D 3C 00 0A 25 00 D0 28 11 11 11 1F 13 14
    // Byte 2: Pressure (raw value in kPa offset format)
    // Byte 3: Temperature (raw - 45 = Celsius, convert to F)
    
    if (mfgData.length() >= 4) {
        uint8_t pressureRaw = (uint8_t)mfgData[2];
        uint8_t tempRaw = (uint8_t)mfgData[3];
        
        // Decode pressure: raw + 56 = kPa, then convert to PSI
        // Calibration offset: +0.6 PSI to better match manufacturer app readings
        // Calibrated against manufacturer app on 2026-01-24:
        // FR: ESP 28.3 vs Mfg 28.7, FL: ESP 27.6 vs Mfg 29.2, RL: ESP 29.2 vs Mfg 29.2, RR: ESP 29.2 vs Mfg 28.7
        // Universal offset of +0.6 minimizes average error across all four tires
        float pressure_kPa = pressureRaw + 56.0f;
        float pressure_psi = (pressure_kPa / 6.895f) + 0.6f;  // Universal calibration offset
        
        // Decode temperature: raw - 45 = Celsius, then convert to Fahrenheit
        float temp_c = tempRaw - 45.0f;
        float temp_f = temp_c * 9.0f / 5.0f + 32.0f;
        
        // Update sensor data
        tpmsSensors[sensorIndex].valid = true;
        tpmsSensors[sensorIndex].pressurePSI = pressure_psi;
        tpmsSensors[sensorIndex].temperatureF = temp_f;
        tpmsSensors[sensorIndex].lastUpdate = millis();
        tpmsSensors[sensorIndex].rssi = device->getRSSI();
        
        // Save to NVS for persistence across power cycles
        saveTPMSToNVS();
        
        // Debug output - show MAC, raw bytes, and decoded values for tire mapping
        Serial.printf("TPMS_DEBUG: MAC=%s RAW_P=%d RAW_T=%d -> %.1f PSI, %.1f°F [%s]\n",
                      TPMS_MAC_ADDRESSES[sensorIndex], pressureRaw, tempRaw,
                      pressure_psi, temp_f, TPMS_POSITION_NAMES[sensorIndex]);
    }
}

// Start BLE scan with cooldown to prevent blocking
void startContinuousBLEScan() {
    if (!bleInitialized || pBLEScan == nullptr) {
        return;
    }
    
    // Don't start if already scanning
    if (pBLEScan->isScanning()) {
        return;
    }
    
    // Cooldown between scans to reduce blocking frequency
    if (millis() - lastBLEScanStart < BLE_SCAN_COOLDOWN) {
        return;
    }
    
    // Start a 1 second scan (minimum supported duration)
    // Non-blocking (false) so main loop continues
    lastBLEScanStart = millis();
    pBLEScan->setMaxResults(0);  // Don't store results, just use callback
    pBLEScan->start(1, false);   // 1 second scan, non-blocking
    bleScanRunning = true;
}

// Stop BLE scanning (when leaving TPMS/Overview screens)
void stopBLEScan() {
    if (pBLEScan != nullptr && bleScanRunning) {
        pBLEScan->stop();
        bleScanRunning = false;
        Serial.println("BLE: Stopped TPMS scanning");
    }
}

// Update telemetry with TPMS data and send to Pi
void sendTPMSDataToPi() {
    // Sensor indices directly map to tire positions:
    // Index 0 = FL, Index 1 = FR, Index 2 = RL, Index 3 = RR
    
    bool anyValid = false;
    float pressures[4] = {0, 0, 0, 0};
    float temps[4] = {0, 0, 0, 0};
    
    for (int tirePos = 0; tirePos < 4; tirePos++) {
        // Direct mapping: tirePos == sensorIndex
        // Check if data is valid and not too old
        if (tpmsSensors[tirePos].valid && 
            (millis() - tpmsSensors[tirePos].lastUpdate) < TPMS_DATA_TIMEOUT) {
            
            pressures[tirePos] = tpmsSensors[tirePos].pressurePSI;
            temps[tirePos] = tpmsSensors[tirePos].temperatureF;
            
            // Also update local telemetry for display
            telemetry.tirePressure[tirePos] = pressures[tirePos];
            telemetry.tireTemp[tirePos] = temps[tirePos];
            
            anyValid = true;
        }
    }
    
    // Send to Pi if we have valid data
    if (anyValid) {
        // Send tire pressures: TPMS_PSI:FL,FR,RL,RR
        Serial.printf("TPMS_PSI:%.1f,%.1f,%.1f,%.1f\n",
                      pressures[0], pressures[1], pressures[2], pressures[3]);
        
        // Send tire temperatures: TPMS_TEMP:FL,FR,RL,RR
        Serial.printf("TPMS_TEMP:%.1f,%.1f,%.1f,%.1f\n",
                      temps[0], temps[1], temps[2], temps[3]);
        
        // Trigger TPMS screen redraw if we're viewing it
        if (currentScreen == SCREEN_TPMS) {
            needsRedraw = true;
            needsFullRedraw = true;  // TPMS screen requires full redraw for value updates
        }
    }
}

// ============================================================================
// TPMS NVS Persistence Functions
// ============================================================================

void saveTPMSToNVS() {
    // Only save if we have valid timestamp data from Pi
    bool anyValid = false;
    for (int i = 0; i < 4; i++) {
        if (tpmsLastUpdateStr[i][0] != '-') {
            anyValid = true;
            break;
        }
    }
    if (!anyValid) return;
    
    tpmsPrefs.begin("tpms", false);  // Read-write mode
    
    // Save pressure and temperature for each tire
    tpmsPrefs.putFloat("psi0", telemetry.tirePressure[0]);
    tpmsPrefs.putFloat("psi1", telemetry.tirePressure[1]);
    tpmsPrefs.putFloat("psi2", telemetry.tirePressure[2]);
    tpmsPrefs.putFloat("psi3", telemetry.tirePressure[3]);
    tpmsPrefs.putFloat("temp0", telemetry.tireTemp[0]);
    tpmsPrefs.putFloat("temp1", telemetry.tireTemp[1]);
    tpmsPrefs.putFloat("temp2", telemetry.tireTemp[2]);
    tpmsPrefs.putFloat("temp3", telemetry.tireTemp[3]);
    
    // Save per-tire timestamps from Pi
    tpmsPrefs.putString("time0", tpmsLastUpdateStr[0]);
    tpmsPrefs.putString("time1", tpmsLastUpdateStr[1]);
    tpmsPrefs.putString("time2", tpmsLastUpdateStr[2]);
    tpmsPrefs.putString("time3", tpmsLastUpdateStr[3]);
    
    tpmsPrefs.end();
    
    tpmsDataFromCache = false;  // Data is fresh, not from cache
    // Removed verbose logging to prevent serial collisions
}

void loadTPMSFromNVS() {
    tpmsPrefs.begin("tpms", true);  // Read-only mode
    
    // Check if we have saved data
    if (!tpmsPrefs.isKey("psi0")) {
        Serial.println("TPMS: No cached data in NVS");
        tpmsPrefs.end();
        return;
    }
    
    // Load pressure and temperature for each tire
    for (int i = 0; i < 4; i++) {
        char keyPsi[8], keyTemp[8], keyTime[8];
        snprintf(keyPsi, sizeof(keyPsi), "psi%d", i);
        snprintf(keyTemp, sizeof(keyTemp), "temp%d", i);
        snprintf(keyTime, sizeof(keyTime), "time%d", i);
        
        float psi = tpmsPrefs.getFloat(keyPsi, 0.0f);
        float temp = tpmsPrefs.getFloat(keyTemp, 0.0f);
        String timestamp = tpmsPrefs.getString(keyTime, "--:--:--");
        
        if (psi > 0) {
            tpmsSensors[i].valid = true;
            tpmsSensors[i].pressurePSI = psi;
            tpmsSensors[i].temperatureF = temp;
            tpmsSensors[i].lastUpdate = millis();
            
            // Update telemetry for display
            telemetry.tirePressure[i] = psi;
            telemetry.tireTemp[i] = temp;
        }
        
        // Load per-tire timestamp
        strncpy(tpmsLastUpdateStr[i], timestamp.c_str(), sizeof(tpmsLastUpdateStr[i]) - 1);
        tpmsLastUpdateStr[i][sizeof(tpmsLastUpdateStr[i]) - 1] = '\0';
    }
    
    tpmsPrefs.end();
    
    tpmsDataFromCache = true;  // Mark that this data came from cache
    
    // Check if any valid data was loaded
    bool anyValid = false;
    for (int i = 0; i < 4; i++) {
        if (tpmsSensors[i].valid) {
            anyValid = true;
            break;
        }
    }
    
    if (anyValid) {
        Serial.printf("TPMS: Loaded cached data from NVS\n");
        Serial.printf("  Pressures: FL=%.1f, FR=%.1f, RL=%.1f, RR=%.1f PSI\n",
                      tpmsSensors[0].pressurePSI, tpmsSensors[1].pressurePSI,
                      tpmsSensors[2].pressurePSI, tpmsSensors[3].pressurePSI);
        Serial.printf("  Times: FL=%s, FR=%s, RL=%s, RR=%s\n",
                      tpmsLastUpdateStr[0], tpmsLastUpdateStr[1],
                      tpmsLastUpdateStr[2], tpmsLastUpdateStr[3]);
    }
}

// ============================================================================
// IMU Calibration NVS Persistence Functions
// ============================================================================

void saveIMUCalibrationToNVS() {
    imuPrefs.begin("imu_cal", false);  // Read-write mode
    
    imuPrefs.putFloat("pitch", imuCalibrationPitch);
    imuPrefs.putFloat("roll", imuCalibrationRoll);
    imuPrefs.putFloat("accelX", imuCalibrationAccelX);
    imuPrefs.putFloat("accelY", imuCalibrationAccelY);
    imuPrefs.putFloat("accelZ", imuCalibrationAccelZ);
    
    imuPrefs.end();
    
    Serial.println("IMU: Calibration saved to NVS");
}

void loadIMUCalibrationFromNVS() {
    imuPrefs.begin("imu_cal", true);  // Read-only mode
    
    // Check if we have saved calibration data
    if (!imuPrefs.isKey("pitch")) {
        Serial.println("IMU: No saved calibration in NVS, using defaults (0,0,0,0,0)");
        imuPrefs.end();
        return;
    }
    
    // Load calibration offsets
    imuCalibrationPitch = imuPrefs.getFloat("pitch", 0.0f);
    imuCalibrationRoll = imuPrefs.getFloat("roll", 0.0f);
    imuCalibrationAccelX = imuPrefs.getFloat("accelX", 0.0f);
    imuCalibrationAccelY = imuPrefs.getFloat("accelY", 0.0f);
    imuCalibrationAccelZ = imuPrefs.getFloat("accelZ", 0.0f);
    
    imuPrefs.end();
    
    Serial.println("IMU: Loaded calibration from NVS");
    Serial.printf("IMU: Offsets - Pitch:%.2f Roll:%.2f AccelX:%.3f AccelY:%.3f AccelZ:%.3f\n",
                  imuCalibrationPitch, imuCalibrationRoll,
                  imuCalibrationAccelX, imuCalibrationAccelY, imuCalibrationAccelZ);
}
