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
#include "ui_core/ui_core.h"

// I2C pins for IMU (QMI8658)
#define IMU_SDA 11
#define IMU_SCL 10

// ESP32 internal temperature sensor for ambient temp fallback
temperature_sensor_handle_t temp_sensor = NULL;

// MX5 NC gear ratios for rev-match calculation
// MPH per 1000 RPM for each gear (calculated from gear ratios, final drive, tire size)
const float MPH_PER_1000_RPM[] = {
    0.0f,    // Gear 0 (neutral) - not used
    4.92f,   // Gear 1: 3.760 ratio
    8.16f,   // Gear 2: 2.269 ratio
    11.25f,  // Gear 3: 1.645 ratio
    15.59f,  // Gear 4: 1.187 ratio
    18.51f,  // Gear 5: 1.000 ratio
    21.95f   // Gear 6: 0.843 ratio
};

// IMU instance
QMI8658 imu;


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
const unsigned long TPMS_DATA_TIMEOUT = 300000; // Data valid for 5 minutes (was 30 sec - too aggressive)
const unsigned long TPMS_CACHE_PRESERVE_TIME = 86400000; // Keep cached values for 24 hours

// TPMS persistence storage
Preferences tpmsPrefs;
Preferences imuPrefs;
bool tpmsDataFromCache = false;  // True if current data was loaded from NVS cache

// Display state - 8 screens to match Pi



unsigned long lastUpdate = 0;
unsigned long lastTouchTime = 0;
unsigned long lastImuUpdate = 0;
unsigned long lastSerialSend = 0;




// Boot countdown - Pi takes ~37 seconds to boot and send data


// Fun loading messages during boot (font size 2 - 10x14 has full character set)


// Page transition animation state


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
    telemetry.batteryVoltage = 0;  // No voltage data yet
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
    currentLoadingMessage = random(NUM_LOADING_MESSAGES);  // Start with random message
    lastMessageChange = millis();
    
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
        
        // During boot countdown, keep redrawing Overview screen to update countdown
        // Check once per second (1000ms) to trigger countdown redraw
        static unsigned long lastCountdownCheck = 0;
        if (!piDataReceived && currentScreen == SCREEN_OVERVIEW) {
            if (millis() - lastCountdownCheck >= 1000) {
                lastCountdownCheck = millis();
                needsRedraw = true;  // Trigger redraw for countdown update
            }
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
        if (!piDataReceived) {
            piDataReceived = true;  // Pi is sending data, end boot countdown
            needsFullRedraw = true;  // Force full redraw to show all indicators
        }
    }
    else if (cmd.startsWith("SPEED:")) {
        telemetry.speed = cmd.substring(6).toFloat();
        telemetry.connected = true;
        if (!piDataReceived) {
            piDataReceived = true;
            needsFullRedraw = true;
        }
    }
    else if (cmd.startsWith("GEAR:")) {
        telemetry.gear = cmd.substring(5).toInt();
        telemetry.connected = true;
        if (!piDataReceived) {
            piDataReceived = true;
            needsFullRedraw = true;
        }
    }
    else if (cmd.startsWith("COOLANT:")) {
        telemetry.coolantTemp = cmd.substring(8).toFloat();
        telemetry.connected = true;
        if (!piDataReceived) { piDataReceived = true; needsFullRedraw = true; }
    }
    else if (cmd.startsWith("OIL:")) {
        telemetry.oilTemp = cmd.substring(4).toFloat();
        telemetry.connected = true;
        if (!piDataReceived) { piDataReceived = true; needsFullRedraw = true; }
    }
    else if (cmd.startsWith("FUEL:")) {
        telemetry.fuelLevel = cmd.substring(5).toFloat();
        telemetry.connected = true;
        if (!piDataReceived) { piDataReceived = true; needsFullRedraw = true; }
    }
    else if (cmd.startsWith("AMBT:")) {
        telemetry.ambientTemp = cmd.substring(5).toFloat();
        telemetry.connected = true;
        if (!piDataReceived) { piDataReceived = true; needsFullRedraw = true; }
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
        if (!piDataReceived) { piDataReceived = true; needsFullRedraw = true; }
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
        if (!piDataReceived) { piDataReceived = true; needsFullRedraw = true; }
    }
    else if (cmd.startsWith("ENGINE:")) {
        telemetry.engineRunning = (cmd.substring(7).toInt() == 1);
        telemetry.connected = true;
        if (!piDataReceived) { piDataReceived = true; needsFullRedraw = true; }
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
    // Bulk telemetry update from Pi (format: TEL:rpm,speed,gear,throttle,coolant,oil,fuel,engine,gear_est,clutch,avg_mpg,range_miles,gear_color,voltage)
    // gear_color: 0=green, 1=red, 2=blue, 3=yellow, 4=cyan
    else if (cmd.startsWith("TEL:")) {
        String data = cmd.substring(4);
        int idx = 0;
        float values[15] = {0};  // 15 fields including voltage and instant MPG
        int start = 0;
        for (int i = 0; i <= data.length() && idx < 15; i++) {
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
            // MPG data fields
            if (idx >= 11) telemetry.averageMPG = values[10];
            if (idx >= 12) telemetry.rangeMiles = (int)values[11];
            // Gear color from Pi (0=green, 1=red, 2=blue, 3=yellow, 4=cyan)
            if (idx >= 13) telemetry.gearColor = (int)values[12];
            // 12V source voltage from ADS1115
            if (idx >= 14) telemetry.batteryVoltage = values[13];
            // Instantaneous MPG from MAF (Pi-calculated)
            if (idx >= 15) telemetry.instantMPG = values[14];
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
    //
    // Only forward genuinely fresh BLE readings to the Pi. Cached/stale values
    // are the Pi's responsibility (it persists its own cache and handles aging),
    // and re-sending them would reset the Pi's staleness timer.
    
    bool anyFreshData = false;  // True if we have recent BLE data
    float pressures[4] = {0, 0, 0, 0};
    float temps[4] = {0, 0, 0, 0};
    
    for (int tirePos = 0; tirePos < 4; tirePos++) {
        // Direct mapping: tirePos == sensorIndex
        unsigned long timeSinceUpdate = millis() - tpmsSensors[tirePos].lastUpdate;
        
        // Check if we have fresh BLE data (within 5 minute timeout)
        if (tpmsSensors[tirePos].valid && timeSinceUpdate < TPMS_DATA_TIMEOUT) {
            // Fresh data from BLE - use it
            pressures[tirePos] = tpmsSensors[tirePos].pressurePSI;
            temps[tirePos] = tpmsSensors[tirePos].temperatureF;
            
            // Update local telemetry for display
            telemetry.tirePressure[tirePos] = pressures[tirePos];
            telemetry.tireTemp[tirePos] = temps[tirePos];
            
            anyFreshData = true;
        }
        // Stale/missing sensors stay 0 - the Pi skips zeros and keeps its own cache
    }
    
    // Only send when we have at least one fresh reading. Pi-side code skips 0.0
    // values, so partially-stale updates won't overwrite good Pi cache.
    if (anyFreshData) {
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
            // Restore for display only. Do NOT mark this as a fresh BLE reading,
            // or the ESP32 would re-send stale values to the Pi and reset its aging.
            tpmsSensors[i].pressurePSI = psi;
            tpmsSensors[i].temperatureF = temp;
            
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
        if (telemetry.tirePressure[i] > 0) {
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
