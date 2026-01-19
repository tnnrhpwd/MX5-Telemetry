# MX5 Web Remote Control

Mobile web interface for controlling the MX5 Telemetry display system when parked.

## Quick Reference - Finding Your URL

**Always check the System screen (Screen 6) on the Pi display for the exact URL!**

| Network | Typical IP Address | URL to Try |
|---------|-------------------|------------|
| Home WiFi | `192.168.1.28` | `http://192.168.1.28:5000` |
| iPhone Hotspot | `172.20.10.2` - `172.20.10.4` | `http://172.20.10.2:5000` |
| Android Hotspot | `192.168.43.2` - `192.168.43.4` | `http://192.168.43.2:5000` |
| mDNS (any) | `mx5-telemetry.local` | `http://mx5-telemetry.local:5000` |

**Pro Tip:** After finding your hotspot IP once, bookmark it on your phone! It usually stays the same.

## Features

- **Screen Navigation** - Switch between all 8 display screens
- **Settings Control** - Toggle demo mode and adjust preferences
- **Real-time Sync** - WebSocket updates show current screen instantly
- **Mobile-Optimized** - Touch-friendly UI designed for phones
- **Zero Configuration** - Just open URL in browser
- **Secure** - Only accessible on local network (your hotspot)

## Setup

### 1. Install Dependencies (on Pi)

```bash
pip3 install flask flask-socketio python-socketio
```

### 2. Start Display App

The web server starts automatically with the main display app:

```bash
cd ~/MX5-Telemetry/pi/ui/src
python3 main.py
```

You'll see:
```
✓ Web remote available at http://192.168.1.28:5000
```

### 3. Find the IP Address

The easiest way to find the web remote URL is to **look at the System screen** on your Pi display:
1. Navigate to **System** screen (Screen 6)
2. Look at the **"WEB REMOTE"** card
3. The URL shown (e.g., `192.168.1.28:5000`) is what you type into your phone's browser

### 4. Connect Phone - Real-World Scenarios

#### Scenario 1: Home WiFi (Garage Start)
**What happens:** Car starts in garage, Pi auto-connects to home WiFi

**Web URL:** `http://192.168.1.28:5000`

**How to access:**
1. Phone connects to your home WiFi
2. Open browser on phone
3. Go to `http://192.168.1.28:5000`

---

#### Scenario 2: Phone Hotspot (Typical Driving)
**What happens:** You enable phone hotspot → Pi switches to phone's hotspot

**⚠️ CRITICAL LIMITATION - Wireless CarPlay:**
If your head unit uses **wireless CarPlay** (like AVH-W4500NEX), this won't work! Your phone's WiFi can only do ONE thing:
- **Option A:** Connect to CarPlay (wireless) = No hotspot = Pi can't connect
- **Option B:** Run hotspot for Pi = No wireless CarPlay

**You must choose:** Wireless CarPlay OR Pi web remote, not both.

**Workarounds:**
1. **Use wired CarPlay** - Connect phone to head unit via USB, then phone WiFi is free for hotspot
2. **Use home WiFi only** - Access web remote before leaving garage
3. **Pi as hotspot** - Configure Pi to create its own WiFi network (see below)
4. **Dedicated WiFi device** - Small travel router or secondary phone

**If using phone hotspot WITHOUT CarPlay active:**

**Web URL:** Varies by phone type
- **iPhone:** Usually `http://172.20.10.2:5000` or `http://172.20.10.3:5000`
- **Android:** Usually `http://192.168.43.2:5000` or `http://192.168.43.3:5000`

**How to access:**
1. Enable hotspot on your phone
2. Wait ~30 seconds for Pi to connect to hotspot
3. Check System screen on Pi display for exact IP
4. Open browser on phone to that IP

**Important:** With wireless CarPlay, you'll need to disconnect from CarPlay first to access the web remote.

---

#### Scenario 3: Pi as WiFi Hotspot (Recommended for Wireless CarPlay Users)

**What happens:** Pi creates its own WiFi network that your phone connects to

**Setup required:** Configure Pi as WiFi access point (one-time setup)

```bash
# Install hostapd and dnsmasq
sudo apt-get install hostapd dnsmasq

# Configure in /etc/hostapd/hostapd.conf
interface=wlan0
ssid=MX5-Telemetry
wpa_passphrase=YourPasswordHere
# ... (full config available online)
```

