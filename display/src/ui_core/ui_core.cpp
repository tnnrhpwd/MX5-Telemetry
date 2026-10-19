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

// ============================================================================
// Theme
//
// The phone app owns the theme; the Pi relays it and the firmware persists it,
// so a display with no phone attached still matches the app (dark by default).
// ============================================================================
char themeScheme[16] = "aurora";
bool themeDark = true;

// Starts as the dark aurora scheme so the palette is never uninitialised, even
// if nothing has applied a theme yet.
ThemePalette g_theme = {
    RGB565(10, 10, 16),   // bg
    RGB565(6, 6, 10),     // bgDark
    RGB565(9, 32, 37),    // bgCard      (bg mixed 12% toward aurora teal)
    RGB565(8, 47, 51),    // bgElevated  (bg mixed 20% toward aurora teal)
    RGB565(245, 245, 250),// text
    RGB565(140, 140, 160),// textDim
    RGB565(55, 55, 70),   // darkGray
    RGB565(255, 70, 85),  // red
    RGB565(255, 140, 50), // orange
    RGB565(255, 210, 60), // yellow
    RGB565(50, 215, 130), // green
    RGB565(65, 135, 255), // blue
    RGB565(50, 220, 255), // cyan
    RGB565(255, 55, 155), // purple
    RGB565(0, 193, 193),  // accent
};

namespace {

struct ThemeSeed {
    const char* id;
    uint8_t aR, aG, aB;   // primary seed
    uint8_t bR, bG, bB;   // secondary seed
};

// Mirrors Palette.SCHEMES in the Android app. Keep the two lists in step.
const ThemeSeed THEME_SEEDS[] = {
    {"aurora",    0x00, 0xC1, 0xC1, 0xFF, 0x37, 0x9B},
    {"crimson",   0xDC, 0x26, 0x26, 0xF4, 0x72, 0xB6},
    {"emerald",   0x10, 0xB9, 0x81, 0x06, 0xB6, 0xD4},
    {"sakura",    0xEC, 0x48, 0x99, 0xA7, 0x8B, 0xFA},
    {"midnight",  0x3B, 0x82, 0xF6, 0x8B, 0x5C, 0xF6},
    {"sunset",    0xF9, 0x73, 0x16, 0xEC, 0x48, 0x99},
    {"ocean",     0x06, 0xB6, 0xD4, 0x3B, 0x82, 0xF6},
    {"cyberpunk", 0xF0, 0xE0, 0x30, 0xE0, 0x40, 0xFB},
    {"monokai",   0xA6, 0xE2, 0x2E, 0x66, 0xD9, 0xEF},
    {"usa",       0xB2, 0x22, 0x34, 0x3C, 0x3B, 0x6E},
    {"forest",    0x4D, 0x8C, 0x57, 0x65, 0xA3, 0x0D},
    {"neutral",   0x80, 0x80, 0x80, 0x80, 0x80, 0x80},
};
const int THEME_SEED_COUNT = (int)(sizeof(THEME_SEEDS) / sizeof(THEME_SEEDS[0]));

inline uint16_t rgb565(int r, int g, int b) {
    if (r < 0) r = 0; if (r > 255) r = 255;
    if (g < 0) g = 0; if (g > 255) g = 255;
    if (b < 0) b = 0; if (b > 255) b = 255;
    return (uint16_t)(((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3));
}

// Blend two 8-bit channels, t=0 -> a, t=1 -> b.
inline int mix8(int a, int b, float t) {
    return (int)(a + (b - a) * t + 0.5f);
}

// Blend a colour toward a target RGB.
inline uint16_t mixColor(uint16_t base, int tr, int tg, int tb, float t) {
    int r = (base >> 11) & 0x1F, g = (base >> 5) & 0x3F, b = base & 0x1F;
    // Expand to 8-bit so the blend happens in sRGB, not in the packed 565 fields.
    int r8 = (r << 3) | (r >> 2);
    int g8 = (g << 2) | (g >> 4);
    int b8 = (b << 3) | (b >> 2);
    return rgb565(mix8(r8, tr, t), mix8(g8, tg, t), mix8(b8, tb, t));
}

// Scale a colour's brightness. f<1 darkens, f>1 lightens.
inline uint16_t scaleColor(uint16_t base, float f) {
    int r = (base >> 11) & 0x1F, g = (base >> 5) & 0x3F, b = base & 0x1F;
    int r8 = (r << 3) | (r >> 2);
    int g8 = (g << 2) | (g >> 4);
    int b8 = (b << 3) | (b >> 2);
    return rgb565((int)(r8 * f), (int)(g8 * f), (int)(b8 * f));
}

const ThemeSeed* findSeed(const char* id) {
    for (int i = 0; i < THEME_SEED_COUNT; i++) {
        if (strcmp(THEME_SEEDS[i].id, id) == 0) return &THEME_SEEDS[i];
    }
    return nullptr;
}

}  // namespace

void applyTheme(const char* scheme, bool dark) {
    const ThemeSeed* seed = findSeed(scheme ? scheme : "");
    if (!seed) seed = &THEME_SEEDS[0];  // aurora is the app's default

    strncpy(themeScheme, seed->id, sizeof(themeScheme) - 1);
    themeScheme[sizeof(themeScheme) - 1] = '\0';
    themeDark = dark;

    if (dark) {
        g_theme.bg         = rgb565(10, 10, 16);
        g_theme.bgDark     = rgb565(6, 6, 10);
        g_theme.bgCard     = mixColor(g_theme.bg, seed->aR, seed->aG, seed->aB, 0.12f);
        g_theme.bgElevated = mixColor(g_theme.bg, seed->aR, seed->aG, seed->aB, 0.20f);
        g_theme.text       = rgb565(245, 245, 250);
        g_theme.textDim    = rgb565(140, 140, 160);
        g_theme.darkGray   = rgb565(55, 55, 70);
        g_theme.accent     = rgb565(seed->aR, seed->aG, seed->aB);
        g_theme.purple     = rgb565(seed->bR, seed->bG, seed->bB);
    } else {
        g_theme.bg         = rgb565(246, 247, 251);
        g_theme.bgDark     = rgb565(232, 234, 242);
        g_theme.bgCard     = mixColor(rgb565(255, 255, 255), seed->aR, seed->aG, seed->aB, 0.08f);
        g_theme.bgElevated = mixColor(rgb565(255, 255, 255), seed->aR, seed->aG, seed->aB, 0.14f);
        g_theme.text       = rgb565(20, 20, 28);
        g_theme.textDim    = rgb565(90, 90, 110);
        // Mid-grey, not near-white: this is the "unlit / subtle stroke" colour, and
        // page-indicator dots at (201,202,214) were invisible on the light background.
        g_theme.darkGray   = rgb565(150, 152, 168);
        // The seed hues are tuned for dark backgrounds; on white they need to be
        // sunk so text and accents keep their contrast.
        g_theme.accent     = scaleColor(rgb565(seed->aR, seed->aG, seed->aB), 0.72f);
        g_theme.purple     = scaleColor(rgb565(seed->bR, seed->bG, seed->bB), 0.72f);
    }

    // Status colours stay semantic in every scheme (red is always a warning), but
    // light mode needs the darker variants to stay legible on white.
    float f = dark ? 1.0f : 0.72f;
    g_theme.red    = scaleColor(rgb565(255, 70, 85), f);
    g_theme.orange = scaleColor(rgb565(255, 140, 50), f);
    g_theme.yellow = scaleColor(rgb565(255, 210, 60), dark ? 1.0f : 0.86f);
    g_theme.green  = scaleColor(rgb565(50, 215, 130), f);
    g_theme.blue   = scaleColor(rgb565(65, 135, 255), f);
    g_theme.cyan   = scaleColor(rgb565(50, 220, 255), f);
}

void applyDefaultTheme() {
    // Used before the phone has ever connected, and at first boot.
    applyTheme("aurora", true);
}

// Speed is km/h end-to-end; only the display converts.
static inline int displaySpeedKmhOrMph() {
    float s = telemetry.speed;
    if (s < 0) s = 0;
    return (int)(settings.useMPH ? s * 0.621371f + 0.5f : s + 0.5f);
}


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
    // The backdrop is a fixed dark carbon image. Painting it under a light theme
    // would leave dark gutters around light cards, which reads as a rendering bug
    // rather than as a theme, so light mode fills with the theme's own background.
    if (themeDark) {
        LCD_DrawImage(0, 0, BACKGROUND_DATA_WIDTH, BACKGROUND_DATA_HEIGHT, background_data);
    } else {
        LCD_FillRect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, COLOR_BG);
    }
}

