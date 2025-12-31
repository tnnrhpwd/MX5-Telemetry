/**
 * @file Display_ST77916.cpp
 * @brief ST77916 QSPI Display Driver for Waveshare ESP32-S3-Touch-LCD-1.85
 * @note Based on Waveshare's official driver, adapted for standalone use
 */

#include "Display_ST77916.h"
#include "fonts_hires.h"
#include <Arduino.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "esp_intr_alloc.h"
#include "driver/spi_master.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_panel_ops.h"
#include "esp_lcd_st77916.h"

#define LCD_OPCODE_WRITE_CMD        (0x02ULL)
#define LCD_OPCODE_READ_CMD         (0x0BULL)
#define LCD_OPCODE_WRITE_COLOR      (0x32ULL)

// Global panel handle
static esp_lcd_panel_handle_t panel_handle = NULL;
static uint8_t backlight_level = 100;

// Static buffer for small fills to avoid heap fragmentation
// 4KB is enough for most UI elements (e.g., 45x45 rect = 4050 bytes)
#define STATIC_FILL_BUFFER_SIZE 4096
static uint16_t* static_fill_buffer = NULL;
static bool static_buffer_initialized = false;

// Vendor-specific initialization for newer hardware revision
// MADCTL value 0xC0 = Mirror X (bit 6) + Mirror Y (bit 7) = 180 degree rotation
static const st77916_lcd_init_cmd_t vendor_specific_init_new[] = {
  {0x36, (uint8_t []){0xC0}, 1, 0},  // MADCTL: 180 degree rotation (MX+MY)
  {0xF0, (uint8_t []){0x28}, 1, 0},
  {0xF2, (uint8_t []){0x28}, 1, 0},
  {0x73, (uint8_t []){0xF0}, 1, 0},
  {0x7C, (uint8_t []){0xD1}, 1, 0},
  {0x83, (uint8_t []){0xE0}, 1, 0},
  {0x84, (uint8_t []){0x61}, 1, 0},
  {0xF2, (uint8_t []){0x82}, 1, 0},
  {0xF0, (uint8_t []){0x00}, 1, 0},
  {0xF0, (uint8_t []){0x01}, 1, 0},
  {0xF1, (uint8_t []){0x01}, 1, 0},
  {0xB0, (uint8_t []){0x56}, 1, 0},
  {0xB1, (uint8_t []){0x4D}, 1, 0},
  {0xB2, (uint8_t []){0x24}, 1, 0},
  {0xB4, (uint8_t []){0x87}, 1, 0},
  {0xB5, (uint8_t []){0x44}, 1, 0},
  {0xB6, (uint8_t []){0x8B}, 1, 0},
  {0xB7, (uint8_t []){0x40}, 1, 0},
  {0xB8, (uint8_t []){0x86}, 1, 0},
  {0xBA, (uint8_t []){0x00}, 1, 0},
  {0xBB, (uint8_t []){0x08}, 1, 0},
  {0xBC, (uint8_t []){0x08}, 1, 0},
  {0xBD, (uint8_t []){0x00}, 1, 0},
  {0xC0, (uint8_t []){0x80}, 1, 0},
  {0xC1, (uint8_t []){0x10}, 1, 0},
  {0xC2, (uint8_t []){0x37}, 1, 0},
  {0xC3, (uint8_t []){0x80}, 1, 0},
  {0xC4, (uint8_t []){0x10}, 1, 0},
  {0xC5, (uint8_t []){0x37}, 1, 0},
  {0xC6, (uint8_t []){0xA9}, 1, 0},
  {0xC7, (uint8_t []){0x41}, 1, 0},
  {0xC8, (uint8_t []){0x01}, 1, 0},
  {0xC9, (uint8_t []){0xA9}, 1, 0},
  {0xCA, (uint8_t []){0x41}, 1, 0},
  {0xCB, (uint8_t []){0x01}, 1, 0},
  {0xD0, (uint8_t []){0x91}, 1, 0},
  {0xD1, (uint8_t []){0x68}, 1, 0},
  {0xD2, (uint8_t []){0x68}, 1, 0},
  {0xF5, (uint8_t []){0x00, 0xA5}, 2, 0},
  {0xDD, (uint8_t []){0x4F}, 1, 0},
  {0xDE, (uint8_t []){0x4F}, 1, 0},
  {0xF1, (uint8_t []){0x10}, 1, 0},
  {0xF0, (uint8_t []){0x00}, 1, 0},
  {0xF0, (uint8_t []){0x02}, 1, 0},
  {0xE0, (uint8_t []){0xF0, 0x0A, 0x10, 0x09, 0x09, 0x36, 0x35, 0x33, 0x4A, 0x29, 0x15, 0x15, 0x2E, 0x34}, 14, 0},
  {0xE1, (uint8_t []){0xF0, 0x0A, 0x0F, 0x08, 0x08, 0x05, 0x34, 0x33, 0x4A, 0x39, 0x15, 0x15, 0x2D, 0x33}, 14, 0},
  {0xF0, (uint8_t []){0x10}, 1, 0},
  {0xF3, (uint8_t []){0x10}, 1, 0},
  {0xE0, (uint8_t []){0x07}, 1, 0},
  {0xE1, (uint8_t []){0x00}, 1, 0},
  {0xE2, (uint8_t []){0x00}, 1, 0},
  {0xE3, (uint8_t []){0x00}, 1, 0},
  {0xE4, (uint8_t []){0xE0}, 1, 0},
  {0xE5, (uint8_t []){0x06}, 1, 0},
  {0xE6, (uint8_t []){0x21}, 1, 0},
  {0xE7, (uint8_t []){0x01}, 1, 0},
  {0xE8, (uint8_t []){0x05}, 1, 0},
  {0xE9, (uint8_t []){0x02}, 1, 0},
  {0xEA, (uint8_t []){0xDA}, 1, 0},
  {0xEB, (uint8_t []){0x00}, 1, 0},
  {0xEC, (uint8_t []){0x00}, 1, 0},
  {0xED, (uint8_t []){0x0F}, 1, 0},
  {0xEE, (uint8_t []){0x00}, 1, 0},
  {0xEF, (uint8_t []){0x00}, 1, 0},
  {0xF8, (uint8_t []){0x00}, 1, 0},
  {0xF9, (uint8_t []){0x00}, 1, 0},
  {0xFA, (uint8_t []){0x00}, 1, 0},
  {0xFB, (uint8_t []){0x00}, 1, 0},
  {0xFC, (uint8_t []){0x00}, 1, 0},
  {0xFD, (uint8_t []){0x00}, 1, 0},
  {0xFE, (uint8_t []){0x00}, 1, 0},
  {0xFF, (uint8_t []){0x00}, 1, 0},
  {0x60, (uint8_t []){0x40}, 1, 0},
  {0x61, (uint8_t []){0x04}, 1, 0},
  {0x62, (uint8_t []){0x00}, 1, 0},
  {0x63, (uint8_t []){0x42}, 1, 0},
  {0x64, (uint8_t []){0xD9}, 1, 0},
  {0x65, (uint8_t []){0x00}, 1, 0},
  {0x66, (uint8_t []){0x00}, 1, 0},
  {0x67, (uint8_t []){0x00}, 1, 0},
  {0x68, (uint8_t []){0x00}, 1, 0},
  {0x69, (uint8_t []){0x00}, 1, 0},
  {0x6A, (uint8_t []){0x00}, 1, 0},
  {0x6B, (uint8_t []){0x00}, 1, 0},
  {0x70, (uint8_t []){0x40}, 1, 0},
  {0x71, (uint8_t []){0x03}, 1, 0},
  {0x72, (uint8_t []){0x00}, 1, 0},
  {0x73, (uint8_t []){0x42}, 1, 0},
  {0x74, (uint8_t []){0xD8}, 1, 0},
  {0x75, (uint8_t []){0x00}, 1, 0},
  {0x76, (uint8_t []){0x00}, 1, 0},
  {0x77, (uint8_t []){0x00}, 1, 0},
  {0x78, (uint8_t []){0x00}, 1, 0},
  {0x79, (uint8_t []){0x00}, 1, 0},
  {0x7A, (uint8_t []){0x00}, 1, 0},
  {0x7B, (uint8_t []){0x00}, 1, 0},
  {0x80, (uint8_t []){0x48}, 1, 0},
  {0x81, (uint8_t []){0x00}, 1, 0},
  {0x82, (uint8_t []){0x06}, 1, 0},
  {0x83, (uint8_t []){0x02}, 1, 0},
  {0x84, (uint8_t []){0xD6}, 1, 0},
  {0x85, (uint8_t []){0x04}, 1, 0},
  {0x86, (uint8_t []){0x00}, 1, 0},
  {0x87, (uint8_t []){0x00}, 1, 0},
  {0x88, (uint8_t []){0x48}, 1, 0},
  {0x89, (uint8_t []){0x00}, 1, 0},
  {0x8A, (uint8_t []){0x08}, 1, 0},
  {0x8B, (uint8_t []){0x02}, 1, 0},
  {0x8C, (uint8_t []){0xD8}, 1, 0},
  {0x8D, (uint8_t []){0x04}, 1, 0},
  {0x8E, (uint8_t []){0x00}, 1, 0},
  {0x8F, (uint8_t []){0x00}, 1, 0},
  {0x90, (uint8_t []){0x48}, 1, 0},
  {0x91, (uint8_t []){0x00}, 1, 0},
  {0x92, (uint8_t []){0x0A}, 1, 0},
  {0x93, (uint8_t []){0x02}, 1, 0},
  {0x94, (uint8_t []){0xDA}, 1, 0},
  {0x95, (uint8_t []){0x04}, 1, 0},
  {0x96, (uint8_t []){0x00}, 1, 0},
  {0x97, (uint8_t []){0x00}, 1, 0},
  {0x98, (uint8_t []){0x48}, 1, 0},
  {0x99, (uint8_t []){0x00}, 1, 0},
  {0x9A, (uint8_t []){0x0C}, 1, 0},
  {0x9B, (uint8_t []){0x02}, 1, 0},
  {0x9C, (uint8_t []){0xDC}, 1, 0},
  {0x9D, (uint8_t []){0x04}, 1, 0},
  {0x9E, (uint8_t []){0x00}, 1, 0},
  {0x9F, (uint8_t []){0x00}, 1, 0},
  {0xA0, (uint8_t []){0x48}, 1, 0},
  {0xA1, (uint8_t []){0x00}, 1, 0},
  {0xA2, (uint8_t []){0x05}, 1, 0},
  {0xA3, (uint8_t []){0x02}, 1, 0},
  {0xA4, (uint8_t []){0xD5}, 1, 0},
  {0xA5, (uint8_t []){0x04}, 1, 0},
  {0xA6, (uint8_t []){0x00}, 1, 0},
  {0xA7, (uint8_t []){0x00}, 1, 0},
  {0xA8, (uint8_t []){0x48}, 1, 0},
  {0xA9, (uint8_t []){0x00}, 1, 0},
  {0xAA, (uint8_t []){0x07}, 1, 0},
  {0xAB, (uint8_t []){0x02}, 1, 0},
  {0xAC, (uint8_t []){0xD7}, 1, 0},
  {0xAD, (uint8_t []){0x04}, 1, 0},
  {0xAE, (uint8_t []){0x00}, 1, 0},
  {0xAF, (uint8_t []){0x00}, 1, 0},
  {0xB0, (uint8_t []){0x48}, 1, 0},
  {0xB1, (uint8_t []){0x00}, 1, 0},
  {0xB2, (uint8_t []){0x09}, 1, 0},
  {0xB3, (uint8_t []){0x02}, 1, 0},
  {0xB4, (uint8_t []){0xD9}, 1, 0},
  {0xB5, (uint8_t []){0x04}, 1, 0},
  {0xB6, (uint8_t []){0x00}, 1, 0},
  {0xB7, (uint8_t []){0x00}, 1, 0},
  {0xB8, (uint8_t []){0x48}, 1, 0},
  {0xB9, (uint8_t []){0x00}, 1, 0},
  {0xBA, (uint8_t []){0x0B}, 1, 0},
  {0xBB, (uint8_t []){0x02}, 1, 0},
  {0xBC, (uint8_t []){0xDB}, 1, 0},
  {0xBD, (uint8_t []){0x04}, 1, 0},
  {0xBE, (uint8_t []){0x00}, 1, 0},
  {0xBF, (uint8_t []){0x00}, 1, 0},
  {0xC0, (uint8_t []){0x10}, 1, 0},
  {0xC1, (uint8_t []){0x47}, 1, 0},
  {0xC2, (uint8_t []){0x56}, 1, 0},
  {0xC3, (uint8_t []){0x65}, 1, 0},
  {0xC4, (uint8_t []){0x74}, 1, 0},
  {0xC5, (uint8_t []){0x88}, 1, 0},
  {0xC6, (uint8_t []){0x99}, 1, 0},
  {0xC7, (uint8_t []){0x01}, 1, 0},
  {0xC8, (uint8_t []){0xBB}, 1, 0},
  {0xC9, (uint8_t []){0xAA}, 1, 0},
  {0xD0, (uint8_t []){0x10}, 1, 0},
  {0xD1, (uint8_t []){0x47}, 1, 0},
  {0xD2, (uint8_t []){0x56}, 1, 0},
  {0xD3, (uint8_t []){0x65}, 1, 0},
  {0xD4, (uint8_t []){0x74}, 1, 0},
  {0xD5, (uint8_t []){0x88}, 1, 0},
  {0xD6, (uint8_t []){0x99}, 1, 0},
  {0xD7, (uint8_t []){0x01}, 1, 0},
  {0xD8, (uint8_t []){0xBB}, 1, 0},
  {0xD9, (uint8_t []){0xAA}, 1, 0},
  {0xF3, (uint8_t []){0x01}, 1, 0},
  {0xF0, (uint8_t []){0x00}, 1, 0},
  {0x21, (uint8_t []){0x00}, 1, 0},
  {0x11, (uint8_t []){0x00}, 1, 120},
  {0x29, (uint8_t []){0x00}, 1, 0},  
};

