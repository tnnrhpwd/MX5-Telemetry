#ifndef LED_SLAVE_H
#define LED_SLAVE_H

#include <Arduino.h>

// ============================================================================
// LED Slave Communication Module
// ============================================================================
// Sends simple commands to external LED controller Arduino via bit-bang serial
// Uses pin D6 for TX to Slave Arduino's D2 (SoftwareSerial RX)
// ============================================================================

class LEDSlave {
public:
    LEDSlave();
    
    void begin();
    void updateRPM(uint16_t rpm);
    void updateRPM(uint16_t rpm, uint16_t speed_kmh);
    void updateRPMError();
    void updateRPMRainbow();  // Rainbow pattern for error display
    void clear();
    void setBrightness(uint8_t brightness);
    
private:
    void sendCommand(const char* cmd);
    void sendByte(uint8_t byte);
    uint16_t lastRPM;
    uint16_t lastSpeed;
    bool lastError;    // Track error state to avoid spamming
    bool initialized;
    unsigned long lastKeepalive;  // Track last send for keep-alive
};

#endif // LED_SLAVE_H
