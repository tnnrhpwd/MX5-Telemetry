/**
 * @file native_display.cpp
 * @brief Mock ST77916 LCD backend for the desktop simulator.
 *
 * Implements every LCD_* primitive used by ui_core against a 360x360 RGB888
 * framebuffer. Text metrics (char widths, advances, line heights) mirror the
 * real Display_ST77916 driver so screen layouts match the device pixel-for-
 * pixel. The 5x7 glyph table is the same classic font the device uses.
 */

#include "native_display.h"
#include "fonts_hires.h"

#include <cstdarg>
#include <chrono>

// ---------------------------------------------------------------------------
// Time base
// ---------------------------------------------------------------------------
static std::chrono::steady_clock::time_point g_start = std::chrono::steady_clock::now();

unsigned long millis() {
    auto now = std::chrono::steady_clock::now();
    return (unsigned long)std::chrono::duration_cast<std::chrono::milliseconds>(now - g_start).count();
}

unsigned long micros() {
    auto now = std::chrono::steady_clock::now();
    return (unsigned long)std::chrono::duration_cast<std::chrono::microseconds>(now - g_start).count();
}

void delay(unsigned long ms) {
    auto end = std::chrono::steady_clock::now() + std::chrono::milliseconds(ms);
    while (std::chrono::steady_clock::now() < end) { /* busy wait */ }
}

long random(long howbig) {
    if (howbig <= 0) return 0;
    return std::rand() % howbig;
}

long random(long howsmall, long howbig) {
    if (howbig <= howsmall) return howsmall;
    return howsmall + (std::rand() % (howbig - howsmall));
}

// ---------------------------------------------------------------------------
// Serial / ESP stubs
// ---------------------------------------------------------------------------
NativeSerial Serial;
NativeESP ESP;

int NativeSerial::printf(const char* fmt, ...) {
    va_list args;
    va_start(args, fmt);
    int n = vprintf(fmt, args);
    va_end(args);
    return n;
}

int NativeSerial::print(const char* s) { return printf("%s", s); }
int NativeSerial::println(const char* s) { return printf("%s\n", s); }
int NativeSerial::println() { return printf("\n"); }
int NativeSerial::print(int v) { return printf("%d", v); }
int NativeSerial::println(int v) { return printf("%d\n", v); }

// ---------------------------------------------------------------------------
// Framebuffer
// ---------------------------------------------------------------------------
static const int FB_W = 360;
static const int FB_H = 360;
static uint32_t fb[FB_W * FB_H];

const uint32_t* native_framebuffer() { return fb; }
int native_framebuffer_width() { return FB_W; }
int native_framebuffer_height() { return FB_H; }

static inline uint32_t rgb565_to_rgb888(uint16_t c) {
    uint8_t r5 = (c >> 11) & 0x1F;
    uint8_t g6 = (c >> 5) & 0x3F;
    uint8_t b5 = c & 0x1F;
    uint8_t r = (r5 << 3) | (r5 >> 2);
    uint8_t g = (g6 << 2) | (g6 >> 4);
    uint8_t b = (b5 << 3) | (b5 >> 2);
    return 0xFF000000u | ((uint32_t)r << 16) | ((uint32_t)g << 8) | b;
}

static inline void set_px(int x, int y, uint32_t c) {
    if (x >= 0 && x < FB_W && y >= 0 && y < FB_H) {
        fb[y * FB_W + x] = c;
    }
}

// ---------------------------------------------------------------------------
// Simple drawing functions
// ---------------------------------------------------------------------------
void LCD_Clear(uint16_t color) {
    uint32_t c = rgb565_to_rgb888(color);
    for (int i = 0; i < FB_W * FB_H; i++) fb[i] = c;
}

uint8_t g_backlight = 100;
void LCD_SetBacklight(uint8_t level) { g_backlight = level; }
uint8_t LCD_GetBacklight(void) { return g_backlight; }

void LCD_DrawPixel(uint16_t x, uint16_t y, uint16_t color) {
    set_px((int)x, (int)y, rgb565_to_rgb888(color));
}

