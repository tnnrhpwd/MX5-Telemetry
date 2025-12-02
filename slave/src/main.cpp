/*
 * ============================================================================
 * MX5-Telemetry LED Slave Controller
 * ============================================================================
 * 
 * Dedicated LED strip controller that receives commands via SoftwareSerial
 * from the master Arduino (logger).
 * 
 * HARDWARE:
 * - Arduino Nano #2
 * - WS2812B LED Strip on Pin D5
 * - D2 (RX via SoftwareSerial) ← TX from Master Arduino (Pin 1) via diode
 * - Shares GND with Master Arduino
 * 
 * SERIAL COMMANDS (1200 baud from Master via D2):
 * - RPM:xxxx     Set RPM and update display (e.g., RPM:3500)
 * - SPD:xxx      Set speed in km/h (e.g., SPD:60)
 * - ERR          Show error state (red pepper animation)
 * - RBW          Show rainbow error pattern (for USB-connected mode)
 * - CLR          Clear all LEDs
 * - BRT:xxx      Set brightness 0-255 (e.g., BRT:128)
 * 
 * VERSION: 2.1.0 - Uses SoftwareSerial on D2 to avoid upload interference
 * ============================================================================
 */

#include <Arduino.h>
#include <SPI.h>
#include <mcp_can.h>
#include <SoftwareSerial.h>
#include <Adafruit_NeoPixel.h>
#include "LEDStates.h"

// ============================================================================
// CONFIGURATION  
// ============================================================================

#define LED_DATA_PIN        5       // D5 on Arduino #2
#define SERIAL_RX_PIN       2       // D2 for SoftwareSerial RX (from master D6)
#define HAPTIC_PIN          3       // D3 for haptic motor (vibration feedback)
#define BRIGHTNESS_POT_PIN  A6      // A6 for brightness potentiometer (B10K-B100K)
#define CAN_CS_PIN          10      // MCP2515 Chip Select (SPI) - same as Master
#define CAN_INT_PIN         7       // MCP2515 Interrupt Pin - DIRECTLY connected to D7
#define LED_COUNT           20      // Number of LEDs in strip (adjust to your strip)
#define SLAVE_SERIAL_BAUD   1200    // Baud rate - very slow for maximum reliability
#define ENABLE_HAPTIC       false   // DISABLED for debugging - set true to enable haptic feedback
#define ENABLE_BRIGHTNESS_POT true  // Enable brightness potentiometer on A6
#define ENABLE_CAN_TEST     false   // DISABLED - set true only for bench testing with 2 Arduinos
#define MIN_VOLTAGE_FOR_HAPTIC  4.7 // Minimum voltage (V) to enable haptic on startup

// ============================================================================
// GLOBAL OBJECTS
// ============================================================================

SoftwareSerial slaveSerial(SERIAL_RX_PIN, -1);  // RX on D2, no TX needed
Adafruit_NeoPixel strip(LED_COUNT, LED_DATA_PIN, NEO_GRB + NEO_KHZ800);

#if ENABLE_CAN_TEST
MCP_CAN canBus(CAN_CS_PIN);
bool canInitialized = false;
bool canTestMode = false;  // When true, slave listens for CAN and responds
unsigned long lastCanCheck = 0;
unsigned long canMsgCount = 0;
#endif

// ============================================================================
// STATE VARIABLES
// ============================================================================

uint16_t currentRPM = 0;
uint16_t currentSpeed = 0;
bool errorMode = false;
bool rainbowMode = false;  // Track if USB is connected
bool usbTestMode = false;  // USB test mode - extends timeout for LED testing
unsigned long lastAnimationUpdate = 0;
uint16_t pepperPosition = 0;  // Changed to uint16_t to handle 0-255 range for rainbow
bool flashState = false;
char inputBuffer[16];
uint8_t bufferIndex = 0;
bool hapticActive = false;
unsigned long hapticStartTime = 0;
uint16_t hapticDuration = 0;
uint8_t currentBrightness = 255;     // Current brightness from potentiometer
unsigned long lastBrightnessRead = 0; // Debounce brightness reads
unsigned long lastCommandTime = 0;          // Track when last command was received
unsigned long lastUSBActivity = 0;          // Track when last USB command was received
bool debugMode = false;                     // Only enable verbose serial when USB recently active
#define MASTER_TIMEOUT_MS 5000              // Enter error mode if no command for 5 seconds
#define USB_TEST_TIMEOUT_MS 30000           // Extended timeout in USB test mode (30 seconds)
#define INITIAL_WAIT_MS 3000                // Wait for master after startup before showing error
#define DEBUG_MODE_TIMEOUT_MS 10000         // Disable debug output 10 seconds after last USB command

// ============================================================================
// FORWARD DECLARATIONS
// ============================================================================

void triggerHaptic(uint16_t durationMs);
void updateHaptic();
float readVcc();

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

