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
 * SERIAL COMMANDS (9600 baud):
 * - RPM:xxxx     Set RPM and update display (e.g., RPM:3500)
 * - SPD:xxx      Set speed in km/h (e.g., SPD:60)
 * - ERR          Show error state (red pepper animation)
 * - CLR          Clear all LEDs
 * - BRT:xxx      Set brightness 0-255 (e.g., BRT:128)
 * 
 * VERSION: 2.1.0 - Uses SoftwareSerial on D2 to avoid upload interference
 * ============================================================================
 */

#include <Arduino.h>
#include <SoftwareSerial.h>
#include <Adafruit_NeoPixel.h>
#include "LEDStates.h"

// ============================================================================
// CONFIGURATION  
// ============================================================================

#define LED_DATA_PIN        5       // D5 on Arduino #2
#define SERIAL_RX_PIN       2       // D2 for SoftwareSerial RX (from master TX1)
#define LED_COUNT           20      // Number of LEDs in strip (adjust to your strip)
#define SERIAL_BAUD         9600    // Serial communication with master

// ============================================================================
// GLOBAL OBJECTS
// ============================================================================

SoftwareSerial slaveSerial(SERIAL_RX_PIN, -1);  // RX on D2, no TX needed
Adafruit_NeoPixel strip(LED_COUNT, LED_DATA_PIN, NEO_GRB + NEO_KHZ800);

// ============================================================================
// STATE VARIABLES
// ============================================================================

uint16_t currentRPM = 0;
uint16_t currentSpeed = 0;
bool errorMode = false;
unsigned long lastAnimationUpdate = 0;
uint8_t pepperPosition = 0;
bool flashState = false;
char inputBuffer[16];
uint8_t bufferIndex = 0;

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
            strip.setPixelColor(i, strip.Color(r, g, b));
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

void gasEfficiencyState() {
    drawMirroredBar(STATE_1_LEDS_PER_SIDE, STATE_1_COLOR_R, STATE_1_COLOR_G, STATE_1_COLOR_B);
}

void stallDangerState() {
    uint8_t brightness = getPulseBrightness(STATE_2_PULSE_PERIOD, 
                                            STATE_2_MIN_BRIGHTNESS, 
                                            STATE_2_MAX_BRIGHTNESS);
    
    solidFill(scaleColor(STATE_2_COLOR_R, brightness),
              scaleColor(STATE_2_COLOR_G, brightness),
              scaleColor(STATE_2_COLOR_B, brightness));
}

void normalDrivingState(uint16_t rpm) {
    uint16_t range = STATE_3_RPM_MAX - STATE_3_RPM_MIN;
    uint16_t rpmInRange = rpm - STATE_3_RPM_MIN;
    uint8_t ledsPerSide = map(rpmInRange, 0, range, 0, LED_COUNT / 2);
    
    drawMirroredBar(ledsPerSide, STATE_3_COLOR_R, STATE_3_COLOR_G, STATE_3_COLOR_B);
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
}

void errorState() {
    pepperAnimation(ERROR_COLOR_R, ERROR_COLOR_G, ERROR_COLOR_B, 
                    ERROR_PEPPER_DELAY, ERROR_HOLD_TIME);
}

void updateLEDDisplay() {
    if (errorMode) {
        errorState();
        return;
    }
    
    // State 0: Idle/Neutral (speed = 0)
    if (currentSpeed <= STATE_0_SPEED_THRESHOLD) {
        idleNeutralState();
        return;
    }
    
    // State 5: Rev Limit
    if (currentRPM >= STATE_5_RPM_MIN) {
        revLimitState();
    }
    // State 4: High RPM
    else if (currentRPM >= STATE_4_RPM_MIN && currentRPM <= STATE_4_RPM_MAX) {
        highRPMShiftState(currentRPM);
    }
    // State 3: Normal Driving
    else if (currentRPM >= STATE_3_RPM_MIN && currentRPM <= STATE_3_RPM_MAX) {
        normalDrivingState(currentRPM);
    }
    // State 2: Stall Danger
    else if (currentRPM >= STATE_2_RPM_MIN && currentRPM <= STATE_2_RPM_MAX) {
        stallDangerState();
    }
    // State 1: Gas Efficiency
    else if (currentRPM >= STATE_1_RPM_MIN && currentRPM <= STATE_1_RPM_MAX) {
        gasEfficiencyState();
    }
    else {
        strip.clear();
        strip.show();
    }
}

// ============================================================================
// COMMAND PROCESSING
// ============================================================================

void processCommand(const char* cmd) {
    // RPM command: RPM:xxxx
    if (strncmp(cmd, "RPM:", 4) == 0) {
        currentRPM = atoi(cmd + 4);
        errorMode = false;
    }
    // Speed command: SPD:xxx
    else if (strncmp(cmd, "SPD:", 4) == 0) {
        currentSpeed = atoi(cmd + 4);
    }
    // Error command: ERR
    else if (strcmp(cmd, "ERR") == 0) {
        errorMode = true;
    }
    // Clear command: CLR
    else if (strcmp(cmd, "CLR") == 0) {
        strip.clear();
        strip.show();
        currentRPM = 0;
        currentSpeed = 0;
        errorMode = false;
    }
    // Brightness command: BRT:xxx
    else if (strncmp(cmd, "BRT:", 4) == 0) {
        uint8_t brightness = atoi(cmd + 4);
        strip.setBrightness(brightness);
    }
}

// ============================================================================
// SETUP
// ============================================================================

void setup() {
    // Initialize SoftwareSerial for commands from master
    slaveSerial.begin(SERIAL_BAUD);
    
    // Initialize LED strip
    strip.begin();
    strip.setBrightness(255);
    strip.clear();
    strip.show();
    
    // Startup animation - quick flash to show it's ready
    for (int i = 0; i < 3; i++) {
        solidFill(0, 255, 0);
        delay(100);
        strip.clear();
        strip.show();
        delay(100);
    }
    
    bufferIndex = 0;
    inputBuffer[0] = '\0';
}

// ============================================================================
// MAIN LOOP
// ============================================================================

void loop() {
    // Read serial commands from master
    while (slaveSerial.available() > 0) {
        char c = slaveSerial.read();
        
        if (c == '\n' || c == '\r') {
            if (bufferIndex > 0) {
                inputBuffer[bufferIndex] = '\0';
                processCommand(inputBuffer);
                bufferIndex = 0;
            }
        } else if (c >= 32 && c <= 126 && bufferIndex < 15) {
            inputBuffer[bufferIndex++] = c;
        }
    }
    
    // Update LED display continuously
    updateLEDDisplay();
    
    // Small delay to prevent overloading
    delay(10);
}
