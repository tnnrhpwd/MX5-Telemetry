#!/usr/bin/env python3
"""
Deep dive into why HDMI signal disappears
Check if display manager or console is killing the signal
"""
import paramiko
import time

print("Waiting for Pi to fully boot...")
time.sleep(15)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.1.28', username='pi', password='Hopwood12', timeout=10)

print("\n" + "="*70)
print("DEEP HDMI OUTPUT DIAGNOSTICS")
print("="*70)

commands = [
    ("Check which displays tvservice sees", "tvservice -l"),
    ("HDMI 0 status (should be off/unused)", "tvservice -s -v 2 2>&1"),
    ("HDMI 1 status (should be active)", "tvservice -s -v 7"),
    ("Display power state", "vcgencmd display_power"),
    ("Check what owns fb0", "fuser /dev/fb0 2>&1 || echo 'Nothing using fb0'"),
    ("Framebuffer info", "fbset -fb /dev/fb0"),
    ("Check for X server", "ps aux | grep X | grep -v grep"),
    ("Check systemd display service", "systemctl status mx5-display.service 2>&1 | head -20"),
    ("Console VT status", "fgconsole 2>&1 || echo 'No VT'"),
    ("Check if console is blanked", "cat /sys/class/graphics/fb0/blank 2>&1"),
]

results = {}
for desc, cmd in commands:
    print(f"\n{'='*70}")
    print(f">>> {desc}")
    print(f"$ {cmd}")
    print("-"*70)
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    result = out if out else err
    results[desc] = result
    print(result)

print("\n" + "="*70)
print("ANALYSIS")
print("="*70)

# Check if HDMI 1 is actually on
if "state 0x" in results.get("HDMI 1 status (should be active)", ""):
    print("\n✓ HDMI 1 (port 7) is active in tvservice")
    if "800x480" in results.get("HDMI 1 status (should be active)", ""):
        print("✓ Resolution is correct (800x480)")
    else:
        print("⚠ Resolution might be wrong")
else:
    print("\n✗ HDMI 1 (port 7) is NOT active - this is the problem!")

# Check if framebuffer is blanked
blank_value = results.get("Check if console is blanked", "").strip()
if blank_value and blank_value != "0":
    print(f"\n⚠ Framebuffer is BLANKED (blank={blank_value})")
    print("  0 = normal, 1 = blanked")
    print("  This could be why you see no output!")
else:
    print(f"\n✓ Framebuffer not blanked (blank={blank_value})")

# Check if something is actually drawing to fb0
if "Nothing using fb0" in results.get("Check what owns fb0", ""):
    print("\n⚠ Nothing is using /dev/fb0!")
    print("  Your display application needs to be writing to fb0")
else:
    print("\n✓ Something is using /dev/fb0")

print("\n" + "="*70)
print("RECOMMENDED FIX")
print("="*70)
print("\nIssue: Boot text works (firmware), but then signal stops")
print("\nLikely causes:")
print("1. Console is switching away or blanking")
print("2. Display service might not be running")
print("3. Need to explicitly keep HDMI 1 powered and active")
print("\nI'll now apply a fix to force HDMI to stay on...")

ssh.close()
