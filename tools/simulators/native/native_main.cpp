/**
 * @file native_main.cpp
 * @brief Native desktop simulator for the ESP32-S3 display UI.
 *
 * Compiles the REAL ui_core.cpp (same code the ESP32 runs) against a mock LCD
 * backend and shows it in a Win32 window. Edit display/src/ui_core/ui_core.cpp
 * and rebuild - the window shows exactly what the device would draw.
 *
 * Usage:
 *   simulator.exe                 interactive window: plays the power-on
 *                                 animation, then the Pi wait, then live
 *   simulator.exe --screenshot    render every screen to shot_0.bmp .. shot_7.bmp
 *   simulator.exe --startup       render the power-on sequence to boot_*.bmp,
 *                                 the Pi wait to wait_*.bmp (+ 1 fps frames),
 *                                 and the live Overview to live_0.bmp
 *
 * Interactive keys: B replays power-on, Enter/Space ends the Pi wait early,
 * everything else is listed under H.
 */

#define NOMINMAX
#define WIN32_LEAN_AND_MEAN

#include "ui_core.h"          // the real UI core + platform shim
#include "native_display.h"

#include <windows.h>
#include <cstdio>

static bool g_dirty = true;
static int g_scale = 2;       // window scale factor (360 -> 720)

// Defined further down; the power-on playback drives both.
static void renderCurrentScreen();
static void initDemoTelemetry();

// ---------------------------------------------------------------------------
// Power-on playback: animation -> Pi wait -> live
//
// ui_startupFrame() is the firmware's own renderer (ui_core.cpp) and the wait
// state is the Overview's own boot path (countdown in the gear disc, count-up
// ring, loading pill, WAITING ladder), so this walks the device's real power-on
// sequence instead of jumping straight to a connected dashboard.
// ---------------------------------------------------------------------------
enum SimPhase {
    PHASE_BOOT_ANIM = 0,   // 1.56 s startup sequence
    PHASE_PI_WAIT,         // PI_BOOT_COUNTDOWN seconds with no link
    PHASE_LIVE             // telemetry arriving
};

static SimPhase g_phase = PHASE_LIVE;
static unsigned long g_phaseStart = 0;
static int g_waitShown = -1;      // last countdown second painted
static bool g_waitHinted = false;
// P pressed: millis() of the kill, while the demo waits out the real link timeout.
// 0 = the link is not being held open.
static unsigned long g_linkKillAt = 0;

// Everything the device has before the first telemetry line.
static void clearTelemetry() {
    telemetry = TelemetryData{};
    piDataReceived = false;
    telemetry.connected = false;
    telemetry.hasReceivedTelemetry = false;
    prevTelemetry.initialized = false;
}

static void enterPiWait() {
    g_phase = PHASE_PI_WAIT;
    g_phaseStart = millis();
    // bootStartTime deliberately stays at power-on: the caption counts the real
    // 30 s, and the wait's ring restarts empty on its own.
    g_waitShown = -1;
    currentScreen = SCREEN_OVERVIEW;
    needsFullRedraw = true;
    needsRedraw = true;
    printf("[SIM] Intro done (%.1f s) - boot screen continues for the rest of the "
           "%d s wait (Enter/Space connects now).\n",
           UI_BOOT_ANIM_MS / 1000.0, PI_BOOT_COUNTDOWN);
}

static void connectNow() {
    g_phase = PHASE_LIVE;
    initDemoTelemetry();              // demo car, link up
    needsFullRedraw = true;
    needsRedraw = true;
    g_dirty = true;
    printf("[SIM] Link up - live Overview.\n");
}

static void startPowerOn() {
    g_phase = PHASE_BOOT_ANIM;
    g_phaseStart = millis();
    bootStartTime = g_phaseStart;     // the countdown is measured from power-on
    g_waitHinted = false;
    clearTelemetry();
    currentScreen = SCREEN_OVERVIEW;
    ui_startupFrame(0, true);
    g_dirty = false;
}

