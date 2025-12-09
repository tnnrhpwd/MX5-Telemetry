/**
 * @file ui_manager.h
 * @brief UI Manager for ESP32-S3 Round Display
 * 
 * Manages screen transitions, rendering, and user input.
 */

#ifndef UI_MANAGER_H
#define UI_MANAGER_H

#include "ui_screens.h"
#include "swc_handler.h"

class UIManager {
public:
    UIManager();
    
    // Initialize UI
    void begin();
    
    // Update UI (call every loop)
    void update();
    
    // Handle button input
    void handleButton(ButtonEvent button);
    
    // Update telemetry data
    void updateTelemetry(const TelemetryData& data);
    
    // Get current screen
    ScreenID getCurrentScreen();
    
    // Set screen directly
    void setScreen(ScreenID screen);
    
    // Toggle sleep mode
    void toggleSleep();
    
    // Check if sleeping
    bool isSleeping();
    
    // Get settings
    UISettings* getSettings();
    
private:
    ScreenID currentScreen;
    ScreenID previousScreen;
    TelemetryData telemetry;
    UISettings settings;
    bool sleeping;
    int menuSelection;
    bool inEditMode;
    
    // Screen rendering functions
    void renderScreen();
    void renderRPMGauge();
    void renderSpeedometer();
    void renderTPMS();
    void renderEngineTemps();
    void renderGForce();
    void renderSettings();
    void renderSleepScreen();
    
    // Helper functions
    void drawGaugeArc(int cx, int cy, int radius, int thickness, 
                      float startAngle, float endAngle, uint16_t color);
    void drawCenteredText(const char* text, int y, uint16_t color, int size);
    uint16_t getRPMColor(uint16_t rpm);
    float rpmToAngle(uint16_t rpm);
    
    // Navigation helpers
    void nextScreen();
    void prevScreen();
    void menuUp();
    void menuDown();
    void menuSelect();
    void menuBack();
    void adjustValue(int delta);
};

#endif // UI_MANAGER_H
