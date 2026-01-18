#!/usr/bin/env python3
"""Test LED sequence changes - watch the LEDs while running this!"""
import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.1.23", username="pi", password="Hopwood12", timeout=10)

print("=" * 70)
print("LED SEQUENCE VISUAL TEST")
print("=" * 70)
print("\n⚠️  WATCH YOUR LED STRIP - It should change every 3 seconds!\n")
print("At RPM=0, you should see:")
print("  SEQ 1 (Center-Out): Blue on BOTH edges")
print("  SEQ 2 (Left-Right):  Blue on LEFT edge only")
print("  SEQ 3 (Right-Left):  Blue on RIGHT edge only")
print("  SEQ 4 (Center-In):   Blue in CENTER only")
print("\n" + "=" * 70)

sequences = [
    (1, "Center-Out (both edges)"),
    (2, "Left-to-Right (left edge)"),
    (3, "Right-to-Left (right edge)"),
    (4, "Center-In (center)"),
]

for seq_num, seq_name in sequences:
    print(f"\n[Sending SEQ:{seq_num}] {seq_name}")
    
    cmd = f'python3 -c "import serial; s=serial.Serial(\\"/dev/ttyUSB0\\",9600,timeout=0.1); s.write(b\\"SEQ:{seq_num}\\\\n\\"); s.close()"'
    stdin, stdout, stderr = ssh.exec_command(cmd)
    stdout.read()
    
    print(f"  → Blue LED(s) should now show: {seq_name}")
    print("  → Waiting 3 seconds...")
    time.sleep(3)

print("\n" + "=" * 70)
print("✓ Test complete!")
print("\nIf LEDs changed, the system is working correctly!")
print("If no changes, check:")
print("  1. Arduino is powered on")
print("  2. LED strip is connected")
print("  3. USB cable between Pi and Arduino is connected")
print("=" * 70)

ssh.close()
