/**
 * @file linux_shot.cpp
 * @brief Portable screenshot harness for the real UI core.
 *
 * native_main.cpp does the same job but is tied to Win32 for its interactive
 * window. The drawing side of the simulator (native_display.cpp) has no Win32
 * dependency at all, so this harness reuses it to render every screen to BMP on
 * any host with a C++ compiler. That means the images come from the same
 * ui_core.cpp the ESP32 runs, not a re-creation.
 *
 * Build (from the repo root):
 *   g++ -std=c++17 -O2 -DUI_CORE_NATIVE \
 *       -Idisplay/src/ui_core -Idisplay/src -Idisplay/include \
 *       -Itools/simulators/native \
 *       display/src/ui_core/ui_core.cpp \
 *       tools/simulators/native/native_display.cpp \
 *       tools/simulators/native/linux_shot.cpp -o /tmp/uishot
 *
 * Run:
 *   /tmp/uishot /tmp/shots        (writes /tmp/shots/shot_0.bmp .. shot_7.bmp)
 */

#include "ui_core.h"

#include <cstdio>
#include <cstring>

// ---------------------------------------------------------------------------
// Screen dispatch - identical to the switch in display/src/main.cpp loop()
// ---------------------------------------------------------------------------
static void renderCurrentScreen() {
    switch (currentScreen) {
        case SCREEN_OVERVIEW:     drawOverviewScreen(); break;
        case SCREEN_RPM:          drawRPMScreen(); break;
        case SCREEN_TPMS:         drawTPMSScreen(); break;
        case SCREEN_ENGINE:       drawEngineScreen(); break;
        case SCREEN_GFORCE:       drawGForceScreen(); break;
        case SCREEN_DIAGNOSTICS:  drawDiagnosticsScreen(); break;
        case SCREEN_SYSTEM:       drawSystemScreen(); break;
        case SCREEN_SETTINGS:     drawSettingsScreen(); break;
        default: break;
    }
    needsFullRedraw = false;
}

static void goToScreen(ScreenMode s) {
    if (s < 0 || s >= SCREEN_COUNT) return;
    currentScreen = s;
    needsFullRedraw = true;
    needsRedraw = true;
}

// ---------------------------------------------------------------------------
// Demo telemetry, so the screens show plausible values rather than zeros.
// Same values the interactive simulator uses.
// ---------------------------------------------------------------------------
static void initDemoTelemetry() {
    telemetry.rpm = 2500;
    telemetry.speed = 45;
    telemetry.gear = 3;
    telemetry.throttle = 25;
    telemetry.brake = 0;
    telemetry.coolantTemp = 190;
    telemetry.oilTemp = 205;
    telemetry.oilPressure = 40;
    telemetry.fuelLevel = 75;
    telemetry.ambientTemp = 72;
    telemetry.tirePressure[0] = 32.0f;
    telemetry.tirePressure[1] = 31.5f;
    telemetry.tirePressure[2] = 32.5f;
    telemetry.tirePressure[3] = 33.0f;
    telemetry.tireTemp[0] = 95; telemetry.tireTemp[1] = 96;
    telemetry.tireTemp[2] = 94; telemetry.tireTemp[3] = 95;
    telemetry.gForceX = 0.1f;
    telemetry.gForceY = 0.05f;
    telemetry.gForceZ = 1.0f;
    telemetry.linearAccelX = 0.02f;
    telemetry.linearAccelY = 0.1f;
    telemetry.averageMPG = 27;
    telemetry.instantMPG = 32.5f;
    telemetry.rangeMiles = 280;
    telemetry.engineRunning = true;
    telemetry.connected = true;
    telemetry.hasDiagnosticData = true;
    telemetry.hasReceivedTelemetry = true;
    telemetry.gearEstimated = false;
    telemetry.clutchEngaged = false;
    telemetry.gearColor = 0;
    telemetry.checkEngine = false;
    telemetry.absWarning = false;
    telemetry.oilWarning = false;
    telemetry.batteryWarning = false;
    telemetry.headlightsOn = false;
    telemetry.highBeamsOn = false;
    telemetry.batteryVoltage = 13.8f;

    piDataReceived = true;
    imuAvailable = true;
    orientationPitch = 0;
    orientationRoll = 0;
}

// ---------------------------------------------------------------------------
// BMP writer (24-bit, bottom-up), copied from native_main.cpp
// ---------------------------------------------------------------------------
static void saveBMP(const char* path) {
    int w = native_framebuffer_width();
    int h = native_framebuffer_height();
    const uint32_t* fb = native_framebuffer();

    FILE* f = fopen(path, "wb");
    if (!f) {
        fprintf(stderr, "cannot write %s\n", path);
        return;
    }

    int rowSize = (w * 3 + 3) & ~3;
    int dataSize = rowSize * h;
    int fileSize = 54 + dataSize;

    uint8_t hdr[54] = {0};
    hdr[0] = 'B'; hdr[1] = 'M';
    hdr[2] = (uint8_t)(fileSize); hdr[3] = (uint8_t)(fileSize >> 8);
    hdr[4] = (uint8_t)(fileSize >> 16); hdr[5] = (uint8_t)(fileSize >> 24);
    hdr[10] = 54;
    hdr[14] = 40;
    hdr[18] = (uint8_t)(w); hdr[19] = (uint8_t)(w >> 8);
    hdr[20] = (uint8_t)(w >> 16); hdr[21] = (uint8_t)(w >> 24);
    hdr[22] = (uint8_t)(h); hdr[23] = (uint8_t)(h >> 8);
    hdr[24] = (uint8_t)(h >> 16); hdr[25] = (uint8_t)(h >> 24);
    hdr[26] = 1;
    hdr[28] = 24;
    hdr[34] = (uint8_t)(dataSize); hdr[35] = (uint8_t)(dataSize >> 8);
    hdr[36] = (uint8_t)(dataSize >> 16); hdr[37] = (uint8_t)(dataSize >> 24);
    fwrite(hdr, 1, 54, f);

    uint8_t pad[4] = {0, 0, 0, 0};
    for (int y = h - 1; y >= 0; y--) {
        for (int x = 0; x < w; x++) {
            uint32_t c = fb[y * w + x];
            uint8_t rgb[3] = {
                (uint8_t)(c & 0xFF), (uint8_t)((c >> 8) & 0xFF), (uint8_t)((c >> 16) & 0xFF)
            };
            fwrite(rgb, 1, 3, f);
        }
        fwrite(pad, 1, (size_t)(rowSize - w * 3), f);
    }
    fclose(f);
    printf("wrote %s\n", path);
}

int main(int argc, char** argv) {
    const char* dir = (argc > 1) ? argv[1] : ".";

    initDemoTelemetry();

    char name[512];
    for (int s = 0; s < SCREEN_COUNT; s++) {
        goToScreen((ScreenMode)s);
        prevTelemetry.initialized = false;
        needsFullRedraw = true;
        renderCurrentScreen();
        snprintf(name, sizeof(name), "%s/shot_%d.bmp", dir, s);
        saveBMP(name);
    }
    return 0;
}
