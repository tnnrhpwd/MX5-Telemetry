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
    
    // === TITLE ===
    LCD_DrawString(CENTER_X - 48, 15, "OVERVIEW", MX5_WHITE, COLOR_BG, 2);
    
    // === GEAR INDICATOR (Large center) ===
    int gearRadius = 50;
    int gearY = CENTER_Y - 30;
    LCD_FillCircle(CENTER_X, gearY, gearRadius, COLOR_BG_CARD);
    
    // Gear color based on RPM
    uint16_t gearGlow = MX5_GREEN;
    if (telemetry.rpm > 6500) gearGlow = MX5_RED;
    else if (telemetry.rpm > 5500) gearGlow = MX5_ORANGE;
    else if (telemetry.rpm > 4500) gearGlow = MX5_YELLOW;
    
    // Draw gear ring
    for (int r = gearRadius; r > gearRadius - 4; r--) {
        LCD_DrawCircle(CENTER_X, gearY, r, gearGlow);
    }
    
    // Gear text - show actual gear number
    char gearStr[4];
    if (telemetry.gear == 0) snprintf(gearStr, sizeof(gearStr), "N");
    else if (telemetry.gear == -1) snprintf(gearStr, sizeof(gearStr), "R");
    else snprintf(gearStr, sizeof(gearStr), "%d", telemetry.gear);
    LCD_DrawString(CENTER_X - 8, gearY - 12, gearStr, gearGlow, COLOR_BG_CARD, 3);
    LCD_DrawString(CENTER_X - 24, gearY + 22, "GEAR", MX5_GRAY, COLOR_BG_CARD, 1);
    
    // === RPM BAR (Top) ===
    float rpmPercent = telemetry.rpm / 8000.0;
    int barWidth = 200;
    int barHeight = 14;
    int barX = CENTER_X - barWidth/2;
    int barY = 48;
    
    LCD_DrawString(CENTER_X - 12, barY - 15, "RPM", MX5_GRAY, COLOR_BG, 1);
    LCD_FillRoundRect(barX, barY, barWidth, barHeight, 6, MX5_DARKGRAY);
    
    uint16_t rpmColor = MX5_GREEN;
    if (telemetry.rpm > 6000) rpmColor = MX5_RED;
    else if (telemetry.rpm > 4500) rpmColor = MX5_ORANGE;
    else if (telemetry.rpm > 3000) rpmColor = MX5_YELLOW;
    
    int fillWidth = (int)(barWidth * rpmPercent);
    if (fillWidth > 12) {
        LCD_FillRoundRect(barX, barY, fillWidth, barHeight, 6, rpmColor);
    } else if (fillWidth > 0) {
        LCD_FillRect(barX, barY, fillWidth, barHeight, rpmColor);
    }
    LCD_DrawRoundRect(barX, barY, barWidth, barHeight, 6, MX5_WHITE);
    
    // === SPEED DISPLAY (Below gear) ===
    int speedY = CENTER_Y + 35;
    char speedStr[8];
    snprintf(speedStr, sizeof(speedStr), "%d", (int)telemetry.speed);
    LCD_DrawString(CENTER_X - 24, speedY, speedStr, MX5_WHITE, COLOR_BG, 3);
    LCD_DrawString(CENTER_X - 18, speedY + 28, "MPH", MX5_GRAY, COLOR_BG, 1);
    
    // === STATUS ROW (Bottom) - with labels ===
    int statusY = CENTER_Y + 95;
    
    // Engine status
    uint16_t engineColor = telemetry.engineRunning ? MX5_GREEN : MX5_RED;
    LCD_FillCircle(CENTER_X - 80, statusY, 12, engineColor);
    LCD_DrawCircle(CENTER_X - 80, statusY, 12, MX5_WHITE);
    LCD_DrawString(CENTER_X - 92, statusY + 18, "ENG", MX5_GRAY, COLOR_BG, 1);
    
    // IMU status  
    uint16_t imuColor = imuAvailable ? MX5_GREEN : MX5_GRAY;
    LCD_FillCircle(CENTER_X, statusY, 12, imuColor);
    LCD_DrawCircle(CENTER_X, statusY, 12, MX5_WHITE);
    LCD_DrawString(CENTER_X - 9, statusY + 18, "IMU", MX5_GRAY, COLOR_BG, 1);
    
    // Connection status
    uint16_t connColor = telemetry.connected ? MX5_GREEN : MX5_ORANGE;
    LCD_FillCircle(CENTER_X + 80, statusY, 12, connColor);
    LCD_DrawCircle(CENTER_X + 80, statusY, 12, MX5_WHITE);
    LCD_DrawString(CENTER_X + 68, statusY + 18, "COM", MX5_GRAY, COLOR_BG, 1);
    
    // === FUEL GAUGE (Left side with tank icon) ===
    int fuelX = 55;
    int fuelY = CENTER_Y - 10;
    int fuelBarH = 60;
    int fuelBarW = 22;
    
    // Fuel tank icon (simplified with rounded corners)
    LCD_FillRoundRect(fuelX - fuelBarW/2, fuelY, fuelBarW, fuelBarH, 6, MX5_DARKGRAY);
    uint16_t fuelColor = MX5_YELLOW;
    if (telemetry.fuelLevel < 15) fuelColor = MX5_RED;
    else if (telemetry.fuelLevel < 25) fuelColor = MX5_ORANGE;
    int fuelFill = (int)(fuelBarH * telemetry.fuelLevel / 100.0);
    if (fuelFill > 12) {
        LCD_FillRoundRect(fuelX - fuelBarW/2, fuelY + fuelBarH - fuelFill, fuelBarW, fuelFill, 6, fuelColor);
    } else if (fuelFill > 0) {
        LCD_FillRect(fuelX - fuelBarW/2, fuelY + fuelBarH - fuelFill, fuelBarW, fuelFill, fuelColor);
    }
    LCD_DrawRoundRect(fuelX - fuelBarW/2, fuelY, fuelBarW, fuelBarH, 6, MX5_WHITE);
    // Tank cap (rounded)
    LCD_FillRoundRect(fuelX - 5, fuelY - 7, 10, 7, 3, MX5_GRAY);
    LCD_DrawString(fuelX - 12, fuelY + fuelBarH + 5, "FUEL", MX5_GRAY, COLOR_BG, 1);
    
    // === TEMP GAUGES (Right side) ===
    int tempX = SCREEN_WIDTH - 55;
    int tempY = CENTER_Y - 20;
    int tempBarW = 20;
    int tempBarH = 45;
    
    // Coolant temp bar
    uint16_t coolCol = MX5_BLUE;
    if (telemetry.coolantTemp > 220) coolCol = MX5_RED;
    else if (telemetry.coolantTemp > 200) coolCol = MX5_ORANGE;
    LCD_FillRoundRect(tempX - 24, tempY, tempBarW, tempBarH, 5, MX5_DARKGRAY);
    float coolPct = constrain((telemetry.coolantTemp - 120) / 120.0, 0, 1);
    int coolFill = (int)(tempBarH * coolPct);
    if (coolFill > 10) {
        LCD_FillRoundRect(tempX - 24, tempY + tempBarH - coolFill, tempBarW, coolFill, 5, coolCol);
    } else if (coolFill > 0) {
        LCD_FillRect(tempX - 24, tempY + tempBarH - coolFill, tempBarW, coolFill, coolCol);
    }
    LCD_DrawRoundRect(tempX - 24, tempY, tempBarW, tempBarH, 5, MX5_WHITE);
    LCD_DrawString(tempX - 24, tempY + tempBarH + 5, "H2O", MX5_GRAY, COLOR_BG, 1);
    
    // Oil temp bar
    uint16_t oilCol = MX5_ORANGE;
    if (telemetry.oilTemp > 250) oilCol = MX5_RED;
    LCD_FillRoundRect(tempX + 4, tempY, tempBarW, tempBarH, 5, MX5_DARKGRAY);
    float oilPct = constrain((telemetry.oilTemp - 150) / 130.0, 0, 1);
    int oilFill = (int)(tempBarH * oilPct);
    if (oilFill > 10) {
        LCD_FillRoundRect(tempX + 4, tempY + tempBarH - oilFill, tempBarW, oilFill, 5, oilCol);
    } else if (oilFill > 0) {
        LCD_FillRect(tempX + 4, tempY + tempBarH - oilFill, tempBarW, oilFill, oilCol);
    }
    LCD_DrawRoundRect(tempX + 4, tempY, tempBarW, tempBarH, 5, MX5_WHITE);
    LCD_DrawString(tempX + 6, tempY + tempBarH + 5, "OIL", MX5_GRAY, COLOR_BG, 1);
    
    drawPageIndicator();
}

