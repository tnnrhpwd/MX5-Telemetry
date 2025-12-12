/*
 * MX5 Telemetry Display - ESP32-S3 Round LCD
 * Waveshare ESP32-S3-Touch-LCD-1.85 (360x360)
 * 
 * This display shows real-time telemetry data from the Raspberry Pi
 * connected via serial communication.
 */

#include <Arduino.h>
#include "Display_ST77916.h"
#include "Touch_CST816.h"

// Screen dimensions
#define SCREEN_WIDTH  360
#define SCREEN_HEIGHT 360
#define CENTER_X      (SCREEN_WIDTH / 2)
#define CENTER_Y      (SCREEN_HEIGHT / 2)

// Colors for MX5 theme
#define MX5_RED       RGB565(200, 0, 0)
#define MX5_ORANGE    RGB565(255, 140, 0)
#define MX5_YELLOW    RGB565(255, 220, 0)
#define MX5_GREEN     RGB565(0, 180, 0)
#define MX5_BLUE      RGB565(0, 100, 200)
#define MX5_WHITE     COLOR_WHITE
#define MX5_BLACK     COLOR_BLACK
#define MX5_GRAY      RGB565(60, 60, 60)
#define MX5_DARKGRAY  RGB565(30, 30, 30)

// Telemetry data structure
struct TelemetryData {
    float rpm;
    float speed;
    int gear;
    float coolantTemp;
    float oilTemp;
    float fuelLevel;
    float voltage;
    float tirePressure[4];  // FL, FR, RL, RR
    float gForceX;
    float gForceY;
    bool engineRunning;
    bool connected;
};

TelemetryData telemetry = {0};

// Display state
enum ScreenMode {
    SCREEN_OVERVIEW,
    SCREEN_RPM,
    SCREEN_TPMS,
    SCREEN_ENGINE,
    SCREEN_GFORCE,
    SCREEN_COUNT
};

ScreenMode currentScreen = SCREEN_OVERVIEW;
unsigned long lastUpdate = 0;
unsigned long lastTouchTime = 0;
bool needsRedraw = true;

// Function prototypes
void drawOverviewScreen();
void drawRPMScreen();
void drawTPMSScreen();
void drawEngineScreen();
void drawGForceScreen();
void handleTouch();
void updateTelemetry();

void setup() {
    Serial.begin(115200);
    delay(100);
    
    Serial.println("MX5 Telemetry Display Starting...");
    Serial.println("Initializing LCD...");
    
    // Initialize display and touch
    LCD_Init();
    
    Serial.println("Display initialized!");
    
    // Draw startup screen
    LCD_Clear(MX5_BLACK);
    LCD_FillCircle(CENTER_X, CENTER_Y, 150, MX5_DARKGRAY);
    LCD_FillCircle(CENTER_X, CENTER_Y, 140, MX5_BLACK);
    
    // Draw MX5 logo placeholder
    LCD_FillCircle(CENTER_X, CENTER_Y - 30, 40, MX5_RED);
    
    delay(1000);
    
    // Set demo values for testing
    telemetry.rpm = 3500;
    telemetry.speed = 65;
    telemetry.gear = 3;
    telemetry.coolantTemp = 85;
    telemetry.oilTemp = 95;
    telemetry.fuelLevel = 75;
    telemetry.voltage = 14.2;
    telemetry.tirePressure[0] = 32;
    telemetry.tirePressure[1] = 32;
    telemetry.tirePressure[2] = 30;
    telemetry.tirePressure[3] = 30;
    telemetry.gForceX = 0.2;
    telemetry.gForceY = -0.1;
    telemetry.engineRunning = true;
    telemetry.connected = true;
    
    needsRedraw = true;
    Serial.println("Setup complete!");
}

