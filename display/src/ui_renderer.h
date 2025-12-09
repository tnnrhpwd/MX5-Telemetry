/*
 * ============================================================================
 * MX5-Telemetry Display - UI Renderer
 * ============================================================================
 * Renders all screens using LovyanGFX, matching the Python simulator exactly
 * ============================================================================
 */

#ifndef UI_RENDERER_H
#define UI_RENDERER_H

#include <LovyanGFX.hpp>
#include "ui_config.h"
#include <math.h>

// Forward declaration
class LGFX;

class UIRenderer {
public:
    UIRenderer(LGFX* display) : _display(display) {}
    
    void setTelemetry(TelemetryData* data) { _telemetry = data; }
    void setSettings(DisplaySettings* settings) { _settings = settings; }
    
    // Main render function
    void render(Screen screen, bool sleeping = false);
    
    // Navigation state
    void setSettingsSelection(int sel) { _settingsSelection = sel; }
    void setSettingsEditMode(bool edit) { _settingsEditMode = edit; }
    int getSettingsSelection() { return _settingsSelection; }
    bool getSettingsEditMode() { return _settingsEditMode; }
    
private:
    LGFX* _display;
    TelemetryData* _telemetry = nullptr;
    DisplaySettings* _settings = nullptr;
    
    int _settingsSelection = 0;
    bool _settingsEditMode = false;
    
    // Screen renderers
    void renderOverview();
    void renderRpmSpeed();
    void renderTpms();
    void renderEngine();
    void renderGforce();
    void renderSettings();
    void renderSleep();
    void renderScreenDots(Screen currentScreen);
    
    // Helper functions
    uint16_t getRpmColor(uint16_t rpm);
    void drawArc(int cx, int cy, int radius, int thickness, float startAngle, float endAngle, uint16_t color);
    void drawRoundedRect(int x, int y, int w, int h, int r, uint16_t color, bool filled = true);
    void drawRoundedRectOutline(int x, int y, int w, int h, int r, uint16_t color, int thickness = 1);
    void drawCenteredText(const char* text, int x, int y, const lgfx::IFont* font, uint16_t color);
    void drawGlowCircle(int cx, int cy, int radius, uint16_t color, uint8_t alpha);
    
    // Alert helpers
    struct Alert {
        const char* text;
        uint16_t color;
    };
    int getAlerts(Alert* alerts, int maxAlerts);
};

// =============================================================================
// Implementation
// =============================================================================

inline void UIRenderer::render(Screen screen, bool sleeping) {
    _display->startWrite();
    _display->fillScreen(COLOR_BG);
    
    if (sleeping) {
        renderSleep();
    } else {
        switch (screen) {
            case SCREEN_OVERVIEW:   renderOverview(); break;
            case SCREEN_RPM_SPEED:  renderRpmSpeed(); break;
            case SCREEN_TPMS:       renderTpms(); break;
            case SCREEN_ENGINE:     renderEngine(); break;
            case SCREEN_GFORCE:     renderGforce(); break;
            case SCREEN_SETTINGS:   renderSettings(); break;
            default: break;
        }
        renderScreenDots(screen);
    }
    
    _display->endWrite();
}

inline void UIRenderer::renderSleep() {
    _display->setTextColor(COLOR_DARK_GRAY);
    _display->setTextDatum(middle_center);
    _display->setFont(&fonts::Font4);
    _display->drawString("SLEEP", CENTER, CENTER);
}

inline void UIRenderer::renderScreenDots(Screen currentScreen) {
    int y = DISPLAY_SIZE - 22;
    int total = SCREEN_COUNT * 12;
    int startX = CENTER - total / 2;
    
    for (int i = 0; i < SCREEN_COUNT; i++) {
        uint16_t color = (i == (int)currentScreen) ? COLOR_WHITE : COLOR_DARK_GRAY;
        _display->fillCircle(startX + i * 12, y, 4, color);
    }
}

