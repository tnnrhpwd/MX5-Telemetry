#!/usr/bin/env python3
"""
Active MCP2515 Loopback Test
============================
Tests two MCP2515 modules wired together by actively sending test messages.

Wiring:
    MCP#1 CAN-H <-> MCP#2 CAN-H
    MCP#1 CAN-L <-> MCP#2 CAN-L
    120Ω termination at each end (or one 60Ω between H and L)

Usage:
    sudo python3 test_mcp2515_loopback_active.py
"""

import can
import time
import sys
import subprocess
import threading
from typing import List, Tuple

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

def setup_interface(interface: str, bitrate: int = 500000) -> bool:
    """Bring up CAN interface."""
    try:
        subprocess.run(['sudo', 'ip', 'link', 'set', interface, 'down'],
                      capture_output=True, timeout=5)
        
        result = subprocess.run([
            'sudo', 'ip', 'link', 'set', interface, 'up',
            'type', 'can',
            'bitrate', str(bitrate)
        ], capture_output=True, text=True, timeout=5)
        
        return result.returncode == 0
    except Exception as e:
        print_error(f"Failed to setup {interface}: {e}")
        return False

class MessageCollector:
    """Collects messages from a CAN interface in a background thread."""
    
    def __init__(self, interface: str):
        self.interface = interface
        self.messages = []
        self.running = False
        self.thread = None
        self.bus = None
    
    def start(self):
        """Start collecting messages."""
        try:
            self.bus = can.interface.Bus(channel=self.interface, bustype='socketcan')
            self.running = True
            self.thread = threading.Thread(target=self._collect)
            self.thread.daemon = True
            self.thread.start()
            return True
        except Exception as e:
            print_error(f"Failed to start collector on {self.interface}: {e}")
            return False
    
    def _collect(self):
        """Background thread that collects messages."""
        while self.running:
            try:
                msg = self.bus.recv(timeout=0.1)
                if msg is not None:
                    self.messages.append(msg)
            except:
                break
    
    def stop(self):
        """Stop collecting and return messages."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
        if self.bus:
            self.bus.shutdown()
        return self.messages

def send_test_messages(interface: str, count: int = 10) -> bool:
    """Send test messages on an interface."""
    try:
        bus = can.interface.Bus(channel=interface, bustype='socketcan')
        
        for i in range(count):
            msg = can.Message(
                arbitration_id=0x100 + i,
                data=[0xAA, 0xBB, 0xCC, 0xDD, i, 0x55, 0x66, 0x77],
                is_extended_id=False
            )
            bus.send(msg)
            time.sleep(0.05)  # 50ms between messages
        
        bus.shutdown()
        return True
        
    except Exception as e:
        print_error(f"Failed to send on {interface}: {e}")
        return False

def test_bidirectional_loopback() -> Tuple[bool, dict]:
    """
    Test both directions:
    - can0 sends, can1 receives
    - can1 sends, can0 receives
    """
    results = {
        'can0_to_can1': {'sent': 0, 'received': 0, 'success': False},
        'can1_to_can0': {'sent': 0, 'received': 0, 'success': False}
    }
    
    # Test 1: can0 -> can1
    print_info("Test 1: Sending from can0, receiving on can1...")
    collector = MessageCollector('can1')
    if not collector.start():
        return False, results
    
    time.sleep(0.5)  # Let collector start
    
    if send_test_messages('can0', 10):
        results['can0_to_can1']['sent'] = 10
    
    time.sleep(1)  # Wait for messages to arrive
    messages = collector.stop()
    results['can0_to_can1']['received'] = len(messages)
    results['can0_to_can1']['success'] = len(messages) >= 8  # Allow some loss
    
    if results['can0_to_can1']['success']:
        print_success(f"  Received {len(messages)}/10 messages on can1")
    else:
        print_error(f"  Only received {len(messages)}/10 messages on can1")
    
    time.sleep(0.5)
    
    # Test 2: can1 -> can0
    print_info("Test 2: Sending from can1, receiving on can0...")
    collector = MessageCollector('can0')
    if not collector.start():
        return False, results
    
    time.sleep(0.5)
    
    if send_test_messages('can1', 10):
        results['can1_to_can0']['sent'] = 10
    
    time.sleep(1)
    messages = collector.stop()
    results['can1_to_can0']['received'] = len(messages)
    results['can1_to_can0']['success'] = len(messages) >= 8
    
    if results['can1_to_can0']['success']:
        print_success(f"  Received {len(messages)}/10 messages on can0")
    else:
        print_error(f"  Only received {len(messages)}/10 messages on can0")
    
    overall_success = (results['can0_to_can1']['success'] and 
                      results['can1_to_can0']['success'])
    
    return overall_success, results

def check_interface_exists(interface: str) -> bool:
    """Check if interface exists."""
    try:
        result = subprocess.run(
            ['ip', 'link', 'show', interface],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except:
        return False

def main():
    print_header("MCP2515 Active Loopback Test")
    
    print_info("Testing two MCP2515 modules wired together:")
    print_info("  MCP#1 (can0) CAN-H <-> MCP#2 (can1) CAN-H")
    print_info("  MCP#1 (can0) CAN-L <-> MCP#2 (can1) CAN-L")
    print_info("  120Ω termination required\n")
    
    # Step 1: Check interfaces exist
    print_section("Step 1: Checking Interfaces")
    
    if not check_interface_exists('can0'):
        print_error("can0 not found - check MCP#1 is loaded")
        return 1
    print_success("can0 found")
    
    if not check_interface_exists('can1'):
        print_error("can1 not found - check MCP#2 is loaded")
        return 1
    print_success("can1 found")
    
    # Step 2: Configure interfaces
    print_section("Step 2: Configuring Interfaces (500kbps)")
    
    if not setup_interface('can0', 500000):
        print_error("Failed to configure can0")
        return 1
    print_success("can0 configured")
    
    if not setup_interface('can1', 500000):
        print_error("Failed to configure can1")
        return 1
    print_success("can1 configured")
    
    time.sleep(1)
    
    # Step 3: Run bidirectional test
    print_section("Step 3: Running Bidirectional Loopback Test")
    
    success, results = test_bidirectional_loopback()
    
    # Step 4: Results
    print_section("Step 4: Test Results")
    
    print_info(f"can0 → can1: {results['can0_to_can1']['received']}/{results['can0_to_can1']['sent']} messages")
    print_info(f"can1 → can0: {results['can1_to_can0']['received']}/{results['can1_to_can0']['sent']} messages")
    print()
    
    if success:
        print_success("✅ LOOPBACK TEST PASSED!")
        print()
        print_info("Both MCP2515 modules can communicate in both directions.")
        print_info("H and L wiring is correct.")
        print()
        return 0
    else:
        print_error("❌ LOOPBACK TEST FAILED")
        print()
        
        if results['can0_to_can1']['received'] == 0 and results['can1_to_can0']['received'] == 0:
            print_warning("No messages received in either direction:")
            print_info("  • Verify CAN-H is connected: MCP#1 H <-> MCP#2 H")
            print_info("  • Verify CAN-L is connected: MCP#1 L <-> MCP#2 L")
            print_info("  • Check 120Ω termination resistors (one at each module)")
            print_info("  • Verify both modules powered (3.3V or 5V)")
            print_info("  • Check oscillator: both should be 8MHz")
        
        elif results['can0_to_can1']['received'] == 0:
            print_warning("can1 not receiving from can0:")
            print_info("  • Check can1 (MCP#2) CAN-H/L connections")
            print_info("  • Verify MCP#2 termination resistor")
            print_info("  • Check MCP#2 SPI wiring (MISO especially)")
        
        elif results['can1_to_can0']['received'] == 0:
            print_warning("can0 not receiving from can1:")
            print_info("  • Check can0 (MCP#1) CAN-H/L connections")
            print_info("  • Verify MCP#1 termination resistor")
            print_info("  • Check MCP#1 SPI wiring (MISO especially)")
        
        else:
            print_warning("Partial communication (some packets lost):")
            print_info("  • Check termination resistor values (should be 120Ω)")
            print_info("  • Look for loose connections")
            print_info("  • Verify wire quality (short, twisted pair if possible)")
            print_info(f"  • Success rate: {(results['can0_to_can1']['received'] + results['can1_to_can0']['received']) / 20 * 100:.0f}%")
        
        print()
        return 1

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted")
        sys.exit(130)
    except Exception as e:
        print_error(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
