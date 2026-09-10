/**
 * @file ui_core.cpp
 * @brief Shared UI core for the MX5 ESP32-S3 round display.
 *
 * This is THE single source of truth for the screen rendering + navigation
 * state. It is compiled unchanged into:
 *   - the ESP32 firmware (display/src/main.cpp includes ui_core.h), and
 *   - the native desktop simulator (tools/simulators/native).
 *
 * All drawing goes through the LCD_* API (real ST77916 driver on device,
 * mock framebuffer backend in the simulator).
 */

#include "ui_core.h"
#include <math.h>
#include <string.h>
#include <stdio.h>

// ============================================================================
// Global state definitions
// ============================================================================

TelemetryData telemetry = {0};

// Settings from Pi
int clutchDisplayMode = 0;  // 0=Gear#(colored), 1='C', 2='S', 3='-'

CachedTelemetry prevTelemetry = {0};

DisplaySettings settings;

bool imuAvailable = false;

// Orientation used by the G-Force screen
float orientationPitch = 0;
float orientationRoll = 0;

const char* SCREEN_NAMES[] = {
    "Overview", "RPM/Speed", "TPMS", "Engine",
    "G-Force", "Diagnostics", "System", "Settings"
};

const char* LED_SEQUENCE_NAMES[] = {
    "",                     // Index 0 unused (sequences start at 1)
    "Center-Out",           // 1: Default mirrored
    "Left-Right",           // 2: Double resolution L->R
    "Right-Left",           // 3: Double resolution R->L
    "Center-In"             // 4: From center outward
};

const char* LOADING_MESSAGES[] = {
    "Rocket boosters...",
    "Flux capacitor...",
    "Hamster wheels...",
    "Downloading RAM...",
    "Spline reticulation",
    "Engaging warp...",
    "Brewing coffee...",
    "Polishing pixels...",
    "Car spirits...",
    "Laser cannons...",
    "Turbo snails...",
    "Spaghetti code...",
    "Code monkeys...",
    "Electrons ready",
    "Sensor talks...",
    "Awesomeness init",
    "Dad jokes...",
    "Crystal ball...",
    "Magic tuning...",
    "Aligning chakras"
};

ScreenMode currentScreen = SCREEN_OVERVIEW;
bool needsRedraw = true;
bool needsFullRedraw = true;  // Set to true on screen change to redraw background
bool navLocked = false;       // Navigation lock state (from Pi SWC handler)

// Boot countdown
unsigned long bootStartTime = 0;
bool piDataReceived = false;
int lastBootCountdown = 99;
int currentLoadingMessage = 0;
unsigned long lastMessageChange = 0;

// Page transition animation state
TransitionType currentTransition = TRANSITION_NONE;
unsigned long transitionStartTime = 0;
unsigned long lastTransitionEndTime = 0;
int transitionDuration = 200;  // milliseconds
float transitionProgress = 0.0;
ScreenMode transitionFromScreen = SCREEN_OVERVIEW;
ScreenMode transitionToScreen = SCREEN_OVERVIEW;

// Settings menu state
int settingsSelection = 0;
int settingsScrollOffset = 0;

// TPMS per-tire timestamps
char tpmsLastUpdateStr[4][12] = {"--:--:--", "--:--:--", "--:--:--", "--:--:--"};

// ============================================================================
// Background
// ============================================================================
void drawBackground() {
    LCD_DrawImage(0, 0, BACKGROUND_DATA_WIDTH, BACKGROUND_DATA_HEIGHT, background_data);
}

// ============================================================================
// Page transition animation
// ============================================================================

float easeOutCubic(float t) {
    return 1.0 - pow(1.0 - t, 3);
}

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
        transitionProgress = 1.0;
        currentScreen = transitionToScreen;
        currentTransition = TRANSITION_NONE;
        lastTransitionEndTime = millis();
        needsRedraw = true;
        Serial.printf("Transition complete, now on screen: %s\n", SCREEN_NAMES[currentScreen]);
    }
}

