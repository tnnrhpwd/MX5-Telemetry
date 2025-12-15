#pragma once

#include "TCA9554PWR.h"
#include "Touch_CST816.h"

// Display configuration
#define LCD_WIDTH                   360
#define LCD_HEIGHT                  360
#define LCD_COLOR_BITS              16

// Backlight PWM
#define LCD_BL_PIN                  5
#define LCD_PWM_FREQ                20000
#define LCD_PWM_RESOLUTION          10
#define LCD_BACKLIGHT_MAX           100

// QSPI pins - matching Waveshare pinout
#define LCD_QSPI_CLK                40
#define LCD_QSPI_D0                 46
#define LCD_QSPI_D1                 45
#define LCD_QSPI_D2                 42
#define LCD_QSPI_D3                 41
#define LCD_CS_PIN                  21
#define LCD_TE_PIN                  18

extern uint8_t LCD_Backlight;

// Low-level initialization
bool QSPI_Init(void);
bool LCD_Init(void);

// Display control
void LCD_Clear(uint16_t color);
void LCD_SetBacklight(uint8_t brightness);
uint8_t LCD_GetBacklight(void);

// Simple drawing functions
void LCD_DrawPixel(uint16_t x, uint16_t y, uint16_t color);
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

// UI elements
void LCD_DrawProgressBar(uint16_t x, uint16_t y, uint16_t w, uint16_t h, 
                         uint8_t progress, uint16_t fg, uint16_t bg, uint16_t border);
void LCD_DrawArc(uint16_t x, uint16_t y, uint16_t r, 
                 uint16_t start_angle, uint16_t end_angle, uint16_t color);
void LCD_DrawThickArc(uint16_t x, uint16_t y, uint16_t r, uint16_t thickness,
                      uint16_t start_angle, uint16_t end_angle, uint16_t color);

// Image drawing (RGB565 format, data already byte-swapped for BIG endian)
void LCD_DrawImage(uint16_t x, uint16_t y, uint16_t w, uint16_t h, const uint16_t* data);
void LCD_DrawImageWithAlpha(uint16_t x, uint16_t y, uint16_t w, uint16_t h, 
                            const uint16_t* rgb_data, const uint8_t* alpha_data,
                            uint16_t bg_color);
void LCD_DrawImageCentered(uint16_t w, uint16_t h, const uint16_t* data);
void LCD_DrawImageScaled(uint16_t src_w, uint16_t src_h, const uint16_t* data, 
                         uint16_t dst_x, uint16_t dst_y, uint16_t dst_w, uint16_t dst_h);

// Color helpers
#define RGB565(r, g, b) (((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3))
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

