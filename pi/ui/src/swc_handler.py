"""
Steering Wheel Control (SWC) Handler for Raspberry Pi

Maps CAN bus steering wheel button messages to UI actions.
Receives button events either from:
1. Direct CAN reading (via MCP2515)
2. Serial from ESP32-S3 (forwarded)
"""

from enum import Enum, auto
from dataclasses import dataclass
import time

# CAN IDs for steering wheel controls (MS-CAN 125kbps)
SWC_AUDIO_CAN_ID = 0x240
SWC_CRUISE_CAN_ID = 0x250

# Audio button masks (CAN ID 0x240, Byte 0)
SWC_VOL_UP = 0x01
SWC_VOL_DOWN = 0x02
SWC_MODE = 0x04
SWC_SEEK_UP = 0x08
SWC_SEEK_DOWN = 0x10
SWC_MUTE = 0x20

# Cruise button masks (CAN ID 0x250, Byte 0)
SWC_ON_OFF = 0x01
SWC_CANCEL = 0x02
SWC_RES_PLUS = 0x04
SWC_SET_MINUS = 0x08


class ButtonEvent(Enum):
    """Button event types"""
    NONE = auto()
    VOL_UP = auto()
    VOL_DOWN = auto()
    MODE = auto()
    SEEK_UP = auto()
    SEEK_DOWN = auto()
    MUTE = auto()
    ON_OFF = auto()
    CANCEL = auto()
    RES_PLUS = auto()
    SET_MINUS = auto()


# Button names for display
BUTTON_NAMES = {
    ButtonEvent.NONE: "None",
    ButtonEvent.VOL_UP: "VOL+",
    ButtonEvent.VOL_DOWN: "VOL-",
    ButtonEvent.MODE: "MODE",
    ButtonEvent.SEEK_UP: "SEEK▲",
    ButtonEvent.SEEK_DOWN: "SEEK▼",
    ButtonEvent.MUTE: "MUTE",
    ButtonEvent.ON_OFF: "SELECT",
    ButtonEvent.CANCEL: "CANCEL",
    ButtonEvent.RES_PLUS: "UP",
    ButtonEvent.SET_MINUS: "DOWN",
}

# Action descriptions
BUTTON_ACTIONS = {
    ButtonEvent.MODE: "Switch device focus (Pi ↔ ESP32)",
    ButtonEvent.MUTE: "Toggle display sleep/wake",
    ButtonEvent.ON_OFF: "Select / Enter / Confirm",
    ButtonEvent.CANCEL: "Back / Exit / Escape",
    ButtonEvent.RES_PLUS: "Navigate Up / Scroll Up",
    ButtonEvent.SET_MINUS: "Navigate Down / Scroll Down",
    ButtonEvent.SEEK_UP: "Navigate Right / Next",
    ButtonEvent.SEEK_DOWN: "Navigate Left / Previous",
    ButtonEvent.VOL_UP: "Increase value",
    ButtonEvent.VOL_DOWN: "Decrease value",
}


class SWCHandler:
    """Handles steering wheel control button inputs"""
    
    DEBOUNCE_MS = 50
    REPEAT_DELAY_MS = 500
    REPEAT_RATE_MS = 100
    
    def __init__(self):
        self.current_button = ButtonEvent.NONE
        self.last_button = ButtonEvent.NONE
        self.last_press_time = 0
        self.button_processed = True
        self.debounce_time = 0
        self._pending_buttons = []  # Thread-safe queue for button events
        self._callbacks = []
    
    def process_can_message(self, can_id: int, data: bytes):
        """Process incoming CAN message for button events"""
        if len(data) < 1:
            return
        
        now = time.time() * 1000  # milliseconds
        new_button = ButtonEvent.NONE
        
        # Process audio buttons (CAN ID 0x240)
        if can_id == SWC_AUDIO_CAN_ID:
            button_byte = data[0]
            if button_byte & SWC_VOL_UP:
                new_button = ButtonEvent.VOL_UP
            elif button_byte & SWC_VOL_DOWN:
                new_button = ButtonEvent.VOL_DOWN
            elif button_byte & SWC_MODE:
                new_button = ButtonEvent.MODE
            elif button_byte & SWC_SEEK_UP:
                new_button = ButtonEvent.SEEK_UP
            elif button_byte & SWC_SEEK_DOWN:
                new_button = ButtonEvent.SEEK_DOWN
            elif button_byte & SWC_MUTE:
                new_button = ButtonEvent.MUTE
        
        # Process cruise buttons (CAN ID 0x250)
        elif can_id == SWC_CRUISE_CAN_ID:
            button_byte = data[0]
            if button_byte & SWC_ON_OFF:
                new_button = ButtonEvent.ON_OFF
            elif button_byte & SWC_CANCEL:
                new_button = ButtonEvent.CANCEL
            elif button_byte & SWC_RES_PLUS:
                new_button = ButtonEvent.RES_PLUS
            elif button_byte & SWC_SET_MINUS:
                new_button = ButtonEvent.SET_MINUS
        
        # Debounce handling
        if new_button != self.current_button:
            if now - self.debounce_time >= self.DEBOUNCE_MS:
                self.current_button = new_button
                self.debounce_time = now
                
                if new_button != ButtonEvent.NONE:
                    self.last_press_time = now
                    self.button_processed = False
                    # Queue button for main thread processing (CAN runs in background thread)
                    self._pending_buttons.append(new_button)
    
    def poll_buttons(self):
        """Poll for pending button events (call from main loop). Returns list of buttons."""
        buttons = self._pending_buttons.copy()
        self._pending_buttons.clear()
        return buttons
    
    def get_button_press(self) -> ButtonEvent:
        """Get button press event (call in loop)"""
        # Return button if not yet processed
        if not self.button_processed and self.current_button != ButtonEvent.NONE:
            self.button_processed = True
            self.last_button = self.current_button
            self._trigger_callbacks(self.current_button)
            return self.current_button
        
        # Handle button repeat for held buttons
        if self.current_button != ButtonEvent.NONE and self.button_processed:
            now = time.time() * 1000
            hold_time = now - self.last_press_time
            
            if hold_time >= self.REPEAT_DELAY_MS:
                self.last_press_time = now - (self.REPEAT_DELAY_MS - self.REPEAT_RATE_MS)
                self._trigger_callbacks(self.current_button)
                return self.current_button
        
        return ButtonEvent.NONE
    
    def simulate_button(self, button: ButtonEvent):
        """Simulate a button press (for debugging/testing)"""
        self.current_button = button
        self.last_press_time = time.time() * 1000
        self.button_processed = False
        self.debounce_time = time.time() * 1000
    
    def release_button(self):
        """Release the current button"""
        self.current_button = ButtonEvent.NONE
    
    def is_button_held(self) -> bool:
        """Check if any button is currently held"""
        return self.current_button != ButtonEvent.NONE
    
    def get_last_button(self) -> ButtonEvent:
        """Get the last button that was pressed"""
        return self.last_button
    
    def add_callback(self, callback):
        """Add a callback function for button events"""
        self._callbacks.append(callback)
    
    def remove_callback(self, callback):
        """Remove a callback function"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def _trigger_callbacks(self, button: ButtonEvent):
        """Trigger all registered callbacks"""
        for callback in self._callbacks:
            try:
                callback(button)
            except Exception as e:
                print(f"Error in button callback: {e}")
