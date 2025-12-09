/**
 * @file ui_manager.cpp
 * @brief UI Manager implementation for ESP32-S3 Round Display
 */

#include "ui_manager.h"
#include <math.h>

// Note: In actual ESP32 code, you would include your graphics library:
// #include <TFT_eSPI.h>
// extern TFT_eSPI tft;

UIManager::UIManager() {
    currentScreen = SCREEN_RPM_GAUGE;
    previousScreen = SCREEN_RPM_GAUGE;
    sleeping = false;
    menuSelection = 0;
    inEditMode = false;
    
    // Default settings
    settings.brightness = 80;
    settings.shift_rpm = 6500;
    settings.redline_rpm = 7200;
    settings.use_mph = true;
    
    // Initialize telemetry with zeros
    memset(&telemetry, 0, sizeof(TelemetryData));
}

void UIManager::begin() {
    // Initialize display here
    // tft.init();
    // tft.setRotation(0);
    // tft.fillScreen(COLOR_BLACK);
    
    renderScreen();
}

void UIManager::update() {
    if (!sleeping) {
        renderScreen();
    }
}

void UIManager::handleButton(ButtonEvent button) {
    if (button == BTN_NONE) return;
    
    // MUTE always toggles sleep
    if (button == BTN_MUTE) {
        toggleSleep();
        return;
    }
    
    // Wake from sleep on any button
    if (sleeping) {
        sleeping = false;
        return;
    }
    
    // Handle based on current screen
    switch (currentScreen) {
        case SCREEN_SETTINGS:
            handleSettingsInput(button);
            break;
            
        default:
            // Normal screen navigation
            switch (button) {
                case BTN_MODE:
                    nextScreen();
                    break;
                case BTN_SEEK_UP:
                    nextScreen();
                    break;
                case BTN_SEEK_DOWN:
                    prevScreen();
                    break;
                case BTN_ON_OFF:
                    // Could show detail view
                    break;
                case BTN_CANCEL:
                    prevScreen();
                    break;
                case BTN_RES_PLUS:
                case BTN_SET_MINUS:
                    // Direct jump to settings
                    if (button == BTN_SET_MINUS && currentScreen != SCREEN_SETTINGS) {
                        previousScreen = currentScreen;
                        currentScreen = SCREEN_SETTINGS;
                        menuSelection = 0;
                    }
                    break;
                default:
                    break;
            }
            break;
    }
}

void UIManager::handleSettingsInput(ButtonEvent button) {
    switch (button) {
        case BTN_RES_PLUS:
            if (inEditMode) {
                adjustValue(1);
            } else {
                menuUp();
            }
            break;
            
        case BTN_SET_MINUS:
            if (inEditMode) {
                adjustValue(-1);
            } else {
                menuDown();
            }
            break;
            
        case BTN_VOL_UP:
            adjustValue(1);
            break;
            
        case BTN_VOL_DOWN:
            adjustValue(-1);
            break;
            
        case BTN_ON_OFF:
            if (menuSelection == SETTING_BACK) {
                menuBack();
            } else {
                inEditMode = !inEditMode;
            }
            break;
            
        case BTN_CANCEL:
            if (inEditMode) {
                inEditMode = false;
            } else {
                menuBack();
            }
            break;
            
        case BTN_MODE:
            menuBack();
            nextScreen();
            break;
            
        default:
            break;
    }
}

void UIManager::updateTelemetry(const TelemetryData& data) {
    memcpy(&telemetry, &data, sizeof(TelemetryData));
}

ScreenID UIManager::getCurrentScreen() {
    return currentScreen;
}

void UIManager::setScreen(ScreenID screen) {
    if (screen < SCREEN_COUNT) {
        previousScreen = currentScreen;
        currentScreen = screen;
    }
}

void UIManager::toggleSleep() {
    sleeping = !sleeping;
    if (sleeping) {
        renderSleepScreen();
    }
}

bool UIManager::isSleeping() {
    return sleeping;
}

UISettings* UIManager::getSettings() {
    return &settings;
}

void UIManager::renderScreen() {
    switch (currentScreen) {
        case SCREEN_RPM_GAUGE:
            renderRPMGauge();
            break;
        case SCREEN_SPEEDOMETER:
            renderSpeedometer();
            break;
        case SCREEN_TPMS:
            renderTPMS();
            break;
        case SCREEN_ENGINE_TEMPS:
            renderEngineTemps();
            break;
        case SCREEN_GFORCE:
            renderGForce();
            break;
        case SCREEN_SETTINGS:
            renderSettings();
            break;
    }
}