// Forward declaration
extern "C" {
    esp_err_t esp_lcd_new_panel_st77916(const esp_lcd_panel_io_handle_t io, 
                                        const esp_lcd_panel_dev_config_t *panel_dev_config, 
                                        esp_lcd_panel_handle_t *ret_panel);
}

// Hardware reset via IO expander
static void LCD_HardwareReset() {
    Serial.println("LCD: Hardware reset...");
    Set_EXIO(EXIO_PIN2, Low);
    vTaskDelay(pdMS_TO_TICKS(10));
    Set_EXIO(EXIO_PIN2, High);
    vTaskDelay(pdMS_TO_TICKS(50));
    Serial.println("LCD: Hardware reset complete");
}

bool QSPI_Init(void) {
    Serial.println("QSPI_Init: Starting SPI bus initialization...");
    
    // SPI bus configuration for QSPI (matching Waveshare reference exactly)
    static const spi_bus_config_t host_config = {            
        .data0_io_num = LCD_QSPI_D0,                    
        .data1_io_num = LCD_QSPI_D1,                   
        .sclk_io_num = LCD_QSPI_CLK,                   
        .data2_io_num = LCD_QSPI_D2,                    
        .data3_io_num = LCD_QSPI_D3,                    
        .data4_io_num = -1,                       
        .data5_io_num = -1,                      
        .data6_io_num = -1,                       
        .data7_io_num = -1,                      
        .max_transfer_sz = 2048,  // Match reference exactly
        .flags = SPICOMMON_BUSFLAG_MASTER,  // Reference doesn't use QUAD flag here
        .intr_flags = 0,                            
    };
    
    esp_err_t ret = spi_bus_initialize(SPI2_HOST, &host_config, SPI_DMA_CH_AUTO);
    if (ret != ESP_OK) {
        Serial.printf("QSPI_Init: SPI bus init failed: %d\n", ret);
        return false;
    }
    Serial.println("QSPI_Init: SPI bus initialized successfully");
    
    // IO config for slow speed register read (5MHz)
    esp_lcd_panel_io_spi_config_t io_config = {
        .cs_gpio_num = LCD_CS_PIN,               
        .dc_gpio_num = -1,                  
        .spi_mode = 0,                      
        .pclk_hz = 5 * 1000 * 1000,       // Slow for register read
        .trans_queue_depth = 10,            
        .on_color_trans_done = NULL,                            
        .user_ctx = NULL,                   
        .lcd_cmd_bits = 32,                 
        .lcd_param_bits = 8,                
        .flags = {                          
            .dc_low_on_data = 0,            
            .octal_mode = 0,                
            .quad_mode = 1,                 
            .sio_mode = 0,                  
            .lsb_first = 0,                 
            .cs_high_active = 0,            
        },                                  
    };
    
    esp_lcd_panel_io_handle_t io_handle = NULL;
    ret = esp_lcd_new_panel_io_spi((esp_lcd_spi_bus_handle_t)SPI2_HOST, &io_config, &io_handle);
    if (ret != ESP_OK) {
        Serial.printf("QSPI_Init: Failed to create panel IO: %d\n", ret);
        return false;
    }
    Serial.println("QSPI_Init: Panel IO created (5MHz for register read)");
    
    // Read hardware revision register 0x04
    uint8_t register_data[4] = {0}; 
    int lcd_cmd = 0x04;
    lcd_cmd &= 0xff;
    lcd_cmd <<= 8;
    lcd_cmd |= LCD_OPCODE_READ_CMD << 24;
    ret = esp_lcd_panel_io_rx_param(io_handle, lcd_cmd, register_data, sizeof(register_data)); 
    if (ret == ESP_OK) {
        Serial.printf("QSPI_Init: Register 0x04: %02x %02x %02x %02x\n", 
                      register_data[0], register_data[1], register_data[2], register_data[3]);
    } else {
        Serial.printf("QSPI_Init: Failed to read register 0x04, error: %d\n", ret);
    }
    
    // Recreate IO at 80MHz 
    io_config.pclk_hz = 80 * 1000 * 1000;
    ret = esp_lcd_new_panel_io_spi((esp_lcd_spi_bus_handle_t)SPI2_HOST, &io_config, &io_handle);
    if (ret != ESP_OK) {
        Serial.printf("QSPI_Init: Failed to create panel IO at 80MHz: %d\n", ret);
        return false;
    }
    Serial.println("QSPI_Init: Panel IO recreated (80MHz)");
    
    // Prepare vendor config - match reference logic exactly
    st77916_vendor_config_t vendor_config = {  
        .flags = {
            .use_qspi_interface = 1,
        },
    };
    
    // Log hardware revision for debugging
    Serial.printf("QSPI_Init: Hardware ID: %02x %02x %02x %02x\n", 
                  register_data[0], register_data[1], register_data[2], register_data[3]);
    
    // Check register values and configure accordingly (match reference exactly)
    if (register_data[0] == 0x00 && register_data[1] == 0x7F && 
        register_data[2] == 0x7F && register_data[3] == 0x7F) {
        // Case 1: Use driver default init
        Serial.println("QSPI_Init: Case 1 - using driver default init");
    } else if (register_data[0] == 0x00 && register_data[1] == 0x02 && 
               register_data[2] == 0x7F && register_data[3] == 0x7F) {
        // Case 2: Use vendor-specific init
        Serial.println("QSPI_Init: Case 2 - using vendor-specific init");
        vendor_config.init_cmds = vendor_specific_init_new;
        vendor_config.init_cmds_size = sizeof(vendor_specific_init_new) / sizeof(st77916_lcd_init_cmd_t);
    } else {
        // Unknown - try vendor init as fallback
        Serial.println("QSPI_Init: Unknown HW - trying vendor-specific init");
        vendor_config.init_cmds = vendor_specific_init_new;
        vendor_config.init_cmds_size = sizeof(vendor_specific_init_new) / sizeof(st77916_lcd_init_cmd_t);
    }
    
    // Panel configuration (matching reference exactly)
    esp_lcd_panel_dev_config_t panel_config = {
        .reset_gpio_num = -1,  // Using IO expander for reset                                     
        .rgb_ele_order = LCD_RGB_ELEMENT_ORDER_RGB,                   
        .data_endian = LCD_RGB_DATA_ENDIAN_BIG,  // BIG endian - matches reference                       
        .bits_per_pixel = 16,                                 
        .flags = {                                                    
            .reset_active_high = 0,                                   
        },                                                            
        .vendor_config = (void *)&vendor_config,                                  
    };
    
    // Create the ST77916 panel
    ret = esp_lcd_new_panel_st77916(io_handle, &panel_config, &panel_handle);
    if (ret != ESP_OK) {
        Serial.printf("QSPI_Init: Failed to create ST77916 panel: %d\n", ret);
        return false;
    }
    Serial.println("QSPI_Init: ST77916 panel created");
    
    // Reset and initialize panel
    ret = esp_lcd_panel_reset(panel_handle);
    if (ret != ESP_OK) {
        Serial.printf("QSPI_Init: Panel reset failed: %d\n", ret);
    }
    
    ret = esp_lcd_panel_init(panel_handle);
    if (ret != ESP_OK) {
        Serial.printf("QSPI_Init: Panel init failed: %d\n", ret);
        return false;
    }
    Serial.println("QSPI_Init: Panel initialized");
    
    // Rotate display 180 degrees (for upside-down mounting)
    // Mirror both X and Y axes to achieve 180-degree rotation
    ret = esp_lcd_panel_mirror(panel_handle, true, true);
    if (ret != ESP_OK) {
        Serial.printf("QSPI_Init: Panel mirror failed: %d\n", ret);
    }
    Serial.println("QSPI_Init: Display rotated 180 degrees");
    
    // NOTE: Color inversion is already set in init sequence via command 0x21
    // The reference code does NOT call esp_lcd_panel_invert_color after init
    // Commenting this out to match reference behavior
    // ret = esp_lcd_panel_invert_color(panel_handle, true);
    
    // Turn on display
    ret = esp_lcd_panel_disp_on_off(panel_handle, true);
    if (ret != ESP_OK) {
        Serial.printf("QSPI_Init: Display on failed: %d\n", ret);
    }
    Serial.println("QSPI_Init: Display turned on");
    
    return true;
}