**Web URL:** `http://192.168.50.1:5000` (Pi's static IP as hotspot)

**How to use:**
1. Pi boots and creates WiFi network "MX5-Telemetry"
2. Connect phone to "MX5-Telemetry" WiFi  
3. Phone can now use wireless CarPlay (via head unit) AND browse to Pi
4. Open browser: `http://192.168.50.1:5000`

**Advantages:**
- ✅ Works with wireless CarPlay
- ✅ Consistent IP address (always 192.168.50.1)
- ✅ Can bookmark and forget
- ✅ Multiple devices can connect

**Disadvantages:**
- ❌ Requires one-time Pi configuration
- ❌ Pi loses internet access
- ❌ Phone must manually switch WiFi networks

---

#### Scenario 4: Can't Check Pi Display
**What happens:** You need the URL but can't look at the Pi screen

**Solution Options:**

**Option A - Try common IPs based on network:**
- Home WiFi: `http://192.168.1.28:5000`
- iPhone hotspot: Try `http://172.20.10.2:5000` through `http://172.20.10.4:5000`
- Android hotspot: Try `http://192.168.43.2:5000` through `http://192.168.43.4:5000`
- Pi hotspot: `http://192.168.50.1:5000`

**Option B - Use mDNS hostname (if configured):**
```
http://mx5-telemetry.local:5000
```

**Option C - SSH to Pi and check:**
```bash
ssh pi@raspberrypi.local
hostname -I
```

### 5. Save as Home Screen Shortcut (iOS/Android)

**iOS:**
1. Open Safari to the web remote URL
2. Tap Share button
3. Select "Add to Home Screen"
4. Name it "MX5 Remote"

**Android:**
1. Open Chrome to the web remote URL
2. Tap ⋮ (menu)
3. Select "Add to Home Screen"
4. Name it "MX5 Remote"

Now you have a native-feeling app icon!

## Usage

### Navigation
- **Previous/Next buttons** - Cycle through screens
- **Screen grid** - Jump directly to any screen
- **Active screen** - Highlighted in blue

### Settings
- **Demo Mode toggle** - Switch between demo and live data

### Features
- ✅ Live sync - changes on Pi reflect on web
- ✅ Haptic feedback - vibration on button press (if supported)
- ✅ Keyboard shortcuts - Arrow keys, 0-7 for screens
- ✅ Connection indicator - Shows connection status
- ✅ PWA ready - Can be installed as app

## Screen Reference

| # | Screen | Description |
|---|--------|-------------|
| 0 | Overview | Main dashboard with key metrics |
| 1 | RPM | Tachometer and speed |
| 2 | TPMS | Tire pressure and temperature |
| 3 | Engine | Coolant, oil, fuel, voltage |
| 4 | G-Force | Lateral and longitudinal G |
| 5 | Diagnostics | Warning lights and alerts |
| 6 | System | System info and stats |
| 7 | Settings | Configuration options |

## Troubleshooting

### Your Typical Day - Step by Step (WIRELESS CARPLAY VERSION)

**Morning in Garage:**
1. ✅ Start car → Pi boots and connects to home WiFi (192.168.1.28)
2. ✅ You can access web remote from any device on home WiFi: `http://192.168.1.28:5000`

**Leaving Garage - THE PROBLEM:**
3. ❌ Enable phone hotspot → Pi switches to phone hotspot
4. ❌ Phone connects to wireless CarPlay → **Phone STOPS being a hotspot** (WiFi taken over by CarPlay)
5. ❌ Pi loses connection, web remote becomes inaccessible

**The Reality:**
Your phone's WiFi radio can only do ONE thing at a time. You must choose:
- **Wireless CarPlay** (phone WiFi → head unit) = No web remote access
- **Phone hotspot** (phone WiFi → Pi) = No wireless CarPlay

**Practical Solutions:**

**Option 1 - Use Wired CarPlay (Easiest)**
- Connect phone to head unit via USB cable
- Phone WiFi becomes free for hotspot
- Everything works as originally described

**Option 2 - Home WiFi Only**
- Access web remote before leaving garage
- Once driving, no web remote access
- Good enough if you mainly adjust settings at home

**Option 3 - Pi as Hotspot (Best for wireless CarPlay users)**
- Configure Pi to create WiFi network "MX5-Telemetry"
- Phone connects to Pi's WiFi
- Phone can still use wireless CarPlay (head unit has separate WiFi)
- Access web remote at: `http://192.168.50.1:5000`
- Bookmark this URL - it never changes!

**Option 4 - Disconnect CarPlay Temporarily**
- When you need web remote, disconnect from CarPlay
- Enable phone hotspot
- Access web remote
- Reconnect to CarPlay when done

### Common Issues

**Can't connect to web remote:**
- Check Pi and phone are on same network
- **Look at Pi's System screen** for the exact URL to use
- Try accessing: `http://raspberrypi.local:5000`
- Check firewall not blocking port 5000

**Web page loads but buttons don't work:**
- Check Flask and SocketIO are installed
- Look at Pi terminal for errors
- Refresh page (Ctrl+F5 or Cmd+Shift+R)

**Connection keeps dropping:**
- Phone may be switching to cellular data
- Disable cellular data while using web remote
- Check Pi WiFi signal strength

## API Reference (Advanced)

### REST Endpoints

```
GET  /api/status              - Get current screen and settings
POST /api/screen/<0-7>        - Change to specific screen
POST /api/screen/next         - Next screen
POST /api/screen/prev         - Previous screen
POST /api/settings/demo       - Toggle demo mode
POST /api/wake                - Wake display from sleep
```

### WebSocket Events

**Client -> Server:**
```javascript
socket.emit('request_status');  // Request current status
```

**Server -> Client:**
```javascript
socket.on('status', (data) => {
    // Current screen, settings, etc.
});

socket.on('screen_changed', (data) => {
    // Screen changed notification
});

socket.on('setting_changed', (data) => {
    // Setting changed notification
});
```

## Security Note

The web server is **not password protected** and listens on all interfaces (`0.0.0.0`). This is intentional for ease of use, as it's only accessible on your local network (hotspot). If you need additional security:

1. Only enable hotspot when using the remote
2. Use a strong hotspot password
3. Or modify `web_server.py` to add authentication

## Performance

- **Latency:** ~50-100ms (local network)
- **Bandwidth:** ~1-5 KB/s (minimal)
- **Battery:** Negligible impact on Pi
- **Compatibility:** All modern browsers (Chrome, Safari, Firefox)

## Future Enhancements

Potential additions:
- [ ] Live telemetry readout on web UI
- [ ] TPMS pressure display
- [ ] Settings adjustment sliders
- [ ] Dark/light theme toggle
- [ ] Multiple device support
- [ ] Touch gestures for swipe navigation
