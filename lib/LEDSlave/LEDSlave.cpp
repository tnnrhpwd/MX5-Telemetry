#include "LEDSlave.h"
#include <Arduino.h>

// ============================================================================
// LED Slave Communication Implementation
// ============================================================================
// Uses hardware Serial1 (TX on D1) for communication to slave Arduino
// Note: This conflicts with USB Serial debugging, but Arduino Nano only has one hardware UART
// We use TX1 with diode isolation to slave's SoftwareSerial RX on D2
// ============================================================================

// Use HardwareSerial alias for Serial (TX1/D1, RX0/D0)
// On Arduino Nano, Serial is the only UART and handles both USB and TX1
#define SLAVE_SERIAL Serial

LEDSlave::LEDSlave() : lastRPM(0), lastSpeed(1), initialized(false) {}

void LEDSlave::begin() {
    // Serial is already initialized in main setup at 115200 for USB
    // We can't change baud rate without affecting USB communication
    // Solution: Use bit-banging on TX1 pin directly
    initialized = true;
    delay(100);
    clear();
}

// Software UART transmit function (9600 baud, 8N1) on TX1 pin
void LEDSlave::sendByte(uint8_t byte) {
    // Use hardware Serial at 9600 baud would conflict with USB
    // Keep bit-banging but ensure timing is correct
    
    #define TX_PIN 1
    #define BAUD_DELAY_US 104  // 1000000 / 9600 ≈ 104 microseconds
    
    noInterrupts();  // Disable interrupts for accurate timing
    
    // Start bit (LOW)
    pinMode(TX_PIN, OUTPUT);
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
    
    interrupts();  // Re-enable interrupts
}

void LEDSlave::sendCommand(const char* cmd) {
    if (!initialized) return;
    
    // Send each character
    while (*cmd) {
        sendByte(*cmd);
        cmd++;
    }
    // Send newline
    sendByte('\n');
    delay(2);  // Small delay for slave to process
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
    sendCommand("E");  // Single char: Error mode
}

void LEDSlave::updateRPMRainbow() {
    sendCommand("R");  // Single char: Rainbow mode
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
