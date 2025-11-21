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
 * - Live data streaming mode
 * - Graceful error handling with auto-recovery
 * 
 * USB COMMANDS:
 * - START   : Begin logging and LED display
 * - PAUSE   : Stop logging and LED display
 * - RESUME  : Continue logging and LED display
 * - LIVE    : Real-time data streaming (no SD logging)
 * - STOP    : Exit live mode, return to pause
 * - DUMP    : Transfer log files to laptop
 * - STATUS  : Show system diagnostics
 * - LIST    : List all files on SD card
 * - HELP    : Show command reference
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
#include "LEDController.h"
#include "GPSHandler.h"
#include "DataLogger.h"
#include "CommandHandler.h"

// ============================================================================
// GLOBAL OBJECTS
// ============================================================================

CANHandler canBus(CAN_CS_PIN);
LEDController ledStrip(LED_DATA_PIN, LED_COUNT);
GPSHandler gps(GPS_RX_PIN, GPS_TX_PIN);
DataLogger dataLogger(SD_CS_PIN);
CommandHandler cmdHandler;

// ============================================================================
// TIMING VARIABLES
// ============================================================================

unsigned long lastCANRead = 0;
unsigned long lastGPSRead = 0;
unsigned long lastLogWrite = 0;
unsigned long lastStatusPrint = 0;

// ============================================================================
// STATUS PRINTING
// ============================================================================

void printSystemStatus() {
    Serial.print(F("St:"));
    if (cmdHandler.isRunning()) Serial.print('R');
    else if (cmdHandler.isPaused()) Serial.print('P');
    else if (cmdHandler.isLiveMonitoring()) Serial.print('L');
    else Serial.print('I');
    
    Serial.print(F(" CAN:"));
    Serial.print(canBus.isInitialized() ? 'Y' : 'N');
    Serial.print(F(" RPM:"));
    Serial.print(canBus.getRPM());
    
    Serial.print(F(" GPS:"));
    Serial.print(gps.isValid() ? 'Y' : 'N');
    Serial.print(F(" Sat:"));
    Serial.print(gps.getSatellites());
    
    Serial.print(F(" SD:"));
    Serial.print(dataLogger.isInitialized() ? 'Y' : 'N');
    
    Serial.print(F(" LED:"));
    Serial.println(cmdHandler.shouldUpdateLEDs() ? 'Y' : 'N');
}

// ============================================================================
// SETUP
// ============================================================================

void setup() {
    // Initialize Serial first for diagnostics
    Serial.begin(SERIAL_BAUD);
    while (!Serial && millis() < 3000) {
        ; // Wait up to 3 seconds for serial connection
    }
    
    delay(500);
    
    Serial.println(F("MX5v3"));
    canBus.begin();
    ledStrip.begin();
    ledStrip.startupAnimation();
    gps.begin();
    dataLogger.begin();
    cmdHandler.begin();
    ledStrip.readyAnimation();
    Serial.println(F("OK"));
    ledStrip.clear();
}

// ============================================================================
// MAIN LOOP
// ============================================================================

void loop() {
    unsigned long currentMillis = millis();
    
    // ========================================================================
    // COMMAND PROCESSING (Always Active)
    // ========================================================================
    cmdHandler.update();
    
    // ========================================================================
    // HIGH-FREQUENCY CAN BUS READING (50Hz - always read for status)
    // ========================================================================
    if (currentMillis - lastCANRead >= CAN_READ_INTERVAL) {
        lastCANRead = currentMillis;
        canBus.update();
    }
    
    // ========================================================================
    // GPS DATA ACQUISITION (10Hz - always read for status)
    // ========================================================================
    if (currentMillis - lastGPSRead >= GPS_READ_INTERVAL) {
        lastGPSRead = currentMillis;
        gps.update();
    }
    
    // ========================================================================
    // LED VISUAL FEEDBACK (State-dependent)
    // ========================================================================
    if (cmdHandler.shouldUpdateLEDs()) {
        ledStrip.updateRPM(canBus.getRPM());
    } else if (cmdHandler.isPaused()) {
        ledStrip.clear();
    }
    
    // ========================================================================
    // DATA LOGGING (5Hz - Only in RUNNING state)
    // ========================================================================
    if (cmdHandler.shouldLog() && currentMillis - lastLogWrite >= LOG_INTERVAL) {
        lastLogWrite = currentMillis;
        
        // Create log file if first run
        if (dataLogger.getLogFileName().length() == 0) {
            dataLogger.createLogFile(gps.getDate(), gps.getTime());
        }
        
        dataLogger.logData(
            currentMillis,
            gps,
            canBus,
            true,  // Log status: actively logging
            canBus.getErrorCount()
        );
    }
    
    // ========================================================================
    // LIVE DATA STREAMING (5Hz - Only in LIVE_MONITOR state)
    // ========================================================================
    if (cmdHandler.isLiveMonitoring() && currentMillis - lastLogWrite >= LOG_INTERVAL) {
        lastLogWrite = currentMillis;
        dataLogger.streamData(
            currentMillis,
            gps,
            canBus,
            false,  // Log status: streaming only, not logging to SD
            canBus.getErrorCount()
        );
    }
    
    // ========================================================================
    // STATUS COMMAND HANDLING
    // ========================================================================
    if (Serial.available() > 0) {
        String peek = Serial.readStringUntil('\n');
        peek.trim();
        peek.toUpperCase();
        
        if (peek == CMD_STATUS) {
            printSystemStatus();
        }
        else if (peek == CMD_LIST) {
            dataLogger.listFiles();
        }
        else if (peek.startsWith(CMD_DUMP)) {
            cmdHandler.setState(STATE_DUMPING);
            if (peek.length() > 5) {
                String filename = peek.substring(5);
                filename.trim();
                dataLogger.dumpFile(filename);
            } else {
                dataLogger.dumpCurrentLog();
            }
        }
    }
    
    // ========================================================================
    // CONTINUOUS GPS FEEDING (for best parsing performance)
    // ========================================================================
    gps.update();
}
