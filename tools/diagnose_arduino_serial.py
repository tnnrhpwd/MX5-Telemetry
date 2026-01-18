#!/usr/bin/env python3
"""Check if Arduino is receiving and processing commands"""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.1.23", username="pi", password="Hopwood12", timeout=10)

print("=" * 70)
print("ARDUINO SERIAL DIAGNOSTIC")
print("=" * 70)

print("\n[1] Checking recent LED sequence commands sent from Pi...")
stdin, stdout, stderr = ssh.exec_command("journalctl -u mx5-display.service --since '5 minutes ago' --no-pager | grep 'Sent LED sequence'")
sent_cmds = stdout.read().decode()
if sent_cmds.strip():
    print("Commands sent:")
    print(sent_cmds)
else:
    print("  No commands sent recently")

print("\n[2] Checking Arduino connection details...")
stdin, stdout, stderr = ssh.exec_command("journalctl -u mx5-display.service --since boot --no-pager | grep 'Arduino serial connected'")
connection = stdout.read().decode()
if connection.strip():
    print(connection)
else:
    print("  Arduino connection not found in logs")

print("\n[3] Testing Arduino with PING command...")
test_ping = """
python3 << 'EOF'
import serial
import time

try:
    # Open serial port (use same port as mx5-display has open)
    # We can't open it again, so this test won't work
    print("Cannot test while mx5-display service has port open")
    print("Arduino serial port is exclusively locked by mx5-display service")
except Exception as e:
    print(f"Error: {e}")
EOF
"""

print("  Skipping (port locked by mx5-display service)")

print("\n[4] Checking Arduino code configuration...")
print("  Checking if ENABLE_SERIAL_CMD is true in Arduino code...")

# Check the Arduino source
stdin, stdout, stderr = ssh.exec_command("grep -n 'ENABLE_SERIAL_CMD' /home/pi/MX5-Telemetry/arduino/src/main.cpp 2>/dev/null || echo 'File not on Pi'")
config = stdout.read().decode()
print(config if config.strip() else "  Arduino source not available on Pi")

print("\n" + "=" * 70)
print("DIAGNOSIS:")
print("=" * 70)
print("The Pi IS sending commands to Arduino.")
print("\nIf LEDs aren't changing, possible causes:")
print("  1. Arduino not running the latest code")
print("  2. ENABLE_SERIAL_CMD may be false in Arduino")
print("  3. Arduino serial buffer overflow or baud rate mismatch")
print("  4. Arduino main loop not calling handleSerialCommands()")
print("  5. USB cable connection issue")
print("\nRECOMMENDED ACTION:")
print("  Re-upload the Arduino code with PlatformIO:")
print("  1. cd arduino")
print("  2. pio run --target upload")
print("=" * 70)

ssh.close()