inline uint16_t UIRenderer::getRpmColor(uint16_t rpm) {
    if (!_settings) return COLOR_GREEN;
    
    float pct = (float)rpm / _settings->redline_rpm;
    if (pct >= 0.95f) return COLOR_RED;
    if (pct >= 0.85f) return COLOR_ORANGE;
    if (pct >= 0.70f) return COLOR_YELLOW;
    return COLOR_GREEN;
}

inline void UIRenderer::drawArc(int cx, int cy, int radius, int thickness, float startAngle, float endAngle, uint16_t color) {
    // Convert degrees to radians
    float startRad = startAngle * M_PI / 180.0f;
    float endRad = endAngle * M_PI / 180.0f;
    
    // Draw arc using small line segments
    int steps = (int)((endAngle - startAngle) / 2);
    if (steps < 1) steps = 1;
    
    for (int i = 0; i < steps; i++) {
        float a1 = startRad + (endRad - startRad) * i / steps;
        float a2 = startRad + (endRad - startRad) * (i + 1) / steps;
        
        for (int t = -thickness/2; t <= thickness/2; t++) {
            int r = radius + t;
            int x1 = cx + (int)(cos(a1) * r);
            int y1 = cy + (int)(sin(a1) * r);
            int x2 = cx + (int)(cos(a2) * r);
            int y2 = cy + (int)(sin(a2) * r);
            _display->drawLine(x1, y1, x2, y2, color);
        }
    }
}

inline void UIRenderer::drawRoundedRect(int x, int y, int w, int h, int r, uint16_t color, bool filled) {
    if (filled) {
        _display->fillRoundRect(x, y, w, h, r, color);
    } else {
        _display->drawRoundRect(x, y, w, h, r, color);
    }
}

inline void UIRenderer::drawRoundedRectOutline(int x, int y, int w, int h, int r, uint16_t color, int thickness) {
    for (int i = 0; i < thickness; i++) {
        _display->drawRoundRect(x + i, y + i, w - i*2, h - i*2, r, color);
    }
}

inline void UIRenderer::drawCenteredText(const char* text, int x, int y, const lgfx::IFont* font, uint16_t color) {
    _display->setFont(font);
    _display->setTextColor(color);
    _display->setTextDatum(middle_center);
    _display->drawString(text, x, y);
}

inline void UIRenderer::drawGlowCircle(int cx, int cy, int radius, uint16_t color, uint8_t alpha) {
    // Simple glow effect using concentric circles with decreasing opacity
    // Note: Full alpha blending would require more complex implementation
    for (int r = radius; r > radius - 5; r--) {
        _display->drawCircle(cx, cy, r, color);
    }
}

inline int UIRenderer::getAlerts(Alert* alerts, int maxAlerts) {
    if (!_telemetry || !_settings) return 0;
    
    int count = 0;
    
    // Check tire pressures
    for (int i = 0; i < 4 && count < maxAlerts; i++) {
        if (_telemetry->tire_pressure[i] < _settings->tire_low_psi) {
            static char buf[20];
            const char* names[] = {"FL", "FR", "RL", "RR"};
            snprintf(buf, sizeof(buf), "%s LOW: %.1f PSI", names[i], _telemetry->tire_pressure[i]);
            alerts[count].text = buf;
            alerts[count].color = COLOR_RED;
            count++;
        }
    }
    
    // Check coolant temp
    if (_telemetry->coolant_temp_f >= _settings->coolant_warn_f && count < maxAlerts) {
        alerts[count].text = "COOLANT HIGH";
        alerts[count].color = COLOR_RED;
        count++;
    }
    
    // Check oil temp
    if (_telemetry->oil_temp_f >= _settings->oil_warn_f && count < maxAlerts) {
        alerts[count].text = "OIL TEMP HIGH";
        alerts[count].color = COLOR_RED;
        count++;
    }
    
    // Check voltage
    if (_telemetry->voltage < 12.0f && count < maxAlerts) {
        alerts[count].text = "LOW VOLTAGE";
        alerts[count].color = COLOR_YELLOW;
        count++;
    }
    
    // Check fuel
    if (_telemetry->fuel_level_percent < 15.0f && count < maxAlerts) {
        alerts[count].text = "LOW FUEL";
        alerts[count].color = COLOR_YELLOW;
        count++;
    }
    
    return count;
}

