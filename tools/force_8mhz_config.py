#!/usr/bin/env python3
"""
Fix MCP2515 4MHz -> 8MHz by editing /boot/config.txt and forcing the correct format
Then reboot to apply
"""

import paramiko

PI_IP = "192.168.1.23"
PI_USER = "pi"
PI_PASS = "Hopwood12"

def run_command(ssh, command):
    """Execute command and print output"""
    print(f"  $ {command}")
    stdin, stdout, stderr = ssh.exec_command(command)
    output = stdout.read().decode()
    error = stderr.read().decode()
    if output:
        print(output)
    if error:
        print(f"    Error: {error}")
    return output, error

print("=" * 70)
print("Force MCP2515 8MHz Oscillator - Config Fix")
print("=" * 70)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    print(f"\nConnecting to {PI_IP}...")
    ssh.connect(PI_IP, username=PI_USER, password=PI_PASS, timeout=10)
    print("✓ Connected\n")
    
    print("[1/3] Backing up current config.txt...")
    run_command(ssh, "sudo cp /boot/config.txt /boot/config.txt.backup_$(date +%Y%m%d_%H%M%S)")
    
    print("\n[2/3] Removing old MX5 config and adding correct one...")
    
    # Remove old config section
    run_command(ssh, "sudo sed -i '/MX5-Telemetry CAN Bus Configuration/,/^$/d' /boot/config.txt")
    
    # Add new correct config at the end before [HDMI:1]
    new_config = """

# =============================================================================
# MX5-Telemetry CAN Bus Configuration
# =============================================================================
dtparam=spi=on
dtoverlay=mcp2515-can0,oscillator=8000000,interrupt=25,spimaxfrequency=1000000
dtoverlay=mcp2515-can1,oscillator=8000000,interrupt=24,spimaxfrequency=1000000
enable_uart=1
"""
    
    # Create temp file with new config
    stdin, stdout, stderr = ssh.exec_command(f"cat >> /tmp/mx5_can_config.txt << 'EOFMARKER'{new_config}EOFMARKER\n")
    stdout.read()
    
    # Insert before [HDMI:1] section
    run_command(ssh, "sudo sed -i '/\\[HDMI:1\\]/r /tmp/mx5_can_config.txt' /boot/config.txt")
    
    print("\n[3/3] Verifying config...")
    output, _ = run_command(ssh, "grep -A 5 'MX5-Telemetry CAN' /boot/config.txt")
    
    print("\n" + "=" * 70)
    print("Config updated! MUST REBOOT to apply.")
    print("=" * 70)
    print("\nReboot now? (y/n): ", end='')
    
    response = input()
    if response.lower() == 'y':
        print("\nRebooting Pi...")
        ssh.exec_command("sudo reboot")
        print("✓ Reboot initiated")
        print("\nWait 40 seconds then run:")
        print("  python tools\\diagnose_can0_live.py")
        print("\nShould show: clock 8000000 and receiving packets!")
    else:
        print("\nSkipped reboot - manual reboot required:")
        print("  ssh pi@192.168.1.23 'sudo reboot'")
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    ssh.close()