void pepperAnimation(uint8_t r, uint8_t g, uint8_t b, uint16_t delay, uint16_t holdTime) {
    unsigned long currentTime = millis();
    
    if (currentTime - lastAnimationUpdate >= delay) {
        lastAnimationUpdate = currentTime;
        pepperPosition++;
        
        if (pepperPosition >= (LED_COUNT / 2) + (holdTime / delay)) {
            pepperPosition = 0;
        }
    }
    
    for (int i = 0; i < LED_COUNT; i++) {
        int distanceFromEdge = (i < LED_COUNT / 2) ? i : LED_COUNT - 1 - i;
        
        if (distanceFromEdge <= pepperPosition && pepperPosition < (LED_COUNT / 2)) {
            // Calculate how long this LED has been lit (0 = newest, higher = older)
            int ageOfLED = pepperPosition - distanceFromEdge;
            
            // Newest LED is full brightness, older LEDs fade
            // Max fade over ~8 steps to create visible gradient
            uint8_t brightness = 255;
            if (ageOfLED > 0) {
                // Exponential fade looks better than linear
                brightness = 255 - constrain(ageOfLED * 28, 0, 200);  // Fade to ~20% min brightness
            }
            
            // Apply brightness to color
            uint8_t dimR = (r * brightness) / 255;
            uint8_t dimG = (g * brightness) / 255;
            uint8_t dimB = (b * brightness) / 255;
            
            strip.setPixelColor(i, strip.Color(dimR, dimG, dimB));
        } else {
            strip.setPixelColor(i, 0);
        }
    }
    
    strip.show();
}

void solidFill(uint8_t r, uint8_t g, uint8_t b) {
    for (int i = 0; i < LED_COUNT; i++) {
        strip.setPixelColor(i, strip.Color(r, g, b));
    }
    strip.show();
}

void drawMirroredBar(uint8_t ledsPerSide, uint8_t r, uint8_t g, uint8_t b) {
    for (int i = 0; i < LED_COUNT; i++) {
        if (i < ledsPerSide || i >= (LED_COUNT - ledsPerSide)) {
            strip.setPixelColor(i, strip.Color(r, g, b));
        } else {
            strip.setPixelColor(i, 0);
        }
    }
    strip.show();
}

uint8_t getPulseBrightness(uint16_t period, uint8_t minBright, uint8_t maxBright) {
    unsigned long currentTime = millis();
    float phase = (float)(currentTime % period) / (float)period;
    float brightness = minBright + (maxBright - minBright) * (0.5 + 0.5 * sin(phase * 2.0 * PI));
    return (uint8_t)brightness;
}

uint8_t scaleColor(uint8_t color, uint8_t brightness) {
    return (uint16_t)color * brightness / 255;
}

// ============================================================================
// LED STATE FUNCTIONS
// ============================================================================

void idleNeutralState() {
    pepperAnimation(STATE_0_COLOR_R, STATE_0_COLOR_G, STATE_0_COLOR_B, 
                    STATE_0_PEPPER_DELAY, STATE_0_HOLD_TIME);
}

// Helper function to interpolate between two colors
void getInterpolatedColor(uint16_t rpm, uint16_t rpmMin, uint16_t rpmMax,
                          uint8_t r1, uint8_t g1, uint8_t b1,
                          uint8_t r2, uint8_t g2, uint8_t b2,
                          uint8_t* rOut, uint8_t* gOut, uint8_t* bOut) {
    if (rpm <= rpmMin) {
        *rOut = r1; *gOut = g1; *bOut = b1;
        return;
    }
    if (rpm >= rpmMax) {
        *rOut = r2; *gOut = g2; *bOut = b2;
        return;
    }
    // Linear interpolation
    uint16_t range = rpmMax - rpmMin;
    uint16_t pos = rpm - rpmMin;
    *rOut = r1 + ((int16_t)(r2 - r1) * pos / range);
    *gOut = g1 + ((int16_t)(g2 - g1) * pos / range);
    *bOut = b1 + ((int16_t)(b2 - b1) * pos / range);
}

// Get color for a specific RPM in the normal driving zone
// Smooth gradient: Blue (2000-2500) -> Green (2500-4000) -> Yellow (4000-4500)
void getEfficiencyColor(uint16_t rpm, uint8_t* r, uint8_t* g, uint8_t* b) {
    if (rpm <= EFFICIENCY_BLUE_END) {
        // Blue zone (best MPG): 2000-2500 RPM
        // Interpolate from pure blue to green-blue
        getInterpolatedColor(rpm, NORMAL_RPM_MIN, EFFICIENCY_BLUE_END,
                            BLUE_COLOR_R, BLUE_COLOR_G, BLUE_COLOR_B,
                            GREEN_COLOR_R, GREEN_COLOR_G, GREEN_COLOR_B,
                            r, g, b);
    } else if (rpm <= EFFICIENCY_GREEN_END) {
        // Green zone (best thermal efficiency): 2500-4000 RPM
        // Interpolate from green to yellow-green
        getInterpolatedColor(rpm, EFFICIENCY_BLUE_END, EFFICIENCY_GREEN_END,
                            GREEN_COLOR_R, GREEN_COLOR_G, GREEN_COLOR_B,
                            YELLOW_COLOR_R, YELLOW_COLOR_G, YELLOW_COLOR_B,
                            r, g, b);
    } else {
        // Yellow zone (approaching high RPM): 4000-4500 RPM
        // Stay yellow
        *r = YELLOW_COLOR_R;
        *g = YELLOW_COLOR_G;
        *b = YELLOW_COLOR_B;
    }
}

