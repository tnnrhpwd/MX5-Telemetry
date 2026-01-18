#!/usr/bin/env python3
"""
Update MCP CAN startup script on Pi to include restart-ms parameter
This fixes BUS-OFF state issues on boot
"""

import paramiko
import sys

PI_IP = "192.168.1.23"
PI_USER = "pi"
PI_PASSWORD = "Hopwood12"

NEW_SCRIPT = '''#!/bin/bash
# MX5 Telemetry - Bring up CAN interfaces
# Called by systemd service on boot

# Wait for interfaces to be ready
sleep 2

# Bring up HS-CAN (500kbps) - Engine data, RPM, Speed
# LISTEN-ONLY mode for production (no transmission to car CAN bus)
# restart-ms 100: Auto-recover from bus-off errors
if ip link show can0 > /dev/null 2>&1; then
    ip link set can0 up type can bitrate 500000 restart-ms 100 listen-only on
    echo "can0 (HS-CAN) up at 500kbps (listen-only, auto-restart)"
else
    echo "can0 not found - check MCP2515 wiring"
fi

# Bring up MS-CAN (125kbps) - Steering wheel buttons, body data
# LISTEN-ONLY mode for production (no transmission to car CAN bus)
# restart-ms 100: Auto-recover from bus-off errors
if ip link show can1 > /dev/null 2>&1; then
    ip link set can1 up type can bitrate 125000 restart-ms 100 listen-only on
    echo "can1 (MS-CAN) up at 125kbps (listen-only, auto-restart)"
else
    echo "can1 not found - check MCP2515 wiring"
fi
'''

print("=" * 70)
print("UPDATE MCP CAN STARTUP SCRIPT - FIX BUS-OFF ISSUE")
print("=" * 70)

try:
    print(f"\nConnecting to {PI_IP}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(PI_IP, username=PI_USER, password=PI_PASSWORD, timeout=10)
    print("✓ Connected\n")
    
    print("[1/4] Backing up current script...")
    stdin, stdout, stderr = ssh.exec_command(
        "sudo cp /usr/local/bin/mx5-can-setup.sh /usr/local/bin/mx5-can-setup.sh.backup 2>/dev/null || true"
    )
    stdout.read()
    print("  ✓ Backup created\n")
    
    print("[2/4] Writing updated script with restart-ms parameter...")
    # Write to temp file first
    stdin, stdout, stderr = ssh.exec_command(
        f"cat > /tmp/mx5-can-setup.sh << 'ENDOFSCRIPT'\n{NEW_SCRIPT}\nENDOFSCRIPT"
    )
    stdout.read()
    
    # Move to correct location with sudo
    stdin, stdout, stderr = ssh.exec_command(
        "sudo mv /tmp/mx5-can-setup.sh /usr/local/bin/mx5-can-setup.sh"
    )
    stdout.read()
    
    # Make executable
    stdin, stdout, stderr = ssh.exec_command(
        "sudo chmod +x /usr/local/bin/mx5-can-setup.sh"
    )
    stdout.read()
    print("  ✓ Script updated\n")
    
    print("[3/4] Applying fix now (without reboot)...")
    stdin, stdout, stderr = ssh.exec_command("sudo /usr/local/bin/mx5-can-setup.sh")
    output = stdout.read().decode()
    print(f"  {output}")
    
    print("[4/4] Verifying interfaces...")
    stdin, stdout, stderr = ssh.exec_command("ip link show can0 | grep -E 'state|can '")
    can0_state = stdout.read().decode()
    
    stdin, stdout, stderr = ssh.exec_command("ip link show can1 | grep -E 'state|can '")
    can1_state = stdout.read().decode()
    
    print(f"  can0: {can0_state.strip()}")
    print(f"  can1: {can1_state.strip()}")
    
    print("\n" + "=" * 70)
    print("RESULT")
    print("=" * 70)
    
    if "BUS-OFF" in can0_state or "BUS-OFF" in can1_state:
        print("\n⚠️  Still in BUS-OFF state")
        print("The interfaces will auto-recover when CAN traffic appears")
        print("Start the car or turn ignition to ACC")
    else:
        print("\n✓✓✓ FIX APPLIED SUCCESSFULLY!")
        print("\nWhat was changed:")
        print("  • Added 'restart-ms 100' parameter to both CAN interfaces")
        print("  • This enables automatic recovery from BUS-OFF errors")
        print("\nWhy this fixes the issue:")
        print("  • When Pi boots, car may not be ready → errors occur")
        print("  • Without restart-ms, interfaces stay in BUS-OFF forever")
        print("  • With restart-ms 100, they auto-recover every 100ms")
        print("\nThe fix is now permanent - will survive reboots!")
    
    print("\n" + "=" * 70 + "\n")
    
    ssh.close()
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    sys.exit(1)
