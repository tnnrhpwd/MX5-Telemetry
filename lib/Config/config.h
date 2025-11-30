#ifndef CONFIG_H
#define CONFIG_H

// ============================================================================
// MX5-Telemetry System Configuration
// ============================================================================
// Central configuration file for all system parameters
// Modify these values to customize behavior for your vehicle and setup
// ============================================================================

// ============================================================================
// FIRMWARE VERSION
// ============================================================================
#define FIRMWARE_VERSION "3.2.0"
#define BUILD_DATE __DATE__
#define BUILD_TIME __TIME__

// ============================================================================
// PIN DEFINITIONS
// ============================================================================
#define CAN_CS_PIN      10    // MCP2515 Chip Select (SPI)
#define SD_CS_PIN       4     // SD Card Chip Select (SPI)
#define LED_DATA_PIN    5     // WS2812B Data Pin (D5 per wiring diagram)
#define SLAVE_TX_PIN    6     // TX to LED Slave Arduino (connect to Slave D2)
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
#define LED_COUNT       20    // Number of LEDs for dashboard RPM display
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
#define ENABLE_CAN_BUS      true     // MCP2515 CAN controller for OBD-II
#define ENABLE_GPS          true    // GPS with dynamic enable/disable during logging
                                     // true = GPS enabled during RUNNING, disabled during USB commands
                                     // false = GPS completely disabled (no serial interference)
#define ENABLE_LED_STRIP    false    // LED strip DISABLED (using external slave Arduino)
#define ENABLE_LED_SLAVE    true     // Send LED commands to slave Arduino via Serial1 (TX pin 1)
#define ENABLE_LOGGING      true     // SD card data logging

// ============================================================================
// TIMING CONFIGURATION (optimized for >20Hz RPM polling)
// ============================================================================
#define CAN_READ_INTERVAL    20      // Read CAN bus every 20ms (50Hz)
#define GPS_READ_INTERVAL    100     // Read GPS every 100ms (10Hz)
#define LOG_INTERVAL         200     // Log data every 200ms (5Hz)
#define LED_UPDATE_INTERVAL  50      // Update LEDs every 50ms (20Hz) - fast for responsive visuals
#define STATUS_INTERVAL      1000    // Status update interval (1Hz)

// ============================================================================
// LOG ROTATION (automatic new file creation) - Costs ~300 bytes flash
// ============================================================================
#define LOG_ROTATION_ENABLED  true    // Automatically create new file every N minutes
#define LOG_ROTATION_INTERVAL 600000  // Create new log file every 10 minutes
                                      // 600000 = 10 min, 1800000 = 30 min, 3600000 = 1 hour
#define GPS_FILENAMES_ENABLED false   // Use GPS datetime for filenames (MMDD_HHMM.CSV)
                                      // Costs 340 bytes - set true only if LED strip disabled

// ============================================================================
// STANDALONE AUTO-START CONFIGURATION
// ============================================================================
#define AUTO_START_ENABLED     true   // Automatically start logging if no USB commands received
#define AUTO_START_TIMEOUT     10000  // Wait 10 seconds for USB commands before auto-start (milliseconds)
#define BOOT_DELAY_MS          10000  // Delay before SD init to prevent corrupted files during upload/reset

// ============================================================================
// USB COMMAND INTERFACE
// ============================================================================
// Single-letter commands (corruption-resistant): S X D I T
#define CMD_START       "S"          // Start logging
#define CMD_STOP        "X"          // Stop/exit
#define CMD_DUMP        "D"          // Dump log file
#define CMD_LIST        "I"          // List files
#define CMD_STATUS      "T"          // Status info

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
