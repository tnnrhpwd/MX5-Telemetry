#!/usr/bin/env python3
"""Monitor serial data being sent TO ESP32"""
import serial
import time

print("Monitoring serial data TO ESP32...")
print("This shows what the Pi is sending to the ESP32\n")

try:
    # ESP32 is typically on /dev/ttyUSB0 or /dev/ttyACM0
    for port in ['/dev/ttyUSB0', '/dev/ttyACM0', '/dev/ttyUSB1']:
        try:
            ser = serial.Serial(port, 115200, timeout=1)
            print(f"Connected to {port}")
            print("Listening for 10 seconds...\n")
            
            start = time.time()
            line_count = 0
            tel_count = 0
            
            while (time.time() - start) < 10:
                if ser.in_waiting:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        line_count += 1
                        if line.startswith('TEL:'):
                            tel_count += 1
                            print(f"[TEL] {line}")
                        else:
                            print(f"[{time.strftime('%H:%M:%S')}] {line}")
            
            print(f"\n=== SUMMARY ===")
            print(f"Total lines received from ESP32: {line_count}")
            print(f"TEL: messages from Pi (should be ~5/sec): {tel_count}")
            
            if tel_count == 0:
                print("\n*** PROBLEM: No TEL: messages seen! ***")
                print("This means Pi is NOT sending telemetry to ESP32")
                print("Check esp32_handler in Pi UI")
            
            ser.close()
            break
            
        except Exception as e:
            continue
    else:
        print("Could not connect to ESP32 on any port")
        
except KeyboardInterrupt:
    print("\nMonitoring stopped")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