// =============================================================================
// Screen: Overview
// =============================================================================
inline void UIRenderer::renderOverview() {
    // Subtle radial gradient background effect
    _display->fillCircle(CENTER, CENTER, 160, COLOR_BG_CARD);
    _display->fillCircle(CENTER, CENTER, 100, COLOR_BG);
    
    // Get alerts
    Alert alerts[8];
    int alertCount = getAlerts(alerts, 8);
    
    // Gear in center-top with glow
    char gearStr[2] = {(_telemetry->gear == 0) ? 'N' : (char)('0' + _telemetry->gear), '\0'};
    uint16_t rpmColor = getRpmColor(_telemetry->rpm);
    
    // Gear glow (simplified)
    _display->fillCircle(CENTER, 55, 30, rpmColor);
    _display->fillCircle(CENTER, 55, 25, COLOR_BG);
    
    drawCenteredText(gearStr, CENTER, 60, &fonts::Font7, rpmColor);
    
    // Speed below gear
    uint16_t speed = _telemetry->speed_kmh;
    if (_settings->use_mph) {
        speed = (uint16_t)(speed * 0.621371f);
    }
    char speedStr[16];
    snprintf(speedStr, sizeof(speedStr), "%d %s", speed, _settings->use_mph ? "MPH" : "KMH");
    drawCenteredText(speedStr, CENTER, 105, &fonts::Font2, COLOR_WHITE);
    
    // Mini TPMS (4 boxes)
    int tireY = 150;
    int boxW = 48, boxH = 38;
    int positions[4][2] = {
        {CENTER - 52, tireY}, {CENTER + 52, tireY},
        {CENTER - 52, tireY + 45}, {CENTER + 52, tireY + 45}
    };
    
    for (int i = 0; i < 4; i++) {
        int x = positions[i][0];
        int y = positions[i][1];
        float psi = _telemetry->tire_pressure[i];
        float temp = _telemetry->tire_temp[i];
        
        uint16_t color = COLOR_GREEN;
        if (psi < _settings->tire_low_psi) color = COLOR_RED;
        else if (psi > _settings->tire_high_psi) color = COLOR_YELLOW;
        
        drawRoundedRect(x - boxW/2, y - boxH/2, boxW, boxH, 6, COLOR_BG_CARD);
        drawRoundedRectOutline(x - boxW/2, y - boxH/2, boxW, boxH, 6, color, 2);
        
        char psiStr[12];
        snprintf(psiStr, sizeof(psiStr), "%.0f/%.0f", psi, temp);
        drawCenteredText(psiStr, x, y, &fonts::Font0, color);
    }
    
    // Alert section at bottom
    int alertY = 260;
    if (alertCount > 0) {
        drawRoundedRect(40, alertY, DISPLAY_SIZE - 80, 26, 6, alerts[0].color);
        drawCenteredText(alerts[0].text, CENTER, alertY + 13, &fonts::Font0, COLOR_BG);
        
        if (alertCount > 1) {
            char countStr[8];
            snprintf(countStr, sizeof(countStr), "+%d", alertCount - 1);
            drawCenteredText(countStr, CENTER, alertY + 38, &fonts::Font0, COLOR_YELLOW);
        }
    } else {
        drawRoundedRect(40, alertY, DISPLAY_SIZE - 80, 26, 6, COLOR_BG_CARD);
        drawRoundedRectOutline(40, alertY, DISPLAY_SIZE - 80, 26, 6, COLOR_GREEN, 2);
        drawCenteredText("ALL OK", CENTER, alertY + 13, &fonts::Font0, COLOR_GREEN);
    }
}

