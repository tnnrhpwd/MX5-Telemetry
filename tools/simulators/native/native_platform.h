/**
 * @file native_platform.h
 * @brief Minimal Arduino-compatibility shim for building ui_core on Windows.
 *
 * Provides the handful of Arduino names that the UI core uses, backed by the
 * C++ standard library only. No hardware, no Arduino headers.
 */

#ifndef NATIVE_PLATFORM_H
#define NATIVE_PLATFORM_H

#include <cstdint>
#include <cstddef>
#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <math.h>
#include <algorithm>

// PROGMEM is a flash placement attribute on AVR/ESP32. On a desktop build the
// arrays are just ordinary RAM constants.
#define PROGMEM

// Arduino defines PI; the C++ standard library does not.
#define PI 3.14159265358979323846f

// Arduino-style constrain
#ifndef constrain
#define constrain(amt, low, high) ((amt) < (low) ? (low) : ((amt) > (high) ? (high) : (amt)))
#endif

// Arduino brings min/max/abs into the global namespace.
using std::min;
using std::max;
using std::abs;

// Time base (implemented in native_display.cpp)
unsigned long millis();
unsigned long micros();
void delay(unsigned long ms);

// Random (implemented in native_display.cpp)
long random(long howbig);
long random(long howsmall, long howbig);

// ---------------------------------------------------------------------------
// Serial stub - routes printf-style output to stdout.
// ---------------------------------------------------------------------------
class NativeSerial {
public:
    void begin(unsigned long baud) { (void)baud; }
    int printf(const char* fmt, ...);
    int print(const char* s);
    int println(const char* s);
    int println();
    int print(int v);
    int println(int v);
};
extern NativeSerial Serial;

// ---------------------------------------------------------------------------
// ESP stub - only getFreeHeap() is used (System screen).
// ---------------------------------------------------------------------------
class NativeESP {
public:
    int getFreeHeap() const { return 260000; }
};
extern NativeESP ESP;

#endif // NATIVE_PLATFORM_H
