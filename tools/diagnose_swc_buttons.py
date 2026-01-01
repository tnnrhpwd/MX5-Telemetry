#!/usr/bin/env python3
"""
Diagnostic tool for troubleshooting steering wheel control buttons

This script helps diagnose why SWC buttons aren't working on the ESP32 display.
It checks the entire signal path from MS-CAN through the Pi to the ESP32.

Checks performed:
1. MS-CAN interface status (can1 / MCP2515)
2. Live monitoring of CAN ID 0x250 (cruise control buttons)
3. Pi UI application status
4. ESP32 serial connection
5. Button event processing in swc_handler

Usage:
    python3 tools/diagnose_swc_buttons.py
    
Then press cruise control buttons on steering wheel and observe output.
"""

import sys
import os
import time
import subprocess

# Colors for terminal output
class Color:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text):
    print(f"\n{Color.BOLD}{Color.BLUE}{'=' * 60}{Color.END}")
    print(f"{Color.BOLD}{Color.BLUE}{text}{Color.END}")
    print(f"{Color.BOLD}{Color.BLUE}{'=' * 60}{Color.END}")

def print_success(text):
    print(f"{Color.GREEN}✓ {text}{Color.END}")

def print_warning(text):
    print(f"{Color.YELLOW}⚠ {text}{Color.END}")

def print_error(text):
    print(f"{Color.RED}✗ {text}{Color.END}")

def print_info(text):
    print(f"{Color.BLUE}ℹ {text}{Color.END}")

def run_command(cmd, shell=False):
    """Run a command and return output"""
    try:
        result = subprocess.run(
            cmd if not shell else cmd,
            shell=shell,
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)

def check_can_interface():
    """Check if MS-CAN interface is up"""
    print_header("Step 1: Checking MS-CAN Interface (can1)")
    
    # Check if can1 exists
    ret, out, err = run_command(["ip", "link", "show", "can1"])
    
    if ret != 0:
        print_error("MS-CAN interface 'can1' not found!")
        print_info("Expected interface: can1 (125kbps for body/SWC data)")
        print_info("Run setup script: sudo bash pi/setup_can_bus.sh")
        return False
    
    print_success("Interface 'can1' exists")
    
    # Check if interface is UP
    if "UP" in out and "RUNNING" in out:
        print_success("Interface is UP and RUNNING")
    else:
        print_error("Interface is DOWN!")
        print_info("Try: sudo ip link set can1 up type can bitrate 125000")
        return False
    
    # Check bitrate
    if "125000" in out or "125 Kbit" in out:
        print_success("Bitrate is 125kbps (correct for MS-CAN)")
    else:
        print_warning("Bitrate may be incorrect (should be 125kbps)")
    
    return True

def check_can_traffic():
    """Check if there's any traffic on MS-CAN"""
    print_header("Step 2: Monitoring MS-CAN Traffic")
    
    print_info("Checking for any CAN messages on can1...")
    print_info("(This will timeout after 3 seconds)")
    
    try:
        import can
        bus = can.interface.Bus(channel='can1', bustype='socketcan')
        
        msg_count = 0
        swc_count = 0
        start_time = time.time()
        timeout = 3.0
        
        while time.time() - start_time < timeout:
            msg = bus.recv(timeout=0.1)
            if msg:
                msg_count += 1
                if msg.arbitration_id == 0x250:
                    swc_count += 1
                    print(f"  CAN ID 0x250: {' '.join(f'{b:02X}' for b in msg.data)}")
        
        bus.shutdown()
        
        if msg_count > 0:
            print_success(f"Received {msg_count} CAN messages in {timeout}s")
            if swc_count > 0:
                print_success(f"Received {swc_count} SWC button messages (0x250)")
            else:
                print_warning("No SWC button messages detected")
                print_info("Try pressing cruise control buttons now...")
        else:
            print_error("No CAN traffic detected!")
            print_info("Check wiring: MS-CAN should be pins 3(H) and 11(L) on OBD-II")
            return False
        
        return True
        
    except ImportError:
        print_error("python-can not installed!")
        print_info("Install: pip install python-can")
        return False
    except Exception as e:
        print_error(f"CAN monitoring failed: {e}")
        return False

