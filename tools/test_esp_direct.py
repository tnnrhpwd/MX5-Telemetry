#!/usr/bin/env python3
"""Direct test of ESP32 serial communication"""
import serial
import time

print("Testing ESP32 serial on /dev/ttyACM0...")
print("Sending test TEL: message and waiting for response\n")

try:
    ser = serial.Serial('/dev/ttyACM0', 115200, timeout=2)
    time.sleep(0.5)  # Let port stabilize
    
    # Send a test telemetry message
    test_msg = "TEL:1234,56,3,78,190,210,14.2,50,0,1\n"
    print(f"Sending: {test_msg.strip()}")
    ser.write(test_msg.encode('utf-8'))
    ser.flush()
    
    # Wait for any response
    print("Waiting for response (5 seconds)...")
    start = time.time()
    responses = []
    
    while (time.time() - start) < 5:
        if ser.in_waiting:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if line:
                responses.append(line)
                print(f"  RX: {line}")
    
    print(f"\n=== RESULTS ===")
    print(f"Responses received: {len(responses)}")
    
    if len(responses) == 0:
        print("\n*** NO RESPONSE FROM ESP32! ***")
        print("Possible issues:")
        print("1. ESP32 is not running/crashed")
        print("2. ESP32 serial port is different")
        print("3. ESP32 USB cable is data-only (no data lines)")
        print("4. ESP32 is in bootloader mode")
        print("\nTry:")
        print("- Check ESP32 display - is it showing anything?")
        print("- Press reset button on ESP32")
        print("- Check USB cable supports data (not just power)")
    else:
        print("ESP32 is responding!")
        
    ser.close()
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