void drawRPMScreen() {
    // Only draw on full redraw to prevent flickering overlaps
    if (!needsFullRedraw) return;
    
    drawBackground();
    
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
    
    // Draw continuous arc segments
    int numSegments = 20;
    for (int i = 0; i < numSegments; i++) {
        float segStart = i / (float)numSegments;
        float segEnd = (i + 1) / (float)numSegments;
        
        // Determine segment color
        uint16_t segColor = MX5_DARKGRAY;
        if (segStart < rpmPercent) {
            float rpmAt = segStart * 8000;
            if (rpmAt >= 6400) segColor = MX5_RED;
            else if (rpmAt >= 5600) segColor = MX5_ORANGE;
            else if (rpmAt >= 4000) segColor = MX5_YELLOW;
            else segColor = MX5_GREEN;
        }
        
        // Arc from -150° to +150° (300° total, open at top)
        float startAngle = (120 + i * 15) * PI / 180.0;  // Start from bottom-left
        float endAngle = (120 + (i + 1) * 15) * PI / 180.0;
        
        // Draw thick arc segment
        for (float a = startAngle; a < endAngle; a += 0.02) {
            int px = CENTER_X + cos(a) * gaugeRadius;
            int py = gaugeY + sin(a) * gaugeRadius;
            LCD_FillCircle(px, py, 8, segColor);
        }
    }
    
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
    LCD_DrawString(CENTER_X - rpmLen * 10, gaugeY - 8, rpmStr, MX5_WHITE, COLOR_BG, 3);
    LCD_DrawString(CENTER_X - 12, gaugeY + 22, "RPM", MX5_GRAY, COLOR_BG, 1);
    
    // === SPEED (Bottom) ===
    int speedY = SCREEN_HEIGHT - 70;
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
    auto getTireColor = [](float psi) -> uint16_t {
        if (psi < 26) return MX5_RED;      // Dangerously low
        if (psi < 28) return MX5_ORANGE;   // Low warning
        if (psi > 36) return MX5_ORANGE;   // High warning
        if (psi > 38) return MX5_RED;      // Dangerously high
        return MX5_GREEN;                   // Normal 28-36 PSI
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
    
    // === PRESSURE VALUE LABELS ===
    char psiStr[8];
    
    // Front Left
    snprintf(psiStr, sizeof(psiStr), "%.0f", telemetry.tirePressure[0]);
    LCD_DrawString(flX - 42, flY + 8, psiStr, flColor, COLOR_BG, 2);
    LCD_DrawString(flX - 42, flY + 26, "PSI", MX5_GRAY, COLOR_BG, 1);
    LCD_DrawString(flX - 18, flY - 14, "FL", MX5_GRAY, COLOR_BG, 1);
    
    // Front Right
    snprintf(psiStr, sizeof(psiStr), "%.0f", telemetry.tirePressure[1]);
    LCD_DrawString(frX + tireW + 8, frY + 8, psiStr, frColor, COLOR_BG, 2);
    LCD_DrawString(frX + tireW + 8, frY + 26, "PSI", MX5_GRAY, COLOR_BG, 1);
    LCD_DrawString(frX + 6, frY - 14, "FR", MX5_GRAY, COLOR_BG, 1);
    
    // Rear Left
    snprintf(psiStr, sizeof(psiStr), "%.0f", telemetry.tirePressure[2]);
    LCD_DrawString(rlX - 42, rlY + 8, psiStr, rlColor, COLOR_BG, 2);
    LCD_DrawString(rlX - 42, rlY + 26, "PSI", MX5_GRAY, COLOR_BG, 1);
    LCD_DrawString(rlX - 18, rlY + tireH + 4, "RL", MX5_GRAY, COLOR_BG, 1);
    
    // Rear Right
    snprintf(psiStr, sizeof(psiStr), "%.0f", telemetry.tirePressure[3]);
    LCD_DrawString(rrX + tireW + 8, rrY + 8, psiStr, rrColor, COLOR_BG, 2);
    LCD_DrawString(rrX + tireW + 8, rrY + 26, "PSI", MX5_GRAY, COLOR_BG, 1);
    LCD_DrawString(rrX + 6, rrY + tireH + 4, "RR", MX5_GRAY, COLOR_BG, 1);
    
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
    
    // === VOLTAGE (Bottom Right) ===
    uint16_t voltColor = MX5_GREEN;
    if (telemetry.voltage < 12.0) voltColor = MX5_RED;
    else if (telemetry.voltage < 12.8) voltColor = MX5_ORANGE;
    else if (telemetry.voltage > 15.0) voltColor = MX5_RED;
    
    LCD_FillRoundRect(rightX, bottomY, cardW, cardH, CARD_RADIUS, COLOR_BG_CARD);
    LCD_DrawRoundRect(rightX, bottomY, cardW, cardH, CARD_RADIUS, voltColor);
    
    // Label
    LCD_DrawString(rightX + 10, bottomY + 8, "BATTERY", MX5_GRAY, COLOR_BG_CARD, 1);
    
    // Voltage value
    char voltStr[12];
    snprintf(voltStr, sizeof(voltStr), "%.1fV", telemetry.voltage);
    LCD_DrawString(rightX + 10, bottomY + 24, voltStr, voltColor, COLOR_BG_CARD, 2);
    
    // Progress bar (rounded)
    float voltPct = constrain((telemetry.voltage - 11.0) / 4.0, 0, 1);
    LCD_FillRoundRect(rightX + 10, bottomY + cardH - 20, cardW - 20, 12, 4, MX5_DARKGRAY);
    int voltFillW = (int)((cardW - 20) * voltPct);
    if (voltFillW > 8) {
        LCD_FillRoundRect(rightX + 10, bottomY + cardH - 20, voltFillW, 12, 4, voltColor);
    }
    
    drawPageIndicator();
}

void drawGForceScreen() {
    // Static variables to track previous ball position for partial redraw
    static int prevGX = CENTER_X;
    static int prevGY = CENTER_Y;
    
    // Calculate G-force dot position (1.5G = full radius)
    float maxG = 1.5;
    int maxRadius = 120;
    int gX = CENTER_X + (int)(telemetry.gForceX / maxG * maxRadius);
    int gY = CENTER_Y - (int)(telemetry.gForceY / maxG * maxRadius);  // Y inverted
    
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
    
    if (needsFullRedraw) {
        // Full redraw - draw everything
        drawBackground();
        
        // === TITLE ===
        LCD_DrawString(CENTER_X - 42, 20, "G-FORCE", MX5_WHITE, COLOR_BG, 2);
        
        // Draw grid circles for G reference with labels
        for (int g = 1; g <= 3; g++) {
            int radius = g * 40;
            LCD_DrawCircle(CENTER_X, CENTER_Y, radius, MX5_DARKGRAY);
        }
        
        // Draw crosshairs
        LCD_DrawLine(CENTER_X - 130, CENTER_Y, CENTER_X + 130, CENTER_Y, MX5_DARKGRAY);
        LCD_DrawLine(CENTER_X, CENTER_Y - 130, CENTER_X, CENTER_Y + 130, MX5_DARKGRAY);
        
        // Axis labels
        LCD_DrawString(CENTER_X - 6, CENTER_Y - 145, "ACC", MX5_GREEN, COLOR_BG, 1);
        LCD_DrawString(CENTER_X - 6, CENTER_Y + 135, "BRK", MX5_RED, COLOR_BG, 1);
        LCD_DrawString(CENTER_X - 145, CENTER_Y - 4, "L", MX5_CYAN, COLOR_BG, 1);
        LCD_DrawString(CENTER_X + 138, CENTER_Y - 4, "R", MX5_CYAN, COLOR_BG, 1);
        
        // G-force ring labels
        LCD_DrawString(CENTER_X + 42, CENTER_Y - 6, "1G", MX5_GRAY, COLOR_BG, 1);
        LCD_DrawString(CENTER_X + 82, CENTER_Y - 6, "2G", MX5_GRAY, COLOR_BG, 1);
        
        // Fixed center reference point
        LCD_FillCircle(CENTER_X, CENTER_Y, 3, MX5_WHITE);
        
        drawPageIndicator();
        
        // Reset previous position on full redraw
        prevGX = CENTER_X;
        prevGY = CENTER_Y;
    } else {
        // Partial redraw - only update the moving ball and values
        
        // Erase old ball position by filling with background color
        LCD_FillCircle(prevGX, prevGY, 16, COLOR_BG);
        
        // Redraw any grid elements that might have been covered by the old ball
        // Check if old position was near crosshairs or circles
        if (abs(prevGY - CENTER_Y) < 20) {
            // Redraw horizontal crosshair segment near old position
            int lineStart = max(CENTER_X - 130, prevGX - 20);
            int lineEnd = min(CENTER_X + 130, prevGX + 20);
            LCD_DrawLine(lineStart, CENTER_Y, lineEnd, CENTER_Y, MX5_DARKGRAY);
        }
        if (abs(prevGX - CENTER_X) < 20) {
            // Redraw vertical crosshair segment near old position
            int lineStart = max(CENTER_Y - 130, prevGY - 20);
            int lineEnd = min(CENTER_Y + 130, prevGY + 20);
            LCD_DrawLine(CENTER_X, lineStart, CENTER_X, lineEnd, MX5_DARKGRAY);
        }
        
        // Redraw any grid circles that might have been affected
        for (int g = 1; g <= 3; g++) {
            int radius = g * 40;
            float prevDist = sqrt(pow(prevGX - CENTER_X, 2) + pow(prevGY - CENTER_Y, 2));
            if (abs(prevDist - radius) < 20) {
                LCD_DrawCircle(CENTER_X, CENTER_Y, radius, MX5_DARKGRAY);
            }
        }
        
        // Redraw center reference if it was covered
        if (abs(prevGX - CENTER_X) < 20 && abs(prevGY - CENTER_Y) < 20) {
            LCD_FillCircle(CENTER_X, CENTER_Y, 3, MX5_WHITE);
        }
    }
    
    // Draw G-force indicator at new position
    LCD_FillCircle(gX, gY, 14, dotColor);
    LCD_DrawCircle(gX, gY, 14, MX5_WHITE);
    LCD_DrawCircle(gX, gY, 15, MX5_WHITE);
    
    // Save current position for next partial redraw
    prevGX = gX;
    prevGY = gY;
    
    // === G VALUES DISPLAY (Bottom) - always update ===
    int infoY = SCREEN_HEIGHT - 60;
    LCD_FillRoundRect(CENTER_X - 90, infoY, 180, 40, 10, COLOR_BG_CARD);
    LCD_DrawRoundRect(CENTER_X - 90, infoY, 180, 40, 10, MX5_ACCENT);
    
    // Show current G values
    char gStr[16];
    snprintf(gStr, sizeof(gStr), "LAT: %.2fG", telemetry.gForceX);
    LCD_DrawString(CENTER_X - 80, infoY + 6, gStr, MX5_CYAN, COLOR_BG_CARD, 1);
    
    snprintf(gStr, sizeof(gStr), "LON: %.2fG", telemetry.gForceY);
    LCD_DrawString(CENTER_X - 80, infoY + 22, gStr, (telemetry.gForceY > 0) ? MX5_GREEN : MX5_RED, COLOR_BG_CARD, 1);
    
    snprintf(gStr, sizeof(gStr), "%.2fG", totalG);
    LCD_DrawString(CENTER_X + 40, infoY + 12, gStr, dotColor, COLOR_BG_CARD, 2);
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
        
        // Item background card (rounded)
        LCD_FillRoundRect(startX, y, itemW, itemH, CARD_RADIUS, COLOR_BG_CARD);
        
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
        
        // TEXT LABEL - draw the item name
        LCD_DrawString(startX + 50, y + 12, items[i].name, MX5_WHITE, COLOR_BG_CARD, 2);
        
        // Status text (OK or WARN)
        const char* statusText = items[i].isWarning ? "WARN" : "OK";
        LCD_DrawString(startX + 50, y + itemH - 20, statusText, statusColor, COLOR_BG_CARD, 1);
        
        // Status circle on right
        int circleX = startX + itemW - 25;
        int circleY = y + itemH/2;
        LCD_FillCircle(circleX, circleY, 12, statusColor);
        LCD_DrawCircle(circleX, circleY, 12, MX5_WHITE);
        
        // Inner indicator
        if (!items[i].isWarning) {
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
    LCD_FillRoundRect(startX, startY, itemW, itemH, CARD_RADIUS, COLOR_BG_CARD);
    LCD_DrawRoundRect(startX, startY, itemW, itemH, CARD_RADIUS, MX5_YELLOW);
    
    // Sun icon
    int iconX = startX + 30;
    int iconY = startY + 18;
    LCD_FillCircle(iconX, iconY, 8, MX5_YELLOW);
    for (int r = 0; r < 8; r++) {
        float angle = r * 3.14159 / 4;
        int x1 = iconX + cos(angle) * 11;
        int y1 = iconY + sin(angle) * 11;
        int x2 = iconX + cos(angle) * 15;
        int y2 = iconY + sin(angle) * 15;
        LCD_DrawLine(x1, y1, x2, y2, MX5_YELLOW);
    }
    
    // Text label
    LCD_DrawString(startX + 55, startY + 8, "BRIGHTNESS", MX5_WHITE, COLOR_BG_CARD, 2);
    
    // Slider bar (rounded)
    int sliderX = startX + 55;
    int sliderW = 180;
    int sliderY = startY + 40;
    LCD_FillRoundRect(sliderX, sliderY - 4, sliderW, 8, 4, MX5_DARKGRAY);
    LCD_FillRoundRect(sliderX, sliderY - 4, (int)(sliderW * 0.75), 8, 4, MX5_YELLOW);
    LCD_FillCircle(sliderX + (int)(sliderW * 0.75), sliderY, 7, MX5_WHITE);
    LCD_DrawString(startX + itemW - 40, startY + 32, "75%", MX5_YELLOW, COLOR_BG_CARD, 1);
    
    startY += itemH + itemGap;
    
    // === UNITS (toggle) ===
    LCD_FillRoundRect(startX, startY, itemW, itemH, CARD_RADIUS, COLOR_BG_CARD);
    LCD_DrawRoundRect(startX, startY, itemW, itemH, CARD_RADIUS, MX5_ACCENT);
    
    // Speed icon
    iconX = startX + 30;
    iconY = startY + itemH/2;
    LCD_DrawCircle(iconX, iconY, 10, MX5_ACCENT);
    LCD_DrawLine(iconX, iconY, iconX + 6, iconY - 6, MX5_ACCENT);
    LCD_DrawLine(iconX, iconY, iconX + 7, iconY - 5, MX5_ACCENT);
    
    // Text label
    LCD_DrawString(startX + 55, startY + 10, "SPEED UNITS", MX5_WHITE, COLOR_BG_CARD, 2);
    LCD_DrawString(startX + 55, startY + 32, "MPH", MX5_ACCENT, COLOR_BG_CARD, 1);
    
    // Toggle switch (ON position for MPH) - rounded
    int toggleX = startX + itemW - 70;
    int toggleW = 50;
    int toggleH = 24;
    LCD_FillRoundRect(toggleX, iconY - toggleH/2, toggleW, toggleH, 12, MX5_GREEN);
    LCD_DrawRoundRect(toggleX, iconY - toggleH/2, toggleW, toggleH, 12, MX5_WHITE);
    LCD_FillCircle(toggleX + toggleW - 12, iconY, 9, MX5_WHITE);
    
    startY += itemH + itemGap;
    
    // === SHIFT LIGHT RPM (with value) ===
    LCD_FillRoundRect(startX, startY, itemW, itemH, CARD_RADIUS, COLOR_BG_CARD);
    LCD_DrawRoundRect(startX, startY, itemW, itemH, CARD_RADIUS, MX5_RED);
    
    // Warning light icon
    iconX = startX + 30;
    iconY = startY + itemH/2;
    LCD_FillCircle(iconX, iconY, 10, MX5_RED);
    LCD_FillCircle(iconX, iconY, 6, COLOR_BG_CARD);
    LCD_FillCircle(iconX, iconY, 3, MX5_RED);
    
    // Text label
    LCD_DrawString(startX + 55, startY + 10, "SHIFT LIGHT", MX5_WHITE, COLOR_BG_CARD, 2);
    LCD_DrawString(startX + 55, startY + 32, "Redline Alert", MX5_RED, COLOR_BG_CARD, 1);
    
    // RPM value
    int valueX = startX + itemW - 70;
    LCD_DrawString(valueX, startY + 18, "6500", MX5_WHITE, COLOR_BG_CARD, 2);
    
    startY += itemH + itemGap;
    
    // === SCREEN TIMEOUT (with value) ===
    LCD_FillRoundRect(startX, startY, itemW, itemH, CARD_RADIUS, COLOR_BG_CARD);
    LCD_DrawRoundRect(startX, startY, itemW, itemH, CARD_RADIUS, MX5_CYAN);
    
    // Timer/clock icon
    iconX = startX + 30;
    iconY = startY + itemH/2;
    LCD_DrawCircle(iconX, iconY, 10, MX5_CYAN);
    LCD_DrawCircle(iconX, iconY, 11, MX5_CYAN);
    LCD_DrawLine(iconX, iconY - 7, iconX, iconY, MX5_CYAN);
    LCD_DrawLine(iconX, iconY, iconX + 5, iconY, MX5_CYAN);
    LCD_FillRect(iconX - 2, iconY - 14, 4, 4, MX5_CYAN);  // Top knob
    
    // Text label
    LCD_DrawString(startX + 55, startY + 10, "TIMEOUT", MX5_WHITE, COLOR_BG_CARD, 2);
    LCD_DrawString(startX + 55, startY + 32, "Screen Dim", MX5_CYAN, COLOR_BG_CARD, 1);
    
    // Timeout value
    valueX = startX + itemW - 70;
    LCD_DrawString(valueX, startY + 18, "30s", MX5_WHITE, COLOR_BG_CARD, 2);
    
    startY += itemH + itemGap;
    
    // === DEMO MODE (toggle) ===
    LCD_FillRoundRect(startX, startY, itemW, itemH, CARD_RADIUS, COLOR_BG_CARD);
    LCD_DrawRoundRect(startX, startY, itemW, itemH, CARD_RADIUS, MX5_PURPLE);
    
    // Play/demo icon (rounded square)
    iconX = startX + 30;
    iconY = startY + itemH/2;
    LCD_FillRoundRect(iconX - 10, iconY - 10, 20, 20, 4, MX5_PURPLE);
    // Play triangle inside
    LCD_DrawLine(iconX - 4, iconY - 6, iconX - 4, iconY + 6, COLOR_BG_CARD);
    LCD_DrawLine(iconX - 4, iconY - 6, iconX + 6, iconY, COLOR_BG_CARD);
    LCD_DrawLine(iconX - 4, iconY + 6, iconX + 6, iconY, COLOR_BG_CARD);
    
    // Text label
    LCD_DrawString(startX + 55, startY + 10, "DEMO MODE", MX5_WHITE, COLOR_BG_CARD, 2);
    LCD_DrawString(startX + 55, startY + 32, "Simulate Data", MX5_PURPLE, COLOR_BG_CARD, 1);
    
    // Toggle switch (OFF position) - rounded
    int toggleX2 = startX + itemW - 70;
    LCD_FillRoundRect(toggleX2, iconY - toggleH/2, toggleW, toggleH, 12, MX5_DARKGRAY);
    LCD_DrawRoundRect(toggleX2, iconY - toggleH/2, toggleW, toggleH, 12, MX5_GRAY);
    LCD_FillCircle(toggleX2 + 12, iconY, 9, MX5_WHITE);
    LCD_DrawString(startX + itemW - 45, startY + 18, "OFF", MX5_GRAY, COLOR_BG_CARD, 1);
    
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
