#!/usr/bin/env python3
"""
Emergency recovery - disable the keepalive service and restore VNC access
"""
import paramiko
import time

print("Attempting to connect to Pi...")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

for attempt in range(10):
    try:
        ssh.connect('192.168.1.28', username='pi', password='Hopwood12', timeout=15)
        print(f"✓ Connected on attempt {attempt+1}")
        break
    except Exception as e:
        print(f"Attempt {attempt+1}/10 failed: {e}")
        if attempt < 9:
            time.sleep(5)
        else:
            print("\nCannot connect to Pi. It may need a hard reboot (power cycle).")
            print("After power cycling:")
            print("1. Wait for it to boot (2 minutes)")
            print("2. Run this script again to clean up")
            exit(1)

print("\n" + "="*70)
print("EMERGENCY RECOVERY")
print("="*70)

print("\n1. Stopping hdmi-keepalive service...")
stdin, stdout, stderr = ssh.exec_command("sudo systemctl stop hdmi-keepalive.service")
time.sleep(1)
print("  ✓ Stopped")

print("\n2. Disabling hdmi-keepalive service...")
stdin, stdout, stderr = ssh.exec_command("sudo systemctl disable hdmi-keepalive.service")
print("  ✓ Disabled")

print("\n3. Removing service files...")
stdin, stdout, stderr = ssh.exec_command("sudo rm /etc/systemd/system/hdmi-keepalive.service /usr/local/bin/hdmi-keepalive.sh 2>/dev/null")
stdin, stdout, stderr = ssh.exec_command("sudo systemctl daemon-reload")
print("  ✓ Removed")

print("\n4. Checking VNC service...")
stdin, stdout, stderr = ssh.exec_command("sudo systemctl status vncserver-x11-serviced.service | head -10")
vnc_status = stdout.read().decode()
print(vnc_status)

if "active (running)" not in vnc_status:
    print("\n5. Restarting VNC service...")
    stdin, stdout, stderr = ssh.exec_command("sudo systemctl restart vncserver-x11-serviced.service")
    time.sleep(2)
    print("  ✓ VNC restarted")

print("\n6. Checking if X/display is running...")
stdin, stdout, stderr = ssh.exec_command("ps aux | grep -E 'Xorg|startx' | grep -v grep")
x_status = stdout.read().decode()
if x_status:
    print("  ✓ X is running")
else:
    print("  ⚠ X might not be running")

print("\n" + "="*70)
print("RECOVERY COMPLETE")
print("="*70)
print("\nProblematic service has been removed.")
print("Try connecting to VNC now at: 192.168.1.28")
print("\nIf VNC still doesn't work, the Pi may need a reboot:")

response = input("\nReboot Pi now? (y/n): ").strip().lower()
if response == 'y':
    print("\nRebooting...")
    ssh.exec_command('sudo reboot')
    print("✓ Rebooting - wait 60 seconds then try VNC")

ssh.close()
print("\nDone!")
