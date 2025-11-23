# LED Simulator Arduino Connection Feature

## Overview
The LED Simulator v2.1 now supports real-time control of physical Arduino LEDs to mirror the simulator visualization.

## Features Added

### 1. Arduino Connection UI
- **Port Selection Dropdown**: Lists available serial ports
- **Refresh Button**: Updates port list (🔄)
- **Connect/Disconnect Button**: Establishes serial connection
- **Status Indicator**: Shows connection state
  - ⚪ Not Connected (gray)
  - 🟢 Connected (green)
  - ❌ Connection Lost (red)
  - ⚠️ Select a port (orange warning)

### 2. Python Serial Communication
- **Auto-detection**: Automatically detects available COM ports
- **Connection Settings**: 115200 baud, no flow control
- **RPM Synchronization**: Sends RPM values to Arduino in real-time
- **Format**: `RPM:xxxx\n` (e.g., "RPM:5000\n")
- **Optimization**: Only sends when RPM changes by 50+ to reduce serial traffic
- **Auto-reconnect**: Disconnects on errors with clear status indication

### 3. Arduino Firmware Changes

#### CommandHandler Enhancements
- **New Command**: `RPM:xxxx` command handler
- **LED Integration**: Direct connection to LEDController
- **Immediate Update**: Updates LED strip instantly on RPM command

#### Files Modified
1. **CommandHandler.cpp**
   - Added `handleRPM(const char* command)` method
   - Parses RPM value from command string
   - Calls `ledController->setRPM(rpm)` and `ledController->update()`

2. **CommandHandler.h**
   - Added `LEDController* ledController` member
   - Added `setLEDController()` setter method
   - Added `handleRPM()` declaration

3. **LEDController.h**
   - Added `setRPM(uint16_t rpm)` inline method
   - Added `update()` method to force display refresh

4. **main.cpp**
   - Added `cmdHandler.setLEDController(&ledStrip)` in setup()

5. **led_simulator_v2.1.py**
   - Added serial/pyserial imports with availability checking
   - Added Arduino connection UI controls
   - Added `refresh_ports()`, `toggle_arduino_connection()`, `send_rpm_to_arduino()` methods
   - Integrated RPM sending in simulation loop
   - Added cleanup on close

## Usage

### Starting the Simulator
1. Run the LED Simulator: `venv\Scripts\python.exe tools\LED_Simulator\led_simulator_v2.1.py`
2. The Arduino connection panel appears in the control frame (requires pyserial)

### Connecting to Arduino
1. **Upload Firmware**: Flash the updated firmware to your Arduino Nano
2. **Select Port**: Use the dropdown to select your Arduino's COM port (e.g., COM3)
3. **Refresh Ports**: Click 🔄 if you don't see your port
4. **Connect**: Click "Connect" button
5. **Wait**: Arduino initializes for ~2 seconds
6. **Verify**: Status shows "🟢 Connected"

### Using Real-Time LED Control
1. **Start Engine**: Click "🔴 START ENGINE" in simulator (hold Shift+Down+Space)
2. **Drive**: Use arrow keys to control throttle/brake
3. **Watch LEDs**: Physical LED strip mirrors simulator display in real-time
4. **RPM Sync**: LEDs update instantly as simulator RPM changes

### Disconnecting
1. Click "Disconnect" button
2. Status shows "⚪ Not Connected"
3. Simulator continues working normally

## Technical Details

### Serial Protocol
```
Command Format: RPM:<value>\n
Example: RPM:5000\n

Arduino Response: None (silent mode for performance)
```

### Performance
- **Update Rate**: ~20 times per second (limited by 50 RPM threshold)
- **Latency**: <50ms from simulator to LED update
- **Serial Overhead**: Minimal (~10 bytes per update)

### Error Handling
- Port selection validation
- Connection timeout detection
- Automatic disconnection on errors
- Clear error messages in status label

## Requirements

### Python Dependencies
```
pyserial>=3.5
serial.tools.list_ports (included with pyserial)
```

Install with:
```bash
pip install pyserial
```

### Arduino Requirements
- Arduino Nano V3.0 (ATmega328P)
- WS2812B LED strip connected to pin 5
- USB connection to laptop
- Updated firmware with RPM command handler

## Troubleshooting

### "No ports found"
- Check USB cable connection
- Ensure Arduino is powered on
- Click 🔄 to refresh port list
- Check Device Manager for COM port assignment

### Connection fails
- Verify correct COM port selected
- Close other programs using the port (Arduino IDE, Serial Monitor, etc.)
- Check Arduino is running correct firmware
- Try unplugging and reconnecting Arduino

### LEDs not responding
- Verify firmware was uploaded successfully
- Check LED strip wiring (pin 5, GND, 5V)
- Test with Arduino Actions tool to verify LEDs work
- Check serial connection status indicator

### "pyserial not available"
- Arduino connection panel won't appear
- Install pyserial: `pip install pyserial`
- Restart LED Simulator

## Future Enhancements
- [ ] Bidirectional communication (Arduino status → simulator)
- [ ] Multiple LED strip support
- [ ] Custom RPM mapping presets
- [ ] Connection profiles (save favorite ports)
- [ ] Automatic port detection and connection
- [ ] LED brightness control from simulator
