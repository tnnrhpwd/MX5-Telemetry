#!/usr/bin/env python3
"""
Deploy fixed oil_status code to Pi and restart display app
"""

import paramiko
import os

PI_IP = "192.168.1.23"
PI_USER = "pi"
PI_PASSWORD = "Hopwood12"

FILES_TO_UPDATE = [
    ("pi/ui/src/telemetry_data.py", "/home/pi/MX5-Telemetry/pi/ui/src/telemetry_data.py"),
    ("pi/ui/src/can_handler.py", "/home/pi/MX5-Telemetry/pi/ui/src/can_handler.py"),
    ("pi/ui/src/esp32_serial_handler.py", "/home/pi/MX5-Telemetry/pi/ui/src/esp32_serial_handler.py"),
    ("pi/ui/src/web_server.py", "/home/pi/MX5-Telemetry/pi/ui/src/web_server.py"),
]

print("=" * 70)
print("DEPLOY OIL STATUS FIX TO PI")
print("=" * 70)

try:
    print(f"\nConnecting to {PI_IP}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(PI_IP, username=PI_USER, password=PI_PASSWORD, timeout=10)
    sftp = ssh.open_sftp()
    print("✓ Connected\n")
    
    # Get base directory
    base_dir = "C:\\Users\\tanne\\Documents\\Github\\MX5-Telemetry"
    
    print("[1/3] Uploading fixed files...")
    for local_path, remote_path in FILES_TO_UPDATE:
        full_local = os.path.join(base_dir, local_path)
        print(f"  Uploading {local_path}...")
        sftp.put(full_local, remote_path)
        print(f"    ✓ {os.path.basename(local_path)}")
    
    sftp.close()
    print("  ✓ All files uploaded\n")
    
    print("[2/3] Stopping display application...")
    stdin, stdout, stderr = ssh.exec_command("pkill -f 'python3.*main.py'")
    stdout.read()
    print("  ✓ Display app stopped\n")
    
    print("[3/3] Starting display application...")
    stdin, stdout, stderr = ssh.exec_command(
        "cd /home/pi/MX5-Telemetry/pi/ui/src && nohup python3 main.py --fullscreen > /tmp/display.log 2>&1 &"
    )
    stdout.read()
    print("  ✓ Display app started\n")
    
    print("Waiting 3 seconds for app to initialize...")
    import time
    time.sleep(3)
    
    print("\nChecking if app is running...")
    stdin, stdout, stderr = ssh.exec_command("ps aux | grep '[m]ain.py'")
    output = stdout.read().decode()
    if output:
        print("  ✓ Display app is running!")
    else:
        print("  ✗ Display app failed to start")
        print("\nCheck logs:")
        stdin, stdout, stderr = ssh.exec_command("tail -20 /tmp/display.log")
        print(stdout.read().decode())
    
    print("\n" + "=" * 70)
    print("DEPLOYMENT COMPLETE")
    print("=" * 70)
    print("\nFixed issues:")
    print("  • Removed oil_temp_f (not available on your car)")
    print("  • Removed oil_warn_f threshold")
    print("  • Changed oil_pressure_ok → oil_status")
    print("  • Oil is now simple TRUE/FALSE boolean")
    print("\nThe display should now show correct data!")
    print("=" * 70 + "\n")
    
    ssh.close()
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
