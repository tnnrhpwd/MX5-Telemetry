#!/usr/bin/env python3
"""
Check what's happening after boot and try full KMS instead of FKMS
FKMS (Fake KMS) might be causing the handoff issue
"""
import paramiko
import time

print("Waiting for Pi to boot...")
time.sleep(10)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.1.28', username='pi', password='Hopwood12', timeout=10)

print("\n" + "="*70)
print("POST-BOOT DIAGNOSTICS")
print("="*70)

commands = [
    ("DRM connector status", "cat /sys/class/drm/card*/status 2>/dev/null || echo 'No DRM status'"),
    ("DRM connector enabled", "cat /sys/class/drm/card*/enabled 2>/dev/null || echo 'No enabled status'"),
    ("List DRM devices", "ls -la /sys/class/drm/"),
    ("HDMI status", "tvservice -s -v 7"),
    ("Framebuffer info", "fbset -fb /dev/fb0"),
    ("Check what's using fb0", "fuser /dev/fb0 2>&1"),
    ("Check if X is running", "ps aux | grep -E 'X|startx|xinit' | grep -v grep"),
    ("KMS initialization from dmesg", "dmesg | grep -i 'drm\\|vc4\\|hdmi\\|fb0' | tail -25"),
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
    if err and 'grep' not in cmd:
        print(f"STDERR: {err}")

print("\n" + "="*70)
print("ANALYSIS")
print("="*70)

# Check if we should try full KMS instead
stdin, stdout, stderr = ssh.exec_command("grep 'vc4-fkms-v3d' /boot/config.txt")
has_fkms = stdout.read().decode().strip()

if has_fkms:
    print("\nCurrently using: FKMS (Fake KMS)")
    print("Problem: FKMS has known issues with dual HDMI output")
    print("\nSolution options:")
    print("1. Try full KMS (vc4-kms-v3d) - better DRM support")
    print("2. Disable KMS entirely - use legacy framebuffer")
    print("\nRecommendation: Try disabling KMS for now (legacy mode)")
    print("This will keep the firmware in control of HDMI throughout boot")

ssh.close()
