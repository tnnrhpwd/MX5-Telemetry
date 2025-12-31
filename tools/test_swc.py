#!/usr/bin/env python3
"""Test SWC handler CAN message processing

NOTE: Only cruise control buttons (CAN ID 0x250) are available on MS-CAN.
Audio buttons (CAN ID 0x240) are NOT readable on the CAN bus.
"""
import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pi', 'ui', 'src'))

from swc_handler import SWCHandler, ButtonEvent, SWC_CRUISE_CAN_ID

# Create handler
h = SWCHandler()
print("SWC Handler created")
print("NOTE: Only cruise control buttons are available (RES_PLUS, SET_MINUS, ON_OFF, CANCEL)")

# Test RES_PLUS (0x250, byte 0 = 0x04)
print("\nTesting RES_PLUS (UP)...")
h.process_can_message(SWC_CRUISE_CAN_ID, bytes([0x04]))
pending = h.poll_buttons()
print(f"  After RES_PLUS CAN msg: pending={pending}")
assert len(pending) == 1 and pending[0] == ButtonEvent.RES_PLUS, "RES_PLUS failed!"

# Release button
time.sleep(0.1)
h.process_can_message(SWC_CRUISE_CAN_ID, bytes([0x00]))
h.poll_buttons()

# Test SET_MINUS (0x250, byte 0 = 0x08)
print("Testing SET_MINUS (DOWN)...")
time.sleep(0.1)
h.process_can_message(SWC_CRUISE_CAN_ID, bytes([0x08]))
pending = h.poll_buttons()
print(f"  After SET_MINUS CAN msg: pending={pending}")
assert len(pending) == 1 and pending[0] == ButtonEvent.SET_MINUS, "SET_MINUS failed!"

# Release button
time.sleep(0.1)
h.process_can_message(SWC_CRUISE_CAN_ID, bytes([0x00]))
h.poll_buttons()

# Test ON_OFF (0x250, byte 0 = 0x01)
print("Testing ON_OFF (SELECT)...")
time.sleep(0.1)
h.process_can_message(SWC_CRUISE_CAN_ID, bytes([0x01]))
pending = h.poll_buttons()
print(f"  After ON_OFF CAN msg: pending={pending}")
assert len(pending) == 1 and pending[0] == ButtonEvent.ON_OFF, "ON_OFF failed!"

# Release button
time.sleep(0.1)
h.process_can_message(SWC_CRUISE_CAN_ID, bytes([0x00]))
h.poll_buttons()

# Test CANCEL (0x250, byte 0 = 0x02)
print("Testing CANCEL (BACK)...")
time.sleep(0.1)
h.process_can_message(SWC_CRUISE_CAN_ID, bytes([0x02]))
pending = h.poll_buttons()
print(f"  After CANCEL CAN msg: pending={pending}")
assert len(pending) == 1 and pending[0] == ButtonEvent.CANCEL, "CANCEL failed!"

# Verify button release detection
time.sleep(0.1)
h.process_can_message(SWC_CRUISE_CAN_ID, bytes([0x00]))
pending = h.poll_buttons()
print(f"  After release: pending={pending}")

print("\n✓ SWC Handler Test PASSED!")
print("  All cruise control buttons work correctly.")
print("  (Audio buttons are not available on MS-CAN)")