// Calculate LED position for efficiency zones with emphasis on MPG and thermal zones
// Returns 0 to maxLeds based on RPM, with non-linear mapping:
//   LEDs 0-2 (3 LEDs): MPG zone 2000-2500 RPM (30% of LEDs for 20% of range)
//   LEDs 3-6 (4 LEDs): Thermal zone 2500-4000 RPM (40% of LEDs for 60% of range)  
//   LEDs 7-9 (3 LEDs): Yellow zone 4000-4500 RPM (30% of LEDs for 20% of range)
uint8_t getEfficiencyLedCount(uint16_t rpm, uint8_t maxLeds) {
    // MPG zone: 2000-2500 RPM → LEDs 0-2 (first 30% of LEDs)
    if (rpm <= EFFICIENCY_BLUE_END) {
        uint16_t rpmInZone = rpm - NORMAL_RPM_MIN;  // 0 to 500
        uint16_t zoneRange = EFFICIENCY_BLUE_END - NORMAL_RPM_MIN;  // 500
        uint8_t zoneLeds = (maxLeds * 3) / 10;  // 30% = 3 LEDs per side
        return map(rpmInZone, 0, zoneRange, 0, zoneLeds);
    }
    // Thermal zone: 2500-4000 RPM → LEDs 3-6 (next 40% of LEDs)
    else if (rpm <= EFFICIENCY_GREEN_END) {
        uint16_t rpmInZone = rpm - EFFICIENCY_BLUE_END;  // 0 to 1500
        uint16_t zoneRange = EFFICIENCY_GREEN_END - EFFICIENCY_BLUE_END;  // 1500
        uint8_t mpgLeds = (maxLeds * 3) / 10;  // 3 LEDs from MPG zone
        uint8_t zoneLeds = (maxLeds * 4) / 10;  // 40% = 4 LEDs for thermal
        return mpgLeds + map(rpmInZone, 0, zoneRange, 0, zoneLeds);
    }
    // Yellow zone: 4000-4500 RPM → LEDs 7-9 (last 30% of LEDs)
    else {
        uint16_t rpmInZone = rpm - EFFICIENCY_GREEN_END;  // 0 to 500
        uint16_t zoneRange = NORMAL_RPM_MAX - EFFICIENCY_GREEN_END;  // 500
        uint8_t mpgLeds = (maxLeds * 3) / 10;  // 3 LEDs from MPG zone
        uint8_t thermalLeds = (maxLeds * 4) / 10;  // 4 LEDs from thermal zone
        uint8_t zoneLeds = maxLeds - mpgLeds - thermalLeds;  // remaining ~3 LEDs
        return mpgLeds + thermalLeds + map(rpmInZone, 0, zoneRange, 0, zoneLeds);
    }
}

// Normal driving state with smooth blue-green-yellow gradient (2000-4500 RPM)
// Uses non-linear LED mapping to emphasize MPG and thermal efficiency zones
void normalDrivingState(uint16_t rpm) {
    // Calculate LEDs per side using non-linear efficiency mapping
    uint8_t ledsPerSide = getEfficiencyLedCount(rpm, LED_COUNT / 2);
    
    // Get the color for current RPM
    uint8_t r, g, b;
    getEfficiencyColor(rpm, &r, &g, &b);
    
    // Draw the bar with the interpolated color
    for (int i = 0; i < LED_COUNT; i++) {
        bool isLit;
        
        if (i < LED_COUNT / 2) {
            // Left side
            isLit = (i < ledsPerSide);
        } else {
            // Right side
            isLit = (i >= (LED_COUNT - ledsPerSide));
        }
        
        if (isLit) {
            strip.setPixelColor(i, strip.Color(r, g, b));
        } else {
            strip.setPixelColor(i, 0);
        }
    }
    strip.show();
}

void stallDangerState(uint16_t rpm) {
    // Progressive bar - INVERTED: more LEDs = lower RPM = more danger
    // At RPM=0: full bar (maximum danger)
    // At RPM=1999: minimal bar (almost safe)
    uint16_t range = STATE_2_RPM_MAX - STATE_2_RPM_MIN;  // 1999 - 0 = 1999
    uint16_t rpmInRange = rpm - STATE_2_RPM_MIN;         // rpm - 0 = rpm
    
    // Invert: at rpm=0 we want max LEDs, at rpm=1999 we want min LEDs
    uint8_t ledsPerSide = map(range - rpmInRange, 0, range, 0, LED_COUNT / 2);
    
    drawMirroredBar(ledsPerSide, STATE_2_COLOR_R, STATE_2_COLOR_G, STATE_2_COLOR_B);
}

void highRPMShiftState(uint16_t rpm) {
    unsigned long currentTime = millis();
    uint16_t range = STATE_4_RPM_MAX - STATE_4_RPM_MIN;
    uint16_t rpmInRange = rpm - STATE_4_RPM_MIN;
    uint8_t ledsPerSide = LED_COUNT / 2 - 3 + map(rpmInRange, 0, range, 0, 3);
    
    uint16_t flashSpeed = map(rpmInRange, 0, range, STATE_4_FLASH_SPEED_MIN, STATE_4_FLASH_SPEED_MAX);
    
    if (currentTime - lastAnimationUpdate >= flashSpeed) {
        lastAnimationUpdate = currentTime;
        flashState = !flashState;
    }
    
    for (int i = 0; i < LED_COUNT; i++) {
        if (i < ledsPerSide || i >= (LED_COUNT - ledsPerSide)) {
            strip.setPixelColor(i, strip.Color(STATE_4_BAR_R, STATE_4_BAR_G, STATE_4_BAR_B));
        } else {
            if (flashState) {
                strip.setPixelColor(i, strip.Color(STATE_4_FLASH_2_R, STATE_4_FLASH_2_G, STATE_4_FLASH_2_B));
            } else {
                strip.setPixelColor(i, strip.Color(STATE_4_FLASH_1_R, STATE_4_FLASH_1_G, STATE_4_FLASH_1_B));
            }
        }
    }
    strip.show();
}

