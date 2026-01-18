#!/usr/bin/env python3
"""
Diagnose why can0 (HS-CAN) is not receiving data on the Pi
"""

import paramiko
import time

PI_IP = "192.168.1.23"
PI_USER = "pi"
PI_PASSWORD = "Hopwood12"

def run_command(ssh, cmd):
    """Run command and return output"""
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=5)
    return stdout.read().decode(), stderr.read().decode()

try:
    print("Connecting to Pi...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(PI_IP, username=PI_USER, password=PI_PASSWORD, timeout=10)
    print("✓ Connected\n")
    
    # Check interface status
    print("=" * 60)
    print("CAN INTERFACE STATUS")
    print("=" * 60)
    
    print("\n📡 can0 (should be HS-CAN @ 500kbps):")
    out, err = run_command(ssh, "ip -details link show can0 2>&1")
    print(out)
    
    print("\n📡 can1 (should be MS-CAN @ 125kbps):")
    out, err = run_command(ssh, "ip -details link show can1 2>&1")
    print(out)
    
    # Check packet statistics
    print("\n" + "=" * 60)
    print("PACKET STATISTICS")
    print("=" * 60)
    
    print("\n📊 can0 packets:")
    out, err = run_command(ssh, "ip -s link show can0 | grep -A 2 'RX:' 2>&1")
    print(out)
    
    print("\n📊 can1 packets:")
    out, err = run_command(ssh, "ip -s link show can1 | grep -A 2 'RX:' 2>&1")
    print(out)
    
    # Check for errors
    print("\n" + "=" * 60)
    print("ERROR COUNTERS")
    print("=" * 60)
    
    print("\n⚠️  can0 errors:")
    out, err = run_command(ssh, "ip -s -d link show can0 | grep -i 'error' 2>&1")
    print(out if out.strip() else "No error info")
    
    print("\n⚠️  can1 errors:")
    out, err = run_command(ssh, "ip -s -d link show can1 | grep -i 'error' 2>&1")
    print(out if out.strip() else "No error info")
    
    # Sample CAN traffic
    print("\n" + "=" * 60)
    print("CAN TRAFFIC SAMPLE (2 seconds each)")
    print("=" * 60)
    
    print("\n🔍 can0 traffic (timeout in 2 sec):")
    try:
        out, err = run_command(ssh, "timeout 2 candump can0 2>&1 | head -10")
        if out.strip():
            print(out)
        else:
            print("❌ NO TRAFFIC on can0!")
    except:
        print("❌ TIMEOUT - no data on can0")
    
    print("\n🔍 can1 traffic (timeout in 2 sec):")
    try:
        out, err = run_command(ssh, "timeout 2 candump can1 2>&1 | head -10")
        if out.strip():
            print(out)
        else:
            print("❌ NO TRAFFIC on can1!")
    except:
        print("❌ TIMEOUT - no data on can1")
    
    # Check for specific CAN IDs we care about
    print("\n" + "=" * 60)
    print("LOOKING FOR SPECIFIC CAN IDs")
    print("=" * 60)
    print("0x201 = RPM/Speed")
    print("0x420 = Coolant Temp")
    print("0x212 = Brake/Oil Status")
    
    print("\n🎯 Searching for 0x201, 0x420, 0x212 on can0 (5 sec):")
    try:
        out, err = run_command(ssh, "timeout 5 candump can0,201:7FF,420:7FF,212:7FF 2>&1")
        if out.strip():
            print(out)
        else:
            print("❌ NO matching CAN IDs found on can0!")
    except:
        print("❌ TIMEOUT - no matching IDs on can0")
    
    print("\n🎯 Searching for 0x201, 0x420, 0x212 on can1 (5 sec):")
    try:
        out, err = run_command(ssh, "timeout 5 candump can1,201:7FF,420:7FF,212:7FF 2>&1")
        if out.strip():
            print(out)
        else:
            print("❌ NO matching CAN IDs found on can1!")
    except:
        print("❌ TIMEOUT - no matching IDs on can1")
    
    # Check MCP2515 dtoverlay
    print("\n" + "=" * 60)
    print("MCP2515 CONFIGURATION")
    print("=" * 60)
    
    print("\n📝 /boot/config.txt MCP2515 settings:")
    out, err = run_command(ssh, "grep mcp2515 /boot/config.txt 2>&1")
    print(out if out.strip() else "❌ No MCP2515 dtoverlay found!")
    
    # Check display app logs
    print("\n" + "=" * 60)
    print("DISPLAY APP LOGS (last 30 lines)")
    print("=" * 60)
    
    out, err = run_command(ssh, "sudo journalctl -u mx5-display.service -n 30 --no-pager 2>&1")
    print(out)
    
    ssh.close()
    
    print("\n" + "=" * 60)
    print("DIAGNOSIS COMPLETE")
    print("=" * 60)
    
except Exception as e:
    print(f"\n❌ Error: {e}")
