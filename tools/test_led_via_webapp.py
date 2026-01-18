#!/usr/bin/env python3
"""Test LED sequence via webapp API (proper way - no serial conflict)"""
import requests
import time

print("=" * 70)
print("TESTING LED SEQUENCE VIA WEBAPP API")
print("=" * 70)
print("\n⚠️  WATCH YOUR LED STRIP!\n")

sequences = [
    (1, "Center-Out (both edges)"),
    (2, "Left-to-Right (left edge)"),
    (3, "Right-to-Left (right edge)"),
    (4, "Center-In (center)"),
]

for seq_num, seq_name in sequences:
    print(f"\n[Setting SEQ:{seq_num} via webapp] {seq_name}")
    
    try:
        response = requests.post(
            'http://192.168.1.23:5000/api/settings/update',
            json={'name': 'led_sequence', 'value': seq_num},
            timeout=2
        )
        
        if response.status_code == 200:
            print(f"  ✓ Webapp accepted setting change")
            print(f"  → Blue LED(s) should now show: {seq_name}")
        else:
            print(f"  ✗ Error: {response.status_code}")
            
    except Exception as e:
        print(f"  ✗ Failed: {e}")
    
    print("  → Waiting 3 seconds...")
    time.sleep(3)

print("\n" + "=" * 70)
print("✓ Test complete!")
print("\nIf LEDs changed, the webapp LED control is working!")
print("If not, check the Pi logs for errors:")
print("  ssh pi@192.168.1.23")
print("  journalctl -u mx5-display.service -f")
print("=" * 70)
