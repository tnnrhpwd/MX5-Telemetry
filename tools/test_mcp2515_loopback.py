#!/usr/bin/env python3
"""
MCP2515 Loopback Test Script
=============================
Tests both MCP2515 modules by connecting them together.
This verifies wiring, SPI communication, and CAN bus functionality.

Usage:
    python3 test_mcp2515_loopback.py
"""

import can
import time
import sys
from typing import Optional

# ANSI color codes
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
RESET = '\033[0m'
BOLD = '\033[1m'

def print_header(text):
    print(f"\n{CYAN}{BOLD}{'='*60}{RESET}")
    print(f"{CYAN}{BOLD}{text}{RESET}")
    print(f"{CYAN}{BOLD}{'='*60}{RESET}\n")

def print_success(text):
    print(f"{GREEN}✓ {text}{RESET}")

def print_error(text):
    print(f"{RED}✗ {text}{RESET}")

def print_warning(text):
    print(f"{YELLOW}⚠ {text}{RESET}")

def print_info(text):
    print(f"{CYAN}ℹ {text}{RESET}")

def setup_can_interface(interface: str, bitrate: int) -> bool:
    """
    Set up a CAN interface with specified bitrate.
    
    Args:
        interface: Interface name (can0 or can1)
        bitrate: Bitrate in bps (e.g., 500000, 125000)
    
    Returns:
        True if successful, False otherwise
    """
    import subprocess
    
    try:
        # Bring down interface first
        subprocess.run(['sudo', 'ip', 'link', 'set', interface, 'down'], 
                      check=False, capture_output=True)
        
        # Configure and bring up
        result = subprocess.run([
            'sudo', 'ip', 'link', 'set', interface, 'up', 
            'type', 'can', 
            'bitrate', str(bitrate)
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print_success(f"{interface} configured at {bitrate} bps")
            return True
        else:
            print_error(f"Failed to configure {interface}: {result.stderr}")
            return False
            
    except Exception as e:
        print_error(f"Exception configuring {interface}: {e}")
        return False

def test_send_receive(sender_if: str, receiver_if: str, test_name: str) -> bool:
    """
    Test sending from one interface and receiving on another.
    
    Args:
        sender_if: Interface to send from
        receiver_if: Interface to receive on
        test_name: Description of the test
    
    Returns:
        True if test passed, False otherwise
    """
    print_info(f"Test: {test_name}")
    print(f"      Sender: {sender_if}, Receiver: {receiver_if}")
    
    try:
        # Open both interfaces
        sender = can.interface.Bus(channel=sender_if, bustype='socketcan')
        receiver = can.interface.Bus(channel=receiver_if, bustype='socketcan')
        
        # Prepare test message
        test_id = 0x123
        test_data = [0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88]
        msg = can.Message(arbitration_id=test_id, data=test_data, is_extended_id=False)
        
        print(f"      Sending: ID=0x{test_id:03X}, Data={test_data}")
        
        # Send message
        sender.send(msg)
        time.sleep(0.1)  # Small delay for propagation
        
        # Try to receive
        received_msg = receiver.recv(timeout=1.0)
        
        if received_msg is None:
            print_error(f"      No message received on {receiver_if}")
            sender.shutdown()
            receiver.shutdown()
            return False
        
        # Verify message
        if received_msg.arbitration_id == test_id and list(received_msg.data) == test_data:
            print_success(f"      Message received correctly!")
            print(f"      Received: ID=0x{received_msg.arbitration_id:03X}, Data={list(received_msg.data)}")
            sender.shutdown()
            receiver.shutdown()
            return True
        else:
            print_error(f"      Message mismatch!")
            print(f"      Expected: ID=0x{test_id:03X}, Data={test_data}")
            print(f"      Received: ID=0x{received_msg.arbitration_id:03X}, Data={list(received_msg.data)}")
            sender.shutdown()
            receiver.shutdown()
            return False
            
    except Exception as e:
        print_error(f"      Exception: {e}")
        return False

def test_burst(sender_if: str, receiver_if: str, count: int = 10) -> bool:
    """
    Test burst transmission of multiple messages.
    
    Args:
        sender_if: Interface to send from
        receiver_if: Interface to receive on
        count: Number of messages to send
    
    Returns:
        True if all messages received, False otherwise
    """
    print_info(f"Burst test: Sending {count} messages from {sender_if} to {receiver_if}")
    
    try:
        sender = can.interface.Bus(channel=sender_if, bustype='socketcan')
        receiver = can.interface.Bus(channel=receiver_if, bustype='socketcan')
        
        # Send burst
        sent_ids = []
        for i in range(count):
            msg_id = 0x100 + i
            data = [i] * 8
            msg = can.Message(arbitration_id=msg_id, data=data, is_extended_id=False)
            sender.send(msg)
            sent_ids.append(msg_id)
            time.sleep(0.01)  # 10ms between messages
        
        print(f"      Sent {count} messages")
        
        # Receive burst
        received_ids = []
        timeout_start = time.time()
        while len(received_ids) < count and (time.time() - timeout_start) < 2.0:
            msg = receiver.recv(timeout=0.1)
            if msg:
                received_ids.append(msg.arbitration_id)
        
        print(f"      Received {len(received_ids)} messages")
        
        # Check results
        if len(received_ids) == count:
            print_success(f"      All {count} messages received!")
            sender.shutdown()
            receiver.shutdown()
            return True
        else:
            print_error(f"      Only {len(received_ids)}/{count} messages received")
            missed = set(sent_ids) - set(received_ids)
            if missed:
                print_warning(f"      Missed IDs: {[hex(x) for x in sorted(missed)]}")
            sender.shutdown()
            receiver.shutdown()
            return False
            
    except Exception as e:
        print_error(f"      Exception: {e}")
        return False

def check_interface_exists(interface: str) -> bool:
    """Check if a CAN interface exists."""
    import subprocess
    result = subprocess.run(['ip', 'link', 'show', interface], 
                          capture_output=True)
    return result.returncode == 0

def main():
    print_header("MCP2515 Loopback Debug Test")
    
    print("This script tests both MCP2515 modules by connecting them together.")
    print("Make sure you have wired CAN-H to CAN-H and CAN-L to CAN-L!")
    print()
    
    # Check if interfaces exist
    print_info("Checking for CAN interfaces...")
    can0_exists = check_interface_exists('can0')
    can1_exists = check_interface_exists('can1')
    
    if not can0_exists:
        print_error("can0 not found!")
        print("      Check boot config has: dtoverlay=mcp2515-can0,oscillator=8000000,interrupt=25")
        return 1
    else:
        print_success("can0 found")
    
    if not can1_exists:
        print_error("can1 not found!")
        print("      Check boot config has: dtoverlay=mcp2515-can1,oscillator=8000000,interrupt=24")
        return 1
    else:
        print_success("can1 found")
    
    # Choose test bitrate
    print()
    print_info("Using 500kbps for testing (HS-CAN speed)")
    bitrate = 500000
    
    # Configure interfaces
    print_header("Step 1: Configure CAN Interfaces")
    if not setup_can_interface('can0', bitrate):
        return 1
    if not setup_can_interface('can1', bitrate):
        return 1
    
    # Wait for interfaces to stabilize
    time.sleep(0.5)
    
    # Run tests
    print_header("Step 2: Single Message Tests")
    
    test_results = []
    
    # Test 1: can0 -> can1
    result1 = test_send_receive('can0', 'can1', "can0 → can1")
    test_results.append(("can0 → can1", result1))
    time.sleep(0.5)
    
    # Test 2: can1 -> can0
    result2 = test_send_receive('can1', 'can0', "can1 → can0")
    test_results.append(("can1 → can0", result2))
    time.sleep(0.5)
    
    # Burst tests
    print_header("Step 3: Burst Tests")
    
    result3 = test_burst('can0', 'can1', count=20)
    test_results.append(("can0 → can1 (burst)", result3))
    time.sleep(0.5)
    
    result4 = test_burst('can1', 'can0', count=20)
    test_results.append(("can1 → can0 (burst)", result4))
    
    # Summary
    print_header("Test Summary")
    
    all_passed = True
    for test_name, result in test_results:
        if result:
            print_success(f"{test_name:30s} PASSED")
        else:
            print_error(f"{test_name:30s} FAILED")
            all_passed = False
    
    print()
    if all_passed:
        print_success("All tests passed! Both MCP2515 modules are working correctly.")
        print_info("Your wiring and configuration are correct.")
        print_info("You can now connect them to the vehicle CAN bus.")
        return 0
    else:
        print_error("Some tests failed. Check the results above.")
        print()
        print_info("Troubleshooting tips:")
        print("  • Verify CAN-H is connected to CAN-H")
        print("  • Verify CAN-L is connected to CAN-L")
        print("  • Check both modules have 120Ω termination enabled")
        print("  • Verify both modules have power (3.3V or 5V)")
        print("  • Check SPI wiring (MISO, MOSI, SCK, CS, INT)")
        print("  • Confirm oscillator frequency matches boot config (8MHz or 16MHz)")
        return 1

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        print_warning("Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)
