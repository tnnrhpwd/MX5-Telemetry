#include "CommandHandler.h"
#include "DataLogger.h"
#include "GPSHandler.h"
#include "CANHandler.h"
#include "LEDSlave.h"
#include <SdFat.h>

// ============================================================================
// Command Handler Implementation
// ============================================================================

CommandHandler::CommandHandler()
    : currentState(STATE_IDLE), bufferIndex(0), dataLogger(nullptr), gpsHandler(nullptr), canHandler(nullptr), dataReceived(false), ledSpeed(50), lastUSBLedCommand(0), lastUSBActivity(0), debugMode(false) {
    inputBuffer[0] = '\0';
}

void CommandHandler::begin() {
    currentState = STATE_IDLE;
    bufferIndex = 0;
    inputBuffer[0] = '\0';
    dataReceived = false;
    debugMode = false;  // Start with debug output disabled
    lastUSBActivity = 0;
}

void CommandHandler::update() {
    // Anti-flooding: limit command processing rate
    static unsigned long lastCommandTime = 0;
    static const unsigned long MIN_COMMAND_INTERVAL = 50; // 50ms minimum between commands
    
    // Non-blocking serial read with char buffer
    // Read all available characters rapidly to prevent buffer overflow
    int charsRead = 0;
    while (Serial.available() > 0 && charsRead < 64) {  // Limit chars per update
        // Mark that we've received USB data (prevents auto-start)
        dataReceived = true;
        
        // Enable debug mode and track USB activity time
        lastUSBActivity = millis();
        if (!debugMode) {
            debugMode = true;
            Serial.println(F("Debug mode enabled"));
        }
        
        char c = Serial.read();
        charsRead++;
        
        if (c == '\n' || c == '\r') {
            if (bufferIndex > 0) {
                inputBuffer[bufferIndex] = '\0';  // Null terminate
                
                // Flush any remaining CR/LF characters
                while (Serial.available() > 0 && charsRead < 64) {
                    char peek = Serial.peek();
                    if (peek == '\n' || peek == '\r') {
                        Serial.read();
                        charsRead++;
                    } else {
                        break;
                    }
                }
                
                // Rate limit command processing
                if (millis() - lastCommandTime >= MIN_COMMAND_INTERVAL) {
                    processCommand(inputBuffer);
                    lastCommandTime = millis();
                }
                
                bufferIndex = 0;
                inputBuffer[0] = '\0';
                break;  // Process one command per update call
            }
        } else if (c >= 32 && c <= 126 && bufferIndex < 255) {  // Printable ASCII, prevent overflow
            inputBuffer[bufferIndex++] = c;
        }
        // If buffer is getting full, clear it to prevent corruption
        if (bufferIndex >= 250) {
            bufferIndex = 0;
            inputBuffer[0] = '\0';
        }
    }
}

void CommandHandler::processCommand(const char* cmd) {
    // Fast path for LED commands (don't convert to uppercase - it's expensive for 244 chars)
    if (strncmp(cmd, "LED:", 4) == 0 || strncmp(cmd, "led:", 4) == 0) {
        handleLED(cmd);
        return;
    }
    
    // Fast path for RPM commands (also skip uppercase conversion)
    if (strncmp(cmd, "RPM:", 4) == 0 || strncmp(cmd, "rpm:", 4) == 0) {
        handleRPM(cmd);
        return;
    }
    
    // PRIORITY: Single-letter commands (most corruption-resistant)
    // Process first character only for speed and reliability
    char firstChar = toupper(cmd[0]);
    
    // Single letter commands take priority
    if (cmd[1] == '\0' || cmd[1] == '\r' || cmd[1] == '\n') {
        switch (firstChar) {
            case 'S': handleStart(); return;      // S = START
            case 'X': handleStop(); return;        // X = STOP (eXit)
            case 'I': handleList(); return;        // I = LIST (lIst)
            case 'T': handleStatus(); return;      // T = STATUS (sTatus)
            case 'L': handleLoopback(); return;    // L = LOOPBACK test
            // case 'C': handleCANTest(); return;  // C = CAN two-Arduino test (DISABLED for car safety)
        }
    }
    
    // Convert to uppercase for comparison (only for short commands)
    char command[32];  // Short buffer for non-LED/RPM commands
    uint8_t i = 0;
    while (cmd[i] && i < 31) {
        command[i] = toupper(cmd[i]);
        i++;
    }
    command[i] = '\0';
    
    // Short commands only
    if (firstChar == 'S') handleStart();
    else if (firstChar == 'X') handleStop();
    else if (firstChar == 'T') handleStatus();
    else if (firstChar == 'I') handleList();
    else if (firstChar == 'D') handleDump(cmd);
    else if (command[0] != '\0') {
        Serial.print(F("? "));
        Serial.println(command);
    }
}

