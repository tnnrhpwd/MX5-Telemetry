"""
ESP32-S3 Serial Handler for Raspberry Pi

Handles bidirectional serial communication with ESP32-S3 round display:
- Receives: TPMS data (BLE sensors) and IMU data (QMI8658 G-force)
- Sends: CAN telemetry data, screen navigation, and SWC button events

Serial Connection (USB-C - preferred):
    Pi USB-A port -> ESP32-S3 USB-C port
    Shows as /dev/ttyACM0 on Pi (USB CDC)
    Single cable for power AND data!

Serial Connection (GPIO UART - alternative):
    Pi GPIO 14 (TXD) -> ESP32 RX (GPIO 44)
    Pi GPIO 15 (RXD) -> ESP32 TX (GPIO 43)
    Baud: 115200

Protocol (ESP32 -> Pi):
    TPMS:0,32.5,25.3,95\n    - Tire 0: PSI, temp °C, battery %
    TPMS:1,31.8,24.1,92\n    - Tire 1
    TPMS:2,33.1,26.0,88\n    - Tire 2
    TPMS:3,32.9,25.8,90\n    - Tire 3
    TPMS_PSI:FL,FR,RL,RR\n   - BLE TPMS pressures (all 4 tires)
    TPMS_TEMP:FL,FR,RL,RR\n  - BLE TPMS temperatures (all 4 tires)
    IMU:0.25,-0.15\n         - G-force: lateral, longitudinal
    OK:SCREEN_X\n            - Confirmation of screen change

Protocol (Pi -> ESP32):
    TEL:3500,65,3,45,185,1,72,95,1,0,0\n  - RPM,speed,gear,throttle,coolant,oil,ambient_temp,fuel,engine,gear_est,clutch
    SCREEN:0\n                        - Change to screen 0 (Overview)
    SCREEN:1\n                        - Change to screen 1 (RPM)
    LEFT\n                            - Next screen
    RIGHT\n                           - Previous screen
    SWC:RES_PLUS\n                    - Steering wheel button event
"""

import threading
import time
import glob
import json
import os
import queue
from typing import Optional

# Try to import serial library
try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    print("Warning: pyserial not installed. ESP32 serial disabled.")

# TPMS data persistence file
TPMS_CACHE_FILE = "/home/pi/MX5-Telemetry/data/tpms_cache.json"


