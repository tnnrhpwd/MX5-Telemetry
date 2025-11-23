#ifndef CONFIG_H
#define CONFIG_H

// ============================================================================
// MX5-Telemetry System Configuration
// ============================================================================
// Central configuration file for all system parameters
// Modify these values to customize behavior for your vehicle and setup
// ============================================================================

// ============================================================================
// PIN DEFINITIONS
// ============================================================================
#define CAN_CS_PIN      10    // MCP2515 Chip Select (SPI)
#define SD_CS_PIN       4     // SD Card Chip Select (SPI)
#define LED_DATA_PIN    5     // WS2812B Data Pin (D5 per wiring diagram)
#define GPS_RX_PIN      8     // GPS Module RX (connect to GPS TX) - CHANGED FROM PIN 2
#define GPS_TX_PIN      9     // GPS Module TX (connect to GPS RX) - CHANGED FROM PIN 3
#define WIDEBAND_PIN    A0    // Wideband A/F sensor analog input

// SPI Pins (shared between CAN and SD):
// D11 - MOSI
// D12 - MISO
// D13 - SCK

// ============================================================================
// HARDWARE CONFIGURATION
// ============================================================================
#define LED_COUNT       144   // Number of LEDs in the strip (144 LEDs/M, 1M strip)
#define CAN_SPEED       CAN_500KBPS  // Miata NC CAN bus speed
#define SERIAL_BAUD     115200       // Serial monitor baud rate
#define GPS_BAUD        9600         // GPS module baud rate

// ============================================================================
// RPM THRESHOLDS (adjust for your Miata's redline)
// ============================================================================
#define RPM_IDLE        800          // Idle RPM
#define RPM_MIN_DISPLAY 1000         // Minimum RPM to show on LED strip
#define RPM_MAX_DISPLAY 7000         // Maximum RPM for gradient
#define RPM_SHIFT_LIGHT 6500         // RPM to activate shift light
#define RPM_REDLINE     7200         // Absolute redline

// ============================================================================
// FEATURE ENABLE/DISABLE FLAGS
// ============================================================================
// Enable/disable hardware modules (set to false to disable unused components)
#define ENABLE_CAN_BUS      false    // MCP2515 CAN controller (set true when connected to OBD-II)
#define ENABLE_GPS          true     // Neo-6M GPS module (RE-ENABLED - testing if commands still work)
#define ENABLE_LED_STRIP    true     // WS2812B LED strip (ENABLED - wired per diagram)
#define ENABLE_LOGGING      true     // SD card data logging (requires SD card)

// ============================================================================
// TIMING CONFIGURATION (optimized for >20Hz RPM polling)
// ============================================================================
#define CAN_READ_INTERVAL    20      // Read CAN bus every 20ms (50Hz)
#define GPS_READ_INTERVAL    100     // Read GPS every 100ms (10Hz)
#define LOG_INTERVAL         200     // Log data every 200ms (5Hz)
#define STATUS_INTERVAL      1000    // Status update interval (1Hz)

// ============================================================================
// USB COMMAND INTERFACE
// ============================================================================
#define CMD_START       "START"      // Start logging and LED display
#define CMD_PAUSE       "PAUSE"      // Pause logging and LED display
#define CMD_DUMP        "DUMP"       // Dump log data to laptop
#define CMD_STATUS      "STATUS"     // Print diagnostic information
#define CMD_LIVE        "LIVE"       // Show live data stream
#define CMD_STOP        "STOP"       // Stop live data stream (same as PAUSE)
#define CMD_LIST        "LIST"       // List all files on SD card
#define CMD_HELP        "HELP"       // Show available commands

// ============================================================================
// OBD-II PROTOCOL CONSTANTS - Complete Parameter Set
// ============================================================================
#define OBD2_MODE_01           0x01  // Show current data

// Core Performance
#define PID_CALCULATED_LOAD    0x04  // Calculated engine load (%)
#define PID_ENGINE_RPM         0x0C  // Engine RPM
#define PID_VEHICLE_SPEED      0x0D  // Vehicle speed (km/h)
#define PID_THROTTLE           0x11  // Throttle position (%)

// Engine Health & Environment
#define PID_COOLANT_TEMP       0x05  // Engine coolant temperature (°C)
#define PID_INTAKE_TEMP        0x0F  // Intake air temperature (°C)
#define PID_BAROMETRIC         0x33  // Barometric pressure (kPa)

// Tuning Data
#define PID_TIMING_ADVANCE     0x0E  // Ignition timing advance (degrees before TDC)
#define PID_MAF_RATE           0x10  // MAF air flow rate (g/s)
#define PID_SHORT_FUEL_TRIM    0x06  // Short term fuel trim - Bank 1 (%)
#define PID_LONG_FUEL_TRIM     0x07  // Long term fuel trim - Bank 1 (%)

// ============================================================================
// WIDEBAND A/F SENSOR CONFIGURATION
// ============================================================================
// Configure these based on your wideband controller output
// Common: 0-5V = 10:1 to 20:1 AFR (or 0.68 to 1.36 lambda)
#define AFR_MIN            10.0      // AFR at 0V
#define AFR_MAX            20.0      // AFR at 5V
#define AFR_VOLTAGE_MIN    0.0       // Minimum voltage
#define AFR_VOLTAGE_MAX    5.0       // Maximum voltage

// ============================================================================
// CAN BUS IDENTIFIERS
// ============================================================================
#define OBD2_REQUEST_ID 0x7DF        // Standard OBD-II request ID
#define OBD2_RESPONSE_ID 0x7E8       // Standard OBD-II response ID
#define MAZDA_RPM_CAN_ID 0x201       // Mazda-specific RPM CAN ID

// ============================================================================
// ERROR THRESHOLDS
// ============================================================================
#define CAN_ERROR_THRESHOLD  100     // Reinitialize CAN after this many errors
#define SD_ERROR_THRESHOLD   10      // Reinitialize SD after this many errors

#endif // CONFIG_H
