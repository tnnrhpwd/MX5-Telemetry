#include "LEDController.h"

// ============================================================================
// LED Controller Implementation - Mirrored Progress Bar System
// ============================================================================

LEDController::LEDController(uint8_t pin, uint16_t numLeds)
    : strip(numLeds, pin, NEO_GRB + NEO_KHZ800), 
      lastAnimationUpdate(0), 
      chasePosition(0),
      pepperPosition(0),
      flashState(false) {
}

void LEDController::begin() {
    strip.begin();
    strip.show();  // Initialize all pixels to 'off'
    strip.setBrightness(255);  // Full brightness
}

void LEDController::updateRPM(uint16_t rpm) {
    // Default: assume vehicle is moving (no speed check)
    updateRPM(rpm, 1);  // Non-zero speed bypasses idle/neutral state
}

void LEDController::updateRPM(uint16_t rpm, uint16_t speed_kmh) {
    // State 0: Idle/Neutral (speed = 0, not moving)
    if (IS_STATE_0(speed_kmh)) {
        idleNeutralState();
        return;
    }
    
    // State 5: Rev Limit Cut (7200+ RPM)
    if (IS_STATE_5(rpm)) {
        revLimitState();
    }
    // State 4: High RPM / Shift Danger (4501-7199 RPM)
    else if (IS_STATE_4(rpm)) {
        highRPMShiftState(rpm);
    }
    // State 3: Normal Driving / Power Band (2501-4500 RPM)
    else if (IS_STATE_3(rpm)) {
        normalDrivingState(rpm);
    }
    // State 1: Gas Efficiency Zone (2000-2500 RPM)
    else if (IS_STATE_1(rpm)) {
        gasEfficiencyState();
    }
    // State 2: Stall Danger (750-1999 RPM)
    else if (IS_STATE_2(rpm)) {
        stallDangerState(rpm);
    }
    // Below minimum RPM - turn off
    else {
        strip.clear();
        strip.show();
    }
}

void LEDController::updateRPMError() {
    canErrorState();
}

// ============================================================================
// State 0: Idle/Neutral - White Pepper Inward (Speed = 0)
// ============================================================================
void LEDController::idleNeutralState() {
    unsigned long currentTime = millis();
    
    // Update pepper animation
    if (currentTime - lastAnimationUpdate >= STATE_0_PEPPER_DELAY) {
        lastAnimationUpdate = currentTime;
        pepperPosition++;
        
        // Reset after completing full animation + hold time
        if (pepperPosition >= (LED_COUNT / 2) + (STATE_0_HOLD_TIME / STATE_0_PEPPER_DELAY)) {
            pepperPosition = 0;
        }
    }
    
    // Draw pepper effect from edges inward
    for (int i = 0; i < LED_COUNT; i++) {
        int distanceFromEdge;
        if (i < LED_COUNT / 2) {
            distanceFromEdge = i;  // Left side
        } else {
            distanceFromEdge = LED_COUNT - 1 - i;  // Right side
        }
        
        if (distanceFromEdge <= pepperPosition && pepperPosition < (LED_COUNT / 2)) {
            // Light up this LED
            strip.setPixelColor(i, strip.Color(STATE_0_COLOR_R, STATE_0_COLOR_G, STATE_0_COLOR_B));
        } else {
            strip.setPixelColor(i, 0);
        }
    }
    
    strip.show();
}

// ============================================================================
// State 1: Gas Efficiency Zone - Steady Green Edges
// ============================================================================
void LEDController::gasEfficiencyState() {
    // Light up outermost LEDs on each side with steady green
    for (int i = 0; i < LED_COUNT; i++) {
        if (i < STATE_1_LEDS_PER_SIDE || i >= (LED_COUNT - STATE_1_LEDS_PER_SIDE)) {
            // Outer LEDs - Green
            strip.setPixelColor(i, strip.Color(STATE_1_COLOR_R, STATE_1_COLOR_G, STATE_1_COLOR_B));
        } else {
            // Inner LEDs - Off
            strip.setPixelColor(i, 0);
        }
    }
    
    strip.show();
}

// ============================================================================
// State 2: Stall Danger - Orange Pulse Outward
// ============================================================================
void LEDController::stallDangerState(uint16_t /* rpm */) {
    uint8_t brightness = getPulseBrightness(STATE_2_PULSE_PERIOD, 
                                            STATE_2_MIN_BRIGHTNESS, 
                                            STATE_2_MAX_BRIGHTNESS);
    
    // Pulsing orange on all LEDs
    for (int i = 0; i < LED_COUNT; i++) {
        uint8_t r = scaleColor(STATE_2_COLOR_R, brightness);
        uint8_t g = scaleColor(STATE_2_COLOR_G, brightness);
        uint8_t b = scaleColor(STATE_2_COLOR_B, brightness);
        strip.setPixelColor(i, strip.Color(r, g, b));
    }
    
    strip.show();
}

