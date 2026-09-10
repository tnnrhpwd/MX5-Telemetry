/**
 * @file native_display.h
 * @brief Mock of the Waveshare Display_ST77916 drawing API for the desktop
 *        simulator. Same function signatures as the real driver, but each call
 *        writes into a 360x360 RGB888 framebuffer that the harness blits to a
 *        Win32 window (or writes out as BMP in headless mode).
 */

#ifndef NATIVE_DISPLAY_H
#define NATIVE_DISPLAY_H

#include "native_platform.h"

// Color helpers (match Display_ST77916.h)
#define RGB565(r, g, b) ((((uint16_t)(r) & 0xF8) << 8) | (((uint16_t)(g) & 0xFC) << 3) | ((uint16_t)(b) >> 3))
#define COLOR_BLACK     0x0000
#define COLOR_WHITE     0xFFFF
#define COLOR_RED       0xF800
#define COLOR_GREEN     0x07E0
#define COLOR_BLUE      0x001F
#define COLOR_YELLOW    0xFFE0
#define COLOR_CYAN      0x07FF
#define COLOR_MAGENTA   0xF81F
#define COLOR_ORANGE    0xFD20
#define COLOR_GRAY      0x8410
#define COLOR_DARKGRAY  0x4208

// Display control
void LCD_Clear(uint16_t color);
void LCD_SetBacklight(uint8_t brightness);
uint8_t LCD_GetBacklight(void);

// Simple drawing functions
void LCD_DrawPixel(uint16_t x, uint16_t y, uint16_t color);
void LCD_DrawPixelBlend(uint16_t x, uint16_t y, uint16_t color, uint16_t bg, uint8_t coverage);
void LCD_FillRect(uint16_t x, uint16_t y, uint16_t w, uint16_t h, uint16_t color);
void LCD_DrawRect(uint16_t x, uint16_t y, uint16_t w, uint16_t h, uint16_t color);
void LCD_FillRoundRect(uint16_t x, uint16_t y, uint16_t w, uint16_t h, uint16_t r, uint16_t color);
void LCD_DrawRoundRect(uint16_t x, uint16_t y, uint16_t w, uint16_t h, uint16_t r, uint16_t color);
void LCD_DrawLine(uint16_t x0, uint16_t y0, uint16_t x1, uint16_t y1, uint16_t color);
void LCD_FillCircle(uint16_t x0, uint16_t y0, uint16_t r, uint16_t color);
void LCD_DrawCircle(uint16_t x0, uint16_t y0, uint16_t r, uint16_t color);

// Text drawing
void LCD_DrawChar(uint16_t x, uint16_t y, char c, uint16_t color, uint16_t bg, uint8_t size);
void LCD_DrawString(uint16_t x, uint16_t y, const char* str, uint16_t color, uint16_t bg, uint8_t size);
void LCD_DrawNumber(uint16_t x, uint16_t y, int32_t num, uint16_t color, uint16_t bg, uint8_t size);

// UI elements (unused by ui_core but declared for parity)
void LCD_DrawProgressBar(uint16_t x, uint16_t y, uint16_t w, uint16_t h,
                         uint8_t progress, uint16_t fg, uint16_t bg, uint16_t border);
void LCD_DrawArc(uint16_t x, uint16_t y, uint16_t r,
                 uint16_t start_angle, uint16_t end_angle, uint16_t color);
void LCD_DrawThickArc(uint16_t x, uint16_t y, uint16_t r, uint16_t thickness,
                      uint16_t start_angle, uint16_t end_angle, uint16_t color);

// Image drawing (RGB565 big-endian-swapped data, exactly like the converter)
void LCD_DrawImage(uint16_t x, uint16_t y, uint16_t w, uint16_t h, const uint16_t* data);
void LCD_DrawImageWithAlpha(uint16_t x, uint16_t y, uint16_t w, uint16_t h,
                            const uint16_t* rgb_data, const uint8_t* alpha_data,
                            uint16_t bg_color);
void LCD_DrawImageCentered(uint16_t w, uint16_t h, const uint16_t* data);
void LCD_DrawImageScaled(uint16_t src_w, uint16_t src_h, const uint16_t* data,
                         uint16_t dst_x, uint16_t dst_y, uint16_t dst_w, uint16_t dst_h);

// ---------------------------------------------------------------------------
// Framebuffer access for the harness
// ---------------------------------------------------------------------------
// Returns the 360x360 RGBA (0x00RRGGBB) framebuffer, width = 360, height = 360.
const uint32_t* native_framebuffer();
int native_framebuffer_width();
int native_framebuffer_height();

#endif // NATIVE_DISPLAY_H
