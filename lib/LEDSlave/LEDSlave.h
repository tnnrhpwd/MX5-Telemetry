#ifndef LED_SLAVE_H
#define LED_SLAVE_H

#include <Arduino.h>

// ============================================================================
// LED Slave Communication Module
// ============================================================================
// Sends simple commands to external LED controller Arduino via Serial (TX)
// ============================================================================

class LEDSlave {
public:
    LEDSlave();
    
    void begin();
    void updateRPM(uint16_t rpm);
    void updateRPM(uint16_t rpm, uint16_t speed_kmh);
    void updateRPMError();
    void clear();
    void setBrightness(uint8_t brightness);
    
private:
    void sendCommand(const char* cmd);
    void sendByte(uint8_t byte);  // Software UART transmit
    uint16_t lastRPM;
    uint16_t lastSpeed;
};

#endif // LED_SLAVE_H