void LCD_FillRect(uint16_t x, uint16_t y, uint16_t w, uint16_t h, uint16_t color) {
    uint32_t c = rgb565_to_rgb888(color);
    int x0 = (int)x, y0 = (int)y;
    int x1 = (int)x + (int)w - 1;
    int y1 = (int)y + (int)h - 1;
    if (x1 >= FB_W) x1 = FB_W - 1;
    if (y1 >= FB_H) y1 = FB_H - 1;
    for (int yy = y0; yy <= y1; yy++) {
        if (yy < 0 || yy >= FB_H) continue;
        for (int xx = x0; xx <= x1; xx++) {
            if (xx < 0 || xx >= FB_W) continue;
            fb[yy * FB_W + xx] = c;
        }
    }
}

void LCD_DrawRect(uint16_t x, uint16_t y, uint16_t w, uint16_t h, uint16_t color) {
    if (w == 0 || h == 0) return;
    LCD_FillRect(x, y, w, 1, color);
    LCD_FillRect(x, y + h - 1, w, 1, color);
    LCD_FillRect(x, y, 1, h, color);
    LCD_FillRect(x + w - 1, y, 1, h, color);
}

static void fill_circle_px(int cx, int cy, int r, uint32_t c) {
    int x = r, y = 0;
    int err = 0;
    while (x >= y) {
        // horizontal spans for filled circle
        for (int i = -x; i <= x; i++) { set_px(cx + i, cy + y, c); set_px(cx + i, cy - y, c); }
        for (int i = -y; i <= y; i++) { set_px(cx + i, cy + x, c); set_px(cx + i, cy - x, c); }
        y++;
        if (err <= 0) err += 2 * y + 1;
        if (err > 0) { x--; err -= 2 * x + 1; }
    }
}

void LCD_FillCircle(uint16_t x0, uint16_t y0, uint16_t r, uint16_t color) {
    fill_circle_px((int)x0, (int)y0, (int)r, rgb565_to_rgb888(color));
}

static void circle_outline_px(int cx, int cy, int r, uint32_t c) {
    int x = r, y = 0, err = 0;
    while (x >= y) {
        set_px(cx + x, cy + y, c); set_px(cx + y, cy + x, c);
        set_px(cx - y, cy + x, c); set_px(cx - x, cy + y, c);
        set_px(cx - x, cy - y, c); set_px(cx - y, cy - x, c);
        set_px(cx + y, cy - x, c); set_px(cx + x, cy - y, c);
        y++;
        if (err <= 0) err += 2 * y + 1;
        if (err > 0) { x--; err -= 2 * x + 1; }
    }
}

void LCD_DrawCircle(uint16_t x0, uint16_t y0, uint16_t r, uint16_t color) {
    circle_outline_px((int)x0, (int)y0, (int)r, rgb565_to_rgb888(color));
}

void LCD_DrawLine(uint16_t x0, uint16_t y0, uint16_t x1, uint16_t y1, uint16_t color) {
    uint32_t c = rgb565_to_rgb888(color);
    int dx = abs((int)x1 - (int)x0);
    int dy = -abs((int)y1 - (int)y0);
    int sx = x0 < x1 ? 1 : -1;
    int sy = y0 < y1 ? 1 : -1;
    int err = dx + dy;
    int x = (int)x0, y = (int)y0;
    for (;;) {
        set_px(x, y, c);
        if (x == (int)x1 && y == (int)y1) break;
        int e2 = 2 * err;
        if (e2 >= dy) { err += dy; x += sx; }
        if (e2 <= dx) { err += dx; y += sy; }
    }
}

