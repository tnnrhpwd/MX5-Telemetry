#pragma once
#include <stdint.h>

// High resolution fonts for smooth rendering at larger sizes
// Font 10x14 - for size 2 text (replaces scaled 5x7)
// Each character: 10 bits wide × 14 rows = 14 uint16_t values
extern const uint16_t font_10x14[96][14];

// Font 15x21 - for size 3/4 text (replaces scaled 5x7)
// Each character: 15 bits wide × 21 rows = 21 uint16_t values
extern const uint16_t font_15x21[96][21];
