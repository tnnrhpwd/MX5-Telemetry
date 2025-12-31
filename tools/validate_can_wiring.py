#!/usr/bin/env python3
"""
CAN Bus H/L Wiring Validation Script
=====================================
Validates that both MCP2515 modules can read from CAN-H and CAN-L correctly.
Tests both MCP#1 and MCP#2 to ensure proper wiring after fixes.

Usage:
    python3 validate_can_wiring.py
    
This will:
1. Check that both CAN interfaces are up
2. Monitor traffic on both interfaces
3. Validate signal integrity
4. Report on H/L connectivity
"""

import can
import time
import sys
import subprocess
from typing import Tuple, Optional

# ANSI colors
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

def print_header(text):
    print(f"\n{CYAN}{BOLD}{'='*70}{RESET}")
    print(f"{CYAN}{BOLD}{text.center(70)}{RESET}")
    print(f"{CYAN}{BOLD}{'='*70}{RESET}\n")

def print_section(text):
    print(f"\n{BLUE}{BOLD}{text}{RESET}")
    print(f"{BLUE}{'-'*70}{RESET}")

def print_success(text):
    print(f"{GREEN}✓ {text}{RESET}")

def print_error(text):
    print(f"{RED}✗ {text}{RESET}")

def print_warning(text):
    print(f"{YELLOW}⚠ {text}{RESET}")

def print_info(text):
    print(f"  {text}")