class ESP32SerialHandler:
    """Handles serial communication with ESP32-S3 display"""
    
    # Serial port options (tried in order)
    USB_PORTS = ['/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyUSB0', '/dev/ttyUSB1']
    GPIO_PORT = '/dev/serial0'  # Pi GPIO UART (14/15)
    BAUD_RATE = 115200
    
    # Screen mapping (must match ESP32 ScreenMode enum - 8 screens)
    SCREEN_OVERVIEW = 0
    SCREEN_RPM = 1
    SCREEN_TPMS = 2
    SCREEN_ENGINE = 3
    SCREEN_GFORCE = 4
    SCREEN_DIAGNOSTICS = 5
    SCREEN_SYSTEM = 6
    SCREEN_SETTINGS = 7
    
    def __init__(self, telemetry_data, port: str = None, on_screen_change=None,
                 on_setting_change=None, on_settings_sync=None):
        """
        Args:
            telemetry_data: TelemetryData object to update with received values
            port: Serial port path (default: auto-detect USB then GPIO)
            on_screen_change: Callback function(screen_index) called when ESP32 changes screen
            on_setting_change: Callback function(name, value) called when single setting changes on ESP32
            on_settings_sync: Callback function(settings_dict) called when full settings received
        """
        self.telemetry = telemetry_data
        self.port = port  # Will be auto-detected if None
        self.on_screen_change = on_screen_change  # Callback for bidirectional sync
        self.on_setting_change = on_setting_change  # Callback for single setting change
        self.on_settings_sync = on_settings_sync  # Callback for full settings sync
        self.on_selection_change = None  # Callback for settings selection change
        
        self.serial_conn = None
        self._running = False
        self._read_thread = None
        self._write_lock = threading.Lock()  # Lock for serial writes
        
        # Async write queue - screen changes are queued and processed by background thread
        # This prevents blocking the main UI thread when navigating pages
        self._write_queue = queue.Queue()
        self._pending_screen = None  # Last queued screen (only latest matters)
        
        self.connected = False
        self.last_rx_time = 0
        self.last_tx_time = 0
        self.last_imu_time = 0  # Track when last IMU data was received
        
        # Current ESP32 screen (synced from acknowledgements)
        self.esp32_screen = 0
        
        # TPMS data cache (updated from ESP32)
        self.tpms_pressure = [0.0, 0.0, 0.0, 0.0]  # PSI
        self.tpms_temp = [0.0, 0.0, 0.0, 0.0]      # °C
        self.tpms_battery = [0, 0, 0, 0]           # %
        self.tpms_last_update = 0                  # timestamp of last TPMS data
        self.tpms_last_update_str = ["--:--:--", "--:--:--", "--:--:--", "--:--:--"]  # HH:MM:SS per tire
        
        # Load cached TPMS data from disk
        self._load_tpms_cache()
    
    def _load_tpms_cache(self):
        """Load cached TPMS data from disk to persist through reloads"""
        try:
            if os.path.exists(TPMS_CACHE_FILE):
                with open(TPMS_CACHE_FILE, 'r') as f:
                    data = json.load(f)
                    
                # Restore cached values - update in-place to preserve list references
                if 'pressure' in data and len(data['pressure']) == 4:
                    self.tpms_pressure = list(data['pressure'])
                    for i in range(4):
                        self.telemetry.tire_pressure[i] = data['pressure'][i]
                    
                if 'temp' in data and len(data['temp']) == 4:
                    self.tpms_temp = list(data['temp'])  # Stored as Celsius
                    for i in range(4):
                        # Convert Celsius to Fahrenheit for telemetry display
                        self.telemetry.tire_temp[i] = data['temp'][i] * 9.0 / 5.0 + 32
                    
                if 'battery' in data and len(data['battery']) == 4:
                    self.tpms_battery = list(data['battery'])
                    
                if 'timestamp' in data:
                    self.tpms_last_update = data['timestamp']
                    
                # Restore per-tire HH:MM:SS timestamp strings
                if 'last_update_str' in data:
                    cached_timestamps = data['last_update_str']
                    # Handle both old single-string format and new list format
                    if isinstance(cached_timestamps, list) and len(cached_timestamps) == 4:
                        self.tpms_last_update_str = list(cached_timestamps)
                        for i in range(4):
                            self.telemetry.tpms_last_update_str[i] = cached_timestamps[i]
                    elif isinstance(cached_timestamps, str):
                        # Old format - apply same timestamp to all tires
                        self.tpms_last_update_str = [cached_timestamps] * 4
                        for i in range(4):
                            self.telemetry.tpms_last_update_str[i] = cached_timestamps
                    
                # Mark as connected if we have recent cached data (within 24 hours)
                age_hours = (time.time() - self.tpms_last_update) / 3600
                if age_hours < 24 and any(p > 0 for p in self.tpms_pressure):
                    self.telemetry.tpms_connected = True
                    print(f"TPMS: Loaded cached data (age: {age_hours:.1f} hours)")
                    print(f"  Last updates: FL={self.tpms_last_update_str[0]}, FR={self.tpms_last_update_str[1]}, RL={self.tpms_last_update_str[2]}, RR={self.tpms_last_update_str[3]}")
                    print(f"  Pressures: FL={self.tpms_pressure[0]:.1f}, FR={self.tpms_pressure[1]:.1f}, RL={self.tpms_pressure[2]:.1f}, RR={self.tpms_pressure[3]:.1f} PSI")
                    print(f"  Temps: FL={self.tpms_temp[0]:.1f}, FR={self.tpms_temp[1]:.1f}, RL={self.tpms_temp[2]:.1f}, RR={self.tpms_temp[3]:.1f} °C")
                else:
                    print(f"TPMS: Cache expired or empty (age: {age_hours:.1f} hours)")
            else:
                print(f"TPMS: No cache file found at {TPMS_CACHE_FILE}")
        except Exception as e:
            print(f"TPMS: Failed to load cache: {e}")
    
    def _save_tpms_cache(self, updated_tires=None):
        """Save TPMS data to disk for persistence
        
        Args:
            updated_tires: List of tire indices (0-3) that were updated, or None for all
        """
        try:
            # Ensure directory exists
            cache_dir = os.path.dirname(TPMS_CACHE_FILE)
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir)
            
            # Generate HH:MM:SS timestamp from current time
            now = time.localtime()
            current_time_str = f"{now.tm_hour:02d}:{now.tm_min:02d}:{now.tm_sec:02d}"
            
            # Update timestamps for specific tires or all tires
            if updated_tires is not None:
                for i in updated_tires:
                    self.tpms_last_update_str[i] = current_time_str
                    self.telemetry.tpms_last_update_str[i] = current_time_str
            else:
                for i in range(4):
                    self.tpms_last_update_str[i] = current_time_str
                    self.telemetry.tpms_last_update_str[i] = current_time_str
                
            data = {
                'pressure': self.tpms_pressure,
                'temp': self.tpms_temp,
                'battery': self.tpms_battery,
                'timestamp': time.time(),
                'last_update_str': self.tpms_last_update_str
            }
            
            with open(TPMS_CACHE_FILE, 'w') as f:
                json.dump(data, f, indent=2)
                
            print(f"TPMS: Saved cache (updated tires: {updated_tires if updated_tires else 'all'})")
        except Exception as e:
            print(f"TPMS: Failed to save cache: {e}")
    
    def _find_serial_port(self) -> Optional[str]:
        """Auto-detect ESP32 serial port (USB preferred over GPIO)"""
        # Try USB ports first (ESP32-S3 USB CDC)
        for port in self.USB_PORTS:
            try:
                import os
                if os.path.exists(port):
                    # Try to open it briefly
                    test = serial.Serial(port, self.BAUD_RATE, timeout=0.1)
                    test.close()
                    print(f"Found ESP32 on USB: {port}")
                    return port
            except Exception:
                pass
        
        # Fall back to GPIO UART
        try:
            import os
            if os.path.exists(self.GPIO_PORT):
                print(f"Using GPIO UART: {self.GPIO_PORT}")
                return self.GPIO_PORT
        except Exception:
            pass
        
        return None
    
    def _try_connect(self) -> bool:
        """Try to establish serial connection to ESP32"""
        # Close existing connection if any
        if self.serial_conn:
            try:
                self.serial_conn.close()
            except:
                pass
            self.serial_conn = None
        
        # Auto-detect port
        port = self._find_serial_port()
        if not port:
            return False
        
        try:
            self.serial_conn = serial.Serial(
                port=port,
                baudrate=self.BAUD_RATE,
                timeout=0.1,
                write_timeout=0.1
            )
            self.port = port
            self.connected = True
            print(f"ESP32 serial connected on {port}")
            return True
        except Exception as e:
            print(f"ESP32 serial connect failed: {e}")
            return False
        
    def start(self) -> bool:
        """Initialize and start serial communication"""
        if not SERIAL_AVAILABLE:
            print("Serial library not available")
            return False
        
        # Try initial connection
        if not self._try_connect():
            print("ESP32 not found - will keep trying in background")
        
        # Start background thread regardless (it will handle reconnection)
        self._running = True
        self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._read_thread.start()
        
        return True  # Always return True - connection will be established when ESP32 is ready
    
    def stop(self):
        """Stop serial communication"""
        self._running = False
        
        if self._read_thread:
            self._read_thread.join(timeout=1.0)
        
        if self.serial_conn:
            self.serial_conn.close()
        
        self.connected = False
    
    def _read_loop(self):
        """Read incoming data from ESP32 and process write queue in background thread.
        Handles automatic reconnection when ESP32 restarts."""
        buffer = ""
        last_screen_send = 0  # Rate limiting for screen commands
        last_reconnect_attempt = 0
        reconnect_interval = 2.0  # Try reconnecting every 2 seconds
        consecutive_errors = 0
        
        while self._running:
            # Handle reconnection if not connected
            if not self.serial_conn or not self.connected:
                now = time.time()
                if now - last_reconnect_attempt >= reconnect_interval:
                    last_reconnect_attempt = now
                    if self._try_connect():
                        buffer = ""  # Clear buffer on reconnect
                        consecutive_errors = 0
                        print("ESP32: Reconnected successfully")
                    else:
                        time.sleep(0.5)
                        continue
                else:
                    time.sleep(0.1)
                    continue
            
            try:
                # Process any pending screen changes from queue (non-blocking)
                # Only send latest screen command (skip intermediate ones)
                if self._pending_screen is not None:
                    now = time.time()
                    # Rate limit to 10Hz (100ms between screen commands)
                    if now - last_screen_send >= 0.10:
                        screen_idx = self._pending_screen
                        self._pending_screen = None  # Clear pending
                        try:
                            with self._write_lock:
                                msg = f"SCREEN:{screen_idx}\n"
                                self.serial_conn.write(msg.encode('utf-8'))
                                # No flush() - let it send naturally to avoid blocking
                                last_screen_send = now
                                self.last_tx_time = now
                                print(f"ESP32: Sent SCREEN:{screen_idx} (async)")
                        except Exception as e:
                            print(f"ESP32 screen write error: {e}")
                            consecutive_errors += 1
                
                # Read incoming data
                if self.serial_conn.in_waiting > 0:
                    data = self.serial_conn.read(self.serial_conn.in_waiting)
                    buffer += data.decode('utf-8', errors='ignore')
                    consecutive_errors = 0  # Reset on successful read
                    
                    # Process complete lines
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        if line:
                            self._process_line(line)
                            self.last_rx_time = time.time()
                else:
                    time.sleep(0.01)  # Small sleep to prevent busy-waiting
                
                # Check for stale connection (no data for 10+ seconds when we expect data)
                if time.time() - self.last_rx_time > 10.0 and self.last_rx_time > 0:
                    consecutive_errors += 1
                    
            except serial.SerialException as e:
                print(f"ESP32 serial error (will reconnect): {e}")
                self.connected = False
                consecutive_errors += 1
                time.sleep(0.5)
            except OSError as e:
                # Device disconnected (common when ESP32 restarts)
                print(f"ESP32 disconnected (will reconnect): {e}")
                self.connected = False
                if self.serial_conn:
                    try:
                        self.serial_conn.close()
                    except:
                        pass
                    self.serial_conn = None
                consecutive_errors = 0  # Expected during restart
                time.sleep(0.5)
            except Exception as e:
                print(f"ESP32 serial read error: {e}")
                consecutive_errors += 1
                time.sleep(0.1)
            
            # If too many consecutive errors, force reconnect
            if consecutive_errors > 10:
                print("ESP32: Too many errors, forcing reconnect...")
                self.connected = False
                if self.serial_conn:
                    try:
                        self.serial_conn.close()
                    except:
                        pass
                    self.serial_conn = None
                consecutive_errors = 0
    
    def _process_line(self, line: str):
        """Process a complete line from ESP32"""
        try:
            if line.startswith("TPMS:"):
                self._parse_tpms(line[5:])
            elif line.startswith("TPMS_PSI:"):
                # BLE TPMS pressure data: TPMS_PSI:FL,FR,RL,RR
                self._parse_tpms_psi(line[9:])
            elif line.startswith("TPMS_TEMP:"):
                # BLE TPMS temperature data: TPMS_TEMP:FL,FR,RL,RR
                self._parse_tpms_temp(line[10:])
            elif line.startswith("IMU:"):
                self._parse_imu(line[4:])
            elif line.startswith("SCREEN_CHANGED:"):
                # ESP32 user changed screen via touch - sync Pi display
                try:
                    new_screen = int(line[15:])
                    self.esp32_screen = new_screen
                    print(f"ESP32: Screen changed to {new_screen} via touch")
                    if self.on_screen_change:
                        self.on_screen_change(new_screen)
                except ValueError:
                    pass
            elif line.startswith("SETTING:"):
                # Single setting changed on ESP32 - sync to Pi
                self._parse_setting(line[8:])
            elif line.startswith("SELECTION:"):
                # Settings selection changed on ESP32 - sync to Pi
                try:
                    selection = int(line[10:])
                    if self.on_selection_change:
                        self.on_selection_change(selection)
                except ValueError:
                    pass
            elif line.startswith("SETTINGS:"):
                # All settings from ESP32 - full sync
                self._parse_all_settings(line[9:])
            elif line.startswith("OK:SCREEN_"):
                # Screen change acknowledgement
                try:
                    self.esp32_screen = int(line[10:])
                except ValueError:
                    pass
            elif line.startswith("OK:SET:"):
                # Setting change acknowledgement
                print(f"ESP32: Setting confirmed - {line[7:]}")
            elif line.startswith("OK:"):
                # Other acknowledgements (SCREEN_NEXT, SCREEN_PREV, etc.)
                pass
            elif line.startswith("Touch I2C"):
                # Ignore touch debug messages
                pass
            elif line.startswith("PERF:"):
                # Performance monitoring from ESP32 - always print for debugging
                print(f"ESP32 {line}")
            else:
                # Log unknown messages for debugging
                print(f"ESP32: {line}")
        except Exception as e:
            print(f"Error parsing ESP32 data '{line}': {e}")
    
    def _parse_setting(self, data: str):
        """Parse a single setting from ESP32: name=value"""
        if '=' not in data:
            return
        name, value = data.split('=', 1)
        name = name.strip()
        value = value.strip()
        
        # Call the callback if registered
        if self.on_setting_change:
            self.on_setting_change(name, value)
        print(f"ESP32: Setting changed - {name}={value}")
    
    def _parse_all_settings(self, data: str):
        """Parse all settings from ESP32: name1=val1,name2=val2,..."""
        settings_dict = {}
        for pair in data.split(','):
            if '=' in pair:
                name, value = pair.split('=', 1)
                settings_dict[name.strip()] = value.strip()
        
        # Call callback with all settings
        if self.on_settings_sync:
            self.on_settings_sync(settings_dict)
        print(f"ESP32: Full settings sync - {len(settings_dict)} settings received")
    
    def _parse_tpms(self, data: str):
        """Parse TPMS data: sensor_num,psi,temp_c,battery"""
        parts = data.split(',')
        if len(parts) >= 4:
            sensor = int(parts[0])
            if 0 <= sensor <= 3:
                psi = float(parts[1])
                temp_c = float(parts[2])
                battery = int(parts[3])
                
                # Update cache
                self.tpms_pressure[sensor] = psi
                self.tpms_temp[sensor] = temp_c
                self.tpms_battery[sensor] = battery
                
                # Update telemetry object
                self.telemetry.tire_pressure[sensor] = psi
                # Convert C to F for display
                self.telemetry.tire_temp[sensor] = temp_c * 9.0 / 5.0 + 32.0
    
    def _parse_tpms_psi(self, data: str):
        """Parse BLE TPMS pressure data: FL,FR,RL,RR (all in PSI)"""
        parts = data.split(',')
        if len(parts) >= 4:
            updated_tires = []
            for i in range(4):
                try:
                    psi = float(parts[i])
                    if psi > 0:  # Only update if valid (non-zero)
                        self.tpms_pressure[i] = psi
                        self.telemetry.tire_pressure[i] = psi
                        self.telemetry.tpms_connected = True
                        updated_tires.append(i)
                except (ValueError, IndexError):
                    pass
            if updated_tires:
                self.tpms_last_update = time.time()
                self._save_tpms_cache(updated_tires)  # Persist with per-tire timestamps
            print(f"TPMS BLE PSI: {self.telemetry.tire_pressure}")
    
    def _parse_tpms_temp(self, data: str):
        """Parse BLE TPMS temperature data: FL,FR,RL,RR (all in Fahrenheit)"""
        parts = data.split(',')
        if len(parts) >= 4:
            updated_tires = []
            for i in range(4):
                try:
                    temp_f = float(parts[i])
                    if temp_f != 0:  # Only update if valid
                        self.tpms_temp[i] = (temp_f - 32) * 5.0 / 9.0  # Store as Celsius
                        self.telemetry.tire_temp[i] = temp_f  # Already in F
                        self.telemetry.tpms_connected = True
                        updated_tires.append(i)
                except (ValueError, IndexError):
                    pass
            if updated_tires:
                self.tpms_last_update = time.time()
                self._save_tpms_cache(updated_tires)  # Persist with per-tire timestamps
            print(f"TPMS BLE Temp: {self.telemetry.tire_temp}")
    
    def _parse_imu(self, data: str):
        """Parse IMU data: accelX,accelY,accelZ,gyroX,gyroY,gyroZ,linearX,linearY,pitch,roll"""
        parts = data.split(',')
        if len(parts) >= 2:
            # Always parse the first 2 for backward compatibility
            self.telemetry.g_lateral = float(parts[0])
            self.telemetry.g_longitudinal = float(parts[1])
            
            # Parse extended data if available
            if len(parts) >= 10:
                self.telemetry.g_vertical = float(parts[2])
                self.telemetry.gyro_x = float(parts[3])
                self.telemetry.gyro_y = float(parts[4])
                self.telemetry.gyro_z = float(parts[5])
                self.telemetry.linear_accel_x = float(parts[6])
                self.telemetry.linear_accel_y = float(parts[7])
                self.telemetry.orientation_pitch = float(parts[8])
                self.telemetry.orientation_roll = float(parts[9])
            
            # Track when IMU data was last received
            self.last_imu_time = time.time()
    
    def send_telemetry(self):
        """Send current telemetry data to ESP32"""
        if not self.serial_conn or not self._running or not self.connected:
            return
        
        # Priority: If there's a pending screen change, send it first and skip telemetry
        if hasattr(self, '_pending_screen_index') and self._pending_screen_index is not None:
            now = time.time()
            if hasattr(self, '_last_screen_send_time'):
                elapsed = now - self._last_screen_send_time
                if elapsed >= 0.10:
                    pending = self._pending_screen_index
                    self._pending_screen_index = None
                    self.send_screen_change(pending)
                    return  # Skip telemetry this cycle to let ESP32 process screen change
            return  # Skip telemetry while screen change is pending
        
        try:
            # Use lock to prevent collision with screen commands
            with self._write_lock:
                # Combine all telemetry into fewer messages to reduce serial traffic
                # Format: TEL:rpm,speed,gear,throttle,coolant,oil_ok,fuel,engine,gear_est,clutch
                msg = f"TEL:{self.telemetry.rpm:.0f},{self.telemetry.speed_kmh:.0f},{self.telemetry.gear},"
                msg += f"{self.telemetry.throttle_percent:.0f},{self.telemetry.coolant_temp_f:.0f},"
                oil_val = 1 if self.telemetry.oil_status else 0
                msg += f"{oil_val},"
                fuel_pct = self.telemetry.fuel_level_percent
                msg += f"{fuel_pct:.0f},"
                # DEBUG: Log what we're sending
                if fuel_pct > 0:
                    print(f"DEBUG: Sending fuel={fuel_pct:.1f}% to ESP32")
                engine_running = 1 if self.telemetry.rpm > 0 else 0
                msg += f"{engine_running},"
                # Add gear estimation and clutch flags
                gear_est = 1 if self.telemetry.gear_estimated else 0
                clutch = 1 if self.telemetry.clutch_engaged else 0
                msg += f"{gear_est},{clutch}\n"
                
                # DEBUG: Log fuel value
                if fuel_pct == 0:
                    print(f"DEBUG: Sending fuel={fuel_pct:.0f}% (telemetry.fuel_level_percent={self.telemetry.fuel_level_percent})")
                
                self.serial_conn.write(msg.encode('utf-8'))
                
                # Send diagnostics (less frequently important)
                diag_msg = f"DIAG:{int(self.telemetry.check_engine_light)},{int(self.telemetry.abs_warning)},"
                # Oil warning is the INVERSE of oil_status (True = OK, False = WARNING)
                oil_warning = not self.telemetry.oil_status
                diag_msg += f"{int(oil_warning)},{int(self.telemetry.battery_warning)},"
                diag_msg += f"{int(self.telemetry.headlights_on)},{int(self.telemetry.high_beams_on)}\n"
                self.serial_conn.write(diag_msg.encode('utf-8'))
                
                # Send tire pressure data from cache (FL, FR, RL, RR)
                tire_msg = f"TIRE:{self.telemetry.tire_pressure[0]:.1f},{self.telemetry.tire_pressure[1]:.1f},"
                tire_msg += f"{self.telemetry.tire_pressure[2]:.1f},{self.telemetry.tire_pressure[3]:.1f}\n"
                self.serial_conn.write(tire_msg.encode('utf-8'))
                
                # Send tire temperature data from cache (FL, FR, RL, RR in Fahrenheit)
                tire_temp_msg = f"TIRE_TEMP:{self.telemetry.tire_temp[0]:.1f},{self.telemetry.tire_temp[1]:.1f},"
                tire_temp_msg += f"{self.telemetry.tire_temp[2]:.1f},{self.telemetry.tire_temp[3]:.1f}\n"
                self.serial_conn.write(tire_temp_msg.encode('utf-8'))
                
                # Send tire timestamps (HH:MM:SS per tire)
                tire_time_msg = f"TIRE_TIME:{self.tpms_last_update_str[0]},{self.tpms_last_update_str[1]},"
                tire_time_msg += f"{self.tpms_last_update_str[2]},{self.tpms_last_update_str[3]}\n"
                self.serial_conn.write(tire_time_msg.encode('utf-8'))
                
                # Flush all at once
                self.serial_conn.flush()
                self.last_tx_time = time.time()
            
        except Exception as e:
            print(f"ESP32 serial write error: {e}")
    
    def send_swc_button(self, button_name: str):
        """Send steering wheel button event to ESP32"""
        if not self.serial_conn or not self._running:
            return
        
        try:
            msg = f"SWC:{button_name}\n"
            self.serial_conn.write(msg.encode('utf-8'))
            self.last_tx_time = time.time()
            
        except Exception as e:
            print(f"ESP32 serial write error: {e}")
    
    def is_receiving_data(self) -> bool:
        """Check if we're receiving data from ESP32"""
        return (time.time() - self.last_rx_time) < 2.0
    
    def send_screen_change(self, screen_index: int):
        """
        Queue screen change command to ESP32 display (async/non-blocking).
        
        The command is queued and sent by the background thread.
        Only the latest screen is kept - intermediate screens are skipped.
        This prevents UI blocking when navigating between pages.
        
        Args:
            screen_index: Screen number (0-7)
        """
        if not self._running:
            print(f"ESP32: Cannot send screen {screen_index} - handler not running")
            return
        
        if not self.connected:
            print(f"ESP32: Cannot send screen {screen_index} - not connected (will retry on reconnect)")
        
        # Clamp to valid range (ESP32 has 8 screens)
        screen_index = max(0, min(7, screen_index))
        
        # Queue for async send by background thread
        # Only keep latest screen command (overwrite any pending)
        self._pending_screen = screen_index
        print(f"ESP32: Queued SCREEN:{screen_index} (async)")
    
    
    def send_next_screen(self):
        """Send next screen command to ESP32"""
        if not self.serial_conn or not self._running or not self.connected:
            return
        
        try:
            self.serial_conn.write(b"LEFT\n")
            self.last_tx_time = time.time()
        except Exception as e:
            print(f"ESP32 serial write error: {e}")
    
    def send_prev_screen(self):
        """Send previous screen command to ESP32"""
        if not self.serial_conn or not self._running or not self.connected:
            return
        
        try:
            self.serial_conn.write(b"RIGHT\n")
            self.last_tx_time = time.time()
        except Exception as e:
            print(f"ESP32 serial write error: {e}")
    
    def send_calibrate_imu(self):
        """Send command to ESP32 to calibrate IMU gyroscope zero point"""
        if not self.serial_conn or not self._running or not self.connected:
            print("ESP32: Cannot calibrate IMU - not connected")
            return False
        
        try:
            with self._write_lock:
                self.serial_conn.write(b"CAL_IMU\n")
                self.serial_conn.flush()
                self.last_tx_time = time.time()
                print("ESP32: Sent IMU calibration command")
                return True
        except Exception as e:
            print(f"ESP32 IMU calibration error: {e}")
            return False
    
    def send_setting(self, name: str, value):
        """
        Send a single setting to ESP32 display for synchronization.
        
        Args:
            name: Setting name (brightness, volume, shift_rpm, redline_rpm, 
                  use_mph, tire_low_psi, coolant_warn, demo_mode, timeout)
            value: Setting value (int, float, or bool)
        """
        if not self.serial_conn or not self._running or not self.connected:
            return
        
        try:
            # Convert bool to int for transmission
            if isinstance(value, bool):
                value = 1 if value else 0
            elif isinstance(value, float):
                value = f"{value:.1f}"
            
            msg = f"SET:{name}={value}\n"
            self.serial_conn.write(msg.encode('utf-8'))
            self.last_tx_time = time.time()
            print(f"ESP32: Sent setting {name}={value}")
            
        except Exception as e:
            print(f"ESP32 serial write error: {e}")
    
    def send_selection(self, index: int):
        """Send settings selection index to ESP32 for hover sync"""
        if not self.serial_conn or not self._running or not self.connected:
            return

        try:
            msg = f"SELECTION:{index}\n"
            self.serial_conn.write(msg.encode('utf-8'))
            self.last_tx_time = time.time()
        except Exception as e:
            print(f"ESP32 serial write error: {e}")
    
    def send_nav_lock(self, locked: bool):
        """Send navigation lock state to ESP32 for visual indicator"""
        if not self.serial_conn or not self._running or not self.connected:
            return
        
        try:
            msg = f"NAVLOCK:{1 if locked else 0}\n"
            self.serial_conn.write(msg.encode('utf-8'))
            self.last_tx_time = time.time()
            print(f"ESP32: Sent NAVLOCK:{1 if locked else 0}")
        except Exception as e:
            print(f"ESP32 serial write error: {e}")

    def send_all_settings(self, settings):
        """
        Send all settings to ESP32 for full synchronization.
        
        Args:
            settings: Settings object with attributes:
                brightness, volume, shift_rpm, redline_rpm, use_mph, 
                tire_low_psi, coolant_warn_f, demo_mode, led_sequence
        """
        if not self._running or not self.connected:
            return
        
        self.send_setting("brightness", settings.brightness)
        self.send_setting("volume", settings.volume)
        self.send_setting("shift_rpm", settings.shift_rpm)
        self.send_setting("redline_rpm", settings.redline_rpm)
        self.send_setting("use_mph", settings.use_mph)
        self.send_setting("tire_low_psi", settings.tire_low_psi)
        self.send_setting("coolant_warn", settings.coolant_warn_f)
        self.send_setting("demo_mode", settings.demo_mode)
        # LED sequence - syncs to ESP32 display settings
        if hasattr(settings, 'led_sequence'):
            self.send_setting("led_sequence", settings.led_sequence)
    
    def request_settings(self):
        """Request all current settings from ESP32"""
        if not self.serial_conn or not self._running or not self.connected:
            return
        
        try:
            self.serial_conn.write(b"GET_SETTINGS\n")
            self.last_tx_time = time.time()
        except Exception as e:
            print(f"ESP32 serial write error: {e}")


# =============================================================================
# Setup Instructions
# =============================================================================
"""
To use UART serial on Raspberry Pi with ESP32-S3:

1. Enable UART on Pi:
   sudo raspi-config
   -> Interface Options -> Serial Port
   -> Login shell: NO
   -> Serial hardware: YES

2. Add to /boot/config.txt:
   enable_uart=1
   dtoverlay=disable-bt  # Optional: disable Bluetooth to free up UART

3. Install pyserial:
   pip install pyserial

4. Wire connections:
   Pi GPIO 14 (TXD, Pin 8)  -> ESP32 RX (GPIO 44)
   Pi GPIO 15 (RXD, Pin 10) -> ESP32 TX (GPIO 43)
   Pi GND                   -> ESP32 GND

5. Test serial:
   # On Pi:
   python3 -c "import serial; s=serial.Serial('/dev/serial0', 115200); print('OK')"
"""