bool LCD_Init(void) {
    Serial.println("LCD_Init: Starting...");
    
    // Initialize I2C bus for IO expander and touch
    Serial.println("LCD_Init: Initializing I2C...");
    I2C_Init();
    delay(10);
    
    // Initialize IO expander (TCA9554PWR) - all outputs
    Serial.println("LCD_Init: Initializing IO expander...");
    TCA9554PWR_Init(0x00);  // All pins as outputs
    delay(10);
    
    // Set up backlight PWM
    Serial.println("LCD_Init: Setting up backlight PWM...");
    ledcAttach(LCD_BL_PIN, LCD_PWM_FREQ, LCD_PWM_RESOLUTION);
    ledcWrite(LCD_BL_PIN, 512);  // 50% brightness initially
    
    // Hardware reset via IO expander
    LCD_HardwareReset();
    
    // Initialize QSPI and panel
    if (!QSPI_Init()) {
        Serial.println("LCD_Init: QSPI initialization failed!");
        return false;
    }
    
    // Set backlight to 100%
    Serial.println("LCD_Init: Enabling backlight...");
    ledcWrite(LCD_BL_PIN, 1024);  // Full brightness
    
    // Initialize touch controller
    Serial.println("LCD_Init: Initializing touch...");
    Touch_Init();
    
    Serial.println("LCD_Init: Complete");
    return true;
}