// Returns true while this owns the screen (the caller then just blits).
static bool tickPowerOn() {
    if (g_phase == PHASE_BOOT_ANIM) {
        unsigned long t = millis() - g_phaseStart;
        if (t >= UI_BOOT_ANIM_MS) {
            enterPiWait();
            return true;
        }
        ui_startupFrame(t);
        return true;
    }

    if (g_phase == PHASE_PI_WAIT) {
        // The countdown is measured from power-on, like the firmware's: the intro
        // already ate 22 s of the 30, so this phase only lasts the remaining 8 s.
        // Timing it from g_phaseStart instead would make the power-on sequence 22
        // + 30 s here and 30 s on the panel.
        if (millis() - bootStartTime >= (unsigned long)PI_BOOT_COUNTDOWN * 1000UL) {
            connectNow();
            return false;
        }
        // The wait is animated at 8 fps, exactly like the firmware's loop.
        unsigned long elapsed = millis() - g_phaseStart;
        unsigned long frame = elapsed / 125UL;
        if ((int)frame != g_waitShown) {
            g_waitShown = (int)frame;
            if (currentScreen == SCREEN_OVERVIEW) {
                needsRedraw = true;
                renderCurrentScreen();
                return true;
            }
        }
        return false;
    }

    return false;
}

static bool inPiWait() { return g_phase == PHASE_PI_WAIT; }

