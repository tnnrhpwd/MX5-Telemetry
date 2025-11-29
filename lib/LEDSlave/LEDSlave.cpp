#include "LEDSlave.h"
#include <Arduino.h>
#include <config.h>

// ============================================================================
// LED Slave Communication Implementation
// ============================================================================
// Uses bit-bang serial on D6 at 9600 baud to communicate with Slave Arduino
// Slave Arduino listens on SoftwareSerial D2 at 9600 baud
// ============================================================================

// Bit-bang timing for 9600 baud (104 microseconds per bit)
#define BIT_DELAY_US 104

LEDSlave::LEDSlave() : lastRPM(65535), lastSpeed(65535), initialized(false) {}

void LEDSlave::begin() {
    // Configure D6 as output for bit-bang TX
    pinMode(SLAVE_TX_PIN, OUTPUT);
    digitalWrite(SLAVE_TX_PIN, HIGH);  // Idle high (like UART)
    initialized = true;
    delay(100);
    clear();
}

void LEDSlave::sendByte(uint8_t byte) {
    // Bit-bang 8N1 serial: start bit (LOW), 8 data bits (LSB first), stop bit (HIGH)
    noInterrupts();  // Disable interrupts for precise timing
    
    // Start bit
    digitalWrite(SLAVE_TX_PIN, LOW);
    delayMicroseconds(BIT_DELAY_US);
    
    // 8 data bits, LSB first
    for (uint8_t i = 0; i < 8; i++) {
        digitalWrite(SLAVE_TX_PIN, (byte & (1 << i)) ? HIGH : LOW);
        delayMicroseconds(BIT_DELAY_US);
    }
    
    // Stop bit
    digitalWrite(SLAVE_TX_PIN, HIGH);
    delayMicroseconds(BIT_DELAY_US);
    
    interrupts();  // Re-enable interrupts
}

void LEDSlave::sendCommand(const char* cmd) {
    if (!initialized) return;
    
    // Log to USB serial for debugging
    Serial.print(F("LED->Slave: "));
    Serial.println(cmd);
    
    // Send each character via bit-bang to Slave
    while (*cmd) {
        sendByte(*cmd++);
    }
    sendByte('\n');  // End with newline
}

void LEDSlave::updateRPM(uint16_t rpm) {
    updateRPM(rpm, 0);  // Default: assume stationary (idle animation)
}

void LEDSlave::updateRPM(uint16_t rpm, uint16_t speed_kmh) {
    // Only send if changed to reduce serial traffic
    if (rpm != lastRPM) {
        char cmd[16];
        sprintf(cmd, "RPM:%u", rpm);
        sendCommand(cmd);
        lastRPM = rpm;
    }
    
    if (speed_kmh != lastSpeed) {
        char cmd[16];
        sprintf(cmd, "SPD:%u", speed_kmh);
        sendCommand(cmd);
        lastSpeed = speed_kmh;
    }
}

void LEDSlave::updateRPMError() {
    sendCommand("E");  // Single char: Error mode
}

void LEDSlave::updateRPMRainbow() {
    sendCommand("R");  // Single char: Rainbow mode
}

void LEDSlave::clear() {
    sendCommand("CLR");
    // Set to invalid values so next updateRPM always sends
    lastRPM = 65535;
    lastSpeed = 65535;
}

void LEDSlave::setBrightness(uint8_t brightness) {
    char cmd[16];
    sprintf(cmd, "BRT:%u", brightness);
    sendCommand(cmd);
}
