#!/usr/bin/env python3
"""
Fix CAN0 clock speed issue - force 8MHz oscillator setting
"""

import paramiko
import time

PI_IP = "192.168.1.23"
PI_USER = "pi"
PI_PASS = "Hopwood12"

def run_command(ssh, command):
    """Execute command and print output"""
    print(f"  $ {command}")
    stdin, stdout, stderr = ssh.exec_command(command)
    output = stdout.read().decode()
    error = stderr.read().decode()
    if output:
        print(output)
    if error:
        print(f"    Error: {error}")
    return output, error

print("=" * 70)
print("Fixing CAN0 Clock Speed (4MHz -> 8MHz)")
print("=" * 70)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    print(f"\nConnecting to {PI_IP}...")
    ssh.connect(PI_IP, username=PI_USER, password=PI_PASS, timeout=10)
    print("✓ Connected\n")
    
    print("[1/4] Current can0 status:")
    run_command(ssh, "ip -details link show can0 | grep clock")
    
    print("\n[2/4] Bringing down can0...")
    run_command(ssh, "sudo ip link set can0 down")
    time.sleep(1)
    
    print("\n[3/4] Rebooting Pi to reload MCP2515 with correct 8MHz oscillator...")
    print("       (This is necessary because the oscillator freq is set at boot)")
    
    response = input("\nReboot now? (y/n): ")
    if response.lower() == 'y':
        run_command(ssh, "sudo reboot")
        print("\n✓ Reboot initiated - wait 30 seconds then check can0 again")
        print("\nAfter reboot, run this to verify:")
        print("  ssh pi@192.168.1.23 'ip -details link show can0 | grep clock'")
        print("  Should show: clock 8000000")
    else:
        print("\nSkipped reboot - can0 will continue using wrong clock speed")
        print("Manual fix: ssh into Pi and run 'sudo reboot'")
    
except Exception as e:
    print(f"\n✗ Error: {e}")
finally:
    ssh.close()

print("\n" + "=" * 70)
