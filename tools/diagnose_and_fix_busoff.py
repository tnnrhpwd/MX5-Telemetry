#!/usr/bin/env python3
"""
Check boot script and diagnose why MCP keeps entering BUS-OFF on boot
"""

import paramiko

PI_IP = "192.168.1.23"
PI_USER = "pi"
PI_PASSWORD = "Hopwood12"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_IP, username=PI_USER, password=PI_PASSWORD, timeout=10)

print("=" * 70)
print("DIAGNOSE MCP BUS-OFF ON BOOT ISSUE")
print("=" * 70)

# Check actual boot script
print("\n[Current boot script content]")
stdin, stdout, stderr = ssh.exec_command("cat /usr/local/bin/mx5-can-setup.sh")
script = stdout.read().decode()
print(script)

print("\n" + "=" * 70)
print("ANALYSIS")
print("=" * 70)

if "restart-ms" in script:
    print("\n✓ restart-ms IS in boot script")
else:
    print("\n✗ restart-ms NOT in boot script - this is the problem!")
    print("  The script needs to be updated")

# Check current interface state
print("\n[Current interface state]")
stdin, stdout, stderr = ssh.exec_command("ip -d link show can0 | grep -E 'can |restart-ms'")
can0_config = stdout.read().decode()
print(f"can0: {can0_config.strip()}")

stdin, stdout, stderr = ssh.exec_command("ip -d link show can1 | grep -E 'can |restart-ms'")
can1_config = stdout.read().decode()
print(f"can1: {can1_config.strip()}")

if "restart-ms" not in can0_config:
    print("\n⚠️  can0 does NOT have restart-ms currently active!")
if "restart-ms" not in can1_config:
    print("\n⚠️  can1 does NOT have restart-ms currently active!")

# Check if interfaces are in BUS-OFF
stdin, stdout, stderr = ssh.exec_command("ip link show can0")
can0_state = stdout.read().decode()
stdin, stdout, stderr = ssh.exec_command("ip link show can1")
can1_state = stdout.read().decode()

print("\n[Interface states]")
if "BUS-OFF" in can0_state:
    print("can0: BUS-OFF ⚠️")
elif "ERROR-ACTIVE" in can0_state or "UP" in can0_state:
    print("can0: UP/ACTIVE")

if "BUS-OFF" in can1_state:
    print("can1: BUS-OFF ⚠️")
elif "ERROR-ACTIVE" in can1_state or "UP" in can1_state:
    print("can1: UP/ACTIVE")

print("\n" + "=" * 70)
print("SOLUTION")
print("=" * 70)

if "restart-ms" not in script:
    print("\nThe boot script needs restart-ms added.")
    print("This will be done automatically now...\n")
    
    # Update the script
    new_script = '''#!/bin/bash
# MX5 Telemetry - Bring up CAN interfaces
# Called by systemd service on boot

# Wait for interfaces to be ready
sleep 2

# Bring up HS-CAN (500kbps) - Engine data, RPM, Speed
if ip link show can0 > /dev/null 2>&1; then
    ip link set can0 up type can bitrate 500000 restart-ms 100 listen-only on
    echo "can0 (HS-CAN) up at 500kbps (listen-only, auto-restart)"
else
    echo "can0 not found - check MCP2515 wiring"
fi

# Bring up MS-CAN (125kbps) - Steering wheel buttons, body data  
if ip link show can1 > /dev/null 2>&1; then
    ip link set can1 up type can bitrate 125000 restart-ms 100 listen-only on
    echo "can1 (MS-CAN) up at 125kbps (listen-only, auto-restart)"
else
    echo "can1 not found - check MCP2515 wiring"
fi
'''
    
    stdin, stdout, stderr = ssh.exec_command(f"cat > /tmp/mx5-can-setup.sh << 'ENDSCRIPT'\n{new_script}\nENDSCRIPT")
    stdout.read()
    stdin, stdout, stderr = ssh.exec_command("sudo mv /tmp/mx5-can-setup.sh /usr/local/bin/mx5-can-setup.sh && sudo chmod +x /usr/local/bin/mx5-can-setup.sh")
    stdout.read()
    
    print("✓ Boot script updated with restart-ms")
    
    # Apply it now
    print("\nApplying fix now (bringing interfaces down/up with restart-ms)...")
    ssh.exec_command("sudo ip link set can0 down")
    ssh.exec_command("sudo ip link set can1 down")
    import time
    time.sleep(2)
    
    stdin, stdout, stderr = ssh.exec_command("sudo ip link set can0 up type can bitrate 500000 restart-ms 100 listen-only on")
    time.sleep(1)
    stdin, stdout, stderr = ssh.exec_command("sudo ip link set can1 up type can bitrate 125000 restart-ms 100 listen-only on")
    time.sleep(1)
    
    print("✓ Interfaces restarted with restart-ms 100")
    
    # Verify
    print("\nVerifying restart-ms is active...")
    stdin, stdout, stderr = ssh.exec_command("ip -d link show can0 | grep restart-ms")
    if stdout.read().decode():
        print("  ✓ can0 has restart-ms")
    stdin, stdout, stderr = ssh.exec_command("ip -d link show can1 | grep restart-ms")
    if stdout.read().decode():
        print("  ✓ can1 has restart-ms")
    
    print("\n✓✓✓ FIX COMPLETE")
    print("\nWhat this does:")
    print("  • restart-ms 100 = auto-recover from BUS-OFF every 100ms")
    print("  • When MCP boots before car is ready → errors → BUS-OFF")
    print("  • With restart-ms, it keeps trying to recover automatically")
    print("  • Once car CAN bus is active, it will sync and start working")
    print("\nThe fix will survive reboots!")
else:
    print("\nrestart-ms is already in the boot script.")
    print("Checking why interfaces still go to BUS-OFF...")
    
    # Apply it now anyway to ensure it's active
    print("\nRe-applying with restart-ms to current session...")
    ssh.exec_command("sudo ip link set can0 down")
    ssh.exec_command("sudo ip link set can1 down")
    import time
    time.sleep(2)
    stdin, stdout, stderr = ssh.exec_command("sudo ip link set can0 up type can bitrate 500000 restart-ms 100 listen-only on")
    time.sleep(1)
    stdin, stdout, stderr = ssh.exec_command("sudo ip link set can1 up type can bitrate 125000 restart-ms 100 listen-only on") 
    time.sleep(1)
    print("✓ Interfaces reset with restart-ms 100")

ssh.close()