def check_interface_status(interface: str) -> Tuple[bool, str]:
    """Check if CAN interface exists and is up."""
    try:
        result = subprocess.run(
            ['ip', '-details', 'link', 'show', interface],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            return False, f"Interface {interface} not found"
        
        if 'UP' in result.stdout:
            return True, "UP"
        else:
            return False, "DOWN"
            
    except Exception as e:
        return False, str(e)

def bring_up_interface(interface: str, bitrate: int = 500000) -> bool:
    """Bring up CAN interface with specified bitrate."""
    try:
        # Bring down first
        subprocess.run(['sudo', 'ip', 'link', 'set', interface, 'down'],
                      capture_output=True, timeout=5)
        
        # Configure and bring up
        result = subprocess.run([
            'sudo', 'ip', 'link', 'set', interface, 'up',
            'type', 'can',
            'bitrate', str(bitrate)
        ], capture_output=True, text=True, timeout=5)
        
        return result.returncode == 0
        
    except Exception as e:
        print_error(f"Failed to bring up {interface}: {e}")
        return False

def get_interface_stats(interface: str) -> dict:
    """Get error statistics for interface."""
    try:
        result = subprocess.run(
            ['ip', '-s', 'link', 'show', interface],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            # Parse statistics (simplified)
            return {'output': result.stdout}
        return {}
        
    except Exception as e:
        return {'error': str(e)}

def monitor_interface(interface: str, duration: int = 5) -> Tuple[int, list]:
    """
    Monitor interface for CAN messages.
    
    Returns:
        Tuple of (message_count, sample_messages)
    """
    messages = []
    count = 0
    
    try:
        bus = can.interface.Bus(channel=interface, bustype='socketcan')
        print_info(f"Monitoring {interface} for {duration} seconds...")
        
        start_time = time.time()
        while (time.time() - start_time) < duration:
            msg = bus.recv(timeout=0.1)
            if msg is not None:
                count += 1
                # Store first 5 messages as samples
                if len(messages) < 5:
                    messages.append(msg)
        
        bus.shutdown()
        return count, messages
        
    except Exception as e:
        print_error(f"Error monitoring {interface}: {e}")
        return 0, []

def check_physical_layer(interface: str) -> dict:
    """Check physical layer health."""
    try:
        result = subprocess.run(
            ['cat', f'/sys/class/net/{interface}/statistics/rx_errors'],
            capture_output=True,
            text=True,
            timeout=5
        )
        rx_errors = int(result.stdout.strip()) if result.returncode == 0 else -1
        
        result = subprocess.run(
            ['cat', f'/sys/class/net/{interface}/statistics/tx_errors'],
            capture_output=True,
            text=True,
            timeout=5
        )
        tx_errors = int(result.stdout.strip()) if result.returncode == 0 else -1
        
        return {
            'rx_errors': rx_errors,
            'tx_errors': tx_errors
        }
    except:
        return {'rx_errors': -1, 'tx_errors': -1}

def test_loopback(can0_count: int, can1_count: int) -> Tuple[bool, str]:
    """
    Determine if both interfaces are reading the same bus.
    If counts are similar, they're likely on the same physical bus.
    """
    if can0_count == 0 and can1_count == 0:
        return False, "No traffic detected on either interface"
    
    if can0_count == 0:
        return False, "can0 not receiving (check H/L wiring)"
    
    if can1_count == 0:
        return False, "can1 not receiving (check H/L wiring)"
    
    # If both receiving, check if counts are reasonably similar
    ratio = min(can0_count, can1_count) / max(can0_count, can1_count)
    
    if ratio > 0.8:
        return True, "Both interfaces receiving similar traffic (good!)"
    else:
        return False, f"Traffic mismatch (can0: {can0_count}, can1: {can1_count})"

def main():
    print_header("MX5 Telemetry - CAN Bus H/L Wiring Validation")
    
    print_info("This script validates that both MCP2515 modules are correctly")
    print_info("wired to CAN-H and CAN-L and can read car CAN bus traffic.\n")
    
    # Step 1: Check interface existence
    print_section("Step 1: Checking CAN Interface Status")
    
    can0_exists, can0_status = check_interface_status('can0')
    can1_exists, can1_status = check_interface_status('can1')
    
    if can0_exists:
        print_success(f"can0 (MCP#1) found - Status: {can0_status}")
    else:
        print_error(f"can0 (MCP#1) not found - {can0_status}")
    
    if can1_exists:
        print_success(f"can1 (MCP#2) found - Status: {can1_status}")
    else:
        print_error(f"can1 (MCP#2) not found - {can1_status}")
    
    if not can0_exists or not can1_exists:
        print_error("\nCannot proceed - interfaces not found!")
        print_info("Check that MCP2515 drivers are loaded:")
        print_info("  sudo dtoverlay mcp2515 spi0.0 interrupt=25")
        print_info("  sudo dtoverlay mcp2515 spi0.1 interrupt=24")
        return 1
    
    # Step 2: Bring up interfaces if needed
    print_section("Step 2: Configuring CAN Interfaces")
    
    if can0_status != "UP":
        print_info("Bringing up can0...")
        if bring_up_interface('can0', 500000):
            print_success("can0 configured at 500kbps")
        else:
            print_error("Failed to configure can0")
            return 1
    else:
        print_success("can0 already up")
    
    if can1_status != "UP":
        print_info("Bringing up can1...")
        if bring_up_interface('can1', 500000):
            print_success("can1 configured at 500kbps")
        else:
            print_error("Failed to configure can1")
            return 1
    else:
        print_success("can1 already up")
    
    # Step 3: Check error counters
    print_section("Step 3: Checking Physical Layer Health")
    
    can0_stats = check_physical_layer('can0')
    can1_stats = check_physical_layer('can1')
    
    print_info(f"can0 - RX errors: {can0_stats.get('rx_errors', 'N/A')}, "
               f"TX errors: {can0_stats.get('tx_errors', 'N/A')}")
    print_info(f"can1 - RX errors: {can1_stats.get('rx_errors', 'N/A')}, "
               f"TX errors: {can1_stats.get('tx_errors', 'N/A')}")
    
    if can0_stats.get('rx_errors', 0) > 100:
        print_warning("can0 has high RX errors - check termination/wiring")
    if can1_stats.get('rx_errors', 0) > 100:
        print_warning("can1 has high RX errors - check termination/wiring")
    
    # Step 4: Monitor traffic
    print_section("Step 4: Monitoring CAN Bus Traffic")
    
    print_info("\n🚗 Please ensure the car is ON or generating CAN traffic")
    print_info("Monitoring both interfaces for 10 seconds...\n")
    
    time.sleep(1)
    
    # Monitor both in sequence
    can0_count, can0_msgs = monitor_interface('can0', 5)
    can1_count, can1_msgs = monitor_interface('can1', 5)
    
    print()
    print_info(f"can0 received: {can0_count} messages")
    print_info(f"can1 received: {can1_count} messages")
    
    # Step 5: Analyze results
    print_section("Step 5: Analysis & Results")
    
    success, message = test_loopback(can0_count, can1_count)
    
    if success:
        print_success(message)
        print()
        print_success("✅ VALIDATION PASSED - Both H and L are reading correctly!")
        print()
        print_info("Both MCP2515 modules are properly wired and receiving CAN traffic.")
        
        # Show sample messages
        if can0_msgs:
            print_info("\nSample messages from can0:")
            for i, msg in enumerate(can0_msgs[:3], 1):
                print(f"    {i}. ID: 0x{msg.arbitration_id:03X}, Data: {msg.data.hex()}")
        
        if can1_msgs:
            print_info("\nSample messages from can1:")
            for i, msg in enumerate(can1_msgs[:3], 1):
                print(f"    {i}. ID: 0x{msg.arbitration_id:03X}, Data: {msg.data.hex()}")
        
        return 0
        
    else:
        print_error(message)
        print()
        print_error("❌ VALIDATION FAILED")
        print()
        
        if can0_count == 0:
            print_warning("can0 (MCP#1) not receiving:")
            print_info("  • Check CAN-H connection to car CAN bus")
            print_info("  • Check CAN-L connection to car CAN bus")
            print_info("  • Verify 120Ω termination resistor")
            print_info("  • Check SPI wiring (CS, MISO, MOSI, SCK)")
        
        if can1_count == 0:
            print_warning("\ncan1 (MCP#2) not receiving:")
            print_info("  • Check CAN-H connection to car CAN bus")
            print_info("  • Check CAN-L connection to car CAN bus")
            print_info("  • Verify 120Ω termination resistor")
            print_info("  • Check SPI wiring (CS, MISO, MOSI, SCK)")
        
        if can0_count > 0 and can1_count > 0:
            print_warning("\nBoth receiving but counts differ significantly:")
            print_info("  • May indicate one interface has intermittent connection")
            print_info("  • Check for loose wires or poor connections")
            print_info("  • Verify proper termination on both modules")
        
        return 1

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(130)
    except Exception as e:
        print_error(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