// ============================================================================
// Design system
// ============================================================================
// The panel is 360x360 round, so everything has to live inside a disc. These
// helpers keep all 8 screens on one type scale and one layout rhythm instead of
// each screen inventing its own coordinates.
//
//   y   0 ..  16   bezel gutter
//   y  16 ..  34   screen title + accent rule
//   y  44 .. 326   content
//   y 326 .. 348   page indicator
//
// Horizontal budget shrinks fast towards the top/bottom of the disc, so wide
// elements belong near the vertical centre.
// ============================================================================
#define SAFE_RADIUS  165
#define TITLE_Y      16
#define RULE_Y       34
#define FOOTER_Y     338

// Advance widths from the LCD driver: 5x7 -> 6, 10x14 -> 11, 15x21 -> 16.
// Glyph width is always advance - 1, so a run of N chars is N*advance - 1 px.
static inline int textW(const char* s, uint8_t size) {
    int adv = (size >= 3) ? 16 : (size == 2 ? 11 : 6);
    int n = (int)strlen(s);
    return n ? n * adv - 1 : 0;
}

static void drawCentered(int cx, int y, const char* s, uint16_t fg, uint16_t bg, uint8_t size) {
    LCD_DrawString(cx - textW(s, size) / 2, y, s, fg, bg, size);
}

static void drawRightAligned(int xRight, int y, const char* s, uint16_t fg, uint16_t bg, uint8_t size) {
    LCD_DrawString(xRight - textW(s, size), y, s, fg, bg, size);
}

// Superscript degree ring. The bundled fonts only cover ASCII 32..127, so a
// literal "°" would be drawn as "?" - the mark is composed from rects instead.
static void drawDegMark(int x, int y, uint16_t fg) {
    LCD_FillRect(x, y, 3, 1, fg);
    LCD_FillRect(x, y + 2, 3, 1, fg);
    LCD_FillRect(x, y + 1, 1, 1, fg);
    LCD_FillRect(x + 2, y + 1, 1, 1, fg);
}

// Standard screen title: name centred, with an accent rule beneath it.
static void drawHeader(const char* title, uint16_t accent) {
    drawCentered(CENTER_X, TITLE_Y, title, MX5_WHITE, COLOR_BG, 2);
    LCD_FillRect(CENTER_X - 30, RULE_Y, 24, 2, accent);
    LCD_FillRect(CENTER_X + 6, RULE_Y, 24, 2, MX5_DARKGRAY);
}

// Small filled triangle used as a scroll hint on the Settings screen.
static void drawChevron(int cx, int y, bool pointDown) {
    for (int i = 0; i < 5; i++) {
        int w = 18 - i * 4;
        int yy = pointDown ? (y + i) : (y + 4 - i);
        LCD_FillRect(cx - w / 2, yy, w, 1, MX5_WHITE);
    }
}

// Label above a size-2 value, used by the Overview side columns and the
// Engine/Diagnostics rows.
static void drawStatCell(int x, int y, const char* label, const char* value,
                         uint16_t valueColor, uint16_t bg) {
    LCD_DrawString(x, y, label, MX5_GRAY, bg, 1);
    LCD_DrawString(x, y + 9, value, valueColor, bg, 2);
}

// Horizontal meter: track, fill, and a 1px top-lit highlight.
static void drawMeter(int x, int y, int w, int h, float pct, uint16_t color, uint16_t bg) {
    if (pct < 0) pct = 0;
    if (pct > 1) pct = 1;
    LCD_FillRoundRect(x, y, w, h, h / 2, MX5_DARKGRAY);
    int fillW = (int)(w * pct);
    if (fillW >= h) {
        LCD_FillRoundRect(x, y, fillW, h, h / 2, color);
    } else if (fillW > 0) {
        LCD_FillRect(x, y + 1, fillW, h - 2, color);
    }
    (void)bg;
}

// Tire pressure status. Uses the configured low-pressure threshold instead of
// hard-coded PSI values, so a perfectly normal 33 PSI no longer reads as a
// warning the way the old >32 rule made it.
static uint16_t tireStatusColor(float psi) {
    if (psi <= 0.0f) return MX5_DARKGRAY;
    float low = (float)settings.tireLowPSI;
    if (low < 10.0f) low = 28.0f;              // settings not loaded yet
    if (psi < low - 3.0f) return MX5_RED;
    if (psi < low) return MX5_YELLOW;
    if (psi > 40.0f) return MX5_RED;
    if (psi > 36.0f) return MX5_YELLOW;
    return MX5_GREEN;
}

// Arc of evenly spaced dots - used as the Overview tach halo. Segments are
// individually addressable so a live gauge only repaints the ones that flipped.
static void drawDotArcSeg(int cx, int cy, int r, float startDeg, float sweepDeg,
                          int segCount, int index, bool active) {
    const int dotR = 4;
    float t = (index + 0.5f) / (float)segCount;
    float rad = (startDeg + sweepDeg * t) * (float)PI / 180.0f;
    int px = cx + (int)(cosf(rad) * r);
    int py = cy + (int)(sinf(rad) * r);
    uint16_t color = MX5_DARKGRAY;
    if (active) {
        float rpmAt = (index / (float)segCount) * 8000.0f;
        if (rpmAt >= 5500)      color = LED_RED;
        else if (rpmAt >= 4500) color = LED_ORANGE;
        else if (rpmAt >= 3000) color = LED_YELLOW;
        else if (rpmAt >= 2000) color = LED_GREEN;
        else                    color = LED_BLUE;
    }
    LCD_FillCircle(px, py, dotR, color);
}

#define OV_ARC_SEGS      24
#define OV_ARC_START     200.0f
#define OV_ARC_SWEEP     140.0f
#define OV_ARC_RADIUS    170


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

    // Blend fg over bg at 0..15 coverage (same math as the driver's blitter).
    auto mix = [](uint16_t bgc, uint16_t fgc, int cov) -> uint16_t {
        if (cov <= 0) return bgc;
        if (cov >= 15) return fgc;
        int br = (bgc >> 11) & 0x1F, bg_ = (bgc >> 5) & 0x3F, bb = bgc & 0x1F;
        int fr = (fgc >> 11) & 0x1F, fg_ = (fgc >> 5) & 0x3F, fb = fgc & 0x1F;
        int r = br + ((fr - br) * cov) / 15;
        int g = bg_ + ((fg_ - bg_) * cov) / 15;
        int b = bb + ((fb - bb) * cov) / 15;
        return (uint16_t)((r << 11) | (g << 5) | b);
    };

    // Composite the whole cell - foreground AND background - into one buffer and
    // push it with a single panel transaction. Writing the uncovered pixels as
    // the background also erases whatever glyph was there before; the old
    // blend-only path skipped them and left the previous digit behind.
    static uint16_t gearBuf[charW * charH];
    for (int row = 0; row < charH; row++) {
        uint16_t* dst = gearBuf + row * charW;
        for (int col = 0; col < charW; col++) {
            float sum = sample(col - 0.25f, row - 0.25f)
                      + sample(col + 0.25f, row - 0.25f)
                      + sample(col - 0.25f, row + 0.25f)
                      + sample(col + 0.25f, row + 0.25f);
            int cov = (int)(sum * 15.0f / 4.0f + 0.5f);
            if (cov > 15) cov = 15;
            dst[col] = mix(bgColor, color, cov);
        }
    }
    LCD_DrawBuffer(x0, y0, charW, charH, gearBuf);
}

// ============================================================================
// Overview screen
// ============================================================================

// Road speed per 1000 rpm in each gear, in km/h. Derived from the NC 6-speed
// ratios, 4.10 final drive and 24.3" tyre - the same numbers the Android
// GearRpmView uses, converted from mph so the ladder needs no unit handling.
static const float KMH_PER_1000_RPM[7] = {
    0.0f, 7.92f, 13.13f, 18.11f, 25.09f, 29.79f, 35.32f
};

// The band a driver wants to be in. Gears predicted inside it are "most likely".
#define GEAR_BAND_LOW   2400
#define GEAR_BAND_HIGH  4500

static int predictedRpm(int gear, float speedKmh) {
    if (gear < 1 || gear > 6 || speedKmh <= 0.5f) return 0;
    return (int)(speedKmh / KMH_PER_1000_RPM[gear] * 1000.0f + 0.5f);
}