// ---------------------------------------------------------------------------
// Screen dispatch - identical to the switch in display/src/main.cpp loop()
// ---------------------------------------------------------------------------
static void renderCurrentScreen() {
    // A dead link outranks the selected screen, exactly as it does on the panel.
    if (ui_linkLostActive()) {
        ui_linkLostFrame();
    } else switch (currentScreen) {
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
    // Without this the Overview card renders "--" and the INST MPG row looks
    // broken in every screenshot taken from the simulator.
    telemetry.instantMPGValid = true;
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
    // While the boot animation runs, only replay and quit make sense.
    if (g_phase == PHASE_BOOT_ANIM && key != 'B' && key != 'b' && key != 'Q' && key != 'q') return;

    if (inPiWait() && (key == VK_RETURN || key == VK_SPACE)) {
        printf("[SIM] Link up - ending the Pi wait early.\n");
        connectNow();
        return;
    }

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
            telemetry.speed = telemetry.speed - 5; if (telemetry.speed < -20) telemetry.speed = -20; g_dirty = true; break;
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
        case 'B': case 'b': startPowerOn(); break;
        case 'P': case 'p':
            // Kill / restore the Pi link, so the takeover can be watched live.
            // (Not 'K': 0x6B is VK_ADD, the numpad plus, which is RPM up.)
            if (ui_linkLostActive()) {
                initDemoTelemetry();
                lastPiDataMs = millis();
                g_linkKillAt = 0;
                printf("[SIM] Link restored - back to the live screen.\n");
            } else {
                // "The Pi died while driving": stop refreshing the link and let the
                // panel's own 5 s timeout run, so the demo holds the last readings
                // and then hands over exactly like the firmware does. During the
                // boot wait there are no readings to hold, so make it live first.
                if (g_phase == PHASE_PI_WAIT) {
                    g_phase = PHASE_LIVE;
                    initDemoTelemetry();
                }
                piDataReceived = true;
                lastPiDataMs = millis();
                g_linkKillAt = millis();
                printf("[SIM] Pi link lost - holding for %d s, then the link-lost screen.\n",
                       PI_LINK_TIMEOUT_MS / 1000);
            }
            needsFullRedraw = true;
            needsRedraw = true;
            g_dirty = true;
            break;
        case 'H': case 'h':
            printf("\n=== ESP32-S3 UI Simulator controls ===\n");
            printf("Up/Down/Left/Right : previous/next screen\n");
            printf("1-8                : jump to screen (1=Overview .. 8=Settings)\n");
            printf("Enter              : select setting (Settings screen)\n");
            printf("Enter / Space      : connect now (while the Pi is 'booting')\n");
            printf("+/-                : RPM up/down      [ ] : speed up/down\n");
            printf("G                  : cycle gear        E   : toggle engine\n");
            printf("C                  : toggle clutch     L   : toggle nav lock\n");
            printf("B                  : replay power-on (animation + Pi wait)\n");
            printf("P                  : kill/restore the Pi link (link-lost screen)\n");
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

// ---------------------------------------------------------------------------
// Power-on capture: boot animation stills, the Pi wait, and the live Overview
// ---------------------------------------------------------------------------
static void captureBootFrames() {
    static const unsigned long ts[] = {
        0, 200, 600, 900, 1500, 2500, 3500, 5000, 6500, 8000,
        9000, 9600, 10200, 10600, 11000, 11800, 12500, 13500, 14500, 15500,
        16400, 16600, 17000, 18000, 19000, 20400, 21200, 22000
    };
    char name[64];
    for (int i = 0; i < (int)(sizeof(ts) / sizeof(ts[0])); i++) {
        ui_startupFrame(ts[i], true);
        snprintf(name, sizeof(name), "boot_%02d_%05lums.bmp", i, ts[i]);
        saveBMP(name);
    }

    // The whole intro at ~12 fps. Twenty-two seconds at 30 fps would be 660
    // 360x360 BMPs for no visible gain - the film's own frame rate is 25 fps and
    // the motion trails cover the rest - and this is only ever assembled into a
    // film.
    CreateDirectoryA("startup_frames", nullptr);
    int frame = 0;
    for (unsigned long t = 0; t <= UI_BOOT_ANIM_MS; t += 80, frame++) {
        ui_startupFrame(t, true);
        snprintf(name, sizeof(name), "startup_frames\\f%03d.bmp", frame);
        saveBMP(name);
    }
}

// The boot wait with no Pi yet: filling ring, orbiting comet, breathing emblem,
// rotating loading message and the seconds remaining.
static void captureBootWait(int elapsedSec, const char* path) {
    clearTelemetry();
    bootStartTime = millis() - (unsigned long)elapsedSec * 1000UL;
    currentScreen = SCREEN_OVERVIEW;
    prevTelemetry.initialized = false;
    needsFullRedraw = true;
    needsRedraw = true;
    renderCurrentScreen();
    if (path) saveBMP(path);
}

// The whole PI_BOOT_COUNTDOWN wait at 1 fps, so the 30 s can be replayed.
static void capturePiWaitSequence() {
    CreateDirectoryA("startup_frames_wait", nullptr);
    char name[80];
    for (int sec = 0; sec <= PI_BOOT_COUNTDOWN; sec++) {
        snprintf(name, sizeof(name), "startup_frames_wait\\w%03d.bmp", sec);
        captureBootWait(sec, name);
    }
}

static void captureLiveOverview(const char* path) {
    initDemoTelemetry();
    currentScreen = SCREEN_OVERVIEW;
    prevTelemetry.initialized = false;
    needsFullRedraw = true;
    needsRedraw = true;
    renderCurrentScreen();
    saveBMP(path);
}

// The link-lost screen: the Pi was streaming and then went quiet. Rendered from
// an explicit "seconds since the last packet" so the still is reproducible - the
// sweep's phase is derived from that, not from the wall clock.
static void captureLinkLost(unsigned long sinceMs, const char* path) {
    initDemoTelemetry();
    telemetry.connected = false;
    telemetry.hasReceivedTelemetry = false;
    bootStartTime = millis() - 60000UL;
    lastPiDataMs = millis() - sinceMs;
    prevTelemetry.initialized = false;
    needsFullRedraw = true;
    needsRedraw = true;
    renderCurrentScreen();
    if (path) saveBMP(path);
}

static int runStartupCapture() {
    applyDefaultTheme();
    captureBootFrames();

    captureBootWait(8,  "wait_00_intro8s.bmp");   // still in the intro: bloom
    captureBootWait(24, "wait_01_06s.bmp");       // wait, ring just started filling
    captureBootWait(28, "wait_02_02s.bmp");       // wait, ring all but full
    captureBootWait(31, "wait_03_over.bmp");      // countdown spent, still no Pi
    capturePiWaitSequence();
    captureLiveOverview("live_0_overview.bmp");

    // The link-lost takeover, at two depths of silence, plus a few sweep phases so
    // the radar can be checked without opening the window.
    // Silence past the panel's own timeout (5 s), far enough into the sweep that
    // the radar trail is visible in the still.
    captureLinkLost(6400,  "linklost_dark.bmp");
    captureLinkLost(70000, "linklost_1m.bmp");   // past a minute: "1m 10s", not "70s"
    for (int i = 0; i < 4; i++) {
        char sweep[64];
        snprintf(sweep, sizeof(sweep), "linklost_sweep_%d.bmp", i);
        captureLinkLost(6000 + (unsigned long)i * 500, sweep);
    }

    // Two seconds of the sweep at the firmware's 10 fps, for a film/GIF. The
    // phase comes from the silence, so the frames are evenly spaced in time.
    CreateDirectoryA("linklost_frames", nullptr);
    for (int i = 0; i < 20; i++) {
        char seq[64];
        snprintf(seq, sizeof(seq), "linklost_frames\\l%02d.bmp", i);
        captureLinkLost(6000 + (unsigned long)i * 100, seq);
    }

    // The same beats in the light theme: the boot title used to be drawn in
    // the theme's text colour on top of the dark logo, which made it vanish, and
    // a white flash is invisible on a near-white page.
    applyTheme("aurora", false);
    ui_startupFrame(5000, true);
    saveBMP("boot_light_film.bmp");
    ui_startupFrame(10300, true);          // the flash peak, see BOOT_T_FLASH_PEAK
    saveBMP("boot_light_impact.bmp");
    ui_startupFrame(UI_BOOT_ANIM_MS, true);
    saveBMP("boot_light_final.bmp");
    captureBootWait(26, "wait_light.bmp");
    captureLiveOverview("live_light.bmp");
    captureLinkLost(8200, "linklost_light.bmp");

    applyDefaultTheme();
    return 0;
}

// One frame per stored colour scheme, dark and light: proof that the opening
// paints from the theme rather than from fixed colours.
static int runThemeCapture() {
    char name[80];
    for (int i = 0; i < ui_themeCount(); i++) {
        const char* id = ui_themeId(i);
        for (int dark = 1; dark >= 0; dark--) {
            applyTheme(id, dark != 0);
            ui_startupFrame(5000, true);          // warp burst
            snprintf(name, sizeof(name), "theme_%02d_%s_%s_burst.bmp", i, id,
                     dark ? "dark" : "light");
            saveBMP(name);
            ui_startupFrame(10300, true);         // impact
            snprintf(name, sizeof(name), "theme_%02d_%s_%s_impact.bmp", i, id,
                     dark ? "dark" : "light");
            saveBMP(name);
            ui_startupFrame(UI_BOOT_ANIM_MS, true);
            snprintf(name, sizeof(name), "theme_%02d_%s_%s_final.bmp", i, id,
                     dark ? "dark" : "light");
            saveBMP(name);
        }
    }
    applyDefaultTheme();
    return 0;
}

static int runHeadless(bool reverse, bool stale, int demoSpeed) {
    initDemoTelemetry();
    if (demoSpeed > 0) {
        // Mostly for checking the gear ladder at motorway speed, where the
        // predicted RPM for 1st/2nd runs to five digits.
        telemetry.speed = (float)demoSpeed;
        telemetry.rpm = 2500;
        telemetry.gear = 6;
    }
    if (reverse) {
        // Reversing at walking pace: the case where the sign used to be clamped
        // to zero at the wire and rounded away by the display, so the speed read
        // "0" and the gear read "1" while the car was actually rolling back.
        telemetry.speed = -3;
        telemetry.gear = -1;
        telemetry.isInReverse = true;
        telemetry.rpm = 900;
        telemetry.throttle = 0;
    }
    if (stale) {
        // The Pi has gone quiet: the panel hands itself to the link-lost screen
        // rather than holding the last frame, whatever screen was selected.
        telemetry.connected = false;
        telemetry.hasReceivedTelemetry = false;
        telemetry.speed = 0;
        telemetry.rpm = 0;
        telemetry.gear = 0;
        telemetry.isInReverse = false;
        telemetry.throttle = 0;
        telemetry.brake = 0;
        telemetry.engineRunning = false;
        // 6.4 s of silence: past the panel's 5 s link timeout, and far enough
        // into the sweep that the radar trail is visible in the still.
        bootStartTime = millis() - 60000UL;
        lastPiDataMs = millis() - 6400UL;
    }
    const char* prefix = reverse ? "rev_" : (stale ? "stale_" : "shot_");
    char name[64];
    for (int s = 0; s < SCREEN_COUNT; s++) {
        goToScreen((ScreenMode)s);
        prevTelemetry.initialized = false;
        needsFullRedraw = true;
        renderCurrentScreen();
        snprintf(name, sizeof(name), "%s%d.bmp", prefix, s);
        saveBMP(name);
    }
    return 0;
}

int main(int argc, char** argv) {
    // Logs are the only trace of the phase machine; keep them unbuffered so they
    // appear even when the window is the thing being watched.
    setvbuf(stdout, nullptr, _IONBF, 0);

    bool headless = false;
    bool reverse = false;
    bool stale = false;
    bool startup = false;
    bool themes = false;
    int demoSpeed = 0;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--screenshot") == 0) headless = true;
        if (strcmp(argv[i], "--reverse") == 0) reverse = true;
        if (strcmp(argv[i], "--stale") == 0) stale = true;
        if (strcmp(argv[i], "--startup") == 0) startup = true;
        if (strcmp(argv[i], "--themes") == 0) themes = true;
        if (strncmp(argv[i], "--speed=", 8) == 0) demoSpeed = atoi(argv[i] + 8);
    }
    if (themes) return runThemeCapture();
    if (startup) return runStartupCapture();
    if (headless) return runHeadless(reverse, stale, demoSpeed);

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

    printf("\nESP32-S3 Display Simulator - press H for controls, Q to quit.\n");
    printf("Playing the real power-on sequence: %.1f s of intro, then the rest of the "
           "%d s Pi countdown (Enter/Space connects now).\n\n",
           UI_BOOT_ANIM_MS / 1000.0, PI_BOOT_COUNTDOWN);

    // Initial draw: the real power-on path - animation, Pi wait, live Overview.
    startPowerOn();

    MSG msg;
    for (;;) {
        while (PeekMessageA(&msg, nullptr, 0, 0, PM_REMOVE)) {
            if (msg.message == WM_QUIT) return 0;
            TranslateMessage(&msg);
            DispatchMessageA(&msg);
        }

        // The demo's stale watchdog: what display/src/main.cpp does at the same
        // instant the timeout expires - clear the readings, keep the stamp, and
        // let the dispatcher hand the panel to the link-lost screen.
        if (g_linkKillAt && millis() - g_linkKillAt > (unsigned long)PI_LINK_TIMEOUT_MS) {
            lastPiDataMs = g_linkKillAt;
            g_linkKillAt = 0;
            telemetry.connected = false;
            telemetry.hasReceivedTelemetry = false;
            telemetry.rpm = 0;
            telemetry.speed = 0;
            telemetry.gear = 0;
            telemetry.engineRunning = false;
            printf("[SIM] %d s of silence - link-lost screen takes the panel.\n",
                   PI_LINK_TIMEOUT_MS / 1000);
            g_dirty = true;
        }

        if (tickPowerOn()) {
            InvalidateRect(hwnd, nullptr, FALSE);
        } else if (ui_linkLostActive()) {
            // The waiting screen is an animation: 10 fps, same budget as the
            // firmware's link-lost tick.
            static unsigned long lastLinkFrame = 0;
            if (millis() - lastLinkFrame >= 100) {
                lastLinkFrame = millis();
                renderCurrentScreen();
                InvalidateRect(hwnd, nullptr, FALSE);
            }
            g_dirty = false;
        } else if (g_dirty) {
            g_dirty = false;
            renderCurrentScreen();
            InvalidateRect(hwnd, nullptr, FALSE);
        }
        Sleep(16); // ~60 FPS cap
    }
    return 0;
}
