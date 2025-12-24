#!/usr/bin/env python3
"""
Direct approach - manually activate HDMI and draw something to framebuffer
This will prove if the issue is output or something else
"""
import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.1.28', username='pi', password='Hopwood12', timeout=10)

print("\n" + "="*70)
print("TESTING HDMI OUTPUT DIRECTLY")
print("="*70)

print("\n1. Forcing HDMI 1 on with tvservice...")
stdin, stdout, stderr = ssh.exec_command("tvservice -o -v 7; sleep 1; tvservice -e 'DMT 87 HDMI' -v 7")
time.sleep(2)
print(stdout.read().decode())

print("\n2. Checking status...")
stdin, stdout, stderr = ssh.exec_command("tvservice -s -v 7")
print(stdout.read().decode())

print("\n3. Unblanking framebuffer...")
stdin, stdout, stderr = ssh.exec_command("echo 0 | sudo tee /sys/class/graphics/fb0/blank")
print(f"  Blank set to: {stdout.read().decode()}")

print("\n4. Writing test pattern to framebuffer...")
# Write white screen to framebuffer
stdin, stdout, stderr = ssh.exec_command("sudo dd if=/dev/zero of=/dev/fb0 bs=800x480x4 count=1 2>&1 | head -5")
time.sleep(1)
print(stdout.read().decode())

print("\n5. Check framebuffer settings...")
stdin, stdout, stderr = ssh.exec_command("fbset -fb /dev/fb0")
print(stdout.read().decode())

print("\n" + "="*70)
print("CHECK PIONEER NOW")
print("="*70)
print("\nI just:")
print("  1. Forced HDMI 1 on")
print("  2. Unblanked the framebuffer")
print("  3. Wrote data to /dev/fb0")
print("\nDo you see ANYTHING on the Pioneer now?")
print("(Should see white/pattern if framebuffer is reaching HDMI)")

response = input("\nDo you see output on Pioneer? (y/n): ").strip().lower()

if response == 'y':
    print("\n✓ Good! HDMI hardware path works.")
    print("Issue: Your display application isn't writing to fb0")
    print("or console is being redirected elsewhere.")
elif response == 'n':
    print("\n✗ No output even with direct framebuffer write.")
    print("This means:")
    print("  - HDMI hardware connection issue, OR")
    print("  - Pi is outputting to wrong HDMI port, OR")
    print("  - Console/framebuffer is mapped to wrong port")
    print("\nLet me check which physical port is actually active...")
    
    print("\nTesting: Turn OFF HDMI 1, turn ON HDMI 0...")
    stdin, stdout, stderr = ssh.exec_command("tvservice -o -v 7; tvservice -e 'DMT 87 HDMI' -v 2")
    time.sleep(2)
    
    response2 = input("\nDid anything appear on Pioneer? (y/n): ").strip().lower()
    if response2 == 'y':
        print("\n⚠ FOUND THE PROBLEM!")
        print("The Pioneer is physically connected to HDMI 0 (first port, near USB-C)")
        print("NOT HDMI 1 (second port, far from USB-C)")
        print("\nYou said you want port 2 (far from USB-C) but cable might be in port 1?")
    else:
        print("\nNeither port showing output. Let me check cables and config...")

ssh.close()
print("\nDone!")
