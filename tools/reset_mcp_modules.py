#!/usr/bin/env python3
"""
MCP2515 Module Reset and Diagnostic Tool
Resets CAN interfaces and checks for startup errors
"""

import paramiko
import time
import sys

# Connection details
PI_IP = "192.168.1.23"
PI_USER = "pi"
PI_PASSWORD = "Hopwood12"

def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def execute_command(ssh, command, description, timeout=10):
    """Execute SSH command and return output"""
    print(f"\n→ {description}")
    print(f"  Command: {command}")
    stdin, stdout, stderr = ssh.exec_command(command, timeout=timeout, get_pty=True)
    
    output = stdout.read().decode()
    error = stderr.read().decode()
    
    if output:
        print(f"  Output:\n{output}")
    if error and "WARNING" not in error:
        print(f"  Error: {error}")
    
    return output, error

def check_dmesg_errors(ssh):
    """Check kernel log for MCP2515 errors"""
    print_section("CHECKING KERNEL LOG FOR MCP2515 ERRORS")
    
    cmd = "dmesg | grep -i 'mcp2515\\|can\\|spi' | tail -30"
    output, _ = execute_command(ssh, cmd, "Searching dmesg for CAN/SPI errors")
    
    if "error" in output.lower() or "fail" in output.lower():
        print("\n⚠️  ERRORS DETECTED IN KERNEL LOG!")
        return False
    else:
        print("\n✓ No critical errors in kernel log")
        return True

def check_interfaces(ssh):
    """Check if CAN interfaces exist"""
    print_section("CHECKING CAN INTERFACES")
    
    output, _ = execute_command(ssh, "ip link show", "Listing network interfaces")
    
    has_can0 = "can0" in output
    has_can1 = "can1" in output
    
    print(f"\n  can0 (HS-CAN): {'✓ FOUND' if has_can0 else '✗ MISSING'}")
    print(f"  can1 (MS-CAN): {'✓ FOUND' if has_can1 else '✗ MISSING'}")
    
    return has_can0, has_can1

def reset_can_interfaces(ssh):
    """Reset CAN interfaces"""
    print_section("RESETTING CAN INTERFACES")
    
    # Bring down interfaces
    execute_command(ssh, "sudo ip link set can0 down 2>/dev/null || true", 
                   "Bringing down can0")
    execute_command(ssh, "sudo ip link set can1 down 2>/dev/null || true", 
                   "Bringing down can1")
    
    time.sleep(2)
    
    # Bring up HS-CAN (can0) at 500kbps
    output, error = execute_command(ssh, 
                                   "sudo ip link set can0 up type can bitrate 500000 listen-only on",
                                   "Bringing up can0 (HS-CAN) at 500kbps")
    can0_up = "Cannot" not in output and "error" not in error.lower()
    
    # Bring up MS-CAN (can1) at 125kbps
    output, error = execute_command(ssh, 
                                   "sudo ip link set can1 up type can bitrate 125000 listen-only on",
                                   "Bringing up can1 (MS-CAN) at 125kbps")
    can1_up = "Cannot" not in output and "error" not in error.lower()
    
    print(f"\n  can0: {'✓ UP' if can0_up else '✗ FAILED'}")
    print(f"  can1: {'✓ UP' if can1_up else '✗ FAILED'}")
    
    return can0_up, can1_up

def check_interface_status(ssh):
    """Check detailed interface status"""
    print_section("INTERFACE STATUS")
    
    execute_command(ssh, "ip -s -d link show can0", "Checking can0 statistics")
    execute_command(ssh, "ip -s -d link show can1", "Checking can1 statistics")

def test_can_traffic(ssh, interface="can0", timeout=5):
    """Test for CAN traffic"""
    print_section(f"TESTING FOR CAN TRAFFIC ON {interface}")
    
    print(f"\n→ Listening for CAN messages (timeout: {timeout}s)")
    print("  Note: Car ignition must be in ACC or ON position")
    
    cmd = f"timeout {timeout} candump {interface} -n 10 2>&1"
    stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True)
    
    messages = []
    while True:
        line = stdout.readline()
        if not line:
            break
        messages.append(line.strip())
        if len(messages) <= 10:
            print(f"  {line.strip()}")
    
    if messages:
        print(f"\n✓ Received {len(messages)} CAN messages on {interface}")
        return True
    else:
        print(f"\n✗ NO CAN TRAFFIC on {interface}!")
        print("  Possible causes:")
        print("  - Car ignition not in ACC/ON")
        print("  - MCP2515 not properly connected")
        print("  - Wrong CAN bus (check wiring)")
        return False

