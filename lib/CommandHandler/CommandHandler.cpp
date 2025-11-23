#include "CommandHandler.h"
#include "DataLogger.h"

// ============================================================================
// Command Handler Implementation
// ============================================================================

CommandHandler::CommandHandler()
    : currentState(STATE_IDLE), inputBuffer(""), dataLogger(nullptr) {
}

void CommandHandler::begin() {
    currentState = STATE_IDLE;
}

void CommandHandler::update() {
    // Non-blocking serial read
    while (Serial.available() > 0) {
        char c = Serial.read();
        
        if (c == '\n' || c == '\r') {
            if (inputBuffer.length() > 0) {
                processCommand(inputBuffer);
                inputBuffer = "";
            }
        } else {
            inputBuffer += c;
        }
    }
}

void CommandHandler::processCommand(const String& cmd) {
    String command = cmd;
    command.trim();
    command.toUpperCase();
    
    if (command == CMD_START) handleStart();
    else if (command == CMD_PAUSE) handlePause();
    else if (command == CMD_LIVE) handleLive();
    else if (command == CMD_STOP) handleStop();
    else if (command == CMD_HELP) handleHelp();
    else if (command == CMD_STATUS) handleStatus();
    else if (command == CMD_LIST) handleList();
    else if (command.startsWith(CMD_DUMP)) handleDump(command);
    else if (command.length() > 0) {
        Serial.print(F("? "));
        Serial.println(command);
    }
}

void CommandHandler::handleStart() {
    if (currentState == STATE_IDLE || currentState == STATE_PAUSED || currentState == STATE_DUMPING) {
        setState(STATE_RUNNING);
        Serial.println(F("OK"));
    }
}

void CommandHandler::handlePause() {
    if (currentState == STATE_RUNNING || currentState == STATE_LIVE_MONITOR) {
        setState(STATE_PAUSED);
        Serial.println(F("OK"));
    }
}

void CommandHandler::handleLive() {
    if (currentState == STATE_PAUSED || currentState == STATE_IDLE || currentState == STATE_RUNNING) {
        setState(STATE_LIVE_MONITOR);
        Serial.println(F("LIVE"));
    }
}

void CommandHandler::handleStop() {
    setState(STATE_PAUSED);
    Serial.println(F("OK"));
}

void CommandHandler::handleHelp() {
    Serial.println(F("START|PAUSE|LIVE|STOP|DUMP|LIST|STATUS"));
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
}

void CommandHandler::handleList() {
    // Call DataLogger to list files
    if (dataLogger) {
        Serial.println(F("DEBUG:Calling listFiles"));
        dataLogger->listFiles();
    } else {
        Serial.println(F("ERR:NO_LOGGER"));
        Serial.println(F("Files:0"));
    }
}

void CommandHandler::handleDump(const String& command) {
    if (!dataLogger) {
        Serial.println(F("ERR:NO_LOGGER"));
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



