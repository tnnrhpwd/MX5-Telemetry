#include "LEDSlave.h"
#include <Arduino.h>
#include <config.h>

// ============================================================================
// LED Slave Communication Implementation
// ============================================================================
// Uses bit-bang serial on D6 at 9600 baud to communicate with Slave Arduino
// Slave Arduino listens on SoftwareSerial D2 at 9600 baud
// ============================================================================

// Bit-bang timing for 1200 baud (very slow = maximum reliability)
// 1,000,000 us / 1200 baud = 833.33 us per bit
#define BIT_DELAY_US 833

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

void LEDSlave::sendByteRaw(uint8_t byte) {
    // Bit-bang 8N1 serial: start bit (LOW), 8 data bits (LSB first), stop bit (HIGH)
    // NOTE: Caller must disable interrupts before calling this!
    
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
    
    // Stop bit (held for 2 bit periods)
    TX_HIGH();
    delayMicroseconds(BIT_DELAY_US);
    delayMicroseconds(BIT_DELAY_US);
}

void LEDSlave::sendByte(uint8_t byte) {
    noInterrupts();
    sendByteRaw(byte);
    interrupts();
}

void LEDSlave::sendCommand(const char* cmd) {
    if (!initialized) return;
    
    // Ensure line is HIGH and stable before starting
    TX_HIGH();
    delay(2);  // 2ms settling time (interrupts OK here)
    
    // Disable interrupts for ENTIRE transmission to prevent timing glitches
    noInterrupts();
    
    // Send start-of-message marker
    sendByteRaw('!');
    
    // Small gap after marker (in bit periods, not ms)
    delayMicroseconds(BIT_DELAY_US * 4);
    
    // Send each character
    while (*cmd) {
        sendByteRaw(*cmd++);
        delayMicroseconds(BIT_DELAY_US * 2);  // Gap between bytes
    }
    sendByteRaw('\n');  // End with newline
    
    interrupts();  // Re-enable interrupts after full transmission
    
    delay(1);  // 1ms cooldown after command
}

void LEDSlave::updateRPM(uint16_t rpm) {
    updateRPM(rpm, 0);  // Speed parameter is no longer used for LED state
}

void LEDSlave::updateRPM(uint16_t rpm, uint16_t speed_kmh) {
    // Clear error state when receiving valid RPM data
    lastError = false;
    
    // Always send RPM for responsive LEDs (removed caching that caused 3-second delays)
    char cmd[8];
    cmd[0] = 'R';  // Short prefix: R1234 instead of RPM:1234
    itoa(rpm, cmd + 1, 10);
    sendCommand(cmd);
    lastRPM = rpm;
    
    // Send speed if changed (no keep-alive needed, RPM already sent)
    if (speed_kmh != lastSpeed) {
        char cmd[8];
        cmd[0] = 'S';  // Short prefix: S123 instead of SPD:123
        itoa(speed_kmh, cmd + 1, 10);
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
    sendCommand("W");  // W = Rainbow/Wave mode (R is now RPM prefix)
}

void LEDSlave::clear() {
    sendCommand("C");  // Short: C instead of CLR
    // Set to invalid values so next updateRPM always sends
    lastRPM = 65535;
    lastSpeed = 65535;
    lastError = false;
}

void LEDSlave::setBrightness(uint8_t brightness) {
    char cmd[6];
    cmd[0] = 'B';  // Short prefix: B255 instead of BRT:255
    itoa(brightness, cmd + 1, 10);
    sendCommand(cmd);
}
