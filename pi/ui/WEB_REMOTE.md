# MX5 Web Remote Control

Mobile web interface for controlling the MX5 Telemetry display system when parked.

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

### 3. Connect Phone

#### Option A: Pi Hotspot Mode
1. Enable hotspot on Pi (or configure in Pi settings)
2. Connect phone to Pi's hotspot
3. Open browser: `http://192.168.1.28:5000`

#### Option B: Phone Hotspot Mode (Recommended)
1. Enable hotspot on your phone
2. Connect Pi to your phone's hotspot
3. Find Pi's IP address: `hostname -I`
4. Open browser: `http://[PI_IP]:5000`

### 4. Save as Home Screen Shortcut (iOS/Android)

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

**Can't connect to web remote:**
- Check Pi and phone are on same network
- Verify Pi IP address: `hostname -I`
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