void LCD_Clear(uint16_t color) {
    LCD_FillRect(0, 0, LCD_WIDTH, LCD_HEIGHT, color);
}

void LCD_FillRect(uint16_t x, uint16_t y, uint16_t w, uint16_t h, uint16_t color) {
    if (panel_handle == NULL) return;
    if (x >= LCD_WIDTH || y >= LCD_HEIGHT) return;
    if (x + w > LCD_WIDTH) w = LCD_WIDTH - x;
    if (y + h > LCD_HEIGHT) h = LCD_HEIGHT - y;
    
    uint32_t size = w * h;
    uint16_t* buf = NULL;
    bool use_static = false;
    
    // Initialize static buffer on first use (DMA-capable memory)
    if (!static_buffer_initialized) {
        static_fill_buffer = (uint16_t*)heap_caps_malloc(STATIC_FILL_BUFFER_SIZE, MALLOC_CAP_DMA);
        static_buffer_initialized = true;
    }
    
    // Use static buffer for small fills to avoid heap fragmentation
    if (size * 2 <= STATIC_FILL_BUFFER_SIZE && static_fill_buffer != NULL) {
        buf = static_fill_buffer;
        use_static = true;
    } else {
        // Large fill - must allocate dynamically
        buf = (uint16_t*)heap_caps_malloc(size * 2, MALLOC_CAP_DMA);
        if (!buf) {
            // Fallback: fill row by row using static buffer
            if (static_fill_buffer != NULL && w * 2 <= STATIC_FILL_BUFFER_SIZE) {
                uint16_t swapped = ((color >> 8) & 0xFF) | ((color << 8) & 0xFF00);
                for (uint32_t i = 0; i < w; i++) {
                    static_fill_buffer[i] = swapped;
                }
                for (uint16_t row = 0; row < h; row++) {
                    esp_lcd_panel_draw_bitmap(panel_handle, x, y + row, x + w, y + row + 1, static_fill_buffer);
                }
                return;
            }
            Serial.println("LCD_FillRect: Failed to allocate buffer");
            return;
        }
    }
    
    // Byte swap for BIG endian (matching reference LCD_addWindow)
    uint16_t swapped = ((color >> 8) & 0xFF) | ((color << 8) & 0xFF00);
    for (uint32_t i = 0; i < size; i++) {
        buf[i] = swapped;
    }
    
    esp_lcd_panel_draw_bitmap(panel_handle, x, y, x + w, y + h, buf);
    
    // Only free if dynamically allocated
    if (!use_static) {
        heap_caps_free(buf);
    }
}

