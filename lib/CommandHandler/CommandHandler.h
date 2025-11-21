#ifndef COMMAND_HANDLER_H
#define COMMAND_HANDLER_H

#include <Arduino.h>
#include <config.h>

// ============================================================================
// System State Management and USB Command Interface
// ============================================================================
// Handles serial commands from laptop for remote control of logging and display
// ============================================================================

// System operating states
enum SystemState {
    STATE_IDLE,          // Initial state, waiting for START command
    STATE_RUNNING,       // Normal operation: logging + LED display active
    STATE_PAUSED,        // Logging and LED paused, awaiting commands
    STATE_LIVE_MONITOR,  // Real-time data streaming to laptop (no SD logging)
    STATE_DUMPING        // Transferring log files to laptop
};

class CommandHandler {
public:
    CommandHandler();
    
    // Initialization
    void begin();
    
    // Command processing
    void update();  // Check for and process incoming commands
    
    // State management
    SystemState getState() const { return currentState; }
    bool isRunning() const { return currentState == STATE_RUNNING; }
    bool isPaused() const { return currentState == STATE_PAUSED; }
    bool isLiveMonitoring() const { return currentState == STATE_LIVE_MONITOR; }
    bool isDumping() const { return currentState == STATE_DUMPING; }
    bool shouldLog() const { return currentState == STATE_RUNNING; }
    bool shouldUpdateLEDs() const { return currentState == STATE_RUNNING || currentState == STATE_LIVE_MONITOR; }
    
    // State transitions
    void setState(SystemState newState) { currentState = newState; }
    
private:
    SystemState currentState;
    String inputBuffer;
    
    // Command processors
    void processCommand(const String& command);
    void handleStart();
    void handlePause();
    void handleResume();
    void handleLive();
    void handleStop();
    void handleHelp();
};

#endif // COMMAND_HANDLER_H