void CommandHandler::handleStart() {
    if (currentState == STATE_IDLE || currentState == STATE_DUMPING) {
        setState(STATE_RUNNING);
        
        // Enable GPS if feature is enabled in config
        #if ENABLE_GPS
        if (gpsHandler) {
            gpsHandler->enable();  // Enable GPS for logging
        }
        #endif
        
        // Create log file immediately on START
        delay(100);  // Extra delay after disabling LEDs
        if (dataLogger) {
            #if ENABLE_GPS
            if (gpsHandler) {
                dataLogger->createLogFile(gpsHandler->getDate(), gpsHandler->getTime());
            } else {
                dataLogger->createLogFile(0, 0);
            }
            #else
            dataLogger->createLogFile(0, 0);  // GPS disabled in config
            #endif
        }
        
        Serial.println(F("OK"));
        Serial.flush();
    } else {
        Serial.println(F("E:S"));
    }
}

void CommandHandler::handleStop() {
    // Disable GPS to prevent serial interference
    #if ENABLE_GPS
    if (gpsHandler) {
        gpsHandler->disable();
    }
    #endif
    
    setState(STATE_IDLE);
    
    // Signal stop request - cleanup happens in logData
    if (dataLogger) {
        dataLogger->finishLogging();
    }
    
    while (Serial.available() > 0) {
        Serial.read();
    }
    
    Serial.println(F("OK"));
    Serial.flush();
}

void CommandHandler::handleStatus() {
    // Compact status with all system components
    Serial.print(F("St:"));
    if (currentState == STATE_RUNNING) Serial.print('R');
    else if (currentState == STATE_DUMPING) Serial.print('D');
    else Serial.print('I');
    
    #if ENABLE_LOGGING
    Serial.print(F(" SD:"));
    Serial.print((dataLogger && dataLogger->isInitialized()) ? 'Y' : 'N');
    #endif
    
    // Show GPS status with satellite count (key diagnostic info)
    #if ENABLE_GPS
    Serial.print(F(" GPS:"));
    if (gpsHandler) {
        Serial.print(gpsHandler->isEnabled() ? 'Y' : 'N');
        Serial.print(F(" S"));
        Serial.print(gpsHandler->getSatellites());
    } else {
        Serial.print('X');
    }
    #endif
    
    Serial.println(F(" OK"));
}

void CommandHandler::handleList() {
    if (dataLogger) {
        dataLogger->listFiles();
        delay(100);  // Long delay after SD operation
    } else {
        Serial.println(F("Files:0"));
        Serial.println(F("OK"));
    }
}

void CommandHandler::handleDump(const char* command) {
    if (!dataLogger) {
        Serial.println(F("E:DL"));
        return;
    }
    
    // Check current state - can't dump while running
    if (currentState == STATE_RUNNING) {
        Serial.println(F("E:B"));
        return;
    }
    
    setState(STATE_DUMPING);
    
    // Parse filename from command without using String objects
    // Format: "DUMP filename", "D filename", or just "DUMP"/"D"
    const char* spacePtr = strchr(command, ' ');
    
    if (spacePtr != nullptr && *(spacePtr + 1) != '\0') {
        // Found space and there's content after it
        const char* filename = spacePtr + 1;
        
        // Skip leading whitespace and any trailing CR/LF
        while (*filename == ' ' || *filename == '\t') filename++;
        
        // Create clean filename without line endings
        char cleanName[32];
        uint8_t i = 0;
        while (filename[i] && filename[i] != '\r' && filename[i] != '\n' && i < 31) {
            cleanName[i] = filename[i];
            i++;
        }
        cleanName[i] = '\0';
        
        if (cleanName[0] != '\0') {
            // Have a filename - pass cleaned version
            dataLogger->dumpFile(cleanName);
        } else {
            dataLogger->dumpCurrentLog();
        }
    } else {
        // No space or no content after space - dump current log
        dataLogger->dumpCurrentLog();
    }
    
    setState(STATE_IDLE);
}

