/*
 * ============================================================================
 * MX5-Telemetry Display Module - ESP32-S3 Round Touch Screen
 * ============================================================================
 * 
 * UI identical to Python simulator - see tools/simulators/ui_simulator/
 * 
 * HARDWARE:
 * - ESP32-S3 with 1.85" Round Touch Screen (360x360 IPS LCD)
 * - Built-in QMI8658 IMU for G-Force measurement
 * - 8Ω 2W Speaker with onboard Audio Codec
 * 
 * SCREENS (synchronized with Pi display):
 * 1. Overview    - Gear, speed, TPMS summary, alerts
 * 2. RPM/Speed   - Primary driving data with arc gauge
 * 3. TPMS        - Tire pressure and temperatures
 * 4. Engine      - Coolant, oil, fuel, voltage
 * 5. G-Force     - Lateral and longitudinal G visualization
 * 6. Settings    - Configuration options
 * 
 * CONTROLS (SWC - Steering Wheel Controls):
 * - RES+/SET-   = Navigate between screens
 * - VOL+/VOL-   = Adjust values (in settings)
 * - ON/OFF      = Select / Enter settings
 * - CANCEL      = Exit settings / Back
 * 
 * ============================================================================
 */

#include <Arduino.h>

// Display library
#define LGFX_USE_V1
#include <LovyanGFX.hpp>

// UI components
#include "ui_config.h"
#include "ui_renderer.h"

// ============================================================================
// Display Configuration for 1.85" Round LCD (GC9A01)
// ============================================================================
class LGFX : public lgfx::LGFX_Device {
    lgfx::Panel_GC9A01 _panel_instance;
    lgfx::Bus_SPI _bus_instance;
    lgfx::Light_PWM _light_instance;
    lgfx::Touch_FT5x06 _touch_instance;

public:
    LGFX(void) {
        // SPI Bus Configuration
        {
            auto cfg = _bus_instance.config();
            cfg.spi_host = SPI2_HOST;
            cfg.spi_mode = 0;
            cfg.freq_write = 80000000;
            cfg.freq_read = 16000000;
            cfg.spi_3wire = true;
            cfg.use_lock = true;
            cfg.dma_channel = SPI_DMA_CH_AUTO;
            
            // Pin configuration - adjust based on your specific board
            cfg.pin_sclk = 12;  // SCK
            cfg.pin_mosi = 11;  // MOSI
            cfg.pin_miso = -1;  // Not used
            cfg.pin_dc = 8;     // Data/Command
            
            _bus_instance.config(cfg);
            _panel_instance.setBus(&_bus_instance);
        }

        // Panel Configuration
        {
            auto cfg = _panel_instance.config();
            cfg.pin_cs = 10;    // Chip Select
            cfg.pin_rst = 14;   // Reset
            cfg.pin_busy = -1;  // Not used
            
            cfg.panel_width = DISPLAY_SIZE;
            cfg.panel_height = DISPLAY_SIZE;
            cfg.offset_x = 0;
            cfg.offset_y = 0;
            cfg.offset_rotation = 0;
            cfg.dummy_read_pixel = 8;
            cfg.dummy_read_bits = 1;
            cfg.readable = true;
            cfg.invert = true;
            cfg.rgb_order = false;
            cfg.dlen_16bit = false;
            cfg.bus_shared = true;
            
            _panel_instance.config(cfg);
        }

        // Backlight Configuration
        {
            auto cfg = _light_instance.config();
            cfg.pin_bl = 45;    // Backlight PWM pin
            cfg.invert = false;
            cfg.freq = 44100;
            cfg.pwm_channel = 7;
            
            _light_instance.config(cfg);
            _panel_instance.setLight(&_light_instance);
        }

        // Touch Configuration (FT5x06/FT6206)
        {
            auto cfg = _touch_instance.config();
            cfg.x_min = 0;
            cfg.x_max = DISPLAY_SIZE - 1;
            cfg.y_min = 0;
            cfg.y_max = DISPLAY_SIZE - 1;
            cfg.pin_int = 3;    // Touch interrupt
            cfg.bus_shared = true;
            cfg.offset_rotation = 0;
            
            // I2C configuration for touch
            cfg.i2c_port = 0;
            cfg.i2c_addr = 0x38;
            cfg.pin_sda = 4;
            cfg.pin_scl = 5;
            cfg.freq = 400000;
            
            _touch_instance.config(cfg);
            _panel_instance.setTouch(&_touch_instance);
        }

        setPanel(&_panel_instance);
    }
};

