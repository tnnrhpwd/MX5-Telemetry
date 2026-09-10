/**
 * @file native_main.cpp
 * @brief Native desktop simulator for the ESP32-S3 display UI.
 *
 * Compiles the REAL ui_core.cpp (same code the ESP32 runs) against a mock LCD
 * backend and shows it in a Win32 window. Edit display/src/ui_core/ui_core.cpp
 * and rebuild - the window shows exactly what the device would draw.
 *
 * Usage:
 *   simulator.exe                 interactive window
 *   simulator.exe --screenshot    render every screen to shot_0.bmp .. shot_7.bmp
 */

#define NOMINMAX
#define WIN32_LEAN_AND_MEAN

#include "ui_core.h"          // the real UI core + platform shim
#include "native_display.h"

#include <windows.h>
#include <cstdio>

static bool g_dirty = true;
static int g_scale = 2;       // window scale factor (360 -> 720)

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
    g_dirty = true;
}

// ---------------------------------------------------------------------------
// Demo telemetry setup
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

    for (int i = 0; i < 4; i++) {
        snprintf(tpmsLastUpdateStr[i], 12, "12:%02d:00", 30 + i);
    }
}

// ---------------------------------------------------------------------------
// Keyboard -> device input mapping
// ---------------------------------------------------------------------------
static void adjustSelection() {
    // Enter on the settings screen: invoke the REAL touch-select logic by
    // synthesizing a tap in the middle of the currently selected row.
    int i = settingsSelection - settingsScrollOffset;
    int itemH = 52, itemGap = 8, startY = 55;
    int itemY = startY + i * (itemH + itemGap);
    handleSettingsTouch(CENTER_X, itemY + itemH / 2);
    needsFullRedraw = true;
    g_dirty = true;
}

static void handleKey(WPARAM key) {
    switch (key) {
        case VK_UP:    goToScreen((ScreenMode)((currentScreen - 1 + SCREEN_COUNT) % SCREEN_COUNT)); break;
        case VK_DOWN:  goToScreen((ScreenMode)((currentScreen + 1) % SCREEN_COUNT)); break;
        case VK_LEFT:  goToScreen((ScreenMode)((currentScreen - 1 + SCREEN_COUNT) % SCREEN_COUNT)); break;
        case VK_RIGHT: goToScreen((ScreenMode)((currentScreen + 1) % SCREEN_COUNT)); break;
        case VK_RETURN:
            if (currentScreen == SCREEN_SETTINGS) adjustSelection();
            break;
        case VK_ESCAPE: goToScreen(SCREEN_OVERVIEW); break;
        case '1': case '2': case '3': case '4':
        case '5': case '6': case '7': case '8':
            goToScreen((ScreenMode)(key - '1'));
            break;
        case VK_OEM_PLUS: case VK_ADD:
            telemetry.rpm = telemetry.rpm + 250; if (telemetry.rpm > 8000) telemetry.rpm = 8000; g_dirty = true; break;
        case VK_OEM_MINUS: case VK_SUBTRACT:
            telemetry.rpm = telemetry.rpm - 250; if (telemetry.rpm < 0) telemetry.rpm = 0; g_dirty = true; break;
        case VK_OEM_4: // [
            telemetry.speed = telemetry.speed - 5; if (telemetry.speed < 0) telemetry.speed = 0; g_dirty = true; break;
        case VK_OEM_6: // ]
            telemetry.speed = telemetry.speed + 5; if (telemetry.speed > 150) telemetry.speed = 150; g_dirty = true; break;
        case 'G': case 'g': {
            int gears[] = {0,1,2,3,4,5,6};
            int idx = 0;
            for (int i = 0; i < 7; i++) if (gears[i] == telemetry.gear) idx = i;
            telemetry.gear = gears[(idx + 1) % 7];
            g_dirty = true;
            break;
        }
        case 'E': case 'e': telemetry.engineRunning = !telemetry.engineRunning; g_dirty = true; break;
        case 'C': case 'c': telemetry.clutchEngaged = !telemetry.clutchEngaged; g_dirty = true; break;
        case 'L': case 'l': navLocked = !navLocked; needsFullRedraw = true; g_dirty = true; break;
        case 'H': case 'h':
            printf("\n=== ESP32-S3 UI Simulator controls ===\n");
            printf("Up/Down/Left/Right : previous/next screen\n");
            printf("1-8                : jump to screen (1=Overview .. 8=Settings)\n");
            printf("Enter              : select setting (Settings screen)\n");
            printf("+/-                : RPM up/down      [ ] : speed up/down\n");
            printf("G                  : cycle gear        E   : toggle engine\n");
            printf("C                  : toggle clutch     L   : toggle nav lock\n");
            printf("Esc                : go to Overview    Q   : quit\n\n");
            break;
        default: break;
    }
}

