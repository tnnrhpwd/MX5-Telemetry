#!/usr/bin/env python3
"""Diagnose HDMI 2 (second port) issues with Pioneer"""
import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print("Connecting to Pi...")
ssh.connect('192.168.1.28', username='pi', password='Hopwood12', timeout=10)

print("\n" + "="*70)
print("HDMI DIAGNOSTICS")
print("="*70)

commands = [
    ("List available displays", "tvservice -l"),
    ("HDMI 0 status (port near USB-C)", "tvservice -s -v 2"),
    ("HDMI 1 status (port away from USB-C)", "tvservice -s -v 7"),
    ("Display power status", "vcgencmd display_power"),
    ("Current config HDMI:1 section", "grep -A15 'HDMI:1' /boot/config.txt"),
    ("All HDMI settings in config", "grep -i hdmi /boot/config.txt | head -40"),
    ("Check for DRM/KMS driver", "dmesg | grep -i 'drm\\|hdmi' | tail -20"),
    ("Framebuffer devices", "ls -la /dev/fb*"),
    ("DRM devices", "ls -la /sys/class/drm/"),
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
    if err:
        print(f"STDERR: {err}")

# Try to get more specific info
print("\n" + "="*70)
print("CHECKING KMS/DRM CONNECTORS")
print("="*70)
stdin, stdout, stderr = ssh.exec_command("for d in /sys/class/drm/card?-HDMI-*; do echo \"$d:\"; cat $d/status 2>/dev/null || echo 'N/A'; cat $d/enabled 2>/dev/null || echo 'N/A'; done")
print(stdout.read().decode())

ssh.close()
print("\nDiagnostics complete!")