def check_spi_devices(ssh):
    """Check SPI devices"""
    print_section("CHECKING SPI DEVICES")
    
    execute_command(ssh, "ls -la /dev/spidev*", "Listing SPI devices")
    execute_command(ssh, "lsmod | grep spi", "Checking SPI kernel modules")

def full_diagnostic(ssh):
    """Run complete diagnostic"""
    print("\n" + "█" * 70)
    print("█  MCP2515 CAN MODULE DIAGNOSTIC & RESET")
    print("█" * 70)
    
    # Step 1: Check dmesg for errors
    check_dmesg_errors(ssh)
    
    # Step 2: Check SPI
    check_spi_devices(ssh)
    
    # Step 3: Check if interfaces exist
    has_can0, has_can1 = check_interfaces(ssh)
    
    if not has_can0 or not has_can1:
        print("\n⚠️  WARNING: One or both CAN interfaces missing!")
        print("   This indicates a hardware or kernel configuration issue.")
        
        print_section("ATTEMPTING TO RELOAD MCP2515 MODULES")
        execute_command(ssh, "sudo dtoverlay -r mcp2515-can0 2>/dev/null || true", 
                       "Removing can0 overlay")
        execute_command(ssh, "sudo dtoverlay -r mcp2515-can1 2>/dev/null || true", 
                       "Removing can1 overlay")
        time.sleep(2)
        execute_command(ssh, "sudo dtoverlay mcp2515-can0,oscillator=8000000,interrupt=25", 
                       "Loading can0 overlay")
        execute_command(ssh, "sudo dtoverlay mcp2515-can1,oscillator=8000000,interrupt=24", 
                       "Loading can1 overlay")
        time.sleep(2)
        has_can0, has_can1 = check_interfaces(ssh)
    
    # Step 4: Reset interfaces
    can0_up, can1_up = reset_can_interfaces(ssh)
    
    # Step 5: Check status
    check_interface_status(ssh)
    
    # Step 6: Test traffic
    if can0_up:
        can0_traffic = test_can_traffic(ssh, "can0", timeout=5)
    else:
        can0_traffic = False
    
    if can1_up:
        can1_traffic = test_can_traffic(ssh, "can1", timeout=5)
    else:
        can1_traffic = False
    
    # Summary
    print_section("DIAGNOSTIC SUMMARY")
    print(f"\n  Interface can0 exists:  {'✓' if has_can0 else '✗'}")
    print(f"  Interface can1 exists:  {'✓' if has_can1 else '✗'}")
    print(f"  can0 is up:             {'✓' if can0_up else '✗'}")
    print(f"  can1 is up:             {'✓' if can1_up else '✗'}")
    print(f"  can0 has traffic:       {'✓' if can0_traffic else '✗'}")
    print(f"  can1 has traffic:       {'✓' if can1_traffic else '✗'}")
    
    all_good = has_can0 and has_can1 and can0_up and can1_up and (can0_traffic or can1_traffic)
    
    if all_good:
        print("\n✓✓✓ MCP2515 MODULES ARE WORKING! ✓✓✓")
    else:
        print("\n⚠️  ISSUES DETECTED - SEE ABOVE FOR DETAILS")
        print("\nRECOMMENDATIONS:")
        if not (has_can0 and has_can1):
            print("  • Check MCP2515 hardware connections (SPI, power, ground)")
            print("  • Verify /boot/config.txt has correct dtoverlay settings")
            print("  • Try: sudo reboot")
        if not (can0_traffic or can1_traffic):
            print("  • Ensure car ignition is in ACC or ON position")
            print("  • Check CAN-H and CAN-L wiring to OBD-II port")
            print("  • Verify correct bitrates (500k for HS-CAN, 125k for MS-CAN)")
    
    print("\n" + "=" * 70 + "\n")

def main():
    print(f"Connecting to Pi at {PI_IP}...")
    
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(PI_IP, username=PI_USER, password=PI_PASSWORD, timeout=10)
        
        print("✓ Connected to Pi\n")
        
        full_diagnostic(ssh)
        
        ssh.close()
        print("✓ Disconnected from Pi")
        
    except paramiko.AuthenticationException:
        print(f"✗ Authentication failed. Check username/password.")
        sys.exit(1)
    except paramiko.SSHException as e:
        print(f"✗ SSH error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