// ---------------------------------------------------------------------------
// Win32 window
// ---------------------------------------------------------------------------
static LRESULT CALLBACK wndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    switch (msg) {
        case WM_PAINT: {
            PAINTSTRUCT ps;
            HDC hdc = BeginPaint(hwnd, &ps);
            BITMAPINFO bmi = {0};
            bmi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
            bmi.bmiHeader.biWidth = native_framebuffer_width();
            bmi.bmiHeader.biHeight = -native_framebuffer_height(); // top-down
            bmi.bmiHeader.biPlanes = 1;
            bmi.bmiHeader.biBitCount = 32;
            bmi.bmiHeader.biCompression = BI_RGB;
            int w = native_framebuffer_width() * g_scale;
            int h = native_framebuffer_height() * g_scale;
            StretchDIBits(hdc, 0, 0, w, h,
                          0, 0, native_framebuffer_width(), native_framebuffer_height(),
                          native_framebuffer(), &bmi, DIB_RGB_COLORS, SRCCOPY);
            EndPaint(hwnd, &ps);
            return 0;
        }
        case WM_KEYDOWN:
            if (wParam == 'Q' || wParam == 'q') { PostQuitMessage(0); return 0; }
            handleKey(wParam);
            return 0;
        case WM_DESTROY:
            PostQuitMessage(0);
            return 0;
    }
    return DefWindowProc(hwnd, msg, wParam, lParam);
}

// ---------------------------------------------------------------------------
// BMP writer (headless mode)
// ---------------------------------------------------------------------------
static void saveBMP(const char* path) {
    int w = native_framebuffer_width();
    int h = native_framebuffer_height();
    const uint32_t* fb = native_framebuffer();

    FILE* f = fopen(path, "wb");
    if (!f) { fprintf(stderr, "cannot write %s\n", path); return; }

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

    uint8_t pad[4] = {0,0,0,0};
    for (int y = h - 1; y >= 0; y--) {
        for (int x = 0; x < w; x++) {
            uint32_t c = fb[y * w + x];
            uint8_t rgb[3] = { (uint8_t)(c & 0xFF), (uint8_t)((c >> 8) & 0xFF), (uint8_t)((c >> 16) & 0xFF) };
            fwrite(rgb, 1, 3, f);
        }
        fwrite(pad, 1, (size_t)(rowSize - w * 3), f);
    }
    fclose(f);
    printf("wrote %s\n", path);
}

static int runHeadless() {
    initDemoTelemetry();
    char name[64];
    for (int s = 0; s < SCREEN_COUNT; s++) {
        goToScreen((ScreenMode)s);
        prevTelemetry.initialized = false;
        needsFullRedraw = true;
        renderCurrentScreen();
        snprintf(name, sizeof(name), "shot_%d.bmp", s);
        saveBMP(name);
    }
    return 0;
}

int main(int argc, char** argv) {
    bool headless = false;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--screenshot") == 0) headless = true;
    }
    if (headless) return runHeadless();

    initDemoTelemetry();

    WNDCLASSA wc = {0};
    wc.lpfnWndProc = wndProc;
    wc.hInstance = GetModuleHandleA(nullptr);
    wc.lpszClassName = "MX5UISim";
    wc.hCursor = LoadCursor(nullptr, IDC_ARROW);
    wc.hbrBackground = (HBRUSH)GetStockObject(BLACK_BRUSH);
    RegisterClassA(&wc);

    int w = native_framebuffer_width() * g_scale;
    int h = native_framebuffer_height() * g_scale;
    DWORD style = WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX;
    RECT rc = {0, 0, w, h};
    AdjustWindowRect(&rc, style, FALSE);

    HWND hwnd = CreateWindowA("MX5UISim", "ESP32-S3 Display Simulator (360x360)",
                              style, CW_USEDEFAULT, CW_USEDEFAULT,
                              rc.right - rc.left, rc.bottom - rc.top,
                              nullptr, nullptr, wc.hInstance, nullptr);
    if (!hwnd) { fprintf(stderr, "CreateWindow failed\n"); return 1; }
    ShowWindow(hwnd, SW_SHOW);
    UpdateWindow(hwnd);

    printf("\nESP32-S3 Display Simulator - press H for controls, Q to quit.\n\n");

    // Initial draw
    needsFullRedraw = true;
    needsRedraw = true;

    MSG msg;
    for (;;) {
        while (PeekMessageA(&msg, nullptr, 0, 0, PM_REMOVE)) {
            if (msg.message == WM_QUIT) return 0;
            TranslateMessage(&msg);
            DispatchMessageA(&msg);
        }

        if (g_dirty) {
            g_dirty = false;
            renderCurrentScreen();
            InvalidateRect(hwnd, nullptr, FALSE);
        }
        Sleep(16); // ~60 FPS cap
    }
    return 0;
}
