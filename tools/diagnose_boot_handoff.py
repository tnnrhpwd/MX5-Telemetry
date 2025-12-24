#!/usr/bin/env python3
"""
Diagnose why HDMI signal is lost after boot text appears
This is typically a KMS/framebuffer handoff issue
"""
import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print("Connecting to Pi...")
time.sleep(3)  # Give it a moment after reboot
try:
    ssh.connect('192.168.1.28', username='pi', password='Hopwood12', timeout=15)
except Exception as e:
    print(f"Connection failed: {e}")
    print("Pi might still be booting. Wait a moment and try again.")
    exit(1)

print("\n" + "="*70)
print("BOOT TO DESKTOP HANDOFF DIAGNOSTICS")
print("="*70)

commands = [
    ("Check which framebuffer is active", "fbset -fb /dev/fb0"),
    ("Check HDMI status after boot", "tvservice -s -v 7"),
    ("Check display power", "vcgencmd display_power"),
    ("Check for mode switch errors in dmesg", "dmesg | grep -i 'hdmi\\|mode\\|fb' | tail -30"),
    ("Check KMS driver status", "dmesg | grep -i 'drm\\|vc4' | tail -20"),
    ("Check X11 display status", "DISPLAY=:0 xrandr 2>&1 | head -20"),
    ("Check console mode", "cat /sys/class/graphics/fb0/mode"),
    ("Check virtual console", "cat /sys/class/graphics/fb0/virtual_size"),
]

for desc, cmd in commands:
    print(f"\n{'='*70}")
    print(f">>> {desc}")
    print(f"$ {cmd}")
    print("-"*70)
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out:
        print(out)
    if err and 'DISPLAY' not in cmd:
        print(f"STDERR: {err}")

# Check if console is blanking
print("\n" + "="*70)
print("CHECKING CONSOLE BLANKING SETTINGS")
print("="*70)
stdin, stdout, stderr = ssh.exec_command("cat /boot/cmdline.txt")
cmdline = stdout.read().decode()
print("Current cmdline.txt:")
print(cmdline)

issues = []
if 'consoleblank=' not in cmdline:
    issues.append("- No consoleblank setting (default is 600s)")
if 'logo.nologo' in cmdline:
    issues.append("- logo.nologo prevents boot logo")
if 'fbcon=' not in cmdline:
    issues.append("- No explicit framebuffer console settings")

if issues:
    print("\n⚠ POTENTIAL ISSUES FOUND:")
    for issue in issues:
        print(issue)

ssh.close()
print("\nDiagnostics complete!")