void revLimitState() {
    solidFill(STATE_5_COLOR_R, STATE_5_COLOR_G, STATE_5_COLOR_B);
    
    // Trigger haptic pulse when hitting rev limit
    #if ENABLE_HAPTIC
    static unsigned long lastHapticPulse = 0;
    if (millis() - lastHapticPulse >= 500) {  // Pulse every 500ms
        triggerHaptic(100);  // Short 100ms pulse
        lastHapticPulse = millis();
    }
    #endif
}

// Read Arduino Vcc (5V rail voltage) using internal 1.1V reference
// Returns voltage in volts (e.g., 4.85)
float readVcc() {
    // Read 1.1V reference against AVcc
    // Set the reference to Vcc and the measurement to the internal 1.1V reference
    #if defined(__AVR_ATmega32U4__) || defined(__AVR_ATmega1280__) || defined(__AVR_ATmega2560__)
        ADMUX = _BV(REFS0) | _BV(MUX4) | _BV(MUX3) | _BV(MUX2) | _BV(MUX1);
    #elif defined (__AVR_ATtiny24__) || defined(__AVR_ATtiny44__) || defined(__AVR_ATtiny84__)
        ADMUX = _BV(MUX5) | _BV(MUX0);
    #elif defined (__AVR_ATtiny25__) || defined(__AVR_ATtiny45__) || defined(__AVR_ATtiny85__)
        ADMUX = _BV(MUX3) | _BV(MUX2);
    #else
        // ATmega328P (Arduino Nano/Uno)
        ADMUX = _BV(REFS0) | _BV(MUX3) | _BV(MUX2) | _BV(MUX1);
    #endif
    
    delay(2); // Wait for Vref to settle
    ADCSRA |= _BV(ADSC); // Start conversion
    while (bit_is_set(ADCSRA, ADSC)); // Wait for conversion to complete
    
    uint8_t low = ADCL; // Read ADCL first
    uint8_t high = ADCH; // Then ADCH
    
    long result = (high << 8) | low;
    
    // Calculate Vcc (in mV); 1125300 = 1.1*1023*1000
    result = 1125300L / result; // Calculate Vcc (in mV)
    
    return result / 1000.0; // Convert to volts
}

void triggerHaptic(uint16_t durationMs) {
    #if ENABLE_HAPTIC
    hapticActive = true;
    hapticStartTime = millis();
    hapticDuration = durationMs;
    analogWrite(HAPTIC_PIN, 51);  // 20% power (51/255 = 0.2)
    #endif
}

void updateHaptic() {
    #if ENABLE_HAPTIC
    if (hapticActive && (millis() - hapticStartTime >= hapticDuration)) {
        analogWrite(HAPTIC_PIN, 0);  // Turn off
        hapticActive = false;
    }
    #endif
}

// Read brightness from potentiometer and apply to LED strip
void updateBrightness() {
    #if ENABLE_BRIGHTNESS_POT
    unsigned long currentTime = millis();
    
    // Only read every 50ms to avoid jitter and save CPU
    if (currentTime - lastBrightnessRead >= 50) {
        lastBrightnessRead = currentTime;
        
        // Read potentiometer (0-1023), INVERT (1023-value), map to brightness (0-255)
        // Inversion: turning clockwise now increases brightness
        int potValue = 1023 - analogRead(BRIGHTNESS_POT_PIN);
        uint8_t newBrightness = map(potValue, 0, 1023, 0, 255);
        
        // Only update if brightness changed significantly (reduces flicker)
        if (abs((int)newBrightness - (int)currentBrightness) > 2) {
            currentBrightness = newBrightness;
            strip.setBrightness(currentBrightness);
            // Note: strip.show() will be called by the LED state functions
        }
    }
    #endif
}

void errorState() {
    pepperAnimation(ERROR_COLOR_R, ERROR_COLOR_G, ERROR_COLOR_B, 
                    ERROR_PEPPER_DELAY, ERROR_HOLD_TIME);
}

void rainbowErrorState() {
    unsigned long currentTime = millis();
    
    // Update at slower rate for more visible chase effect
    if (currentTime - lastAnimationUpdate >= 60) {  // Slowed down from 20ms to 60ms
        lastAnimationUpdate = currentTime;
        pepperPosition++;
        if (pepperPosition >= (LED_COUNT / 2) + 8) pepperPosition = 0;  // Reset after reaching center + tail length
    }
    
    // Rainbow comet/chase effect - chases from edges to center (mirrored)
    for (int i = 0; i < LED_COUNT; i++) {
        // Calculate distance from edge (mirrored from both ends)
        int distanceFromEdge = (i < LED_COUNT / 2) ? i : LED_COUNT - 1 - i;
        
        // Calculate distance from the comet head
        int distanceFromComet = distanceFromEdge - pepperPosition;
        
        // Comet head is at pepperPosition moving toward center
        if (distanceFromComet == 0 && pepperPosition < (LED_COUNT / 2)) {
            // Head - full brightness with rotating hue
            uint16_t hue = (pepperPosition * 2048) & 0xFFFF;
            uint32_t color = strip.gamma32(strip.ColorHSV(hue, 255, 255));
            strip.setPixelColor(i, color);
        } else if (distanceFromComet < 0 && distanceFromComet >= -6) {
            // Tail - same hue but fading brightness (trail behind the comet)
            uint16_t hue = (pepperPosition * 2048) & 0xFFFF;
            uint8_t brightness = 255 + (distanceFromComet * 40);  // Fade over 6 LEDs behind
            uint32_t color = strip.gamma32(strip.ColorHSV(hue, 255, brightness));
            strip.setPixelColor(i, color);
        } else {
            strip.setPixelColor(i, 0);  // Off
        }
    }
    strip.show();
}

