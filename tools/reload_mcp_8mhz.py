#!/usr/bin/env python3
"""
Manually reload MCP2515 with correct 8MHz oscillator using dtoverlay command
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
    if error and 'warning' not in error.lower():
        print(f"    Error: {error}")
    return output, error

print("=" * 70)
print("Manually Loading MCP2515 with 8MHz Oscillator")
print("=" * 70)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    print(f"\nConnecting to {PI_IP}...")
    ssh.connect(PI_IP, username=PI_USER, password=PI_PASS, timeout=10)
    print("✓ Connected\n")
    
    print("[1/6] Stopping MX5 display service...")
    run_command(ssh, "sudo systemctl stop mx5-display")
    time.sleep(2)
    
    print("\n[2/6] Bringing down CAN interfaces...")
    run_command(ssh, "sudo ip link set can0 down")
    run_command(ssh, "sudo ip link set can1 down")
    time.sleep(1)
    
    print("\n[3/6] Removing old MCP2515 module...")
    run_command(ssh, "sudo modprobe -r mcp251x")
    time.sleep(1)
    
    print("\n[4/6] Manually loading MCP2515 overlays with 8MHz...")
    run_command(ssh, "sudo dtoverlay mcp2515-can0 oscillator=8000000 interrupt=25")
    time.sleep(1)
    run_command(ssh, "sudo dtoverlay mcp2515-can1 oscillator=8000000 interrupt=24")
    time.sleep(2)
    
    print("\n[5/6] Bringing up CAN interfaces...")
    run_command(ssh, "sudo ip link set can0 up type can bitrate 500000 restart-ms 100 listen-only on")
    run_command(ssh, "sudo ip link set can1 up type can bitrate 125000 restart-ms 100 listen-only on")
    time.sleep(1)
    
    print("\n[6/6] Checking can0 clock speed...")
    output, _ = run_command(ssh, "ip -details link show can0 | grep clock")
    
    if "clock 8000000" in output:
        print("\n✓ SUCCESS! can0 now has 8MHz clock")
        print("\nRestarting MX5 display service...")
        run_command(ssh, "sudo systemctl start mx5-display")
        print("\n✓ Check coolant/oil data - should now be working!")
    else:
        print("\n✗ FAILED - clock still wrong")
        print("Output:", output)
    
except Exception as e:
    print(f"\n✗ Error: {e}")
finally:
    ssh.close()

print("\n" + "=" * 70)