void UIManager::renderRPMGauge() {
    // Clear screen
    // tft.fillScreen(COLOR_BLACK);
    
    // Draw gauge background arc
    // drawGaugeArc(DISPLAY_CENTER_X, DISPLAY_CENTER_Y, GAUGE_RADIUS, 
    //              GAUGE_THICKNESS, 135, 405, COLOR_DARK_GRAY);
    
    // Calculate RPM arc
    float rpmAngle = rpmToAngle(telemetry.rpm);
    uint16_t rpmColor = getRPMColor(telemetry.rpm);
    
    // Draw RPM arc
    // drawGaugeArc(DISPLAY_CENTER_X, DISPLAY_CENTER_Y, GAUGE_RADIUS,
    //              GAUGE_THICKNESS, 135, 135 + rpmAngle, rpmColor);
    
    // Draw center circle with RPM text
    // tft.fillCircle(DISPLAY_CENTER_X, DISPLAY_CENTER_Y, CENTER_CIRCLE_R, COLOR_DARK_GRAY);
    
    // Draw RPM value
    char rpmText[10];
    snprintf(rpmText, sizeof(rpmText), "%d", telemetry.rpm);
    // drawCenteredText(rpmText, DISPLAY_CENTER_Y - 15, COLOR_WHITE, 4);
    
    // Draw "RPM" label
    // drawCenteredText("RPM", DISPLAY_CENTER_Y + 20, COLOR_LIGHT_GRAY, 2);
    
    // Draw gear indicator at bottom
    char gearText[5];
    if (telemetry.gear == 0) {
        snprintf(gearText, sizeof(gearText), "N");
    } else {
        snprintf(gearText, sizeof(gearText), "%d", telemetry.gear);
    }
    // drawCenteredText(gearText, DISPLAY_HEIGHT - 60, rpmColor, 5);
}

void UIManager::renderSpeedometer() {
    // Clear screen
    // tft.fillScreen(COLOR_BLACK);
    
    // Convert speed if needed
    uint16_t displaySpeed = settings.use_mph ? 
        (telemetry.speed_kmh * 10 / 16) : telemetry.speed_kmh;
    
    // Draw speed value large
    char speedText[10];
    snprintf(speedText, sizeof(speedText), "%d", displaySpeed);
    // drawCenteredText(speedText, DISPLAY_CENTER_Y - 30, COLOR_WHITE, 6);
    
    // Draw unit label
    const char* unitText = settings.use_mph ? "MPH" : "KMH";
    // drawCenteredText(unitText, DISPLAY_CENTER_Y + 40, COLOR_LIGHT_GRAY, 2);
    
    // Draw gear box at bottom
    char gearText[5];
    if (telemetry.gear == 0) {
        snprintf(gearText, sizeof(gearText), "N");
    } else {
        snprintf(gearText, sizeof(gearText), "%d", telemetry.gear);
    }
    // Draw box around gear
    // tft.drawRoundRect(DISPLAY_CENTER_X - 30, DISPLAY_HEIGHT - 80, 60, 50, 8, COLOR_WHITE);
    // drawCenteredText(gearText, DISPLAY_HEIGHT - 65, COLOR_GREEN, 4);
}

void UIManager::renderTPMS() {
    // Clear screen
    // tft.fillScreen(COLOR_BLACK);
    
    // Title
    // drawCenteredText("TPMS", 30, COLOR_WHITE, 2);
    
    // Draw 4 tire positions with pressure/temp
    // Layout:  FL    FR
    //          RL    RR
    
    const int leftX = 90;
    const int rightX = 270;
    const int topY = 100;
    const int bottomY = 220;
    
    const char* positions[] = {"FL", "FR", "RL", "RR"};
    int xPos[] = {leftX, rightX, leftX, rightX};
    int yPos[] = {topY, topY, bottomY, bottomY};
    
    for (int i = 0; i < 4; i++) {
        // Determine color based on pressure (warn if < 28 or > 36 PSI)
        uint16_t color = COLOR_GREEN;
        if (telemetry.tire_pressure[i] < 28.0 || telemetry.tire_pressure[i] > 36.0) {
            color = COLOR_YELLOW;
        }
        if (telemetry.tire_pressure[i] < 25.0 || telemetry.tire_pressure[i] > 40.0) {
            color = COLOR_RED;
        }
        
        // Draw tire box
        // tft.drawRoundRect(xPos[i] - 40, yPos[i] - 35, 80, 70, 5, color);
        
        // Draw position label
        // tft.setCursor(xPos[i] - 10, yPos[i] - 25);
        // tft.print(positions[i]);
        
        // Draw pressure
        char pressText[10];
        snprintf(pressText, sizeof(pressText), "%.1f", telemetry.tire_pressure[i]);
        // tft.setCursor(xPos[i] - 25, yPos[i] - 5);
        // tft.print(pressText);
        
        // Draw temp
        char tempText[10];
        snprintf(tempText, sizeof(tempText), "%.0fC", telemetry.tire_temp[i]);
        // tft.setCursor(xPos[i] - 15, yPos[i] + 15);
        // tft.print(tempText);
    }
    
    // Draw car outline in center
    // Simple rectangle to represent car
    // tft.drawRect(DISPLAY_CENTER_X - 20, DISPLAY_CENTER_Y - 40, 40, 80, COLOR_LIGHT_GRAY);
}

