#include "LEDSlave.h"
#include <Arduino.h>
#include <config.h>

// ============================================================================
// LED Slave Communication Implementation
// ============================================================================
// Uses bit-bang serial on D6 at 9600 baud to communicate with Slave Arduino
// Slave Arduino listens on SoftwareSerial D2 at 9600 baud
// ============================================================================

// Bit-bang timing for 9600 baud
// 1,000,000 us / 9600 baud = 104.166... us per bit
// Using direct port manipulation to reduce overhead and improve timing accuracy
// Increased slightly to 104us for better compatibility with SoftwareSerial
#define BIT_DELAY_US 104

// Direct port manipulation for D6 (PORTD bit 6) - much faster than digitalWrite
#define TX_HIGH()  (PORTD |= (1 << 6))
#define TX_LOW()   (PORTD &= ~(1 << 6))

LEDSlave::LEDSlave() : lastRPM(65535), lastSpeed(65535), lastError(false), initialized(false), lastKeepalive(0) {}

void LEDSlave::begin() {
    // Configure D6 as output for bit-bang TX
    pinMode(SLAVE_TX_PIN, OUTPUT);
    TX_HIGH();  // Idle high (like UART)
    initialized = true;
    delay(100);
    clear();
}

void LEDSlave::sendByte(uint8_t byte) {
    // Bit-bang 8N1 serial: start bit (LOW), 8 data bits (LSB first), stop bit (HIGH)
    noInterrupts();  // Disable interrupts for precise timing
    
    // Start bit
    TX_LOW();
    delayMicroseconds(BIT_DELAY_US);
    
    // 8 data bits, LSB first - using direct port manipulation
    for (uint8_t i = 0; i < 8; i++) {
        if (byte & (1 << i)) {
            TX_HIGH();
        } else {
            TX_LOW();
        }
        delayMicroseconds(BIT_DELAY_US);
    }
    
    // Stop bit
    TX_HIGH();
    delayMicroseconds(BIT_DELAY_US);
    
    // Extra stop bit time for reliability
    delayMicroseconds(BIT_DELAY_US);
    
    interrupts();  // Re-enable interrupts
}

void LEDSlave::sendCommand(const char* cmd) {
    if (!initialized) return;
    
    // Small delay before transmission to let any previous byte settle
    delayMicroseconds(500);
    
    // Send each character via bit-bang to Slave
    // Add delay between bytes for receiver's SoftwareSerial to process
    while (*cmd) {
        sendByte(*cmd++);
        delayMicroseconds(500);  // Increased inter-byte gap for SoftwareSerial reliability
    }
    sendByte('\n');  // End with newline
    
    // Small delay after transmission
    delayMicroseconds(500);
}

void LEDSlave::updateRPM(uint16_t rpm) {
    updateRPM(rpm, 0);  // Default: assume stationary (idle animation)
}

void LEDSlave::updateRPM(uint16_t rpm, uint16_t speed_kmh) {
    // Clear error state when receiving valid RPM data
    lastError = false;
    
    unsigned long now = millis();
    bool needsKeepalive = (now - lastKeepalive) >= 3000;  // Keep-alive every 3 seconds
    
    // Send RPM if changed OR keep-alive needed
    if (rpm != lastRPM || needsKeepalive) {
        char cmd[12];
        // Manual uint16 to string (avoids sprintf, saves ~500 bytes flash)
        strcpy(cmd, "RPM:");
        itoa(rpm, cmd + 4, 10);
        sendCommand(cmd);
        lastRPM = rpm;
        lastKeepalive = now;
    }
    
    // Send speed if changed (no keep-alive needed, RPM already sent)
    if (speed_kmh != lastSpeed) {
        char cmd[12];
        strcpy(cmd, "SPD:");
        itoa(speed_kmh, cmd + 4, 10);
        sendCommand(cmd);
        lastSpeed = speed_kmh;
    }
}

void LEDSlave::updateRPMError() {
    // Only send error command once when entering error state
    if (!lastError) {
        sendCommand("E");  // Single char: Error mode
        lastError = true;
    }
}

void LEDSlave::updateRPMRainbow() {
    sendCommand("R");  // Single char: Rainbow mode
}

void LEDSlave::clear() {
    sendCommand("CLR");
    // Set to invalid values so next updateRPM always sends
    lastRPM = 65535;
    lastSpeed = 65535;
    lastError = false;
}

void LEDSlave::setBrightness(uint8_t brightness) {
    char cmd[10];
    strcpy(cmd, "BRT:");
    itoa(brightness, cmd + 4, 10);
    sendCommand(cmd);
}
