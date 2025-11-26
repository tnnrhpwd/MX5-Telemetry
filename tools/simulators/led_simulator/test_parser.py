"""
Quick test to verify the Arduino config parser works.
Run this before starting the simulator to check for issues.
"""

import os
import sys

print("="*70)
print("Testing Arduino LED Config Parser")
print("="*70)

# Test 1: Check if parse script exists
parser_path = os.path.join(os.path.dirname(__file__), 'parse_arduino_led_config.py')
print(f"\n1. Checking parser file: {parser_path}")
if os.path.exists(parser_path):
    print("   ✓ Parser file found")
else:
    print("   ✗ Parser file NOT found")
    sys.exit(1)

# Test 2: Check if LEDStates.h exists
project_root = os.path.dirname(os.path.dirname(__file__))
ledstates_path = os.path.join(project_root, 'lib', 'Config', 'LEDStates.h')
print(f"\n2. Checking Arduino config: {ledstates_path}")
if os.path.exists(ledstates_path):
    print("   ✓ LEDStates.h found")
else:
    print("   ✗ LEDStates.h NOT found")
    sys.exit(1)

# Test 3: Try to import parser
print("\n3. Importing parser module...")
try:
    from parse_arduino_led_config import load_led_config
    print("   ✓ Parser module imported")
except Exception as e:
    print(f"   ✗ Failed to import: {e}")
    sys.exit(1)

# Test 4: Try to load config
print("\n4. Loading LED configuration from Arduino...")
try:
    config = load_led_config()
    print(f"   ✓ Loaded {len(config)} constants")
except Exception as e:
    print(f"   ✗ Failed to load config: {e}")
    sys.exit(1)

# Test 5: Verify key constants exist
print("\n5. Verifying critical constants...")
required = ['STATE_1_RPM_MIN', 'STATE_2_RPM_MIN', 'STATE_3_RPM_MIN', 'STATE_1_MIN_SPEED_KMH']
missing = [k for k in required if k not in config]
if missing:
    print(f"   ✗ Missing constants: {missing}")
    sys.exit(1)
else:
    print("   ✓ All critical constants present")

# Success summary
print("\n" + "="*70)
print("✓ ALL TESTS PASSED")
print("="*70)
print("\nKey values:")
print(f"  State 1 RPM: {config['STATE_1_RPM_MIN']}-{config['STATE_1_RPM_MAX']}")
print(f"  State 2 RPM: {config['STATE_2_RPM_MIN']}-{config['STATE_2_RPM_MAX']}")
print(f"  State 3 RPM: {config['STATE_3_RPM_MIN']}-{config['STATE_3_RPM_MAX']}")
print(f"  Min Speed for State 1: {config['STATE_1_MIN_SPEED_KMH']} km/h")
print("\nSimulator should work correctly!")
print("="*70)
