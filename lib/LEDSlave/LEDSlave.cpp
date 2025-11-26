#include "LEDSlave.h"

// ============================================================================
// LED Slave Communication Implementation
// ============================================================================
// Uses TX pin (D1) for one-way communication to slave Arduino
// Simple bit-banging at 9600 baud to avoid conflicts with USB Serial
// ============================================================================

#define TX_PIN 1
#define BAUD_DELAY_US 104  // 1000000 / 9600 ≈ 104 microseconds per bit

LEDSlave::LEDSlave() : lastRPM(0), lastSpeed(1) {}

void LEDSlave::begin() {
    // Configure TX pin as output
    pinMode(TX_PIN, OUTPUT);
    digitalWrite(TX_PIN, HIGH);  // Idle state is HIGH for UART
    delay(100);
    clear();
}

// Software UART transmit function (9600 baud, 8N1)
void LEDSlave::sendByte(uint8_t byte) {
    // Start bit (LOW)
    digitalWrite(TX_PIN, LOW);
    delayMicroseconds(BAUD_DELAY_US);
    
    // 8 data bits (LSB first)
    for (uint8_t i = 0; i < 8; i++) {
        digitalWrite(TX_PIN, (byte & (1 << i)) ? HIGH : LOW);
        delayMicroseconds(BAUD_DELAY_US);
    }
    
    // Stop bit (HIGH)
    digitalWrite(TX_PIN, HIGH);
    delayMicroseconds(BAUD_DELAY_US);
}

void LEDSlave::sendCommand(const char* cmd) {
    // Send each character
    while (*cmd) {
        sendByte(*cmd);
        cmd++;
    }
    // Send newline
    sendByte('\n');
    delayMicroseconds(BAUD_DELAY_US * 2);  // Extra delay for stability
}

void LEDSlave::updateRPM(uint16_t rpm) {
    updateRPM(rpm, 1);  // Default: assume moving
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
    sendCommand("ERR");
}

void LEDSlave::clear() {
    sendCommand("CLR");
    lastRPM = 0;
    lastSpeed = 0;
}

void LEDSlave::setBrightness(uint8_t brightness) {
    char cmd[16];
    sprintf(cmd, "BRT:%u", brightness);
    sendCommand(cmd);
}
