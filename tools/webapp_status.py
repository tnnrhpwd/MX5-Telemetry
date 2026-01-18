#!/usr/bin/env python3
import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.1.23", username='pi', password='Hopwood12', timeout=10)

time.sleep(3)

stdin, stdout, stderr = ssh.exec_command("ss -tlnp | grep :5000")
result = stdout.read().decode()

print("=" * 60)
if ":5000" in result:
    print("✓ WEBAPP IS RUNNING!")
    print("=" * 60)
    print("\n📱 Open on your phone:\n")
    print("   http://192.168.1.23:5000")
    print("\n(Phone must be on same WiFi)")
else:
    print("⏳ Still starting... checking in 5 seconds")
    print("=" * 60)
    time.sleep(5)
    stdin, stdout, stderr = ssh.exec_command("ss -tlnp | grep :5000")
    result2 = stdout.read().decode()
    if ":5000" in result2:
        print("\n✓ NOW RUNNING!")
        print("\n📱 http://192.168.1.23:5000")
    else:
        print("\n✗ Not running - checking logs")

print("=" * 60)
ssh.close()
