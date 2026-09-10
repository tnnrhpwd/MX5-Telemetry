#!/usr/bin/env python3
"""
Check CAN interface configuration
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.lib.pi_ssh import connect as pi_connect


PI_IP = "192.168.1.23"
PI_USER = "pi"

ssh = pi_connect(host=PI_IP, user=PI_USER, timeout=10)
print("CAN INTERFACE CONFIGURATION")
print("=" * 70)

print("\n[can0 interface status]")
stdin, stdout, stderr = ssh.exec_command("ip link show can0")
print(stdout.read().decode())

print("\n[can1 interface status]")
stdin, stdout, stderr = ssh.exec_command("ip link show can1")
print(stdout.read().decode())

print("\n[Checking CAN bitrates]")
stdin, stdout, stderr = ssh.exec_command("ip -details link show can0 | grep -i bitrate")
can0_bitrate = stdout.read().decode().strip()
print(f"can0: {can0_bitrate if can0_bitrate else 'No bitrate info'}")

stdin, stdout, stderr = ssh.exec_command("ip -details link show can1 | grep -i bitrate")
can1_bitrate = stdout.read().decode().strip()
print(f"can1: {can1_bitrate if can1_bitrate else 'No bitrate info'}")

print("\n[Checking which MCP2515 is on which interface]")
stdin, stdout, stderr = ssh.exec_command("dmesg | grep -i mcp251 | tail -10")
print(stdout.read().decode())

ssh.close()
