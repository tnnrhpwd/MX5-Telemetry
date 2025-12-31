#!/usr/bin/env python3
"""
Combined UI Simulator Launcher

Launch both ESP32-S3 and Raspberry Pi simulators side by side
for synchronized testing of steering wheel button controls.

Usage:
    python launch_simulators.py [options]

Options:
    --esp32     Launch only ESP32-S3 simulator
    --pi        Launch only Raspberry Pi simulator
    --both      Launch both simulators (default)
"""

import subprocess
import sys
import os
import argparse
from pathlib import Path


def get_script_dir():
    """Get the directory containing this script"""
    return Path(__file__).parent.absolute()


def find_simulator(name: str) -> Path:
    """Find simulator script by searching project directories"""
    script_dir = get_script_dir()
    project_root = script_dir.parent.parent.parent  # tools/simulators/ui_simulator -> root
    
    if name == "esp32":
        path = project_root / "display" / "ui" / "simulator" / "esp32_ui_simulator.py"
    elif name == "pi":
        path = project_root / "pi" / "ui" / "simulator" / "pi_ui_simulator.py"
    else:
        raise ValueError(f"Unknown simulator: {name}")
    
    if not path.exists():
        raise FileNotFoundError(f"Simulator not found: {path}")
    
    return path


def launch_simulator(name: str, wait: bool = False):
    """Launch a simulator"""
    try:
        script_path = find_simulator(name)
        print(f"Launching {name.upper()} simulator: {script_path}")
        
        if wait:
            subprocess.run([sys.executable, str(script_path)], check=True)
        else:
            subprocess.Popen([sys.executable, str(script_path)])
            
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return False
    except subprocess.CalledProcessError as e:
        print(f"Error running {name} simulator: {e}")
        return False
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Launch MX5 Telemetry UI Simulators"
    )
    parser.add_argument("--esp32", action="store_true", help="Launch only ESP32-S3 simulator")
    parser.add_argument("--pi", action="store_true", help="Launch only Raspberry Pi simulator")
    parser.add_argument("--both", action="store_true", help="Launch both simulators (default)")
    
    args = parser.parse_args()
    
    # Default to both if nothing specified
    if not args.esp32 and not args.pi:
        args.both = True
    
    print("=" * 60)
    print("MX5 Telemetry UI Simulator Launcher")
    print("=" * 60)
    print()
    print("Keyboard Controls (cruise control buttons only):")
    print("  NOTE: Audio buttons (VOL+/-, MODE, SEEK, MUTE) are")
    print("        NOT available on the CAN bus!")
    print()
    print("  ↑/W       = RES+ (UP) - Previous page / Navigate up")
    print("  ↓/S       = SET- (DOWN) - Next page / Navigate down")
    print("  Enter/Spc = ON/OFF (SELECT) - Select / Confirm edit")
    print("  B/Bksp    = CANCEL (BACK) - Exit / Go to Overview")
    print()
    print("  Settings Screen:")
    print("    UP/DOWN = Navigate settings (wraps to pages)")
    print("    SELECT  = Enter edit mode")
    print("    UP/DOWN = Adjust value (in edit mode)")
    print("    SELECT  = Confirm edit")
    print("    CANCEL  = Cancel edit")
    print()
    print("=" * 60)
    
    if args.both:
        print("\nLaunching both simulators...")
        launch_simulator("esp32", wait=False)
        launch_simulator("pi", wait=True)  # Wait on the last one
    elif args.esp32:
        print("\nLaunching ESP32-S3 simulator...")
        launch_simulator("esp32", wait=True)
    elif args.pi:
        print("\nLaunching Raspberry Pi simulator...")
        launch_simulator("pi", wait=True)


if __name__ == "__main__":
    main()