// =============================================================================
// Screen: RPM/Speed
// =============================================================================
inline void UIRenderer::renderRpmSpeed() {
    // Background ring effect
    _display->fillCircle(CENTER, CENTER, 155, COLOR_BG_CARD);
    _display->fillCircle(CENTER, CENTER, 120, COLOR_BG);
    
    // RPM arc
    int radius = 145;
    int thickness = 20;
    
    // Background arc
    drawArc(CENTER, CENTER, radius, thickness, 135, 405, COLOR_DARK_GRAY);
    
    // RPM fill arc
    float rpmPct = (float)_telemetry->rpm / _settings->redline_rpm;
    float rpmAngle = fmin(270.0f, fmax(0.0f, rpmPct * 270.0f));
    uint16_t rpmColor = getRpmColor(_telemetry->rpm);
    
    if (rpmAngle > 0) {
        drawArc(CENTER, CENTER, radius, thickness, 135, 135 + rpmAngle, rpmColor);
    }
    
    // Shift indicator
    if (_telemetry->rpm >= _settings->shift_rpm) {
        _display->fillCircle(CENTER, 35, 12, COLOR_RED);
    }
    
    // Gear in center
    char gearStr[2] = {(_telemetry->gear == 0) ? 'N' : (char)('0' + _telemetry->gear), '\0'};
    
    _display->fillCircle(CENTER, CENTER - 15, 35, rpmColor);
    _display->fillCircle(CENTER, CENTER - 15, 30, COLOR_BG);
    drawCenteredText(gearStr, CENTER, CENTER - 15, &fonts::Font7, rpmColor);
    
    // Speed
    uint16_t speed = _telemetry->speed_kmh;
    if (_settings->use_mph) {
        speed = (uint16_t)(speed * 0.621371f);
    }
    char speedStr[8];
    snprintf(speedStr, sizeof(speedStr), "%d", speed);
    drawCenteredText(speedStr, CENTER, CENTER + 40, &fonts::Font4, COLOR_WHITE);
    
    const char* unit = _settings->use_mph ? "MPH" : "KMH";
    drawCenteredText(unit, CENTER, CENTER + 65, &fonts::Font0, COLOR_GRAY);
    
    // RPM text
    char rpmStr[16];
    snprintf(rpmStr, sizeof(rpmStr), "%d RPM", _telemetry->rpm);
    drawCenteredText(rpmStr, CENTER, DISPLAY_SIZE - 45, &fonts::Font2, COLOR_GRAY);
}

// =============================================================================
// Screen: TPMS
// =============================================================================
inline void UIRenderer::renderTpms() {
    // Title
    drawCenteredText("TPMS", CENTER, 35, &fonts::Font2, COLOR_WHITE);
    _display->drawFastHLine(CENTER - 40, 52, 80, COLOR_ACCENT);
    
    // Car outline
    int carW = 70, carH = 120;
    drawRoundedRect(CENTER - carW/2, CENTER - carH/2 + 10, carW, carH, 12, COLOR_BG_CARD);
    drawRoundedRectOutline(CENTER - carW/2, CENTER - carH/2 + 10, carW, carH, 12, COLOR_DARK_GRAY, 2);
    
    // Tire positions
    int positions[4][2] = {
        {CENTER - 70, CENTER - 35}, {CENTER + 70, CENTER - 35},
        {CENTER - 70, CENTER + 65}, {CENTER + 70, CENTER + 65}
    };
    const char* labels[] = {"FL", "FR", "RL", "RR"};
    
    int boxW = 68, boxH = 58;
    
    for (int i = 0; i < 4; i++) {
        int x = positions[i][0];
        int y = positions[i][1];
        float psi = _telemetry->tire_pressure[i];
        float temp = _telemetry->tire_temp[i];
        
        uint16_t color = COLOR_GREEN;
        if (psi < _settings->tire_low_psi) color = COLOR_RED;
        else if (psi > _settings->tire_high_psi) color = COLOR_YELLOW;
        
        // Tire card
        drawRoundedRect(x - boxW/2, y - boxH/2, boxW, boxH, 10, COLOR_BG_CARD);
        
        // Color accent bar
        _display->fillRoundRect(x - boxW/2, y - boxH/2, 4, boxH, 2, color);
        
        // Label
        drawCenteredText(labels[i], x + 2, y - 18, &fonts::Font0, COLOR_GRAY);
        
        // PSI
        char psiStr[8];
        snprintf(psiStr, sizeof(psiStr), "%.1f", psi);
        drawCenteredText(psiStr, x + 2, y + 2, &fonts::Font2, color);
        
        // Temp
        char tempStr[8];
        snprintf(tempStr, sizeof(tempStr), "%.0fF", temp);
        drawCenteredText(tempStr, x + 2, y + 20, &fonts::Font0, COLOR_GRAY);
    }
}