void LCD_FillRoundRect(uint16_t x, uint16_t y, uint16_t w, uint16_t h, uint16_t r, uint16_t color) {
    uint32_t c = rgb565_to_rgb888(color);
    int x0 = (int)x, y0 = (int)y;
    int x1 = (int)x + (int)w - 1;
    int y1 = (int)y + (int)h - 1;
    int rr = (int)r;
    if (rr > (int)w / 2) rr = (int)w / 2;
    if (rr > (int)h / 2) rr = (int)h / 2;
    if (rr < 0) rr = 0;

    // Central rectangle
    for (int yy = y0 + rr; yy <= y1 - rr; yy++) {
        if (yy < 0 || yy >= FB_H) continue;
        for (int xx = x0; xx <= x1; xx++) {
            if (xx < 0 || xx >= FB_W) continue;
            fb[yy * FB_W + xx] = c;
        }
    }
    // Left / right bars
    for (int yy = y0; yy <= y1; yy++) {
        if (yy < 0 || yy >= FB_H) continue;
        for (int xx = x0 + rr; xx <= x1 - rr; xx++) {
            if (xx < 0 || xx >= FB_W) continue;
            fb[yy * FB_W + xx] = c;
        }
    }
    // Corner discs
    if (rr > 0) {
        fill_circle_px(x0 + rr, y0 + rr, rr, c);
        fill_circle_px(x1 - rr, y0 + rr, rr, c);
        fill_circle_px(x0 + rr, y1 - rr, rr, c);
        fill_circle_px(x1 - rr, y1 - rr, rr, c);
    }
}

void LCD_DrawRoundRect(uint16_t x, uint16_t y, uint16_t w, uint16_t h, uint16_t r, uint16_t color) {
    if (w == 0 || h == 0) return;
    uint32_t c = rgb565_to_rgb888(color);
    int x0 = (int)x, y0 = (int)y;
    int x1 = (int)x + (int)w - 1;
    int y1 = (int)y + (int)h - 1;
    int rr = (int)r;
    if (rr > (int)w / 2) rr = (int)w / 2;
    if (rr > (int)h / 2) rr = (int)h / 2;
    if (rr < 0) rr = 0;

    // Straight edges
    for (int xx = x0 + rr; xx <= x1 - rr; xx++) { set_px(xx, y0, c); set_px(xx, y1, c); }
    for (int yy = y0 + rr; yy <= y1 - rr; yy++) { set_px(x0, yy, c); set_px(x1, yy, c); }

    // One pixel per 45-degree octant per corner, mirrored into each quadrant.
    auto octants = [&](int cx, int cy, int dx, int dy) {
        int xx = rr, yy = 0, err = 0;
        while (xx >= yy) {
            set_px(cx + dx * xx, cy + dy * yy, c);
            set_px(cx + dx * yy, cy + dy * xx, c);
            yy++;
            if (err <= 0) err += 2 * yy + 1;
            if (err > 0) { xx--; err -= 2 * xx + 1; }
        }
    };
    octants(x0 + rr, y0 + rr, 1, -1);
    octants(x1 - rr, y0 + rr, -1, -1);
    octants(x0 + rr, y1 - rr, 1, 1);
    octants(x1 - rr, y1 - rr, -1, 1);
}

