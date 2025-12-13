/*
 * MX5 Telemetry Display - ESP32-S3 Round LCD
 * Waveshare ESP32-S3-Touch-LCD-1.85 (360x360)
 * 
 * This display shows real-time telemetry data from the Raspberry Pi
 * connected via serial communication.
 */

#include <Arduino.h>
#include <Wire.h>
#include "Display_ST77916.h"
#include "Touch_CST816.h"
#include "QMI8658.h"
#include "boot_logo.h"
#include "background_image.h"

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
    float voltage;
    float tirePressure[4];  // FL, FR, RL, RR
    float tireTemp[4];      // FL, FR, RL, RR
    float gForceX;          // Lateral (left/right)
    float gForceY;          // Longitudinal (accel/brake)
    float gForceZ;          // Vertical
    bool engineRunning;
    bool connected;
    // Diagnostics
    bool checkEngine;
    bool absWarning;
    bool oilWarning;
    bool batteryWarning;
};

TelemetryData telemetry = {0};

// IMU instance
QMI8658 imu;
bool imuAvailable = false;

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
void handleSerialCommands();
void parseCommand(String cmd);
void updateIMU();
void sendIMUData();

// Draw the background image (called on full redraw)
void drawBackground() {
    LCD_DrawImage(0, 0, BACKGROUND_DATA_WIDTH, BACKGROUND_DATA_HEIGHT, background_data);
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
    
    // Draw startup screen with boot logo
    LCD_Clear(COLOR_BG);
    LCD_DrawImageCentered(BOOT_LOGO_DATA_WIDTH, BOOT_LOGO_DATA_HEIGHT, boot_logo_data);
    delay(1500);  // Show logo for 1.5 seconds
    
    // Set demo values for testing (Fahrenheit for temps)
    telemetry.rpm = 3500;
    telemetry.speed = 65;
    telemetry.gear = 3;
    telemetry.throttle = 45;
    telemetry.brake = 0;
    telemetry.coolantTemp = 195;  // Fahrenheit
    telemetry.oilTemp = 210;
    telemetry.oilPressure = 45;
    telemetry.fuelLevel = 75;
    telemetry.voltage = 14.2;
    telemetry.tirePressure[0] = 32; telemetry.tirePressure[1] = 32;
    telemetry.tirePressure[2] = 30; telemetry.tirePressure[3] = 30;
    telemetry.tireTemp[0] = 95; telemetry.tireTemp[1] = 98;
    telemetry.tireTemp[2] = 92; telemetry.tireTemp[3] = 94;
    telemetry.gForceX = 0;
    telemetry.gForceY = 0;
    telemetry.engineRunning = true;
    telemetry.connected = false;  // Start in demo mode
    
    needsRedraw = true;
    needsFullRedraw = true;
    Serial.println("Setup complete!");
}