// Draws the three gears whose predicted RPM sits closest to the sweet-spot band,
// with that RPM. Replaces the TPMS card while the Bluetooth sensors are offline.
static void drawGearLadder() {
    const int rowW = 150;
    const int rowH = 26;
    const int rowGap = 4;
    const int startY = 242;
    const int x = CENTER_X - rowW / 2;

    // Clear the whole ladder area first: the rows are shorter than the block.
    LCD_FillRect(x - 4, startY - 4, rowW + 8,
                 rowH * 3 + rowGap * 2 + 8, COLOR_BG);

    float speed = telemetry.speed;
    if (speed < 0) speed = 0;

    if (speed < 1.0f || telemetry.isInReverse) {
        LCD_FillRoundRect(x, startY, rowW, rowH, 8, COLOR_BG_CARD);
        drawCentered(CENTER_X, startY + 7, telemetry.isInReverse ? "REVERSE" : "STOPPED",
                     MX5_GRAY, COLOR_BG_CARD, 1);
        return;
    }

    // Rank all six gears by how far their predicted RPM is from the band.
    int order[6] = {1, 2, 3, 4, 5, 6};
    int score[6];
    for (int i = 0; i < 6; i++) {
        int rpm = predictedRpm(order[i], speed);
        if (rpm < GEAR_BAND_LOW)       score[i] = GEAR_BAND_LOW - rpm;
        else if (rpm > GEAR_BAND_HIGH) score[i] = rpm - GEAR_BAND_HIGH;
        else                           score[i] = 0;
    }
    for (int i = 0; i < 5; i++) {
        for (int j = 0; j < 5 - i; j++) {
            if (score[j] > score[j + 1]) {
                int t = score[j]; score[j] = score[j + 1]; score[j + 1] = t;
                t = order[j]; order[j] = order[j + 1]; order[j + 1] = t;
            }
        }
    }

    for (int row = 0; row < 3; row++) {
        int gear = order[row];
        int rpm = predictedRpm(gear, speed);
        int y = startY + row * (rowH + rowGap);

        bool isCurrent = (telemetry.gear == gear) && !telemetry.isInReverse;
        uint16_t bg = isCurrent ? COLOR_BG_ELEVATED : COLOR_BG_CARD;

        uint16_t rpmColor;
        if (rpm >= GEAR_BAND_LOW && rpm <= GEAR_BAND_HIGH) rpmColor = MX5_GREEN;
        else if (rpm > GEAR_BAND_HIGH)                    rpmColor = MX5_RED;
        else                                              rpmColor = MX5_BLUE;

        LCD_FillRoundRect(x, y, rowW, rowH, 8, bg);

        char gearStr[6];
        snprintf(gearStr, sizeof(gearStr), "%d", gear);
        LCD_DrawString(x + 14, y + 6, gearStr, isCurrent ? MX5_WHITE : MX5_GRAY, bg, 2);

        char rpmStr[10];
        snprintf(rpmStr, sizeof(rpmStr), "%d", rpm);
        drawRightAligned(x + rowW - 12, y + 6, rpmStr, rpmColor, bg, 2);
    }
}

