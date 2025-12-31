"""
Steering Wheel Control (SWC) Handler for Raspberry Pi

Maps CAN bus steering wheel button messages to UI actions.
Receives button events either from:
1. Direct CAN reading (via MCP2515)
2. Serial from ESP32-S3 (forwarded)

NOTE: Only CRUISE CONTROL buttons are readable on the MS-CAN bus.
Audio/volume buttons (CAN ID 0x240) are NOT accessible.

Navigation scheme (cruise control only):
- RES+ (UP): Previous page / navigate up in settings / increase value in edit mode
- SET- (DOWN): Next page / navigate down in settings / decrease value in edit mode
- ON/OFF: Select setting to edit / confirm edit (HOLD 3s to toggle navigation lock)
- CANCEL: Exit edit mode / go back to overview

Navigation Lock:
- Hold ON/OFF for 3 seconds to toggle navigation lock
- When locked, all button presses are ignored (prevents accidental changes while driving)
- A lock icon appears on ESP32 display to indicate lock status
"""

from enum import Enum, auto
from dataclasses import dataclass
import time

# CAN IDs for steering wheel controls (MS-CAN 125kbps)
# NOTE: Only cruise control buttons (0x250) are readable on the CAN bus
# Audio buttons (0x240) are NOT transmitted on the accessible CAN bus
SWC_CRUISE_CAN_ID = 0x250

# Cruise button masks (CAN ID 0x250, Byte 0)
# These are the ONLY buttons available via CAN bus
SWC_ON_OFF = 0x01      # Select / Enter / Confirm edit (HOLD 3s = toggle lock)
SWC_CANCEL = 0x02      # Back / Exit edit mode
SWC_RES_PLUS = 0x04    # UP - Previous page / Navigate up / Increase value
SWC_SET_MINUS = 0x08   # DOWN - Next page / Navigate down / Decrease value

# Navigation lock hold time (milliseconds)
NAV_LOCK_HOLD_TIME_MS = 3000  # 3 seconds to toggle lock


class ButtonEvent(Enum):
    """Button event types - cruise control buttons only"""
    NONE = auto()
    ON_OFF = auto()      # Select / Enter / Confirm
    CANCEL = auto()      # Back / Exit / Escape
    RES_PLUS = auto()    # UP - Previous page / Navigate up / Increase value
    SET_MINUS = auto()   # DOWN - Next page / Navigate down / Decrease value


# Button names for display
BUTTON_NAMES = {
    ButtonEvent.NONE: "None",
    ButtonEvent.ON_OFF: "SELECT",
    ButtonEvent.CANCEL: "BACK",
    ButtonEvent.RES_PLUS: "UP",
    ButtonEvent.SET_MINUS: "DOWN",
}

# Action descriptions for the cruise-control-only navigation scheme
BUTTON_ACTIONS = {
    ButtonEvent.ON_OFF: "Select setting / Confirm edit (HOLD 3s = toggle lock)",
    ButtonEvent.CANCEL: "Exit edit mode / Back to Overview",
    ButtonEvent.RES_PLUS: "Previous page / Navigate up / Increase value",
    ButtonEvent.SET_MINUS: "Next page / Navigate down / Decrease value",
}


