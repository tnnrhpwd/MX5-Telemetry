# Pi Network Access Information

## Quick Reference

### SSH Access
```bash
# Home WiFi Network
ssh pi@192.168.1.23
ssh pi@mx5pi.local

# Phone Hotspot (Tanner's Galaxy)
ssh pi@10.62.26.67
```

### Web Interface
- Home: http://192.168.1.23:5000
- Hotspot: http://10.62.26.67:5000

### Finding Pi on Network
If you need to locate the Pi on a different network:

```powershell
# Windows - Find IP from ARP table
ipconfig  # Note your IP range
arp -a | Select-String "10.62"  # Adjust for your network range

# Try SSH to each device
ssh pi@<ip-address> "hostname"
# Response "raspberrypi" confirms it's the Pi
```

```bash
# Linux/Mac - Scan network
nmap -sn 192.168.1.0/24  # Home network
nmap -sn 10.62.26.0/24   # Hotspot range
```

## Network Configuration

### Pi WiFi Settings
The Pi is configured to automatically connect to:
1. **Priority 1:** Home WiFi (192.168.1.x)
2. **Priority 2:** Tanner's Galaxy Hotspot (10.62.26.x)

Configuration file: `/etc/wpa_supplicant/wpa_supplicant.conf`

### Hostname
- mDNS hostname: `mx5pi.local`
- Works on most home networks
- May not work on phone hotspots (use IP directly)

## Deployment

The `flash_all_updates.ps1` script automatically tries all network addresses:
1. mx5pi.local (mDNS)
2. 192.168.1.23 (home WiFi static)
3. 10.62.26.67 (typical hotspot IP)

No manual configuration needed!
