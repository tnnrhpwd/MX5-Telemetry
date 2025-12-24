#!/usr/bin/env python3
"""
Force HDMI 2 output by ensuring proper configuration
The issue might be that with FKMS, only one HDMI port can be active at a time
and we need to ensure it's using the correct physical port (HDMI 1 = second port)
"""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print("Connecting to Pi...")
ssh.connect('192.168.1.28', username='pi', password='Hopwood12', timeout=10)

print("\n" + "="*70)
print("TESTING PHYSICAL HDMI PORTS")
print("="*70)

# First, let's check which physical port is actually outputting
print("\nCurrent status:")
print("-"*70)
stdin, stdout, stderr = ssh.exec_command("tvservice -s -v 7")
print("HDMI 1 (second port):", stdout.read().decode())

# Check the kernel command line for video parameter
stdin, stdout, stderr = ssh.exec_command("cat /proc/cmdline | grep -o 'video=[^ ]*'")
video_param = stdout.read().decode().strip()
print(f"\nKernel video parameter: {video_param}")

# The issue: HDMI-A-1 refers to the first DRM connector, which might be HDMI 0
# We need to check if we should be using HDMI-A-2 for the second physical port
stdin, stdout, stderr = ssh.exec_command("ls -la /sys/class/drm/ | grep HDMI")
drm_connectors = stdout.read().decode()
print("\nDRM HDMI connectors:")
print(drm_connectors)

# With FKMS, both ports might map to the same DRM device
# Let's check the actual config.txt being used
print("\n" + "="*70)
print("SOLUTION: Check if we need to disable HDMI 0 explicitly")
print("="*70)

# Read current config
stdin, stdout, stderr = ssh.exec_command('cat /boot/config.txt')
config = stdout.read().decode()

# Check if we have conflicting settings
if 'video=HDMI-A-1' in video_param and '[HDMI:1]' in config:
    print("\n⚠ PROBLEM FOUND:")
    print("- Kernel cmdline forces HDMI-A-1 (first connector)")
    print("- But config.txt has [HDMI:1] section (second port)")
    print("- These might be conflicting")
    
# Check if HDMI:0 is explicitly disabled
if '[HDMI:0]' in config:
    print("\n✓ HDMI:0 section found in config")
else:
    print("\n⚠ HDMI:0 section NOT found - we should disable it explicitly")
    
    # We need to add an HDMI:0 section to disable the first port
    print("\nAdding [HDMI:0] section to disable first port...")
    
    # Find where to insert it (before [HDMI:1])
    import re
    
    hdmi0_section = """
# =============================================================================
# HDMI:0 Configuration - DISABLED (using HDMI:1 for Pioneer instead)
# =============================================================================
[HDMI:0]
hdmi_ignore_hotplug=1

"""
    
    # Insert before [HDMI:1]
    new_config = re.sub(
        r'(# HDMI:1 Configuration)',
        hdmi0_section + r'\1',
        config
    )
    
    # Write it back
    cmd = f'''sudo tee /boot/config.txt > /dev/null << 'EOF'
{new_config}
EOF'''
    
    stdin, stdout, stderr = ssh.exec_command(cmd)
    err = stderr.read().decode()
    if err:
        print(f"Error: {err}")
    else:
        print("✓ Config updated with HDMI:0 disabled")
        
        # Verify
        stdin, stdout, stderr = ssh.exec_command('grep -B2 -A2 "HDMI:0" /boot/config.txt')
        print("\nNew HDMI:0 section:")
        print(stdout.read().decode())
        
        print("\n" + "="*70)
        print("REBOOT REQUIRED")
        print("="*70)
        print("\nThe first HDMI port has been disabled in config.")
        print("After reboot, only HDMI 1 (second port, farthest from USB-C)")
        print("will be active and output to the Pioneer.")
        
        response = input("\nReboot now? (y/n): ").strip().lower()
        if response == 'y':
            print("\nRebooting...")
            ssh.exec_command('sudo reboot')
            print("Reboot initiated!")
        else:
            print("\nRun 'sudo reboot' when ready.")

ssh.close()
print("\nDone!")