// =============================================================================
// Screen: Engine
// =============================================================================
inline void UIRenderer::renderEngine() {
    // Title
    drawCenteredText("ENGINE", CENTER, 35, &fonts::Font2, COLOR_WHITE);
    _display->drawFastHLine(CENTER - 50, 52, 100, COLOR_ACCENT);
    
    // Coolant (left)
    uint16_t coolColor = (_telemetry->coolant_temp_f >= _settings->coolant_warn_f) ? COLOR_RED : COLOR_TEAL;
    drawRoundedRect(30, 70, 100, 75, 12, COLOR_BG_CARD);
    _display->fillRoundRect(30, 70, 4, 75, 2, coolColor);
    drawCenteredText("COOLANT", 80, 85, &fonts::Font0, COLOR_GRAY);
    char coolStr[8];
    snprintf(coolStr, sizeof(coolStr), "%d", _telemetry->coolant_temp_f);
    drawCenteredText(coolStr, 80, 115, &fonts::Font4, coolColor);
    
    // Oil (right)
    uint16_t oilColor = (_telemetry->oil_temp_f >= _settings->oil_warn_f) ? COLOR_RED : COLOR_GREEN;
    drawRoundedRect(DISPLAY_SIZE - 130, 70, 100, 75, 12, COLOR_BG_CARD);
    _display->fillRoundRect(DISPLAY_SIZE - 130, 70, 4, 75, 2, oilColor);
    drawCenteredText("OIL", DISPLAY_SIZE - 80, 85, &fonts::Font0, COLOR_GRAY);
    char oilStr[8];
    snprintf(oilStr, sizeof(oilStr), "%d", _telemetry->oil_temp_f);
    drawCenteredText(oilStr, DISPLAY_SIZE - 80, 115, &fonts::Font4, oilColor);
    
    // Fuel (center circular gauge)
    float fuel = _telemetry->fuel_level_percent;
    uint16_t fuelColor = (fuel < 15) ? COLOR_RED : ((fuel < 25) ? COLOR_YELLOW : COLOR_GREEN);
    
    int fuelCx = CENTER, fuelCy = 210, fuelR = 55;
    _display->fillCircle(fuelCx, fuelCy, fuelR, COLOR_BG_CARD);
    _display->drawCircle(fuelCx, fuelCy, fuelR, COLOR_DARK_GRAY);
    
    // Fuel arc
    float fuelAngle = 360.0f * fuel / 100.0f;
    drawArc(fuelCx, fuelCy, fuelR - 5, 8, -90, -90 + fuelAngle, fuelColor);
    
    char fuelStr[8];
    snprintf(fuelStr, sizeof(fuelStr), "%d%%", (int)fuel);
    drawCenteredText(fuelStr, fuelCx, fuelCy - 5, &fonts::Font4, fuelColor);
    drawCenteredText("FUEL", fuelCx, fuelCy + 20, &fonts::Font0, COLOR_GRAY);
    
    // Voltage at bottom
    uint16_t voltColor = (_telemetry->voltage < 12.0f) ? COLOR_RED : 
                         ((_telemetry->voltage < 13.0f) ? COLOR_YELLOW : COLOR_GREEN);
    drawRoundedRect(CENTER - 60, 280, 120, 35, 8, COLOR_BG_CARD);
    char voltStr[12];
    snprintf(voltStr, sizeof(voltStr), "%.1fV", _telemetry->voltage);
    drawCenteredText(voltStr, CENTER, 297, &fonts::Font0, voltColor);
}