def check_live_swc_buttons():
    """Live monitor for SWC button presses"""
    print_header("Step 3: Live SWC Button Monitor")
    print_info("Press cruise control buttons on steering wheel...")
    print_info("Press Ctrl+C to exit")
    print()
    print("Expected button codes (CAN ID 0x250, Byte 0):")
    print("  0x01 = ON/OFF (Select)")
    print("  0x02 = CANCEL (Back)")
    print("  0x04 = RES+ (Up)")
    print("  0x08 = SET- (Down)")
    print("  0x00 = No button pressed")
    print()
    
    try:
        import can
        bus = can.interface.Bus(channel='can1', bustype='socketcan')
        
        last_value = 0x00
        button_names = {
            0x01: "ON/OFF (Select)",
            0x02: "CANCEL (Back)",
            0x04: "RES+ (Up)",
            0x08: "SET- (Down)",
            0x00: "(released)"
        }
        
        while True:
            msg = bus.recv(timeout=0.5)
            if msg and msg.arbitration_id == 0x250:
                button_byte = msg.data[0] if len(msg.data) > 0 else 0x00
                
                # Only print when value changes
                if button_byte != last_value:
                    button_name = button_names.get(button_byte, f"Unknown (0x{button_byte:02X})")
                    if button_byte == 0x00:
                        print(f"  Button released")
                    else:
                        print_success(f"Button pressed: {button_name}")
                    last_value = button_byte
        
        bus.shutdown()
        
    except KeyboardInterrupt:
        print()
        print_info("Monitoring stopped")
        return True
    except ImportError:
        print_error("python-can not installed!")
        return False
    except Exception as e:
        print_error(f"Monitoring failed: {e}")
        return False

def check_pi_ui_process():
    """Check if Pi UI is running"""
    print_header("Step 4: Checking Pi UI Application")
    
    # Check if main.py process is running
    ret, out, err = run_command(["pgrep", "-f", "main.py"])
    
    if ret == 0 and out.strip():
        print_success(f"Pi UI is running (PID: {out.strip()})")
        
        # Check if it's reading from CAN
        print_info("Checking if UI is reading CAN data...")
        # This would require more sophisticated process inspection
        
        return True
    else:
        print_warning("Pi UI does not appear to be running")
        print_info("Start with: python3 pi/ui/src/main.py --fullscreen")
        return False

def check_esp32_serial():
    """Check ESP32 serial connection"""
    print_header("Step 5: Checking ESP32 Serial Connection")
    
    # List serial devices
    import glob
    ports = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')
    
    if not ports:
        print_error("No USB serial devices found!")
        print_info("Check ESP32 USB connection")
        return False
    
    print_success(f"Found serial ports: {', '.join(ports)}")
    
    # Try to connect to ESP32
    try:
        import serial
        for port in ports:
            try:
                ser = serial.Serial(port, 115200, timeout=1)
                print_success(f"Successfully opened {port}")
                ser.close()
                return True
            except Exception as e:
                print_warning(f"Could not open {port}: {e}")
        
        print_error("Could not connect to any serial port")
        return False
        
    except ImportError:
        print_error("pyserial not installed!")
        print_info("Install: pip install pyserial")
        return False

def print_troubleshooting_tips():
    """Print troubleshooting tips based on findings"""
    print_header("Troubleshooting Tips")
    
    print()
    print(f"{Color.BOLD}Common Issues:{Color.END}")
    print()
    print("1. No CAN traffic on can1:")
    print("   - Check MS-CAN wiring: OBD-II pins 3 (CAN-H) and 11 (CAN-L)")
    print("   - Verify MCP2515 #2 connection to Pi GPIO (CE1, GPIO 24)")
    print("   - Run: sudo bash pi/setup_can_bus.sh")
    print("   - Test: candump can1")
    print()
    print("2. CAN traffic but no button messages:")
    print("   - Car must be in ignition ON or running")
    print("   - Only cruise control buttons visible (ON/OFF, CANCEL, RES+, SET-)")
    print("   - Audio buttons are NOT on CAN bus")
    print()
    print("3. Buttons work in candump but not in UI:")
    print("   - Check if Pi UI is running")
    print("   - Check if navigation is locked (hold ON/OFF for 3s to unlock)")
    print("   - Check Pi UI logs for errors")
    print()
    print("4. Buttons work in Pi but not ESP32:")
    print("   - Check ESP32 serial connection (USB)")
    print("   - Check if ESP32 firmware is running")
    print("   - Check ESP32 serial handler in Pi UI")
    print()
    print(f"{Color.BOLD}Quick Test:{Color.END}")
    print("1. candump can1  (should see 0x250 messages when pressing buttons)")
    print("2. python3 tools/test_swc.py  (test button parsing)")
    print("3. Check navigation lock: press and hold ON/OFF for 3 seconds")
    print()

def main():
    print()
    print(f"{Color.BOLD}MX5 Telemetry - SWC Button Diagnostic Tool{Color.END}")
    print()
    
    # Run diagnostic checks
    can_ok = check_can_interface()
    
    if can_ok:
        traffic_ok = check_can_traffic()
        
        if traffic_ok:
            # Offer live monitoring
            print()
            response = input("Run live button monitoring? (y/n): ")
            if response.lower() == 'y':
                check_live_swc_buttons()
    
    # Check application status
    check_pi_ui_process()
    check_esp32_serial()
    
    # Print tips
    print_troubleshooting_tips()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print_info("Diagnostic cancelled")
    except Exception as e:
        print_error(f"Diagnostic failed: {e}")
        import traceback
        traceback.print_exc()
