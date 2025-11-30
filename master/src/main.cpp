/*
 * ============================================================================
 * MX5-Telemetry System - Main Application
 * ============================================================================
 * 
 * A comprehensive USB-controlled embedded telemetry solution for Mazda Miata NC
 * 
 * FEATURES:
 * - CAN Bus communication at 500 kbaud for real-time vehicle data
 * - High-frequency RPM polling (50Hz) for accurate visual feedback
 * - WS2812B LED strip with color gradient and shift light indicator
 * - GPS logging with Neo-6M module (10Hz updates)
 * - SD card data logging in CSV format (5Hz logging rate)
 * - USB command interface for laptop control
 * - Auto-start logging after 10 seconds if no USB detected (standalone mode)
 * - Graceful error handling with auto-recovery
 * 
 * USB COMMANDS:
 * - S/START : Begin logging and LED display
 * - P/PAUSE : Stop logging and LED display
 * - X/STOP  : Stop logging, return to idle
 * - D/DUMP  : Transfer log files to laptop
 * - T/STATUS: Show system diagnostics
 * - I/LIST  : List all files on SD card
 * - ?/HELP  : Show command reference
 * 
 * HARDWARE REQUIREMENTS:
 * - Arduino Nano V3.0 (ATmega328P, 16MHz, 5V logic)
 * - MCP2515 CAN Controller with TJA1050 transceiver (500 kbaud, 16MHz crystal)
 * - WS2812B Addressable LED Strip (30 LEDs recommended)
 * - Neo-6M GPS Module (UART, 9600 baud)
 * - MicroSD Card Module (SPI, FAT32 formatted)
 * - LM2596 Buck Converter (12V automotive → 5V regulated, 3A minimum)
 * 
 * PERFORMANCE SPECIFICATIONS:
 * - CAN Bus Read Rate: 50Hz (every 20ms)
 * - GPS Update Rate: 10Hz (every 100ms)
 * - Data Logging Rate: 5Hz (every 200ms)
 * - LED Refresh Rate: ~50Hz (flicker-free)
 * - Memory Usage: ~98% Flash, ~67% RAM
 * 
 * AUTHOR: GitHub Copilot
 * DATE: 2025-11-20
 * VERSION: 3.0.0 (USB Command Interface)
 * LICENSE: MIT
 * ============================================================================
 */

#include <Arduino.h>
#include <config.h>
#include "CANHandler.h"
#include "GPSHandler.h"
#include "DataLogger.h"
#include "CommandHandler.h"
#include "LEDSlave.h"

// ============================================================================
// GLOBAL OBJECTS
// ============================================================================

CANHandler canBus(CAN_CS_PIN);
GPSHandler gps(GPS_RX_PIN, GPS_TX_PIN);
DataLogger dataLogger(SD_CS_PIN);
CommandHandler cmdHandler;
LEDSlave ledSlave;  // Communicates with slave Arduino via Serial1

// ============================================================================
// TIMING VARIABLES
// ============================================================================

unsigned long lastCANRead = 0;
unsigned long lastGPSRead = 0;
unsigned long lastLogWrite = 0;
unsigned long lastLEDUpdate = 0;  // Track LED updates to rate-limit
unsigned long logFileStartTime = 0;  // Track when current log file was created
unsigned long bootTime = 0;  // Track system boot time for auto-start
bool autoStartTriggered = false;  // Track if auto-start has been triggered

// ============================================================================
// STATUS PRINTING
// ============================================================================

void printSystemStatus() {
    Serial.print(F("St:"));
    if (cmdHandler.isRunning()) Serial.print('R');
    else if (cmdHandler.isDumping()) Serial.print('D');
    else Serial.print('I');
    
    #if ENABLE_CAN_BUS
        Serial.print(F(" CAN:"));
        Serial.print(canBus.isInitialized() ? 'Y' : 'N');
        Serial.print(F(" RPM:"));
        Serial.print(canBus.getRPM());
    #else
        Serial.print(F(" CAN:Off"));
    #endif
    
    #if ENABLE_GPS
        Serial.print(F(" G:"));
        Serial.print(gps.isEnabled() ? 'E' : 'D');
        Serial.print(gps.isValid() ? 'Y' : 'N');
        Serial.print(gps.getSatellites());
    #endif
    
    #if ENABLE_LOGGING
        Serial.print(F(" SD:"));
        Serial.print(dataLogger.isInitialized() ? 'Y' : 'N');
    #else
        Serial.print(F(" SD:Off"));
    #endif
    
    #if ENABLE_LED_SLAVE
        Serial.print(F(" LED:"));
        Serial.println(cmdHandler.shouldUpdateLEDs() ? 'Y' : 'N');
    #else
        Serial.println(F(" LED:Off"));
    #endif
}