void drawOverviewScreen() {
    bool rpmChanged = !prevTelemetry.initialized || (int)telemetry.rpm != (int)prevTelemetry.rpm;
    bool speedChanged = !prevTelemetry.initialized || (int)telemetry.speed != (int)prevTelemetry.speed;
    bool gearChanged = !prevTelemetry.initialized || telemetry.gear != prevTelemetry.gear;
    // Reverse comes from the explicit Pi flag, not from the sign of the speed.
    bool reverseChanged = !prevTelemetry.initialized || telemetry.isInReverse != prevTelemetry.reverse;
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
    // Tach halo: one dot per segment, only the dots that changed are repainted.
    // (The old version rasterised 45 wedges pixel by pixel - ~4,400 single-pixel
    // QSPI transactions for a full sweep.)
    int currentSegment = (int)(rpmPercent * OV_ARC_SEGS + 0.5f);

    float prevRpmPercent = (prevTelemetry.arcEndAngle - startAngle) / totalArc;
    if (prevRpmPercent < 0) prevRpmPercent = 0;
    if (prevRpmPercent > 1.0f) prevRpmPercent = 1.0f;
    int prevSegment = (int)(prevRpmPercent * OV_ARC_SEGS + 0.5f);

    if (needsFullRedraw || currentSegment != prevSegment) {
        int lo = needsFullRedraw ? 0 : min(prevSegment, currentSegment);
        int hi = needsFullRedraw ? OV_ARC_SEGS : max(prevSegment, currentSegment);
        for (int seg = lo; seg < hi; seg++) {
            drawDotArcSeg(CENTER_X, CENTER_Y, OV_ARC_RADIUS, OV_ARC_START, OV_ARC_SWEEP,
                          OV_ARC_SEGS, seg, seg < currentSegment);
        }
    }

    prevTelemetry.arcEndAngle = startAngle + (currentSegment * (totalArc / OV_ARC_SEGS));
    prevTelemetry.arcColor = rpmColor;
    }

    // Hero readout: two symmetric chips. Everything this high up has to stay
    // inside the disc, so they are narrow and low enough to clear the bezel.
    const int chipY    = 54;
    const int chipH    = 58;
    const int chipW    = 88;
    const int rpmChipX = 88;
    const int mphChipX = 184;
    const int rpmChipCx = rpmChipX + chipW / 2;
    const int mphChipCx = mphChipX + chipW / 2;

    if (hideTopDuringBoot) {
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
            loadingBoxDrawn = true;
            const int pillW = 240, pillH = 64;
            const int pillX = CENTER_X - pillW / 2;
            LCD_FillRect(pillX - 4, chipY - 4, pillW + 8, pillH + 8, COLOR_BG);
            LCD_FillRoundRect(pillX, chipY, pillW, pillH, 16, COLOR_BG_CARD);
            LCD_FillRoundRect(pillX + 24, chipY + pillH - 6, pillW - 48, 3, 1, MX5_CYAN);
            drawCentered(CENTER_X, chipY + 16, LOADING_MESSAGES[currentLoadingMessage],
                         MX5_CYAN, COLOR_BG_CARD, 2);
        }
    } else {
    static bool rpmLabelDrawn = false;
    static bool mphLabelDrawn = false;
    static uint16_t lastRpmAccent = 0xFFFF;

    if (needsFullRedraw) {
        rpmLabelDrawn = false;
        mphLabelDrawn = false;
        lastRpmAccent = 0xFFFF;
    }

    // ---- RPM chip ----
    // Glyphs now go out one panel transaction each, so repainting the whole
    // value is cheaper than the old per-digit comparison bookkeeping.
    if (needsFullRedraw || rpmChanged || rpmColor != lastRpmAccent) {
        if (!rpmLabelDrawn) {
            LCD_FillRect(rpmChipX - 4, chipY - 4, chipW + 8, chipH + 8, COLOR_BG);
            LCD_FillRoundRect(rpmChipX, chipY, chipW, chipH, 16, COLOR_BG_CARD);
            drawCentered(rpmChipCx, chipY + chipH - 15, "RPM", MX5_GRAY, COLOR_BG_CARD, 1);
            rpmLabelDrawn = true;
        }
        LCD_FillRect(rpmChipX + 10, chipY + chipH - 9, chipW - 20, 6, COLOR_BG_CARD);
        LCD_FillRoundRect(rpmChipX + 16, chipY + chipH - 8, chipW - 32, 3, 1, rpmColor);
        lastRpmAccent = rpmColor;

        char rpmStr[8];
        if (!telemetry.hasReceivedTelemetry) snprintf(rpmStr, sizeof(rpmStr), "--");
        else snprintf(rpmStr, sizeof(rpmStr), "%d", (int)telemetry.rpm);
        LCD_FillRect(rpmChipX + 4, chipY + 6, chipW - 8, 27, COLOR_BG_CARD);
        drawCentered(rpmChipCx, chipY + 9, rpmStr, MX5_WHITE, COLOR_BG_CARD, 3);
    }

    // ---- Speed chip ----
    if (needsFullRedraw || speedChanged) {
        if (!mphLabelDrawn) {
            LCD_FillRect(mphChipX - 4, chipY - 4, chipW + 8, chipH + 8, COLOR_BG);
            LCD_FillRoundRect(mphChipX, chipY, chipW, chipH, 16, COLOR_BG_CARD);
            drawCentered(mphChipCx, chipY + chipH - 15, settings.useMPH ? "MPH" : "KMH",
                         MX5_GRAY, COLOR_BG_CARD, 1);
            LCD_FillRoundRect(mphChipX + 16, chipY + chipH - 8, chipW - 32, 3, 1, MX5_CYAN);
            mphLabelDrawn = true;
        }

        char speedStr[8];
        if (!telemetry.hasReceivedTelemetry) snprintf(speedStr, sizeof(speedStr), "--");
        else snprintf(speedStr, sizeof(speedStr), "%d", displaySpeedKmhOrMph());
        LCD_FillRect(mphChipX + 4, chipY + 6, chipW - 8, 27, COLOR_BG_CARD);
        drawCentered(mphChipCx, chipY + 9, speedStr, MX5_CYAN, COLOR_BG_CARD, 3);
    }
    }

    uint16_t gearGlow = MX5_WHITE;

    static uint16_t prevGearGlow = 0;
    bool gearGlowChanged = (gearGlow != prevGearGlow);

    if (needsFullRedraw || gearChanged || reverseChanged || gearGlowChanged || bootCountdownChanged || justReceivedPiData) {
        int gearX = CENTER_X;
        int gearY = 190;
        int gearRadius = 46;
        // Filled annulus (two scanline fills) instead of four midpoint circles -
        // the outline version cost ~700 single-pixel transactions per redraw.
        LCD_FillCircle(gearX, gearY, gearRadius, gearGlow);
        LCD_FillCircle(gearX, gearY, gearRadius - 3, COLOR_BG_CARD);

        char gearStr[4];

        int bootCountdown = currentBootCountdown;
        bool showBootCountdown = inBootCountdown;

        if (showBootCountdown) {
            char countdownStr[4];
            snprintf(countdownStr, sizeof(countdownStr), "%d", bootCountdown);
            drawCentered(gearX, gearY - 12, countdownStr, gearGlow, COLOR_BG_CARD, 3);
            drawCentered(gearX, gearY + 14, "SEC", MX5_GRAY, COLOR_BG_CARD, 1);

            prevGearGlow = gearGlow;
        } else {
        if (telemetry.isInReverse || telemetry.gear == -1) {
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
        drawLargeGear(gearX, gearY, gearStr, gearGlow, COLOR_BG_CARD);

        prevGearGlow = gearGlow;
        }
    }

    bool hideDuringBoot = !piDataReceived;

    const int cardY  = 132;
    const int cardH  = 112;
    const int cardW  = 80;
    const int leftX  = 34;
    const int rightX = SCREEN_WIDTH - 34 - cardW;   // 246

    static bool sideBoxesCleared = false;

    if (hideDuringBoot) {
        if (needsFullRedraw && !sideBoxesCleared) {
            LCD_FillRect(leftX - 4, cardY - 4, cardW + 8, cardH + 8, COLOR_BG);
            LCD_FillRect(rightX - 4, cardY - 4, cardW + 8, cardH + 8, COLOR_BG);
            sideBoxesCleared = true;
        }
    } else {
    sideBoxesCleared = false;

    uint16_t coolColor = MX5_CYAN;
    if (telemetry.coolantTemp == 0) coolColor = MX5_RED;
    else if (telemetry.coolantTemp > 220) coolColor = MX5_RED;
    else if (telemetry.coolantTemp > 200) coolColor = MX5_ORANGE;

    if (needsFullRedraw) {
        LCD_FillRect(leftX - 4, cardY - 4, cardW + 8, cardH + 8, COLOR_BG);
        LCD_FillRoundRect(leftX, cardY, cardW, cardH, 10, COLOR_BG_CARD);
        LCD_DrawString(leftX + 9, cardY + 8,  "COOL", MX5_GRAY, COLOR_BG_CARD, 1);
        LCD_DrawString(leftX + 9, cardY + 44, "OIL",  MX5_GRAY, COLOR_BG_CARD, 1);
        LCD_DrawString(leftX + 9, cardY + 80, "VOLT", MX5_GRAY, COLOR_BG_CARD, 1);
    }

    if (needsFullRedraw || coolantChanged) {
        LCD_FillRect(leftX + 8, cardY + 17, cardW - 16, 16, COLOR_BG_CARD);
        char coolStr[8];
        snprintf(coolStr, sizeof(coolStr), "%d", (int)telemetry.coolantTemp);
        LCD_DrawString(leftX + 9, cardY + 17, coolStr, coolColor, COLOR_BG_CARD, 2);
        int degX = leftX + 9 + textW(coolStr, 2) + 2;
        drawDegMark(degX, cardY + 18, coolColor);
        LCD_DrawString(degX + 5, cardY + 17, "F", coolColor, COLOR_BG_CARD, 1);
    }

    if (needsFullRedraw || oilChanged) {
        uint16_t oilColor = telemetry.oilWarning ? MX5_RED : MX5_GREEN;
        LCD_FillRect(leftX + 8, cardY + 53, cardW - 16, 16, COLOR_BG_CARD);
        const char* oilStatus = telemetry.oilWarning ? "LOW" : "OK";
        LCD_DrawString(leftX + 9, cardY + 53, oilStatus, oilColor, COLOR_BG_CARD, 2);
    }

    if (needsFullRedraw || voltageChanged) {
        uint16_t voltColor = MX5_GREEN;
        if (telemetry.batteryVoltage < 0.1f) voltColor = MX5_GRAY;
        else if (telemetry.batteryVoltage < 12.0f) voltColor = MX5_RED;
        else if (telemetry.batteryVoltage < 13.0f) voltColor = MX5_YELLOW;
        LCD_FillRect(leftX + 8, cardY + 89, cardW - 16, 16, COLOR_BG_CARD);
        char voltStr[8];
        if (telemetry.batteryVoltage >= 0.1f) {
            snprintf(voltStr, sizeof(voltStr), "%.1fV", telemetry.batteryVoltage);
        } else {
            snprintf(voltStr, sizeof(voltStr), "--.-V");
        }
        LCD_DrawString(leftX + 9, cardY + 89, voltStr, voltColor, COLOR_BG_CARD, 2);
    }

    uint16_t mpgColor = MX5_GREEN;
    float displayMPG = telemetry.averageMPG > 0 ? telemetry.averageMPG : 26.0f;
    if (displayMPG < 15) mpgColor = MX5_RED;
    else if (displayMPG < 20) mpgColor = MX5_ORANGE;
    else if (displayMPG > 30) mpgColor = MX5_CYAN;

    uint16_t instMpgColor = MX5_CYAN;
    float displayInstMPG = telemetry.instantMPG;
    if (!telemetry.instantMPGValid) instMpgColor = MX5_GRAY;  // unknown (no MAF/speed)
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
        LCD_FillRect(rightX - 4, cardY - 4, cardW + 8, cardH + 8, COLOR_BG);
        LCD_FillRoundRect(rightX, cardY, cardW, cardH, 10, COLOR_BG_CARD);
        LCD_DrawString(rightX + 9, cardY + 4,  "AVG MPG",  MX5_GRAY, COLOR_BG_CARD, 1);
        LCD_DrawString(rightX + 9, cardY + 32, "INST MPG", MX5_GRAY, COLOR_BG_CARD, 1);
        LCD_DrawString(rightX + 9, cardY + 60, "FUEL",     MX5_GRAY, COLOR_BG_CARD, 1);
        LCD_DrawString(rightX + 9, cardY + 88, "RANGE",    MX5_GRAY, COLOR_BG_CARD, 1);
    }

    if (needsFullRedraw || mpgChanged) {
        LCD_FillRect(rightX + 8, cardY + 13, cardW - 16, 16, COLOR_BG_CARD);
        char mpgStr[10];
        snprintf(mpgStr, sizeof(mpgStr), "%.0f", displayMPG);
        LCD_DrawString(rightX + 9, cardY + 13, mpgStr, mpgColor, COLOR_BG_CARD, 2);
    }

    if (needsFullRedraw || instMpgChanged) {
        LCD_FillRect(rightX + 8, cardY + 41, cardW - 16, 16, COLOR_BG_CARD);
        char instStr[10];
        if (telemetry.instantMPGValid) snprintf(instStr, sizeof(instStr), "%.0f", displayInstMPG);
        else snprintf(instStr, sizeof(instStr), "--");
        LCD_DrawString(rightX + 9, cardY + 41, instStr, instMpgColor, COLOR_BG_CARD, 2);
    }

    if (needsFullRedraw || fuelChanged) {
        LCD_FillRect(rightX + 8, cardY + 69, cardW - 16, 16, COLOR_BG_CARD);
        char tankStr[10];
        snprintf(tankStr, sizeof(tankStr), "%d%%", (int)telemetry.fuelLevel);
        LCD_DrawString(rightX + 9, cardY + 69, tankStr, tankColor, COLOR_BG_CARD, 2);
    }

    if (needsFullRedraw || rangeChanged) {
        LCD_FillRect(rightX + 8, cardY + 97, cardW - 16, 16, COLOR_BG_CARD);
        char rangeStr[10];
        if (displayRange > 0) snprintf(rangeStr, sizeof(rangeStr), "%dmi", displayRange);
        else snprintf(rangeStr, sizeof(rangeStr), "--mi");
        LCD_DrawString(rightX + 9, cardY + 97, rangeStr, rangeColor, COLOR_BG_CARD, 2);
    }
    }

    if (needsFullRedraw && navLocked) {
        // Nav-lock is signalled by the page indicator turning amber (see
        // drawPageIndicator); a badge in the corner does not fit the disc.
    }

    // Gear ladder. This used to be the TPMS card; the Bluetooth sensors are out
    // of service until the 315 MHz ones are fitted, so the space shows the three
    // most likely gears for the current road speed and the RPM each would sit at.
    if (needsFullRedraw || speedChanged || gearChanged || reverseChanged) {
        drawGearLadder();
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
    prevTelemetry.reverse = telemetry.isInReverse;
    prevTelemetry.instantMPGValid = telemetry.instantMPGValid;
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
#define RPM_SEGS      36
#define RPM_ARC_CX    CENTER_X
#define RPM_ARC_CY    168
#define RPM_ARC_R     102
#define RPM_ARC_START 135.0f
#define RPM_ARC_SWEEP 270.0f
#define GEAR_CY       140
#define GEAR_R        44

static uint16_t rpmSegColor(int index) {
    float rpmAt = (index / (float)RPM_SEGS) * 8000.0f;
    if (rpmAt >= 5500) return LED_RED;
    if (rpmAt >= 4500) return LED_ORANGE;
    if (rpmAt >= 3000) return LED_YELLOW;
    if (rpmAt >= 2000) return LED_GREEN;
    return LED_BLUE;
}

static void drawRpmArcSeg(int index, bool active) {
    float t = (index + 0.5f) / (float)RPM_SEGS;
    float rad = (RPM_ARC_START + RPM_ARC_SWEEP * t) * (float)PI / 180.0f;
    int px = RPM_ARC_CX + (int)(cosf(rad) * RPM_ARC_R);
    int py = RPM_ARC_CY + (int)(sinf(rad) * RPM_ARC_R);
    LCD_FillCircle(px, py, 6, active ? rpmSegColor(index) : MX5_DARKGRAY);
}

void drawRPMScreen() {
    bool rpmChanged   = !prevTelemetry.initialized || (int)telemetry.rpm != (int)prevTelemetry.rpm;
    bool speedChanged = !prevTelemetry.initialized || (int)telemetry.speed != (int)prevTelemetry.speed;
    bool gearChanged  = !prevTelemetry.initialized || telemetry.gear != prevTelemetry.gear;
    bool reverseChanged = !prevTelemetry.initialized || telemetry.isInReverse != prevTelemetry.reverse;
    bool thrChanged   = !prevTelemetry.initialized || (int)telemetry.throttle != (int)prevTelemetry.throttle;
    bool brkChanged   = !prevTelemetry.initialized || (int)telemetry.brake != (int)prevTelemetry.brake;

    if (needsFullRedraw) {
        drawBackground();
        drawHeader("RPM", MX5_RED);

        const char* rpmLabels[] = {"0", "2", "4", "6", "8"};
        for (int i = 0; i < 5; i++) {
            float t = i / 4.0f;
            float rad = (RPM_ARC_START + RPM_ARC_SWEEP * t) * (float)PI / 180.0f;
            int lx = RPM_ARC_CX + (int)(cosf(rad) * (RPM_ARC_R - 22));
            int ly = RPM_ARC_CY + (int)(sinf(rad) * (RPM_ARC_R - 22));
            drawCentered(lx, ly - 3, rpmLabels[i], MX5_GRAY, COLOR_BG, 1);
        }
    }

    // ---- ring ----
    float rpmPercent = constrain(telemetry.rpm / 8000.0, 0, 1);
    int activeSegs = (int)(rpmPercent * RPM_SEGS + 0.5f);
    if (activeSegs > RPM_SEGS) activeSegs = RPM_SEGS;

    static int prevActiveSegs = -1;
    if (needsFullRedraw || prevActiveSegs < 0 || activeSegs != prevActiveSegs) {
        bool full = needsFullRedraw || prevActiveSegs < 0;
        int lo = full ? 0 : min(prevActiveSegs, activeSegs);
        int hi = full ? RPM_SEGS : max(prevActiveSegs, activeSegs);
        for (int i = lo; i < hi; i++) {
            drawRpmArcSeg(i, i < activeSegs);
        }
        prevActiveSegs = activeSegs;
    }

    // ---- gear ----
    char gearStr[4];
    if (telemetry.isInReverse || telemetry.gear == -1) snprintf(gearStr, sizeof(gearStr), "R");
    else if (telemetry.gear == 0) snprintf(gearStr, sizeof(gearStr), "N");
    else snprintf(gearStr, sizeof(gearStr), "%d", telemetry.gear);

    if (needsFullRedraw || gearChanged || reverseChanged) {
        LCD_FillCircle(CENTER_X, GEAR_CY, GEAR_R, MX5_WHITE);
        LCD_FillCircle(CENTER_X, GEAR_CY, GEAR_R - 3, COLOR_BG_CARD);
        drawLargeGear(CENTER_X, GEAR_CY, gearStr, MX5_WHITE, COLOR_BG_CARD);
    }

    // ---- rpm digits ----
    char rpmStr[8];
    snprintf(rpmStr, sizeof(rpmStr), "%d", (int)telemetry.rpm);
    if (needsFullRedraw || rpmChanged) {
        LCD_FillRect(CENTER_X - 46, 190, 92, 34, COLOR_BG);
        drawCentered(CENTER_X, 192, rpmStr, MX5_WHITE, COLOR_BG, 3);
        drawCentered(CENTER_X, 216, "RPM", MX5_GRAY, COLOR_BG, 1);
    }

    // ---- speed ----
    if (needsFullRedraw || speedChanged) {
        char speedStr[8];
        snprintf(speedStr, sizeof(speedStr), "%d", displaySpeedKmhOrMph());
        LCD_FillRect(CENTER_X - 46, 248, 92, 38, COLOR_BG);
        drawCentered(CENTER_X, 250, speedStr, MX5_CYAN, COLOR_BG, 3);
        drawCentered(CENTER_X, 274, settings.useMPH ? "MPH" : "KMH", MX5_GRAY, COLOR_BG, 1);
    }

    // ---- throttle / brake ----
    // Throttle is a real 0-100% position. Brake is only a pedal switch on this
    // car, so it is drawn as an on/off indicator rather than a proportional bar -
    // a bar that can only ever be empty or full reads as a broken gauge.
    if (needsFullRedraw || thrChanged) {
        LCD_FillRect(252, 250, 60, 30, COLOR_BG);
        LCD_DrawString(252, 252, "THR", MX5_GRAY, COLOR_BG, 1);
        drawMeter(252, 262, 56, 6, telemetry.throttle / 100.0f, MX5_GREEN, COLOR_BG);
        char thrPct[8];
        snprintf(thrPct, sizeof(thrPct), "%d%%", (int)telemetry.throttle);
        LCD_DrawString(252, 272, thrPct, MX5_GREEN, COLOR_BG, 1);
    }

    if (needsFullRedraw || brkChanged) {
        bool pressed = telemetry.brake > 50.0f;
        LCD_FillRect(48, 250, 60, 30, COLOR_BG);
        LCD_DrawString(48, 252, "BRK", MX5_GRAY, COLOR_BG, 1);
        const int ledX = 48, ledY = 262, ledW = 56, ledH = 8;
        LCD_FillRoundRect(ledX, ledY, ledW, ledH, 4, pressed ? MX5_RED : MX5_DARKGRAY);
        LCD_DrawString(48, 272, pressed ? "ON" : "OFF",
                       pressed ? MX5_RED : MX5_GRAY, COLOR_BG, 1);
    }

    if (needsFullRedraw) {
        drawPageIndicator();
    }

    prevTelemetry.rpm = telemetry.rpm;
    prevTelemetry.speed = telemetry.speed;
    prevTelemetry.gear = telemetry.gear;
    prevTelemetry.gearColor = telemetry.gearColor;
    prevTelemetry.throttle = telemetry.throttle;
    prevTelemetry.brake = telemetry.brake;
    prevTelemetry.reverse = telemetry.isInReverse;
    prevTelemetry.initialized = true;
}

// ============================================================================
// TPMS screen
// ============================================================================
void drawTPMSScreen() {
    if (!needsFullRedraw) return;

    drawBackground();

    drawHeader("TPMS", MX5_GREEN);

    auto getTireColor = [](float psi) -> uint16_t {
        return tireStatusColor(psi);
    };

    // Car body down the middle
    const int carW = 64;
    const int carH = 146;
    const int carX = CENTER_X - carW / 2;
    const int carY = 112;
    LCD_FillRoundRect(carX, carY, carW, carH, 18, COLOR_BG_CARD);
    LCD_FillRect(carX + 10, carY + 18, carW - 20, 2, MX5_ACCENT);
    LCD_FillRect(carX + 10, carY + carH - 20, carW - 20, 2, MX5_ACCENT);
    LCD_FillRoundRect(carX + 12, carY + 40, carW - 24, 46, 8, COLOR_BG_ELEVATED);

    const char* names[4] = {"FL", "FR", "RL", "RR"};
    const int cardW = 90;
    const int cardH = 56;
    const int colX[2] = {36, SCREEN_WIDTH - 36 - cardW};
    const int rowY[2] = {106, 200};

    bool allGood = true;

    for (int i = 0; i < 4; i++) {
        int x = colX[i % 2];
        int y = rowY[i / 2];
        uint16_t c = getTireColor(telemetry.tirePressure[i]);
        if (c != MX5_GREEN) allGood = false;

        LCD_FillRoundRect(x, y, cardW, cardH, 10, COLOR_BG_CARD);
        LCD_FillRect(x + 6, y + 10, 3, cardH - 20, c);

        LCD_DrawString(x + 14, y + 6, names[i], MX5_GRAY, COLOR_BG_CARD, 1);

        // Live dot: green once this wheel's sensor has reported this session.
        bool live = (tpmsLastUpdateStr[i][0] != '-');
        LCD_FillRect(x + cardW - 16, y + 9, 5, 5, live ? MX5_GREEN : MX5_DARKGRAY);

        char psiStr[8];
        if (telemetry.tirePressure[i] > 0) snprintf(psiStr, sizeof(psiStr), "%.1f", telemetry.tirePressure[i]);
        else snprintf(psiStr, sizeof(psiStr), "--");
        LCD_DrawString(x + 14, y + 18, psiStr, c, COLOR_BG_CARD, 2);
        LCD_DrawString(x + 64, y + 22, "PSI", MX5_GRAY, COLOR_BG_CARD, 1);

        char tempStr[8];
        if (telemetry.tireTemp[i] > 0) snprintf(tempStr, sizeof(tempStr), "%.1fF", telemetry.tireTemp[i]);
        else snprintf(tempStr, sizeof(tempStr), "--");
        LCD_DrawString(x + 14, y + 38, tempStr, MX5_ACCENT, COLOR_BG_CARD, 1);
    }

    const char* statusText = allGood ? "ALL TIRES OK" : "CHECK PRESSURE";
    uint16_t statusColor = allGood ? MX5_GREEN : MX5_ORANGE;
    drawCentered(CENTER_X, 282, statusText, statusColor, COLOR_BG, 2);

    drawPageIndicator();
}

// ============================================================================
// Engine screen
// ============================================================================
// Engine readout card: label, large value with an optional degree mark, meter.
// pct < 0 omits the meter (used where a percentage would be meaningless).
static void drawEngineCard(int x, int y, const char* label, const char* value,
                           const char* unit, bool degMark, uint16_t color, float pct) {
    const int w = 128, h = 80;
    LCD_FillRoundRect(x, y, w, h, 12, COLOR_BG_CARD);

    LCD_DrawString(x + 12, y + 8, label, MX5_GRAY, COLOR_BG_CARD, 1);
    LCD_DrawString(x + 12, y + 20, value, color, COLOR_BG_CARD, 3);

    int ux = x + 12 + textW(value, 3) + 3;
    if (degMark) {
        drawDegMark(ux, y + 22, color);
        ux += 6;
    }
    if (unit && unit[0]) LCD_DrawString(ux, y + 32, unit, MX5_GRAY, COLOR_BG_CARD, 1);

    if (pct >= 0.0f) drawMeter(x + 12, y + 62, w - 24, 8, pct, color, COLOR_BG_CARD);
}

void drawEngineScreen() {
    if (!needsFullRedraw) return;

    drawBackground();
    drawHeader("ENGINE", MX5_ORANGE);

    char v[12];

    uint16_t coolantColor = MX5_BLUE;
    if (telemetry.coolantTemp > 230) coolantColor = MX5_RED;
    else if (telemetry.coolantTemp > 215) coolantColor = MX5_ORANGE;
    snprintf(v, sizeof(v), "%d", (int)telemetry.coolantTemp);
    drawEngineCard(46, 106, "COOLANT", v, "F", true, coolantColor,
                   constrain((telemetry.coolantTemp - 100) / 150.0, 0, 1));

    uint16_t oilColor = MX5_ORANGE;
    if (telemetry.oilTemp > 260) oilColor = MX5_RED;
    else if (telemetry.oilTemp < 180) oilColor = MX5_BLUE;
    snprintf(v, sizeof(v), "%d", (int)telemetry.oilTemp);
    drawEngineCard(186, 106, "OIL TEMP", v, "F", true, oilColor,
                   constrain((telemetry.oilTemp - 150) / 150.0, 0, 1));

    uint16_t fuelColor = MX5_YELLOW;
    if (telemetry.fuelLevel < 15) fuelColor = MX5_RED;
    else if (telemetry.fuelLevel < 25) fuelColor = MX5_ORANGE;
    snprintf(v, sizeof(v), "%d", (int)telemetry.fuelLevel);
    drawEngineCard(46, 194, "FUEL", v, "%", false, fuelColor, telemetry.fuelLevel / 100.0f);

    uint16_t ambientColor = MX5_GREEN;
    if (telemetry.ambientTemp < 32) ambientColor = MX5_CYAN;
    else if (telemetry.ambientTemp > 95) ambientColor = MX5_RED;
    else if (telemetry.ambientTemp > 85) ambientColor = MX5_ORANGE;
    snprintf(v, sizeof(v), "%.0f", telemetry.ambientTemp);
    drawEngineCard(186, 194, "AMBIENT", v, "F", true, ambientColor, -1.0f);

    drawPageIndicator();
}

// ============================================================================
// G-Force screen
//
// A g-scatter with a decaying trail, ported from the Android GForceView. Position
// is the instantaneous lateral/longitudinal acceleration, colour and size are the
// magnitude, and the last two seconds of points show the shape of the corner. A
// single dot tells you almost nothing about a turn; the trail is the point.
//
// The face is rebuilt from code rather than erased with a black rectangle so the
// dots can be restored without smearing over the carbon background.
// ============================================================================
#define GF_CX          CENTER_X
#define GF_CY          158
#define GF_RIM_R       106
#define GF_FACE_R      104
#define GF_TRAVEL      88          // outer ring radius in pixels = RANGE_G
#define GF_RANGE_G     1.2f
#define GF_RING1       ((int)(GF_TRAVEL * 0.4f / 1.2f))   // 0.4 g
#define GF_RING2       ((int)(GF_TRAVEL * 0.8f / 1.2f))   // 0.8 g
#define GF_RESTORE_MAX 44
#define GF_TRAIL       24

static uint16_t gfBlend(uint16_t a, uint16_t b, float t) {
    int ar = (a >> 11) & 0x1F, ag = (a >> 5) & 0x3F, ab = a & 0x1F;
    int br = (b >> 11) & 0x1F, bg = (b >> 5) & 0x3F, bb = b & 0x1F;
    int r = ar + (int)((br - ar) * t + 0.5f);
    int g = ag + (int)((bg - ag) * t + 0.5f);
    int bl = ab + (int)((bb - ab) * t + 0.5f);
    return (uint16_t)((r << 11) | (g << 5) | bl);
}

static uint16_t gfFaceAt(int x, int y) {
    int dx = x - GF_CX;
    int dy = y - GF_CY;
    int d2 = dx * dx + dy * dy;
    if (d2 > GF_FACE_R * GF_FACE_R) return COLOR_BG;
    if (d2 >= (GF_RING2 - 2) * (GF_RING2 - 2) && d2 <= GF_RING2 * GF_RING2) return MX5_DARKGRAY;
    if (d2 >= (GF_RING1 - 2) * (GF_RING1 - 2) && d2 <= GF_RING1 * GF_RING1) return MX5_DARKGRAY;
    if (dx == 0 || dy == 0) return MX5_DARKGRAY;
    return COLOR_BG_CARD;
}

static void gfRestore(int bx, int by, int size) {
    static uint16_t buf[GF_RESTORE_MAX * GF_RESTORE_MAX];
    if (size > GF_RESTORE_MAX) size = GF_RESTORE_MAX;
    for (int row = 0; row < size; row++) {
        for (int col = 0; col < size; col++) {
            buf[row * size + col] = gfFaceAt(bx + col, by + row);
        }
    }
    LCD_DrawBuffer(bx, by, size, size, buf);
}

// Paint a dot by compositing it over the face into one buffer. A scanline
// FillCircle costs ~13 panel transactions; this costs exactly one.
static void gfDrawDot(int cx, int cy, int r, uint16_t color) {
    static uint16_t buf[GF_RESTORE_MAX * GF_RESTORE_MAX];
    int size = (r + 3) * 2 + 1;
    if (size > GF_RESTORE_MAX) size = GF_RESTORE_MAX;
    int bx = cx - size / 2;
    int by = cy - size / 2;
    int rin = r * r;
    int rout = (r + 1) * (r + 1);
    for (int row = 0; row < size; row++) {
        for (int col = 0; col < size; col++) {
            int x = bx + col;
            int y = by + row;
            int dx = x - cx;
            int dy = y - cy;
            int d2 = dx * dx + dy * dy;
            uint16_t c;
            if (d2 <= rin)       c = color;
            else if (d2 <= rout) c = gfBlend(color, MX5_WHITE, 0.35f);
            else                 c = gfFaceAt(x, y);
            buf[row * size + col] = c;
        }
    }
    LCD_DrawBuffer(bx, by, size, size, buf);
}

static uint16_t gfColorFor(float m) {
    if (m >= 0.75f) return MX5_RED;
    if (m >= 0.50f) return MX5_ORANGE;
    if (m >= 0.25f) return MX5_YELLOW;
    return MX5_GREEN;
}

void drawGForceScreen() {
    static float trailLat[GF_TRAIL];
    static float trailLong[GF_TRAIL];
    static int trailHead = 0;
    static int trailCount = 0;
    static int prevX[GF_TRAIL], prevY[GF_TRAIL], prevR[GF_TRAIL];
    static int prevDrawn = 0;
    static unsigned long lastSample = 0;
    static unsigned long lastValueUpdate = 0;

    // Lateral is X, longitudinal is Y; forward is up, so Y is negated on the way
    // to the screen (same convention as the Android view).
    float lat = telemetry.linearAccelX;
    float lon = telemetry.linearAccelY;

    if (needsFullRedraw) {
        drawBackground();
        drawHeader("G-FORCE", MX5_CYAN);

        LCD_FillCircle(GF_CX, GF_CY, GF_RIM_R, MX5_DARKGRAY);
        LCD_FillCircle(GF_CX, GF_CY, GF_FACE_R, COLOR_BG_CARD);
        LCD_FillCircle(GF_CX, GF_CY, GF_RING2, MX5_DARKGRAY);
        LCD_FillCircle(GF_CX, GF_CY, GF_RING2 - 2, COLOR_BG_CARD);
        LCD_FillCircle(GF_CX, GF_CY, GF_RING1, MX5_DARKGRAY);
        LCD_FillCircle(GF_CX, GF_CY, GF_RING1 - 2, COLOR_BG_CARD);
        LCD_FillRect(GF_CX - GF_TRAVEL, GF_CY, GF_TRAVEL * 2, 1, MX5_DARKGRAY);
        LCD_FillRect(GF_CX, GF_CY - GF_TRAVEL, 1, GF_TRAVEL * 2, MX5_DARKGRAY);
        LCD_FillCircle(GF_CX, GF_CY, 2, MX5_WHITE);

        // Axis labels, matching the Android pad: accel up, brake down, L/R across.
        drawCentered(GF_CX, GF_CY - GF_TRAVEL - 14, "ACCEL", MX5_GRAY, COLOR_BG_CARD, 1);
        drawCentered(GF_CX, GF_CY + GF_TRAVEL + 3, "BRAKE", MX5_GRAY, COLOR_BG_CARD, 1);
        drawCentered(GF_CX - GF_TRAVEL - 2, GF_CY - 3, "L", MX5_GRAY, COLOR_BG_CARD, 1);
        drawCentered(GF_CX + GF_TRAVEL + 2, GF_CY - 3, "R", MX5_GRAY, COLOR_BG_CARD, 1);

        const char* labels[3] = {"MAG", "LAT", "LONG"};
        const int colX[3] = {108, CENTER_X, 252};
        for (int i = 0; i < 3; i++) drawCentered(colX[i], 274, labels[i], MX5_GRAY, COLOR_BG, 1);

        drawPageIndicator();

        trailCount = 0;
        trailHead = 0;
        prevDrawn = 0;
    }

    // Sample the trail at ~20 Hz. The IMU feeds this screen at 100 Hz; keeping every
    // sample would make the trail only a fifth of a second long.
    if (millis() - lastSample >= 50) {
        lastSample = millis();
        trailLat[trailHead] = lat;
        trailLong[trailHead] = lon;
        trailHead = (trailHead + 1) % GF_TRAIL;
        if (trailCount < GF_TRAIL) trailCount++;

        // Erase the previous frame's dots before painting the new ones.
        for (int i = 0; i < prevDrawn; i++) {
            int pad = prevR[i] + 3;
            gfRestore(prevX[i] - pad, prevY[i] - pad, pad * 2 + 1);
        }

        const float scale = (float)GF_TRAVEL / GF_RANGE_G;
        prevDrawn = 0;

        // Oldest first, so the newest dot ends up on top.
        for (int i = 0; i < trailCount && prevDrawn < GF_TRAIL; i++) {
            int index = (trailHead - trailCount + i + GF_TRAIL * 2) % GF_TRAIL;
            float age = (i + 1) / (float)trailCount;   // 0 = oldest, 1 = newest

            int px = GF_CX + (int)(trailLat[index] * scale);
            int py = GF_CY - (int)(trailLong[index] * scale);

            // Clamp to the outer ring: on a bumpy road a clamped dot is more useful
            // than one that has left the dial.
            int dx = px - GF_CX, dy = py - GF_CY;
            int d2 = dx * dx + dy * dy;
            if (d2 > GF_TRAVEL * GF_TRAVEL) {
                float k = (float)GF_TRAVEL / sqrtf((float)d2);
                px = GF_CX + (int)(dx * k);
                py = GF_CY + (int)(dy * k);
            }

            float m = sqrtf(trailLat[index] * trailLat[index] +
                            trailLong[index] * trailLong[index]);
            uint16_t color = gfColorFor(m);
            int r = 2 + (int)(age * 3.0f);

            // Older points fade toward the panel surface instead of being drawn at
            // full brightness, which is what makes the direction of travel readable.
            uint16_t faded = gfBlend(COLOR_BG_CARD, color, 0.35f + 0.65f * age);

            gfDrawDot(px, py, r, faded);

            prevX[prevDrawn] = px;
            prevY[prevDrawn] = py;
            prevR[prevDrawn] = r;
            prevDrawn++;
        }
    }

    // Numeric readouts at 10Hz, and only when the text actually changed.
    if (needsFullRedraw || millis() - lastValueUpdate >= 100) {
        lastValueUpdate = millis();
        static char lastV[3][12] = {"", "", ""};
        char v[3][12];
        float mag = sqrtf(lat * lat + lon * lon);

        snprintf(v[0], sizeof(v[0]), "%.2f", mag);
        snprintf(v[1], sizeof(v[1]), "%+.2f", lat);
        snprintf(v[2], sizeof(v[2]), "%+.2f", lon);

        const int colX[3] = {108, CENTER_X, 252};
        const uint16_t colors[3] = {gfColorFor(mag), MX5_CYAN, MX5_GREEN};
        const int widths[3] = {56, 56, 64};

        for (int i = 0; i < 3; i++) {
            if (!needsFullRedraw && strcmp(v[i], lastV[i]) == 0) continue;
            LCD_FillRect(colX[i] - widths[i] / 2, 284, widths[i], 18, COLOR_BG);
            drawCentered(colX[i], 284, v[i], colors[i], COLOR_BG, 2);
            strncpy(lastV[i], v[i], sizeof(lastV[i]) - 1);
            lastV[i][sizeof(lastV[i]) - 1] = '\0';
        }
    }
}


// ============================================================================
// Helper drawing functions
// ============================================================================
void drawPageIndicator() {
    // Current page is a pill, the rest are small squares. Amber = nav locked.
    const int gap = 13;
    const int span = (SCREEN_COUNT - 1) * gap;
    const int x0 = CENTER_X - span / 2;
    const uint16_t activeColor = navLocked ? MX5_ORANGE : MX5_WHITE;

    for (int i = 0; i < SCREEN_COUNT; i++) {
        int cx = x0 + i * gap;
        if (i == (int)currentScreen) {
            LCD_FillRoundRect(cx - 6, FOOTER_Y - 2, 12, 4, 2, activeColor);
        } else {
            LCD_FillRect(cx - 1, FOOTER_Y - 1, 3, 3, MX5_DARKGRAY);
        }
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
    drawHeader("DIAGNOSTICS", MX5_RED);

    struct DiagItem {
        const char* name;
        bool isWarning;
        bool hasData;
        uint16_t colorWarn;
    };

    DiagItem items[] = {
        {"CHECK ENGINE", telemetry.checkEngine,     telemetry.hasDiagnosticData, MX5_RED},
        {"ABS SYSTEM",   telemetry.absWarning,      telemetry.hasDiagnosticData, MX5_ORANGE},
        {"OIL PRESSURE", telemetry.oilWarning,      telemetry.hasDiagnosticData, MX5_RED},
        {"BATTERY",      telemetry.batteryWarning,  telemetry.hasDiagnosticData, MX5_YELLOW},
        {"ENGINE RUN",   !telemetry.engineRunning,  telemetry.hasDiagnosticData, MX5_RED},
        {"CONNECTION",   !telemetry.connected,      true,                        MX5_ORANGE},
    };
    const int n = 6;

    const int itemW = 210;
    const int itemH = 32;
    const int itemGap = 5;
    const int startX = CENTER_X - itemW / 2;
    const int startY = 70;

    int warnCount = 0;
    int noDataCount = 0;
    for (int i = 0; i < n; i++) {
        if (!items[i].hasData) noDataCount++;
        else if (items[i].isWarning) warnCount++;
    }

    // One-line verdict above the list, so the screen is readable at a glance.
    char summaryBuf[24];
    const char* summary;
    uint16_t summaryColor;
    if (noDataCount == n) {
        summary = "AWAITING ECU DATA";
        summaryColor = MX5_GRAY;
    } else if (warnCount == 0) {
        summary = "ALL SYSTEMS NOMINAL";
        summaryColor = MX5_GREEN;
    } else {
        snprintf(summaryBuf, sizeof(summaryBuf), "%d WARNING%s", warnCount, warnCount == 1 ? "" : "S");
        summary = summaryBuf;
        summaryColor = MX5_ORANGE;
    }
    drawCentered(CENTER_X, 48, summary, summaryColor, COLOR_BG, 1);

    for (int i = 0; i < n; i++) {
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
            statusColor = MX5_GREEN;
            statusText = "OK";
        }

        LCD_FillRoundRect(startX, y, itemW, itemH, 8, COLOR_BG_CARD);
        LCD_FillRect(startX + 6, y + 8, 3, itemH - 16, statusColor);
        LCD_DrawString(startX + 16, y + 9, items[i].name, MX5_WHITE, COLOR_BG_CARD, 2);
        drawRightAligned(startX + itemW - 8, y + 12, statusText, statusColor, COLOR_BG_CARD, 1);
    }

    drawPageIndicator();
}

// ============================================================================
// System screen
// ============================================================================
void drawSystemScreen() {
    if (!needsFullRedraw) return;

    drawBackground();
    drawHeader("SYSTEM", MX5_PURPLE);

    drawCentered(CENTER_X, 48, "ESP32-S3 240MHZ", MX5_GRAY, COLOR_BG, 1);

    const int itemW = 210;
    const int itemH = 32;
    const int itemGap = 6;
    const int startX = CENTER_X - itemW / 2;
    const int startY = 70;

    unsigned long uptimeSec = millis() / 1000;
    int hrs = uptimeSec / 3600;
    int mins = (uptimeSec % 3600) / 60;
    int secs = uptimeSec % 60;

    char memStr[16];
    snprintf(memStr, sizeof(memStr), "%dKB", (int)(ESP.getFreeHeap() / 1024));

    char upStr[16];
    snprintf(upStr, sizeof(upStr), "%02d:%02d:%02d", hrs, mins, secs);

    const char* labels[5] = {"IMU", "PI LINK", "DISPLAY", "FREE HEAP", "UPTIME"};
    const char* values[5];
    uint16_t colors[5];

    colors[0] = imuAvailable ? MX5_GREEN : MX5_RED;
    values[0] = imuAvailable ? "READY" : "OFFLINE";
    colors[1] = telemetry.connected ? MX5_GREEN : MX5_ORANGE;
    values[1] = telemetry.connected ? "LINK" : "WAIT";
    colors[2] = MX5_ACCENT;
    values[2] = "360 ST77916";
    colors[3] = MX5_PURPLE;
    values[3] = memStr;
    colors[4] = MX5_CYAN;
    values[4] = upStr;

    for (int i = 0; i < 5; i++) {
        int y = startY + i * (itemH + itemGap);
        LCD_FillRoundRect(startX, y, itemW, itemH, 8, COLOR_BG_CARD);
        LCD_FillRect(startX + 6, y + 8, 3, itemH - 16, colors[i]);
        LCD_DrawString(startX + 16, y + 9, labels[i], MX5_WHITE, COLOR_BG_CARD, 2);
        drawRightAligned(startX + itemW - 8, y + 13, values[i], colors[i], COLOR_BG_CARD, 1);
    }

    drawPageIndicator();
}

// ============================================================================
// Settings screen
// ============================================================================
// Settings row geometry, shared with handleSettingsTouch() so the hit boxes and
// the drawing can never drift apart.
#define ST_SET_X        55
#define ST_SET_Y        62
#define ST_SET_W        250
#define ST_SET_H        48
#define ST_SET_GAP      8
#define ST_SLIDER_X     (ST_SET_X + 12)
#define ST_SLIDER_W     (ST_SET_W - 24)

void drawSettingsItem(int index, int screenY, int itemW, int startX, bool isSelected) {
    const int itemH = ST_SET_H;
    const uint16_t bgColor = isSelected ? COLOR_BG_ELEVATED : COLOR_BG_CARD;

    LCD_FillRoundRect(startX, screenY, itemW, itemH, 12, bgColor);
    if (isSelected) {
        LCD_FillRect(startX + 5, screenY + 10, 3, itemH - 20, MX5_ACCENT);
    }

    char valueStr[20] = "";
    const char* label = "";
    uint16_t valueColor = MX5_ACCENT;
    int sliderPct = -1;

    switch (index) {
        case 0:
            label = "DATA SOURCE";
            snprintf(valueStr, sizeof(valueStr), "%s", settings.demoMode ? "DEMO" : "CAN BUS");
            valueColor = MX5_PURPLE;
            break;

        case 1:
            label = "BRIGHTNESS";
            sliderPct = settings.brightness;
            valueColor = MX5_YELLOW;
            snprintf(valueStr, sizeof(valueStr), "%d%%", settings.brightness);
            break;

        case 2:
            label = "VOLUME";
            sliderPct = settings.volume;
            valueColor = MX5_CYAN;
            snprintf(valueStr, sizeof(valueStr), "%d%%", settings.volume);
            break;

        case 3:
            label = "SHIFT RPM";
            valueColor = MX5_RED;
            snprintf(valueStr, sizeof(valueStr), "%d", settings.shiftRPM);
            break;

        case 4:
            label = "REDLINE";
            valueColor = MX5_ORANGE;
            snprintf(valueStr, sizeof(valueStr), "%d", settings.redlineRPM);
            break;

        case 5:
            label = "UNITS";
            valueColor = MX5_ACCENT;
            snprintf(valueStr, sizeof(valueStr), "%s", settings.useMPH ? "MPH" : "KMH");
            break;

        case 6:
            label = "LOW TIRE PSI";
            valueColor = MX5_GREEN;
            snprintf(valueStr, sizeof(valueStr), "%.1f", settings.tireLowPSI);
            break;

        case 7:
            label = "COOLANT WARN";
            valueColor = MX5_BLUE;
            snprintf(valueStr, sizeof(valueStr), "%dF", settings.coolantWarnF);
            break;

        case 8:
            label = "LED SEQUENCE";
            valueColor = MX5_PURPLE;
            if (settings.ledSequence >= 1 && settings.ledSequence <= SEQ_COUNT) {
                snprintf(valueStr, sizeof(valueStr), "%s", LED_SEQUENCE_NAMES[settings.ledSequence]);
            } else {
                snprintf(valueStr, sizeof(valueStr), "%d/%d", settings.ledSequence, SEQ_COUNT);
            }
            break;
    }

    LCD_DrawString(startX + 12, screenY + 7, label, MX5_WHITE, bgColor, 2);

    if (sliderPct >= 0) {
        drawMeter(startX + 12, screenY + 32, itemW - 24, 7, sliderPct / 100.0f, valueColor, bgColor);
        drawRightAligned(startX + itemW - 10, screenY + 8, valueStr, valueColor, bgColor, 1);
    } else {
        drawRightAligned(startX + itemW - 10, screenY + 27, valueStr, valueColor, bgColor, 2);
    }
}

void drawSettingsScreen() {
    if (!needsFullRedraw) return;

    drawBackground();
    drawHeader("SETTINGS", MX5_BLUE);

    if (settingsScrollOffset > 0) {
        drawChevron(CENTER_X, 40, false);
    }
    if (settingsScrollOffset + SETTINGS_VISIBLE < SETTINGS_COUNT) {
        drawChevron(CENTER_X, 298, true);
    }

    for (int i = 0; i < SETTINGS_VISIBLE && (settingsScrollOffset + i) < SETTINGS_COUNT; i++) {
        int itemIndex = settingsScrollOffset + i;
        int screenY = ST_SET_Y + i * (ST_SET_H + ST_SET_GAP);
        bool isSelected = (itemIndex == settingsSelection);
        drawSettingsItem(itemIndex, screenY, ST_SET_W, ST_SET_X, isSelected);
    }

    drawPageIndicator();
}

// ============================================================================
// Settings touch handling
// ============================================================================
void handleSettingsTouch(int x, int y) {
    const int startY = ST_SET_Y;
    const int itemH = ST_SET_H;
    const int itemGap = ST_SET_GAP;
    const int itemW = ST_SET_W;
    const int startX = ST_SET_X;

    if (y < 56 && settingsScrollOffset > 0) {
        settingsScrollOffset--;
        if (settingsSelection > settingsScrollOffset + SETTINGS_VISIBLE - 1) {
            settingsSelection = settingsScrollOffset + SETTINGS_VISIBLE - 1;
            Serial.printf("SELECTION:%d\n", settingsSelection);
        }
        needsRedraw = true;
        needsFullRedraw = true;
        return;
    }
    if (y > 290 && settingsScrollOffset + SETTINGS_VISIBLE < SETTINGS_COUNT) {
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
                        const int sliderX = ST_SLIDER_X;
                        const int sliderW = ST_SLIDER_W;
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
                        const int sliderX = ST_SLIDER_X;
                        const int sliderW = ST_SLIDER_W;
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