void LCD_DrawPixel(uint16_t x, uint16_t y, uint16_t color) {
    if (panel_handle == NULL) return;
    if (x >= LCD_WIDTH || y >= LCD_HEIGHT) return;
    
    // Byte swap for BIG endian
    uint16_t swapped = ((color >> 8) & 0xFF) | ((color << 8) & 0xFF00);
    esp_lcd_panel_draw_bitmap(panel_handle, x, y, x + 1, y + 1, &swapped);
}

void LCD_DrawLine(uint16_t x0, uint16_t y0, uint16_t x1, uint16_t y1, uint16_t color) {
    int dx = abs(x1 - x0), sx = x0 < x1 ? 1 : -1;
    int dy = -abs(y1 - y0), sy = y0 < y1 ? 1 : -1;
    int err = dx + dy, e2;
    
    while (true) {
        LCD_DrawPixel(x0, y0, color);
        if (x0 == x1 && y0 == y1) break;
        e2 = 2 * err;
        if (e2 >= dy) { err += dy; x0 += sx; }
        if (e2 <= dx) { err += dx; y0 += sy; }
    }
}

void LCD_DrawRect(uint16_t x, uint16_t y, uint16_t w, uint16_t h, uint16_t color) {
    // Draw horizontal lines more efficiently
    LCD_FillRect(x, y, w, 1, color);
    LCD_FillRect(x, y + h - 1, w, 1, color);
    // Draw vertical lines
    LCD_FillRect(x, y, 1, h, color);
    LCD_FillRect(x + w - 1, y, 1, h, color);
}

// Helper to draw corner arcs for rounded rectangles
static void LCD_DrawCorner(int16_t x0, int16_t y0, int16_t r, uint8_t corner, uint16_t color) {
    int f = 1 - r;
    int ddF_x = 1;
    int ddF_y = -2 * r;
    int x = 0;
    int y = r;
    
    while (x < y) {
        if (f >= 0) {
            y--;
            ddF_y += 2;
            f += ddF_y;
        }
        x++;
        ddF_x += 2;
        f += ddF_x;
        
        if (corner & 0x1) { // Top-right
            LCD_DrawPixel(x0 + x, y0 - y, color);
            LCD_DrawPixel(x0 + y, y0 - x, color);
        }
        if (corner & 0x2) { // Bottom-right
            LCD_DrawPixel(x0 + x, y0 + y, color);
            LCD_DrawPixel(x0 + y, y0 + x, color);
        }
        if (corner & 0x4) { // Bottom-left
            LCD_DrawPixel(x0 - x, y0 + y, color);
            LCD_DrawPixel(x0 - y, y0 + x, color);
        }
        if (corner & 0x8) { // Top-left
            LCD_DrawPixel(x0 - x, y0 - y, color);
            LCD_DrawPixel(x0 - y, y0 - x, color);
        }
    }
}

// Helper to fill corner arcs for rounded rectangles
static void LCD_FillCorner(int16_t x0, int16_t y0, int16_t r, uint8_t corner, int16_t delta, uint16_t color) {
    int f = 1 - r;
    int ddF_x = 1;
    int ddF_y = -2 * r;
    int x = 0;
    int y = r;
    
    while (x < y) {
        if (f >= 0) {
            y--;
            ddF_y += 2;
            f += ddF_y;
        }
        x++;
        ddF_x += 2;
        f += ddF_x;
        
        if (corner & 0x1) { // Right side
            LCD_FillRect(x0 + x, y0 - y, 1, 2 * y + delta, color);
            LCD_FillRect(x0 + y, y0 - x, 1, 2 * x + delta, color);
        }
        if (corner & 0x2) { // Left side
            LCD_FillRect(x0 - x, y0 - y, 1, 2 * y + delta, color);
            LCD_FillRect(x0 - y, y0 - x, 1, 2 * x + delta, color);
        }
    }
}

void LCD_DrawRoundRect(uint16_t x, uint16_t y, uint16_t w, uint16_t h, uint16_t r, uint16_t color) {
    if (r > w/2) r = w/2;
    if (r > h/2) r = h/2;
    
    // Draw four sides (excluding corners)
    LCD_FillRect(x + r, y, w - 2*r, 1, color);           // Top
    LCD_FillRect(x + r, y + h - 1, w - 2*r, 1, color);   // Bottom
    LCD_FillRect(x, y + r, 1, h - 2*r, color);           // Left
    LCD_FillRect(x + w - 1, y + r, 1, h - 2*r, color);   // Right
    
    // Draw four corners
    LCD_DrawCorner(x + r, y + r, r, 0x8, color);             // Top-left
    LCD_DrawCorner(x + w - r - 1, y + r, r, 0x1, color);     // Top-right
    LCD_DrawCorner(x + w - r - 1, y + h - r - 1, r, 0x2, color); // Bottom-right
    LCD_DrawCorner(x + r, y + h - r - 1, r, 0x4, color);     // Bottom-left
}

void LCD_FillRoundRect(uint16_t x, uint16_t y, uint16_t w, uint16_t h, uint16_t r, uint16_t color) {
    if (r > w/2) r = w/2;
    if (r > h/2) r = h/2;
    
    // For small radius or no radius, just fill a regular rect
    if (r <= 1) {
        LCD_FillRect(x, y, w, h, color);
        return;
    }
    
    // Optimized: Use horizontal scanlines for the entire shape
    // This is faster than filling center + corners separately
    
    // Top rounded section
    for (int row = 0; row < r; row++) {
        int dx = r - (int)sqrt((float)(r * r - (r - row) * (r - row)));
        LCD_FillRect(x + dx, y + row, w - 2 * dx, 1, color);
    }
    
    // Middle rectangular section (no rounding)
    if (h > 2 * r) {
        LCD_FillRect(x, y + r, w, h - 2 * r, color);
    }
    
    // Bottom rounded section
    for (int row = 0; row < r; row++) {
        int dx = r - (int)sqrt((float)(r * r - (r - row) * (r - row)));
        LCD_FillRect(x + dx, y + h - r + row, w - 2 * dx, 1, color);
    }
}

