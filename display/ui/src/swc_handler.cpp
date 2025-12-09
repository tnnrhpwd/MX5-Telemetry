/**
 * @file swc_handler.cpp
 * @brief Steering Wheel Control button handler implementation
 */

#include "swc_handler.h"

SWCHandler::SWCHandler() {
    currentButton = BTN_NONE;
    lastButton = BTN_NONE;
    lastPressTime = 0;
    repeatDelay = REPEAT_DELAY_MS;
    buttonProcessed = true;
    debounceTime = 0;
}

void SWCHandler::processCANMessage(uint32_t canId, uint8_t* data, uint8_t len) {
    if (len < 1) return;
    
    uint32_t now = millis();
    ButtonEvent newButton = BTN_NONE;
    
    // Process audio buttons (CAN ID 0x240)
    if (canId == SWC_AUDIO_CAN_ID) {
        uint8_t buttonByte = data[0];
        
        if (buttonByte & SWC_VOL_UP)      newButton = BTN_VOL_UP;
        else if (buttonByte & SWC_VOL_DOWN)  newButton = BTN_VOL_DOWN;
        else if (buttonByte & SWC_MODE)      newButton = BTN_MODE;
        else if (buttonByte & SWC_SEEK_UP)   newButton = BTN_SEEK_UP;
        else if (buttonByte & SWC_SEEK_DOWN) newButton = BTN_SEEK_DOWN;
        else if (buttonByte & SWC_MUTE)      newButton = BTN_MUTE;
    }
    // Process cruise buttons (CAN ID 0x250)
    else if (canId == SWC_CRUISE_CAN_ID) {
        uint8_t buttonByte = data[0];
        
        if (buttonByte & SWC_ON_OFF)      newButton = BTN_ON_OFF;
        else if (buttonByte & SWC_CANCEL)    newButton = BTN_CANCEL;
        else if (buttonByte & SWC_RES_PLUS)  newButton = BTN_RES_PLUS;
        else if (buttonByte & SWC_SET_MINUS) newButton = BTN_SET_MINUS;
    }
    
    // Debounce handling
    if (newButton != currentButton) {
        if (now - debounceTime >= DEBOUNCE_MS) {
            currentButton = newButton;
            debounceTime = now;
            
            if (newButton != BTN_NONE) {
                lastPressTime = now;
                buttonProcessed = false;
            }
        }
    }
}

ButtonEvent SWCHandler::getButtonPress() {
    // Return button if not yet processed
    if (!buttonProcessed && currentButton != BTN_NONE) {
        buttonProcessed = true;
        lastButton = currentButton;
        return currentButton;
    }
    
    // Handle button repeat (for held buttons like VOL+/-)
    if (currentButton != BTN_NONE && buttonProcessed) {
        uint32_t now = millis();
        uint32_t holdTime = now - lastPressTime;
        
        // Start repeating after initial delay
        if (holdTime >= repeatDelay) {
            lastPressTime = now - (REPEAT_DELAY_MS - REPEAT_RATE_MS);
            return currentButton;
        }
    }
    
    return BTN_NONE;
}

void SWCHandler::simulateButton(ButtonEvent button) {
    currentButton = button;
    lastPressTime = millis();
    buttonProcessed = false;
    debounceTime = millis();
}

bool SWCHandler::isButtonHeld() {
    return currentButton != BTN_NONE;
}

ButtonEvent SWCHandler::getLastButton() {
    return lastButton;
}
