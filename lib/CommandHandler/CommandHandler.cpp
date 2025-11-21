#include "CommandHandler.h"

// ============================================================================
// Command Handler Implementation
// ============================================================================

CommandHandler::CommandHandler()
    : currentState(STATE_IDLE), inputBuffer("") {
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
    else if (command.startsWith(CMD_DUMP)) setState(STATE_DUMPING);
    else if (command == CMD_STATUS || command == CMD_LIST) return; // handled in main
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


