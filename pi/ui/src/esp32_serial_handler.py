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
    IMU:0.25,-0.15\n         - G-force: lateral, longitudinal
    OK:SCREEN_X\n            - Confirmation of screen change

Protocol (Pi -> ESP32):
    TEL:3500,65,3,45,185,210,14.2\n  - RPM,speed,gear,throttle,coolant,oil,voltage
    SCREEN:0\n                        - Change to screen 0 (Overview)
    SCREEN:1\n                        - Change to screen 1 (RPM)
    LEFT\n                            - Next screen
    RIGHT\n                           - Previous screen
    SWC:RES_PLUS\n                    - Steering wheel button event
"""

import threading
import time
import glob
from typing import Optional

# Try to import serial library
try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    print("Warning: pyserial not installed. ESP32 serial disabled.")


class ESP32SerialHandler:
    """Handles serial communication with ESP32-S3 display"""
    
    # Serial port options (tried in order)
    USB_PORTS = ['/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyUSB0', '/dev/ttyUSB1']
    GPIO_PORT = '/dev/serial0'  # Pi GPIO UART (14/15)
    BAUD_RATE = 115200
    
    # Screen mapping (must match ESP32 ScreenMode enum)
    SCREEN_OVERVIEW = 0
    SCREEN_RPM = 1
    SCREEN_TPMS = 2
    SCREEN_ENGINE = 3
    SCREEN_GFORCE = 4
    
    def __init__(self, telemetry_data, port: str = None):
        """
        Args:
            telemetry_data: TelemetryData object to update with received values
            port: Serial port path (default: auto-detect USB then GPIO)
        """
        self.telemetry = telemetry_data
        self.port = port  # Will be auto-detected if None
        
        self.serial_conn = None
        self._running = False
        self._read_thread = None
        
        self.connected = False
        self.last_rx_time = 0
        self.last_tx_time = 0
        
        # Current ESP32 screen (synced from acknowledgements)
        self.esp32_screen = 0
        
        # TPMS data cache (updated from ESP32)
        self.tpms_pressure = [0.0, 0.0, 0.0, 0.0]  # PSI
        self.tpms_temp = [0.0, 0.0, 0.0, 0.0]      # °C
        self.tpms_battery = [0, 0, 0, 0]           # %
    
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
        
    def start(self) -> bool:
        """Initialize and start serial communication"""
        if not SERIAL_AVAILABLE:
            print("Serial library not available")
            return False
        
        # Auto-detect port if not specified
        if not self.port:
            self.port = self._find_serial_port()
        
        if not self.port:
            print("No ESP32 serial port found")
            return False
        
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.BAUD_RATE,
                timeout=0.1,
                write_timeout=0.1
            )
            print(f"ESP32 serial opened on {self.port} at {self.BAUD_RATE} baud")
            
            self._running = True
            self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._read_thread.start()
            
            self.connected = True
            return True
            
        except Exception as e:
            print(f"Failed to open ESP32 serial: {e}")
            return False
    
    def stop(self):
        """Stop serial communication"""
        self._running = False
        
        if self._read_thread:
            self._read_thread.join(timeout=1.0)
        
        if self.serial_conn:
            self.serial_conn.close()
        
        self.connected = False
    
    def _read_loop(self):
        """Read incoming data from ESP32 in background thread"""
        buffer = ""
        
        while self._running and self.serial_conn:
            try:
                if self.serial_conn.in_waiting > 0:
                    data = self.serial_conn.read(self.serial_conn.in_waiting)
                    buffer += data.decode('utf-8', errors='ignore')
                    
                    # Process complete lines
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        if line:
                            self._process_line(line)
                            self.last_rx_time = time.time()
                else:
                    time.sleep(0.01)  # Small sleep to prevent busy-waiting
                    
            except Exception as e:
                print(f"ESP32 serial read error: {e}")
                time.sleep(0.1)
    
    def _process_line(self, line: str):
        """Process a complete line from ESP32"""
        try:
            if line.startswith("TPMS:"):
                self._parse_tpms(line[5:])
            elif line.startswith("IMU:"):
                self._parse_imu(line[4:])
            elif line.startswith("OK:SCREEN_"):
                # Screen change acknowledgement
                try:
                    self.esp32_screen = int(line[10:])
                except ValueError:
                    pass
            elif line.startswith("OK:"):
                # Other acknowledgements (SCREEN_NEXT, SCREEN_PREV, etc.)
                pass
            elif line.startswith("Touch I2C"):
                # Ignore touch debug messages
                pass
            else:
                # Log unknown messages for debugging
                print(f"ESP32: {line}")
        except Exception as e:
            print(f"Error parsing ESP32 data '{line}': {e}")
    
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
    
    def _parse_imu(self, data: str):
        """Parse IMU data: lateral_g,longitudinal_g"""
        parts = data.split(',')
        if len(parts) >= 2:
            lateral = float(parts[0])
            longitudinal = float(parts[1])
            
            # Update telemetry object
            self.telemetry.g_lateral = lateral
            self.telemetry.g_longitudinal = longitudinal
    
    def send_telemetry(self):
        """Send current telemetry data to ESP32"""
        if not self.serial_conn or not self._running:
            return
        
        try:
            # Format: TEL:rpm,speed,gear,throttle,coolant,oil,voltage
            msg = f"TEL:{self.telemetry.rpm},{self.telemetry.speed_kmh},{self.telemetry.gear},"
            msg += f"{self.telemetry.throttle_percent},{self.telemetry.coolant_temp_f},"
            msg += f"{self.telemetry.oil_temp_f},{self.telemetry.voltage:.1f}\n"
            
            self.serial_conn.write(msg.encode('utf-8'))
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
        Send screen change command to ESP32 display.
        
        Args:
            screen_index: Screen number (0-4)
                0 = Overview
                1 = RPM/Speed
                2 = TPMS
                3 = Engine
                4 = G-Force
        """
        if not self.serial_conn or not self._running:
            return
        
        try:
            # Clamp to valid range (ESP32 has 5 screens)
            screen_index = max(0, min(4, screen_index))
            msg = f"SCREEN:{screen_index}\n"
            self.serial_conn.write(msg.encode('utf-8'))
            self.last_tx_time = time.time()
            print(f"ESP32: Sent screen change to {screen_index}")
            
        except Exception as e:
            print(f"ESP32 serial write error: {e}")
    
    def send_next_screen(self):
        """Send next screen command to ESP32"""
        if not self.serial_conn or not self._running:
            return
        
        try:
            self.serial_conn.write(b"LEFT\n")
            self.last_tx_time = time.time()
        except Exception as e:
            print(f"ESP32 serial write error: {e}")
    
    def send_prev_screen(self):
        """Send previous screen command to ESP32"""
        if not self.serial_conn or not self._running:
            return
        
        try:
            self.serial_conn.write(b"RIGHT\n")
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