// =============================================================================
// Screen: G-Force
// =============================================================================
inline void UIRenderer::renderGforce() {
    // Title
    drawCenteredText("G-FORCE", CENTER, 35, &fonts::Font2, COLOR_WHITE);
    _display->drawFastHLine(CENTER - 55, 52, 110, COLOR_ACCENT);
    
    // G-ball background
    int ballCx = CENTER, ballCy = CENTER + 15;
    int ballR = 105;
    
    _display->fillCircle(ballCx, ballCy, ballR + 8, COLOR_BG_CARD);
    _display->fillCircle(ballCx, ballCy, ballR, COLOR_BG);
    
    // Grid circles
    for (float g = 0.5f; g <= 1.5f; g += 0.5f) {
        int r = (int)(g * 60);
        _display->drawCircle(ballCx, ballCy, r, COLOR_DARK_GRAY);
    }
    
    // Crosshairs
    _display->drawFastHLine(ballCx - ballR, ballCy, ballR * 2, COLOR_DARK_GRAY);
    _display->drawFastVLine(ballCx, ballCy - ballR, ballR * 2, COLOR_DARK_GRAY);
    
    // G-ball position
    int gScale = 60;
    int gx = ballCx + (int)(_telemetry->g_lateral * gScale);
    int gy = ballCy - (int)(_telemetry->g_longitudinal * gScale);
    
    // Clamp to circle
    float dx = gx - ballCx;
    float dy = gy - ballCy;
    float dist = sqrtf(dx*dx + dy*dy);
    if (dist > ballR - 12) {
        float scale = (ballR - 12) / dist;
        gx = ballCx + (int)(dx * scale);
        gy = ballCy + (int)(dy * scale);
    }
    
    // G-ball
    _display->fillCircle(gx, gy, 12, COLOR_ACCENT);
    _display->drawCircle(gx, gy, 12, COLOR_WHITE);
    
    // Value cards at bottom
    int cardY = DISPLAY_SIZE - 80;
    int cardW = 85, cardH = 45;
    
    // Lateral
    drawRoundedRect(30, cardY, cardW, cardH, 8, COLOR_BG_CARD);
    _display->fillRoundRect(30, cardY, 3, cardH, 2, COLOR_CYAN);
    drawCenteredText("LAT", 72, cardY + 10, &fonts::Font0, COLOR_GRAY);
    char latStr[8];
    snprintf(latStr, sizeof(latStr), "%+.1fG", _telemetry->g_lateral);
    drawCenteredText(latStr, 72, cardY + 30, &fonts::Font2, COLOR_CYAN);
    
    // Longitudinal
    drawRoundedRect(DISPLAY_SIZE - 30 - cardW, cardY, cardW, cardH, 8, COLOR_BG_CARD);
    _display->fillRoundRect(DISPLAY_SIZE - 30 - cardW, cardY, 3, cardH, 2, COLOR_PURPLE);
    drawCenteredText("LONG", DISPLAY_SIZE - 72, cardY + 10, &fonts::Font0, COLOR_GRAY);
    char longStr[8];
    snprintf(longStr, sizeof(longStr), "%+.1fG", _telemetry->g_longitudinal);
    drawCenteredText(longStr, DISPLAY_SIZE - 72, cardY + 30, &fonts::Font2, COLOR_PURPLE);
}

