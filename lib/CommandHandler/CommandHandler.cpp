#include "CommandHandler.h"
#include "DataLogger.h"

// ============================================================================
// Command Handler Implementation
// ============================================================================

CommandHandler::CommandHandler()
    : currentState(STATE_IDLE), bufferIndex(0), dataLogger(nullptr) {
    inputBuffer[0] = '\0';
}

void CommandHandler::begin() {
    currentState = STATE_IDLE;
    bufferIndex = 0;
    inputBuffer[0] = '\0';
}

void CommandHandler::update() {
    // Non-blocking serial read with char buffer
    while (Serial.available() > 0) {
        char c = Serial.read();
        
        if (c == '\n' || c == '\r') {
            if (bufferIndex > 0) {
                inputBuffer[bufferIndex] = '\0';  // Null terminate
                processCommand(inputBuffer);
                bufferIndex = 0;
                inputBuffer[0] = '\0';
            }
        } else if (c >= 32 && c <= 126 && bufferIndex < 31) {  // Printable ASCII, prevent overflow
            inputBuffer[bufferIndex++] = c;
        }
    }
}

void CommandHandler::processCommand(const char* cmd) {
    // Convert to uppercase for comparison
    char command[32];
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
        handleDump(String(command));
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
    setState(STATE_PAUSED);
    Serial.println(F("OK"));
    Serial.flush();
}

void CommandHandler::handleHelp() {
    Serial.println(F("START|PAUSE|LIVE|STOP|DUMP|LIST|STATUS"));
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
        dataLogger->getSDCardInfo(totalKB, usedKB, fileCount);
        
        Serial.print(F(" SD:"));
        Serial.print(usedKB);
        Serial.print(F("KB"));
        
        Serial.print(F(" Files:"));
        Serial.print(fileCount);
        
        String currentLog = dataLogger->getLogFileName();
        if (currentLog.length() > 0) {
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
        Serial.println(F("DEBUG:Calling listFiles"));
        Serial.flush();
        dataLogger->listFiles();
    } else {
        Serial.println(F("ERR:NO_LOGGER"));
        Serial.println(F("Files:0"));
        Serial.flush();
    }
}

void CommandHandler::handleDump(const String& command) {
    if (!dataLogger) {
        Serial.println(F("ERR:NO_LOGGER"));
        Serial.flush();
        return;
    }
    
    setState(STATE_DUMPING);
    
    // Parse filename if provided
    if (command.length() > 5) {
        String filename = command.substring(5);
        filename.trim();
        dataLogger->dumpFile(filename);
    } else {
        // Current log dump
        dataLogger->dumpCurrentLog();
    }
    
    setState(STATE_IDLE);
}