void drawTransitionSlide(bool slideLeft) {
    float easedProgress = easeOutCubic(transitionProgress);
    int offset = (int)(SCREEN_WIDTH * easedProgress);

    if (slideLeft) {
        int dividerX = SCREEN_WIDTH - offset;

        for (int i = 0; i < 4; i++) {
            LCD_DrawLine(dividerX + i - 2, 0, dividerX + i - 2, SCREEN_HEIGHT - 1, MX5_ACCENT);
        }

        if (offset > 10) {
            for (int x = dividerX; x < SCREEN_WIDTH; x++) {
                float brightness = (float)(x - dividerX) / offset;
                brightness = brightness * brightness;
                uint16_t col = RGB565((int)(12 + 10 * brightness),
                                      (int)(12 + 10 * brightness),
                                      (int)(18 + 14 * brightness));
                LCD_DrawLine(x, 0, x, SCREEN_HEIGHT - 1, col);
            }
        }
    } else {
        int dividerX = offset;

        for (int i = 0; i < 4; i++) {
            LCD_DrawLine(dividerX + i - 2, 0, dividerX + i - 2, SCREEN_HEIGHT - 1, MX5_ACCENT);
        }

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
    float easedProgress = easeInOutQuad(transitionProgress);
    int maxRadius = (int)(sqrt(CENTER_X * CENTER_X + CENTER_Y * CENTER_Y) + 20);
    int currentRadius = (int)(maxRadius * easedProgress);

    for (int r = currentRadius - 20; r <= currentRadius; r++) {
        if (r > 0) {
            uint16_t col = MX5_ACCENT;
            float fade = (float)(r - (currentRadius - 20)) / 20.0;
            if (fade < 0.3) col = RGB565((int)(100 * fade / 0.3), (int)(140 * fade / 0.3), (int)(255 * fade / 0.3));
            LCD_DrawCircle(CENTER_X, CENTER_Y, r, col);
        }
    }
}

void drawTransitionZoom() {
    float easedProgress = easeOutCubic(transitionProgress);

    int rectW = (int)(SCREEN_WIDTH * (1.0 - easedProgress));
    int rectH = (int)(SCREEN_HEIGHT * (1.0 - easedProgress));
    int rectX = (SCREEN_WIDTH - rectW) / 2;
    int rectY = (SCREEN_HEIGHT - rectH) / 2;

    if (rectW > 10 && rectH > 10) {
        LCD_DrawRect(rectX, rectY, rectW, rectH, MX5_ACCENT);
        LCD_DrawRect(rectX + 1, rectY + 1, rectW - 2, rectH - 2, MX5_BLUE);
    }

    if (easedProgress > 0.1) {
        LCD_FillRect(0, 0, SCREEN_WIDTH, rectY, COLOR_BG);
        LCD_FillRect(0, rectY + rectH, SCREEN_WIDTH, SCREEN_HEIGHT - rectY - rectH, COLOR_BG);
        LCD_FillRect(0, rectY, rectX, rectH, COLOR_BG);
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

// ============================================================================
// Large gear indicator (anti-aliased)
// ============================================================================
// The large gear glyph is rasterized into a 1-bit buffer, then edge-smoothed
// with the same bilinear 2x2 supersampling used by the text fonts, so the big
// number matches the smooth look of the rest of the UI.
// ============================================================================
void drawLargeGear(int centerX, int centerY, const char* str, uint16_t color, uint16_t bgColor) {
    const int charW = 44;
    const int charH = 64;
    const int stroke = 10;

    static uint8_t glyphBits[charW * charH];
    memset(glyphBits, 0, sizeof(glyphBits));

    // Fill a rectangle into the 1-bit glyph raster (clipped to the cell).
    auto fill = [&](int fx, int fy, int fw, int fh) {
        for (int yy = fy; yy < fy + fh; yy++) {
            for (int xx = fx; xx < fx + fw; xx++) {
                if (xx >= 0 && xx < charW && yy >= 0 && yy < charH) {
                    glyphBits[yy * charW + xx] = 1;
                }
            }
        }
    };

    char c = str[0];
    switch (c) {
        case '1':
            fill(charW / 2 - stroke / 2, 0, stroke, charH);
            fill(charW / 2 - stroke / 2 - stroke, 0, stroke, stroke);
            break;

        case '2':
            fill(0, 0, charW, stroke);                          // Top
            fill(charW - stroke, 0, stroke, charH / 2);         // Top right
            fill(0, charH / 2 - stroke / 2, charW, stroke);     // Middle
            fill(0, charH / 2, stroke, charH / 2);              // Bottom left
            fill(0, charH - stroke, charW, stroke);             // Bottom
            break;

        case '3':
            fill(0, 0, charW, stroke);                          // Top
            fill(charW - stroke, 0, stroke, charH);             // Right
            fill(0, charH / 2 - stroke / 2, charW, stroke);     // Middle
            fill(0, charH - stroke, charW, stroke);             // Bottom
            break;

        case '4':
            fill(0, 0, stroke, charH / 2 + stroke);             // Left top
            fill(0, charH / 2 - stroke / 2, charW, stroke);     // Middle
            fill(charW - stroke, 0, stroke, charH);             // Right
            break;

        case '5':
            fill(0, 0, charW, stroke);                          // Top
            fill(0, 0, stroke, charH / 2);                      // Top left
            fill(0, charH / 2 - stroke / 2, charW, stroke);     // Middle
            fill(charW - stroke, charH / 2, stroke, charH / 2); // Bottom right
            fill(0, charH - stroke, charW, stroke);             // Bottom
            break;

        case '6':
            fill(0, 0, charW, stroke);                          // Top
            fill(0, 0, stroke, charH);                          // Left
            fill(0, charH / 2 - stroke / 2, charW, stroke);     // Middle
            fill(charW - stroke, charH / 2, stroke, charH / 2); // Bottom right
            fill(0, charH - stroke, charW, stroke);             // Bottom
            break;

        case 'N':
            fill(0, 0, stroke, charH);                          // Left
            fill(charW - stroke, 0, stroke, charH);             // Right
            for (int i = 0; i < charH; i += 4) {                // Diagonal
                int dx = (i * (charW - stroke)) / charH;
                fill(dx, i, stroke + 2, 6);
            }
            break;

        case 'R':
            fill(0, 0, stroke, charH);                          // Left
            fill(0, 0, charW - stroke / 2, stroke);             // Top
            fill(charW - stroke, 0, stroke, charH / 2);         // Top right
            fill(0, charH / 2 - stroke / 2, charW - stroke / 2, stroke);  // Middle
            for (int i = 0; i < charH / 2; i += 4) {            // Diagonal leg
                int dx = (i * (charW - stroke)) / (charH / 2);
                fill(charW / 3 + dx, charH / 2 + i, stroke + 2, 6);
            }
            break;

        case 'C':
            fill(0, 0, charW, stroke);                          // Top
            fill(0, 0, stroke, charH);                          // Left
            fill(0, charH - stroke, charW, stroke);             // Bottom
            break;

        case 'G':
            fill(0, 0, charW, stroke);                          // Top
            fill(0, 0, stroke, charH);                          // Left
            fill(0, charH - stroke, charW, stroke);             // Bottom
            fill(charW - stroke, charH / 2, stroke, charH / 2); // Bottom right
            fill(charW / 2, charH / 2 - stroke / 2, charW / 2, stroke);  // Middle bar
            break;

        case '0':
            fill(0, 0, charW, stroke);                          // Top
            fill(0, 0, stroke, charH);                          // Left
            fill(charW - stroke, 0, stroke, charH);             // Right
            fill(0, charH - stroke, charW, stroke);             // Bottom
            break;

        case '-':
        default:
            fill(4, charH / 2 - stroke / 2, charW - 8, stroke);
            break;
    }

    auto gearBit = [&](int xx, int yy) -> int {
        if (xx < 0 || xx >= charW || yy < 0 || yy >= charH) return 0;
        return glyphBits[yy * charW + xx];
    };

    auto sample = [&](float fx, float fy) -> float {
        int sx = (int)floorf(fx);
        int sy = (int)floorf(fy);
        float tx = fx - (float)sx;
        float ty = fy - (float)sy;
        float v00 = (float)gearBit(sx, sy);
        float v10 = (float)gearBit(sx + 1, sy);
        float v01 = (float)gearBit(sx, sy + 1);
        float v11 = (float)gearBit(sx + 1, sy + 1);
        return v00 * (1.0f - tx) * (1.0f - ty) + v10 * tx * (1.0f - ty)
             + v01 * (1.0f - tx) * ty + v11 * tx * ty;
    };

    int x0 = centerX - charW / 2;
    int y0 = centerY - charH / 2;

    for (int row = 0; row < charH; row++) {
        for (int col = 0; col < charW; col++) {
            float sum = sample(col - 0.25f, row - 0.25f)
                      + sample(col + 0.25f, row - 0.25f)
                      + sample(col - 0.25f, row + 0.25f)
                      + sample(col + 0.25f, row + 0.25f);
            int cov = (int)(sum * 15.0f / 4.0f + 0.5f);
            if (cov > 15) cov = 15;
            if (cov > 0) {
                LCD_DrawPixelBlend(x0 + col, y0 + row, color, bgColor, (uint8_t)cov);
            }
        }
    }
}

// ============================================================================
// Overview screen
// ============================================================================
void drawOverviewScreen() {
    bool rpmChanged = !prevTelemetry.initialized || (int)telemetry.rpm != (int)prevTelemetry.rpm;
    bool speedChanged = !prevTelemetry.initialized || (int)telemetry.speed != (int)prevTelemetry.speed;
    bool gearChanged = !prevTelemetry.initialized || telemetry.gear != prevTelemetry.gear;
    // Reverse-state transition: negative speed means reverse (R indicator)
    bool reverseChanged = (telemetry.speed < 0) != (prevTelemetry.speed < 0);
    bool coolantChanged = !prevTelemetry.initialized || (int)telemetry.coolantTemp != (int)prevTelemetry.coolantTemp;
    bool fuelChanged = !prevTelemetry.initialized || (int)telemetry.fuelLevel != (int)prevTelemetry.fuelLevel;
    bool ambientChanged = !prevTelemetry.initialized || (int)telemetry.ambientTemp != (int)prevTelemetry.ambientTemp;
    bool oilChanged = !prevTelemetry.initialized || telemetry.oilWarning != prevTelemetry.oilWarning;
    bool voltageChanged = !prevTelemetry.initialized ||
                          fabsf(telemetry.batteryVoltage - prevTelemetry.batteryVoltage) >= 0.1f;
    bool mpgChanged = !prevTelemetry.initialized ||
                      fabsf(telemetry.averageMPG - prevTelemetry.averageMPG) >= 0.1f;
    bool instMpgChanged = !prevTelemetry.initialized ||
                          fabsf(telemetry.instantMPG - prevTelemetry.instantMPG) >= 0.1f;
    bool rangeChanged = !prevTelemetry.initialized ||
                        telemetry.rangeMiles != prevTelemetry.rangeMiles;

    int currentBootCountdown = PI_BOOT_COUNTDOWN - ((millis() - bootStartTime) / 1000);
    if (currentBootCountdown < 0) currentBootCountdown = 0;
    bool inBootCountdown = !piDataReceived && currentBootCountdown > 0;
    bool bootCountdownChanged = inBootCountdown && (currentBootCountdown != lastBootCountdown);

    bool wasInCountdown = !piDataReceived && lastBootCountdown > 0;
    bool countdownJustEnded = wasInCountdown && !inBootCountdown;

    lastBootCountdown = currentBootCountdown;

    static bool prevPiDataReceived = false;
    bool justReceivedPiData = piDataReceived && !prevPiDataReceived;
    prevPiDataReceived = piDataReceived;

    if (justReceivedPiData || countdownJustEnded) {
        needsFullRedraw = true;
    }

    bool tpmsChanged = false;
    for (int i = 0; i < 4; i++) {
        if (fabsf(telemetry.tirePressure[i] - prevTelemetry.tirePressure[i]) > 0.05f) {
            tpmsChanged = true;
            break;
        }
    }

    float rpmPercent = telemetry.rpm / 8000.0;
    if (rpmPercent > 1.0) rpmPercent = 1.0;
    float startAngle = 135.0;
    float totalArc = 270.0;
    float endAngle = startAngle + (totalArc * rpmPercent);

    bool arcChanged = !prevTelemetry.initialized ||
                      fabsf(endAngle - prevTelemetry.arcEndAngle) >= 1.0;

    bool anyChange = needsFullRedraw || rpmChanged || speedChanged || gearChanged ||
        coolantChanged || fuelChanged || ambientChanged || oilChanged || tpmsChanged ||
        arcChanged || mpgChanged || instMpgChanged || rangeChanged || voltageChanged || bootCountdownChanged || justReceivedPiData || countdownJustEnded || reverseChanged;

    if (!anyChange) return;

    if (needsFullRedraw) {
        drawBackground();
        prevTelemetry.arcEndAngle = 135.0;
        prevTelemetry.arcColor = MX5_DARKGRAY;
    }

    bool hideTopDuringBoot = !piDataReceived && currentBootCountdown > 0;

    uint16_t rpmColor = LED_BLUE;
    if (telemetry.rpm >= 5500) rpmColor = LED_RED;
    else if (telemetry.rpm >= 4500) rpmColor = LED_ORANGE;
    else if (telemetry.rpm >= 3000) rpmColor = LED_YELLOW;
    else if (telemetry.rpm >= 2000) rpmColor = LED_GREEN;

    if (!hideTopDuringBoot) {
    int arcRadius = 174;
    int arcThickness = 14;

    const int NUM_SEGMENTS = 45;
    const float DEGREES_PER_SEGMENT = 6.0f;

    int currentSegment = (int)(rpmPercent * NUM_SEGMENTS);

    float prevRpmPercent = (prevTelemetry.arcEndAngle - startAngle) / totalArc;
    if (prevRpmPercent < 0) prevRpmPercent = 0;
    if (prevRpmPercent > 1.0f) prevRpmPercent = 1.0f;
    int prevSegment = (int)(prevRpmPercent * NUM_SEGMENTS);

    auto getSegmentColor = [](int segmentIndex) -> uint16_t {
        float segmentRpm = (segmentIndex / 45.0f) * 8000.0f;

        if (segmentRpm < 2000) {
            return LED_BLUE;
        }
        else if (segmentRpm < 3000) {
            float pos = (segmentRpm - 2000) / 1000.0f;
            uint8_t r = 0;
            uint8_t g = (uint8_t)(255 * pos);
            uint8_t b = (uint8_t)(255 * (1.0f - pos));
            return RGB565(r, g, b);
        }
        else if (segmentRpm < 4500) {
            float pos = (segmentRpm - 3000) / 1500.0f;
            uint8_t r = (uint8_t)(255 * pos);
            uint8_t g = 255;
            uint8_t b = 0;
            return RGB565(r, g, b);
        }
        else if (segmentRpm < 5500) {
            float pos = (segmentRpm - 4500) / 1000.0f;
            uint8_t r = 255;
            uint8_t g = (uint8_t)(255 - 127 * pos);
            uint8_t b = 0;
            return RGB565(r, g, b);
        }
        else if (segmentRpm < 6200) {
            float pos = (segmentRpm - 5500) / 700.0f;
            uint8_t r = 255;
            uint8_t g = (uint8_t)(128 * (1.0f - pos));
            uint8_t b = 0;
            return RGB565(r, g, b);
        }
        else {
            return LED_RED;
        }
    };

    auto drawSegment = [&](int segmentIndex, bool colored) {
        float segStartAngle = startAngle + (segmentIndex * DEGREES_PER_SEGMENT);
        float segEndAngle = segStartAngle + DEGREES_PER_SEGMENT;

        uint16_t color = colored ? getSegmentColor(segmentIndex) : MX5_DARKGRAY;

        for (int t = 0; t < arcThickness; t++) {
            int r = arcRadius - t;
            for (float angle = segStartAngle; angle <= segEndAngle; angle += 1.0f) {
                float rad = angle * 3.14159f / 180.0f;
                int x = CENTER_X + (int)(r * cosf(rad));
                int y = CENTER_Y + (int)(r * sinf(rad));
                LCD_DrawPixel(x, y, color);
            }
        }
    };

    if (needsFullRedraw || prevSegment < 0) {
        for (int seg = 0; seg < NUM_SEGMENTS; seg++) {
            drawSegment(seg, seg < currentSegment);
        }
    } else if (currentSegment > prevSegment) {
        for (int seg = prevSegment; seg < currentSegment; seg++) {
            drawSegment(seg, true);
        }
    } else if (currentSegment < prevSegment) {
        for (int seg = currentSegment; seg < prevSegment; seg++) {
            drawSegment(seg, false);
        }
    }

    prevTelemetry.arcEndAngle = startAngle + (currentSegment * DEGREES_PER_SEGMENT);
    prevTelemetry.arcColor = rpmColor;

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
    }

    int boxW = 100;
    int boxH = 35;
    int boxY = 60;
    int rpmBoxX = 80;
    int mphBoxX = 180;

    if (hideTopDuringBoot) {
        static int lastDisplayedMessage = -1;
        static bool loadingBoxDrawn = false;
        bool messageChanged = false;

        if (millis() - lastMessageChange >= 5000) {
            int newMessage;
            do {
                newMessage = random(NUM_LOADING_MESSAGES);
            } while (newMessage == currentLoadingMessage && NUM_LOADING_MESSAGES > 1);
            currentLoadingMessage = newMessage;
            lastMessageChange = millis();
            messageChanged = true;
        }

        if (needsFullRedraw || messageChanged || !loadingBoxDrawn) {
            lastDisplayedMessage = currentLoadingMessage;
            loadingBoxDrawn = true;

            LCD_FillRect(50, boxY - 5, 260, boxH + 15, COLOR_BG);

            int msgBoxX = 70;
            int msgBoxW = 220;
            LCD_FillRoundRect(msgBoxX, boxY - 2, msgBoxW, boxH + 4, 6, COLOR_BG_CARD);
            int bottomY = boxY + boxH + 2;
            for (int i = 0; i < 2; i++) {
                LCD_DrawLine(msgBoxX, bottomY + i, msgBoxX + msgBoxW, bottomY + i, MX5_CYAN);
            }

            const char* msg = LOADING_MESSAGES[currentLoadingMessage];
            int msgLen = strlen(msg);
            int msgWidth = msgLen * 11;
            int msgX = 180 - msgWidth / 2;
            LCD_DrawString(msgX, boxY + 10, msg, MX5_CYAN, COLOR_BG_CARD, 2);
        }
    } else {
    static bool rpmLabelDrawn = false;
    static bool mphLabelDrawn = false;
    if (needsFullRedraw) {
        rpmLabelDrawn = false;
        mphLabelDrawn = false;
        prevTelemetry.rpmStr[0] = '\0';
        prevTelemetry.speedStr[0] = '\0';
        prevTelemetry.rpmDigitCount = 0;
        prevTelemetry.speedDigitCount = 0;
    }

    if (needsFullRedraw || rpmChanged) {
        char rpmStr[8];
        if (!telemetry.hasReceivedTelemetry) {
            snprintf(rpmStr, sizeof(rpmStr), "--");
        } else {
            snprintf(rpmStr, sizeof(rpmStr), "%d", (int)telemetry.rpm);
        }
        int rpmLen = strlen(rpmStr);

        if (!rpmLabelDrawn) {
            LCD_FillRect(rpmBoxX, boxY, boxW, boxH, COLOR_BG);
            int labelWidth = 3 * 6;
            int labelX = rpmBoxX + (boxW - labelWidth) / 2;
            LCD_DrawString(labelX, boxY, "rpm", MX5_GRAY, COLOR_BG, 1);
            rpmLabelDrawn = true;
            int bottomY = boxY + boxH;
            for (int i = 0; i < 2; i++) {
                LCD_DrawLine(rpmBoxX, bottomY + i, rpmBoxX + boxW, bottomY + i, MX5_WHITE);
            }
        }

        int prevRpmLen = prevTelemetry.rpmDigitCount;
        bool digitCountChanged = (rpmLen != prevRpmLen);

        int valueWidth = rpmLen * 18;
        int valueX = rpmBoxX + (boxW - valueWidth) / 2;
        int valueY = boxY + 12;

        if (digitCountChanged || needsFullRedraw) {
            LCD_FillRect(rpmBoxX, valueY, boxW, boxH - 12, COLOR_BG);
            LCD_DrawString(valueX, valueY, rpmStr, MX5_WHITE, COLOR_BG, 3);
        } else {
            for (int i = 0; i < rpmLen; i++) {
                if (rpmStr[i] != prevTelemetry.rpmStr[i]) {
                    int digitX = valueX + (i * 18);
                    LCD_FillRect(digitX, valueY, 18, 24, COLOR_BG);
                    char digitStr[2] = {rpmStr[i], '\0'};
                    LCD_DrawString(digitX, valueY, digitStr, MX5_WHITE, COLOR_BG, 3);
                }
            }
        }

        strncpy(prevTelemetry.rpmStr, rpmStr, sizeof(prevTelemetry.rpmStr));
        prevTelemetry.rpmDigitCount = rpmLen;
    }

    if (needsFullRedraw || speedChanged) {
        char speedStr[8];
        if (!telemetry.hasReceivedTelemetry) {
            snprintf(speedStr, sizeof(speedStr), "--");
        } else {
            snprintf(speedStr, sizeof(speedStr), "%d", (int)telemetry.speed);
        }
        int speedLen = strlen(speedStr);

        if (!mphLabelDrawn) {
            LCD_FillRect(mphBoxX, boxY, boxW, boxH, COLOR_BG);
            int labelWidth = 3 * 6;
            int labelX = mphBoxX + (boxW - labelWidth) / 2;
            LCD_DrawString(labelX, boxY, "mph", MX5_GRAY, COLOR_BG, 1);
            mphLabelDrawn = true;
            int bottomY = boxY + boxH;
            for (int i = 0; i < 2; i++) {
                LCD_DrawLine(mphBoxX, bottomY + i, mphBoxX + boxW, bottomY + i, MX5_WHITE);
            }
        }

        int prevSpeedLen = prevTelemetry.speedDigitCount;
        bool digitCountChanged = (speedLen != prevSpeedLen);

        int valueWidth = speedLen * 18;
        int valueX = mphBoxX + (boxW - valueWidth) / 2;
        int valueY = boxY + 12;

        if (digitCountChanged || needsFullRedraw) {
            LCD_FillRect(mphBoxX, valueY, boxW, boxH - 12, COLOR_BG);
            LCD_DrawString(valueX, valueY, speedStr, MX5_WHITE, COLOR_BG, 3);
        } else {
            for (int i = 0; i < speedLen; i++) {
                if (speedStr[i] != prevTelemetry.speedStr[i]) {
                    int digitX = valueX + (i * 18);
                    LCD_FillRect(digitX, valueY, 18, 24, COLOR_BG);
                    char digitStr[2] = {speedStr[i], '\0'};
                    LCD_DrawString(digitX, valueY, digitStr, MX5_WHITE, COLOR_BG, 3);
                }
            }
        }

        strncpy(prevTelemetry.speedStr, speedStr, sizeof(prevTelemetry.speedStr));
        prevTelemetry.speedDigitCount = speedLen;
    }
    }

    uint16_t gearGlow = MX5_WHITE;

    static uint16_t prevGearGlow = 0;
    bool gearGlowChanged = (gearGlow != prevGearGlow);

    if (needsFullRedraw || gearChanged || reverseChanged || gearGlowChanged || bootCountdownChanged || justReceivedPiData) {
        int gearX = 180;
        int gearY = 180;
        int gearRadius = 50;
        LCD_FillCircle(gearX, gearY, gearRadius, COLOR_BG_CARD);

        for (int r = gearRadius; r > gearRadius - 5; r--) {
            LCD_DrawCircle(gearX, gearY, r, gearGlow);
        }

        char gearStr[4];

        int bootCountdown = currentBootCountdown;
        bool showBootCountdown = inBootCountdown;

        if (showBootCountdown) {
            char countdownStr[4];
            snprintf(countdownStr, sizeof(countdownStr), "%d", bootCountdown);
            int textWidth = strlen(countdownStr) * 12;
            LCD_DrawString(gearX - textWidth/2, gearY - 16, countdownStr, gearGlow, COLOR_BG_CARD, 8);

            prevGearGlow = gearGlow;
        } else {
        if (telemetry.speed < 0 || telemetry.gear == -1) {
            snprintf(gearStr, sizeof(gearStr), "R");
        } else if (!telemetry.engineRunning) {
            if (telemetry.gear == 0) snprintf(gearStr, sizeof(gearStr), "N");
            else snprintf(gearStr, sizeof(gearStr), "%d", telemetry.gear);
        } else if (telemetry.clutchEngaged) {
            switch (clutchDisplayMode) {
                case 0:
                    if (telemetry.gear == 0) snprintf(gearStr, sizeof(gearStr), "N");
                    else snprintf(gearStr, sizeof(gearStr), "%d", telemetry.gear);
                    break;
                case 1:
                    snprintf(gearStr, sizeof(gearStr), "C");
                    break;
                case 2:
                    snprintf(gearStr, sizeof(gearStr), "S");
                    break;
                case 3:
                    snprintf(gearStr, sizeof(gearStr), "-");
                    break;
                default:
                    snprintf(gearStr, sizeof(gearStr), "-");
                    break;
            }
        } else {
            if (telemetry.gear == 0) snprintf(gearStr, sizeof(gearStr), "N");
            else snprintf(gearStr, sizeof(gearStr), "%d", telemetry.gear);
        }
        drawLargeGear(180, 180, gearStr, gearGlow, COLOR_BG_CARD);

        prevGearGlow = gearGlow;
        }
    }

    bool hideDuringBoot = !piDataReceived;

    static bool sideBoxesCleared = false;

    if (hideDuringBoot) {
        if (needsFullRedraw && !sideBoxesCleared) {
            int sideBoxY = CENTER_Y - 36;
            int sideBoxH = 106;
            LCD_FillRoundRect(50, sideBoxY, 70, sideBoxH, 4, COLOR_BG);
            LCD_FillRoundRect(SCREEN_WIDTH - 110, sideBoxY, 70, sideBoxH, 4, COLOR_BG);
            sideBoxesCleared = true;
        }
    } else {
    sideBoxesCleared = false;
    int sideBoxY = CENTER_Y - 36;
    int sideBoxH = 106;

    int leftBoxX = 50;
    int leftBoxW = 70;

    uint16_t coolColor = MX5_CYAN;
    if (telemetry.coolantTemp == 0) coolColor = MX5_RED;
    else if (telemetry.coolantTemp > 220) coolColor = MX5_RED;
    else if (telemetry.coolantTemp > 200) coolColor = MX5_ORANGE;

    if (needsFullRedraw) {
        LCD_FillRoundRect(leftBoxX, sideBoxY, leftBoxW, sideBoxH, 4, COLOR_BG_CARD);
        LCD_FillRect(leftBoxX, sideBoxY, 3, sideBoxH, coolColor);
        LCD_DrawString(leftBoxX + 6, sideBoxY + 3, "COOL", MX5_GRAY, COLOR_BG_CARD, 1);
        LCD_DrawString(leftBoxX + 6, sideBoxY + 42, "OIL", MX5_GRAY, COLOR_BG_CARD, 1);
        LCD_DrawString(leftBoxX + 6, sideBoxY + 76, "VOLT", MX5_GRAY, COLOR_BG_CARD, 1);
    }

    if (needsFullRedraw || coolantChanged) {
        if (coolantChanged && !needsFullRedraw) {
            LCD_FillRect(leftBoxX, sideBoxY, 3, sideBoxH, coolColor);
        }
        LCD_FillRect(leftBoxX + 6, sideBoxY + 16, leftBoxW - 10, 16, COLOR_BG_CARD);
        char coolStr[8];
        snprintf(coolStr, sizeof(coolStr), "%dF", (int)telemetry.coolantTemp);
        LCD_DrawString(leftBoxX + 6, sideBoxY + 16, coolStr, coolColor, COLOR_BG_CARD, 2);
    }

    if (needsFullRedraw || oilChanged) {
        uint16_t oilColor = telemetry.oilWarning ? MX5_RED : MX5_GREEN;
        LCD_FillRect(leftBoxX + 6, sideBoxY + 56, leftBoxW - 10, 16, COLOR_BG_CARD);
        const char* oilStatus = telemetry.oilWarning ? "LOW" : "OK";
        LCD_DrawString(leftBoxX + 6, sideBoxY + 56, oilStatus, oilColor, COLOR_BG_CARD, 2);
    }

    if (needsFullRedraw || voltageChanged) {
        uint16_t voltColor = MX5_GREEN;
        if (telemetry.batteryVoltage < 0.1f) voltColor = MX5_GRAY;
        else if (telemetry.batteryVoltage < 12.0f) voltColor = MX5_RED;
        else if (telemetry.batteryVoltage < 13.0f) voltColor = MX5_YELLOW;
        LCD_FillRect(leftBoxX + 6, sideBoxY + 88, leftBoxW - 10, 16, COLOR_BG_CARD);
        char voltStr[8];
        if (telemetry.batteryVoltage >= 0.1f) {
            snprintf(voltStr, sizeof(voltStr), "%.1fV", telemetry.batteryVoltage);
        } else {
            snprintf(voltStr, sizeof(voltStr), "--.-V");
        }
        LCD_DrawString(leftBoxX + 6, sideBoxY + 88, voltStr, voltColor, COLOR_BG_CARD, 2);
    }

    int gasBoxX = SCREEN_WIDTH - 110;
    int gasBoxW = 70;

    uint16_t gasAccentColor = MX5_GREEN;
    if (telemetry.fuelLevel < 15) gasAccentColor = MX5_RED;
    else if (telemetry.fuelLevel < 25) gasAccentColor = MX5_ORANGE;
    else if (telemetry.fuelLevel < 40) gasAccentColor = MX5_YELLOW;

    uint16_t mpgColor = MX5_GREEN;
    float displayMPG = telemetry.averageMPG > 0 ? telemetry.averageMPG : 26.0f;
    if (displayMPG < 15) mpgColor = MX5_RED;
    else if (displayMPG < 20) mpgColor = MX5_ORANGE;
    else if (displayMPG > 30) mpgColor = MX5_CYAN;

    uint16_t instMpgColor = MX5_CYAN;
    float displayInstMPG = telemetry.instantMPG;
    if (displayInstMPG <= 0.1f) instMpgColor = MX5_GRAY;   // no data / stopped
    else if (displayInstMPG < 15) instMpgColor = MX5_RED;
    else if (displayInstMPG < 20) instMpgColor = MX5_ORANGE;

    uint16_t tankColor = MX5_GREEN;
    if (telemetry.fuelLevel < 15) tankColor = MX5_RED;
    else if (telemetry.fuelLevel < 25) tankColor = MX5_ORANGE;
    else if (telemetry.fuelLevel < 40) tankColor = MX5_YELLOW;

    int displayRange = telemetry.rangeMiles;
    if (displayRange <= 0) {
        if (telemetry.fuelLevel > 0) {
            float mpgForCalc = telemetry.averageMPG > 0 ? telemetry.averageMPG : 26.0f;
            displayRange = (int)(12.7f * (telemetry.fuelLevel / 100.0f) * mpgForCalc);
        }
        if (displayRange <= 0 && prevTelemetry.rangeMiles > 0) {
            displayRange = prevTelemetry.rangeMiles;
        }
    }

    uint16_t rangeColor = MX5_GREEN;
    if (displayRange < 30) rangeColor = MX5_RED;
    else if (displayRange < 60) rangeColor = MX5_ORANGE;
    else if (displayRange < 100) rangeColor = MX5_YELLOW;

    if (needsFullRedraw) {
        LCD_FillRoundRect(gasBoxX, sideBoxY, gasBoxW, sideBoxH, 4, COLOR_BG_CARD);
        LCD_FillRect(gasBoxX, sideBoxY, 3, sideBoxH, gasAccentColor);
        LCD_DrawString(gasBoxX + 6, sideBoxY + 3, "GAS", MX5_GRAY, COLOR_BG_CARD, 1);
    }

    if (fuelChanged && !needsFullRedraw) {
        LCD_FillRect(gasBoxX, sideBoxY, 3, sideBoxH, gasAccentColor);
    }

    if (needsFullRedraw || instMpgChanged) {
        LCD_FillRect(gasBoxX + 6, sideBoxY + 15, gasBoxW - 10, 15, COLOR_BG_CARD);
        char instStr[10];
        if (displayInstMPG > 0.1f) snprintf(instStr, sizeof(instStr), "%.0fmpg", displayInstMPG);
        else snprintf(instStr, sizeof(instStr), "--mpg");
        LCD_DrawString(gasBoxX + 6, sideBoxY + 15, instStr, instMpgColor, COLOR_BG_CARD, 2);
    }

    if (needsFullRedraw || mpgChanged) {
        LCD_FillRect(gasBoxX + 6, sideBoxY + 32, gasBoxW - 10, 15, COLOR_BG_CARD);
        char mpgStr[10];
        snprintf(mpgStr, sizeof(mpgStr), "%.0fmpg", displayMPG);
        LCD_DrawString(gasBoxX + 6, sideBoxY + 32, mpgStr, mpgColor, COLOR_BG_CARD, 2);
    }

    if (needsFullRedraw || fuelChanged) {
        LCD_FillRect(gasBoxX + 6, sideBoxY + 49, gasBoxW - 10, 15, COLOR_BG_CARD);
        char tankStr[10];
        snprintf(tankStr, sizeof(tankStr), "%d%%", (int)telemetry.fuelLevel);
        LCD_DrawString(gasBoxX + 6, sideBoxY + 49, tankStr, tankColor, COLOR_BG_CARD, 2);
    }

    if (needsFullRedraw || rangeChanged) {
        LCD_FillRect(gasBoxX + 6, sideBoxY + 66, gasBoxW - 10, 15, COLOR_BG_CARD);
        char rangeStr[10];
        if (displayRange > 0) {
            snprintf(rangeStr, sizeof(rangeStr), "%dmi", displayRange);
        } else {
            snprintf(rangeStr, sizeof(rangeStr), "--mi");
        }
        LCD_DrawString(gasBoxX + 6, sideBoxY + 66, rangeStr, rangeColor, COLOR_BG_CARD, 2);
    }
    }

    if (needsFullRedraw && navLocked) {
        int lockX = SCREEN_WIDTH - 35;
        int lockY = SCREEN_HEIGHT - 50;
        uint16_t lockColor = MX5_ORANGE;
        LCD_FillRoundRect(lockX - 6, lockY, 12, 10, 2, lockColor);
        LCD_DrawCircle(lockX, lockY - 2, 5, lockColor);
        LCD_DrawCircle(lockX, lockY - 2, 4, lockColor);
        LCD_FillRect(lockX - 3, lockY - 2, 6, 4, COLOR_BG);
        LCD_DrawString(lockX - 9, lockY + 13, "LCK", MX5_ORANGE, COLOR_BG, 1);
    }

    if (needsFullRedraw || tpmsChanged) {
        int tireW = 55;
        int tireH = 38;
        int tireGap = 6;
        int tpmsStartX = CENTER_X - tireW - tireGap/2;
        int tpmsStartY = SCREEN_HEIGHT - 110;

        const char* tireNames[] = {"FL", "FR", "RL", "RR"};
        int tirePositions[4][2] = {{0, 0}, {1, 0}, {0, 1}, {1, 1}};

        for (int i = 0; i < 4; i++) {
            int col = tirePositions[i][0];
            int row = tirePositions[i][1];
            int tireX = tpmsStartX + col * (tireW + tireGap);
            int tireY = tpmsStartY + row * (tireH + tireGap);

            uint16_t tireColor = MX5_GREEN;
            if (telemetry.tirePressure[i] <= 0) tireColor = MX5_DARKGRAY;
            else if (telemetry.tirePressure[i] < 25.0) tireColor = MX5_RED;
            else if (telemetry.tirePressure[i] < 27.0) tireColor = MX5_YELLOW;
            else if (telemetry.tirePressure[i] > 38.0) tireColor = MX5_RED;
            else if (telemetry.tirePressure[i] > 32.0) tireColor = MX5_YELLOW;

            LCD_FillRoundRect(tireX, tireY, tireW, tireH, 3, COLOR_BG_CARD);
            LCD_FillRect(tireX, tireY, 2, tireH, tireColor);

            LCD_DrawString(tireX + 5, tireY + 4, tireNames[i], MX5_GRAY, COLOR_BG_CARD, 1);
            char psiStr[8];
            if (telemetry.tirePressure[i] > 0) snprintf(psiStr, sizeof(psiStr), "%.1f", telemetry.tirePressure[i]);
            else snprintf(psiStr, sizeof(psiStr), "--");
            LCD_DrawString(tireX + 5, tireY + 18, psiStr, tireColor, COLOR_BG_CARD, 2);
        }
    }

    if (needsFullRedraw) {
        drawPageIndicator();
    }

    prevTelemetry.rpm = telemetry.rpm;
    prevTelemetry.speed = telemetry.speed;
    prevTelemetry.gear = telemetry.gear;
    prevTelemetry.gearColor = telemetry.gearColor;
    prevTelemetry.coolantTemp = telemetry.coolantTemp;
    prevTelemetry.fuelLevel = telemetry.fuelLevel;
    prevTelemetry.ambientTemp = telemetry.ambientTemp;
    prevTelemetry.averageMPG = telemetry.averageMPG;
    prevTelemetry.instantMPG = telemetry.instantMPG;
    prevTelemetry.rangeMiles = telemetry.rangeMiles;
    prevTelemetry.engineRunning = telemetry.engineRunning;
    prevTelemetry.connected = telemetry.connected;
    prevTelemetry.oilWarning = telemetry.oilWarning;
    prevTelemetry.headlightsOn = telemetry.headlightsOn;
    prevTelemetry.highBeamsOn = telemetry.highBeamsOn;
    prevTelemetry.batteryVoltage = telemetry.batteryVoltage;
    for (int i = 0; i < 4; i++) {
        prevTelemetry.tirePressure[i] = telemetry.tirePressure[i];
    }
    prevTelemetry.initialized = true;
}

// ============================================================================
// RPM screen
// ============================================================================
void drawRPMScreen() {
    bool valuesChanged = !prevTelemetry.initialized ||
        (int)telemetry.rpm != (int)prevTelemetry.rpm ||
        (int)telemetry.speed != (int)prevTelemetry.speed ||
        telemetry.gear != prevTelemetry.gear;

    if (!needsFullRedraw && !valuesChanged) return;

    if (needsFullRedraw) {
        drawBackground();
    }

    int gearY = 55;

    uint16_t gearColor = MX5_WHITE;

    char gearStr[4];
    if (telemetry.speed < 0 || telemetry.gear == -1) snprintf(gearStr, sizeof(gearStr), "R");
    else if (telemetry.gear == 0) snprintf(gearStr, sizeof(gearStr), "N");
    else snprintf(gearStr, sizeof(gearStr), "%d", telemetry.gear);

    int gearStrLen = strlen(gearStr);
    LCD_DrawString(CENTER_X - gearStrLen * 14, gearY, gearStr, gearColor, COLOR_BG, 4);
    LCD_DrawString(CENTER_X - 18, gearY + 38, "GEAR", MX5_GRAY, COLOR_BG, 1);

    float rpmPercent = constrain(telemetry.rpm / 8000.0, 0, 1);
    int gaugeRadius = 95;
    int gaugeY = CENTER_Y + 25;

    static int prevActiveSegment = -1;
    int numSegments = 20;
    int currentActiveSegment = (int)(rpmPercent * numSegments);
    if (currentActiveSegment > numSegments) currentActiveSegment = numSegments;

    for (int i = 0; i < numSegments; i++) {
        bool wasActive = (i < prevActiveSegment);
        bool isActive = (i < currentActiveSegment);

        if (!needsFullRedraw && wasActive == isActive) continue;

        float segStart = i / (float)numSegments;

        uint16_t segColor;
        if (isActive) {
            float rpmAt = segStart * 8000;
            if (rpmAt >= 5500) segColor = LED_RED;
            else if (rpmAt >= 4500) segColor = LED_ORANGE;
            else if (rpmAt >= 3000) segColor = LED_YELLOW;
            else if (rpmAt >= 2000) segColor = LED_GREEN;
            else segColor = LED_BLUE;
        } else {
            segColor = MX5_DARKGRAY;
        }

        float startAngle = (120 + i * 15) * PI / 180.0;
        float endAngle = (120 + (i + 1) * 15) * PI / 180.0;

        for (float a = startAngle; a < endAngle; a += 0.02) {
            int px = CENTER_X + cos(a) * gaugeRadius;
            int py = gaugeY + sin(a) * gaugeRadius;
            LCD_FillCircle(px, py, 8, segColor);
        }
    }
    prevActiveSegment = currentActiveSegment;

    const char* rpmLabels[] = {"0", "2", "4", "6", "8"};
    for (int i = 0; i < 5; i++) {
        float angle = (120 + i * 75) * PI / 180.0;
        int lx = CENTER_X + cos(angle) * (gaugeRadius + 22) - 4;
        int ly = gaugeY + sin(angle) * (gaugeRadius + 22) - 4;
        LCD_DrawString(lx, ly, rpmLabels[i], MX5_GRAY, COLOR_BG, 1);
    }

    char rpmStr[8];
    snprintf(rpmStr, sizeof(rpmStr), "%d", (int)telemetry.rpm);
    int rpmLen = strlen(rpmStr);
    LCD_DrawString(CENTER_X - rpmLen * 10, gaugeY + 5, rpmStr, MX5_WHITE, COLOR_BG, 3);
    LCD_DrawString(CENTER_X - 12, gaugeY + 35, "RPM", MX5_GRAY, COLOR_BG, 1);

    int speedY = SCREEN_HEIGHT - 50;
    char speedStr[8];
    snprintf(speedStr, sizeof(speedStr), "%d", (int)telemetry.speed);
    int speedLen = strlen(speedStr);
    LCD_DrawString(CENTER_X - speedLen * 10, speedY, speedStr, MX5_CYAN, COLOR_BG, 3);
    LCD_DrawString(CENTER_X - 12, speedY + 28, "MPH", MX5_GRAY, COLOR_BG, 1);

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

    char thrPct[8];
    snprintf(thrPct, sizeof(thrPct), "%d%%", (int)telemetry.throttle);
    LCD_DrawString(throttleX - 2, barY + barH + 5, thrPct, MX5_GREEN, COLOR_BG, 1);

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

    char brkPct[8];
    snprintf(brkPct, sizeof(brkPct), "%d%%", (int)telemetry.brake);
    LCD_DrawString(brakeX, barY + barH + 5, brkPct, MX5_RED, COLOR_BG, 1);

    drawPageIndicator();

    prevTelemetry.rpm = telemetry.rpm;
    prevTelemetry.speed = telemetry.speed;
    prevTelemetry.gear = telemetry.gear;
    prevTelemetry.gearColor = telemetry.gearColor;
    prevTelemetry.initialized = true;
}

// ============================================================================
// TPMS screen
// ============================================================================
void drawTPMSScreen() {
    if (!needsFullRedraw) return;

    drawBackground();

    LCD_DrawString(CENTER_X - 24, 25, "TPMS", MX5_WHITE, COLOR_BG, 2);

    int carW = 60, carH = 110;
    int carX = CENTER_X - carW/2;
    int carY = CENTER_Y - carH/2;

    LCD_FillRoundRect(carX, carY, carW, carH, 12, COLOR_BG_CARD);
    LCD_DrawRoundRect(carX, carY, carW, carH, 12, MX5_GRAY);

    LCD_DrawLine(carX + 8, carY + 15, carX + carW - 8, carY + 15, MX5_ACCENT);
    LCD_DrawLine(carX + 5, carY + 25, carX + carW - 5, carY + 25, MX5_ACCENT);

    LCD_DrawLine(carX + 8, carY + carH - 15, carX + carW - 8, carY + carH - 15, MX5_ACCENT);
    LCD_DrawLine(carX + 5, carY + carH - 25, carX + carW - 5, carY + carH - 25, MX5_ACCENT);

    LCD_DrawLine(carX + carW/2, carY + 30, carX + carW/2, carY + carH - 30, MX5_DARKGRAY);

    const int tireW = 26, tireH = 40;
    const int tireOffsetX = 55, tireOffsetY = 38;

    auto getTireColor = [](float psi) -> uint16_t {
        if (psi <= 0.0f) return MX5_DARKGRAY;
        if (psi < 25.0) return MX5_RED;
        if (psi < 27.0) return MX5_YELLOW;
        if (psi > 38.0) return MX5_RED;
        if (psi > 32.0) return MX5_YELLOW;
        return MX5_GREEN;
    };

    auto drawTire = [&](int x, int y, uint16_t color) {
        LCD_FillRoundRect(x, y, tireW, tireH, 6, color);
        LCD_DrawRoundRect(x, y, tireW, tireH, 6, MX5_WHITE);
        for (int i = 8; i < tireH - 8; i += 8) {
            LCD_FillRoundRect(x + 4, y + i, tireW - 8, 3, 1, COLOR_BG_CARD);
        }
    };

    uint16_t flColor = getTireColor(telemetry.tirePressure[0]);
    int flX = CENTER_X - tireOffsetX - tireW/2;
    int flY = CENTER_Y - tireOffsetY - tireH/2;
    drawTire(flX, flY, flColor);

    uint16_t frColor = getTireColor(telemetry.tirePressure[1]);
    int frX = CENTER_X + tireOffsetX - tireW/2;
    int frY = CENTER_Y - tireOffsetY - tireH/2;
    drawTire(frX, frY, frColor);

    uint16_t rlColor = getTireColor(telemetry.tirePressure[2]);
    int rlX = CENTER_X - tireOffsetX - tireW/2;
    int rlY = CENTER_Y + tireOffsetY - tireH/2;
    drawTire(rlX, rlY, rlColor);

    uint16_t rrColor = getTireColor(telemetry.tirePressure[3]);
    int rrX = CENTER_X + tireOffsetX - tireW/2;
    int rrY = CENTER_Y + tireOffsetY - tireH/2;
    drawTire(rrX, rrY, rrColor);

    char psiStr[8];
    char tempStr[8];

    if (telemetry.tirePressure[0] > 0) snprintf(psiStr, sizeof(psiStr), "%.1f", telemetry.tirePressure[0]);
    else snprintf(psiStr, sizeof(psiStr), "--");
    if (telemetry.tireTemp[0] > 0) snprintf(tempStr, sizeof(tempStr), "%.1fF", telemetry.tireTemp[0]);
    else snprintf(tempStr, sizeof(tempStr), "--");
    uint16_t fl_time_color = (tpmsLastUpdateStr[0][0] != '-') ? MX5_GREEN : MX5_DARKGRAY;
    LCD_DrawString(flX - 50, flY + 2, psiStr, flColor, COLOR_BG, 2);
    LCD_DrawString(flX - 50, flY + 20, "PSI", MX5_GRAY, COLOR_BG, 1);
    LCD_DrawString(flX - 50, flY + 32, tempStr, MX5_ACCENT, COLOR_BG, 1);
    LCD_DrawString(flX - 66, flY - 14, "FL", MX5_GRAY, COLOR_BG, 1);
    LCD_DrawString(flX - 50, flY - 14, tpmsLastUpdateStr[0], fl_time_color, COLOR_BG, 1);

    if (telemetry.tirePressure[1] > 0) snprintf(psiStr, sizeof(psiStr), "%.1f", telemetry.tirePressure[1]);
    else snprintf(psiStr, sizeof(psiStr), "--");
    if (telemetry.tireTemp[1] > 0) snprintf(tempStr, sizeof(tempStr), "%.1fF", telemetry.tireTemp[1]);
    else snprintf(tempStr, sizeof(tempStr), "--");
    uint16_t fr_time_color = (tpmsLastUpdateStr[1][0] != '-') ? MX5_GREEN : MX5_DARKGRAY;
    LCD_DrawString(frX + tireW + 8, frY + 2, psiStr, frColor, COLOR_BG, 2);
    LCD_DrawString(frX + tireW + 8, frY + 20, "PSI", MX5_GRAY, COLOR_BG, 1);
    LCD_DrawString(frX + tireW + 8, frY + 32, tempStr, MX5_ACCENT, COLOR_BG, 1);
    LCD_DrawString(frX + 6, frY - 14, "FR", MX5_GRAY, COLOR_BG, 1);
    LCD_DrawString(frX + 24, frY - 14, tpmsLastUpdateStr[1], fr_time_color, COLOR_BG, 1);

    if (telemetry.tirePressure[2] > 0) snprintf(psiStr, sizeof(psiStr), "%.1f", telemetry.tirePressure[2]);
    else snprintf(psiStr, sizeof(psiStr), "--");
    if (telemetry.tireTemp[2] > 0) snprintf(tempStr, sizeof(tempStr), "%.1fF", telemetry.tireTemp[2]);
    else snprintf(tempStr, sizeof(tempStr), "--");
    uint16_t rl_time_color = (tpmsLastUpdateStr[2][0] != '-') ? MX5_GREEN : MX5_DARKGRAY;
    LCD_DrawString(rlX - 50, rlY + 2, psiStr, rlColor, COLOR_BG, 2);
    LCD_DrawString(rlX - 50, rlY + 20, "PSI", MX5_GRAY, COLOR_BG, 1);
    LCD_DrawString(rlX - 50, rlY + 32, tempStr, MX5_ACCENT, COLOR_BG, 1);
    LCD_DrawString(rlX - 66, rlY + tireH + 4, "RL", MX5_GRAY, COLOR_BG, 1);
    LCD_DrawString(rlX - 50, rlY + tireH + 4, tpmsLastUpdateStr[2], rl_time_color, COLOR_BG, 1);

    if (telemetry.tirePressure[3] > 0) snprintf(psiStr, sizeof(psiStr), "%.1f", telemetry.tirePressure[3]);
    else snprintf(psiStr, sizeof(psiStr), "--");
    if (telemetry.tireTemp[3] > 0) snprintf(tempStr, sizeof(tempStr), "%.1fF", telemetry.tireTemp[3]);
    else snprintf(tempStr, sizeof(tempStr), "--");
    uint16_t rr_time_color = (tpmsLastUpdateStr[3][0] != '-') ? MX5_GREEN : MX5_DARKGRAY;
    LCD_DrawString(rrX + tireW + 8, rrY + 2, psiStr, rrColor, COLOR_BG, 2);
    LCD_DrawString(rrX + tireW + 8, rrY + 20, "PSI", MX5_GRAY, COLOR_BG, 1);
    LCD_DrawString(rrX + tireW + 8, rrY + 32, tempStr, MX5_ACCENT, COLOR_BG, 1);
    LCD_DrawString(rrX + 6, rrY + tireH + 4, "RR", MX5_GRAY, COLOR_BG, 1);
    LCD_DrawString(rrX + 24, rrY + tireH + 4, tpmsLastUpdateStr[3], rr_time_color, COLOR_BG, 1);

    bool allGood = (flColor == MX5_GREEN && frColor == MX5_GREEN &&
                   rlColor == MX5_GREEN && rrColor == MX5_GREEN);
    const char* statusText = allGood ? "ALL TIRES OK" : "CHECK PRESSURE";
    uint16_t statusColor = allGood ? MX5_GREEN : MX5_ORANGE;
    LCD_DrawString(CENTER_X - 54, SCREEN_HEIGHT - 50, statusText, statusColor, COLOR_BG, 1);

    drawPageIndicator();
}

// ============================================================================
// Engine screen
// ============================================================================
void drawEngineScreen() {
    if (!needsFullRedraw) return;

    drawBackground();

    LCD_DrawString(CENTER_X - 36, 20, "ENGINE", MX5_WHITE, COLOR_BG, 2);

    int cardW = 140, cardH = 70;
    int gap = 12;
    int startX = CENTER_X - cardW - gap/2;
    int startY = CENTER_Y - cardH - gap/2 - 5;

    uint16_t coolantColor = MX5_BLUE;
    if (telemetry.coolantTemp > 230) coolantColor = MX5_RED;
    else if (telemetry.coolantTemp > 215) coolantColor = MX5_ORANGE;

    LCD_FillRoundRect(startX, startY, cardW, cardH, CARD_RADIUS, COLOR_BG_CARD);
    LCD_DrawRoundRect(startX, startY, cardW, cardH, CARD_RADIUS, coolantColor);

    LCD_DrawString(startX + 10, startY + 8, "COOLANT", MX5_GRAY, COLOR_BG_CARD, 1);

    char tempStr[12];
    snprintf(tempStr, sizeof(tempStr), "%d F", (int)telemetry.coolantTemp);
    LCD_DrawString(startX + 10, startY + 24, tempStr, coolantColor, COLOR_BG_CARD, 2);

    float coolantPct = constrain((telemetry.coolantTemp - 100) / 150.0, 0, 1);
    LCD_FillRoundRect(startX + 10, startY + cardH - 20, cardW - 20, 12, 4, MX5_DARKGRAY);
    int coolFillW = (int)((cardW - 20) * coolantPct);
    if (coolFillW > 8) {
        LCD_FillRoundRect(startX + 10, startY + cardH - 20, coolFillW, 12, 4, coolantColor);
    }

    uint16_t oilColor = MX5_ORANGE;
    if (telemetry.oilTemp > 260) oilColor = MX5_RED;
    else if (telemetry.oilTemp < 180) oilColor = MX5_BLUE;

    int rightX = startX + cardW + gap;
    LCD_FillRoundRect(rightX, startY, cardW, cardH, CARD_RADIUS, COLOR_BG_CARD);
    LCD_DrawRoundRect(rightX, startY, cardW, cardH, CARD_RADIUS, oilColor);

    LCD_DrawString(rightX + 10, startY + 8, "OIL TEMP", MX5_GRAY, COLOR_BG_CARD, 1);

    snprintf(tempStr, sizeof(tempStr), "%d F", (int)telemetry.oilTemp);
    LCD_DrawString(rightX + 10, startY + 24, tempStr, oilColor, COLOR_BG_CARD, 2);

    float oilPct = constrain((telemetry.oilTemp - 150) / 150.0, 0, 1);
    LCD_FillRoundRect(rightX + 10, startY + cardH - 20, cardW - 20, 12, 4, MX5_DARKGRAY);
    int oilFillW = (int)((cardW - 20) * oilPct);
    if (oilFillW > 8) {
        LCD_FillRoundRect(rightX + 10, startY + cardH - 20, oilFillW, 12, 4, oilColor);
    }

    uint16_t fuelColor = MX5_YELLOW;
    if (telemetry.fuelLevel < 15) fuelColor = MX5_RED;
    else if (telemetry.fuelLevel < 25) fuelColor = MX5_ORANGE;

    int bottomY = CENTER_Y + gap/2 - 5;
    LCD_FillRoundRect(startX, bottomY, cardW, cardH, CARD_RADIUS, COLOR_BG_CARD);
    LCD_DrawRoundRect(startX, bottomY, cardW, cardH, CARD_RADIUS, fuelColor);

    LCD_DrawString(startX + 10, bottomY + 8, "FUEL", MX5_GRAY, COLOR_BG_CARD, 1);

    char fuelStr[12];
    snprintf(fuelStr, sizeof(fuelStr), "%d%%", (int)telemetry.fuelLevel);
    LCD_DrawString(startX + 10, bottomY + 24, fuelStr, fuelColor, COLOR_BG_CARD, 2);

    LCD_FillRoundRect(startX + 10, bottomY + cardH - 20, cardW - 20, 12, 4, MX5_DARKGRAY);
    int fuelFillW = (int)((cardW - 20) * telemetry.fuelLevel / 100.0);
    if (fuelFillW > 8) {
        LCD_FillRoundRect(startX + 10, bottomY + cardH - 20, fuelFillW, 12, 4, fuelColor);
    }

    uint16_t ambientColor = MX5_GREEN;
    if (telemetry.ambientTemp < 32) ambientColor = MX5_CYAN;
    else if (telemetry.ambientTemp > 95) ambientColor = MX5_RED;
    else if (telemetry.ambientTemp > 85) ambientColor = MX5_ORANGE;

    LCD_FillRoundRect(rightX, bottomY, cardW, cardH, CARD_RADIUS, COLOR_BG_CARD);
    LCD_DrawRoundRect(rightX, bottomY, cardW, cardH, CARD_RADIUS, ambientColor);

    LCD_DrawString(rightX + 10, bottomY + 8, "AMBIENT", MX5_GRAY, COLOR_BG_CARD, 1);

    char ambStr[12];
    snprintf(ambStr, sizeof(ambStr), "%.0f°F", telemetry.ambientTemp);
    LCD_DrawString(rightX + 10, bottomY + 24, ambStr, ambientColor, COLOR_BG_CARD, 2);

    drawPageIndicator();
}

// ============================================================================
// G-Force screen
// ============================================================================
void drawGForceScreen() {
    static int prevGX = CENTER_X;
    static int prevGY = CENTER_Y;
    static int prevBallRadius = 14;
    static float prevPitch = 0;
    static float prevRoll = 0;
    static float prevForwardAccel = 0;
    static bool firstDraw = true;

    float maxDegrees = 10.0;
    int maxRadius = 120;
    float pixelsPerDegree = maxRadius / maxDegrees;

    int gX = CENTER_X + (int)(orientationRoll * pixelsPerDegree);
    int gY = CENTER_Y + (int)(orientationPitch * pixelsPerDegree);

    float forwardAccel = telemetry.linearAccelY;
    int ballRadius = 14 + (int)(forwardAccel * 10);
    ballRadius = max(6, min(24, ballRadius));

    float dist = sqrt(pow(gX - CENTER_X, 2) + pow(gY - CENTER_Y, 2));
    if (dist > maxRadius) {
        float scale = maxRadius / dist;
        gX = CENTER_X + (int)((gX - CENTER_X) * scale);
        gY = CENTER_Y + (int)((gY - CENTER_Y) * scale);
    }

    uint16_t dotColor = MX5_GREEN;
    if (forwardAccel > 0.5) dotColor = MX5_RED;
    else if (forwardAccel > 0.2) dotColor = MX5_ORANGE;
    else if (forwardAccel < -0.5) dotColor = MX5_CYAN;
    else if (forwardAccel < -0.2) dotColor = MX5_YELLOW;

    if (needsFullRedraw || firstDraw) {
        firstDraw = false;
        drawBackground();

        LCD_DrawString(CENTER_X - 24, 20, "TILT", MX5_WHITE, COLOR_BG, 2);

        LCD_DrawCircle(CENTER_X, CENTER_Y, 30, MX5_DARKGRAY);
        LCD_DrawCircle(CENTER_X, CENTER_Y, 60, MX5_DARKGRAY);
        LCD_DrawCircle(CENTER_X, CENTER_Y, 120, MX5_DARKGRAY);

        LCD_DrawLine(CENTER_X - 130, CENTER_Y, CENTER_X + 130, CENTER_Y, MX5_DARKGRAY);
        LCD_DrawLine(CENTER_X, CENTER_Y - 130, CENTER_X, CENTER_Y + 130, MX5_DARKGRAY);

        LCD_DrawString(CENTER_X + 33, CENTER_Y - 6, "2.5\xF8", MX5_GRAY, COLOR_BG, 1);
        LCD_DrawString(CENTER_X + 63, CENTER_Y - 6, "5\xF8", MX5_GRAY, COLOR_BG, 1);
        LCD_DrawString(CENTER_X + 123, CENTER_Y - 6, "10\xF8", MX5_GRAY, COLOR_BG, 1);

        LCD_FillCircle(CENTER_X, CENTER_Y, 3, MX5_WHITE);

        LCD_FillCircle(gX, gY, ballRadius, dotColor);
        LCD_DrawCircle(gX, gY, ballRadius, MX5_WHITE);
        LCD_DrawCircle(gX, gY, ballRadius + 1, MX5_WHITE);

        int infoY = SCREEN_HEIGHT - 55;
        LCD_FillRoundRect(CENTER_X - 100, infoY, 200, 50, 10, COLOR_BG_CARD);
        LCD_DrawRoundRect(CENTER_X - 100, infoY, 200, 50, 10, MX5_ACCENT);

        char gStr[20];
        snprintf(gStr, sizeof(gStr), "Pitch:%+.1f\xF8", orientationPitch);
        LCD_DrawString(CENTER_X - 90, infoY + 6, gStr, MX5_CYAN, COLOR_BG_CARD, 1);

        snprintf(gStr, sizeof(gStr), "Roll:%+.1f\xF8", orientationRoll);
        LCD_DrawString(CENTER_X - 90, infoY + 20, gStr, MX5_GREEN, COLOR_BG_CARD, 1);

        snprintf(gStr, sizeof(gStr), "Fwd:%+.2fG", forwardAccel);
        LCD_DrawString(CENTER_X - 90, infoY + 34, gStr, dotColor, COLOR_BG_CARD, 1);

        snprintf(gStr, sizeof(gStr), "%+.1fG", forwardAccel);
        LCD_DrawString(CENTER_X + 30, infoY + 16, gStr, dotColor, COLOR_BG_CARD, 2);

        drawPageIndicator();

        prevGX = gX;
        prevGY = gY;
        prevPitch = orientationPitch;
        prevRoll = orientationRoll;
        prevForwardAccel = forwardAccel;
        prevBallRadius = ballRadius;
    } else {
        bool ballMoved = (abs(gX - prevGX) > 2 || abs(gY - prevGY) > 2);
        bool ballSizeChanged = (abs(ballRadius - prevBallRadius) > 2);

        static unsigned long lastValueUpdate = 0;
        bool valuesChanged = (millis() - lastValueUpdate > 100) &&
                             (abs(orientationPitch - prevPitch) > 0.3 ||
                              abs(orientationRoll - prevRoll) > 0.3 ||
                              abs(forwardAccel - prevForwardAccel) > 0.05);

        if (ballMoved || ballSizeChanged) {
            int eraseSize = prevBallRadius + 3;
            LCD_FillRect(prevGX - eraseSize, prevGY - eraseSize,
                        eraseSize * 2, eraseSize * 2, COLOR_BG);

            if (abs(prevGY - CENTER_Y) < eraseSize + 2) {
                LCD_DrawLine(prevGX - eraseSize - 5, CENTER_Y,
                            prevGX + eraseSize + 5, CENTER_Y, MX5_DARKGRAY);
            }
            if (abs(prevGX - CENTER_X) < eraseSize + 2) {
                LCD_DrawLine(CENTER_X, prevGY - eraseSize - 5,
                            CENTER_X, prevGY + eraseSize + 5, MX5_DARKGRAY);
            }

            float prevDist = sqrt(pow(prevGX - CENTER_X, 2) + pow(prevGY - CENTER_Y, 2));
            int gridRadii[3] = {30, 60, 120};
            for (int g = 0; g < 3; g++) {
                if (abs(prevDist - gridRadii[g]) < eraseSize + 5) {
                    LCD_DrawCircle(CENTER_X, CENTER_Y, gridRadii[g], MX5_DARKGRAY);
                }
            }

            if (prevDist < eraseSize + 5) {
                LCD_FillCircle(CENTER_X, CENTER_Y, 3, MX5_WHITE);
            }

            LCD_FillCircle(gX, gY, ballRadius, dotColor);
            LCD_DrawCircle(gX, gY, ballRadius, MX5_WHITE);

            prevGX = gX;
            prevGY = gY;
            prevBallRadius = ballRadius;
        }

        if (valuesChanged) {
            lastValueUpdate = millis();
            int infoY = SCREEN_HEIGHT - 55;

            LCD_FillRect(CENTER_X - 92, infoY + 4, 80, 44, COLOR_BG_CARD);
            LCD_FillRect(CENTER_X + 28, infoY + 14, 65, 24, COLOR_BG_CARD);

            char gStr[20];
            snprintf(gStr, sizeof(gStr), "Pitch:%+.1f\xF8", orientationPitch);
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
// Helper drawing functions
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
// Diagnostics screen
// ============================================================================
void drawDiagnosticsScreen() {
    if (!needsFullRedraw) return;

    drawBackground();

    int startY = 40;
    int itemH = 42;
    int itemGap = 6;
    int itemW = 280;
    int startX = CENTER_X - itemW/2;

    struct DiagItem {
        const char* name;
        bool isWarning;
        bool hasData;
        uint16_t colorOk;
        uint16_t colorWarn;
    };

    DiagItem items[] = {
        {"CHECK ENGINE", telemetry.checkEngine, telemetry.hasDiagnosticData, MX5_GREEN, MX5_RED},
        {"ABS SYSTEM", telemetry.absWarning, telemetry.hasDiagnosticData, MX5_GREEN, MX5_ORANGE},
        {"OIL PRESSURE", telemetry.oilWarning, telemetry.hasDiagnosticData, MX5_GREEN, MX5_RED},
        {"BATTERY", telemetry.batteryWarning, telemetry.hasDiagnosticData, MX5_GREEN, MX5_YELLOW},
        {"ENGINE RUN", !telemetry.engineRunning, telemetry.hasDiagnosticData, MX5_GREEN, MX5_RED},
        {"CONNECTION", !telemetry.connected, true, MX5_GREEN, MX5_ORANGE},
    };

    for (int i = 0; i < 6; i++) {
        int y = startY + i * (itemH + itemGap);

        uint16_t statusColor;
        const char* statusText;

        if (!items[i].hasData) {
            statusColor = MX5_GRAY;
            statusText = "NO DATA";
        } else if (items[i].isWarning) {
            statusColor = items[i].colorWarn;
            statusText = "WARN";
        } else {
            statusColor = items[i].colorOk;
            statusText = "OK";
        }

        LCD_FillRoundRect(startX, y, itemW, itemH, CARD_RADIUS, COLOR_BG_CARD);

        if (!items[i].hasData) {
            LCD_DrawString(startX + 18, y + 12, "?", MX5_GRAY, COLOR_BG_CARD, 2);
        } else if (items[i].isWarning) {
            LCD_DrawLine(startX + 15, y + 13, startX + 30, y + itemH - 13, statusColor);
            LCD_DrawLine(startX + 16, y + 13, startX + 31, y + itemH - 13, statusColor);
            LCD_DrawLine(startX + 30, y + 13, startX + 15, y + itemH - 13, statusColor);
            LCD_DrawLine(startX + 31, y + 13, startX + 16, y + itemH - 13, statusColor);
        } else {
            LCD_DrawLine(startX + 15, y + itemH/2, startX + 22, y + itemH - 12, statusColor);
            LCD_DrawLine(startX + 16, y + itemH/2, startX + 23, y + itemH - 12, statusColor);
            LCD_DrawLine(startX + 22, y + itemH - 12, startX + 35, y + 12, statusColor);
            LCD_DrawLine(startX + 23, y + itemH - 12, startX + 36, y + 12, statusColor);
        }

        LCD_DrawString(startX + 50, y + 12, items[i].name, MX5_WHITE, COLOR_BG_CARD, 2);

        LCD_DrawString(startX + 50, y + itemH - 20, statusText, statusColor, COLOR_BG_CARD, 1);

        int circleX = startX + itemW - 25;
        int circleY = y + itemH/2;
        LCD_FillCircle(circleX, circleY, 12, statusColor);
        LCD_DrawCircle(circleX, circleY, 12, MX5_WHITE);

        if (items[i].hasData && !items[i].isWarning) {
            LCD_FillCircle(circleX, circleY, 5, MX5_WHITE);
        }

        LCD_DrawRoundRect(startX, y, itemW, itemH, CARD_RADIUS, statusColor);
    }

    drawPageIndicator();
}

// ============================================================================
// System screen
// ============================================================================
void drawSystemScreen() {
    if (!needsFullRedraw) return;

    drawBackground();

    int startY = 40;
    int itemH = 50;
    int itemGap = 8;
    int itemW = 290;
    int startX = CENTER_X - itemW/2;

    uint16_t imuColor = imuAvailable ? MX5_GREEN : MX5_RED;
    LCD_FillRoundRect(startX, startY, itemW, itemH, CARD_RADIUS, COLOR_BG_CARD);
    LCD_DrawRoundRect(startX, startY, itemW, itemH, CARD_RADIUS, imuColor);

    int iconX = startX + 30;
    int iconY = startY + itemH/2;
    LCD_DrawRect(iconX - 10, iconY - 10, 20, 20, imuColor);
    LCD_DrawLine(iconX, iconY - 15, iconX, iconY + 15, imuColor);
    LCD_DrawLine(iconX - 15, iconY, iconX + 15, iconY, imuColor);
    LCD_FillCircle(iconX, iconY, 4, imuColor);

    LCD_DrawString(startX + 55, startY + 10, "IMU SENSOR", MX5_WHITE, COLOR_BG_CARD, 2);
    const char* imuStatus = imuAvailable ? "READY" : "OFFLINE";
    LCD_DrawString(startX + 55, startY + 32, imuStatus, imuColor, COLOR_BG_CARD, 1);

    LCD_FillCircle(startX + itemW - 30, iconY, 10, imuColor);

    startY += itemH + itemGap;

    uint16_t serialColor = telemetry.connected ? MX5_GREEN : MX5_ORANGE;
    LCD_FillRoundRect(startX, startY, itemW, itemH, CARD_RADIUS, COLOR_BG_CARD);
    LCD_DrawRoundRect(startX, startY, itemW, itemH, CARD_RADIUS, serialColor);

    iconY = startY + itemH/2;
    LCD_FillRect(iconX - 8, iconY - 6, 16, 12, serialColor);
    LCD_FillRect(iconX - 4, iconY + 6, 8, 4, serialColor);
    LCD_FillRect(iconX - 2, iconY - 10, 4, 4, serialColor);

    LCD_DrawString(startX + 55, startY + 10, "PI SERIAL", MX5_WHITE, COLOR_BG_CARD, 2);
    const char* serialStatus = telemetry.connected ? "CONNECTED" : "WAITING";
    LCD_DrawString(startX + 55, startY + 32, serialStatus, serialColor, COLOR_BG_CARD, 1);

    LCD_FillCircle(startX + itemW - 30, iconY, 10, serialColor);

    startY += itemH + itemGap;

    LCD_FillRoundRect(startX, startY, itemW, itemH, CARD_RADIUS, COLOR_BG_CARD);
    LCD_DrawRoundRect(startX, startY, itemW, itemH, CARD_RADIUS, MX5_ACCENT);

    iconY = startY + itemH/2;
    LCD_DrawRect(iconX - 12, iconY - 8, 24, 16, MX5_ACCENT);
    LCD_FillRect(iconX - 10, iconY - 6, 20, 12, MX5_ACCENT);
    LCD_FillRect(iconX - 4, iconY + 8, 8, 3, MX5_ACCENT);
    LCD_FillRect(iconX - 8, iconY + 11, 16, 2, MX5_ACCENT);

    LCD_DrawString(startX + 55, startY + 10, "DISPLAY", MX5_WHITE, COLOR_BG_CARD, 2);
    LCD_DrawString(startX + 55, startY + 32, "360x360 ST77916", MX5_ACCENT, COLOR_BG_CARD, 1);

    LCD_FillCircle(startX + itemW - 30, iconY, 10, MX5_ACCENT);

    startY += itemH + itemGap;

    LCD_FillRoundRect(startX, startY, itemW, itemH, CARD_RADIUS, COLOR_BG_CARD);
    LCD_DrawRoundRect(startX, startY, itemW, itemH, CARD_RADIUS, MX5_PURPLE);

    iconY = startY + itemH/2;
    LCD_FillRect(iconX - 8, iconY - 10, 16, 20, MX5_PURPLE);
    for (int p = 0; p < 4; p++) {
        LCD_FillRect(iconX - 12, iconY - 8 + p * 5, 4, 3, MX5_PURPLE);
        LCD_FillRect(iconX + 8, iconY - 8 + p * 5, 4, 3, MX5_PURPLE);
    }

    LCD_DrawString(startX + 55, startY + 10, "FREE MEMORY", MX5_WHITE, COLOR_BG_CARD, 2);
    char memStr[16];
    snprintf(memStr, sizeof(memStr), "%d KB", ESP.getFreeHeap() / 1024);
    LCD_DrawString(startX + 55, startY + 32, memStr, MX5_PURPLE, COLOR_BG_CARD, 1);

    LCD_FillCircle(startX + itemW - 30, iconY, 10, MX5_PURPLE);

    startY += itemH + itemGap;

    LCD_FillRoundRect(startX, startY, itemW, itemH, CARD_RADIUS, COLOR_BG_CARD);
    LCD_DrawRoundRect(startX, startY, itemW, itemH, CARD_RADIUS, MX5_CYAN);

    iconY = startY + itemH/2;
    LCD_DrawCircle(iconX, iconY, 10, MX5_CYAN);
    LCD_DrawCircle(iconX, iconY, 11, MX5_CYAN);
    LCD_DrawLine(iconX, iconY, iconX, iconY - 6, MX5_CYAN);
    LCD_DrawLine(iconX, iconY, iconX + 5, iconY + 2, MX5_CYAN);
    LCD_FillCircle(iconX, iconY, 2, MX5_CYAN);

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

// ============================================================================
// Settings screen
// ============================================================================
void drawSettingsItem(int index, int screenY, int itemW, int startX, bool isSelected) {
    int itemH = 52;
    int toggleW = 50;
    int toggleH = 24;
    int iconX = startX + 30;
    int iconY = screenY + itemH/2;

    uint16_t borderColors[] = {
        MX5_PURPLE,
        MX5_YELLOW,
        MX5_CYAN,
        MX5_RED,
        MX5_ORANGE,
        MX5_ACCENT,
        MX5_GREEN,
        MX5_BLUE,
        MX5_PURPLE,
    };

    uint16_t borderColor = borderColors[index];
    uint16_t bgColor;
    if (isSelected) {
        uint8_t r = ((borderColor >> 11) & 0x1F) * 2;
        uint8_t g = ((borderColor >> 5) & 0x3F);
        uint8_t b = (borderColor & 0x1F) * 2;
        bgColor = RGB565(r + 20, g/4 + 20, b + 20);
    } else {
        bgColor = COLOR_BG_CARD;
    }

    LCD_FillRoundRect(startX, screenY, itemW, itemH, CARD_RADIUS, bgColor);
    LCD_DrawRoundRect(startX, screenY, itemW, itemH, CARD_RADIUS, borderColor);
    if (isSelected) {
        LCD_DrawRoundRect(startX + 1, screenY + 1, itemW - 2, itemH - 2, CARD_RADIUS - 1, borderColor);
        LCD_DrawRoundRect(startX + 2, screenY + 2, itemW - 4, itemH - 4, CARD_RADIUS - 2, borderColor);
    }

    char valueStr[16];
    int valueX = startX + itemW - 70;
    int toggleX = startX + itemW - 70;

    switch (index) {
        case 0:
            LCD_FillRoundRect(iconX - 10, iconY - 10, 20, 20, 4, MX5_PURPLE);
            LCD_DrawLine(iconX - 4, iconY - 6, iconX - 4, iconY + 6, bgColor);
            LCD_DrawLine(iconX - 4, iconY - 6, iconX + 6, iconY, bgColor);
            LCD_DrawLine(iconX - 4, iconY + 6, iconX + 6, iconY, bgColor);
            LCD_DrawString(startX + 55, screenY + 10, "DATA SOURCE", MX5_WHITE, bgColor, 2);
            LCD_DrawString(startX + 55, screenY + 32, settings.demoMode ? "DEMO" : "CAN BUS", MX5_PURPLE, bgColor, 1);
            if (settings.demoMode) {
                LCD_FillRoundRect(toggleX, iconY - toggleH/2, toggleW, toggleH, 12, MX5_GREEN);
                LCD_FillCircle(toggleX + toggleW - 12, iconY, 9, MX5_WHITE);
            } else {
                LCD_FillRoundRect(toggleX, iconY - toggleH/2, toggleW, toggleH, 12, MX5_DARKGRAY);
                LCD_FillCircle(toggleX + 12, iconY, 9, MX5_WHITE);
            }
            break;

        case 1:
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

        case 2:
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

        case 3:
            LCD_FillCircle(iconX, iconY, 10, MX5_RED);
            LCD_FillCircle(iconX, iconY, 6, bgColor);
            LCD_FillCircle(iconX, iconY, 3, MX5_RED);
            LCD_DrawString(startX + 55, screenY + 10, "SHIFT RPM", MX5_WHITE, bgColor, 2);
            snprintf(valueStr, sizeof(valueStr), "%d", settings.shiftRPM);
            LCD_DrawString(valueX, screenY + 18, valueStr, MX5_WHITE, bgColor, 2);
            break;

        case 4:
            LCD_FillCircle(iconX, iconY, 10, MX5_ORANGE);
            LCD_DrawLine(iconX - 6, iconY, iconX + 6, iconY, bgColor);
            LCD_DrawLine(iconX, iconY - 6, iconX, iconY + 6, bgColor);
            LCD_DrawString(startX + 55, screenY + 10, "REDLINE", MX5_WHITE, bgColor, 2);
            snprintf(valueStr, sizeof(valueStr), "%d", settings.redlineRPM);
            LCD_DrawString(valueX, screenY + 18, valueStr, MX5_WHITE, bgColor, 2);
            break;

        case 5:
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

        case 6:
            LCD_DrawCircle(iconX, iconY, 10, MX5_GREEN);
            LCD_DrawCircle(iconX, iconY, 6, MX5_GREEN);
            LCD_DrawString(startX + 55, screenY + 10, "LOW TIRE PSI", MX5_WHITE, bgColor, 2);
            snprintf(valueStr, sizeof(valueStr), "%.1f", settings.tireLowPSI);
            LCD_DrawString(valueX, screenY + 18, valueStr, MX5_WHITE, bgColor, 2);
            break;

        case 7:
            LCD_FillCircle(iconX, iconY, 10, MX5_BLUE);
            LCD_DrawLine(iconX - 4, iconY + 4, iconX, iconY - 6, MX5_WHITE);
            LCD_DrawLine(iconX, iconY - 6, iconX + 4, iconY + 4, MX5_WHITE);
            LCD_DrawString(startX + 55, screenY + 10, "COOLANT WARN", MX5_WHITE, bgColor, 2);
            snprintf(valueStr, sizeof(valueStr), "%dF", settings.coolantWarnF);
            LCD_DrawString(valueX, screenY + 18, valueStr, MX5_WHITE, bgColor, 2);
            break;

        case 8:
            for (int led = 0; led < 5; led++) {
                int ledX = iconX - 8 + led * 4;
                LCD_FillRect(ledX, iconY - 6, 3, 12, (led < 3) ? MX5_GREEN : MX5_DARKGRAY);
            }
            LCD_DrawString(startX + 55, screenY + 10, "LED SEQUENCE", MX5_WHITE, bgColor, 2);
            if (settings.ledSequence >= 1 && settings.ledSequence <= SEQ_COUNT) {
                LCD_DrawString(startX + 55, screenY + 32, LED_SEQUENCE_NAMES[settings.ledSequence], MX5_PURPLE, bgColor, 1);
            }
            snprintf(valueStr, sizeof(valueStr), "%d/%d", settings.ledSequence, SEQ_COUNT);
            LCD_DrawString(valueX + 20, screenY + 18, valueStr, MX5_WHITE, bgColor, 2);
            break;
    }
}

void drawSettingsScreen() {
    if (!needsFullRedraw) return;

    drawBackground();

    int startY = 55;
    int itemH = 52;
    int itemGap = 8;
    int itemW = 270;
    int startX = CENTER_X - itemW/2;

    if (settingsScrollOffset > 0) {
        LCD_DrawLine(CENTER_X - 10, 18, CENTER_X, 8, MX5_WHITE);
        LCD_DrawLine(CENTER_X + 10, 18, CENTER_X, 8, MX5_WHITE);
        LCD_DrawLine(CENTER_X - 10, 18, CENTER_X + 10, 18, MX5_WHITE);
    }
    if (settingsScrollOffset + SETTINGS_VISIBLE < SETTINGS_COUNT) {
        int baseY = SCREEN_HEIGHT - 28;
        int tipY = SCREEN_HEIGHT - 18;
        LCD_DrawLine(CENTER_X - 10, baseY, CENTER_X, tipY, MX5_WHITE);
        LCD_DrawLine(CENTER_X + 10, baseY, CENTER_X, tipY, MX5_WHITE);
        LCD_DrawLine(CENTER_X - 10, baseY, CENTER_X + 10, baseY, MX5_WHITE);
    }

    for (int i = 0; i < SETTINGS_VISIBLE && (settingsScrollOffset + i) < SETTINGS_COUNT; i++) {
        int itemIndex = settingsScrollOffset + i;
        int screenY = startY + i * (itemH + itemGap);
        bool isSelected = (itemIndex == settingsSelection);
        drawSettingsItem(itemIndex, screenY, itemW, startX, isSelected);
    }

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

// ============================================================================
// Settings touch handling
// ============================================================================
void handleSettingsTouch(int x, int y) {
    int startY = 55;
    int itemH = 52;
    int itemGap = 8;
    int itemW = 270;
    int startX = CENTER_X - itemW/2;

    if (y < 50 && settingsScrollOffset > 0) {
        settingsScrollOffset--;
        if (settingsSelection > settingsScrollOffset + SETTINGS_VISIBLE - 1) {
            settingsSelection = settingsScrollOffset + SETTINGS_VISIBLE - 1;
            Serial.printf("SELECTION:%d\n", settingsSelection);
        }
        needsRedraw = true;
        needsFullRedraw = true;
        return;
    }
    if (y > SCREEN_HEIGHT - 35 && settingsScrollOffset + SETTINGS_VISIBLE < SETTINGS_COUNT) {
        settingsScrollOffset++;
        if (settingsSelection < settingsScrollOffset) {
            settingsSelection = settingsScrollOffset;
            Serial.printf("SELECTION:%d\n", settingsSelection);
        }
        needsRedraw = true;
        needsFullRedraw = true;
        return;
    }

    for (int i = 0; i < SETTINGS_VISIBLE && (settingsScrollOffset + i) < SETTINGS_COUNT; i++) {
        int itemIndex = settingsScrollOffset + i;
        int itemY = startY + i * (itemH + itemGap);

        if (x >= startX && x <= startX + itemW && y >= itemY && y <= itemY + itemH) {
            int prevSelection = settingsSelection;
            settingsSelection = itemIndex;

            if (settingsSelection != prevSelection) {
                Serial.printf("SELECTION:%d\n", settingsSelection);
            }

            bool changed = false;

            switch (itemIndex) {
                case 0:
                    settings.demoMode = !settings.demoMode;
                    telemetry.connected = !settings.demoMode;
                    sendSettingToPI("demo_mode", settings.demoMode);
                    changed = true;
                    break;

                case 1:
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

                case 2:
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

                case 3:
                    if (settings.shiftRPM < 5500) settings.shiftRPM = 5500;
                    else if (settings.shiftRPM < 6000) settings.shiftRPM = 6000;
                    else if (settings.shiftRPM < 6500) settings.shiftRPM = 6500;
                    else if (settings.shiftRPM < 7000) settings.shiftRPM = 7000;
                    else settings.shiftRPM = 5000;
                    sendSettingToPI("shift_rpm", settings.shiftRPM);
                    changed = true;
                    break;

                case 4:
                    if (settings.redlineRPM < 6500) settings.redlineRPM = 6500;
                    else if (settings.redlineRPM < 7000) settings.redlineRPM = 7000;
                    else if (settings.redlineRPM < 7500) settings.redlineRPM = 7500;
                    else if (settings.redlineRPM < 8000) settings.redlineRPM = 8000;
                    else settings.redlineRPM = 6000;
                    sendSettingToPI("redline_rpm", settings.redlineRPM);
                    changed = true;
                    break;

                case 5:
                    settings.useMPH = !settings.useMPH;
                    sendSettingToPI("use_mph", settings.useMPH);
                    changed = true;
                    break;

                case 6:
                    settings.tireLowPSI += 0.5;
                    if (settings.tireLowPSI > 35.0) settings.tireLowPSI = 25.0;
                    sendSettingToPI("tire_low_psi", settings.tireLowPSI);
                    changed = true;
                    break;

                case 7:
                    settings.coolantWarnF += 5;
                    if (settings.coolantWarnF > 250) settings.coolantWarnF = 200;
                    sendSettingToPI("coolant_warn", settings.coolantWarnF);
                    changed = true;
                    break;

                case 8:
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

// ============================================================================
// Settings -> Pi serial bridge
// ============================================================================
void sendSettingToPI(const char* name, int value) {
    Serial.printf("SETTING:%s=%d\n", name, value);
}

void sendSettingToPI(const char* name, float value) {
    Serial.printf("SETTING:%s=%.1f\n", name, value);
}

void sendSettingToPI(const char* name, bool value) {
    Serial.printf("SETTING:%s=%d\n", name, value ? 1 : 0);
}
