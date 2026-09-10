/**
 * @file ui_core_platform.h
 * @brief Platform abstraction for the shared UI core.
 *
 * On the ESP32 this pulls in the Arduino environment (which provides
 * `millis()`, `constrain()`, `min`/`max`, `PI`, `PROGMEM`, `Serial`, `ESP`,
 * `uint16_t`, etc.).
 *
 * In the native desktop simulator (UI_CORE_NATIVE) it pulls in a small shim
 * that provides the same names using only the C++ standard library + Win32.
 */

#ifndef UI_CORE_PLATFORM_H
#define UI_CORE_PLATFORM_H

#ifdef UI_CORE_NATIVE
  #include "native_platform.h"
#else
  #include <Arduino.h>
#endif

#endif // UI_CORE_PLATFORM_H