void loop() {
    // Handle touch input
    Touch_Loop();
    handleTouch();
    
    // Static display test - only redraw once every 2 seconds
    // This helps verify if the display hardware works without animation tearing
    static bool initialDrawDone = false;
    if (!initialDrawDone) {
        // Draw a simple static test pattern
        LCD_Clear(COLOR_BLACK);
        
        // Draw colored quadrants to verify colors
        LCD_FillRect(0, 0, 180, 180, RGB565(255, 0, 0));      // Red - top left
        LCD_FillRect(180, 0, 180, 180, RGB565(0, 255, 0));    // Green - top right  
        LCD_FillRect(0, 180, 180, 180, RGB565(0, 0, 255));    // Blue - bottom left
        LCD_FillRect(180, 180, 180, 180, RGB565(255, 255, 0)); // Yellow - bottom right
        
        // Draw center circle
        LCD_FillCircle(180, 180, 80, COLOR_WHITE);
        LCD_FillCircle(180, 180, 60, COLOR_BLACK);
        
        Serial.println("Static test pattern drawn");
        initialDrawDone = true;
        
        delay(3000);  // Show test pattern for 3 seconds
    }
    
    // After test, update display slowly (every 500ms)
    if (millis() - lastUpdate > 500) {
        lastUpdate = millis();
        
        // Slow demo animation
        static float rpmDir = 50;
        telemetry.rpm += rpmDir;
        if (telemetry.rpm > 7000) rpmDir = -50;
        if (telemetry.rpm < 1000) rpmDir = 50;
        
        telemetry.gForceX = sin(millis() / 1000.0) * 0.3;
        telemetry.gForceY = cos(millis() / 1500.0) * 0.2;
        
        needsRedraw = true;
    }
    
    // Redraw screen if needed
    if (needsRedraw) {
        needsRedraw = false;
        
        switch (currentScreen) {
            case SCREEN_OVERVIEW:
                drawOverviewScreen();
                break;
            case SCREEN_RPM:
                drawRPMScreen();
                break;
            case SCREEN_TPMS:
                drawTPMSScreen();
                break;
            case SCREEN_ENGINE:
                drawEngineScreen();
                break;
            case SCREEN_GFORCE:
                drawGForceScreen();
                break;
        }
    }
    
    delay(10);
}

void handleTouch() {
    if (touch_data.gesture != NONE && millis() - lastTouchTime > 300) {
        lastTouchTime = millis();
        
        switch (touch_data.gesture) {
            case SWIPE_LEFT:
                currentScreen = (ScreenMode)((currentScreen + 1) % SCREEN_COUNT);
                needsRedraw = true;
                LCD_Clear(MX5_BLACK);
                break;
            case SWIPE_RIGHT:
                currentScreen = (ScreenMode)((currentScreen - 1 + SCREEN_COUNT) % SCREEN_COUNT);
                needsRedraw = true;
                LCD_Clear(MX5_BLACK);
                break;
            case SINGLE_CLICK:
                // Toggle backlight or other action
                break;
            default:
                break;
        }
        
        // Clear gesture after handling
        touch_data.gesture = NONE;
    }
}

void drawOverviewScreen() {
    // Clear only the changing areas
    LCD_FillCircle(CENTER_X, CENTER_Y, 170, MX5_DARKGRAY);
    LCD_FillCircle(CENTER_X, CENTER_Y, 160, MX5_BLACK);
    
    // Draw outer ring
    LCD_DrawCircle(CENTER_X, CENTER_Y, 175, MX5_GRAY);
    
    // Gear indicator (center)
    char gearStr[4];
    if (telemetry.gear == 0) {
        strcpy(gearStr, "N");
    } else if (telemetry.gear == -1) {
        strcpy(gearStr, "R");
    } else {
        snprintf(gearStr, sizeof(gearStr), "%d", telemetry.gear);
    }
    
    // Draw large gear number
    LCD_FillCircle(CENTER_X, CENTER_Y - 20, 50, MX5_DARKGRAY);
    LCD_DrawCircle(CENTER_X, CENTER_Y - 20, 50, MX5_WHITE);
    
    // Speed (bottom center)
    LCD_FillRect(CENTER_X - 60, CENTER_Y + 50, 120, 40, MX5_BLACK);
    char speedStr[16];
    snprintf(speedStr, sizeof(speedStr), "%.0f", telemetry.speed);
    
    // RPM bar (top)
    uint16_t rpmBarWidth = (telemetry.rpm / 8000.0) * 200;
    uint16_t rpmColor = MX5_GREEN;
    if (telemetry.rpm > 6000) rpmColor = MX5_RED;
    else if (telemetry.rpm > 4500) rpmColor = MX5_ORANGE;
    else if (telemetry.rpm > 3000) rpmColor = MX5_YELLOW;
    
    LCD_FillRect(CENTER_X - 100, 30, 200, 15, MX5_DARKGRAY);
    LCD_FillRect(CENTER_X - 100, 30, rpmBarWidth, 15, rpmColor);
    LCD_DrawRect(CENTER_X - 100, 30, 200, 15, MX5_WHITE);
    
    // Status indicators (bottom)
    uint16_t engineColor = telemetry.engineRunning ? MX5_GREEN : MX5_RED;
    uint16_t connColor = telemetry.connected ? MX5_GREEN : MX5_RED;
    
    LCD_FillCircle(CENTER_X - 50, CENTER_Y + 120, 8, engineColor);
    LCD_FillCircle(CENTER_X + 50, CENTER_Y + 120, 8, connColor);
    
    // Page indicator dots
    for (int i = 0; i < SCREEN_COUNT; i++) {
        uint16_t dotColor = (i == currentScreen) ? MX5_WHITE : MX5_GRAY;
        LCD_FillCircle(CENTER_X - 40 + i * 20, SCREEN_HEIGHT - 20, 4, dotColor);
    }
}

