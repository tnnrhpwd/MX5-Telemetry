#!/usr/bin/env python3
"""Simple Arduino LED test"""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.1.23", username="pi", password="Hopwood12", timeout=10)

print("Sending test commands to Arduino...")

# Test with Python one-liner
cmd = "python3 -c 'import serial; s=serial.Serial(\"/dev/ttyUSB0\",9600,timeout=0.5); s.write(b\"SEQ:2\\\\n\"); import time; time.sleep(0.3); print(\"Sent: SEQ:2\"); r=s.read(100); print(f\"Response: {r}\") if r else print(\"No response\"); s.close()'"

stdin, stdout, stderr = ssh.exec_command(cmd, timeout=5)
output = stdout.read().decode()
print(output)

print("\n✓ Command sent. Check if LEDs changed pattern.")
print("\nThe LED sequence should now be:")
print("  SEQ:1 = Center-Out (default)")
print("  SEQ:2 = Left-to-Right")
print("  SEQ:3 = Right-to-Left")
print("  SEQ:4 = Center-In")

ssh.close()