// =============================================================================
// Screen: Settings (shows only 3 visible items)
// =============================================================================
inline void UIRenderer::renderSettings() {
    // Title
    drawCenteredText("SETTINGS", CENTER, 50, &fonts::Font2, COLOR_WHITE);
    _display->drawFastHLine(CENTER - 60, 68, 120, COLOR_ACCENT);
    
    // Settings items
    const char* names[] = {"Brightness", "Shift RPM", "Redline", "Units", "Low PSI", "Coolant Warn", "Back"};
    const int itemCount = 7;
    
    int sel = _settingsSelection;
    
    // Determine visible indices (previous, selected, next)
    int visible[3];
    int visibleCount = 0;
    
    if (sel > 0) visible[visibleCount++] = sel - 1;
    visible[visibleCount++] = sel;
    if (sel < itemCount - 1) visible[visibleCount++] = sel + 1;
    
    // Up arrow indicator
    if (sel > 0) {
        drawCenteredText("^", CENTER, 85, &fonts::Font0, COLOR_GRAY);
    }
    
    // Calculate positions
    int itemH = 50;
    int totalH = visibleCount * itemH;
    int startY = CENTER - totalH/2 + 20;
    
    for (int slot = 0; slot < visibleCount; slot++) {
        int idx = visible[slot];
        int y = startY + slot * itemH;
        bool isSelected = (idx == sel);
        
        int cardMargin = isSelected ? 45 : 55;
        uint16_t bgColor = isSelected ? COLOR_BG_ELEVATED : COLOR_BG_CARD;
        int cardH = isSelected ? 42 : 36;
        
        drawRoundedRect(cardMargin, y, DISPLAY_SIZE - cardMargin*2, cardH, 10, bgColor);
        
        if (isSelected) {
            _display->fillRoundRect(cardMargin, y, 4, cardH, 2, COLOR_ACCENT);
            if (_settingsEditMode) {
                drawRoundedRectOutline(cardMargin, y, DISPLAY_SIZE - cardMargin*2, cardH, 10, COLOR_ACCENT, 2);
            }
        }
        
        uint16_t textColor = isSelected ? COLOR_WHITE : COLOR_GRAY;
        const lgfx::IFont* font = isSelected ? &fonts::Font2 : &fonts::Font0;
        
        // Name
        _display->setFont(font);
        _display->setTextColor(textColor);
        _display->setTextDatum(middle_left);
        _display->drawString(names[idx], cardMargin + 12, y + cardH/2);
        
        // Value
        char valStr[16] = "";
        switch (idx) {
            case 0: snprintf(valStr, sizeof(valStr), "%d%%", _settings->brightness); break;
            case 1: snprintf(valStr, sizeof(valStr), "%d", _settings->shift_rpm); break;
            case 2: snprintf(valStr, sizeof(valStr), "%d", _settings->redline_rpm); break;
            case 3: snprintf(valStr, sizeof(valStr), "%s", _settings->use_mph ? "MPH" : "KMH"); break;
            case 4: snprintf(valStr, sizeof(valStr), "%.0f", _settings->tire_low_psi); break;
            case 5: snprintf(valStr, sizeof(valStr), "%d°F", _settings->coolant_warn_f); break;
            default: break;
        }
        
        if (strlen(valStr) > 0) {
            uint16_t valColor = isSelected ? COLOR_ACCENT : COLOR_WHITE;
            _display->setTextColor(valColor);
            _display->setTextDatum(middle_right);
            _display->drawString(valStr, DISPLAY_SIZE - cardMargin - 12, y + cardH/2);
        }
    }
    
    // Down arrow indicator
    if (sel < itemCount - 1) {
        drawCenteredText("v", CENTER, DISPLAY_SIZE - 85, &fonts::Font0, COLOR_GRAY);
    }
    
    // Item counter
    char countStr[8];
    snprintf(countStr, sizeof(countStr), "%d/%d", sel + 1, itemCount);
    drawCenteredText(countStr, CENTER, DISPLAY_SIZE - 60, &fonts::Font0, COLOR_DARK_GRAY);
}

#endif // UI_RENDERER_H