void LCD_DrawCircle(uint16_t x0, uint16_t y0, uint16_t r, uint16_t color) {
    int f = 1 - r;
    int ddF_x = 1;
    int ddF_y = -2 * r;
    int x = 0;
    int y = r;
    
    LCD_DrawPixel(x0, y0 + r, color);
    LCD_DrawPixel(x0, y0 - r, color);
    LCD_DrawPixel(x0 + r, y0, color);
    LCD_DrawPixel(x0 - r, y0, color);
    
    while (x < y) {
        if (f >= 0) {
            y--;
            ddF_y += 2;
            f += ddF_y;
        }
        x++;
        ddF_x += 2;
        f += ddF_x;
        
        LCD_DrawPixel(x0 + x, y0 + y, color);
        LCD_DrawPixel(x0 - x, y0 + y, color);
        LCD_DrawPixel(x0 + x, y0 - y, color);
        LCD_DrawPixel(x0 - x, y0 - y, color);
        LCD_DrawPixel(x0 + y, y0 + x, color);
        LCD_DrawPixel(x0 - y, y0 + x, color);
        LCD_DrawPixel(x0 + y, y0 - x, color);
        LCD_DrawPixel(x0 - y, y0 - x, color);
    }
}

void LCD_FillCircle(uint16_t x0, uint16_t y0, uint16_t r, uint16_t color) {
    // Optimized scanline fill - batch adjacent horizontal lines
    // For small circles (common in UI), this is much faster
    if (r == 0) {
        LCD_DrawPixel(x0, y0, color);
        return;
    }
    
    // For very small circles, just fill a rectangle approximation
    if (r <= 2) {
        LCD_FillRect(x0 - r, y0 - r, 2 * r + 1, 2 * r + 1, color);
        return;
    }
    
    // Use horizontal line approach but batch into larger rectangles where possible
    // Draw the center horizontal line first
    LCD_FillRect(x0 - r, y0, 2 * r + 1, 1, color);
    
    // Draw symmetric pairs of lines above and below center
    for (int y = 1; y <= r; y++) {
        int x = (int)sqrt((float)(r * r - y * y));
        // Draw two lines at once if possible (above and below)
        LCD_FillRect(x0 - x, y0 - y, 2 * x + 1, 1, color);
        LCD_FillRect(x0 - x, y0 + y, 2 * x + 1, 1, color);
    }
}

// Basic font - 5x7 characters
static const uint8_t font_5x7[96][5] = {
    {0x00,0x00,0x00,0x00,0x00}, // Space
    {0x00,0x00,0x5F,0x00,0x00}, // !
    {0x00,0x07,0x00,0x07,0x00}, // "
    {0x14,0x7F,0x14,0x7F,0x14}, // #
    {0x24,0x2A,0x7F,0x2A,0x12}, // $
    {0x23,0x13,0x08,0x64,0x62}, // %
    {0x36,0x49,0x55,0x22,0x50}, // &
    {0x00,0x05,0x03,0x00,0x00}, // '
    {0x00,0x1C,0x22,0x41,0x00}, // (
    {0x00,0x41,0x22,0x1C,0x00}, // )
    {0x14,0x08,0x3E,0x08,0x14}, // *
    {0x08,0x08,0x3E,0x08,0x08}, // +
    {0x00,0x50,0x30,0x00,0x00}, // ,
    {0x08,0x08,0x08,0x08,0x08}, // -
    {0x00,0x60,0x60,0x00,0x00}, // .
    {0x20,0x10,0x08,0x04,0x02}, // /
    {0x3E,0x51,0x49,0x45,0x3E}, // 0
    {0x00,0x42,0x7F,0x40,0x00}, // 1
    {0x42,0x61,0x51,0x49,0x46}, // 2
    {0x21,0x41,0x45,0x4B,0x31}, // 3
    {0x18,0x14,0x12,0x7F,0x10}, // 4
    {0x27,0x45,0x45,0x45,0x39}, // 5
    {0x3C,0x4A,0x49,0x49,0x30}, // 6
    {0x01,0x71,0x09,0x05,0x03}, // 7
    {0x36,0x49,0x49,0x49,0x36}, // 8
    {0x06,0x49,0x49,0x29,0x1E}, // 9
    {0x00,0x36,0x36,0x00,0x00}, // :
    {0x00,0x56,0x36,0x00,0x00}, // ;
    {0x08,0x14,0x22,0x41,0x00}, // <
    {0x14,0x14,0x14,0x14,0x14}, // =
    {0x00,0x41,0x22,0x14,0x08}, // >
    {0x02,0x01,0x51,0x09,0x06}, // ?
    {0x32,0x49,0x79,0x41,0x3E}, // @
    {0x7E,0x11,0x11,0x11,0x7E}, // A
    {0x7F,0x49,0x49,0x49,0x36}, // B
    {0x3E,0x41,0x41,0x41,0x22}, // C
    {0x7F,0x41,0x41,0x22,0x1C}, // D
    {0x7F,0x49,0x49,0x49,0x41}, // E
    {0x7F,0x09,0x09,0x09,0x01}, // F
    {0x3E,0x41,0x49,0x49,0x7A}, // G
    {0x7F,0x08,0x08,0x08,0x7F}, // H
    {0x00,0x41,0x7F,0x41,0x00}, // I
    {0x20,0x40,0x41,0x3F,0x01}, // J
    {0x7F,0x08,0x14,0x22,0x41}, // K
    {0x7F,0x40,0x40,0x40,0x40}, // L
    {0x7F,0x02,0x0C,0x02,0x7F}, // M
    {0x7F,0x04,0x08,0x10,0x7F}, // N
    {0x3E,0x41,0x41,0x41,0x3E}, // O
    {0x7F,0x09,0x09,0x09,0x06}, // P
    {0x3E,0x41,0x51,0x21,0x5E}, // Q
    {0x7F,0x09,0x19,0x29,0x46}, // R
    {0x46,0x49,0x49,0x49,0x31}, // S
    {0x01,0x01,0x7F,0x01,0x01}, // T
    {0x3F,0x40,0x40,0x40,0x3F}, // U
    {0x1F,0x20,0x40,0x20,0x1F}, // V
    {0x3F,0x40,0x38,0x40,0x3F}, // W
    {0x63,0x14,0x08,0x14,0x63}, // X
    {0x07,0x08,0x70,0x08,0x07}, // Y
    {0x61,0x51,0x49,0x45,0x43}, // Z
    {0x00,0x7F,0x41,0x41,0x00}, // [
    {0x02,0x04,0x08,0x10,0x20}, // backslash
    {0x00,0x41,0x41,0x7F,0x00}, // ]
    {0x04,0x02,0x01,0x02,0x04}, // ^
    {0x40,0x40,0x40,0x40,0x40}, // _
    {0x00,0x01,0x02,0x04,0x00}, // `
    {0x20,0x54,0x54,0x54,0x78}, // a
    {0x7F,0x48,0x44,0x44,0x38}, // b
    {0x38,0x44,0x44,0x44,0x20}, // c
    {0x38,0x44,0x44,0x48,0x7F}, // d
    {0x38,0x54,0x54,0x54,0x18}, // e
    {0x08,0x7E,0x09,0x01,0x02}, // f
    {0x0C,0x52,0x52,0x52,0x3E}, // g
    {0x7F,0x08,0x04,0x04,0x78}, // h
    {0x00,0x44,0x7D,0x40,0x00}, // i
    {0x20,0x40,0x44,0x3D,0x00}, // j
    {0x7F,0x10,0x28,0x44,0x00}, // k
    {0x00,0x41,0x7F,0x40,0x00}, // l
    {0x7C,0x04,0x18,0x04,0x78}, // m
    {0x7C,0x08,0x04,0x04,0x78}, // n
    {0x38,0x44,0x44,0x44,0x38}, // o
    {0x7C,0x14,0x14,0x14,0x08}, // p
    {0x08,0x14,0x14,0x18,0x7C}, // q
    {0x7C,0x08,0x04,0x04,0x08}, // r
    {0x48,0x54,0x54,0x54,0x20}, // s
    {0x04,0x3F,0x44,0x40,0x20}, // t
    {0x3C,0x40,0x40,0x20,0x7C}, // u
    {0x1C,0x20,0x40,0x20,0x1C}, // v
    {0x3C,0x40,0x30,0x40,0x3C}, // w
    {0x44,0x28,0x10,0x28,0x44}, // x
    {0x0C,0x50,0x50,0x50,0x3C}, // y
    {0x44,0x64,0x54,0x4C,0x44}, // z
    {0x00,0x08,0x36,0x41,0x00}, // {
    {0x00,0x00,0x7F,0x00,0x00}, // |
    {0x00,0x41,0x36,0x08,0x00}, // }
    {0x10,0x08,0x08,0x10,0x08}, // ~
    {0x00,0x00,0x00,0x00,0x00}  // DEL
};