// ============================================================================
// SETUP
// ============================================================================

void setup() {
    // Initialize Serial first for diagnostics
    Serial.begin(SERIAL_BAUD);
    Serial.setTimeout(100); // Set 100ms timeout for Serial operations
    
    // Record boot time for auto-start feature
    bootTime = millis();
    autoStartTriggered = false;
    
    // Print identification (ignored if no PC)
    Serial.println(F("MX5v3"));
    
    // ========================================================================
    // BOOT DELAY - Prevent corrupted log files during upload/reset cycles
    // The bootloader can cause multiple resets during upload, creating garbage files
    // ========================================================================
    Serial.println(F("Boot delay (10s)..."));
    delay(BOOT_DELAY_MS);
    Serial.println(F("Boot delay complete"));
    
    // Reset boot time AFTER delay so auto-start timer starts from here
    bootTime = millis();
    
    // Initialize only enabled modules
    #if ENABLE_CAN_BUS
        if (canBus.begin()) {
            if (Serial) Serial.println(F("CAN: OK"));
        } else {
            if (Serial) Serial.println(F("CAN: Error"));
        }
    #else
        if (Serial) Serial.println(F("CAN: Disabled"));
    #endif
    
    #if ENABLE_LED_SLAVE
        ledSlave.begin();
        if (Serial) Serial.println(F("LED: Slave Ready"));
        
        // Test communication - send clear command
        delay(500);
        ledSlave.clear();
        delay(100);
    #else
        if (Serial) Serial.println(F("LED: Disabled"));
    #endif
    
    #if ENABLE_GPS
        gps.begin();
        if (Serial) Serial.println(F("GPS: Ready (disabled until START)"));
    #else
        if (Serial) Serial.println(F("GPS: Disabled"));
    #endif
    
    #if ENABLE_LOGGING
        if (dataLogger.begin()) {
            if (Serial) Serial.println(F("SD: OK"));
        } else {
            if (Serial) Serial.println(F("SD: FAIL (No card/Bad format)"));
        }
    #else
        if (Serial) Serial.println(F("LOG: Disabled"));
    #endif
    
    cmdHandler.begin();
    
    // Connect components
    #if ENABLE_LOGGING
        cmdHandler.setDataLogger(&dataLogger);
    #endif
    
    // LED control handled by LEDSlave class via bit-bang serial
    
    #if ENABLE_GPS
        cmdHandler.setGPSHandler(&gps);
    #endif
    
    #if ENABLE_LED_SLAVE
        ledSlave.clear();
        delay(100);  // Wait for slave to process clear command
        
        // Send initial LED state immediately after setup
        #if ENABLE_CAN_BUS
            if (!canBus.isInitialized()) {
                ledSlave.updateRPMError();  // Show error pattern
            } else {
                ledSlave.updateRPM(0, 0);  // Show idle state (car off)
            }
        #else
            ledSlave.updateRPM(0, 0);  // Show idle state when CAN disabled
        #endif
    #endif
    
    Serial.println(F("OK"));
    Serial.flush();
}

// ============================================================================
// MAIN LOOP
// ============================================================================

