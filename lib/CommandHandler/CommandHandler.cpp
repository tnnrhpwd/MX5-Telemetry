#include "CommandHandler.h"
#include "DataLogger.h"
#include "LEDController.h"
#include <SdFat.h>

// ============================================================================
// Command Handler Implementation
// ============================================================================

CommandHandler::CommandHandler()
    : currentState(STATE_IDLE), bufferIndex(0), dataLogger(nullptr), ledController(nullptr) {
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
    
    // Convert to uppercase for comparison (only for short commands)
    char command[32];  // Short buffer for non-LED/RPM commands
    uint8_t i = 0;
    while (cmd[i] && i < 31) {
        command[i] = toupper(cmd[i]);
        i++;
    }
    command[i] = '\0';
    
    if (strcmp(command, "START") == 0) {
        handleStart();
    }
    else if (strcmp(command, "PAUSE") == 0) handlePause();
    else if (strcmp(command, "LIVE") == 0) handleLive();
    else if (strcmp(command, "STOP") == 0) {
        handleStop();
    }
    else if (strcmp(command, "HELP") == 0) handleHelp();
    else if (strcmp(command, "STATUS") == 0) {
        handleStatus();
    }
    else if (strcmp(command, "LIST") == 0) {
        handleList();
    }
    else if (strncmp(command, "DUMP", 4) == 0) {
        handleDump(cmd);  // Use original cmd, not uppercase command
    }
    else if (strcmp(command, "TEST") == 0) {
        handleTest();
    }
    else if (command[0] != '\0') {
        Serial.print(F("? "));
        Serial.println(command);
        Serial.flush();
    }
}

void CommandHandler::handleStart() {
    if (currentState == STATE_IDLE || currentState == STATE_PAUSED || currentState == STATE_DUMPING) {
        setState(STATE_RUNNING);
        Serial.println(F("OK"));
        Serial.flush();
    } else if (currentState == STATE_RUNNING) {
        Serial.println(F("ALREADY_RUNNING"));
        Serial.flush();
    } else if (currentState == STATE_LIVE_MONITOR) {
        Serial.println(F("ERR:IN_LIVE_MODE"));
        Serial.flush();
    }
}

void CommandHandler::handlePause() {
    if (currentState == STATE_RUNNING || currentState == STATE_LIVE_MONITOR) {
        setState(STATE_PAUSED);
        Serial.println(F("OK"));
        Serial.flush();
    } else if (currentState == STATE_PAUSED || currentState == STATE_IDLE) {
        Serial.println(F("ALREADY_PAUSED"));
        Serial.flush();
    } else {
        Serial.println(F("ERR:INVALID_STATE"));
        Serial.flush();
    }
}

void CommandHandler::handleLive() {
    if (currentState == STATE_PAUSED || currentState == STATE_IDLE || currentState == STATE_RUNNING) {
        setState(STATE_LIVE_MONITOR);
        Serial.println(F("LIVE"));
        Serial.flush();
    } else if (currentState == STATE_LIVE_MONITOR) {
        Serial.println(F("ALREADY_LIVE"));
        Serial.flush();
    } else {
        Serial.println(F("ERR:INVALID_STATE"));
        Serial.flush();
    }
}

void CommandHandler::handleStop() {
    // Stop all operations immediately
    setState(STATE_PAUSED);
    
    // Signal stop request - cleanup happens in logData
    if (dataLogger) {
        dataLogger->finishLogging();
    }
    
    Serial.println(F("OK"));
    Serial.flush();
}

void CommandHandler::handleHelp() {
    Serial.println(F("START|PAUSE|LIVE|STOP|DUMP|LIST|STATUS|TEST"));
    Serial.flush();
}

void CommandHandler::handleStatus() {
    // Status printing moved to CommandHandler for better encapsulation
    Serial.print(F("St:"));
    if (currentState == STATE_RUNNING) Serial.print('R');
    else if (currentState == STATE_PAUSED) Serial.print('P');
    else if (currentState == STATE_LIVE_MONITOR) Serial.print('L');
    else if (currentState == STATE_DUMPING) Serial.print('D');
    else Serial.print('I');
    
    // Add SD card information if DataLogger is available
    if (dataLogger && dataLogger->isInitialized()) {
        uint32_t totalKB = 0;
        uint32_t usedKB = 0;
        uint8_t fileCount = 0;
        
        // Flush before SD operations to prevent corruption
        Serial.flush();
        
        dataLogger->getSDCardInfo(totalKB, usedKB, fileCount);
        
        Serial.print(F(" SD:"));
        Serial.print(usedKB);
        Serial.print(F("KB"));
        
        Serial.print(F(" Files:"));
        Serial.print(fileCount);
        
        const char* currentLog = dataLogger->getLogFileName();
        if (currentLog[0] != '\0') {
            Serial.print(F(" Log:"));
            Serial.print(currentLog);
        }
    } else {
        Serial.print(F(" SD:N/A"));
    }
    
    Serial.println(F(" OK"));
    Serial.flush();
}

void CommandHandler::handleList() {
    // Call DataLogger to list files
    if (dataLogger) {
        dataLogger->listFiles();
    } else {
        Serial.println(F("Files:0"));
        Serial.flush();
    }
}

void CommandHandler::handleDump(const char* command) {
    if (!dataLogger) {
        Serial.println(F("ERR:NO_LOGGER"));
        Serial.flush();
        return;
    }
    
    setState(STATE_DUMPING);
    
    // Parse filename from command without using String objects
    // Format: "DUMP filename" or just "DUMP"
    const char* spacePtr = strchr(command, ' ');
    
    if (spacePtr != nullptr && *(spacePtr + 1) != '\0') {
        // Found space and there's content after it
        const char* filename = spacePtr + 1;
        
        // Skip leading whitespace
        while (*filename == ' ' || *filename == '\t') filename++;
        
        if (*filename != '\0') {
            // Have a filename - pass directly without String conversion
            dataLogger->dumpFile(filename);
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

void CommandHandler::handleTest() {
    if (!dataLogger) {
        Serial.println(F("ERR:NO_LOGGER"));
        Serial.flush();
        return;
    }
    
    Serial.println(F("Creating test file..."));
    Serial.flush();
    
    // TEST command not critical - just acknowledge
    Serial.println(F("Test mode disabled"));
    Serial.flush();
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