void loop() {
    // Handle touch input - check more frequently for responsiveness
    Touch_Loop();
    handleTouch();
    
    // Handle serial commands from Pi
    handleSerialCommands();
    
    // Update IMU at 50Hz
    if (imuAvailable && millis() - lastImuUpdate > 20) {
        lastImuUpdate = millis();
        updateIMU();
    }
    
    // Send IMU data to Pi at 10Hz
    if (imuAvailable && millis() - lastSerialSend > 100) {
        lastSerialSend = millis();
        sendIMUData();
    }
    
    // Update demo animation data at ~30Hz (only when in demo mode)
    if (millis() - lastUpdate > 33) {
        lastUpdate = millis();
        
        // Demo animation when not receiving real data
        if (!telemetry.connected) {
            static float rpmDir = 50;
            telemetry.rpm += rpmDir;
            if (telemetry.rpm > 7000) rpmDir = -50;
            if (telemetry.rpm < 1000) rpmDir = 50;
            
            // Calculate gear from RPM
            if (telemetry.rpm < 2500) telemetry.gear = 1;
            else if (telemetry.rpm < 4000) telemetry.gear = 2;
            else if (telemetry.rpm < 5500) telemetry.gear = 3;
            else if (telemetry.rpm < 6500) telemetry.gear = 4;
            else telemetry.gear = 5;
            
            telemetry.speed = telemetry.rpm / 100.0;
            
            // Demo G-force (if no IMU)
            if (!imuAvailable) {
                telemetry.gForceX = sin(millis() / 1000.0) * 0.5;
                telemetry.gForceY = cos(millis() / 1500.0) * 0.3;
            }
            
            // Only G-Force screen needs frequent updates (smooth ball movement)
            // All other screens are static - only update on screen change
            if (currentScreen == SCREEN_GFORCE) {
                needsRedraw = true;
                // G-Force handles its own partial redraw, no needsFullRedraw
            }
            // Other screens don't need continuous demo updates - they redraw on screen change
        }
    }
    
    // Redraw screen if needed
    if (needsRedraw) {
        needsRedraw = false;
        
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
    
    delay(5);  // ~200Hz loop rate for responsive touch
}

// ============================================================================
// IMU Functions
// ============================================================================

void updateIMU() {
    imu.update();
    
    // Map accelerometer axes to car orientation
    // X = lateral (positive = right turn)
    // Y = longitudinal (positive = acceleration)
    // Adjust based on how display is mounted
    telemetry.gForceX = imu.ay;  // Lateral
    telemetry.gForceY = -imu.ax; // Longitudinal (inverted)
    telemetry.gForceZ = imu.az;
    
    // Only trigger redraw on G-Force screen
    if (currentScreen == SCREEN_GFORCE) {
        needsRedraw = true;
    }
}

void sendIMUData() {
    // Send IMU data to Pi for display sync
    Serial.printf("IMU:%.3f,%.3f\n", telemetry.gForceX, telemetry.gForceY);
}

void handleTouch() {
    // Debug: Print any touch activity
    static unsigned long lastTouchDebug = 0;
    if (touch_data.points > 0 || touch_data.gesture != NONE) {
        if (millis() - lastTouchDebug > 100) {
            Serial.printf("Touch: x=%d y=%d pts=%d gesture=%d\n", 
                          touch_data.x, touch_data.y, touch_data.points, touch_data.gesture);
            lastTouchDebug = millis();
        }
    }
    
    // Handle gestures with debounce
    if (touch_data.gesture != NONE && millis() - lastTouchTime > 200) {
        lastTouchTime = millis();
        Serial.printf("Gesture detected: %d\n", touch_data.gesture);
        
        switch (touch_data.gesture) {
            case SWIPE_LEFT:
                // Swipe left = finger moves left = go to NEXT screen
                currentScreen = (ScreenMode)((currentScreen + 1) % SCREEN_COUNT);
                needsRedraw = true;
                needsFullRedraw = true;
                Serial.printf("Screen: %d (swipe left -> next)\n", currentScreen);
                // Notify Pi of screen change for sync
                Serial.printf("SCREEN_CHANGED:%d\n", currentScreen);
                break;
            case SWIPE_RIGHT:
                // Swipe right = finger moves right = go to PREVIOUS screen
                currentScreen = (ScreenMode)((currentScreen - 1 + SCREEN_COUNT) % SCREEN_COUNT);
                needsRedraw = true;
                needsFullRedraw = true;
                Serial.printf("Screen: %d (swipe right -> prev)\n", currentScreen);
                // Notify Pi of screen change for sync
                Serial.printf("SCREEN_CHANGED:%d\n", currentScreen);
                break;
            case SINGLE_CLICK:
                Serial.println("Single click detected");
                break;
            case DOUBLE_CLICK:
                Serial.println("Double click detected");
                break;
            case LONG_PRESS:
                Serial.println("Long press detected");
                break;
            case SWIPE_UP:
                Serial.println("Swipe up detected");
                break;
            case SWIPE_DOWN:
                Serial.println("Swipe down detected");
                break;
            default:
                Serial.printf("Unknown gesture: %d\n", touch_data.gesture);
                break;
        }
        
        // Clear gesture after handling
        touch_data.gesture = NONE;
    }
}

void drawOverviewScreen() {
    // Only draw on full redraw to prevent flickering overlaps
    if (!needsFullRedraw) return;
    
    drawBackground();
    
    // === GEAR INDICATOR (Large center) ===
    int gearRadius = 55;
    LCD_FillCircle(CENTER_X, CENTER_Y - 25, gearRadius, COLOR_BG_CARD);
    
    // Gear color based on RPM
    uint16_t gearGlow = MX5_GREEN;
    if (telemetry.rpm > 6500) gearGlow = MX5_RED;
    else if (telemetry.rpm > 5500) gearGlow = MX5_ORANGE;
    else if (telemetry.rpm > 4500) gearGlow = MX5_YELLOW;
    
    // Draw gear ring
    for (int r = gearRadius; r > gearRadius - 4; r--) {
        LCD_DrawCircle(CENTER_X, CENTER_Y - 25, r, gearGlow);
    }
    
    // Gear text placeholder (large centered dot)
    LCD_FillCircle(CENTER_X, CENTER_Y - 25, 20, gearGlow);
    
    // === RPM BAR (Top arc style) ===
    float rpmPercent = telemetry.rpm / 8000.0;
    int barWidth = 220;
    int barHeight = 14;
    int barX = CENTER_X - barWidth/2;
    int barY = 35;
    
    // Background
    LCD_FillRect(barX, barY, barWidth, barHeight, MX5_DARKGRAY);
    
    // RPM segments with gradient effect
    uint16_t rpmColor = MX5_GREEN;
    if (telemetry.rpm > 6000) rpmColor = MX5_RED;
    else if (telemetry.rpm > 4500) rpmColor = MX5_ORANGE;
    else if (telemetry.rpm > 3000) rpmColor = MX5_YELLOW;
    
    int fillWidth = (int)(barWidth * rpmPercent);
    if (fillWidth > 0) {
        LCD_FillRect(barX, barY, fillWidth, barHeight, rpmColor);
    }
    
    // Border and tick marks
    LCD_DrawRect(barX, barY, barWidth, barHeight, MX5_WHITE);
    for (int i = 1; i < 8; i++) {
        int tickX = barX + (barWidth * i / 8);
        LCD_FillRect(tickX, barY + barHeight - 3, 1, 3, MX5_GRAY);
    }
    
    // === SPEED (Bottom center card) ===
    int speedW = 130, speedH = 45;
    LCD_FillRect(CENTER_X - speedW/2, CENTER_Y + 50, speedW, speedH, COLOR_BG_CARD);
    LCD_DrawRect(CENTER_X - speedW/2, CENTER_Y + 50, speedW, speedH, MX5_ACCENT);
    LCD_FillCircle(CENTER_X, CENTER_Y + 72, 12, MX5_WHITE);  // Speed value placeholder
    
    // === STATUS ROW (Bottom) ===
    int statusY = CENTER_Y + 115;
    
    // Engine status
    uint16_t engineColor = telemetry.engineRunning ? MX5_GREEN : MX5_RED;
    LCD_FillCircle(CENTER_X - 70, statusY, 12, engineColor);
    LCD_DrawCircle(CENTER_X - 70, statusY, 12, MX5_WHITE);
    
    // IMU status
    uint16_t imuColor = imuAvailable ? MX5_GREEN : MX5_GRAY;
    LCD_FillCircle(CENTER_X, statusY, 12, imuColor);
    LCD_DrawCircle(CENTER_X, statusY, 12, MX5_WHITE);
    
    // Connection status
    uint16_t connColor = telemetry.connected ? MX5_GREEN : MX5_ORANGE;
    LCD_FillCircle(CENTER_X + 70, statusY, 12, connColor);
    LCD_DrawCircle(CENTER_X + 70, statusY, 12, MX5_WHITE);
    
    // === MINI TPMS (Left side) ===
    int tpmsX = 55, tpmsY = CENTER_Y + 30;
    LCD_FillRect(tpmsX - 18, tpmsY - 25, 36, 50, COLOR_BG_CARD);
    
    // Mini tire indicators
    uint16_t flCol = (telemetry.tirePressure[0] < 28) ? MX5_RED : MX5_GREEN;
    uint16_t frCol = (telemetry.tirePressure[1] < 28) ? MX5_RED : MX5_GREEN;
    uint16_t rlCol = (telemetry.tirePressure[2] < 28) ? MX5_RED : MX5_GREEN;
    uint16_t rrCol = (telemetry.tirePressure[3] < 28) ? MX5_RED : MX5_GREEN;
    
    LCD_FillRect(tpmsX - 28, tpmsY - 18, 8, 14, flCol);
    LCD_FillRect(tpmsX + 20, tpmsY - 18, 8, 14, frCol);
    LCD_FillRect(tpmsX - 28, tpmsY + 6, 8, 14, rlCol);
    LCD_FillRect(tpmsX + 20, tpmsY + 6, 8, 14, rrCol);
    
    // === MINI TEMPS (Right side) ===
    int tempX = SCREEN_WIDTH - 55, tempY = CENTER_Y + 30;
    LCD_FillRect(tempX - 25, tempY - 25, 50, 50, COLOR_BG_CARD);
    
    // Coolant indicator
    uint16_t coolCol = (telemetry.coolantTemp > 220) ? MX5_RED : MX5_BLUE;
    LCD_FillCircle(tempX - 10, tempY - 8, 8, coolCol);
    
    // Oil indicator
    uint16_t oilCol = (telemetry.oilTemp > 250) ? MX5_RED : MX5_ORANGE;
    LCD_FillCircle(tempX + 10, tempY - 8, 8, oilCol);
    
    // Fuel indicator
    uint16_t fuelCol = (telemetry.fuelLevel < 15) ? MX5_RED : MX5_YELLOW;
    LCD_FillCircle(tempX, tempY + 12, 8, fuelCol);
    
    // Page indicator
    drawPageIndicator();
}

void drawRPMScreen() {
    // Only draw on full redraw to prevent flickering overlaps
    if (!needsFullRedraw) return;
    
    drawBackground();
    
    // === RPM ARC GAUGE ===
    float rpmPercent = telemetry.rpm / 8000.0;
    int gaugeRadius = 125;
    int arcThickness = 18;
    
    // Draw gauge segments (10 segments around arc)
    for (int i = 0; i < 10; i++) {
        float segStart = i / 10.0;
        
        // Determine segment color
        uint16_t segColor = MX5_DARKGRAY;
        if (segStart < rpmPercent) {
            if (i >= 8) segColor = MX5_RED;
            else if (i >= 7) segColor = MX5_ORANGE;
            else if (i >= 5) segColor = MX5_YELLOW;
            else segColor = MX5_GREEN;
        }
        
        // Arc from -135° to +135° (270° total)
        float angle = (-135 + i * 27) * PI / 180.0;
        int px = CENTER_X + cos(angle) * gaugeRadius;
        int py = CENTER_Y + sin(angle) * gaugeRadius;
        
        // Draw segment with glow effect for active segments
        LCD_FillCircle(px, py, arcThickness/2 + 2, segColor);
        if (segStart < rpmPercent && segColor != MX5_DARKGRAY) {
            LCD_DrawCircle(px, py, arcThickness/2 + 4, segColor);
        }
    }
    
    // === CENTER DISPLAY ===
    LCD_FillCircle(CENTER_X, CENTER_Y, 55, COLOR_BG_CARD);
    
    // Inner ring
    uint16_t ringColor = MX5_ACCENT;
    if (telemetry.rpm > 6500) ringColor = MX5_RED;
    for (int r = 55; r > 52; r--) {
        LCD_DrawCircle(CENTER_X, CENTER_Y, r, ringColor);
    }
    
    // Gear indicator in center
    uint16_t gearColor = MX5_WHITE;
    if (telemetry.rpm > 6500) gearColor = MX5_RED;
    LCD_FillCircle(CENTER_X, CENTER_Y - 5, 22, gearColor);
    
    // RPM value placeholder below center
    LCD_FillRect(CENTER_X - 35, CENTER_Y + 20, 70, 20, COLOR_BG);
    
    // === SPEED CARD (Bottom) ===
    int speedW = 130, speedH = 55;
    int speedY = CENTER_Y + 85;
    LCD_FillRect(CENTER_X - speedW/2, speedY, speedW, speedH, COLOR_BG_CARD);
    LCD_DrawRect(CENTER_X - speedW/2, speedY, speedW, speedH, MX5_BLUE);
    
    // Speed value placeholder
    LCD_FillCircle(CENTER_X, speedY + 28, 14, MX5_WHITE);
    
    // === THROTTLE/BRAKE BARS (Sides) ===
    int barW = 18, barH = 100;
    int barY = CENTER_Y - barH/2;
    
    // Throttle (right side) - green
    int throttleX = CENTER_X + 95;
    LCD_FillRect(throttleX, barY, barW, barH, MX5_DARKGRAY);
    int throttleFill = (int)(barH * telemetry.throttle / 100.0);
    if (throttleFill > 0) {
        LCD_FillRect(throttleX, barY + barH - throttleFill, barW, throttleFill, MX5_GREEN);
    }
    LCD_DrawRect(throttleX, barY, barW, barH, MX5_GRAY);
    
    // Brake (left side) - red  
    int brakeX = CENTER_X - 95 - barW;
    LCD_FillRect(brakeX, barY, barW, barH, MX5_DARKGRAY);
    int brakeFill = (int)(barH * telemetry.brake / 100.0);
    if (brakeFill > 0) {
        LCD_FillRect(brakeX, barY + barH - brakeFill, barW, brakeFill, MX5_RED);
    }
    LCD_DrawRect(brakeX, barY, barW, barH, MX5_GRAY);
    
    drawPageIndicator();
}

void drawTPMSScreen() {
    // Only draw on full redraw to prevent flickering overlaps
    if (!needsFullRedraw) return;
    
    drawBackground();
    
    // === CAR BODY OUTLINE ===
    // Main body
    LCD_FillRect(CENTER_X - 35, CENTER_Y - 75, 70, 150, COLOR_BG_CARD);
    LCD_DrawRect(CENTER_X - 35, CENTER_Y - 75, 70, 150, MX5_GRAY);
    
    // Windshield (trapezoid top)
    LCD_DrawLine(CENTER_X - 30, CENTER_Y - 55, CENTER_X - 25, CENTER_Y - 70, MX5_GRAY);
    LCD_DrawLine(CENTER_X + 30, CENTER_Y - 55, CENTER_X + 25, CENTER_Y - 70, MX5_GRAY);
    
    // Rear window
    LCD_DrawLine(CENTER_X - 30, CENTER_Y + 55, CENTER_X - 25, CENTER_Y + 70, MX5_GRAY);
    LCD_DrawLine(CENTER_X + 30, CENTER_Y + 55, CENTER_X + 25, CENTER_Y + 70, MX5_GRAY);
    
    // === TIRE BOXES ===
    const int tireW = 32, tireH = 48;
    const int tireOffsetX = 58, tireOffsetY = 50;
    
    // Helper lambda for tire color based on pressure
    auto getTireColor = [](float psi) -> uint16_t {
        if (psi < 26) return MX5_RED;
        if (psi < 28) return MX5_ORANGE;
        if (psi > 36) return MX5_ORANGE;
        if (psi > 38) return MX5_RED;
        return MX5_GREEN;
    };
    
    // Front Left tire
    uint16_t flColor = getTireColor(telemetry.tirePressure[0]);
    int flX = CENTER_X - tireOffsetX - tireW/2;
    int flY = CENTER_Y - tireOffsetY - tireH/2;
    LCD_FillRect(flX, flY, tireW, tireH, flColor);
    LCD_DrawRect(flX, flY, tireW, tireH, MX5_WHITE);
    // Tire groove lines
    LCD_DrawLine(flX + 6, flY + 4, flX + 6, flY + tireH - 4, COLOR_BG_CARD);
    LCD_DrawLine(flX + tireW - 6, flY + 4, flX + tireW - 6, flY + tireH - 4, COLOR_BG_CARD);
    
    // Front Right tire
    uint16_t frColor = getTireColor(telemetry.tirePressure[1]);
    int frX = CENTER_X + tireOffsetX - tireW/2;
    int frY = CENTER_Y - tireOffsetY - tireH/2;
    LCD_FillRect(frX, frY, tireW, tireH, frColor);
    LCD_DrawRect(frX, frY, tireW, tireH, MX5_WHITE);
    LCD_DrawLine(frX + 6, frY + 4, frX + 6, frY + tireH - 4, COLOR_BG_CARD);
    LCD_DrawLine(frX + tireW - 6, frY + 4, frX + tireW - 6, frY + tireH - 4, COLOR_BG_CARD);
    
    // Rear Left tire
    uint16_t rlColor = getTireColor(telemetry.tirePressure[2]);
    int rlX = CENTER_X - tireOffsetX - tireW/2;
    int rlY = CENTER_Y + tireOffsetY - tireH/2;
    LCD_FillRect(rlX, rlY, tireW, tireH, rlColor);
    LCD_DrawRect(rlX, rlY, tireW, tireH, MX5_WHITE);
    LCD_DrawLine(rlX + 6, rlY + 4, rlX + 6, rlY + tireH - 4, COLOR_BG_CARD);
    LCD_DrawLine(rlX + tireW - 6, rlY + 4, rlX + tireW - 6, rlY + tireH - 4, COLOR_BG_CARD);
    
    // Rear Right tire
    uint16_t rrColor = getTireColor(telemetry.tirePressure[3]);
    int rrX = CENTER_X + tireOffsetX - tireW/2;
    int rrY = CENTER_Y + tireOffsetY - tireH/2;
    LCD_FillRect(rrX, rrY, tireW, tireH, rrColor);
    LCD_DrawRect(rrX, rrY, tireW, tireH, MX5_WHITE);
    LCD_DrawLine(rrX + 6, rrY + 4, rrX + 6, rrY + tireH - 4, COLOR_BG_CARD);
    LCD_DrawLine(rrX + tireW - 6, rrY + 4, rrX + tireW - 6, rrY + tireH - 4, COLOR_BG_CARD);
    
    // === PRESSURE VALUE CARDS (outside tires) ===
    int cardW = 50, cardH = 28;
    
    // FL pressure card
    LCD_FillRect(flX - cardW - 8, flY + tireH/2 - cardH/2, cardW, cardH, COLOR_BG_CARD);
    LCD_DrawRect(flX - cardW - 8, flY + tireH/2 - cardH/2, cardW, cardH, flColor);
    
    // FR pressure card
    LCD_FillRect(frX + tireW + 8, frY + tireH/2 - cardH/2, cardW, cardH, COLOR_BG_CARD);
    LCD_DrawRect(frX + tireW + 8, frY + tireH/2 - cardH/2, cardW, cardH, frColor);
    
    // RL pressure card
    LCD_FillRect(rlX - cardW - 8, rlY + tireH/2 - cardH/2, cardW, cardH, COLOR_BG_CARD);
    LCD_DrawRect(rlX - cardW - 8, rlY + tireH/2 - cardH/2, cardW, cardH, rlColor);
    
    // RR pressure card
    LCD_FillRect(rrX + tireW + 8, rrY + tireH/2 - cardH/2, cardW, cardH, COLOR_BG_CARD);
    LCD_DrawRect(rrX + tireW + 8, rrY + tireH/2 - cardH/2, cardW, cardH, rrColor);
    
    drawPageIndicator();
}

void drawEngineScreen() {
    // Only draw on full redraw to prevent flickering overlaps
    if (!needsFullRedraw) return;
    
    drawBackground();
    
    int cardW = 115, cardH = 75;
    int gap = 15;
    int startX = CENTER_X - cardW - gap/2;
    int startY = CENTER_Y - cardH - gap/2 - 10;
    
    // === COOLANT TEMP (Top Left) ===
    uint16_t coolantColor = MX5_BLUE;
    if (telemetry.coolantTemp > 230) coolantColor = MX5_RED;
    else if (telemetry.coolantTemp > 215) coolantColor = MX5_ORANGE;
    
    LCD_FillRect(startX, startY, cardW, cardH, COLOR_BG_CARD);
    LCD_DrawRect(startX, startY, cardW, cardH, coolantColor);
    
    // Temperature icon (thermometer shape)
    int iconX = startX + 25, iconY = startY + cardH/2;
    LCD_FillRect(iconX - 3, iconY - 18, 6, 28, coolantColor);
    LCD_FillCircle(iconX, iconY + 15, 8, coolantColor);
    LCD_FillCircle(iconX, iconY - 18, 4, coolantColor);
    
    // Value indicator bar
    float coolantPct = constrain((telemetry.coolantTemp - 100) / 150.0, 0, 1);
    int barX = startX + 50, barY = startY + 15;
    LCD_FillRect(barX, barY, 50, 10, MX5_DARKGRAY);
    LCD_FillRect(barX, barY, (int)(50 * coolantPct), 10, coolantColor);
    
    // === OIL TEMP (Top Right) ===
    uint16_t oilColor = MX5_ORANGE;
    if (telemetry.oilTemp > 260) oilColor = MX5_RED;
    else if (telemetry.oilTemp < 180) oilColor = MX5_BLUE;
    
    LCD_FillRect(startX + cardW + gap, startY, cardW, cardH, COLOR_BG_CARD);
    LCD_DrawRect(startX + cardW + gap, startY, cardW, cardH, oilColor);
    
    // Oil drop icon
    iconX = startX + cardW + gap + 25;
    LCD_FillCircle(iconX, iconY + 8, 10, oilColor);
    // Drop point
    for (int i = 0; i < 8; i++) {
        LCD_FillRect(iconX - 4 + i/2, iconY - 10 + i, 8 - i, 2, oilColor);
    }
    
    // Value bar
    float oilPct = constrain((telemetry.oilTemp - 150) / 150.0, 0, 1);
    barX = startX + cardW + gap + 50;
    LCD_FillRect(barX, barY, 50, 10, MX5_DARKGRAY);
    LCD_FillRect(barX, barY, (int)(50 * oilPct), 10, oilColor);
    
    // === FUEL LEVEL (Bottom Left) ===
    uint16_t fuelColor = MX5_YELLOW;
    if (telemetry.fuelLevel < 15) fuelColor = MX5_RED;
    else if (telemetry.fuelLevel < 25) fuelColor = MX5_ORANGE;
    
    startY = CENTER_Y + gap/2 - 10;
    LCD_FillRect(startX, startY, cardW, cardH, COLOR_BG_CARD);
    LCD_DrawRect(startX, startY, cardW, cardH, fuelColor);
    
    // Fuel pump icon
    iconX = startX + 25;
    iconY = startY + cardH/2;
    LCD_FillRect(iconX - 8, iconY - 8, 16, 20, fuelColor);
    LCD_FillRect(iconX - 10, iconY - 10, 4, 8, fuelColor);
    LCD_FillRect(iconX + 8, iconY - 5, 6, 3, fuelColor);
    
    // Fuel gauge bar
    barX = startX + 50;
    barY = startY + 15;
    LCD_FillRect(barX, barY, 50, 10, MX5_DARKGRAY);
    LCD_FillRect(barX, barY, (int)(50 * telemetry.fuelLevel / 100.0), 10, fuelColor);
    
    // === VOLTAGE (Bottom Right) ===
    uint16_t voltColor = MX5_GREEN;
    if (telemetry.voltage < 12.0) voltColor = MX5_RED;
    else if (telemetry.voltage < 12.8) voltColor = MX5_ORANGE;
    else if (telemetry.voltage > 15.0) voltColor = MX5_RED;
    
    LCD_FillRect(startX + cardW + gap, startY, cardW, cardH, COLOR_BG_CARD);
    LCD_DrawRect(startX + cardW + gap, startY, cardW, cardH, voltColor);
    
    // Battery icon
    iconX = startX + cardW + gap + 25;
    LCD_FillRect(iconX - 10, iconY - 6, 20, 14, voltColor);
    LCD_FillRect(iconX + 10, iconY - 3, 4, 8, voltColor);
    // Battery segments
    LCD_FillRect(iconX - 7, iconY - 3, 4, 8, COLOR_BG_CARD);
    LCD_FillRect(iconX - 1, iconY - 3, 4, 8, COLOR_BG_CARD);
    LCD_FillRect(iconX + 5, iconY - 3, 4, 8, COLOR_BG_CARD);
    
    // Voltage bar
    float voltPct = constrain((telemetry.voltage - 11.0) / 4.0, 0, 1);
    barX = startX + cardW + gap + 50;
    barY = startY + 15;
    LCD_FillRect(barX, barY, 50, 10, MX5_DARKGRAY);
    LCD_FillRect(barX, barY, (int)(50 * voltPct), 10, voltColor);
    
    drawPageIndicator();
}

void drawGForceScreen() {
    // Track previous G-force position to erase old dot
    static int lastGX = CENTER_X;
    static int lastGY = CENTER_Y;
    
    // Only draw background on full redraw
    if (needsFullRedraw) {
        drawBackground();
        
        // Draw grid circles for G reference
        for (int g = 1; g <= 3; g++) {
            int radius = g * 45;
            LCD_DrawCircle(CENTER_X, CENTER_Y, radius, MX5_DARKGRAY);
        }
        
        // Draw crosshairs
        LCD_DrawLine(CENTER_X - 140, CENTER_Y, CENTER_X + 140, CENTER_Y, MX5_DARKGRAY);
        LCD_DrawLine(CENTER_X, CENTER_Y - 140, CENTER_X, CENTER_Y + 140, MX5_DARKGRAY);
        
        // Labels at edges
        LCD_FillCircle(CENTER_X, CENTER_Y - 145, 5, MX5_GREEN);  // Accel
        LCD_FillCircle(CENTER_X, CENTER_Y + 145, 5, MX5_RED);    // Brake
        LCD_FillCircle(CENTER_X - 145, CENTER_Y, 5, MX5_CYAN);   // Left
        LCD_FillCircle(CENTER_X + 145, CENTER_Y, 5, MX5_CYAN);   // Right
    } else {
        // Clear old G-force dot position
        LCD_FillCircle(lastGX, lastGY, 18, COLOR_BG);
        // Redraw grid at old position
        for (int g = 1; g <= 3; g++) {
            int radius = g * 45;
            if (abs(lastGX - CENTER_X) < radius + 20 || abs(lastGY - CENTER_Y) < radius + 20) {
                LCD_DrawCircle(CENTER_X, CENTER_Y, radius, MX5_DARKGRAY);
            }
        }
    }
    
    // Calculate G-force dot position (1.5G = full radius)
    float maxG = 1.5;
    int maxRadius = 135;
    int gX = CENTER_X + (int)(telemetry.gForceX / maxG * maxRadius);
    int gY = CENTER_Y - (int)(telemetry.gForceY / maxG * maxRadius);  // Y inverted for display
    
    // Clamp to circle
    float dist = sqrt(pow(gX - CENTER_X, 2) + pow(gY - CENTER_Y, 2));
    if (dist > maxRadius) {
        float scale = maxRadius / dist;
        gX = CENTER_X + (int)((gX - CENTER_X) * scale);
        gY = CENTER_Y + (int)((gY - CENTER_Y) * scale);
    }
    
    // Color based on total G
    float totalG = sqrt(telemetry.gForceX * telemetry.gForceX + telemetry.gForceY * telemetry.gForceY);
    uint16_t dotColor = MX5_GREEN;
    if (totalG > 1.0) dotColor = MX5_RED;
    else if (totalG > 0.7) dotColor = MX5_ORANGE;
    else if (totalG > 0.4) dotColor = MX5_YELLOW;
    
    // Draw G-force indicator with glow
    LCD_FillCircle(gX, gY, 16, dotColor);
    LCD_DrawCircle(gX, gY, 16, MX5_WHITE);
    LCD_DrawCircle(gX, gY, 17, MX5_WHITE);
    
    // Trail effect - small dot at center
    LCD_FillCircle(CENTER_X, CENTER_Y, 4, MX5_WHITE);
    
    // Remember position for next frame
    lastGX = gX;
    lastGY = gY;
    
    // G values display (bottom)
    LCD_FillRect(CENTER_X - 80, SCREEN_HEIGHT - 55, 160, 35, COLOR_BG_CARD);
    LCD_DrawRect(CENTER_X - 80, SCREEN_HEIGHT - 55, 160, 35, MX5_ACCENT);
    
    // Page indicator
    int dotSpacing = 12;
    for (int i = 0; i < SCREEN_COUNT; i++) {
        uint16_t dotColor2 = (i == currentScreen) ? MX5_WHITE : MX5_DARKGRAY;
        LCD_FillCircle(CENTER_X - (SCREEN_COUNT * dotSpacing)/2 + i * dotSpacing + 6, SCREEN_HEIGHT - 18, 3, dotColor2);
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
    LCD_FillRect(x, y, w, h, COLOR_BG_CARD);
    LCD_DrawRect(x, y, w, h, borderColor);
}

void drawProgressBar(int x, int y, int w, int h, float percent, uint16_t color) {
    percent = constrain(percent, 0, 100);
    LCD_FillRect(x, y, w, h, MX5_DARKGRAY);
    int fillW = (int)(w * percent / 100.0);
    if (fillW > 0) {
        LCD_FillRect(x, y, fillW, h, color);
    }
    LCD_DrawRect(x, y, w, h, MX5_GRAY);
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
    struct DiagItem {
        const char* name;
        bool isWarning;
        uint16_t colorOk;
        uint16_t colorWarn;
    };
    
    DiagItem items[] = {
        {"CHECK ENGINE", telemetry.checkEngine, MX5_GREEN, MX5_RED},
        {"ABS SYSTEM", telemetry.absWarning, MX5_GREEN, MX5_ORANGE},
        {"OIL PRESSURE", telemetry.oilWarning, MX5_GREEN, MX5_RED},
        {"BATTERY", telemetry.batteryWarning, MX5_GREEN, MX5_YELLOW},
        {"ENGINE RUN", !telemetry.engineRunning, MX5_GREEN, MX5_RED},
        {"CONNECTION", !telemetry.connected, MX5_GREEN, MX5_ORANGE},
    };
    
    for (int i = 0; i < 6; i++) {
        uint16_t statusColor = items[i].isWarning ? items[i].colorWarn : items[i].colorOk;
        int y = startY + i * (itemH + itemGap);
        
        // Item background card
        LCD_FillRect(startX, y, itemW, itemH, COLOR_BG_CARD);
        
        // Left status indicator (checkmark or X style)
        if (items[i].isWarning) {
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
        
        // Status circle on right
        int circleX = startX + itemW - 25;
        int circleY = y + itemH/2;
        LCD_FillCircle(circleX, circleY, 12, statusColor);
        LCD_DrawCircle(circleX, circleY, 12, MX5_WHITE);
        
        // Inner indicator
        if (!items[i].isWarning) {
            LCD_FillCircle(circleX, circleY, 5, MX5_WHITE);
        }
        
        // Border with status color
        LCD_DrawRect(startX, y, itemW, itemH, statusColor);
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
    LCD_FillRect(startX, startY, itemW, itemH, COLOR_BG_CARD);
    LCD_DrawRect(startX, startY, itemW, itemH, imuColor);
    
    // IMU icon (accelerometer shape)
    int iconX = startX + 30;
    int iconY = startY + itemH/2;
    LCD_DrawRect(iconX - 10, iconY - 10, 20, 20, imuColor);
    LCD_DrawLine(iconX, iconY - 15, iconX, iconY + 15, imuColor);
    LCD_DrawLine(iconX - 15, iconY, iconX + 15, iconY, imuColor);
    LCD_FillCircle(iconX, iconY, 4, imuColor);
    
    // Status indicator
    LCD_FillCircle(startX + itemW - 30, iconY, 10, imuColor);
    
    startY += itemH + itemGap;
    
    // === SERIAL STATUS ===
    uint16_t serialColor = telemetry.connected ? MX5_GREEN : MX5_ORANGE;
    LCD_FillRect(startX, startY, itemW, itemH, COLOR_BG_CARD);
    LCD_DrawRect(startX, startY, itemW, itemH, serialColor);
    
    // Serial/USB icon
    iconY = startY + itemH/2;
    LCD_FillRect(iconX - 8, iconY - 6, 16, 12, serialColor);
    LCD_FillRect(iconX - 4, iconY + 6, 8, 4, serialColor);
    LCD_FillRect(iconX - 2, iconY - 10, 4, 4, serialColor);
    
    LCD_FillCircle(startX + itemW - 30, iconY, 10, serialColor);
    
    startY += itemH + itemGap;
    
    // === DISPLAY INFO ===
    LCD_FillRect(startX, startY, itemW, itemH, COLOR_BG_CARD);
    LCD_DrawRect(startX, startY, itemW, itemH, MX5_ACCENT);
    
    // Display icon
    iconY = startY + itemH/2;
    LCD_DrawRect(iconX - 12, iconY - 8, 24, 16, MX5_ACCENT);
    LCD_FillRect(iconX - 10, iconY - 6, 20, 12, MX5_ACCENT);
    LCD_FillRect(iconX - 4, iconY + 8, 8, 3, MX5_ACCENT);
    LCD_FillRect(iconX - 8, iconY + 11, 16, 2, MX5_ACCENT);
    
    // Info circle
    LCD_FillCircle(startX + itemW - 30, iconY, 10, MX5_ACCENT);
    
    startY += itemH + itemGap;
    
    // === MEMORY ===
    LCD_FillRect(startX, startY, itemW, itemH, COLOR_BG_CARD);
    LCD_DrawRect(startX, startY, itemW, itemH, MX5_PURPLE);
    
    // Memory chip icon
    iconY = startY + itemH/2;
    LCD_FillRect(iconX - 8, iconY - 10, 16, 20, MX5_PURPLE);
    for (int p = 0; p < 4; p++) {
        LCD_FillRect(iconX - 12, iconY - 8 + p * 5, 4, 3, MX5_PURPLE);
        LCD_FillRect(iconX + 8, iconY - 8 + p * 5, 4, 3, MX5_PURPLE);
    }
    
    LCD_FillCircle(startX + itemW - 30, iconY, 10, MX5_PURPLE);
    
    startY += itemH + itemGap;
    
    // === UPTIME ===
    LCD_FillRect(startX, startY, itemW, itemH, COLOR_BG_CARD);
    LCD_DrawRect(startX, startY, itemW, itemH, MX5_CYAN);
    
    // Clock icon
    iconY = startY + itemH/2;
    LCD_DrawCircle(iconX, iconY, 10, MX5_CYAN);
    LCD_DrawCircle(iconX, iconY, 11, MX5_CYAN);
    LCD_DrawLine(iconX, iconY, iconX, iconY - 6, MX5_CYAN);
    LCD_DrawLine(iconX, iconY, iconX + 5, iconY + 2, MX5_CYAN);
    LCD_FillCircle(iconX, iconY, 2, MX5_CYAN);
    
    LCD_FillCircle(startX + itemW - 30, iconY, 10, MX5_CYAN);
    
    drawPageIndicator();
}

void drawSettingsScreen() {
    // Only draw on full redraw to prevent flickering overlaps
    if (!needsFullRedraw) return;
    
    drawBackground();
    
    int startY = 35;
    int itemH = 52;
    int itemGap = 6;
    int itemW = 290;
    int startX = CENTER_X - itemW/2;
    
    // === BRIGHTNESS (with slider) ===
    LCD_FillRect(startX, startY, itemW, itemH, COLOR_BG_CARD);
    LCD_DrawRect(startX, startY, itemW, itemH, MX5_YELLOW);
    
    // Sun icon
    int iconX = startX + 30;
    int iconY = startY + itemH/2;
    LCD_FillCircle(iconX, iconY, 8, MX5_YELLOW);
    for (int r = 0; r < 8; r++) {
        float angle = r * 3.14159 / 4;
        int x1 = iconX + cos(angle) * 11;
        int y1 = iconY + sin(angle) * 11;
        int x2 = iconX + cos(angle) * 15;
        int y2 = iconY + sin(angle) * 15;
        LCD_DrawLine(x1, y1, x2, y2, MX5_YELLOW);
    }
    
    // Slider bar
    int sliderX = startX + 70;
    int sliderW = 180;
    int sliderY = iconY;
    LCD_FillRect(sliderX, sliderY - 3, sliderW, 6, MX5_DARKGRAY);
    LCD_FillRect(sliderX, sliderY - 3, (int)(sliderW * 0.75), 6, MX5_YELLOW);
    LCD_FillCircle(sliderX + (int)(sliderW * 0.75), sliderY, 8, MX5_WHITE);
    
    startY += itemH + itemGap;
    
    // === UNITS (toggle) ===
    LCD_FillRect(startX, startY, itemW, itemH, COLOR_BG_CARD);
    LCD_DrawRect(startX, startY, itemW, itemH, MX5_ACCENT);
    
    // Speed icon
    iconX = startX + 30;
    iconY = startY + itemH/2;
    LCD_DrawCircle(iconX, iconY, 10, MX5_ACCENT);
    LCD_DrawLine(iconX, iconY, iconX + 6, iconY - 6, MX5_ACCENT);
    LCD_DrawLine(iconX, iconY, iconX + 7, iconY - 5, MX5_ACCENT);
    
    // Toggle switch (ON position for MPH)
    int toggleX = startX + itemW - 70;
    int toggleW = 50;
    int toggleH = 24;
    LCD_FillRect(toggleX, iconY - toggleH/2, toggleW, toggleH, MX5_GREEN);
    LCD_DrawRect(toggleX, iconY - toggleH/2, toggleW, toggleH, MX5_WHITE);
    LCD_FillCircle(toggleX + toggleW - 12, iconY, 9, MX5_WHITE);
    
    startY += itemH + itemGap;
    
    // === SHIFT LIGHT RPM (with value) ===
    LCD_FillRect(startX, startY, itemW, itemH, COLOR_BG_CARD);
    LCD_DrawRect(startX, startY, itemW, itemH, MX5_RED);
    
    // Warning light icon
    iconX = startX + 30;
    iconY = startY + itemH/2;
    LCD_FillCircle(iconX, iconY, 10, MX5_RED);
    LCD_FillCircle(iconX, iconY, 6, COLOR_BG_CARD);
    LCD_FillCircle(iconX, iconY, 3, MX5_RED);
    
    // RPM value box
    int valueX = startX + itemW - 80;
    int valueW = 60;
    LCD_FillRect(valueX, iconY - 12, valueW, 24, COLOR_BG_ELEVATED);
    LCD_DrawRect(valueX, iconY - 12, valueW, 24, MX5_RED);
    LCD_FillCircle(valueX + valueW/2, iconY, 4, MX5_RED);  // Value indicator
    
    startY += itemH + itemGap;
    
    // === SCREEN TIMEOUT (with value) ===
    LCD_FillRect(startX, startY, itemW, itemH, COLOR_BG_CARD);
    LCD_DrawRect(startX, startY, itemW, itemH, MX5_CYAN);
    
    // Timer/clock icon
    iconX = startX + 30;
    iconY = startY + itemH/2;
    LCD_DrawCircle(iconX, iconY, 10, MX5_CYAN);
    LCD_DrawCircle(iconX, iconY, 11, MX5_CYAN);
    LCD_DrawLine(iconX, iconY - 7, iconX, iconY, MX5_CYAN);
    LCD_DrawLine(iconX, iconY, iconX + 5, iconY, MX5_CYAN);
    LCD_FillRect(iconX - 2, iconY - 14, 4, 4, MX5_CYAN);  // Top knob
    
    // Timeout value box
    valueX = startX + itemW - 80;
    LCD_FillRect(valueX, iconY - 12, valueW, 24, COLOR_BG_ELEVATED);
    LCD_DrawRect(valueX, iconY - 12, valueW, 24, MX5_CYAN);
    LCD_FillCircle(valueX + valueW/2, iconY, 4, MX5_CYAN);  // Value indicator
    
    startY += itemH + itemGap;
    
    // === DEMO MODE (toggle) ===
    LCD_FillRect(startX, startY, itemW, itemH, COLOR_BG_CARD);
    LCD_DrawRect(startX, startY, itemW, itemH, MX5_PURPLE);
    
    // Play/demo icon
    iconX = startX + 30;
    iconY = startY + itemH/2;
    LCD_FillRect(iconX - 10, iconY - 10, 20, 20, MX5_PURPLE);
    // Play triangle inside
    LCD_DrawLine(iconX - 4, iconY - 6, iconX - 4, iconY + 6, COLOR_BG_CARD);
    LCD_DrawLine(iconX - 4, iconY - 6, iconX + 6, iconY, COLOR_BG_CARD);
    LCD_DrawLine(iconX - 4, iconY + 6, iconX + 6, iconY, COLOR_BG_CARD);
    
    // Toggle switch (OFF position)
    toggleX = startX + itemW - 70;
    LCD_FillRect(toggleX, iconY - toggleH/2, toggleW, toggleH, MX5_DARKGRAY);
    LCD_DrawRect(toggleX, iconY - toggleH/2, toggleW, toggleH, MX5_GRAY);
    LCD_FillCircle(toggleX + 12, iconY, 9, MX5_WHITE);
    
    drawPageIndicator();
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
    
    // Navigation commands (swipe simulation)
    if (cmd == "LEFT" || cmd == "left" || cmd == "l") {
        currentScreen = (ScreenMode)((currentScreen + 1) % SCREEN_COUNT);
        needsRedraw = true;
        needsFullRedraw = true;  // Required for screens that only draw on full redraw
        LCD_Clear(MX5_BLACK);
        Serial.println("OK:SCREEN_NEXT");
    }
    else if (cmd == "RIGHT" || cmd == "right" || cmd == "r") {
        currentScreen = (ScreenMode)((currentScreen - 1 + SCREEN_COUNT) % SCREEN_COUNT);
        needsRedraw = true;
        needsFullRedraw = true;  // Required for screens that only draw on full redraw
        LCD_Clear(MX5_BLACK);
        Serial.println("OK:SCREEN_PREV");
    }
    else if (cmd == "CLICK" || cmd == "click" || cmd == "c") {
        // Single click action - toggle something or confirm
        Serial.println("OK:CLICK");
    }
    // Direct screen selection
    else if (cmd.startsWith("SCREEN:") || cmd.startsWith("screen:")) {
        int screenNum = cmd.substring(7).toInt();
        if (screenNum >= 0 && screenNum < SCREEN_COUNT) {
            currentScreen = (ScreenMode)screenNum;
            needsRedraw = true;
            needsFullRedraw = true;  // Redraw background on screen change
            Serial.printf("OK:SCREEN_%d\n", screenNum);
        }
    }
    // Telemetry data updates from Pi (format: KEY:VALUE)
    else if (cmd.startsWith("RPM:")) {
        telemetry.rpm = cmd.substring(4).toFloat();
        telemetry.connected = true;
    }
    else if (cmd.startsWith("SPEED:")) {
        telemetry.speed = cmd.substring(6).toFloat();
        telemetry.connected = true;
    }
    else if (cmd.startsWith("GEAR:")) {
        telemetry.gear = cmd.substring(5).toInt();
        telemetry.connected = true;
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
    else if (cmd.startsWith("VOLT:")) {
        telemetry.voltage = cmd.substring(5).toFloat();
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
    else if (cmd == "PING") {
        Serial.println("PONG");
    }
    else if (cmd == "STATUS") {
        Serial.printf("SCREEN:%d,RPM:%.0f,SPEED:%.0f,GEAR:%d,CONNECTED:%d\n",
                      currentScreen, telemetry.rpm, telemetry.speed, 
                      telemetry.gear, telemetry.connected ? 1 : 0);
    }
    else if (cmd == "DEMO:ON") {
        telemetry.connected = false;  // Enable demo mode
        Serial.println("OK:DEMO_ON");
    }
    else if (cmd == "DEMO:OFF") {
        telemetry.connected = true;   // Disable demo mode
        Serial.println("OK:DEMO_OFF");
    }
}