void drawRPMScreen() {
    // RPM gauge screen
    LCD_FillCircle(CENTER_X, CENTER_Y, 170, MX5_DARKGRAY);
    LCD_FillCircle(CENTER_X, CENTER_Y, 160, MX5_BLACK);
    
    // Draw RPM arc gauge
    float rpmPercent = telemetry.rpm / 8000.0;
    uint16_t rpmColor = MX5_GREEN;
    if (telemetry.rpm > 6500) rpmColor = MX5_RED;
    else if (telemetry.rpm > 5000) rpmColor = MX5_ORANGE;
    else if (telemetry.rpm > 3500) rpmColor = MX5_YELLOW;
    
    // Draw gauge background arc
    for (int i = 0; i < 10; i++) {
        uint16_t segColor = (i < rpmPercent * 10) ? rpmColor : MX5_DARKGRAY;
        float angle1 = -135 + i * 27;
        float angle2 = -135 + (i + 1) * 27 - 2;
        
        // Simple arc segments as filled rectangles rotated
        float midAngle = (angle1 + angle2) / 2.0 * PI / 180.0;
        int px = CENTER_X + cos(midAngle) * 130;
        int py = CENTER_Y + sin(midAngle) * 130;
        LCD_FillCircle(px, py, 12, segColor);
    }
    
    // RPM number
    LCD_FillRect(CENTER_X - 50, CENTER_Y - 20, 100, 40, MX5_BLACK);
    char rpmStr[16];
    snprintf(rpmStr, sizeof(rpmStr), "%.0f", telemetry.rpm);
    
    // Page indicator
    for (int i = 0; i < SCREEN_COUNT; i++) {
        uint16_t dotColor = (i == currentScreen) ? MX5_WHITE : MX5_GRAY;
        LCD_FillCircle(CENTER_X - 40 + i * 20, SCREEN_HEIGHT - 20, 4, dotColor);
    }
}

void drawTPMSScreen() {
    // Tire pressure screen - car outline with 4 tires
    LCD_FillCircle(CENTER_X, CENTER_Y, 170, MX5_DARKGRAY);
    LCD_FillCircle(CENTER_X, CENTER_Y, 160, MX5_BLACK);
    
    // Draw car outline (simplified rectangle)
    LCD_DrawRect(CENTER_X - 40, CENTER_Y - 80, 80, 160, MX5_WHITE);
    
    // Draw tires
    const int tireW = 30, tireH = 50;
    const int tireOffsetX = 55, tireOffsetY = 50;
    
    // Front Left
    uint16_t flColor = (telemetry.tirePressure[0] < 28) ? MX5_RED : MX5_GREEN;
    LCD_FillRect(CENTER_X - tireOffsetX - tireW/2, CENTER_Y - tireOffsetY - tireH/2, tireW, tireH, flColor);
    
    // Front Right
    uint16_t frColor = (telemetry.tirePressure[1] < 28) ? MX5_RED : MX5_GREEN;
    LCD_FillRect(CENTER_X + tireOffsetX - tireW/2, CENTER_Y - tireOffsetY - tireH/2, tireW, tireH, frColor);
    
    // Rear Left
    uint16_t rlColor = (telemetry.tirePressure[2] < 28) ? MX5_RED : MX5_GREEN;
    LCD_FillRect(CENTER_X - tireOffsetX - tireW/2, CENTER_Y + tireOffsetY - tireH/2, tireW, tireH, rlColor);
    
    // Rear Right
    uint16_t rrColor = (telemetry.tirePressure[3] < 28) ? MX5_RED : MX5_GREEN;
    LCD_FillRect(CENTER_X + tireOffsetX - tireW/2, CENTER_Y + tireOffsetY - tireH/2, tireW, tireH, rrColor);
    
    // Page indicator
    for (int i = 0; i < SCREEN_COUNT; i++) {
        uint16_t dotColor = (i == currentScreen) ? MX5_WHITE : MX5_GRAY;
        LCD_FillCircle(CENTER_X - 40 + i * 20, SCREEN_HEIGHT - 20, 4, dotColor);
    }
}

