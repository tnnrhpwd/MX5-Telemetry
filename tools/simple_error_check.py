#!/usr/bin/env python3
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.1.23', username='pi', password='Hopwood12', timeout=10)

print("=" * 60)
print("MCP2515 ERROR CHECK")
print("=" * 60)

# Check for MCP errors in dmesg
print("\nChecking kernel log for MCP2515 errors...")
stdin, stdout, stderr = ssh.exec_command('dmesg | grep -i mcp2515 | tail -10')
mcp_log = stdout.read().decode()
print(mcp_log if mcp_log else "  (No recent MCP2515 messages)")

# Check for any errors
stdin, stdout, stderr = ssh.exec_command('dmesg | grep -i mcp2515 | grep -iE "error|fail|timeout"')
errors = stdout.read().decode()
if errors:
    print("\n⚠️  ERRORS FOUND:")
    print(errors)
else:
    print("\n✓ No MCP2515 errors in kernel log")

# Check CAN interface errors
print("\nChecking CAN interface error counters...")
stdin, stdout, stderr = ssh.exec_command('ip -s link show can0')
can0_stats = stdout.read().decode()
stdin, stdout, stderr = ssh.exec_command('ip -s link show can1')
can1_stats = stdout.read().decode()

if 'errors:' in can0_stats:
    print("\ncan0 stats:")
    for line in can0_stats.split('\n'):
        if 'RX:' in line or 'TX:' in line or 'errors:' in line:
            print(f"  {line.strip()}")

if 'errors:' in can1_stats:
    print("\ncan1 stats:")
    for line in can1_stats.split('\n'):
        if 'RX:' in line or 'TX:' in line or 'errors:' in line:
            print(f"  {line.strip()}")

print("\n" + "=" * 60)
ssh.close()
