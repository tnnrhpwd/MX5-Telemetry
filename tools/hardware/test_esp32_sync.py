#!/usr/bin/env python3
"""Test ESP32 display screen sync via serial"""
import serial
import time

def main():
    print("Opening serial port...")
    ser = serial.Serial('/dev/ttyACM0', 115200, timeout=1)
    time.sleep(0.5)
    
    # Clear startup messages
    while ser.in_waiting:
        line = ser.readline().decode().strip()
        print(f"  Startup: {line}")
    
    # Test screen changes
    screens = [
        (2, "TPMS"),
        (1, "RPM"),
        (3, "Engine"),
        (4, "G-Force"),
        (0, "Overview"),
    ]
    
    for idx, name in screens:
        print(f"\nSending SCREEN:{idx} ({name})...")
        ser.write(f"SCREEN:{idx}\n".encode())
        time.sleep(0.5)
        
        # Read response
        while ser.in_waiting:
            line = ser.readline().decode().strip()
            print(f"  Response: {line}")
    
    ser.close()
    print("\nTest complete! Check ESP32 display for screen changes.")

if __name__ == "__main__":
    main()