void CommandHandler::handleRPM(const char* command) {
    // RPM command from USB - relay to LED Slave for testing
    // Format: RPM:3500 or R3500
    // Extract RPM value and relay to slave
    extern LEDSlave ledSlave;
    
    uint16_t rpm = 0;
    if (strncmp(command, "RPM:", 4) == 0 || strncmp(command, "rpm:", 4) == 0) {
        rpm = atoi(command + 4);
    } else if ((command[0] == 'R' || command[0] == 'r') && command[1] >= '0' && command[1] <= '9') {
        rpm = atoi(command + 1);
    }
    
    // Relay to Slave (use simulated speed of 50 to exit idle state)
    ledSlave.updateRPM(rpm, 50);
    Serial.print(F("LED: RPM="));
    Serial.println(rpm);
}

void CommandHandler::handleLED(const char* command) {
    // LED command from USB - relay to LED Slave for testing
    // Format: LED:<subcmd> where subcmd matches slave commands
    // Examples: LED:R3500, LED:S60, LED:C, LED:E, LED:W, LED:B128
    extern LEDSlave ledSlave;
    
    // Mark USB LED override active - this suppresses CAN->LED updates
    lastUSBLedCommand = millis();
    
    const char* subcmd = command + 4;  // Skip "LED:" prefix
    
    // Parse the sub-command and relay appropriately
    if (subcmd[0] == 'R' && subcmd[1] >= '0' && subcmd[1] <= '9') {
        // RPM command: R<rpm> - use tracked speed for proper LED state
        uint16_t rpm = atoi(subcmd + 1);
        ledSlave.updateRPM(rpm, ledSpeed);  // Use tracked speed for LED state
        Serial.print(F("LED: R"));
        Serial.print(rpm);
        Serial.print(F(" S"));
        Serial.println(ledSpeed);
    }
    else if (subcmd[0] == 'S' && subcmd[1] >= '0' && subcmd[1] <= '9') {
        // Speed command: S<speed> - track for subsequent RPM commands
        ledSpeed = atoi(subcmd + 1);
        ledSlave.updateSpeed(ledSpeed);
        Serial.print(F("LED: S"));
        Serial.println(ledSpeed);
    }
    else if (subcmd[0] == 'C' && (subcmd[1] == '\0' || subcmd[1] == '\r' || subcmd[1] == '\n')) {
        // Clear command
        ledSlave.clear();
        Serial.println(F("LED: Clear"));
    }
    else if (subcmd[0] == 'E' && (subcmd[1] == '\0' || subcmd[1] == '\r' || subcmd[1] == '\n')) {
        // Error mode
        ledSlave.updateRPMError();
        Serial.println(F("LED: Error mode"));
    }
    else if (subcmd[0] == 'W' && (subcmd[1] == '\0' || subcmd[1] == '\r' || subcmd[1] == '\n')) {
        // Wave/rainbow mode
        ledSlave.startWave();
        Serial.println(F("LED: Wave mode"));
    }
    else if (subcmd[0] == 'B' && subcmd[1] >= '0' && subcmd[1] <= '9') {
        // Brightness command: B<value>
        uint8_t brightness = atoi(subcmd + 1);
        ledSlave.setBrightness(brightness);
        Serial.print(F("LED: B"));
        Serial.println(brightness);
    }
    else {
        // Unknown sub-command
        Serial.print(F("LED: Unknown cmd: "));
        Serial.println(subcmd);
    }
}

void CommandHandler::handleLoopback() {
    // Run CAN loopback self-test (internal only, does NOT transmit on real bus)
    if (canHandler) {
        canHandler->runLoopbackTest();
    } else {
        Serial.println(F("E: CAN not available"));
    }
}

void CommandHandler::handleCANTest() {
    // REMOVED: Two-Arduino test transmitted on real CAN bus - unsafe for vehicle use
    Serial.println(F("E: CAN transmit tests disabled for safety"));
    Serial.println(F("   Use LOOPBACK command for self-test instead"));
}