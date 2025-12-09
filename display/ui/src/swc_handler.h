/**
 * @file swc_handler.h
 * @brief Steering Wheel Control (SWC) button handler
 * 
 * Handles CAN messages from MS-CAN bus for steering wheel buttons.
 */

#ifndef SWC_HANDLER_H
#define SWC_HANDLER_H

#include <Arduino.h>

// CAN IDs for steering wheel controls (MS-CAN 125kbps)
#define SWC_AUDIO_CAN_ID    0x240
#define SWC_CRUISE_CAN_ID   0x250

// Audio button masks (CAN ID 0x240, Byte 0)
#define SWC_VOL_UP          0x01
#define SWC_VOL_DOWN        0x02
#define SWC_MODE            0x04
#define SWC_SEEK_UP         0x08
#define SWC_SEEK_DOWN       0x10
#define SWC_MUTE            0x20

// Cruise button masks (CAN ID 0x250, Byte 0)
#define SWC_ON_OFF          0x01
#define SWC_CANCEL          0x02
#define SWC_RES_PLUS        0x04
#define SWC_SET_MINUS       0x08

// Button event types
typedef enum {
    BTN_NONE = 0,
    BTN_VOL_UP,
    BTN_VOL_DOWN,
    BTN_MODE,
    BTN_SEEK_UP,
    BTN_SEEK_DOWN,
    BTN_MUTE,
    BTN_ON_OFF,
    BTN_CANCEL,
    BTN_RES_PLUS,
    BTN_SET_MINUS
} ButtonEvent;

// Button names for debugging
static const char* BUTTON_NAMES[] = {
    "NONE",
    "VOL_UP",
    "VOL_DOWN", 
    "MODE",
    "SEEK_UP",
    "SEEK_DOWN",
    "MUTE",
    "ON_OFF",
    "CANCEL",
    "RES_PLUS",
    "SET_MINUS"
};

class SWCHandler {
public:
    SWCHandler();
    
    // Process incoming CAN message
    void processCANMessage(uint32_t canId, uint8_t* data, uint8_t len);
    
    // Check for button press (call in loop)
    ButtonEvent getButtonPress();
    
    // Simulate button press (for debugging)
    void simulateButton(ButtonEvent button);
    
    // Check if any button is currently held
    bool isButtonHeld();
    
    // Get last button for repeat handling
    ButtonEvent getLastButton();
    
private:
    ButtonEvent currentButton;
    ButtonEvent lastButton;
    uint32_t lastPressTime;
    uint32_t repeatDelay;
    bool buttonProcessed;
    
    // Debounce
    uint32_t debounceTime;
    static const uint32_t DEBOUNCE_MS = 50;
    static const uint32_t REPEAT_DELAY_MS = 500;
    static const uint32_t REPEAT_RATE_MS = 100;
};

#endif // SWC_HANDLER_H