// ---------------------------------------------------------------------------
// Text - classic 5x7 font (same glyphs the device uses), scaled to match the
// device's per-size metrics (size 1 = 5x7/adv6, size 2 = 10x14/adv11,
// size >= 3 = 15x21/adv16).
// ---------------------------------------------------------------------------
static const uint8_t font_5x7[96][5] = {
    {0x00,0x00,0x00,0x00,0x00}, // space
    {0x00,0x00,0x5F,0x00,0x00}, // !
    {0x00,0x07,0x00,0x07,0x00}, // "
    {0x14,0x7F,0x14,0x7F,0x14}, // #
    {0x24,0x2A,0x7F,0x2A,0x12}, // $
    {0x23,0x13,0x08,0x64,0x62}, // %
    {0x36,0x49,0x55,0x22,0x50}, // &
    {0x00,0x05,0x03,0x00,0x00}, // '
    {0x00,0x1C,0x22,0x41,0x00}, // (
    {0x00,0x41,0x22,0x1C,0x00}, // )
    {0x08,0x2A,0x1C,0x2A,0x08}, // *
    {0x08,0x08,0x3E,0x08,0x08}, // +
    {0x00,0x50,0x30,0x00,0x00}, // ,
    {0x08,0x08,0x08,0x08,0x08}, // -
    {0x00,0x60,0x60,0x00,0x00}, // .
    {0x20,0x10,0x08,0x04,0x02}, // /
    {0x3E,0x51,0x49,0x45,0x3E}, // 0
    {0x00,0x42,0x7F,0x40,0x00}, // 1
    {0x42,0x61,0x51,0x49,0x46}, // 2
    {0x21,0x41,0x45,0x4B,0x31}, // 3
    {0x18,0x14,0x12,0x7F,0x10}, // 4
    {0x27,0x45,0x45,0x45,0x39}, // 5
    {0x3C,0x4A,0x49,0x49,0x30}, // 6
    {0x01,0x71,0x09,0x05,0x03}, // 7
    {0x36,0x49,0x49,0x49,0x36}, // 8
    {0x06,0x49,0x49,0x29,0x1E}, // 9
    {0x00,0x36,0x36,0x00,0x00}, // :
    {0x00,0x56,0x36,0x00,0x00}, // ;
    {0x00,0x08,0x14,0x22,0x41}, // <
    {0x14,0x14,0x14,0x14,0x14}, // =
    {0x41,0x22,0x14,0x08,0x00}, // >
    {0x02,0x01,0x51,0x09,0x06}, // ?
    {0x32,0x49,0x79,0x41,0x3E}, // @
    {0x7E,0x11,0x11,0x11,0x7E}, // A
    {0x7F,0x49,0x49,0x49,0x36}, // B
    {0x3E,0x41,0x41,0x41,0x22}, // C
    {0x7F,0x41,0x41,0x22,0x1C}, // D
    {0x7F,0x49,0x49,0x49,0x41}, // E
    {0x7F,0x09,0x09,0x01,0x01}, // F
    {0x3E,0x41,0x41,0x51,0x32}, // G
    {0x7F,0x08,0x08,0x08,0x7F}, // H
    {0x00,0x41,0x7F,0x41,0x00}, // I
    {0x20,0x40,0x41,0x3F,0x01}, // J
    {0x7F,0x08,0x14,0x22,0x41}, // K
    {0x7F,0x40,0x40,0x40,0x40}, // L
    {0x7F,0x02,0x04,0x02,0x7F}, // M
    {0x7F,0x04,0x08,0x10,0x7F}, // N
    {0x3E,0x41,0x41,0x41,0x3E}, // O
    {0x7F,0x09,0x09,0x09,0x06}, // P
    {0x3E,0x41,0x51,0x21,0x5E}, // Q
    {0x7F,0x09,0x19,0x29,0x46}, // R
    {0x46,0x49,0x49,0x49,0x31}, // S
    {0x01,0x01,0x7F,0x01,0x01}, // T
    {0x3F,0x40,0x40,0x40,0x3F}, // U
    {0x1F,0x20,0x40,0x20,0x1F}, // V
    {0x7F,0x20,0x18,0x20,0x7F}, // W
    {0x63,0x14,0x08,0x14,0x63}, // X
    {0x03,0x04,0x78,0x04,0x03}, // Y
    {0x61,0x51,0x49,0x45,0x43}, // Z
    {0x00,0x00,0x7F,0x41,0x41}, // [
    {0x02,0x04,0x08,0x10,0x20}, // backslash
    {0x41,0x41,0x7F,0x00,0x00}, // ]
    {0x04,0x02,0x01,0x02,0x04}, // ^
    {0x40,0x40,0x40,0x40,0x40}, // _
    {0x00,0x01,0x02,0x04,0x00}, // `
    {0x20,0x54,0x54,0x54,0x78}, // a
    {0x7F,0x48,0x44,0x44,0x38}, // b
    {0x38,0x44,0x44,0x44,0x20}, // c
    {0x38,0x44,0x44,0x48,0x7F}, // d
    {0x38,0x54,0x54,0x54,0x18}, // e
    {0x08,0x7E,0x09,0x01,0x02}, // f
    {0x08,0x14,0x54,0x54,0x3C}, // g
    {0x7F,0x08,0x04,0x04,0x78}, // h
    {0x00,0x44,0x7D,0x40,0x00}, // i
    {0x20,0x40,0x44,0x3D,0x00}, // j
    {0x00,0x7F,0x10,0x28,0x44}, // k
    {0x00,0x41,0x7F,0x40,0x00}, // l
    {0x7C,0x04,0x18,0x04,0x78}, // m
    {0x7C,0x08,0x04,0x04,0x78}, // n
    {0x38,0x44,0x44,0x44,0x38}, // o
    {0x7C,0x14,0x14,0x14,0x08}, // p
    {0x08,0x14,0x14,0x18,0x7C}, // q
    {0x7C,0x08,0x04,0x04,0x08}, // r
    {0x48,0x54,0x54,0x54,0x20}, // s
    {0x04,0x3F,0x44,0x40,0x20}, // t
    {0x3C,0x40,0x40,0x20,0x7C}, // u
    {0x1C,0x20,0x40,0x20,0x1C}, // v
    {0x3C,0x40,0x30,0x40,0x3C}, // w
    {0x44,0x28,0x10,0x28,0x44}, // x
    {0x0C,0x50,0x50,0x50,0x3C}, // y
    {0x44,0x64,0x54,0x4C,0x44}, // z
    {0x00,0x08,0x36,0x41,0x00}, // {
    {0x00,0x00,0x7F,0x00,0x00}, // |
    {0x00,0x41,0x36,0x08,0x00}, // }
    {0x08,0x08,0x2A,0x1C,0x08}, // ->
    {0x08,0x1C,0x2A,0x08,0x08}  // <-
};