void updateLEDDisplay() {
    if (errorMode) {
        // Show rainbow if explicitly commanded by master
        if (rainbowMode) {
            rainbowErrorState();
        } else {
            errorState();
        }
        return;
    }
    
    // State 5: Rev Limit (7200+ RPM) - HIGHEST PRIORITY
    if (currentRPM >= STATE_5_RPM_MIN) {
        revLimitState();
        return;
    }
    
    // State 4: High RPM Shift Warning (4501-7199 RPM)
    if (currentRPM >= STATE_4_RPM_MIN) {
        highRPMShiftState(currentRPM);
        return;
    }
    
    // Normal Driving: Efficiency Gradient (2000-4500 RPM)
    // Blue->Green->Yellow based on RPM - works at ANY speed
    if (currentRPM >= NORMAL_RPM_MIN) {
        normalDrivingState(currentRPM);
        return;
    }
    
    // Below 2000 RPM - behavior depends on speed:
    
    // Stall Danger: ONLY when moving (speed > 0) and RPM 0-1999
    // Progressive orange bar - more LEDs = lower RPM = more danger
    if (currentSpeed > STATE_0_SPEED_THRESHOLD) {
        stallDangerState(currentRPM);
        return;
    }
    
    // Idle State: Speed=0 AND RPM below 2000
    // White pepper animation when sitting still
    idleNeutralState();
}

// ============================================================================
// COMMAND PROCESSING
// ============================================================================

void processCommand(const char* cmd) {
    if (debugMode) {
        Serial.print("CMD: ");
        Serial.println(cmd);
    }
    
    // Commands from Master are prefixed with "LED:"
    // Strip the prefix if present
    if (strncmp(cmd, "LED:", 4) == 0) {
        cmd += 4;  // Skip "LED:" prefix
    }
    
    // RPM command: R followed by number (e.g., R1234)
    if (cmd[0] == 'R' && cmd[1] >= '0' && cmd[1] <= '9') {
        currentRPM = atoi(cmd + 1);
        errorMode = false;
        rainbowMode = false;
        if (debugMode) {
            Serial.print("RPM set to: ");
            Serial.println(currentRPM);
        }
    }
    // Speed command: S followed by number (e.g., S123)
    else if (cmd[0] == 'S' && cmd[1] >= '0' && cmd[1] <= '9') {
        currentSpeed = atoi(cmd + 1);
        if (debugMode) {
            Serial.print("Speed set to: ");
            Serial.println(currentSpeed);
        }
    }
    // Error mode command: E
    else if (strcmp(cmd, "E") == 0) {
        errorMode = true;
        rainbowMode = false;
        if (debugMode) Serial.println("Error mode ON");
    }
    // Rainbow/Wave mode command: W
    else if (strcmp(cmd, "W") == 0) {
        errorMode = true;
        rainbowMode = true;
        if (debugMode) Serial.println("Rainbow mode ON");
    }
    // Clear command: C
    else if (strcmp(cmd, "C") == 0) {
        strip.clear();
        strip.show();
        currentRPM = 0;
        currentSpeed = 0;
        errorMode = false;
        rainbowMode = false;
        if (debugMode) Serial.println("LEDs cleared");
    }
    // Brightness command: B followed by number (e.g., B255)
    else if (cmd[0] == 'B' && cmd[1] >= '0' && cmd[1] <= '9') {
        uint8_t brightness = atoi(cmd + 1);
        strip.setBrightness(brightness);
        if (debugMode) {
            Serial.print("Brightness set to: ");
            Serial.println(brightness);
        }
    }
    // Haptic command: V followed by number (e.g., V100)
    else if (cmd[0] == 'V' && cmd[1] >= '0' && cmd[1] <= '9') {
        uint16_t duration = atoi(cmd + 1);
        triggerHaptic(duration);
        if (debugMode) {
            Serial.print("Haptic triggered: ");
            Serial.print(duration);
            Serial.println("ms");
        }
    }
    // ========================================================================
    // CAN TEST COMMANDS
    // ========================================================================
    #if ENABLE_CAN_TEST
    // CAN: Enable CAN test mode
    else if (strcmp(cmd, "CAN") == 0) {
        if (canInitialized) {
            canTestMode = !canTestMode;
            Serial.print(F("CAN test mode: "));
            Serial.println(canTestMode ? F("ENABLED") : F("DISABLED"));
            if (canTestMode) {
                Serial.println(F("Listening for CAN messages from Master..."));
                Serial.println(F("Master should send 'C' command to transmit test"));
                canMsgCount = 0;
            }
        } else {
            Serial.println(F("CAN not initialized - check wiring"));
        }
    }
    // CANSTAT: Show CAN status
    else if (strcmp(cmd, "CANSTAT") == 0) {
        Serial.println(F("\n=== SLAVE CAN STATUS ==="));
        Serial.print(F("Initialized: "));
        Serial.println(canInitialized ? F("YES") : F("NO"));
        Serial.print(F("Test Mode: "));
        Serial.println(canTestMode ? F("ENABLED") : F("DISABLED"));
        Serial.print(F("Messages received: "));
        Serial.println(canMsgCount);
        if (canInitialized) {
            byte errFlag = canBus.getError();
            Serial.print(F("Error flags: 0x"));
            Serial.println(errFlag, HEX);
        }
        Serial.println(F("========================\n"));
    }
    // CANSEND: Send a test message (for testing slave TX)
    else if (strcmp(cmd, "CANSEND") == 0) {
        if (canInitialized) {
            unsigned char testData[8] = {0x53, 0x4C, 0x41, 0x56, 0x45, 0x21, 0x00, 0x00}; // "SLAVE!"
            Serial.print(F("Sending test from SLAVE ID=0x456... "));
            byte result = canBus.sendMsgBuf(0x456, 0, 8, testData);
            Serial.println(result == CAN_OK ? F("OK") : F("FAILED"));
        } else {
            Serial.println(F("CAN not initialized"));
        }
    }
    #endif
    // Legacy support for old commands
    else if (strncmp(cmd, "RPM:", 4) == 0) {
        currentRPM = atoi(cmd + 4);
        errorMode = false;
        rainbowMode = false;
    }
    else if (strncmp(cmd, "SPD:", 4) == 0) {
        currentSpeed = atoi(cmd + 4);
    }
    else if (strcmp(cmd, "CLR") == 0) {
        strip.clear();
        strip.show();
        currentRPM = 0;
        currentSpeed = 0;
        errorMode = false;
        rainbowMode = false;
    }
}