void UIManager::renderEngineTemps() {
    // Clear screen
    // tft.fillScreen(COLOR_BLACK);
    
    // Title
    // drawCenteredText("ENGINE", 30, COLOR_WHITE, 2);
    
    // Coolant temp with bar
    int coolantY = 100;
    // drawCenteredText("COOLANT", coolantY, COLOR_LIGHT_GRAY, 1);
    char coolantText[10];
    snprintf(coolantText, sizeof(coolantText), "%dF", telemetry.coolant_temp);
    // drawCenteredText(coolantText, coolantY + 25, 
    //                  telemetry.coolant_temp > 220 ? COLOR_RED : COLOR_GREEN, 3);
    
    // Oil temp
    int oilY = 180;
    // drawCenteredText("OIL", oilY, COLOR_LIGHT_GRAY, 1);
    char oilText[10];
    snprintf(oilText, sizeof(oilText), "%dF", telemetry.oil_temp);
    // drawCenteredText(oilText, oilY + 25,
    //                  telemetry.oil_temp > 250 ? COLOR_RED : COLOR_GREEN, 3);
    
    // Ambient temp
    int ambientY = 260;
    // drawCenteredText("AMBIENT", ambientY, COLOR_LIGHT_GRAY, 1);
    char ambientText[10];
    snprintf(ambientText, sizeof(ambientText), "%dF", telemetry.ambient_temp);
    // drawCenteredText(ambientText, ambientY + 25, COLOR_CYAN, 3);
}

void UIManager::renderGForce() {
    // Clear screen
    // tft.fillScreen(COLOR_BLACK);
    
    // Title
    // drawCenteredText("G-FORCE", 30, COLOR_WHITE, 2);
    
    // Draw G-force circle background
    // tft.drawCircle(DISPLAY_CENTER_X, DISPLAY_CENTER_Y, 100, COLOR_DARK_GRAY);
    // tft.drawCircle(DISPLAY_CENTER_X, DISPLAY_CENTER_Y, 50, COLOR_DARK_GRAY);
    
    // Draw crosshairs
    // tft.drawLine(DISPLAY_CENTER_X - 110, DISPLAY_CENTER_Y, 
    //              DISPLAY_CENTER_X + 110, DISPLAY_CENTER_Y, COLOR_DARK_GRAY);
    // tft.drawLine(DISPLAY_CENTER_X, DISPLAY_CENTER_Y - 110,
    //              DISPLAY_CENTER_X, DISPLAY_CENTER_Y + 110, COLOR_DARK_GRAY);
    
    // Calculate G-force dot position (scale: 1G = 50 pixels)
    int gX = DISPLAY_CENTER_X + (int)(telemetry.g_lateral * 50);
    int gY = DISPLAY_CENTER_Y - (int)(telemetry.g_longitudinal * 50);
    
    // Clamp to display
    gX = constrain(gX, 80, 280);
    gY = constrain(gY, 80, 280);
    
    // Draw G-force dot
    // tft.fillCircle(gX, gY, 10, COLOR_RED);
    
    // Draw values at bottom
    char gText[20];
    snprintf(gText, sizeof(gText), "L:%.2f A:%.2f", 
             telemetry.g_lateral, telemetry.g_longitudinal);
    // drawCenteredText(gText, DISPLAY_HEIGHT - 40, COLOR_WHITE, 1);
}