// ============================================================================
// State 3: Normal Driving - Yellow Mirrored Progress Bar
// ============================================================================
void LEDController::normalDrivingState(uint16_t rpm) {
    // Calculate position within State 3 range (0.0 to 1.0)
    float position = (float)(rpm - STATE_3_RPM_MIN) / (float)(STATE_3_RPM_MAX - STATE_3_RPM_MIN);
    position = constrain(position, 0.0, 1.0);
    
    // Calculate how many LEDs per side should be lit
    uint8_t ledsPerSide = (uint8_t)(position * (LED_COUNT / 2));
    if (ledsPerSide > LED_COUNT / 2) ledsPerSide = LED_COUNT / 2;
    
    // Draw mirrored bar (yellow growing inward from edges)
    drawMirroredBar(ledsPerSide, STATE_3_COLOR_R, STATE_3_COLOR_G, STATE_3_COLOR_B);
}

// ============================================================================
// State 4: High RPM / Shift Danger - Red with Flashing Gap
// ============================================================================
void LEDController::highRPMShiftState(uint16_t rpm) {
    // Calculate position within State 4 range (0.0 to 1.0)
    float position = (float)(rpm - STATE_4_RPM_MIN) / (float)(STATE_4_RPM_MAX - STATE_4_RPM_MIN);
    position = constrain(position, 0.0, 1.0);
    
    // Calculate flash speed based on RPM (faster as RPM increases)
    uint16_t flashSpeed = STATE_4_FLASH_SPEED_MIN - 
                          (uint16_t)(position * (STATE_4_FLASH_SPEED_MIN - STATE_4_FLASH_SPEED_MAX));
    
    // Update flash state based on timing
    unsigned long currentTime = millis();
    if (currentTime - lastAnimationUpdate >= flashSpeed) {
        lastAnimationUpdate = currentTime;
        flashState = !flashState;
    }
    
    // Calculate how many LEDs per side should be lit (red bars)
    uint8_t ledsPerSide = (uint8_t)(position * (LED_COUNT / 2));
    if (ledsPerSide > LED_COUNT / 2) ledsPerSide = LED_COUNT / 2;
    
    // Draw all LEDs
    for (int i = 0; i < LED_COUNT; i++) {
        bool isInBar;
        if (i < LED_COUNT / 2) {
            // Left side: lit from edge inward
            isInBar = (i < ledsPerSide);
        } else {
            // Right side: lit from edge inward
            isInBar = (i >= (LED_COUNT - ledsPerSide));
        }
        
        if (isInBar) {
            // Red bar
            strip.setPixelColor(i, strip.Color(STATE_4_BAR_R, STATE_4_BAR_G, STATE_4_BAR_B));
        } else {
            // Flashing gap in center
            if (flashState) {
                strip.setPixelColor(i, strip.Color(STATE_4_FLASH_1_R, STATE_4_FLASH_1_G, STATE_4_FLASH_1_B));
            } else {
                strip.setPixelColor(i, strip.Color(STATE_4_FLASH_2_R, STATE_4_FLASH_2_G, STATE_4_FLASH_2_B));
            }
        }
    }
    
    strip.show();
}

// ============================================================================
// State 5: Rev Limit Cut - Solid Red Strip
// ============================================================================
void LEDController::revLimitState() {
    // All LEDs solid red
    for (int i = 0; i < LED_COUNT; i++) {
        strip.setPixelColor(i, strip.Color(STATE_5_COLOR_R, STATE_5_COLOR_G, STATE_5_COLOR_B));
    }
    strip.show();
}

// ============================================================================
// Error State: CAN Bus Read Error - Red Pepper Inward
// ============================================================================
void LEDController::canErrorState() {
    unsigned long currentTime = millis();
    
    // Update pepper animation
    if (currentTime - lastAnimationUpdate >= ERROR_PEPPER_DELAY) {
        lastAnimationUpdate = currentTime;
        pepperPosition++;
        
        // Reset after completing full animation + hold time
        if (pepperPosition >= (LED_COUNT / 2) + (ERROR_HOLD_TIME / ERROR_PEPPER_DELAY)) {
            pepperPosition = 0;
        }
    }
    
    // Draw pepper effect from edges inward (red)
    for (int i = 0; i < LED_COUNT; i++) {
        int distanceFromEdge;
        if (i < LED_COUNT / 2) {
            distanceFromEdge = i;  // Left side
        } else {
            distanceFromEdge = LED_COUNT - 1 - i;  // Right side
        }
        
        if (distanceFromEdge <= pepperPosition && pepperPosition < (LED_COUNT / 2)) {
            // Light up this LED with red
            strip.setPixelColor(i, strip.Color(ERROR_COLOR_R, ERROR_COLOR_G, ERROR_COLOR_B));
        } else {
            strip.setPixelColor(i, 0);
        }
    }
    
    strip.show();
}

