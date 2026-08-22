can#!/usr/bin/env python3
"""
Live CAN0 (HS-CAN) Diagnostic Tool
Connects to Pi and monitors can0 traffic in real-time to diagnose why coolant/oil data isn't working
"""

import sys
import subprocess
import time

PI_IP = "192.168.1.23"  # MX5 display Pi

def run_ssh_command(command, timeout=5):
    """Execute command via SSH and return output"""
    try:
        result = subprocess.run(
            ["ssh", f"pi@{PI_IP}", command],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return None, "Command timed out", -1
    except Exception as e:
        return None, str(e), -1

def main():
    print("=" * 70)
    print("MX5 Telemetry - Live CAN0 Diagnostic")
    print("=" * 70)
    print(f"Connecting to Pi at {PI_IP}...")
    print()
    
    # Check if can0 exists
    print("[1/5] Checking can0 interface status...")
    stdout, stderr, code = run_ssh_command("ip link show can0")
    if code != 0:
        print(f"  ✗ can0 not found: {stderr}")
        return
    print(f"  ✓ can0 exists")
    print(f"     {stdout.strip()}")
    print()
    
    # Check if can0 is UP
    print("[2/5] Checking if can0 is UP...")
    if "UP" in stdout:
        print("  ✓ can0 is UP")
    else:
        print("  ✗ can0 is DOWN - attempting to bring it up...")
        stdout, stderr, code = run_ssh_command(
            "sudo ip link set can0 up type can bitrate 500000 listen-only on restart-ms 100"
        )
        if code == 0:
            print("  ✓ can0 brought up successfully")
        else:
            print(f"  ✗ Failed to bring up can0: {stderr}")
            return
    print()
    
    # Check for errors on interface
    print("[3/5] Checking can0 error counters...")
    stdout, stderr, code = run_ssh_command("ip -details -statistics link show can0")
    if code == 0:
        print(stdout)
    print()
    
    # Check packet count
    print("[4/5] Checking can0 packet statistics...")
    stdout, stderr, code = run_ssh_command("ifconfig can0 | grep 'RX packets'")
    if code == 0:
        print(f"  {stdout.strip()}")
    print()
    
    # Monitor live traffic for 10 seconds
    print("[5/5] Monitoring live can0 traffic for 10 seconds...")
    print("       Looking for HS-CAN IDs: 0x201 (RPM), 0x420 (coolant/oil), 0x200 (throttle)")
    print()
    
    # Use timeout to automatically stop after 10 seconds
    stdout, stderr, code = run_ssh_command("timeout 10 candump can0", timeout=15)
    
    if stdout:
        lines = stdout.strip().split('\n')
        
        # Count messages by ID
        message_counts = {}
        found_engine_ids = False
        
        for line in lines:
            if 'can0' in line:
                parts = line.split()
                if len(parts) >= 2:
                    can_id = parts[1].split('#')[0]
                    message_counts[can_id] = message_counts.get(can_id, 0) + 1
                    
                    # Check for important engine IDs
                    if can_id in ['201', '0x201', '420', '0x420', '200', '0x200']:
                        found_engine_ids = True
        
        print(f"  Total messages received: {len(lines)}")
        print()
        print("  Message breakdown by CAN ID:")
        for can_id, count in sorted(message_counts.items(), key=lambda x: x[1], reverse=True)[:20]:
            indicator = "  ⭐" if can_id in ['201', '0x201', '420', '0x420', '200', '0x200'] else ""
            print(f"    {can_id}: {count} messages{indicator}")
        
        print()
        if found_engine_ids:
            print("  ✓ GOOD: Found HS-CAN engine data (0x201, 0x420, etc.)")
            print("  → Issue is likely in Python CAN handler parsing")
        else:
            print("  ✗ PROBLEM: No engine data IDs detected!")
            print("  → Possible causes:")
            print("    1. Wrong bitrate (should be 500kbps)")
            print("    2. MCP2515 not receiving data despite good wiring")
            print("    3. CAN bus in bus-off or error state")
            print("    4. Wrong oscillator frequency setting")
        
        # Show sample messages
        if lines:
            print()
            print("  Sample messages (first 5):")
            for line in lines[:5]:
                print(f"    {line}")
    
    else:
        print(f"  ✗ No data received from can0")
        if stderr:
            print(f"     Error: {stderr}")
        print()
        print("  Possible causes:")
        print("    - candump not installed (install: sudo apt-get install can-utils)")
        print("    - SSH connection issues")
        print("    - can0 interface not properly configured")
    
    print()
    print("=" * 70)
    print("Diagnostic complete!")
    print("=" * 70)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDiagnostic interrupted by user")
        sys.exit(0)
