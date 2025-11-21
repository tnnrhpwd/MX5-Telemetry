#ifndef LED_CONTROLLER_H
#define LED_CONTROLLER_H

#include <Arduino.h>
#include <Adafruit_NeoPixel.h>
#include <config.h>
#include <LEDStates.h>

// ============================================================================
// LED Strip Controller - Mirrored Progress Bar System
// ============================================================================
// Manages WS2812B LED strip with mirrored progress bar visualization:
// State 0: Idle/Neutral - White pepper inward (speed = 0)
// State 1: Gas Efficiency - Steady green edges (2000-2500 RPM)
// State 2: Stall Danger - Orange pulse outward (750-1999 RPM)
// State 3: Normal Driving - Yellow bars inward (2501-4500 RPM)
// State 4: High RPM - Red bars with flashing gap (4501-7199 RPM)
// State 5: Rev Limit - Solid red strip (7200+ RPM)
// Error: CAN Error - Red pepper inward
// ============================================================================

class LEDController {
public:
    LEDController(uint8_t pin, uint16_t numLeds);
    
    // Initialization
    void begin();
    
    // Update display based on RPM
    void updateRPM(uint16_t rpm);
    
    // Update display based on RPM and vehicle speed
    void updateRPM(uint16_t rpm, uint16_t speed_kmh);
    
    // Update display for CAN error state
    void updateRPMError();
    
    // Animations
    void startupAnimation();
    void readyAnimation();
    void errorAnimation();
    
    // Control
    void clear();
    void setBrightness(uint8_t brightness);
    
private:
    Adafruit_NeoPixel strip;
    unsigned long lastAnimationUpdate;
    uint8_t chasePosition;
    uint8_t pepperPosition;      // For inward pepper animations
    bool flashState;             // For State 4 flashing gap
    
    // State visualization methods
    void idleNeutralState();           // State 0: White pepper inward
    void gasEfficiencyState();         // State 1: Green edges
    void stallDangerState(uint16_t rpm);  // State 2: Orange pulse outward
    void normalDrivingState(uint16_t rpm); // State 3: Yellow mirrored bar
    void highRPMShiftState(uint16_t rpm);  // State 4: Red with flashing gap
    void revLimitState();              // State 5: Solid red
    void canErrorState();              // Error: Red pepper inward
    
    // Helper functions
    uint32_t getRPMColor(int ledIndex, int totalLEDs);
    void shiftLightPattern(uint16_t rpm);
    uint32_t wheelColor(byte wheelPos);
    uint8_t getPulseBrightness(uint16_t period, uint8_t minBright, uint8_t maxBright);
    uint8_t scaleColor(uint8_t color, uint8_t brightness);
    void drawMirroredBar(uint8_t ledsPerSide, uint8_t r, uint8_t g, uint8_t b);
};

#endif // LED_CONTROLLER_H