// ---------------------------------------------------------------------------
// Anti-aliased font rendering (matches the device driver exactly)
// ---------------------------------------------------------------------------
// Same 1-bit fonts, but each glyph pixel is blended with a 4-bit coverage
// value derived by bilinear supersampling - smooth edges, no new fonts.
// ---------------------------------------------------------------------------

static uint8_t alpha_5x7[96 * 5 * 7];
static uint8_t alpha_10x14[96 * 10 * 14];
static uint8_t alpha_15x21[96 * 15 * 21];
static bool alpha_5x7_ready = false;
static bool alpha_10x14_ready = false;
static bool alpha_15x21_ready = false;

static inline int font5x7_bit(int g, int x, int y) {
    if (x < 0 || x >= 5 || y < 0 || y >= 7) return 0;
    return (font_5x7[g][x] >> y) & 1;
}

static inline int font10x14_bit(int g, int x, int y) {
    if (x < 0 || x >= 10 || y < 0 || y >= 14) return 0;
    return (font_10x14[g][y] >> (9 - x)) & 1;
}

static inline int font15x21_bit(int g, int x, int y) {
    if (x < 0 || x >= 15 || y < 0 || y >= 21) return 0;
    return (font_15x21[g][y] >> (14 - x)) & 1;
}

typedef int (*FontBitFn)(int g, int x, int y);

static float bilinearCoverage(FontBitFn glyphBit, int g, float fx, float fy) {
    int x0 = (int)floorf(fx);
    int y0 = (int)floorf(fy);
    float tx = fx - (float)x0;
    float ty = fy - (float)y0;
    float v00 = (float)glyphBit(g, x0, y0);
    float v10 = (float)glyphBit(g, x0 + 1, y0);
    float v01 = (float)glyphBit(g, x0, y0 + 1);
    float v11 = (float)glyphBit(g, x0 + 1, y0 + 1);
    return v00 * (1.0f - tx) * (1.0f - ty) + v10 * tx * (1.0f - ty)
         + v01 * (1.0f - tx) * ty + v11 * tx * ty;
}

static void computeAlphaTable(FontBitFn bit, int W, int H, uint8_t* out) {
    for (int g = 0; g < 96; g++) {
        for (int y = 0; y < H; y++) {
            for (int x = 0; x < W; x++) {
                float sum = bilinearCoverage(bit, g, x - 0.25f, y - 0.25f)
                          + bilinearCoverage(bit, g, x + 0.25f, y - 0.25f)
                          + bilinearCoverage(bit, g, x - 0.25f, y + 0.25f)
                          + bilinearCoverage(bit, g, x + 0.25f, y + 0.25f);
                int cov = (int)(sum * 15.0f / 4.0f + 0.5f);
                if (cov > 15) cov = 15;
                out[g * W * H + y * W + x] = (uint8_t)cov;
            }
        }
    }
}