// ============================================================================
// Global Objects
// ============================================================================
LGFX display;
UIRenderer* ui = nullptr;

// State
Screen currentScreen = SCREEN_OVERVIEW;
bool sleeping = false;
bool demoMode = true;
int demoRpmDir = 1;

// Data
TelemetryData telemetry;
DisplaySettings settings;

// Timing
uint32_t lastUpdate = 0;
uint32_t lastRender = 0;
const uint32_t UPDATE_INTERVAL = 50;    // 20 Hz telemetry update
const uint32_t RENDER_INTERVAL = 33;    // ~30 FPS

// ============================================================================
// Button Handling (placeholder - connect to actual SWC input)
// ============================================================================
ButtonEvent readButton() {
    // TODO: Implement actual button reading from CAN bus or GPIO
    // For now, use touch screen for navigation
    
    static uint32_t lastTouch = 0;
    static int16_t lastTouchY = -1;
    
    uint16_t x, y;
    if (display.getTouch(&x, &y)) {
        if (millis() - lastTouch > 300) {  // Debounce
            lastTouch = millis();
            
            // Swipe detection
            if (lastTouchY >= 0) {
                int dy = y - lastTouchY;
                if (dy < -50) return BTN_RES_PLUS;   // Swipe up = previous screen
                if (dy > 50) return BTN_SET_MINUS;   // Swipe down = next screen
            }
            lastTouchY = y;
            
            // Tap zones
            if (y < 120) return BTN_RES_PLUS;        // Top = previous
            if (y > 240) return BTN_SET_MINUS;       // Bottom = next
            if (x < 120) return BTN_VOL_DOWN;        // Left = decrease
            if (x > 240) return BTN_VOL_UP;          // Right = increase
            return BTN_ON_OFF;                        // Center = select
        }
    } else {
        lastTouchY = -1;
    }
    
    return BTN_NONE;
}

void handleButton(ButtonEvent btn) {
    if (btn == BTN_NONE) return;
    
    if (currentScreen == SCREEN_SETTINGS) {
        // Settings navigation
        int sel = ui->getSettingsSelection();
        bool editMode = ui->getSettingsEditMode();
        
        if (btn == BTN_RES_PLUS && !editMode) {
            if (sel > 0) ui->setSettingsSelection(sel - 1);
        }
        else if (btn == BTN_SET_MINUS && !editMode) {
            if (sel < 6) ui->setSettingsSelection(sel + 1);
        }
        else if (btn == BTN_ON_OFF) {
            if (sel == 6) {  // Back
                currentScreen = SCREEN_OVERVIEW;
                ui->setSettingsSelection(0);
            } else {
                ui->setSettingsEditMode(!editMode);
            }
        }
        else if (btn == BTN_CANCEL) {
            if (editMode) {
                ui->setSettingsEditMode(false);
            } else {
                currentScreen = SCREEN_OVERVIEW;
                ui->setSettingsSelection(0);
            }
        }
        else if (editMode) {
            int delta = (btn == BTN_VOL_UP) ? 1 : ((btn == BTN_VOL_DOWN) ? -1 : 0);
            if (delta != 0) {
                switch (sel) {
                    case 0: settings.brightness = constrain(settings.brightness + delta * 5, 10, 100); break;
                    case 1: settings.shift_rpm = constrain(settings.shift_rpm + delta * 100, 4000, 7500); break;
                    case 2: settings.redline_rpm = constrain(settings.redline_rpm + delta * 100, 5000, 8000); break;
                    case 3: settings.use_mph = !settings.use_mph; break;
                    case 4: settings.tire_low_psi = constrain(settings.tire_low_psi + delta * 0.5f, 20.0f, 35.0f); break;
                    case 5: settings.coolant_warn_f = constrain(settings.coolant_warn_f + delta * 5, 180, 250); break;
                }
                // Apply brightness immediately
                if (sel == 0) {
                    display.setBrightness(settings.brightness * 255 / 100);
                }
            }
        }
    } else {
        // Normal screen navigation
        if (btn == BTN_RES_PLUS) {
            int s = (int)currentScreen - 1;
            if (s < 0) s = SCREEN_COUNT - 1;
            currentScreen = (Screen)s;
        }
        else if (btn == BTN_SET_MINUS) {
            int s = (int)currentScreen + 1;
            if (s >= SCREEN_COUNT) s = 0;
            currentScreen = (Screen)s;
        }
        else if (btn == BTN_ON_OFF && currentScreen == SCREEN_SETTINGS) {
            // Enter settings edit mode
        }
        else if (btn == BTN_CANCEL) {
            sleeping = !sleeping;
        }
    }
}

