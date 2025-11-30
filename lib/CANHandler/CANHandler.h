#ifndef CAN_HANDLER_H
#define CAN_HANDLER_H

#include <Arduino.h>
#include <mcp_can.h>
#include <config.h>

// ============================================================================
// CAN Bus Communication Handler
// ============================================================================
// Handles all CAN bus communication including initialization, reading data,
// and dual-mode operation (direct CAN monitoring + OBD-II fallback)
// ============================================================================

class CANHandler {
public:
    CANHandler(uint8_t csPin);
    
    // Initialization
    bool begin();
    
    // Data reading (50Hz for high-frequency RPM polling)
    void update();
    
    // Data accessors - Core Performance
    uint16_t getRPM() const { return currentRPM; }
    uint8_t getSpeed() const { return vehicleSpeed; }
    uint8_t getThrottle() const { return throttlePosition; }
    uint8_t getCalculatedLoad() const { return calculatedLoad; }
    
    // Data accessors - Engine Health
    int8_t getCoolantTemp() const { return coolantTemp; }
    int8_t getIntakeTemp() const { return intakeTemp; }
    uint8_t getBarometric() const { return barometric; }
    
    // Data accessors - Tuning Data
    int8_t getTimingAdvance() const { return timingAdvance; }
    uint16_t getMAFRate() const { return mafRate; }
    int8_t getShortFuelTrim() const { return shortFuelTrim; }
    int8_t getLongFuelTrim() const { return longFuelTrim; }
    float getO2Voltage() const { return o2Voltage; }
    
    // Status
    bool isInitialized() const { return initialized; }
    uint16_t getErrorCount() const { return errorCount; }
    bool hasRecentData() const { return (millis() - lastDataUpdate) < 2000; }  // Data received within 2 sec
    
    // Diagnostic
    bool runLoopbackTest();  // Self-test: sends message to itself
    
private:
    MCP_CAN can;
    bool initialized;
    uint16_t errorCount;
    unsigned long lastDataUpdate;  // Track when data was last received
    
    // Vehicle data - Core Performance
    volatile uint16_t currentRPM;
    volatile uint8_t vehicleSpeed;
    volatile uint8_t throttlePosition;
    volatile uint8_t calculatedLoad;
    
    // Vehicle data - Engine Health
    volatile int8_t coolantTemp;
    volatile int8_t intakeTemp;
    volatile uint8_t barometric;
    
    // Vehicle data - Tuning
    volatile int8_t timingAdvance;
    volatile uint16_t mafRate;
    volatile int8_t shortFuelTrim;
    volatile int8_t longFuelTrim;
    volatile float o2Voltage;
    
    // OBD-II fallback
    unsigned long lastOBDRequest;
    uint8_t currentPidIndex;
    void requestOBDData(uint8_t pid);
    void cycleOBDRequests();
    
    // Parsing
    void parseMazdaCANFrame(unsigned long rxId, unsigned char len, unsigned char* rxBuf);
    void parseOBDResponse(unsigned long rxId, unsigned char len, unsigned char* rxBuf);
};

#endif // CAN_HANDLER_H
