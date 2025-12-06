/*
 * ============================================================================
 * Display Module Configuration
 * ============================================================================
 * Pin mappings and settings for ESP32-S3 Round Display
 * ============================================================================
 */

#ifndef DISPLAY_CONFIG_H
#define DISPLAY_CONFIG_H

// ============================================================================
// Display Dimensions
// ============================================================================
#define DISPLAY_WIDTH       360
#define DISPLAY_HEIGHT      360

// ============================================================================
// SPI Pins for Display
// ============================================================================
// NOTE: Adjust these for your specific board!
#define TFT_SCLK            12      // SPI Clock
#define TFT_MOSI            11      // SPI MOSI (Data Out)
#define TFT_MISO            -1      // Not used for display
#define TFT_DC              8       // Data/Command
#define TFT_CS              10      // Chip Select
#define TFT_RST             14      // Reset
#define TFT_BL              45      // Backlight PWM

// ============================================================================
// Touch Controller Pins (I2C)
// ============================================================================
#define TOUCH_SDA           4       // I2C Data
#define TOUCH_SCL           5       // I2C Clock
#define TOUCH_INT           3       // Touch Interrupt
#define TOUCH_I2C_ADDR      0x38    // FT5x06/FT6206 address

// ============================================================================
// Audio Pins
// ============================================================================
#define AUDIO_I2S_BCLK      42      // I2S Bit Clock
#define AUDIO_I2S_LRC       41      // I2S Left/Right Clock
#define AUDIO_I2S_DOUT      40      // I2S Data Out

// ============================================================================
// Communication Pins (Optional - for telemetry integration)
// ============================================================================
// UART for Master Arduino connection
#define UART_RX             44      // Receive from Master
#define UART_TX             43      // Transmit to Master
#define UART_BAUD           115200

// CAN Bus (if using MCP2515 module)
#define CAN_CS_PIN          15      // MCP2515 Chip Select
#define CAN_INT_PIN         16      // MCP2515 Interrupt

// ============================================================================
// MX5 Telemetry Settings
// ============================================================================
// RPM Settings
#define RPM_MIN             0
#define RPM_MAX             8000
#define RPM_IDLE            850
#define RPM_REDLINE         7500

// Shift Light Thresholds
#define SHIFT_WARN_RPM      5500    // Yellow zone
#define SHIFT_ALERT_RPM     6500    // Orange zone
#define SHIFT_NOW_RPM       7000    // Red zone - SHIFT!

// Temperature Thresholds (Celsius)
#define COOLANT_NORMAL      90
#define COOLANT_WARN        105
#define COOLANT_CRITICAL    115

#define OIL_NORMAL          100
#define OIL_WARN            130
#define OIL_CRITICAL        140

// ============================================================================
// Display Settings
// ============================================================================
#define DEFAULT_BRIGHTNESS  200     // 0-255
#define SLEEP_TIMEOUT_MS    60000   // Auto-dim after 1 minute of no data

// UI Update Rates (ms)
#define UI_REFRESH_RATE     20      // 50 Hz
#define DATA_POLL_RATE      50      // 20 Hz

// ============================================================================
// WiFi Settings (for OTA and data sync)
// ============================================================================
// Default AP mode settings
#define WIFI_AP_SSID        "MX5-Display"
#define WIFI_AP_PASS        "telemetry"

// mDNS hostname
#define MDNS_HOSTNAME       "mx5-display"

// ============================================================================
// Feature Flags
// ============================================================================
#define ENABLE_TOUCH        1
#define ENABLE_AUDIO        1
#define ENABLE_WIFI         1
#define ENABLE_BLE          0       // Disabled by default (saves memory)
#define ENABLE_OTA          1
#define ENABLE_SPEECH       0       // Disabled by default (requires setup)

#endif // DISPLAY_CONFIG_H