// ============================================================================
// Demo Mode Animation
// ============================================================================
void updateDemo() {
    if (!demoMode) return;
    
    // RPM oscillation
    telemetry.rpm += 50 * demoRpmDir;
    if (telemetry.rpm >= 7200) demoRpmDir = -1;
    if (telemetry.rpm <= 800) demoRpmDir = 1;
    
    // Gear based on RPM
    if (telemetry.rpm < 2000) telemetry.gear = 1;
    else if (telemetry.rpm < 3500) telemetry.gear = 2;
    else if (telemetry.rpm < 5000) telemetry.gear = 3;
    else if (telemetry.rpm < 6000) telemetry.gear = 4;
    else telemetry.gear = 5;
    
    // Speed approximation
    telemetry.speed_kmh = telemetry.rpm * telemetry.gear / 100;
    
    // Slowly varying values
    telemetry.g_lateral = sin(millis() / 1000.0f) * 0.8f;
    telemetry.g_longitudinal = cos(millis() / 1500.0f) * 0.5f;
    
    // Tire temps vary slightly
    for (int i = 0; i < 4; i++) {
        telemetry.tire_temp[i] = 95.0f + sin(millis() / 2000.0f + i) * 5.0f;
    }
    
    // Lap time
    telemetry.lap_time_ms += UPDATE_INTERVAL;
    if (telemetry.lap_time_ms > 120000) telemetry.lap_time_ms = 0;
}

// ============================================================================
// Setup
// ============================================================================
void setup() {
    Serial.begin(115200);
    delay(500);
    
    Serial.println("============================================");
    Serial.println("MX5-Telemetry Round Display Module");
    Serial.println("ESP32-S3 with 1.85\" Touch Screen (360x360)");
    Serial.println("UI Version: 2.0.0 (Simulator Match)");
    Serial.println("============================================");
    
    // Initialize display
    display.init();
    display.setRotation(0);
    display.setBrightness(settings.brightness * 255 / 100);
    display.fillScreen(COLOR_BG);
    
    Serial.println("[DISPLAY] Initialized 360x360 round display");
    
    // Create UI renderer
    ui = new UIRenderer(&display);
    ui->setTelemetry(&telemetry);
    ui->setSettings(&settings);
    
    Serial.println("[UI] Created UI renderer");
    
    // Show startup screen
    display.setTextColor(COLOR_ACCENT);
    display.setTextDatum(middle_center);
    display.setFont(&fonts::Font4);
    display.drawString("MX5", CENTER, CENTER - 30);
    display.setFont(&fonts::Font2);
    display.drawString("TELEMETRY", CENTER, CENTER + 10);
    display.setTextColor(COLOR_GRAY);
    display.setFont(&fonts::Font0);
    display.drawString("Initializing...", CENTER, CENTER + 50);
    
    delay(1500);
    
    Serial.println("[READY] Display module initialized");
    Serial.println();
    Serial.println("Controls:");
    Serial.println("  Touch top/bottom = Navigate screens");
    Serial.println("  Touch center = Select");
    Serial.println("  Touch left/right = Adjust values");
}

// ============================================================================
// Main Loop
// ============================================================================
void loop() {
    uint32_t now = millis();
    
    // Update telemetry/demo at fixed rate
    if (now - lastUpdate >= UPDATE_INTERVAL) {
        lastUpdate = now;
        updateDemo();
        
        // Handle button input
        ButtonEvent btn = readButton();
        handleButton(btn);
    }
    
    // Render at fixed frame rate
    if (now - lastRender >= RENDER_INTERVAL) {
        lastRender = now;
        ui->render(currentScreen, sleeping);
    }
    
    delay(1);
}
