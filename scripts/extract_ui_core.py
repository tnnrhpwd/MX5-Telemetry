#!/usr/bin/env python3
"""
One-time migration helper: strip the UI code out of display/src/main.cpp.

The UI code now lives in display/src/ui_core/ui_core.{h,cpp}. This script
removes the moved definitions/function bodies from main.cpp so it no longer
duplicates them. It operates on exact text markers and fails loudly if a
marker is missing or ambiguous, so it can be re-run safely during review.
"""
import sys
from pathlib import Path

MAIN = Path(r"c:\Users\tanne\Documents\Github\MX5-Telemetry\display\src\main.cpp")


def delete_range(text, start, end, inclusive_end, label):
    """Remove text[start_idx : end_idx], where end_idx is the index of `end`
    (inclusive of the marker if inclusive_end, exclusive otherwise)."""
    si = text.find(start)
    if si == -1:
        print(f"[MISS] start marker not found: {label!r} -> {start!r}")
        return text, False

    if start == end:
        # Single-line deletion
        new = text[:si] + text[si + len(start):]
        print(f"[OK] removed {len(start):5d} chars  ({label})")
        return new, True

    if text.find(start, si + 1) != -1:
        print(f"[AMBIG] start marker ambiguous: {label!r}")
    ei = text.find(end, si + len(start))
    if ei == -1:
        print(f"[MISS] end marker not found: {label!r} -> {end!r}")
        return text, False
    if inclusive_end:
        ei = ei + len(end)
    new = text[:si] + text[ei:]
    print(f"[OK] removed {ei - si:5d} chars  ({label})")
    return new, True


def delete_lines(text, start, end, label):
    """Delete from start marker through the full line containing `end`."""
    return delete_range(text, start, end, inclusive_end=True, label=label)


def delete_upto(text, start, end, label):
    """Delete from start marker up to (not including) `end`."""
    return delete_range(text, start, end, inclusive_end=False, label=label)


def main():
    text = MAIN.read_text(encoding="utf-8")

    ops = [
        # --- top-level definitions moved to ui_core.h / ui_core.cpp ---
        ("dimensions+colors",
         delete_lines, "#define SCREEN_WIDTH  360",
         "#define LED_RED       RGB565(255, 0, 0)       // 5500+ RPM"),
        ("TelemetryData struct + instance",
         delete_lines, "struct TelemetryData {", "TelemetryData telemetry = {0};"),
        ("clutchDisplayMode",
         delete_lines, "int clutchDisplayMode = 0;  // 0=Gear#(colored), 1='C', 2='S', 3='-'",
         "int clutchDisplayMode = 0;  // 0=Gear#(colored), 1='C', 2='S', 3='-'"),
        ("CachedTelemetry + instance",
         delete_lines, "struct CachedTelemetry {", "CachedTelemetry prevTelemetry = {0};"),
        ("LEDSequence enum + names",
         delete_lines, "enum LEDSequence {",
         '    "Center-In"             // 4: From center outward\n};'),
        ("DisplaySettings + instance",
         delete_lines, "struct DisplaySettings {", "DisplaySettings settings;"),
        ("imuAvailable",
         delete_lines, "bool imuAvailable = false;", "bool imuAvailable = false;"),
        ("ScreenMode enum + SCREEN_NAMES",
         delete_lines, "enum ScreenMode {",
         '    "G-Force", "Diagnostics", "System", "Settings"\n};'),
        ("currentScreen",
         delete_lines, "ScreenMode currentScreen = SCREEN_OVERVIEW;",
         "ScreenMode currentScreen = SCREEN_OVERVIEW;"),
        ("needsRedraw",
         delete_lines, "bool needsRedraw = true;", "bool needsRedraw = true;"),
        ("needsFullRedraw",
         delete_lines, "bool needsFullRedraw = true;  // Set to true on screen change to redraw background",
         "bool needsFullRedraw = true;  // Set to true on screen change to redraw background"),
        ("navLocked",
         delete_lines, "bool navLocked = false;       // Navigation lock state (from Pi SWC handler)",
         "bool navLocked = false;       // Navigation lock state (from Pi SWC handler)"),
        ("boot countdown",
         delete_lines, "const int PI_BOOT_COUNTDOWN = 30;  // Seconds to countdown from",
         "int lastBootCountdown = 99;        // Track countdown for redraw detection (start high so first frame triggers)"),
        ("loading messages",
         delete_lines, "const char* LOADING_MESSAGES[] = {",
         "unsigned long lastMessageChange = 0;"),
        ("transition enum + globals",
         delete_lines, "enum TransitionType {", "ScreenMode transitionToScreen = SCREEN_OVERVIEW;"),
        ("settings menu state",
         delete_lines, "int settingsSelection = 0;",
         "const int SETTINGS_VISIBLE = 4;  // How many items fit on round screen (reduced from 5 to avoid edge clipping)"),
        # --- UI function bodies moved to ui_core.cpp ---
        ("transition functions",
         delete_lines, "void drawBackground() {", "// === END TRANSITION FUNCTIONS ==="),
        ("main UI block (screens)",
         delete_upto, "void drawLargeGear(int centerX, int centerY, const char* str, uint16_t color, uint16_t bgColor) {",
         'static String serialBuffer = "";'),
        ("sendSettingToPI overloads",
         delete_upto, "void sendSettingToPI(const char* name, int value) {",
         "void sendAllSettingsToPI() {"),
        ("orientation globals",
         delete_lines, "static float orientationPitch = 0;  // Pitch angle in degrees (nose up/down)",
         "static float orientationPitch = 0;  // Pitch angle in degrees (nose up/down)"),
        ("orientation globals (roll)",
         delete_lines, "static float orientationRoll = 0;   // Roll angle in degrees (left/right tilt)",
         "static float orientationRoll = 0;   // Roll angle in degrees (left/right tilt)"),
    ]

    ok = True
    for label, fn, start, end in ops:
        text, good = fn(text, start, end, label)
        ok = ok and good

    if not ok:
        print("\nABORT: one or more markers were not found; main.cpp left unchanged.")
        sys.exit(1)

    # Insert the ui_core include after car_image.h
    anchor = '#include "car_image.h"\n'
    if anchor in text and '#include "ui_core/ui_core.h"' not in text:
        text = text.replace(anchor, anchor + '#include "ui_core/ui_core.h"\n', 1)
        print("[OK] inserted ui_core include")
    elif '#include "ui_core/ui_core.h"' in text:
        print("[OK] ui_core include already present")
    else:
        print("[MISS] car_image.h anchor not found; include not inserted")
        ok = False

    if not ok:
        sys.exit(1)

    MAIN.write_text(text, encoding="utf-8")
    print(f"\nWrote {MAIN} ({len(text.splitlines())} lines)")


if __name__ == "__main__":
    main()