void loop() {
    unsigned long currentMillis = millis();
    
    // ========================================================================
    // COMMAND PROCESSING (Always Active - HIGHEST PRIORITY)
    // Process commands immediately and repeatedly to prevent GPS interference
    // ========================================================================
    cmdHandler.update();
    
    // Call again to catch any data that arrived during first call
    if (Serial.available() > 0) {
        cmdHandler.update();
    }
    
    // ========================================================================
    // AUTO-START (Standalone mode - no USB commands received)
    // ========================================================================
    #if AUTO_START_ENABLED
        // If no USB data received within timeout and still in IDLE state, auto-start
        if (!autoStartTriggered && 
            !cmdHandler.hasReceivedData() &&
            cmdHandler.getState() == STATE_IDLE && 
            (currentMillis - bootTime) >= AUTO_START_TIMEOUT) {
            
            autoStartTriggered = true;
            
            // Log auto-start (will be ignored if no USB connected)
            if (Serial) Serial.println(F("Auto-start: No USB detected, starting logging..."));
            
            // Trigger START command
            cmdHandler.handleStart();
        }
    #endif
    
    // ========================================================================
    // LOG ROTATION (create new log file periodically to prevent huge files)
    // ========================================================================
    #if LOG_ROTATION_ENABLED && ENABLE_LOGGING
        if (cmdHandler.shouldLog()) {
            // Track when current log file was created
            if (logFileStartTime == 0) {
                logFileStartTime = currentMillis;
            }
            
            // Check if rotation interval exceeded
            if ((currentMillis - logFileStartTime) >= LOG_ROTATION_INTERVAL) {
                // Close current log file
                dataLogger.finishLogging();
                
                // Create new log file with current GPS datetime
                #if ENABLE_GPS
                    dataLogger.createLogFile(gps.getDate(), gps.getTime());
                #else
                    dataLogger.createLogFile(0, 0);
                #endif
                
                // Skip LED updates during file rotation
                #if ENABLE_LED_SLAVE
                    lastLEDUpdate = currentMillis;
                #endif
                
                // Reset timer for new file
                logFileStartTime = currentMillis;
            }
        } else {
            // Not logging, reset timer
            logFileStartTime = 0;
        }
    #endif
    
    // ========================================================================
    // HIGH-FREQUENCY CAN BUS READING (50Hz - only if enabled)
    // Only update if CAN was successfully initialized
    // ========================================================================
    #if ENABLE_CAN_BUS
        if (canBus.isInitialized() && currentMillis - lastCANRead >= CAN_READ_INTERVAL) {
            lastCANRead = currentMillis;
            canBus.update();
        }
    #endif
    
    // ========================================================================
    // GPS DATA ACQUISITION (10Hz - only if enabled)
    // GPS is dynamically enabled/disabled based on system state to prevent
    // SoftwareSerial/hardware Serial conflicts:
    // - ENABLED: During RUNNING state (logging) - GPS data needed
    // - DISABLED: During IDLE/PAUSED/LIVE/DUMPING - Clean USB communication
    // ========================================================================
    #if ENABLE_GPS
        if (gps.isEnabled() && currentMillis - lastGPSRead >= GPS_READ_INTERVAL) {
            lastGPSRead = currentMillis;
            gps.update();
        }
    #endif
    
    // ========================================================================
    // LED VISUAL FEEDBACK (Send commands to slave Arduino)
    // Always show real RPM from CAN bus when available, regardless of logging state
    // ========================================================================
    #if ENABLE_LED_SLAVE
        // Send RPM updates to slave Arduino at reduced rate
        if (currentMillis - lastLEDUpdate >= LED_UPDATE_INTERVAL && Serial.available() == 0) {
            lastLEDUpdate = currentMillis;
            
            // Cache values before sending to avoid SPI during bit-bang
            uint16_t rpm = 0;
            uint16_t speed = 0;
            bool showError = false;
            
            #if ENABLE_CAN_BUS
                if (!canBus.isInitialized()) {
                    showError = true;
                } else if (canBus.hasRecentData()) {
                    rpm = canBus.getRPM();
                    speed = canBus.getSpeed();
                }
            #endif
            
            // Now send to LED slave (no other operations during this)
            if (showError) {
                ledSlave.updateRPMError();
            } else {
                ledSlave.updateRPM(rpm, speed);
            }
            
            // Skip next CAN read cycle to avoid immediate SPI after bit-bang
            lastCANRead = millis();
        }
    #endif
    
    // ========================================================================
    // DATA LOGGING (5Hz - Only in RUNNING state and if enabled)
    // ========================================================================
    #if ENABLE_LOGGING
        if (cmdHandler.shouldLog() && currentMillis - lastLogWrite >= LOG_INTERVAL) {
            lastLogWrite = currentMillis;
            
            // Skip LED updates during this loop iteration (SD write priority)
            #if ENABLE_LED_SLAVE
                lastLEDUpdate = currentMillis;
            #endif
            
            // Safety check: only log if we have an active log file
            if (dataLogger.getLogFileName()[0] == '\0') {
                #if ENABLE_GPS
                    dataLogger.createLogFile(gps.getDate(), gps.getTime());
                #else
                    dataLogger.createLogFile(0, 0);  // Use timestamp-based filename
                #endif
            }
            
            // Double-check we still have a filename after creation attempt
            // This prevents writes after STOP clears the filename
            if (dataLogger.getLogFileName()[0] != '\0') {
                dataLogger.logData(
                    currentMillis,
                    #if ENABLE_GPS
                        gps,
                    #else
                        gps,  // Pass anyway, DataLogger will handle missing data
                    #endif
                    #if ENABLE_CAN_BUS
                        canBus,
                    #else
                        canBus,  // Pass anyway, DataLogger will handle missing data
                    #endif
                    true,  // Log status: actively logging
                    #if ENABLE_CAN_BUS
                        canBus.getErrorCount()
                    #else
                        0
                    #endif
                );
            }
        }
    #endif
    
    // ========================================================================
    // PERIODIC STATUS (disabled - saves flash space)
    // ========================================================================
    
    // GPS is now updated during timed intervals only (see above)
    // This reduces SoftwareSerial interrupt overhead that interferes with USB Serial
}