void drawEngineScreen() {
    // Engine vitals - coolant, oil, fuel, voltage
    LCD_FillCircle(CENTER_X, CENTER_Y, 170, MX5_DARKGRAY);
    LCD_FillCircle(CENTER_X, CENTER_Y, 160, MX5_BLACK);
    
    // Coolant temp (top left)
    uint16_t coolantColor = (telemetry.coolantTemp > 100) ? MX5_RED : MX5_BLUE;
    LCD_FillRect(CENTER_X - 120, CENTER_Y - 80, 100, 60, MX5_DARKGRAY);
    LCD_DrawRect(CENTER_X - 120, CENTER_Y - 80, 100, 60, coolantColor);
    
    // Oil temp (top right)
    uint16_t oilColor = (telemetry.oilTemp > 120) ? MX5_RED : MX5_ORANGE;
    LCD_FillRect(CENTER_X + 20, CENTER_Y - 80, 100, 60, MX5_DARKGRAY);
    LCD_DrawRect(CENTER_X + 20, CENTER_Y - 80, 100, 60, oilColor);
    
    // Fuel (bottom left)
    uint16_t fuelColor = (telemetry.fuelLevel < 15) ? MX5_RED : MX5_YELLOW;
    LCD_FillRect(CENTER_X - 120, CENTER_Y + 20, 100, 60, MX5_DARKGRAY);
    LCD_DrawRect(CENTER_X - 120, CENTER_Y + 20, 100, 60, fuelColor);
    
    // Voltage (bottom right)
    uint16_t voltColor = (telemetry.voltage < 12.5) ? MX5_RED : MX5_GREEN;
    LCD_FillRect(CENTER_X + 20, CENTER_Y + 20, 100, 60, MX5_DARKGRAY);
    LCD_DrawRect(CENTER_X + 20, CENTER_Y + 20, 100, 60, voltColor);
    
    // Page indicator
    for (int i = 0; i < SCREEN_COUNT; i++) {
        uint16_t dotColor = (i == currentScreen) ? MX5_WHITE : MX5_GRAY;
        LCD_FillCircle(CENTER_X - 40 + i * 20, SCREEN_HEIGHT - 20, 4, dotColor);
    }
}

void drawGForceScreen() {
    // G-Force display with centered dot
    LCD_FillCircle(CENTER_X, CENTER_Y, 170, MX5_DARKGRAY);
    LCD_FillCircle(CENTER_X, CENTER_Y, 160, MX5_BLACK);
    
    // Draw grid
    LCD_DrawCircle(CENTER_X, CENTER_Y, 50, MX5_GRAY);
    LCD_DrawCircle(CENTER_X, CENTER_Y, 100, MX5_GRAY);
    LCD_DrawCircle(CENTER_X, CENTER_Y, 150, MX5_GRAY);
    
    // Draw crosshairs
    LCD_FillRect(CENTER_X - 150, CENTER_Y, 300, 1, MX5_GRAY);
    LCD_FillRect(CENTER_X, CENTER_Y - 150, 1, 300, MX5_GRAY);
    
    // Calculate G-force dot position (max 1.5G = full radius)
    int gX = CENTER_X + (telemetry.gForceX / 1.5) * 140;
    int gY = CENTER_Y + (telemetry.gForceY / 1.5) * 140;
    
    // Draw G-force indicator
    LCD_FillCircle(gX, gY, 15, MX5_RED);
    LCD_DrawCircle(gX, gY, 15, MX5_WHITE);
    
    // Page indicator
    for (int i = 0; i < SCREEN_COUNT; i++) {
        uint16_t dotColor = (i == currentScreen) ? MX5_WHITE : MX5_GRAY;
        LCD_FillCircle(CENTER_X - 40 + i * 20, SCREEN_HEIGHT - 20, 4, dotColor);
    }
}
