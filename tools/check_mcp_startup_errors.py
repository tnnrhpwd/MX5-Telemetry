#!/usr/bin/env python3
"""
Check MCP2515 and CAN service startup logs for errors
"""

import paramiko
import sys

PI_IP = "192.168.1.23"
PI_USER = "pi"
PI_PASSWORD = "Hopwood12"

print("=" * 70)
print("MCP2515 STARTUP ERROR CHECKER")
print("=" * 70)

try:
    print(f"\nConnecting to {PI_IP}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(PI_IP, username=PI_USER, password=PI_PASSWORD, timeout=10)
    print("✓ Connected\n")
    
    # Check mx5-can.service status
    print("\n" + "=" * 70)
    print("MX5-CAN SERVICE STATUS")
    print("=" * 70)
    stdin, stdout, stderr = ssh.exec_command("systemctl status mx5-can.service --no-pager")
    output = stdout.read().decode()
    print(output)
    
    # Check mx5-can.service logs
    print("\n" + "=" * 70)
    print("MX5-CAN SERVICE LOGS (Last 30 lines)")
    print("=" * 70)
    stdin, stdout, stderr = ssh.exec_command("journalctl -u mx5-can.service -n 30 --no-pager")
    output = stdout.read().decode()
    print(output)
    
    # Check dmesg for MCP2515 errors
    print("\n" + "=" * 70)
    print("KERNEL LOG - MCP2515 RELATED (Last 20 entries)")
    print("=" * 70)
    stdin, stdout, stderr = ssh.exec_command("dmesg | grep -iE 'mcp2515|spi|can' | tail -20")
    output = stdout.read().decode()
    print(output)
    
    # Check for common error patterns
    print("\n" + "=" * 70)
    print("SEARCHING FOR COMMON ERRORS")
    print("=" * 70)
    
    # Check for SPI errors
    stdin, stdout, stderr = ssh.exec_command("dmesg | grep -i 'spi' | grep -iE 'error|fail|timeout'")
    spi_errors = stdout.read().decode()
    if spi_errors:
        print("\n⚠️  SPI ERRORS FOUND:")
        print(spi_errors)
    else:
        print("  ✓ No SPI errors found")
    
    # Check for MCP2515 errors
    stdin, stdout, stderr = ssh.exec_command("dmesg | grep -i 'mcp2515' | grep -iE 'error|fail'")
    mcp_errors = stdout.read().decode()
    if mcp_errors:
        print("\n⚠️  MCP2515 ERRORS FOUND:")
        print(mcp_errors)
    else:
        print("  ✓ No MCP2515 errors found")
    
    # Check for CAN interface errors
    stdin, stdout, stderr = ssh.exec_command("dmesg | grep -iE 'can0|can1' | grep -iE 'error|fail'")
    can_errors = stdout.read().decode()
    if can_errors:
        print("\n⚠️  CAN INTERFACE ERRORS FOUND:")
        print(can_errors)
    else:
        print("  ✓ No CAN interface errors found")
    
    # Check boot config
    print("\n" + "=" * 70)
    print("BOOT CONFIGURATION CHECK")
    print("=" * 70)
    stdin, stdout, stderr = ssh.exec_command("grep -A 15 'MX5-Telemetry CAN Bus Configuration' /boot/config.txt")
    config = stdout.read().decode()
    if config:
        print("Current configuration in /boot/config.txt:")
        print(config)
    else:
        print("⚠️  MX5 CAN configuration not found in /boot/config.txt!")
        print("   You may need to run: sudo bash pi/setup_can_bus.sh")
    
    # Suggestions
    print("\n" + "=" * 70)
    print("RECOMMENDATIONS")
    print("=" * 70)
    
    if spi_errors or mcp_errors or can_errors:
        print("\n⚠️  Errors detected. Common solutions:")
        print("\n1. HARDWARE CHECK:")
        print("   • Verify all MCP2515 connections (VCC, GND, MOSI, MISO, SCK, CS, INT)")
        print("   • Check for loose wires or poor connections")
        print("   • Ensure 3.3V power supply (NOT 5V!)")
        print("\n2. SOFTWARE FIX:")
        print("   • Run: python tools/quick_reset_mcp.py")
        print("   • Or reboot Pi: python tools/reboot_pi.py")
        print("\n3. IF PERSISTENT:")
        print("   • Re-run setup: sudo bash pi/setup_can_bus.sh")
        print("   • Check oscillator frequency (should be 8MHz)")
    else:
        print("\n✓ No errors found in logs!")
        print("\nIf CAN still not working:")
        print("  • Run: python tools/quick_reset_mcp.py")
        print("  • Ensure car ignition is in ACC or ON")
        print("  • Check CAN-H and CAN-L wiring to OBD-II port")
    
    print("\n" + "=" * 70 + "\n")
    
    ssh.close()
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    sys.exit(1)
