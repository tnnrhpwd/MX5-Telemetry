#!/usr/bin/env python3
"""Check CANBUS data on Raspberry Pi"""

import paramiko
import time
import sys

# Connection details
PI_IP = "192.168.1.23"
PI_USER = "pi"
PI_PASSWORD = "Hopwood12"

def check_can_interfaces(ssh):
    """Check available CAN interfaces"""
    print("=" * 60)
    print("CHECKING CAN INTERFACES")
    print("=" * 60)
    stdin, stdout, stderr = ssh.exec_command("ip link show | grep -E 'can|slcan'")
    interfaces = stdout.read().decode()
    print(interfaces)
    return interfaces

def check_can_stats(ssh, interface="can0"):
    """Check CAN interface statistics"""
    print("\n" + "=" * 60)
    print(f"CAN STATISTICS FOR {interface}")
    print("=" * 60)
    stdin, stdout, stderr = ssh.exec_command(f"ip -s link show {interface}")
    stats = stdout.read().decode()
    print(stats)

def listen_for_can_messages(ssh, interface="can0", count=50):
    """Listen for CAN messages"""
    print("\n" + "=" * 60)
    print(f"LISTENING FOR {count} CAN MESSAGES ON {interface}")
    print("=" * 60)
    print("Waiting for messages...")
    
    # Use timeout to avoid hanging forever
    stdin, stdout, stderr = ssh.exec_command(f"timeout 10 candump {interface} -n {count} 2>&1", get_pty=True)
    
    # Stream output as it arrives
    while True:
        line = stdout.readline()
        if not line:
            break
        print(line.strip())
    
    error = stderr.read().decode()
    if error:
        print(f"Error: {error}")

def main():
    print(f"Connecting to Pi at {PI_IP}...")
    
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(PI_IP, username=PI_USER, password=PI_PASSWORD, timeout=10)
        
        print("✓ Connected to Pi\n")
        
        # Check interfaces
        interfaces = check_can_interfaces(ssh)
        
        # Check stats
        check_can_stats(ssh, "can0")
        
        # Listen for messages
        listen_for_can_messages(ssh, "can0", count=50)
        
        ssh.close()
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
