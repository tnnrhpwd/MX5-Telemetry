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
    STATE_DUMPING        // Transferring log files to laptop
};

// Forward declarations
class DataLogger;
class GPSHandler;
class CANHandler;

class CommandHandler {
public:
    CommandHandler();
    
    // Initialization
    void begin();
    
    // Set references to other components
    void setDataLogger(DataLogger* logger) { dataLogger = logger; }
    void setGPSHandler(GPSHandler* handler) { gpsHandler = handler; }
    void setCANHandler(CANHandler* handler) { canHandler = handler; }
    
    // Command processing
    void update();  // Check for and process incoming commands
    
    // State management
    SystemState getState() const { return currentState; }
    bool isRunning() const { return currentState == STATE_RUNNING; }
    bool isDumping() const { return currentState == STATE_DUMPING; }
    bool shouldLog() const { return currentState == STATE_RUNNING; }
    bool shouldUpdateLEDs() const { return currentState == STATE_RUNNING; }
    bool hasReceivedData() const { return dataReceived; }  // Check if any USB data received
    
    // State transitions
    void setState(SystemState newState) { currentState = newState; }
    
    // Public command handlers (for auto-start on boot)
    void handleStart();
    
private:
    SystemState currentState;
    char inputBuffer[64];  // Reduced buffer - LED control moved to slave Arduino
    uint8_t bufferIndex;
    DataLogger* dataLogger;
    GPSHandler* gpsHandler;
    CANHandler* canHandler;
    bool dataReceived;  // Track if any USB data has been received
    
    // Command processors
    void processCommand(const char* command);
    void handleStop();
    void handleStatus();
    void handleList();
    void handleDump(const char* command);
    void handleRPM(const char* command);
    void handleLED(const char* command);
    void handleLoopback();  // CAN loopback self-test
};

#endif // COMMAND_HANDLER_H