class SWCHandler:
    """Handles steering wheel control button inputs
    
    Features:
    - Debounce and repeat handling for held buttons
    - Navigation lock: Hold ON/OFF for 3 seconds to toggle
    - When locked, all button presses are ignored
    """
    
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
        
        # Navigation lock state
        self.nav_locked = False  # When True, ignore all button presses
        self._on_off_hold_start = 0  # Track when ON/OFF was pressed for lock detection
        self._lock_toggle_pending = False  # Prevent button action after lock toggle
        self._lock_callbacks = []  # Callbacks for lock state changes
    
    def process_can_message(self, can_id: int, data: bytes):
        """Process incoming CAN message for button events
        
        NOTE: Only cruise control buttons (CAN ID 0x250) are available.
        Audio buttons (0x240) are NOT readable on the MS-CAN bus.
        
        Special handling: Hold ON/OFF for 3 seconds to toggle navigation lock.
        """
        if len(data) < 1:
            return
        
        now = time.time() * 1000  # milliseconds
        new_button = ButtonEvent.NONE
        
        # Process cruise buttons ONLY (CAN ID 0x250)
        # Audio buttons (0x240) are NOT available on MS-CAN
        if can_id == SWC_CRUISE_CAN_ID:
            button_byte = data[0]
            if button_byte & SWC_ON_OFF:
                new_button = ButtonEvent.ON_OFF
            elif button_byte & SWC_CANCEL:
                new_button = ButtonEvent.CANCEL
            elif button_byte & SWC_RES_PLUS:
                new_button = ButtonEvent.RES_PLUS
            elif button_byte & SWC_SET_MINUS:
                new_button = ButtonEvent.SET_MINUS
        
        # Track ON/OFF hold time for navigation lock toggle
        if new_button == ButtonEvent.ON_OFF:
            if self._on_off_hold_start == 0:
                # Just started holding ON/OFF
                self._on_off_hold_start = now
            else:
                # Check if held long enough to toggle lock
                hold_duration = now - self._on_off_hold_start
                if hold_duration >= NAV_LOCK_HOLD_TIME_MS and not self._lock_toggle_pending:
                    # Toggle navigation lock
                    self.nav_locked = not self.nav_locked
                    self._lock_toggle_pending = True  # Prevent repeat toggle
                    self._trigger_lock_callbacks(self.nav_locked)
                    print(f"Navigation {'LOCKED' if self.nav_locked else 'UNLOCKED'} (held ON/OFF for {hold_duration/1000:.1f}s)")
        else:
            # ON/OFF released or another button pressed
            if self._on_off_hold_start > 0:
                hold_duration = now - self._on_off_hold_start
                # If released after lock toggle, don't trigger button event
                if self._lock_toggle_pending:
                    self._lock_toggle_pending = False
                    self._on_off_hold_start = 0
                    # Don't queue the ON/OFF button since it was used for lock toggle
                    if new_button == ButtonEvent.NONE:
                        return
            self._on_off_hold_start = 0
            self._lock_toggle_pending = False
        
        # Debounce handling
        if new_button != self.current_button:
            if now - self.debounce_time >= self.DEBOUNCE_MS:
                self.current_button = new_button
                self.debounce_time = now
                
                if new_button != ButtonEvent.NONE:
                    # If navigation is locked, ignore button presses (except for lock toggle)
                    if self.nav_locked and not (new_button == ButtonEvent.ON_OFF):
                        return  # Ignore - navigation is locked
                    
                    # Don't queue ON/OFF immediately - wait to see if it's a hold for lock
                    if new_button == ButtonEvent.ON_OFF:
                        # Will be queued on release if not held for lock toggle
                        pass
                    else:
                        self.last_press_time = now
                        self.button_processed = False
                        # Queue button for main thread processing (CAN runs in background thread)
                        self._pending_buttons.append(new_button)
                else:
                    # Button released - check if ON/OFF should be queued
                    if self.last_button == ButtonEvent.ON_OFF and not self._lock_toggle_pending:
                        # ON/OFF was released without triggering lock - queue it as normal press
                        if not self.nav_locked:
                            self._pending_buttons.append(ButtonEvent.ON_OFF)
                    self.last_button = self.current_button
    
    def poll_buttons(self):
        """Poll for pending button events (call from main loop). Returns list of buttons.
        
        Note: If navigation is locked, this will return empty list (buttons ignored).
        """
        buttons = self._pending_buttons.copy()
        self._pending_buttons.clear()
        return buttons
    
    def get_on_off_hold_progress(self) -> float:
        """Get progress towards lock toggle (0.0 to 1.0)
        
        Returns 0.0 if ON/OFF not held, 1.0 when lock will toggle.
        Can be used to show visual feedback while holding.
        """
        if self._on_off_hold_start == 0:
            return 0.0
        now = time.time() * 1000
        hold_duration = now - self._on_off_hold_start
        return min(1.0, hold_duration / NAV_LOCK_HOLD_TIME_MS)
    
    def is_nav_locked(self) -> bool:
        """Check if navigation is locked"""
        return self.nav_locked
    
    def set_nav_locked(self, locked: bool):
        """Set navigation lock state (for external control/sync)"""
        if locked != self.nav_locked:
            self.nav_locked = locked
            self._trigger_lock_callbacks(locked)
    
    def toggle_nav_lock(self):
        """Toggle navigation lock state"""
        self.set_nav_locked(not self.nav_locked)
    
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
        if self.nav_locked and button != ButtonEvent.ON_OFF:
            return  # Ignore if locked
        self.current_button = button
        self.last_press_time = time.time() * 1000
        self.button_processed = False
        self.debounce_time = time.time() * 1000
        self._pending_buttons.append(button)
    
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
    
    def add_lock_callback(self, callback):
        """Add a callback function for lock state changes
        
        Callback signature: callback(locked: bool)
        """
        self._lock_callbacks.append(callback)
    
    def remove_lock_callback(self, callback):
        """Remove a lock callback function"""
        if callback in self._lock_callbacks:
            self._lock_callbacks.remove(callback)
    
    def _trigger_lock_callbacks(self, locked: bool):
        """Trigger all registered lock callbacks"""
        for callback in self._lock_callbacks:
            try:
                callback(locked)
            except Exception as e:
                print(f"Error in lock callback: {e}")
    
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
