#!/usr/bin/env python3
"""
Check webapp status and IP addresses
"""

import paramiko

PI_IP = "192.168.1.23"
PI_USER = "pi"
PI_PASSWORD = "Hopwood12"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_IP, username=PI_USER, password=PI_PASSWORD, timeout=10)

print("=" * 70)
print("WEBAPP STATUS & IP CONFIGURATION")
print("=" * 70)

# Check if webapp is running
print("\n[Web Server Status]")
stdin, stdout, stderr = ssh.exec_command("ps aux | grep '[w]eb_server.py'")
output = stdout.read().decode()
if output:
    print("  ✓ Web server is RUNNING")
else:
    print("  ✗ Web server is NOT running")

# Check what port it's listening on
stdin, stdout, stderr = ssh.exec_command("netstat -tlnp 2>/dev/null | grep python || ss -tlnp 2>/dev/null | grep python")
port_output = stdout.read().decode()
if port_output:
    print("\n[Listening Ports]")
    for line in port_output.split('\n'):
        if line.strip():
            print(f"  {line}")

# Get current IP addresses
print("\n[Current IP Addresses]")
stdin, stdout, stderr = ssh.exec_command("hostname -I")
ips = stdout.read().decode().strip().split()
for ip in ips:
    print(f"  {ip}")

# Check WiFi configuration
print("\n[WiFi Configuration]")
stdin, stdout, stderr = ssh.exec_command("cat /etc/wpa_supplicant/wpa_supplicant.conf 2>/dev/null | grep -E 'ssid=|psk=' | head -4")
wifi_config = stdout.read().decode()
if wifi_config:
    print(wifi_config)

# Check if hostapd (hotspot) is configured
print("\n[Hotspot Configuration]")
stdin, stdout, stderr = ssh.exec_command("cat /etc/hostapd/hostapd.conf 2>/dev/null | grep -E 'ssid=|channel='")
hotspot_config = stdout.read().decode()
if hotspot_config:
    print("  ✓ Hotspot configured:")
    print(hotspot_config)
else:
    print("  ✗ No hotspot configuration found")

# Check dhcpcd.conf for static IPs
print("\n[Network Interface Configuration]")
stdin, stdout, stderr = ssh.exec_command("cat /etc/dhcpcd.conf 2>/dev/null | grep -A3 'interface wlan0' | head -6")
dhcp_config = stdout.read().decode()
if dhcp_config:
    print(dhcp_config)

print("\n" + "=" * 70)
print("TYPICAL IP ADDRESSES")
print("=" * 70)
print("\nWhen connected to WiFi (current mode):")
print(f"  • Pi IP: {PI_IP}")
print(f"  • Webapp URL: http://{PI_IP}:5000")
print("\nWhen Pi is Hotspot (Access Point mode):")
print("  • Pi IP: 192.168.4.1 (typical)")
print("  • Webapp URL: http://192.168.4.1:5000")
print("  • Hotspot SSID: MX5-Telemetry (or similar)")
print("\nTo access webapp:")
print("  1. Connect device to same network as Pi")
print("  2. Open browser to http://<pi-ip>:5000")
print("=" * 70 + "\n")

ssh.close()
