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
 * - RBW          Show rainbow error pattern (for USB-connected mode)
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
#define SERIAL_RX_PIN       2       // D2 for SoftwareSerial RX (from master D6)
#define HAPTIC_PIN          3       // D3 for haptic motor (vibration feedback)
#define LED_COUNT           20      // Number of LEDs in strip (adjust to your strip)
#define SLAVE_SERIAL_BAUD   9600    // Baud rate for Master->Slave communication (bit-bang)
#define ENABLE_HAPTIC       true    // Enable/disable haptic feedback
#define MIN_VOLTAGE_FOR_HAPTIC  4.7 // Minimum voltage (V) to enable haptic on startup

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
bool rainbowMode = false;  // Track if USB is connected
unsigned long lastAnimationUpdate = 0;
uint16_t pepperPosition = 0;  // Changed to uint16_t to handle 0-255 range for rainbow
bool flashState = false;
char inputBuffer[16];
uint8_t bufferIndex = 0;
bool hapticActive = false;
unsigned long hapticStartTime = 0;
uint16_t hapticDuration = 0;
unsigned long lastCommandTime = 0;          // Track when last command was received
#define MASTER_TIMEOUT_MS 5000              // Enter error mode if no command for 5 seconds
#define INITIAL_WAIT_MS 3000                // Wait for master after startup before showing error

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
    
    // State 0: Idle/Neutral - show when:
    // - Speed is 0 (stopped/stationary)
    // - OR RPM is 0 (engine off but OBD-II connected and working)
    // This gives visual confirmation that CAN communication is working
    if (currentSpeed <= STATE_0_SPEED_THRESHOLD || currentRPM == 0) {
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
    Serial.print("CMD: ");
    Serial.println(cmd);
    
    // Commands from Master are prefixed with "LED:"
    // Strip the prefix if present
    if (strncmp(cmd, "LED:", 4) == 0) {
        cmd += 4;  // Skip "LED:" prefix
    }
    
    // RPM command: RPM:xxxx
    if (strncmp(cmd, "RPM:", 4) == 0) {
        currentRPM = atoi(cmd + 4);
        errorMode = false;
        rainbowMode = false;
        Serial.print("RPM set to: ");
        Serial.println(currentRPM);
    }
    // Speed command: SPD:xxx
    else if (strncmp(cmd, "SPD:", 4) == 0) {
        currentSpeed = atoi(cmd + 4);
        Serial.print("Speed set to: ");
        Serial.println(currentSpeed);
    }
    // Error mode command: E
    else if (strcmp(cmd, "E") == 0) {
        errorMode = true;
        rainbowMode = false;
        Serial.println("Error mode ON");
    }
    // Rainbow error command: R
    else if (strcmp(cmd, "R") == 0) {
        errorMode = true;
        rainbowMode = true;
        Serial.println("Rainbow error mode ON");
    }
    // Clear command: CLR
    else if (strcmp(cmd, "CLR") == 0) {
        strip.clear();
        strip.show();
        currentRPM = 0;
        currentSpeed = 0;
        errorMode = false;  // Clear also resets error mode
        rainbowMode = false;
        Serial.println("LEDs cleared");
    }
    // Brightness command: BRT:xxx
    else if (strncmp(cmd, "BRT:", 4) == 0) {
        uint8_t brightness = atoi(cmd + 4);
        strip.setBrightness(brightness);
        Serial.print("Brightness set to: ");
        Serial.println(brightness);
    }
    // Haptic command: VIB:xxx (vibrate for xxx milliseconds)
    else if (strncmp(cmd, "VIB:", 4) == 0) {
        uint16_t duration = atoi(cmd + 4);
        triggerHaptic(duration);
        Serial.print("Haptic triggered: ");
        Serial.print(duration);
        Serial.println("ms");
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
    
    Serial.println("Waiting for master connection...");
}

// ============================================================================
// MAIN LOOP
// ============================================================================

void loop() {
    unsigned long currentTime = millis();
    static unsigned long totalBytesReceived = 0;  // Track total bytes for diagnostics
    
    // Read serial commands from master - check multiple times per loop for responsiveness
    for (int i = 0; i < 3; i++) {
        while (slaveSerial.available() > 0) {
            char c = slaveSerial.read();
            lastCommandTime = currentTime;  // Update last command time on ANY data
            totalBytesReceived++;  // Count bytes for diagnostics
            
            // Debug: print every byte received
            Serial.print("RX: ");
            Serial.print((int)c);
            Serial.print(" '");
            if (c >= 32 && c <= 126) Serial.print(c);
            Serial.println("'");
            
            if (c == '\n' || c == '\r') {
                if (bufferIndex > 0) {
                    inputBuffer[bufferIndex] = '\0';
                    Serial.print("Processing: ");
                    Serial.println(inputBuffer);
                    processCommand(inputBuffer);
                    bufferIndex = 0;
                }
            } else if (c >= 32 && c <= 126 && bufferIndex < 15) {
                inputBuffer[bufferIndex++] = c;
            }
        }
        delayMicroseconds(500);  // Brief pause between checks
    }
    
    // Timeout check: if no data received from master for MASTER_TIMEOUT_MS, enter error mode
    // But only after the initial wait period has passed
    if (!errorMode && (currentTime - lastCommandTime) > MASTER_TIMEOUT_MS) {
        // Only show error after initial startup wait
        if (currentTime > INITIAL_WAIT_MS) {
            Serial.println("Master timeout - entering error mode");
            errorMode = true;
            rainbowMode = false;
        }
    }
    
    // Periodic diagnostic: print status every 5 seconds when in error mode
    static unsigned long lastDiagTime = 0;
    if (currentTime - lastDiagTime >= 5000) {
        lastDiagTime = currentTime;
        Serial.print("Status: errorMode=");
        Serial.print(errorMode ? "YES" : "NO");
        Serial.print(" bytesRx=");
        Serial.print(totalBytesReceived);
        Serial.print(" D2=");
        Serial.println(digitalRead(SERIAL_RX_PIN) ? "HIGH" : "LOW");
    }
    
    // Update LED display continuously
    updateLEDDisplay();
    
    // Update haptic motor state
    updateHaptic();
    
    // Minimal delay - SoftwareSerial has its own buffering
    delayMicroseconds(500);
}