// ============================================================================
// SETUP
// ============================================================================

void setup() {
    // Initialize hardware Serial for debug output (won't interfere with SoftwareSerial)
    Serial.begin(115200);
    
    // Send identification immediately
    Serial.println("LED Slave v2.2 (Haptic+Diag)");
    Serial.print("RX Pin: D");
    Serial.println(SERIAL_RX_PIN);
    
    // Quick diagnostic: read pin state before SoftwareSerial takes over
    pinMode(SERIAL_RX_PIN, INPUT_PULLUP);
    int pinState = digitalRead(SERIAL_RX_PIN);
    Serial.print("D2 initial state (should be HIGH): ");
    Serial.println(pinState == HIGH ? "HIGH (OK)" : "LOW (Check wiring!)");
    
    // Check supply voltage before enabling haptic
    float vcc = readVcc();
    bool hapticEnabled = false;
    
    // Initialize haptic motor pin
    #if ENABLE_HAPTIC
    pinMode(HAPTIC_PIN, OUTPUT);
    digitalWrite(HAPTIC_PIN, LOW);
    
    if (vcc >= MIN_VOLTAGE_FOR_HAPTIC) {
        hapticEnabled = true;
    }
    #endif
    
    // Initialize SoftwareSerial for commands from master
    slaveSerial.begin(SLAVE_SERIAL_BAUD);
    
    // Initialize LED strip with aggressive reset
    strip.begin();
    strip.setBrightness(255);
    
    // Send multiple clears to wake up strip
    for (int i = 0; i < 5; i++) {
        strip.clear();
        strip.show();
        delay(10);
    }
    
    // Futuristic rainbow startup sequence - wave towards center with haptic sync
    Serial.println("Starting rainbow startup sequence...");
    
    // Rainbow wave converging to center from both edges with synchronized haptic revs
    // Each rainbow cycle = ~1.92 seconds (256 phases × 15ms), 3 cycles = ~5.76 seconds total
    for (int cycle = 0; cycle < 3; cycle++) {  // 3 complete rainbow cycles
        for (int phase = 0; phase < 256; phase += 2) {  // Color wheel rotation
            #if ENABLE_BRIGHTNESS_POT
            // Read brightness from potentiometer during startup animation
            int potValue = 1023 - analogRead(BRIGHTNESS_POT_PIN);
            uint8_t brightness = map(potValue, 0, 1023, 0, 255);
            strip.setBrightness(brightness);
            #endif
            
            #if ENABLE_HAPTIC
            // Check voltage every 10 phases to detect voltage sag from motor
            if (hapticEnabled && (phase % 10 == 0)) {
                float currentVcc = readVcc();
                if (currentVcc < MIN_VOLTAGE_FOR_HAPTIC) {
                    Serial.print("Voltage dropped to ");
                    Serial.print(currentVcc, 2);
                    Serial.println("V - disabling haptic");
                    analogWrite(HAPTIC_PIN, 0);
                    hapticEnabled = false;
                }
            }
            
            // Only run haptic if voltage is sufficient
            if (hapticEnabled) {
                // Calculate haptic intensity based on cycle and phase for smooth rev pattern
                int baseIntensity = 35 + (cycle * 15);  // Rev 1: 35, Rev 2: 50, Rev 3: 65
                int hapticIntensity;
                
                // Rev up during first 20% of cycle
                if (phase < 51) {
                    hapticIntensity = (cycle == 0 ? 0 : 20) + ((phase * baseIntensity) / 51);
                }
                // Hold at peak during middle 40% of cycle
                else if (phase < 154) {
                    hapticIntensity = baseIntensity;
                }
                // Decay during last 40% of cycle
                else {
                    int decayAmount = ((phase - 154) * baseIntensity) / 102;
                    hapticIntensity = baseIntensity - decayAmount;
                    if (cycle < 2) {
                        hapticIntensity = constrain(hapticIntensity, 20, baseIntensity);
                    } else {
                        hapticIntensity = constrain(hapticIntensity, 0, baseIntensity);
                    }
                }
                
                analogWrite(HAPTIC_PIN, hapticIntensity);
            }
            #endif
            
            for (int i = 0; i < LED_COUNT; i++) {
                // Calculate distance from center (makes wave converge to middle)
                int distanceFromCenter = abs(i - (LED_COUNT / 2));
                
                // Calculate hue with mirrored phase offset for center convergence
                uint16_t hue = ((distanceFromCenter * 65536L / (LED_COUNT / 2)) + (phase * 256)) & 0xFFFF;
                
                // Convert HSV to RGB (hue, saturation=255, value=255)
                uint32_t color = strip.gamma32(strip.ColorHSV(hue, 255, 255));
                strip.setPixelColor(i, color);
            }
            strip.show();
            delay(15);  // Smooth animation speed
        }
    }
    
    #if ENABLE_HAPTIC
    if (hapticEnabled) {
        analogWrite(HAPTIC_PIN, 0);
    }
    #endif
    
    // Fade out to black smoothly
    for (int brightness = 255; brightness >= 0; brightness -= 5) {
        strip.setBrightness(brightness);
        strip.show();
        delay(10);
    }
    
    // Reset brightness and clear
    strip.setBrightness(255);
    strip.clear();
    strip.show();
    
    // Start in NON-error mode - wait for master to connect
    // Master will send commands after its boot delay completes
    errorMode = false;
    
    // Record startup time for initial wait period
    lastCommandTime = millis();
    
    bufferIndex = 0;
    inputBuffer[0] = '\0';
    
    // ========================================================================
    // CAN BUS INITIALIZATION (for two-Arduino test)
    // ========================================================================
    #if ENABLE_CAN_TEST
    Serial.println(F("\n--- CAN Bus Init ---"));
    Serial.print(F("CAN init: MCP_ANY, 500KBPS, 8MHz... "));
    
    if (canBus.begin(MCP_ANY, CAN_500KBPS, MCP_8MHZ) == CAN_OK) {
        Serial.println(F("OK"));
        
        // Set masks to accept all messages
        canBus.init_Mask(0, 0, 0x00000000);
        canBus.init_Mask(1, 0, 0x00000000);
        canBus.init_Filt(0, 0, 0x00000000);
        canBus.init_Filt(1, 0, 0x00000000);
        canBus.init_Filt(2, 0, 0x00000000);
        canBus.init_Filt(3, 0, 0x00000000);
        canBus.init_Filt(4, 0, 0x00000000);
        canBus.init_Filt(5, 0, 0x00000000);
        
        Serial.print(F("Setting NORMAL mode... "));
        canBus.setMode(MCP_NORMAL);
        Serial.println(F("OK"));
        
        canInitialized = true;
        Serial.println(F("CAN: Ready for two-Arduino test"));
        Serial.println(F("Send 'CAN' via USB to enable CAN test mode"));
    } else {
        Serial.println(F("FAILED!"));
        Serial.println(F("CAN: Not available (check wiring)"));
        canInitialized = false;
    }
    #endif
    
    Serial.println("Waiting for master connection...");
}

