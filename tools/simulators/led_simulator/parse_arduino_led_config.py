"""
Arduino LED Configuration Parser
=================================
Parses LEDStates.h to extract LED configuration constants.
This ensures the Python simulator always matches the Arduino code.

Usage:
    from parse_arduino_led_config import load_led_config
    config = load_led_config()
    STATE_1_RPM_MIN = config['STATE_1_RPM_MIN']
"""

import re
import os

def load_led_config(led_states_path=None):
    """
    Parse LEDStates.h and extract all #define constants.
    
    Args:
        led_states_path: Path to LEDStates.h file. If None, uses default location.
    
    Returns:
        Dictionary mapping constant names to their values.
    """
    if led_states_path is None:
        # Default path relative to this script
        # Script is now in tools/LED_Simulator/, need to go up two levels
        script_dir = os.path.dirname(os.path.abspath(__file__))
        tools_dir = os.path.dirname(script_dir)
        project_root = os.path.dirname(tools_dir)
        led_states_path = os.path.join(project_root, 'lib', 'Config', 'LEDStates.h')
    
    if not os.path.exists(led_states_path):
        raise FileNotFoundError(f"LEDStates.h not found at: {led_states_path}")
    
    config = {}
    
    # Read the header file
    with open(led_states_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Parse #define statements
    # Pattern: #define NAME value (where value can be integer or float)
    define_pattern = r'#define\s+(\w+)\s+(\d+\.?\d*)\s*(?://.*)?$'
    
    for match in re.finditer(define_pattern, content, re.MULTILINE):
        name = match.group(1)
        value_str = match.group(2)
        
        # Convert to appropriate type
        if '.' in value_str:
            value = float(value_str)
        else:
            value = int(value_str)
        
        config[name] = value
    
    # Validate that we got all the expected constants
    expected_keys = [
        'STATE_0_SPEED_THRESHOLD', 'STATE_0_PEPPER_DELAY', 'STATE_0_HOLD_TIME',
        'STATE_0_COLOR_R', 'STATE_0_COLOR_G', 'STATE_0_COLOR_B', 'STATE_0_BRIGHTNESS',
        'STATE_1_RPM_MIN', 'STATE_1_RPM_MAX', 'STATE_1_LEDS_PER_SIDE',
        'STATE_1_COLOR_R', 'STATE_1_COLOR_G', 'STATE_1_COLOR_B', 'STATE_1_BRIGHTNESS',
        'STATE_2_RPM_MIN', 'STATE_2_RPM_MAX',
        'STATE_2_PULSE_PERIOD', 'STATE_2_MIN_BRIGHTNESS', 'STATE_2_MAX_BRIGHTNESS',
        'STATE_2_COLOR_R', 'STATE_2_COLOR_G', 'STATE_2_COLOR_B',
        'STATE_3_RPM_MIN', 'STATE_3_RPM_MAX',
        'STATE_3_COLOR_R', 'STATE_3_COLOR_G', 'STATE_3_COLOR_B', 'STATE_3_BRIGHTNESS',
        'STATE_4_RPM_MIN', 'STATE_4_RPM_MAX',
        'STATE_4_FLASH_SPEED_MIN', 'STATE_4_FLASH_SPEED_MAX',
        'STATE_4_BAR_R', 'STATE_4_BAR_G', 'STATE_4_BAR_B',
        'STATE_4_FLASH_1_R', 'STATE_4_FLASH_1_G', 'STATE_4_FLASH_1_B',
        'STATE_4_FLASH_2_R', 'STATE_4_FLASH_2_G', 'STATE_4_FLASH_2_B',
        'STATE_4_BRIGHTNESS',
        'STATE_5_RPM_MIN',
        'STATE_5_COLOR_R', 'STATE_5_COLOR_G', 'STATE_5_COLOR_B', 'STATE_5_BRIGHTNESS',
        'ERROR_PEPPER_DELAY', 'ERROR_HOLD_TIME',
        'ERROR_COLOR_R', 'ERROR_COLOR_G', 'ERROR_COLOR_B', 'ERROR_BRIGHTNESS'
    ]
    
    missing_keys = [key for key in expected_keys if key not in config]
    if missing_keys:
        print(f"Warning: Missing constants from LEDStates.h: {missing_keys}")
    
    return config

def print_config_summary(config):
    """Print a formatted summary of the LED configuration."""
    print("\n" + "="*70)
    print("LED CONFIGURATION - MIRRORED PROGRESS BAR SYSTEM")
    print("="*70)
    
    print("\n⚪ STATE 0: IDLE/NEUTRAL (Speed = 0)")
    print(f"  Speed Threshold: {config.get('STATE_0_SPEED_THRESHOLD')} km/h")
    print(f"  Color RGB: ({config.get('STATE_0_COLOR_R')}, {config.get('STATE_0_COLOR_G')}, {config.get('STATE_0_COLOR_B')})")
    print(f"  Pepper Delay: {config.get('STATE_0_PEPPER_DELAY')}ms")
    print(f"  Hold Time: {config.get('STATE_0_HOLD_TIME')}ms")
    print(f"  Brightness: {config.get('STATE_0_BRIGHTNESS')}")
    
    print("\n🟢 STATE 1: GAS EFFICIENCY ZONE")
    print(f"  RPM Range: {config.get('STATE_1_RPM_MIN')} - {config.get('STATE_1_RPM_MAX')}")
    print(f"  Color RGB: ({config.get('STATE_1_COLOR_R')}, {config.get('STATE_1_COLOR_G')}, {config.get('STATE_1_COLOR_B')})")
    print(f"  LEDs Per Side: {config.get('STATE_1_LEDS_PER_SIDE')}")
    print(f"  Brightness: {config.get('STATE_1_BRIGHTNESS')}")
    
    print("\n🟠 STATE 2: STALL DANGER")
    print(f"  RPM Range: {config.get('STATE_2_RPM_MIN')} - {config.get('STATE_2_RPM_MAX')}")
    print(f"  Color RGB: ({config.get('STATE_2_COLOR_R')}, {config.get('STATE_2_COLOR_G')}, {config.get('STATE_2_COLOR_B')})")
    print(f"  Pulse Period: {config.get('STATE_2_PULSE_PERIOD')}ms")
    print(f"  Brightness: {config.get('STATE_2_MIN_BRIGHTNESS')} - {config.get('STATE_2_MAX_BRIGHTNESS')}")
    
    print("\n🟡 STATE 3: NORMAL DRIVING / POWER BAND")
    print(f"  RPM Range: {config.get('STATE_3_RPM_MIN')} - {config.get('STATE_3_RPM_MAX')}")
    print(f"  Color RGB: ({config.get('STATE_3_COLOR_R')}, {config.get('STATE_3_COLOR_G')}, {config.get('STATE_3_COLOR_B')})")
    print(f"  Brightness: {config.get('STATE_3_BRIGHTNESS')}")
    
    print("\n🔴 STATE 4: HIGH RPM / SHIFT DANGER")
    print(f"  RPM Range: {config.get('STATE_4_RPM_MIN')} - {config.get('STATE_4_RPM_MAX')}")
    print(f"  Bar RGB: ({config.get('STATE_4_BAR_R')}, {config.get('STATE_4_BAR_G')}, {config.get('STATE_4_BAR_B')})")
    print(f"  Flash 1 RGB: ({config.get('STATE_4_FLASH_1_R')}, {config.get('STATE_4_FLASH_1_G')}, {config.get('STATE_4_FLASH_1_B')})")
    print(f"  Flash 2 RGB: ({config.get('STATE_4_FLASH_2_R')}, {config.get('STATE_4_FLASH_2_G')}, {config.get('STATE_4_FLASH_2_B')})")
    print(f"  Flash Speed: {config.get('STATE_4_FLASH_SPEED_MIN')}ms - {config.get('STATE_4_FLASH_SPEED_MAX')}ms")
    print(f"  Brightness: {config.get('STATE_4_BRIGHTNESS')}")
    
    print("\n🛑 STATE 5: REV LIMIT CUT")
    print(f"  RPM Min: {config.get('STATE_5_RPM_MIN')}+")
    print(f"  Color RGB: ({config.get('STATE_5_COLOR_R')}, {config.get('STATE_5_COLOR_G')}, {config.get('STATE_5_COLOR_B')})")
    print(f"  Brightness: {config.get('STATE_5_BRIGHTNESS')}")
    
    print("\n❌ ERROR STATE: CAN BUS READ ERROR")
    print(f"  Color RGB: ({config.get('ERROR_COLOR_R')}, {config.get('ERROR_COLOR_G')}, {config.get('ERROR_COLOR_B')})")
    print(f"  Pepper Delay: {config.get('ERROR_PEPPER_DELAY')}ms")
    print(f"  Hold Time: {config.get('ERROR_HOLD_TIME')}ms")
    print(f"  Brightness: {config.get('ERROR_BRIGHTNESS')}")
    
    print("\n" + "="*70 + "\n")

if __name__ == "__main__":
    # Test the parser
    try:
        config = load_led_config()
        print_config_summary(config)
        print("✓ Successfully parsed LEDStates.h")
        print(f"✓ Found {len(config)} constants")
    except Exception as e:
        print(f"✗ Error parsing LEDStates.h: {e}")