void UIManager::renderSettings() {
    // Clear screen
    // tft.fillScreen(COLOR_BLACK);
    
    // Title
    // drawCenteredText("SETTINGS", 30, COLOR_WHITE, 2);
    
    int startY = 80;
    int itemHeight = 45;
    
    for (int i = 0; i < SETTING_COUNT; i++) {
        int itemY = startY + (i * itemHeight);
        bool selected = (i == menuSelection);
        bool editing = selected && inEditMode;
        
        uint16_t bgColor = selected ? COLOR_DARK_GRAY : COLOR_BLACK;
        uint16_t textColor = editing ? COLOR_YELLOW : (selected ? COLOR_WHITE : COLOR_LIGHT_GRAY);
        
        // Draw selection background
        if (selected) {
            // tft.fillRect(30, itemY - 5, 300, 40, bgColor);
        }
        
        // Draw item name
        // tft.setCursor(50, itemY);
        // tft.setTextColor(textColor);
        // tft.print(SETTING_NAMES[i]);
        
        // Draw value (if not Back)
        if (i != SETTING_BACK) {
            char valueText[20];
            switch (i) {
                case SETTING_BRIGHTNESS:
                    snprintf(valueText, sizeof(valueText), "%d%%", settings.brightness);
                    break;
                case SETTING_SHIFT_RPM:
                    snprintf(valueText, sizeof(valueText), "%d", settings.shift_rpm);
                    break;
                case SETTING_REDLINE_RPM:
                    snprintf(valueText, sizeof(valueText), "%d", settings.redline_rpm);
                    break;
                case SETTING_UNITS:
                    snprintf(valueText, sizeof(valueText), "%s", settings.use_mph ? "MPH" : "KMH");
                    break;
            }
            // tft.setCursor(250, itemY);
            // tft.print(valueText);
        }
        
        // Draw edit indicator
        if (editing) {
            // tft.setCursor(35, itemY);
            // tft.print(">");
        }
    }
    
    // Draw navigation hint
    // drawCenteredText("UP/DN:Nav  SEL:Edit  VOL:Adj", DISPLAY_HEIGHT - 30, COLOR_LIGHT_GRAY, 1);
}

void UIManager::renderSleepScreen() {
    // Just turn off display or show black
    // tft.fillScreen(COLOR_BLACK);
    // Could show small clock or nothing
}

// Helper implementations

uint16_t UIManager::getRPMColor(uint16_t rpm) {
    if (rpm < 2000) return COLOR_RPM_IDLE;
    if (rpm < 3000) return COLOR_RPM_ECO;
    if (rpm < 4500) return COLOR_RPM_NORMAL;
    if (rpm < 5500) return COLOR_RPM_SPIRITED;
    return COLOR_RPM_HIGH;
}

float UIManager::rpmToAngle(uint16_t rpm) {
    // Map RPM 0-7200 to angle 0-270 degrees
    float maxRPM = (float)settings.redline_rpm;
    float angle = (rpm / maxRPM) * 270.0f;
    return constrain(angle, 0, 270);
}

void UIManager::nextScreen() {
    currentScreen = (ScreenID)((currentScreen + 1) % SCREEN_COUNT);
}

void UIManager::prevScreen() {
    currentScreen = (ScreenID)((currentScreen + SCREEN_COUNT - 1) % SCREEN_COUNT);
}

void UIManager::menuUp() {
    menuSelection = (menuSelection + SETTING_COUNT - 1) % SETTING_COUNT;
}

void UIManager::menuDown() {
    menuSelection = (menuSelection + 1) % SETTING_COUNT;
}

void UIManager::menuSelect() {
    if (menuSelection == SETTING_BACK) {
        menuBack();
    } else {
        inEditMode = !inEditMode;
    }
}

void UIManager::menuBack() {
    inEditMode = false;
    currentScreen = previousScreen;
    menuSelection = 0;
}

void UIManager::adjustValue(int delta) {
    switch (menuSelection) {
        case SETTING_BRIGHTNESS:
            settings.brightness = constrain(settings.brightness + delta * 5, 10, 100);
            break;
        case SETTING_SHIFT_RPM:
            settings.shift_rpm = constrain(settings.shift_rpm + delta * 100, 4000, 7500);
            break;
        case SETTING_REDLINE_RPM:
            settings.redline_rpm = constrain(settings.redline_rpm + delta * 100, 5000, 8000);
            break;
        case SETTING_UNITS:
            settings.use_mph = !settings.use_mph;
            break;
    }
}
