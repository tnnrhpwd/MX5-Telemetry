#!/usr/bin/env python3
"""Test LED sequence commands with Arduino feedback"""
import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.1.23", username="pi", password="Hopwood12", timeout=10)

test_script = '''
python3 << 'EOF'
import serial
import time

print("Testing Arduino LED sequence control...")
print("=" * 60)

try:
    ser = serial.Serial('/dev/ttyUSB0', 9600, timeout=1)
    print(f"✓ Connected to /dev/ttyUSB0\\n")
    
    # Wait for Arduino to stabilize
    time.sleep(0.5)
    
    # Clear any pending data
    if ser.in_waiting:
        ser.read(ser.in_waiting)
    
    # Test 1: Query current sequence
    print("[Test 1] Querying current sequence...")
    ser.write(b"SEQ?\\n")
    time.sleep(0.2)
    if ser.in_waiting:
        response = ser.read(ser.in_waiting).decode().strip()
        print(f"  Response: {response}")
    else:
        print("  No response")
    
    # Test 2: Set sequence to 2 (Left-to-Right)
    print("\\n[Test 2] Setting sequence to 2 (Left-to-Right)...")
    ser.write(b"SEQ:2\\n")
    time.sleep(0.2)
    if ser.in_waiting:
        response = ser.read(ser.in_waiting).decode().strip()
        print(f"  Response: {response}")
    else:
        print("  No response")
    
    # Test 3: Set sequence to 4 (Center-In)
    print("\\n[Test 3] Setting sequence to 4 (Center-In)...")
    ser.write(b"SEQ:4\\n")
    time.sleep(0.2)
    if ser.in_waiting:
        response = ser.read(ser.in_waiting).decode().strip()
        print(f"  Response: {response}")
    else:
        print("  No response")
    
    # Test 4: Set sequence back to 1 (Center-Out - default)
    print("\\n[Test 4] Setting sequence to 1 (Center-Out - default)...")
    ser.write(b"SEQ:1\\n")
    time.sleep(0.2)
    if ser.in_waiting:
        response = ser.read(ser.in_waiting).decode().strip()
        print(f"  Response: {response}")
    else:
        print("  No response")
    
    # Test 5: PING test
    print("\\n[Test 5] Sending PING...")
    ser.write(b"PING\\n")
    time.sleep(0.2)
    if ser.in_waiting:
        response = ser.read(ser.in_waiting).decode().strip()
        print(f"  Response: {response}")
    else:
        print("  No response")
    
    ser.close()
    
    print("\\n" + "=" * 60)
    print("Tests complete!")
    print("\\nIf you see responses, Arduino is working correctly.")
    print("If no responses, check:")
    print("  1. Arduino code uploaded and running")
    print("  2. ENABLE_SERIAL_CMD is true in Arduino code")
    print("  3. Baud rate matches (9600)")
    
except Exception as e:
    print(f"Error: {e}")
EOF
'''

stdin, stdout, stderr = ssh.exec_command(test_script)
output = stdout.read().decode()
error = stderr.read().decode()

print(output)
if error.strip():
    print("Errors:", error)

ssh.close()
