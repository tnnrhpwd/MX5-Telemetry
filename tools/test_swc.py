#!/usr/bin/env python3
"""Test SWC handler CAN message processing"""
import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pi', 'ui', 'src'))

from swc_handler import SWCHandler, ButtonEvent, SWC_AUDIO_CAN_ID, SWC_CRUISE_CAN_ID

# Create handler
h = SWCHandler()
print("SWC Handler created")

# Simulate CAN message for VOL_UP (0x240, byte 0 = 0x01)
h.process_can_message(SWC_AUDIO_CAN_ID, bytes([0x01]))
pending = h.poll_buttons()
print(f"After VOL_UP CAN msg: pending={pending}")
assert len(pending) == 1 and pending[0] == ButtonEvent.VOL_UP, "VOL_UP failed!"

# Release button first
time.sleep(0.1)  # Wait for debounce
h.process_can_message(SWC_AUDIO_CAN_ID, bytes([0x00]))
h.poll_buttons()  # Clear any pending

# Simulate CAN message for RES_PLUS (0x250, byte 0 = 0x04)  
time.sleep(0.1)  # Wait for debounce
h.process_can_message(SWC_CRUISE_CAN_ID, bytes([0x04]))
pending = h.poll_buttons()
print(f"After RES_PLUS CAN msg: pending={pending}")
assert len(pending) == 1 and pending[0] == ButtonEvent.RES_PLUS, "RES_PLUS failed!"

# Verify button release detection
time.sleep(0.1)
h.process_can_message(SWC_CRUISE_CAN_ID, bytes([0x00]))  # No buttons
pending = h.poll_buttons()
print(f"After release: pending={pending}")

print("\n✓ SWC Handler Test PASSED!")