void LCD_DrawChar(uint16_t x, uint16_t y, char c, uint16_t color, uint16_t bg, uint8_t size) {
    if (x >= LCD_WIDTH || y >= LCD_HEIGHT) return;
    if (c < 32 || c > 127) c = '?';
    if (size == 2) {
        // Use high-res 10x14 font for size 2
        const uint16_t* fontData = font_10x14[c - 32];
        for (uint8_t row = 0; row < 14; row++) {
            uint16_t rowData = fontData[row];
            for (uint8_t col = 0; col < 10; col++) {
                if (rowData & (1 << (9 - col))) {
                    LCD_DrawPixel(x + col, y + row, color);
                } else if (bg != color) {
                    LCD_DrawPixel(x + col, y + row, bg);
                }
            }
        }
    } else if (size >= 3) {
        // Use high-res 15x21 font for size 3 and 4
        const uint32_t* fontData = font_15x21[c - 32];
        for (uint8_t row = 0; row < 21; row++) {
            uint32_t rowData = fontData[row];
            for (uint8_t col = 0; col < 15; col++) {
                if (rowData & (1 << (14 - col))) {
                    LCD_DrawPixel(x + col, y + row, color);
                } else if (bg != color) {
                    LCD_DrawPixel(x + col, y + row, bg);
                }
            }
        }
    } else {
        // Size 1: Use original 5x7 font
        for (uint8_t i = 0; i < 5; i++) {
            uint8_t line = font_5x7[c - 32][i];
            for (uint8_t j = 0; j < 7; j++) {
                if (line & 0x01) {
                    LCD_DrawPixel(x + i, y + j, color);
                } else if (bg != color) {
                    LCD_DrawPixel(x + i, y + j, bg);
                }
                line >>= 1;
            }
        }
    }
}

void LCD_DrawString(uint16_t x, uint16_t y, const char* str, uint16_t color, uint16_t bg, uint8_t size) {
    uint16_t charWidth = (size == 2) ? 11 : (size >= 3) ? 16 : 6;
    
    while (*str) {
        LCD_DrawChar(x, y, *str++, color, bg, size);
        x += charWidth;
        if (x + charWidth > LCD_WIDTH) {
            x = 0;
            uint16_t charHeight = (size == 2) ? 14 : (size >= 3) ? 21 : 8;
            y += charHeight;
        }
        if (y + ((size == 2) ? 14 : (size >= 3) ? 21 : 8) > LCD_HEIGHT) break;
    }
}h + 1 space
        if (x + 6 * size > LCD_WIDTH) {
            x = 0;
            y += 8 * size;
        }
        if (y + 8 * size > LCD_HEIGHT) break;
    }
}

void LCD_DrawNumber(uint16_t x, uint16_t y, int32_t num, uint16_t color, uint16_t bg, uint8_t size) {
    char buf[12];
    snprintf(buf, sizeof(buf), "%ld", num);
    LCD_DrawString(x, y, buf, color, bg, size);
}

void LCD_SetBacklight(uint8_t level) {
    backlight_level = level;
    if (level > 100) level = 100;
    
    // Use ledc for PWM on backlight pin (1024 max for 10-bit resolution)
    uint32_t duty = level * 1024 / 100;
    if (duty > 1024) duty = 1024;
    ledcWrite(LCD_BL_PIN, duty);
}

uint8_t LCD_GetBacklight(void) {
    return backlight_level;
}

// Progress bar
void LCD_DrawProgressBar(uint16_t x, uint16_t y, uint16_t w, uint16_t h, 
                         uint8_t progress, uint16_t fg, uint16_t bg, uint16_t border) {
    // Draw border
    LCD_DrawRect(x, y, w, h, border);
    
    // Fill background
    LCD_FillRect(x + 1, y + 1, w - 2, h - 2, bg);
    
    // Fill progress
    if (progress > 100) progress = 100;
    uint16_t fill_w = (w - 2) * progress / 100;
    if (fill_w > 0) {
        LCD_FillRect(x + 1, y + 1, fill_w, h - 2, fg);
    }
}

