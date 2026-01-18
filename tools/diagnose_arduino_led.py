#!/usr/bin/env python3
"""Diagnose Arduino LED sequence control"""
import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.1.23", username="pi", password="Hopwood12", timeout=10)

print("=" * 70)
print("ARDUINO LED SEQUENCE DIAGNOSTIC")
print("=" * 70)

print("\n[1] Checking if Arduino serial port was found on startup...")
stdin, stdout, stderr = ssh.exec_command("journalctl -u mx5-display.service --since '10 minutes ago' --no-pager | grep -i 'arduino'")
arduino_logs = stdout.read().decode()
if arduino_logs.strip():
    print(arduino_logs)
else:
    print("  No Arduino serial connection messages found")
    print("  This means Arduino is not connected or not responding")

print("\n[2] Checking available serial ports...")
stdin, stdout, stderr = ssh.exec_command("ls -l /dev/serial* /dev/ttyUSB* /dev/ttyAMA* 2>/dev/null")
ports = stdout.read().decode()
if ports.strip():
    print(ports)
else:
    print("  No serial ports found")

print("\n[3] Checking if LED sequence commands are being sent...")
stdin, stdout, stderr = ssh.exec_command("journalctl -u mx5-display.service --since '10 minutes ago' --no-pager | grep -i 'LED sequence'")
led_logs = stdout.read().decode()
if led_logs.strip():
    print("Recent LED sequence commands:")
    print(led_logs)
else:
    print("  No LED sequence commands found in logs")

print("\n[4] Testing Arduino connection manually...")
test_script = """
python3 << 'EOF'
import serial
import time

ports = ['/dev/serial0', '/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyAMA0']
for port in ports:
    try:
        ser = serial.Serial(port, 9600, timeout=0.1)
        print(f"✓ Connected to {port}")
        
        # Send test command
        ser.write(b"SEQ:2\\n")
        print(f"  Sent: SEQ:2")
        
        # Wait and check for response
        time.sleep(0.2)
        if ser.in_waiting:
            response = ser.read(ser.in_waiting).decode()
            print(f"  Response: {response}")
        else:
            print(f"  No response (Arduino may not echo)")
        
        ser.close()
        break
    except Exception as e:
        print(f"✗ {port}: {e}")
EOF
"""

stdin, stdout, stderr = ssh.exec_command(test_script)
test_result = stdout.read().decode()
test_error = stderr.read().decode()
print(test_result)
if test_error.strip():
    print("Errors:", test_error)

print("\n" + "=" * 70)
print("TROUBLESHOOTING:")
print("=" * 70)
print("If Arduino not found:")
print("  1. Check Arduino is powered and connected to Pi")
print("  2. Check USB cable or GPIO UART wiring")
print("  3. Arduino code must be uploaded and running")
print("  4. Arduino must accept 'SEQ:X\\n' commands")

ssh.close()
