#!/usr/bin/env python3
"""
Deploy Arduino code to Pi and flash it to the connected Arduino
"""
import paramiko
import os
import time
import sys

# Configuration
PI_HOST = "192.168.1.23"
PI_USER = "pi"
PI_PASSWORD = "Mototunertanner"
ARDUINO_SRC = r"C:\Users\tanne\Documents\Github\MX5-Telemetry\arduino\src\main.cpp"
PI_ARDUINO_SRC = "/home/pi/MX5-Telemetry/arduino/src/main.cpp"
PI_ARDUINO_DIR = "/home/pi/MX5-Telemetry/arduino"

def run_ssh_command(ssh, command, timeout=60):
    """Execute command over SSH and return output"""
    print(f"  Running: {command}")
    stdin, stdout, stderr = ssh.exec_command(command, timeout=timeout)
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode('utf-8')
    err = stderr.read().decode('utf-8')
    return exit_status, out, err

def main():
    print("=" * 60)
    print("ARDUINO CODE DEPLOYMENT AND FLASH")
    print("=" * 60)
    
    # Connect to Pi
    print("\n[1/5] Connecting to Pi...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(PI_HOST, username=PI_USER, password=PI_PASSWORD, timeout=10)
        print("  ✓ Connected")
    except Exception as e:
        print(f"  ✗ Connection failed: {e}")
        return 1
    
    # Upload main.cpp
    print("\n[2/5] Uploading main.cpp...")
    try:
        sftp = ssh.open_sftp()
        sftp.put(ARDUINO_SRC, PI_ARDUINO_SRC)
        sftp.close()
        print("  ✓ Uploaded")
    except Exception as e:
        print(f"  ✗ Upload failed: {e}")
        ssh.close()
        return 1
    
    # Stop the mx5-display service (it owns the Arduino serial port)
    print("\n[3/5] Stopping mx5-display service...")
    exit_code, out, err = run_ssh_command(ssh, "sudo systemctl stop mx5-display.service")
    if exit_code == 0:
        print("  ✓ Service stopped")
    else:
        print(f"  ⚠ Warning: {err}")
    time.sleep(2)  # Wait for service to fully stop
    
    # Flash Arduino using PlatformIO
    print("\n[4/5] Flashing Arduino (this takes ~30 seconds)...")
    
    # First upload the platformio.ini with correct port
    print("  Uploading platformio.ini...")
    try:
        sftp = ssh.open_sftp()
        local_ini = r"C:\Users\tanne\Documents\Github\MX5-Telemetry\arduino\platformio.ini"
        sftp.put(local_ini, "/home/pi/MX5-Telemetry/arduino/platformio.ini")
        sftp.close()
        print("  ✓ platformio.ini uploaded")
    except Exception as e:
        print(f"  ⚠ Warning: Could not upload platformio.ini: {e}")
    
    print("  Building and uploading firmware...")
    
    # Change to arduino directory and upload
    flash_cmd = f"cd {PI_ARDUINO_DIR} && ~/.local/bin/pio run --target upload"
    exit_code, out, err = run_ssh_command(ssh, flash_cmd, timeout=120)
    
    if exit_code == 0 or "SUCCESS" in out:
        print("  ✓ Arduino flashed successfully!")
        print("\n  Last lines of output:")
        for line in out.split('\n')[-5:]:
            if line.strip():
                print(f"    {line}")
    else:
        print("  ✗ Flash failed!")
        print("\n  Error output:")
        print(err)
        print("\n  Standard output:")
        print(out)
        ssh.close()
        return 1
    
    # Restart the mx5-display service
    print("\n[5/5] Restarting mx5-display service...")
    exit_code, out, err = run_ssh_command(ssh, "sudo systemctl start mx5-display.service")
    if exit_code == 0:
        print("  ✓ Service restarted")
    else:
        print(f"  ✗ Failed to restart: {err}")
    
    time.sleep(3)
    
    # Verify service is running
    exit_code, out, err = run_ssh_command(ssh, "systemctl is-active mx5-display.service")
    if "active" in out:
        print("  ✓ Service is running")
    else:
        print(f"  ⚠ Service status: {out.strip()}")
    
    ssh.close()
    
    print("\n" + "=" * 60)
    print("DEPLOYMENT COMPLETE!")
    print("=" * 60)
    print("\nThe Arduino should now respond to LED sequence commands.")
    print("Test by changing the LED sequence in the webapp.")
    print("\nExpected behavior at RPM=0:")
    print("  SEQ 1 (Center-Out):  Blue on BOTH edges")
    print("  SEQ 2 (Left-Right):  Blue on LEFT edge only")
    print("  SEQ 3 (Right-Left):  Blue on RIGHT edge only")
    print("  SEQ 4 (Center-In):   Blue in CENTER only")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
