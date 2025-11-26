#include "CommandHandler.h"
#include "DataLogger.h"
#include "LEDController.h"
#include "GPSHandler.h"
#include <SdFat.h>

// ============================================================================
// Command Handler Implementation
// ============================================================================

CommandHandler::CommandHandler()
    : currentState(STATE_IDLE), bufferIndex(0), dataLogger(nullptr), ledController(nullptr), gpsHandler(nullptr) {
    inputBuffer[0] = '\0';
}

void CommandHandler::begin() {
    currentState = STATE_IDLE;
    bufferIndex = 0;
    inputBuffer[0] = '\0';
}

void CommandHandler::update() {
    // Anti-flooding: limit command processing rate
    static unsigned long lastCommandTime = 0;
    static const unsigned long MIN_COMMAND_INTERVAL = 50; // 50ms minimum between commands
    
    // Non-blocking serial read with char buffer
    // Read all available characters rapidly to prevent buffer overflow
    int charsRead = 0;
    while (Serial.available() > 0 && charsRead < 64) {  // Limit chars per update
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
            case 'P': handlePause(); return;       // P = PAUSE
            case 'X': handleStop(); return;        // X = STOP (eXit)
            case 'L': handleLive(); return;        // L = LIVE
            case '?': handleHelp(); return;        // ? = HELP
            case 'I': handleList(); return;        // I = LIST (lIst)
            case 'T': handleStatus(); return;      // T = STATUS (sTatus)
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
    else if (firstChar == 'P') handlePause();
    else if (firstChar == 'L') handleLive();
    else if (firstChar == 'X') handleStop();
    else if (firstChar == '?') handleHelp();
    else if (firstChar == 'T') handleStatus();
    else if (firstChar == 'I') handleList();
    else if (firstChar == 'D') handleDump(cmd);
    else if (command[0] != '\0') {
        Serial.print(F("? "));
        Serial.println(command);
    }
}

void CommandHandler::handleStart() {
    if (currentState == STATE_IDLE || currentState == STATE_PAUSED || currentState == STATE_DUMPING) {
        #if ENABLE_LED_STRIP
        if (ledController) ledController->disable();
        #endif
        
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
        
        delay(100);  // Delay after file creation before re-enabling LEDs
        
        #if ENABLE_LED_STRIP
        if (ledController) {
            ledController->enable();
            delay(50);  // Allow enable to settle
        }
        #endif
        
        Serial.println(F("OK"));
        Serial.flush();
    } else {
        Serial.println(F("E:S"));
    }
}

void CommandHandler::handlePause() {
    if (currentState == STATE_RUNNING || currentState == STATE_LIVE_MONITOR) {
        // Disable GPS to restore clean USB communication
        #if ENABLE_GPS
        if (gpsHandler) {
            gpsHandler->disable();
        }
        #endif
        
        setState(STATE_PAUSED);
        Serial.println(F("OK"));
    } else {
        Serial.println(F("E:S"));
    }
}

void CommandHandler::handleLive() {
    if (currentState == STATE_PAUSED || currentState == STATE_IDLE || currentState == STATE_RUNNING) {
        // Disable GPS for clean USB streaming
        #if ENABLE_GPS
        if (gpsHandler) {
            gpsHandler->disable();
        }
        #endif
        
        setState(STATE_LIVE_MONITOR);
        Serial.println(F("LIVE"));
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
    
    setState(STATE_PAUSED);
    
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

void CommandHandler::handleHelp() {
    Serial.println(F("S P X L D I T ?"));
}

void CommandHandler::handleStatus() {
    // Quick status without SD card enumeration (avoids timeout)
    Serial.print(F("St:"));
    if (currentState == STATE_RUNNING) Serial.print('R');
    else if (currentState == STATE_PAUSED) Serial.print('P');
    else if (currentState == STATE_LIVE_MONITOR) Serial.print('L');
    else if (currentState == STATE_DUMPING) Serial.print('D');
    else Serial.print('I');
    
    Serial.println(F(" OK"));
}

void CommandHandler::handleList() {
    #if ENABLE_LED_STRIP
    if (ledController) {
        ledController->disable();
        delay(100);  // Long delay after disabling LEDs
    }
    #endif
    
    if (dataLogger) {
        dataLogger->listFiles();
        delay(100);  // Long delay after SD operation
    } else {
        Serial.println(F("Files:0"));
    }
    
    #if ENABLE_LED_STRIP
    // Re-enable LEDs after SD operation completes
    if (ledController && shouldUpdateLEDs()) {
        delay(100);  // Long delay before re-enabling LEDs
        ledController->enable();
    }
    #endif
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
    
    #if ENABLE_LED_STRIP
    if (ledController) {
        ledController->disable();
        delay(100);  // Long delay after disabling LEDs
    }
    #endif
    
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
    
    #if ENABLE_LED_STRIP
    // Re-enable LEDs after SD operation completes (only if appropriate for current state)
    if (ledController && shouldUpdateLEDs()) {
        delay(100);  // Long delay before re-enabling LEDs
        ledController->enable();
    }
    #endif
}

void CommandHandler::handleRPM(const char* command) {
    // Parse RPM value from command (format: RPM:xxxx)
    int rpm = 0;
    
    // Skip "RPM:" prefix (4 characters)
    const char* rpmStr = command + 4;
    
    // Convert string to integer
    while (*rpmStr >= '0' && *rpmStr <= '9') {
        rpm = rpm * 10 + (*rpmStr - '0');
        rpmStr++;
    }
    
    // Update LED display based on RPM
    // This directly updates the LED strip to match the simulator
    if (ledController) {
        ledController->setRPM(rpm);
        ledController->update();
    }
}



void CommandHandler::handleLED(const char* command) {
    // Parse LED color data from command (format: LED:RRGGBBRRGGBB...)
    // Each LED is 6 hex characters: RRGGBB
    
    if (!ledController) {
        return;
    }
    
    // Skip "LED:" prefix (4 characters)
    const char* hexData = command + 4;
    
    // Helper function to convert hex char to int
    auto hexToInt = [](char c) -> int {
        if (c >= '0' && c <= '9') return c - '0';
        if (c >= 'A' && c <= 'F') return c - 'A' + 10;
        if (c >= 'a' && c <= 'f') return c - 'a' + 10;
        return 0;
    };
    
    // Parse each LED color (40 LEDs * 6 chars = 240 chars expected)
    int ledIndex = 0;
    while (*hexData && ledIndex < 40) {
        // Parse R (2 hex chars)
        if (!hexData[0] || !hexData[1]) break;
        uint8_t r = (hexToInt(hexData[0]) << 4) | hexToInt(hexData[1]);
        hexData += 2;
        
        // Parse G (2 hex chars)
        if (!hexData[0] || !hexData[1]) break;
        uint8_t g = (hexToInt(hexData[0]) << 4) | hexToInt(hexData[1]);
        hexData += 2;
        
        // Parse B (2 hex chars)
        if (!hexData[0] || !hexData[1]) break;
        uint8_t b = (hexToInt(hexData[0]) << 4) | hexToInt(hexData[1]);
        hexData += 2;
        
        // Set LED color directly
        ledController->setPixelColor(ledIndex, r, g, b);
        ledIndex++;
    }
    
    // Update the strip to show changes
    ledController->update();
}