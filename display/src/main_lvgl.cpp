/*
 * ============================================================================
 * MX5-Telemetry Display Module - ESP32-S3 Round Touch Screen
 * ============================================================================
 * 
 * A visual dashboard for the MX5 Telemetry system using a 1.85" round display
 * 
 * HARDWARE:
 * - ESP32-S3 with 1.85" Round Touch Screen (360x360 IPS LCD)
 * - 8Ω 2W Speaker with onboard Audio Codec
 * - Supports Offline Speech Recognition and AI Speech Interaction
 * 
 * FEATURES:
 * - Real-time RPM gauge display
 * - Speed and gear indicator
 * - Touch-based menu navigation
 * - Audio alerts for shift lights
 * - WiFi/BLE connectivity for data sync
 * - OTA firmware updates
 * 
 * AUTHOR: MX5-Telemetry Team
 * VERSION: 1.0.0
 * LICENSE: MIT
 * ============================================================================
 */

#include <Arduino.h>

// Display library
#define LGFX_USE_V1
#include <LovyanGFX.hpp>

// LVGL for UI
#include <lvgl.h>

// ============================================================================
// Display Configuration for 1.85" Round LCD (GC9A01 or similar)
// ============================================================================
class LGFX_RoundDisplay : public lgfx::LGFX_Device {
    lgfx::Panel_GC9A01 _panel_instance;
    lgfx::Bus_SPI _bus_instance;
    lgfx::Light_PWM _light_instance;
    lgfx::Touch_FT5x06 _touch_instance;

public:
    LGFX_RoundDisplay(void) {
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
            
            cfg.panel_width = 360;
            cfg.panel_height = 360;
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
            cfg.x_max = 359;
            cfg.y_min = 0;
            cfg.y_max = 359;
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
LGFX_RoundDisplay display;

// LVGL display buffer
static lv_disp_draw_buf_t draw_buf;
static lv_color_t buf[360 * 10];

// Telemetry data
struct TelemetryData {
    uint16_t rpm = 0;
    uint8_t speed = 0;
    uint8_t gear = 0;
    float coolantTemp = 0;
    float oilTemp = 0;
    float throttle = 0;
    float fuel = 100;
    bool connected = false;
};

TelemetryData telemetry;

// UI elements
static lv_obj_t* rpmGauge = nullptr;
static lv_obj_t* speedLabel = nullptr;
static lv_obj_t* gearLabel = nullptr;
static lv_obj_t* statusLabel = nullptr;

// ============================================================================
// LVGL Display/Touch Callbacks
// ============================================================================
void lvgl_display_flush(lv_disp_drv_t* disp, const lv_area_t* area, lv_color_t* color_p) {
    uint32_t w = (area->x2 - area->x1 + 1);
    uint32_t h = (area->y2 - area->y1 + 1);
    
    display.startWrite();
    display.setAddrWindow(area->x1, area->y1, w, h);
    display.writePixels((lgfx::rgb565_t*)&color_p->full, w * h);
    display.endWrite();
    
    lv_disp_flush_ready(disp);
}

void lvgl_touchpad_read(lv_indev_drv_t* indev_driver, lv_indev_data_t* data) {
    uint16_t touchX, touchY;
    
    if (display.getTouch(&touchX, &touchY)) {
        data->state = LV_INDEV_STATE_PR;
        data->point.x = touchX;
        data->point.y = touchY;
    } else {
        data->state = LV_INDEV_STATE_REL;
    }
}

// ============================================================================
// UI Setup
// ============================================================================
void createGaugeUI() {
    // Set dark theme
    lv_obj_set_style_bg_color(lv_scr_act(), lv_color_hex(0x000000), 0);
    
    // RPM Arc Gauge
    rpmGauge = lv_arc_create(lv_scr_act());
    lv_obj_set_size(rpmGauge, 320, 320);
    lv_arc_set_rotation(rpmGauge, 135);
    lv_arc_set_bg_angles(rpmGauge, 0, 270);
    lv_arc_set_range(rpmGauge, 0, 8000);
    lv_arc_set_value(rpmGauge, 0);
    lv_obj_center(rpmGauge);
    lv_obj_remove_style(rpmGauge, NULL, LV_PART_KNOB);
    lv_obj_clear_flag(rpmGauge, LV_OBJ_FLAG_CLICKABLE);
    
    // RPM gauge colors
    lv_obj_set_style_arc_color(rpmGauge, lv_color_hex(0x333333), LV_PART_MAIN);
    lv_obj_set_style_arc_color(rpmGauge, lv_color_hex(0x00FF00), LV_PART_INDICATOR);
    lv_obj_set_style_arc_width(rpmGauge, 20, LV_PART_MAIN);
    lv_obj_set_style_arc_width(rpmGauge, 20, LV_PART_INDICATOR);
    
    // RPM value label
    lv_obj_t* rpmLabel = lv_label_create(lv_scr_act());
    lv_label_set_text(rpmLabel, "0");
    lv_obj_set_style_text_font(rpmLabel, &lv_font_montserrat_48, 0);
    lv_obj_set_style_text_color(rpmLabel, lv_color_hex(0xFFFFFF), 0);
    lv_obj_align(rpmLabel, LV_ALIGN_CENTER, 0, -30);
    
    // RPM unit label
    lv_obj_t* rpmUnitLabel = lv_label_create(lv_scr_act());
    lv_label_set_text(rpmUnitLabel, "RPM");
    lv_obj_set_style_text_font(rpmUnitLabel, &lv_font_montserrat_16, 0);
    lv_obj_set_style_text_color(rpmUnitLabel, lv_color_hex(0x888888), 0);
    lv_obj_align(rpmUnitLabel, LV_ALIGN_CENTER, 0, 10);
    
    // Gear indicator
    gearLabel = lv_label_create(lv_scr_act());
    lv_label_set_text(gearLabel, "N");
    lv_obj_set_style_text_font(gearLabel, &lv_font_montserrat_28, 0);
    lv_obj_set_style_text_color(gearLabel, lv_color_hex(0x00FFFF), 0);
    lv_obj_align(gearLabel, LV_ALIGN_CENTER, 0, 60);
    
    // Speed label
    speedLabel = lv_label_create(lv_scr_act());
    lv_label_set_text(speedLabel, "0 km/h");
    lv_obj_set_style_text_font(speedLabel, &lv_font_montserrat_20, 0);
    lv_obj_set_style_text_color(speedLabel, lv_color_hex(0xFFFFFF), 0);
    lv_obj_align(speedLabel, LV_ALIGN_CENTER, 0, 100);
    
    // Status indicator
    statusLabel = lv_label_create(lv_scr_act());
    lv_label_set_text(statusLabel, "Disconnected");
    lv_obj_set_style_text_font(statusLabel, &lv_font_montserrat_12, 0);
    lv_obj_set_style_text_color(statusLabel, lv_color_hex(0xFF0000), 0);
    lv_obj_align(statusLabel, LV_ALIGN_BOTTOM_MID, 0, -20);
}

void updateGaugeColor(uint16_t rpm) {
    lv_color_t color;
    
    if (rpm < 4000) {
        color = lv_color_hex(0x00FF00);       // Green - normal
    } else if (rpm < 5500) {
        color = lv_color_hex(0xFFFF00);       // Yellow - getting warm
    } else if (rpm < 6500) {
        color = lv_color_hex(0xFF8800);       // Orange - high RPM
    } else {
        color = lv_color_hex(0xFF0000);       // Red - shift!
    }
    
    lv_obj_set_style_arc_color(rpmGauge, color, LV_PART_INDICATOR);
}

// ============================================================================
// Setup
// ============================================================================
void setup() {
    Serial.begin(115200);
    delay(1000);
    
    Serial.println("============================================");
    Serial.println("MX5-Telemetry Round Display Module");
    Serial.println("ESP32-S3 with 1.85\" Touch Screen");
    Serial.println("Version: 1.0.0");
    Serial.println("============================================");
    
    // Initialize display
    display.init();
    display.setRotation(0);
    display.setBrightness(200);
    display.fillScreen(TFT_BLACK);
    
    Serial.println("[DISPLAY] Initialized 360x360 round display");
    
    // Initialize LVGL
    lv_init();
    
    // Setup display buffer
    lv_disp_draw_buf_init(&draw_buf, buf, NULL, 360 * 10);
    
    // Setup display driver
    static lv_disp_drv_t disp_drv;
    lv_disp_drv_init(&disp_drv);
    disp_drv.hor_res = 360;
    disp_drv.ver_res = 360;
    disp_drv.flush_cb = lvgl_display_flush;
    disp_drv.draw_buf = &draw_buf;
    lv_disp_drv_register(&disp_drv);
    
    // Setup touch driver
    static lv_indev_drv_t indev_drv;
    lv_indev_drv_init(&indev_drv);
    indev_drv.type = LV_INDEV_TYPE_POINTER;
    indev_drv.read_cb = lvgl_touchpad_read;
    lv_indev_drv_register(&indev_drv);
    
    Serial.println("[LVGL] Initialized with touch support");
    
    // Create UI
    createGaugeUI();
    
    Serial.println("[UI] Created gauge interface");
    Serial.println("[READY] Display module initialized");
}

// ============================================================================
// Main Loop
// ============================================================================
void loop() {
    // Handle LVGL tasks
    lv_timer_handler();
    
    // Demo: animate RPM for testing
    static uint32_t lastUpdate = 0;
    static int16_t rpmDirection = 100;
    
    if (millis() - lastUpdate > 50) {
        lastUpdate = millis();
        
        // Simulate RPM changes for demo
        telemetry.rpm += rpmDirection;
        if (telemetry.rpm >= 7500) rpmDirection = -100;
        if (telemetry.rpm <= 800) rpmDirection = 100;
        
        // Update gauge
        lv_arc_set_value(rpmGauge, telemetry.rpm);
        updateGaugeColor(telemetry.rpm);
        
        // Update labels (find them by iterating or store references)
        // For now, just update the gauge
    }
    
    delay(5);
}
