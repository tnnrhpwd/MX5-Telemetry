#!/usr/bin/env python3
"""
Verify CAN Listen-Only Mode
============================
Checks if both CAN interfaces are configured in listen-only mode.
"""

import subprocess
import sys

RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
RESET = '\033[0m'
BOLD = '\033[1m'

def check_listen_only(interface: str) -> tuple:
    """Check if interface is in listen-only mode."""
    try:
        result = subprocess.run(
            ['ip', '-details', 'link', 'show', interface],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            return False, "Not found", False
        
        output = result.stdout
        is_up = 'UP' in output
        is_listen_only = 'LISTEN-ONLY' in output
        
        return True, "UP" if is_up else "DOWN", is_listen_only
        
    except Exception as e:
        return False, str(e), False

def main():
    print(f"\n{CYAN}{BOLD}{'='*60}{RESET}")
    print(f"{CYAN}{BOLD}{'CAN Listen-Only Mode Verification'.center(60)}{RESET}")
    print(f"{CYAN}{BOLD}{'='*60}{RESET}\n")
    
    all_good = True
    
    # Check can0
    exists, status, listen_only = check_listen_only('can0')
    
    if exists and listen_only:
        print(f"{GREEN}✓ can0: {status}, LISTEN-ONLY enabled{RESET}")
    elif exists and not listen_only:
        print(f"{RED}✗ can0: {status}, LISTEN-ONLY NOT enabled{RESET}")
        all_good = False
    else:
        print(f"{RED}✗ can0: Not found{RESET}")
        all_good = False
    
    # Check can1
    exists, status, listen_only = check_listen_only('can1')
    
    if exists and listen_only:
        print(f"{GREEN}✓ can1: {status}, LISTEN-ONLY enabled{RESET}")
    elif exists and not listen_only:
        print(f"{RED}✗ can1: {status}, LISTEN-ONLY NOT enabled{RESET}")
        all_good = False
    else:
        print(f"{RED}✗ can1: Not found{RESET}")
        all_good = False
    
    print()
    
    if all_good:
        print(f"{GREEN}{BOLD}✅ Production configuration correct!{RESET}")
        print(f"{GREEN}   Both interfaces in listen-only mode.{RESET}")
        print(f"{GREEN}   Pi will NOT transmit to car CAN bus.{RESET}\n")
        return 0
    else:
        print(f"{RED}{BOLD}❌ Configuration needs update{RESET}")
        print(f"{YELLOW}   Run: sudo bash pi/scripts/enable_listen_only.sh{RESET}\n")
        return 1

if __name__ == '__main__':
    sys.exit(main())