// ============================================================================
// MAIN LOOP
// ============================================================================

void loop() {
    unsigned long currentTime = millis();
    static unsigned long totalBytesReceived = 0;  // Track total bytes for diagnostics
    static char usbBuffer[16];  // Separate buffer for USB commands
    static uint8_t usbBufferIndex = 0;
    
    // =======================================================================
    // USB Serial Commands (for testing/debugging from Arduino Actions)
    // =======================================================================
    while (Serial.available() > 0) {
        char c = Serial.read();
        
        if (c == '\n' || c == '\r') {
            if (usbBufferIndex > 0) {
                usbBuffer[usbBufferIndex] = '\0';
                
                // Enable debug mode when USB command received
                lastUSBActivity = currentTime;
                debugMode = true;
                
                Serial.print("USB CMD: ");
                Serial.println(usbBuffer);
                processCommand(usbBuffer);
                lastCommandTime = currentTime;  // Reset timeout on USB command too
                usbTestMode = true;  // Enable extended timeout for USB testing
                errorMode = false;   // Exit error mode when receiving USB commands
                usbBufferIndex = 0;
                
                // Small delay to allow LED update before next command
                delay(10);
            }
        } else if (c >= 32 && c <= 126 && usbBufferIndex < 15) {
            usbBuffer[usbBufferIndex++] = c;
        }
    }
    
    // Auto-disable debug mode after timeout (saves CPU when running standalone)
    if (debugMode && (currentTime - lastUSBActivity) > DEBUG_MODE_TIMEOUT_MS) {
        debugMode = false;
        Serial.println("Debug mode disabled (USB timeout)");
    }
    
    // =======================================================================
    // SoftwareSerial Commands (from Master Arduino via D2)
    // =======================================================================
    // Read serial commands from master - check multiple times per loop for responsiveness
    for (int i = 0; i < 3; i++) {
        while (slaveSerial.available() > 0) {
            char c = slaveSerial.read();
            lastCommandTime = currentTime;  // Update last command time on ANY data
            usbTestMode = false;  // Disable USB test mode when Master sends data
            totalBytesReceived++;  // Count bytes for diagnostics
            
            // Debug: print every byte received (only when USB debug active)
            if (debugMode) {
                Serial.print("RX: ");
                Serial.print((int)c);
                Serial.print(" '");
                if (c >= 32 && c <= 126) Serial.print(c);
                Serial.println("'");
            }
            
            // Start-of-message marker - process previous command and reset buffer
            if (c == '!') {
                // Process whatever was in the buffer before resetting
                if (bufferIndex > 0) {
                    inputBuffer[bufferIndex] = '\0';
                    if (debugMode) {
                        Serial.print("Processing: ");
                        Serial.println(inputBuffer);
                    }
                    processCommand(inputBuffer);
                }
                bufferIndex = 0;
                continue;  // Don't add ! to buffer
            }
            
            if (c == '\n' || c == '\r') {
                if (bufferIndex > 0) {
                    inputBuffer[bufferIndex] = '\0';
                    if (debugMode) {
                        Serial.print("Processing: ");
                        Serial.println(inputBuffer);
                    }
                    processCommand(inputBuffer);
                    bufferIndex = 0;
                }
            } else if (c >= 32 && c <= 126 && bufferIndex < 15) {
                inputBuffer[bufferIndex++] = c;
            }
        }
        delayMicroseconds(500);  // Brief pause between checks
    }
    
    // =======================================================================
    // CAN BUS MESSAGE HANDLING (two-Arduino test mode)
    // =======================================================================
    #if ENABLE_CAN_TEST
    if (canInitialized && canTestMode) {
        // Check for incoming CAN messages
        if (canBus.checkReceive() == CAN_MSGAVAIL) {
            unsigned long rxId;
            unsigned char len = 0;
            unsigned char rxBuf[8];
            
            canBus.readMsgBuf(&rxId, &len, rxBuf);
            canMsgCount++;
            
            // Print received message
            Serial.print(F("CAN RX: ID=0x"));
            Serial.print(rxId, HEX);
            Serial.print(F(" len="));
            Serial.print(len);
            Serial.print(F(" data="));
            for (uint8_t i = 0; i < len && i < 8; i++) {
                if (rxBuf[i] < 0x10) Serial.print('0');
                Serial.print(rxBuf[i], HEX);
                Serial.print(' ');
            }
            Serial.println();
            
            // If we receive test message from Master (ID 0x123), flash green and respond
            if (rxId == 0x123) {
                Serial.println(F("*** TEST MSG FROM MASTER ***"));
                
                // Flash LEDs green to indicate receipt
                for (int i = 0; i < LED_COUNT; i++) {
                    strip.setPixelColor(i, strip.Color(0, 255, 0));
                }
                strip.show();
                delay(200);
                strip.clear();
                strip.show();
                
                // Send response back to Master (ID 0x456)
                unsigned char respData[8] = {0x41, 0x43, 0x4B, rxBuf[0], rxBuf[1], rxBuf[2], 0x00, 0x00}; // "ACK" + echo
                Serial.print(F("Sending ACK response ID=0x456... "));
                byte result = canBus.sendMsgBuf(0x456, 0, 8, respData);
                Serial.println(result == CAN_OK ? F("OK") : F("FAILED"));
            }
        }
        
        // Periodic CAN status and broadcast
        if (currentTime - lastCanCheck >= 2000) {
            lastCanCheck = currentTime;
            byte errFlag = canBus.getError();
            Serial.print(F("CAN: msgs="));
            Serial.print(canMsgCount);
            Serial.print(F(" err=0x"));
            Serial.print(errFlag, HEX);
            
            // Send periodic broadcast message (simulates car ECU sending data)
            // Use standard OBD-II response ID 0x7E8 with fake RPM/speed data
            static uint16_t fakeRPM = 1000;
            static uint8_t fakeSpeed = 25;
            
            // Simulate RPM response (PID 0x0C)
            unsigned char rpmData[8] = {0x04, 0x41, 0x0C, (uint8_t)(fakeRPM >> 2), (uint8_t)((fakeRPM << 6) & 0xFF), 0x00, 0x00, 0x00};
            byte result = canBus.sendMsgBuf(0x7E8, 0, 8, rpmData);
            
            Serial.print(F(" TX:0x7E8="));
            Serial.println(result == CAN_OK ? F("OK") : F("FAIL"));
            
            // Vary the fake data slightly
            fakeRPM += 100;
            if (fakeRPM > 6000) fakeRPM = 1000;
            fakeSpeed += 5;
            if (fakeSpeed > 120) fakeSpeed = 25;
        }
    }
    #endif
    
    // Timeout check: if no data received for timeout period, enter error mode
    // USB test mode uses extended timeout (30s) for LED testing without Master
    unsigned long timeoutMs = usbTestMode ? USB_TEST_TIMEOUT_MS : MASTER_TIMEOUT_MS;
    if (!errorMode && (currentTime - lastCommandTime) > timeoutMs) {
        // Only show error after initial startup wait
        if (currentTime > INITIAL_WAIT_MS) {
            if (debugMode) {
                Serial.println(usbTestMode ? "USB test timeout - entering error mode" : "Master timeout - entering error mode");
            }
            errorMode = true;
            rainbowMode = false;
            usbTestMode = false;
        }
    }
    
    // Periodic diagnostic: print status every 5 seconds (only in debug mode)
    static unsigned long lastDiagTime = 0;
    if (debugMode && (currentTime - lastDiagTime >= 5000)) {
        lastDiagTime = currentTime;
        Serial.print("Status: errorMode=");
        Serial.print(errorMode ? "YES" : "NO");
        Serial.print(" debugMode=ON");
        if (usbTestMode) Serial.print(" [USB TEST]");
        Serial.print(" bytesRx=");
        Serial.print(totalBytesReceived);
        Serial.print(" D2=");
        Serial.println(digitalRead(SERIAL_RX_PIN) ? "HIGH" : "LOW");
    }
    
    // Update LED display continuously
    updateLEDDisplay();
    
    // Update brightness from potentiometer
    updateBrightness();
    
    // Update haptic motor state
    updateHaptic();
    
    // Minimal delay - SoftwareSerial has its own buffering
    delayMicroseconds(500);
}