static inline uint32_t rgb888Blend(uint32_t bg, uint32_t fg, uint8_t cov) {
    if (cov == 0) return bg;
    if (cov == 15) return fg;
    int br = (bg >> 16) & 0xFF, bg8 = (bg >> 8) & 0xFF, bb = bg & 0xFF;
    int fr = (fg >> 16) & 0xFF, fg8 = (fg >> 8) & 0xFF, fb = fg & 0xFF;
    int r = br + ((fr - br) * (int)cov) / 15;
    int g = bg8 + ((fg8 - bg8) * (int)cov) / 15;
    int b = bb + ((fb - bb) * (int)cov) / 15;
    return 0xFF000000u | ((uint32_t)r << 16) | ((uint32_t)g << 8) | (uint32_t)b;
}

void LCD_DrawPixelBlend(uint16_t x, uint16_t y, uint16_t color, uint16_t bg, uint8_t coverage) {
    if (coverage == 0) return;
    uint32_t fg = rgb565_to_rgb888(color);
    uint32_t bgc = rgb565_to_rgb888(bg);
    set_px((int)x, (int)y, (coverage >= 15) ? fg : rgb888Blend(bgc, fg, coverage));
}

void LCD_DrawChar(uint16_t x, uint16_t y, char c, uint16_t color, uint16_t bg, uint8_t size) {
    if (x >= FB_W || y >= FB_H) return;
    if (c < 32 || c > 127) c = '?';

    uint32_t fg = rgb565_to_rgb888(color);
    uint32_t bgc = rgb565_to_rgb888(bg);

    uint8_t* alpha;
    int W, H;
    if (size == 2) {
        if (!alpha_10x14_ready) { computeAlphaTable(font10x14_bit, 10, 14, alpha_10x14); alpha_10x14_ready = true; }
        alpha = alpha_10x14; W = 10; H = 14;
    } else if (size >= 3) {
        if (!alpha_15x21_ready) { computeAlphaTable(font15x21_bit, 15, 21, alpha_15x21); alpha_15x21_ready = true; }
        alpha = alpha_15x21; W = 15; H = 21;
    } else {
        if (!alpha_5x7_ready) { computeAlphaTable(font5x7_bit, 5, 7, alpha_5x7); alpha_5x7_ready = true; }
        alpha = alpha_5x7; W = 5; H = 7;
    }

    int g = c - 32;
    for (int row = 0; row < H; row++) {
        for (int col = 0; col < W; col++) {
            uint8_t cov = alpha[g * W * H + row * W + col];
            if (cov == 0) {
                if (bg != color) set_px((int)x + col, (int)y + row, bgc);
            } else {
                set_px((int)x + col, (int)y + row, (cov == 15) ? fg : rgb888Blend(bgc, fg, cov));
            }
        }
    }
}

void LCD_DrawString(uint16_t x, uint16_t y, const char* str, uint16_t color, uint16_t bg, uint8_t size) {
    int advance;
    int lineHeight;
    if (size == 2) { advance = 11; lineHeight = 14; }
    else if (size >= 3) { advance = 16; lineHeight = 21; }
    else { advance = 6; lineHeight = 8; }

    while (*str) {
        LCD_DrawChar(x, y, *str++, color, bg, size);
        x += advance;

        if ((int)x + advance > FB_W) {
            x = 0;
            y += lineHeight;
        }
        if ((int)y + lineHeight > FB_H) break;
    }
}

void LCD_DrawNumber(uint16_t x, uint16_t y, int32_t num, uint16_t color, uint16_t bg, uint8_t size) {
    char buf[12];
    snprintf(buf, sizeof(buf), "%ld", (long)num);
    LCD_DrawString(x, y, buf, color, bg, size);
}

