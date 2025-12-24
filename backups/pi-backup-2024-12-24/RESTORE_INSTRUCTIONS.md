# MX5 Telemetry Pi Backup - December 24, 2024

## What's Backed Up
- `boot-config.txt` - /boot/config.txt (HDMI, CAN bus, SPI settings)
- `boot-cmdline.txt` - /boot/cmdline.txt (kernel parameters)
- `mx5-display.service` - Systemd service for MX5 display app
- `mx5-can-setup.sh` - CAN bus initialization script
- `installed-packages.txt` - All installed apt packages
- `pip-packages.txt` - Python packages
- `enabled-services.txt` - Enabled systemd services
- `network-info.txt` - Network configuration
- `bashrc` - User bash config

## Full SD Card Backup (Recommended)

For a complete backup that can fully restore the Pi:

1. **Shutdown the Pi cleanly:**
   ```
   ssh pi@192.168.1.28 "sudo shutdown -h now"
   ```

2. **Remove the SD card** from the Pi

3. **Insert into Windows PC** using SD card reader

4. **Download Win32 Disk Imager:**
   https://sourceforge.net/projects/win32diskimager/

5. **Create image:**
   - Open Win32 Disk Imager
   - Select the SD card drive (e.g., E:)
   - Choose image file: `MX5-Pi-Backup-2024-12-24.img`
   - Click "Read" to create the image

6. **Store the .img file** safely (it will be ~32GB or your SD card size)

## Restore from Full Image

1. Insert new SD card
2. Open Win32 Disk Imager
3. Select the .img file
4. Select the SD card
5. Click "Write"

## Restore Config Files Only (Fresh Pi Setup)

If starting from a fresh Raspberry Pi OS:

```bash
# 1. Copy boot config
sudo cp boot-config.txt /boot/config.txt
sudo cp boot-cmdline.txt /boot/cmdline.txt

# 2. Install MX5 display service
sudo cp mx5-display.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mx5-display

# 3. Install CAN setup script
sudo cp mx5-can-setup.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/mx5-can-setup.sh

# 4. Clone the MX5-Telemetry repo
cd ~
git clone https://github.com/tnnrhpwd/MX5-Telemetry.git

# 5. Install Python packages
pip3 install pygame python-can

# 6. Reboot
sudo reboot
```

## Key Settings Reference

### HDMI (720p for Pioneer)
- hdmi_group=1
- hdmi_mode=4
- hdmi_drive=2
- dtoverlay=vc4-fkms-v3d,audio=on

### CAN Bus
- dtparam=spi=on
- dtoverlay=mcp2515-can0,oscillator=8000000,interrupt=25
- dtoverlay=mcp2515-can1,oscillator=8000000,interrupt=24

### Pi IP Address
- Static: 192.168.1.28