// Arc drawing for gauges
void LCD_DrawArc(uint16_t x, uint16_t y, uint16_t r, 
                 uint16_t start_angle, uint16_t end_angle, uint16_t color) {
    for (uint16_t angle = start_angle; angle <= end_angle; angle++) {
        float rad = angle * 3.14159f / 180.0f;
        int px = x + (int)(r * cos(rad));
        int py = y - (int)(r * sin(rad));  // Y is inverted
        LCD_DrawPixel(px, py, color);
    }
}

void LCD_DrawThickArc(uint16_t x, uint16_t y, uint16_t r, uint16_t thickness,
                      uint16_t start_angle, uint16_t end_angle, uint16_t color) {
    for (uint16_t t = 0; t < thickness; t++) {
        LCD_DrawArc(x, y, r - t, start_angle, end_angle, color);
    }
}

void LCD_DrawImage(uint16_t x, uint16_t y, uint16_t w, uint16_t h, const uint16_t* data) {
    if (panel_handle == NULL) return;
    if (x >= LCD_WIDTH || y >= LCD_HEIGHT) return;
    
    // Clip if necessary
    uint16_t draw_w = (x + w > LCD_WIDTH) ? (LCD_WIDTH - x) : w;
    uint16_t draw_h = (y + h > LCD_HEIGHT) ? (LCD_HEIGHT - y) : h;
    
    // Draw multiple rows at once for better performance
    // Use 8KB buffer = ~11 rows at 360 width, or 22 rows at 180 width
    const uint32_t MAX_BUF_SIZE = 8192;
    uint16_t rows_per_batch = MAX_BUF_SIZE / (draw_w * 2);
    if (rows_per_batch < 1) rows_per_batch = 1;
    if (rows_per_batch > draw_h) rows_per_batch = draw_h;
    
    uint16_t* row_buf = (uint16_t*)heap_caps_malloc(rows_per_batch * draw_w * 2, MALLOC_CAP_DMA);
    if (!row_buf) {
        Serial.println("LCD_DrawImage: Failed to allocate row buffer");
        return;
    }
    
    for (uint16_t row = 0; row < draw_h; row += rows_per_batch) {
        uint16_t batch_rows = rows_per_batch;
        if (row + batch_rows > draw_h) batch_rows = draw_h - row;
        
        // Copy multiple rows from PROGMEM (data is already byte-swapped by converter)
        for (uint16_t r = 0; r < batch_rows; r++) {
            memcpy_P(&row_buf[r * draw_w], &data[(row + r) * w], draw_w * 2);
        }
        esp_lcd_panel_draw_bitmap(panel_handle, x, y + row, x + draw_w, y + row + batch_rows, row_buf);
    }
    
    heap_caps_free(row_buf);
}

void LCD_DrawImageWithAlpha(uint16_t x, uint16_t y, uint16_t w, uint16_t h, 
                            const uint16_t* rgb_data, const uint8_t* alpha_data,
                            uint16_t bg_color) {
    if (panel_handle == NULL) return;
    if (x >= LCD_WIDTH || y >= LCD_HEIGHT) return;
    
    // Clip if necessary
    uint16_t draw_w = (x + w > LCD_WIDTH) ? (LCD_WIDTH - x) : w;
    uint16_t draw_h = (y + h > LCD_HEIGHT) ? (LCD_HEIGHT - y) : h;
    
    uint16_t* row_buf = (uint16_t*)heap_caps_malloc(draw_w * 2, MALLOC_CAP_DMA);
    if (!row_buf) {
        Serial.println("LCD_DrawImageWithAlpha: Failed to allocate row buffer");
        return;
    }
    
    for (uint16_t row = 0; row < draw_h; row++) {
        for (uint16_t col = 0; col < draw_w; col++) {
            uint16_t idx = row * w + col;
            uint8_t alpha = pgm_read_byte(&alpha_data[idx]);
            
            // Simple threshold: if alpha > 128, draw pixel, else background
            // This gives clean edges without muddy blending
            if (alpha > 128) {
                uint16_t pixel = pgm_read_word(&rgb_data[idx]);
                row_buf[col] = pixel;
            } else {
                row_buf[col] = bg_color;
            }
        }
        esp_lcd_panel_draw_bitmap(panel_handle, x, y + row, x + draw_w, y + row + 1, row_buf);
    }
    
    heap_caps_free(row_buf);
}

void LCD_DrawImageCentered(uint16_t w, uint16_t h, const uint16_t* data) {
    uint16_t x = (LCD_WIDTH - w) / 2;
    uint16_t y = (LCD_HEIGHT - h) / 2;
    LCD_DrawImage(x, y, w, h, data);
}

void LCD_DrawImageScaled(uint16_t src_w, uint16_t src_h, const uint16_t* data, 
                         uint16_t dst_x, uint16_t dst_y, uint16_t dst_w, uint16_t dst_h) {
    if (panel_handle == NULL) return;
    if (dst_x >= LCD_WIDTH || dst_y >= LCD_HEIGHT) return;
    
    // Clip if necessary
    uint16_t draw_w = (dst_x + dst_w > LCD_WIDTH) ? (LCD_WIDTH - dst_x) : dst_w;
    uint16_t draw_h = (dst_y + dst_h > LCD_HEIGHT) ? (LCD_HEIGHT - dst_y) : dst_h;
    
    // Allocate buffer for one row of output pixels
    uint16_t* row_buf = (uint16_t*)heap_caps_malloc(draw_w * sizeof(uint16_t), MALLOC_CAP_DMA);
    if (!row_buf) {
        Serial.println("LCD_DrawImageScaled: Failed to allocate row buffer");
        return;
    }
    
    // Fixed-point scaling factors (16.16 format for precision)
    uint32_t x_ratio = ((src_w - 1) << 16) / draw_w;
    uint32_t y_ratio = ((src_h - 1) << 16) / draw_h;
    
    for (uint16_t y = 0; y < draw_h; y++) {
        uint32_t src_y = (y * y_ratio) >> 16;
        const uint16_t* src_row = data + (src_y * src_w);
        
        for (uint16_t x = 0; x < draw_w; x++) {
            uint32_t src_x = (x * x_ratio) >> 16;
            row_buf[x] = pgm_read_word(&src_row[src_x]);
        }
        
        // Draw this row using the panel API
        esp_lcd_panel_draw_bitmap(panel_handle, dst_x, dst_y + y, dst_x + draw_w, dst_y + y + 1, row_buf);
    }
    
    heap_caps_free(row_buf);
}
