#!/usr/bin/env python3
"""
Verify and fix telemetry_data.py on Pi
"""

import paramiko

PI_IP = "192.168.1.23"
PI_USER = "pi"
PI_PASSWORD = "Hopwood12"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_IP, username=PI_USER, password=PI_PASSWORD, timeout=10)

print("=" * 70)
print("CHECKING TELEMETRY_DATA.PY ON PI")
print("=" * 70)

# Check what's actually in the file
stdin, stdout, stderr = ssh.exec_command("grep -n 'oil' /home/pi/MX5-Telemetry/pi/ui/src/telemetry_data.py | head -10")
current = stdout.read().decode()
print("\nCurrent oil-related lines:")
print(current)

if "oil_status" not in current:
    print("\n⚠️  oil_status NOT found! File wasn't updated.")
    print("\nFixing now with sed command...")
    
    # Use sed to fix the file directly on the Pi
    commands = [
        # Remove oil_temp_f line
        "sed -i '/oil_temp_f.*=.*0/d' /home/pi/MX5-Telemetry/pi/ui/src/telemetry_data.py",
        # Replace oil_pressure_ok with oil_status
        "sed -i 's/oil_pressure_ok: bool = False/oil_status: bool = False/' /home/pi/MX5-Telemetry/pi/ui/src/telemetry_data.py",
        # Remove oil_warn_f line
        "sed -i '/oil_warn_f.*=.*250/d' /home/pi/MX5-Telemetry/pi/ui/src/telemetry_data.py",
    ]
    
    for cmd in commands:
        stdin, stdout, stderr = ssh.exec_command(cmd)
        stdout.read()
    
    print("  ✓ Fixed with sed")
    
    # Verify
    stdin, stdout, stderr = ssh.exec_command("grep -n 'oil' /home/pi/MX5-Telemetry/pi/ui/src/telemetry_data.py | head -10")
    new_content = stdout.read().decode()
    print("\nUpdated oil-related lines:")
    print(new_content)
    
    if "oil_status" in new_content:
        print("\n✓ File is now fixed!")
        print("\nRestarting service...")
        stdin, stdout, stderr = ssh.exec_command("sudo systemctl restart mx5-display")
        stdout.read()
        
        import time
        time.sleep(5)
        
        print("\nChecking for errors...")
        stdin, stdout, stderr = ssh.exec_command("journalctl -u mx5-display.service --since '5 seconds ago' --no-pager | grep -i 'oil_status'")
        errors = stdout.read().decode()
        
        if errors:
            print("✗ Still errors:")
            print(errors)
        else:
            print("✓ No more oil_status errors!")
    else:
        print("\n✗ Fix failed")
else:
    print("\n✓ oil_status exists in file")

ssh.close()