// ============================================================================
// Helper: Calculate Pulsing Brightness
// ============================================================================
uint8_t LEDController::getPulseBrightness(uint16_t period, uint8_t minBright, uint8_t maxBright) {
    unsigned long currentTime = millis();
    float phase = (float)(currentTime % period) / (float)period;
    
    // Sine wave for smooth pulsing (0 to 2π)
    float angle = phase * 2.0 * PI;
    float sineValue = (sin(angle) + 1.0) / 2.0;  // Normalize to 0.0 to 1.0
    
    // Map to brightness range
    uint8_t brightness = minBright + (uint8_t)(sineValue * (maxBright - minBright));
    
    return brightness;
}

// ============================================================================
// Helper: Scale a Color Component by Brightness
// ============================================================================
uint8_t LEDController::scaleColor(uint8_t color, uint8_t brightness) {
    return (uint8_t)((color * brightness) / 255);
}

// ============================================================================
// Helper: Draw Mirrored Bar (from edges inward)
// ============================================================================
void LEDController::drawMirroredBar(uint8_t ledsPerSide, uint8_t r, uint8_t g, uint8_t b) {
    for (int i = 0; i < LED_COUNT; i++) {
        bool isLit;
        if (i < LED_COUNT / 2) {
            // Left side: lit from edge inward
            isLit = (i < ledsPerSide);
        } else {
            // Right side: lit from edge inward
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

uint32_t LEDController::getRPMColor(int ledIndex, int totalLEDs) {
    // Create gradient from green (low RPM) to red (high RPM)
    // Green -> Yellow -> Orange -> Red
    
    float position = (float)ledIndex / (float)totalLEDs;
    
    uint8_t red, green, blue = 0;
    
    if (position < 0.5) {
        // Green to Yellow (first half)
        red = (uint8_t)(position * 2.0 * 255);
        green = 255;
    } else {
        // Yellow to Red (second half)
        red = 255;
        green = (uint8_t)((1.0 - position) * 2.0 * 255);
    }
    
    return strip.Color(red, green, blue);
}

void LEDController::shiftLightPattern(uint16_t rpm) {
    // Flash all LEDs red when at shift point
    static unsigned long lastFlash = 0;
    static bool flashState = false;
    
    unsigned long currentMillis = millis();
    
    // Flash faster as RPM approaches redline
    uint16_t flashInterval = map(rpm, RPM_SHIFT_LIGHT, RPM_REDLINE, 200, 50);
    flashInterval = constrain(flashInterval, 50, 200);
    
    if (currentMillis - lastFlash >= flashInterval) {
        lastFlash = currentMillis;
        flashState = !flashState;
    }
    
    if (flashState) {
        // All LEDs bright red
        for (int i = 0; i < LED_COUNT; i++) {
            strip.setPixelColor(i, strip.Color(255, 0, 0));
        }
    } else {
        // All LEDs dim red
        for (int i = 0; i < LED_COUNT; i++) {
            strip.setPixelColor(i, strip.Color(64, 0, 0));
        }
    }
    
    strip.show();
}

void LEDController::startupAnimation() {
    // Rainbow chase animation
    for (int j = 0; j < 255; j += 5) {
        for (int i = 0; i < LED_COUNT; i++) {
            strip.setPixelColor(i, wheelColor((i * 256 / LED_COUNT + j) & 255));
        }
        strip.show();
        delay(10);
    }
    strip.clear();
    strip.show();
}

void LEDController::errorAnimation() {
    // Flash red 3 times
    for (int i = 0; i < 3; i++) {
        for (int j = 0; j < LED_COUNT; j++) {
            strip.setPixelColor(j, strip.Color(255, 0, 0));
        }
        strip.show();
        delay(200);
        strip.clear();
        strip.show();
        delay(200);
    }
}

void LEDController::readyAnimation() {
    // Green fill animation
    for (int i = 0; i < LED_COUNT; i++) {
        strip.setPixelColor(i, strip.Color(0, 255, 0));
        strip.show();
        delay(30);
    }
    delay(500);
    strip.clear();
    strip.show();
}

void LEDController::clear() {
    strip.clear();
    strip.show();
}

void LEDController::setBrightness(uint8_t brightness) {
    strip.setBrightness(brightness);
}

uint32_t LEDController::wheelColor(byte wheelPos) {
    // Color wheel for rainbow effect
    wheelPos = 255 - wheelPos;
    if (wheelPos < 85) {
        return strip.Color(255 - wheelPos * 3, 0, wheelPos * 3);
    }
    if (wheelPos < 170) {
        wheelPos -= 85;
        return strip.Color(0, wheelPos * 3, 255 - wheelPos * 3);
    }
    wheelPos -= 170;
    return strip.Color(wheelPos * 3, 255 - wheelPos * 3, 0);
}