// ---------------------------------------------------------------------------
// UI elements (parity stubs)
// ---------------------------------------------------------------------------
void LCD_DrawProgressBar(uint16_t x, uint16_t y, uint16_t w, uint16_t h,
                         uint8_t progress, uint16_t fg, uint16_t bg, uint16_t border) {
    LCD_DrawRect(x, y, w, h, border);
    LCD_FillRect(x + 1, y + 1, w - 2, h - 2, bg);
    if (progress > 100) progress = 100;
    uint16_t fill_w = (w - 2) * progress / 100;
    if (fill_w > 0) LCD_FillRect(x + 1, y + 1, fill_w, h - 2, fg);
}

void LCD_DrawArc(uint16_t x, uint16_t y, uint16_t r,
                 uint16_t start_angle, uint16_t end_angle, uint16_t color) {
    for (uint16_t angle = start_angle; angle <= end_angle; angle++) {
        float rad = angle * 3.14159f / 180.0f;
        int px = (int)x + (int)(r * cos(rad));
        int py = (int)y - (int)(r * sin(rad));
        LCD_DrawPixel(px, py, color);
    }
}

void LCD_DrawThickArc(uint16_t x, uint16_t y, uint16_t r, uint16_t thickness,
                      uint16_t start_angle, uint16_t end_angle, uint16_t color) {
    for (uint16_t t = 0; t < thickness; t++) {
        LCD_DrawArc(x, y, r - t, start_angle, end_angle, color);
    }
}

// ---------------------------------------------------------------------------
// Images (data is stored byte-swapped for the big-endian panel)
// ---------------------------------------------------------------------------
void LCD_DrawImage(uint16_t x, uint16_t y, uint16_t w, uint16_t h, const uint16_t* data) {
    for (uint16_t row = 0; row < h; row++) {
        for (uint16_t col = 0; col < w; col++) {
            int px = (int)x + (int)col;
            int py = (int)y + (int)row;
            if (px < 0 || px >= FB_W || py < 0 || py >= FB_H) continue;
            uint16_t raw = data[row * w + col];
            uint16_t rgb565 = (uint16_t)((raw << 8) | (raw >> 8));
            set_px(px, py, rgb565_to_rgb888(rgb565));
        }
    }
}

void LCD_DrawImageWithAlpha(uint16_t x, uint16_t y, uint16_t w, uint16_t h,
                            const uint16_t* rgb_data, const uint8_t* alpha_data,
                            uint16_t bg_color) {
    for (uint16_t row = 0; row < h; row++) {
        for (uint16_t col = 0; col < w; col++) {
            int px = (int)x + (int)col;
            int py = (int)y + (int)row;
            if (px < 0 || px >= FB_W || py < 0 || py >= FB_H) continue;
            if (alpha_data[row * w + col] > 128) {
                uint16_t raw = rgb_data[row * w + col];
                uint16_t rgb565 = (uint16_t)((raw << 8) | (raw >> 8));
                set_px(px, py, rgb565_to_rgb888(rgb565));
            } else {
                set_px(px, py, rgb565_to_rgb888(bg_color));
            }
        }
    }
}

void LCD_DrawImageCentered(uint16_t w, uint16_t h, const uint16_t* data) {
    LCD_DrawImage((FB_W - w) / 2, (FB_H - h) / 2, w, h, data);
}

void LCD_DrawImageScaled(uint16_t src_w, uint16_t src_h, const uint16_t* data,
                         uint16_t dst_x, uint16_t dst_y, uint16_t dst_w, uint16_t dst_h) {
    for (uint16_t dy = 0; dy < dst_h; dy++) {
        for (uint16_t dx = 0; dx < dst_w; dx++) {
            uint16_t sx = (uint16_t)((uint32_t)dx * src_w / dst_w);
            uint16_t sy = (uint16_t)((uint32_t)dy * src_h / dst_h);
            uint16_t raw = data[sy * src_w + sx];
            uint16_t rgb565 = (uint16_t)((raw << 8) | (raw >> 8));
            set_px((int)dst_x + dx, (int)dst_y + dy, rgb565_to_rgb888(rgb565));
        }
    }
}
