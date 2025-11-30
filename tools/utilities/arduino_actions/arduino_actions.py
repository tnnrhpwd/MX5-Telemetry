"""
MX5-Telemetry Arduino Actions - USB Command Interface
======================================================
Interactive GUI for controlling Arduino telemetry system via USB-C.

Features:
- Auto-detect Arduino on USB ports
- Send commands (START, STOP, etc.)
- Dump log files from SD card to computer
- Real-time system status monitoring
- Log file browser and management

Commands (single-letter for reliability):
- S       : START - Begin logging and LED display
- X       : STOP - Stop logging
- D       : DUMP - Transfer log files to laptop
- I       : LIST - List all files on SD card
- T       : STATUS - Full diagnostics

Hardware Requirements:
- Arduino Nano V3.0 with MX5-Telemetry firmware
- USB-C connection to computer

This tool provides an easy interface for controlling the telemetry system
without needing to use terminal commands.
"""

import tkinter as tk
from tkinter import messagebox, filedialog, ttk, scrolledtext
import serial
import serial.tools.list_ports
import threading
import time
import os
from datetime import datetime

# ============================================================================
# Serial Communication Manager
# ============================================================================

class ArduinoConnection:
    """Manages serial communication with Arduino."""
    
    def __init__(self):
        self.serial_port = None
        self.port_name = None
        self.is_connected = False
        self.read_thread = None
        self.running = False
        self.callbacks = {
            'on_data': None,
            'on_status': None,
            'on_connect': None,
            'on_disconnect': None
        }
    
    def find_arduino_ports(self):
        """Find all available serial ports that might be Arduino."""
        ports = []
        for port in serial.tools.list_ports.comports():
            # Look for common Arduino identifiers
            if 'Arduino' in port.description or 'CH340' in port.description or 'USB Serial' in port.description:
                # Identify if it's Master or Slave
                arduino_type = self._identify_arduino(port.device)
                desc = f"{port.description} [{arduino_type}]"
                ports.append({'port': port.device, 'desc': desc, 'type': arduino_type})
            # Also include all USB serial devices
            elif 'USB' in port.description or 'COM' in port.device:
                arduino_type = self._identify_arduino(port.device)
                desc = f"{port.description} [{arduino_type}]"
                ports.append({'port': port.device, 'desc': desc, 'type': arduino_type})
        return ports
    
    def _identify_arduino(self, port_name):
        """Identify if Arduino is Master or Slave by actively probing."""
        try:
            # Open with short timeout to avoid freezing
            test_serial = serial.Serial(port=port_name, baudrate=115200, timeout=0.5,
                                       rtscts=False, dsrdtr=False, xonxoff=False,
                                       write_timeout=0.5)
            
            # Flush buffers
            test_serial.reset_input_buffer()
            test_serial.reset_output_buffer()
            time.sleep(0.1)
            
            # Try multiple detection methods
            data = ""
            
            # Method 1: Send 'T' for status (master responds with "St:")
            test_serial.write(b"T\n")
            test_serial.flush()
            time.sleep(0.3)
            
            if test_serial.in_waiting > 0:
                data += test_serial.read(test_serial.in_waiting).decode('utf-8', errors='ignore')
            
            # Method 2: Just listen briefly
            if len(data.strip()) == 0:
                time.sleep(0.3)
                if test_serial.in_waiting > 0:
                    data += test_serial.read(test_serial.in_waiting).decode('utf-8', errors='ignore')
            
            # Close and wait for port to free up
            test_serial.close()
            time.sleep(0.1)
            
            # Determine type based on response
            result = 'UNKNOWN'
            
            # Master responds with: help text "S P X...", status "St:", or data "RPM:,SPD:"
            if any(keyword in data for keyword in ['S P X', 'St:', 'CAN:', 'GPS:', 'SD:', 'RPM:', 'SPD:', 'MX5v3']):
                result = 'MASTER'
                self._log_identification(port_name, result, f"Got: {data[:60].strip()}")
            # Slave sends debug messages like "LED Slave", "LED Pin:", "Serial RX Pin:"
            elif any(keyword in data for keyword in ['LED Slave', 'LED Pin:', 'Serial RX Pin:']):
                result = 'SLAVE'
                self._log_identification(port_name, result, f"Got: {data[:60].strip()}")
            # Slave might also be silent at 115200 baud (uses 9600 baud SoftwareSerial on D2)
            elif len(data.strip()) == 0:
                result = 'SLAVE'
                self._log_identification(port_name, result, "Silent at 115200 (SoftwareSerial@9600)")
            else:
                result = 'UNKNOWN'
                self._log_identification(port_name, result, f"Unexpected: {data[:60].strip()}")
            
            return result
        except Exception as e:
            self._log_identification(port_name, 'ERROR', str(e))
            return 'UNKNOWN'
    
    def _log_identification(self, port, result, details):
        """Log identification results to console (called from background thread)."""
        # Store for later display in UI thread
        if not hasattr(self, '_id_logs'):
            self._id_logs = []
        self._id_logs.append(f"🔍 {port}: {result} - {details}")
    
    def connect(self, port_name, baud_rate=115200):
        """Connect to Arduino on specified port."""
        try:
            self.serial_port = serial.Serial(
                port=port_name,
                baudrate=baud_rate,
                timeout=1,
                write_timeout=1,
                inter_byte_timeout=0.1,
                # Disable flow control
                rtscts=False,
                dsrdtr=False,
                xonxoff=False
            )
            # Force buffers to minimum for low latency
            self.serial_port.set_buffer_size(rx_size=4096, tx_size=4096)
            # Clear any stale data
            self.serial_port.reset_input_buffer()
            self.serial_port.reset_output_buffer()
            
            time.sleep(2)
            self.port_name = port_name
            self.is_connected = True
            self.running = True
            
            # Start read thread
            self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self.read_thread.start()
            
            if self.callbacks['on_connect']:
                self.callbacks['on_connect']()
            
            return True
        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed to connect to {port_name}:\n{str(e)}")
            return False
    
    def disconnect(self):
        """Disconnect from Arduino."""
        self.running = False
        if self.read_thread:
            self.read_thread.join(timeout=2)
        
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        
        self.is_connected = False
        self.port_name = None
        
        if self.callbacks['on_disconnect']:
            self.callbacks['on_disconnect']()
    
    def send_command(self, command):
        """Send command to Arduino."""
        if not self.is_connected or not self.serial_port:
            return False
        
        try:
            # Clear any pending input before sending command
            if self.serial_port.in_waiting > 0:
                self.serial_port.reset_input_buffer()
            
            # Send command with newline
            self.serial_port.write(f"{command}\n".encode())
            self.serial_port.flush()
            
            # Small delay to prevent command flooding
            time.sleep(0.1)
            return True
        except Exception as e:
            print(f"Error sending command: {e}")
            return False
    
    def _read_loop(self):
        """Background thread for reading serial data."""
        buffer = ""
        # Skip boot messages (but allow DEBUG messages through)
        skip_patterns = ['MX5v3', 'Entering Configuration', 'Setting Baudrate']
        while self.running and self.is_connected:
            try:
                if self.serial_port and self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(self.serial_port.in_waiting).decode('utf-8', errors='ignore')
                    buffer += data
                    
                    # Process complete lines
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        
                        if line:
                            # Skip boot/debug messages
                            skip = any(pattern in line for pattern in skip_patterns)
                            if skip:
                                continue
                            
                            # Parse status messages
                            if line.startswith('St:'):
                                if self.callbacks['on_status']:
                                    self.callbacks['on_status'](line)
                            # Regular data
                            elif self.callbacks['on_data']:
                                self.callbacks['on_data'](line)
                
                time.sleep(0.01)  # Small delay to prevent CPU spinning
            except Exception as e:
                print(f"Read error: {e}")
                if not self.serial_port or not self.serial_port.is_open:
                    self.disconnect()
                    break
    
    def set_callback(self, event, callback):
        """Set callback for events."""
        if event in self.callbacks:
            self.callbacks[event] = callback

# ============================================================================
# Main Application Class
# ============================================================================

class ArduinoActionsApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MX5-Telemetry Arduino Actions - USB Command Interface")
        self.root.geometry("1400x850")
        self.root.configure(bg='#1a1a1a')
        self.root.resizable(True, True)
        self.root.minsize(800, 600)
        
        # Two Arduino connections for dual monitor
        self.master_arduino = ArduinoConnection()
        self.slave_arduino = ArduinoConnection()
        
        # Set up callbacks for both
        self.master_arduino.set_callback('on_data', self.on_master_data_received)
        self.master_arduino.set_callback('on_status', self.on_status_received)
        self.master_arduino.set_callback('on_connect', self.on_master_connected)
        self.master_arduino.set_callback('on_disconnect', self.on_master_disconnected)
        
        self.slave_arduino.set_callback('on_data', self.on_slave_data_received)
        self.slave_arduino.set_callback('on_connect', self.on_slave_connected)
        self.slave_arduino.set_callback('on_disconnect', self.on_slave_disconnected)
        
        # Legacy alias for compatibility
        self.arduino = self.master_arduino
        
        # State
        self.current_state = "IDLE"
        self.dump_mode = False
        self.dump_buffer = []
        self.dump_save_path = None
        self.dump_timeout = None
        self.dump_file_size = 0  # Expected file size from Arduino
        self.dump_bytes_received = 0  # Bytes received so far
        self.dump_filename = None  # Name of file being dumped
        self.dump_ignore_first_ok = False  # Flag to ignore OK from stop command before dump
        self.log_files = []
        self.last_command_time = 0
        self.command_cooldown = 0.5  # 500ms between commands
        
        # Command tracking for timeout detection
        self.pending_command = None
        self.pending_command_time = None
        self.command_timeout = 15.0  # 15 seconds (extended for slower operations)
        self.last_data_time = time.time()
        self.error_count = 0
        self.consecutive_timeouts = 0
        
        # Byte counters for stats
        self.master_bytes = 0
        self.slave_bytes = 0
        
        # Create UI
        self.create_ui()
        
        # Cleanup on close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Auto-refresh port list periodically
        self.refresh_ports_periodically()
        
        # Start watchdog for command timeouts
        self.check_command_timeout()
    
    def create_ui(self):
        """Create the user interface with scrollable content and dual consoles."""
        
        # Create main scrollable canvas for small screens
        self.canvas = tk.Canvas(self.root, bg='#1a1a1a', highlightthickness=0)
        self.scrollbar_y = tk.Scrollbar(self.root, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg='#1a1a1a')
        
        self.canvas_frame = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar_y.set)
        
        # Bind canvas resize to stretch content
        self.canvas.bind('<Configure>', self._on_canvas_configure)
        
        # Bind scrollable frame configure to update scroll region
        self.scrollable_frame.bind("<Configure>", self._on_frame_configure)
        
        # Enable mousewheel scrolling
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
        self.scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Title
        title = tk.Label(self.scrollable_frame, text="Arduino Actions - Dual Monitor", 
                        font=("Segoe UI", 16, "bold"), fg="#ffffff", bg="#1a1a1a")
        title.pack(pady=6)
        
        # =================================================================
        # CONNECTION SECTION - Both Arduinos
        # =================================================================
        conn_frame = tk.Frame(self.scrollable_frame, bg="#2a2a2a", relief=tk.FLAT, bd=0)
        conn_frame.pack(pady=4, padx=12, fill=tk.X)
        
        tk.Label(conn_frame, text="CONNECTIONS", font=("Segoe UI", 10, "bold"), 
                fg="#ffffff", bg="#2a2a2a").pack(pady=3)
        
        # Two-column port layout
        ports_frame = tk.Frame(conn_frame, bg="#2a2a2a")
        ports_frame.pack(pady=3, fill=tk.X)
        
        # Style for combobox
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TCombobox', fieldbackground='#3a3a3a', background='#3a3a3a', 
                       foreground="#2600ff", borderwidth=0)
        
        # Master port (left)
        master_port_frame = tk.Frame(ports_frame, bg="#2a2a2a")
        master_port_frame.pack(side=tk.LEFT, padx=15, expand=True, fill=tk.X)
        
        tk.Label(master_port_frame, text="📡 MASTER:", font=("Segoe UI", 9, "bold"), 
                fg="#00aaff", bg="#2a2a2a").pack(side=tk.LEFT, padx=3)
        
        self.master_port_combo = ttk.Combobox(master_port_frame, width=32, state='readonly', style='TCombobox')
        self.master_port_combo.pack(side=tk.LEFT, padx=3)
        
        self.master_connect_btn = tk.Button(master_port_frame, text="Connect", 
                                           command=self.toggle_master_connection,
                                           bg="#00aa00", fg="#ffffff", font=("Segoe UI", 8, "bold"),
                                           relief=tk.FLAT, bd=0, padx=8, pady=2,
                                           cursor="hand2")
        self.master_connect_btn.pack(side=tk.LEFT, padx=3)
        
        self.master_status_label = tk.Label(master_port_frame, text="⚫", 
                                            font=("Segoe UI", 10), fg="#888888", bg="#2a2a2a")
        self.master_status_label.pack(side=tk.LEFT, padx=3)
        
        # Slave port (right)
        slave_port_frame = tk.Frame(ports_frame, bg="#2a2a2a")
        slave_port_frame.pack(side=tk.LEFT, padx=15, expand=True, fill=tk.X)
        
        tk.Label(slave_port_frame, text="💡 SLAVE:", font=("Segoe UI", 9, "bold"), 
                fg="#ff8800", bg="#2a2a2a").pack(side=tk.LEFT, padx=3)
        
        self.slave_port_combo = ttk.Combobox(slave_port_frame, width=32, state='readonly', style='TCombobox')
        self.slave_port_combo.pack(side=tk.LEFT, padx=3)
        
        self.slave_connect_btn = tk.Button(slave_port_frame, text="Connect", 
                                          command=self.toggle_slave_connection,
                                          bg="#00aa00", fg="#ffffff", font=("Segoe UI", 8, "bold"),
                                          relief=tk.FLAT, bd=0, padx=8, pady=2,
                                          cursor="hand2")
        self.slave_connect_btn.pack(side=tk.LEFT, padx=3)
        
        self.slave_status_label = tk.Label(slave_port_frame, text="⚫", 
                                           font=("Segoe UI", 10), fg="#888888", bg="#2a2a2a")
        self.slave_status_label.pack(side=tk.LEFT, padx=3)
        
        # Quick buttons row
        quick_frame = tk.Frame(conn_frame, bg="#2a2a2a")
        quick_frame.pack(pady=4)
        
        self.refresh_btn = tk.Button(quick_frame, text="🔄 Refresh", 
                                     command=self.refresh_ports,
                                     bg="#3a3a3a", fg="#ffffff", font=("Segoe UI", 8),
                                     relief=tk.FLAT, bd=0, padx=10, pady=3,
                                     cursor="hand2")
        self.refresh_btn.pack(side=tk.LEFT, padx=4)
        
        self.auto_connect_btn = tk.Button(quick_frame, text="⚡ Connect Both", 
                                          command=self.toggle_both_connections,
                                          bg="#00aa00", fg="#ffffff", font=("Segoe UI", 8, "bold"),
                                          relief=tk.FLAT, bd=0, padx=10, pady=3,
                                          cursor="hand2")
        self.auto_connect_btn.pack(side=tk.LEFT, padx=4)
        
        # =================================================================
        # COMMANDS + SD CARD (compact row)
        # =================================================================
        cmd_sd_frame = tk.Frame(self.scrollable_frame, bg="#2a2a2a", relief=tk.FLAT, bd=0)
        cmd_sd_frame.pack(pady=4, padx=12, fill=tk.X)
        
        # Commands (left side)
        cmd_section = tk.Frame(cmd_sd_frame, bg="#2a2a2a")
        cmd_section.pack(side=tk.LEFT, padx=10)
        
        tk.Label(cmd_section, text="COMMANDS", font=("Segoe UI", 9, "bold"), 
                fg="#ffffff", bg="#2a2a2a").pack(pady=2)
        
        btn_row = tk.Frame(cmd_section, bg="#2a2a2a")
        btn_row.pack(pady=2)
        
        self.start_btn = tk.Button(btn_row, text="▶ START", 
                                   command=lambda: self.send_command("S"),
                                   bg="#00aa00", fg="#ffffff", font=("Segoe UI", 9, "bold"),
                                   relief=tk.FLAT, bd=0, padx=12, pady=4,
                                   cursor="hand2", state=tk.DISABLED)
        self.start_btn.pack(side=tk.LEFT, padx=3)
        
        self.stop_btn = tk.Button(btn_row, text="⏹ STOP", 
                                  command=lambda: self.send_command("X"),
                                  bg="#cc0000", fg="#ffffff", font=("Segoe UI", 9, "bold"),
                                  relief=tk.FLAT, bd=0, padx=12, pady=4,
                                  cursor="hand2", state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=3)
        
        self.status_btn = tk.Button(btn_row, text="📊 STATUS", 
                                    command=self.request_status,
                                    bg="#555555", fg="#ffffff", font=("Segoe UI", 9, "bold"),
                                    relief=tk.FLAT, bd=0, padx=12, pady=4,
                                    cursor="hand2", state=tk.DISABLED)
        self.status_btn.pack(side=tk.LEFT, padx=3)
        
        # SD Card files (right side - expandable)
        sd_section = tk.Frame(cmd_sd_frame, bg="#2a2a2a")
        sd_section.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        
        sd_header = tk.Frame(sd_section, bg="#2a2a2a")
        sd_header.pack(fill=tk.X, pady=2)
        
        tk.Label(sd_header, text="SD CARD", font=("Segoe UI", 9, "bold"), 
                fg="#ffffff", bg="#2a2a2a").pack(side=tk.LEFT)
        
        self.list_btn = tk.Button(sd_header, text="🔄 Refresh", 
                                 command=self.list_files,
                                 bg="#3a3a3a", fg="#ffffff", font=("Segoe UI", 8),
                                 relief=tk.FLAT, bd=0, padx=8, pady=2,
                                 cursor="hand2", state=tk.DISABLED)
        self.list_btn.pack(side=tk.LEFT, padx=8)
        
        self.dump_selected_btn = tk.Button(sd_header, text="💾 Download", 
                                          command=self.dump_selected_file,
                                          bg="#00aa00", fg="#ffffff", font=("Segoe UI", 8),
                                          relief=tk.FLAT, bd=0, padx=8, pady=2,
                                          cursor="hand2", state=tk.DISABLED)
        self.dump_selected_btn.pack(side=tk.LEFT, padx=3)
        
        # Compact file listbox
        listbox_frame = tk.Frame(sd_section, bg="#0d0d0d")
        listbox_frame.pack(fill=tk.X, pady=2)
        
        scrollbar = tk.Scrollbar(listbox_frame, orient=tk.VERTICAL, bg="#3a3a3a")
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.file_listbox = tk.Listbox(listbox_frame, height=3, bg="#0d0d0d", fg="#00ff88",
                                       font=("Consolas", 9), selectmode=tk.SINGLE,
                                       relief=tk.FLAT, bd=0, highlightthickness=1,
                                       highlightbackground="#333333",
                                       selectbackground="#0066cc", selectforeground="#ffffff",
                                       yscrollcommand=scrollbar.set)
        self.file_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        scrollbar.config(command=self.file_listbox.yview)
        
        # =================================================================
        # LED TEST SECTION - RPM slider for LED debugging
        # =================================================================
        led_test_frame = tk.Frame(self.scrollable_frame, bg="#2a2a2a", relief=tk.FLAT, bd=0)
        led_test_frame.pack(pady=4, padx=12, fill=tk.X)
        
        tk.Label(led_test_frame, text="💡 LED TEST", font=("Segoe UI", 9, "bold"), 
                fg="#ff8800", bg="#2a2a2a").pack(side=tk.LEFT, padx=5)
        
        # RPM Slider
        self.rpm_slider_value = tk.IntVar(value=0)
        self.rpm_label = tk.Label(led_test_frame, text="RPM: 0", 
                                  font=("Segoe UI", 9, "bold"), fg="#00ff00", bg="#2a2a2a",
                                  width=10)
        self.rpm_label.pack(side=tk.LEFT, padx=5)
        
        self.rpm_slider = tk.Scale(led_test_frame, from_=0, to=8000, orient=tk.HORIZONTAL,
                                   variable=self.rpm_slider_value,
                                   command=self.on_rpm_slider_change,
                                   bg="#3a3a3a", fg="#ffffff", font=("Segoe UI", 7),
                                   troughcolor="#1a1a1a", activebackground="#ff8800",
                                   highlightthickness=0, bd=0, sliderlength=20,
                                   length=200, showvalue=False, resolution=100)
        self.rpm_slider.pack(side=tk.LEFT, padx=5)
        
        # Quick RPM preset buttons
        preset_frame = tk.Frame(led_test_frame, bg="#2a2a2a")
        preset_frame.pack(side=tk.LEFT, padx=5)
        
        rpm_presets = [
            ("0", 0, "#333333"),
            ("3K", 3000, "#006600"),
            ("5K", 5000, "#888800"),
            ("6K", 6000, "#cc4400"),
            ("7K", 7000, "#ff0000"),
            ("8K", 8000, "#ff00ff"),
        ]
        
        for label, rpm, color in rpm_presets:
            btn = tk.Button(preset_frame, text=label, 
                           command=lambda r=rpm: self.set_rpm_slider(r),
                           bg=color, fg="#ffffff", font=("Segoe UI", 7, "bold"),
                           relief=tk.FLAT, bd=0, padx=4, pady=1,
                           cursor="hand2")
            btn.pack(side=tk.LEFT, padx=1)
        
        # Separator
        tk.Label(led_test_frame, text="|", fg="#444444", bg="#2a2a2a").pack(side=tk.LEFT, padx=4)
        
        # Special commands
        special_tests = [
            ("CLR", "CLR", "#333333"),
            ("SPD:60", "SPD:60", "#0066aa"),
            ("SPD:120", "SPD:120", "#0088cc"),
        ]
        
        for label, cmd, color in special_tests:
            btn = tk.Button(led_test_frame, text=label, 
                           command=lambda c=cmd: self.send_led_test(c),
                           bg=color, fg="#ffffff", font=("Segoe UI", 8, "bold"),
                           relief=tk.FLAT, bd=0, padx=6, pady=2,
                           cursor="hand2")
            btn.pack(side=tk.LEFT, padx=2)
        
        # =================================================================
        # RESIZABLE PANED WINDOW - SD Card + Console with drag handles
        # =================================================================
        
        # Main vertical paned window for resizable sections
        self.main_paned = tk.PanedWindow(self.scrollable_frame, orient=tk.VERTICAL,
                                         bg="#444444", sashwidth=6, sashrelief=tk.RAISED,
                                         sashpad=2, showhandle=True, handlesize=10,
                                         handlepad=100)
        self.main_paned.pack(pady=4, padx=12, fill=tk.BOTH, expand=True)
        
        # =================================================================
        # SD CARD PANE (resizable)
        # =================================================================
        sd_pane = tk.Frame(self.main_paned, bg="#2a2a2a")
        
        sd_pane_header = tk.Frame(sd_pane, bg="#2a2a2a")
        sd_pane_header.pack(fill=tk.X, pady=2)
        
        tk.Label(sd_pane_header, text="📁 SD CARD FILES", font=("Segoe UI", 9, "bold"), 
                fg="#ffffff", bg="#2a2a2a").pack(side=tk.LEFT, padx=5)
        
        # Drag hint
        tk.Label(sd_pane_header, text="⋮⋮ drag to resize ⋮⋮", font=("Segoe UI", 7), 
                fg="#666666", bg="#2a2a2a").pack(side=tk.RIGHT, padx=5)
        
        # SD file listbox (expandable)
        sd_listbox_frame = tk.Frame(sd_pane, bg="#0d0d0d")
        sd_listbox_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        
        sd_scrollbar = tk.Scrollbar(sd_listbox_frame, orient=tk.VERTICAL, bg="#3a3a3a")
        sd_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.sd_file_listbox = tk.Listbox(sd_listbox_frame, bg="#0d0d0d", fg="#00ff88",
                                          font=("Consolas", 10), selectmode=tk.SINGLE,
                                          relief=tk.FLAT, bd=0, highlightthickness=1,
                                          highlightbackground="#333333",
                                          selectbackground="#0066cc", selectforeground="#ffffff",
                                          yscrollcommand=sd_scrollbar.set)
        self.sd_file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sd_scrollbar.config(command=self.sd_file_listbox.yview)
        
        # Link to main file_listbox for compatibility
        self.file_listbox = self.sd_file_listbox
        
        self.main_paned.add(sd_pane, minsize=60, height=100)
        
        # =================================================================
        # DUAL CONSOLE PANE (resizable) - Side by side Master & Slave
        # =================================================================
        console_pane = tk.Frame(self.main_paned, bg="#1a1a1a")
        
        console_header = tk.Frame(console_pane, bg="#1a1a1a")
        console_header.pack(fill=tk.X, pady=2)
        
        tk.Label(console_header, text="CONSOLE OUTPUT", font=("Segoe UI", 10, "bold"), 
                fg="#ffffff", bg="#1a1a1a").pack(side=tk.LEFT, padx=5)
        
        # Horizontal paned window for Master/Slave consoles
        self.console_paned = tk.PanedWindow(console_pane, orient=tk.HORIZONTAL,
                                            bg="#444444", sashwidth=6, sashrelief=tk.RAISED,
                                            sashpad=2, showhandle=True, handlesize=10,
                                            handlepad=80)
        self.console_paned.pack(fill=tk.BOTH, expand=True, pady=2)
        
        # Master console (left pane)
        master_console_frame = tk.Frame(self.console_paned, bg="#2a2a2a", relief=tk.FLAT)
        
        master_header = tk.Frame(master_console_frame, bg="#2a2a2a")
        master_header.pack(fill=tk.X, pady=2)
        
        tk.Label(master_header, text="📡 MASTER (Logger)", font=("Segoe UI", 9, "bold"), 
                fg="#00aaff", bg="#2a2a2a").pack(side=tk.LEFT, padx=5)
        
        tk.Label(master_header, text="⋮ drag ⋮", font=("Segoe UI", 7), 
                fg="#666666", bg="#2a2a2a").pack(side=tk.RIGHT, padx=2)
        
        clear_master_btn = tk.Button(master_header, text="🗑", 
                                     command=self.clear_master_console,
                                     bg="#3a3a3a", fg="#ffffff", font=("Segoe UI", 8),
                                     relief=tk.FLAT, bd=0, padx=4, pady=1,
                                     cursor="hand2")
        clear_master_btn.pack(side=tk.RIGHT, padx=5)
        
        self.master_console = scrolledtext.ScrolledText(master_console_frame,
                                                        bg="#0a0a0a", fg="#00ff88",
                                                        font=("Consolas", 9), wrap=tk.WORD,
                                                        state=tk.DISABLED, relief=tk.FLAT,
                                                        highlightthickness=1, 
                                                        highlightbackground="#00aaff")
        self.master_console.pack(pady=2, padx=4, fill=tk.BOTH, expand=True)
        
        # Configure tags for master console
        self.master_console.tag_configure("send", foreground="#ffaa00")
        self.master_console.tag_configure("led", foreground="#ff00ff")
        self.master_console.tag_configure("error", foreground="#ff4444")
        self.master_console.tag_configure("info", foreground="#888888")
        self.master_console.tag_configure("status", foreground="#00ffff")
        
        self.console_paned.add(master_console_frame, minsize=200)
        
        # Slave console (right pane)
        slave_console_frame = tk.Frame(self.console_paned, bg="#2a2a2a", relief=tk.FLAT)
        
        slave_header = tk.Frame(slave_console_frame, bg="#2a2a2a")
        slave_header.pack(fill=tk.X, pady=2)
        
        tk.Label(slave_header, text="💡 SLAVE (LED Controller)", font=("Segoe UI", 9, "bold"), 
                fg="#ff8800", bg="#2a2a2a").pack(side=tk.LEFT, padx=5)
        
        clear_slave_btn = tk.Button(slave_header, text="🗑", 
                                    command=self.clear_slave_console,
                                    bg="#3a3a3a", fg="#ffffff", font=("Segoe UI", 8),
                                    relief=tk.FLAT, bd=0, padx=4, pady=1,
                                    cursor="hand2")
        clear_slave_btn.pack(side=tk.RIGHT, padx=5)
        
        self.slave_console = scrolledtext.ScrolledText(slave_console_frame,
                                                       bg="#0a0a0a", fg="#ffff00",
                                                       font=("Consolas", 9), wrap=tk.WORD,
                                                       state=tk.DISABLED, relief=tk.FLAT,
                                                       highlightthickness=1, 
                                                       highlightbackground="#ff8800")
        self.slave_console.pack(pady=2, padx=4, fill=tk.BOTH, expand=True)
        
        # Configure tags for slave console
        self.slave_console.tag_configure("rx", foreground="#00ffff")
        self.slave_console.tag_configure("cmd", foreground="#00ff00")
        self.slave_console.tag_configure("error", foreground="#ff4444")
        self.slave_console.tag_configure("status", foreground="#888888")
        
        self.console_paned.add(slave_console_frame, minsize=200)
        
        # Add console pane to main paned window
        self.main_paned.add(console_pane, minsize=150)
        
        # Legacy console reference (for compatibility)
        self.console = self.master_console
        
        # =================================================================
        # STATUS BAR
        # =================================================================
        status_bar = tk.Frame(self.scrollable_frame, bg="#2a2a2a")
        status_bar.pack(pady=4, padx=12, fill=tk.X)
        
        self.state_label = tk.Label(status_bar, text="System: IDLE", 
                                   font=("Segoe UI", 9, "bold"), fg="#ffffff", bg="#2a2a2a")
        self.state_label.pack(side=tk.LEFT, padx=8)
        
        self.stats_label = tk.Label(status_bar, text="Bytes: M=0 | S=0", 
                                   font=("Consolas", 8), fg="#888888", bg="#2a2a2a")
        self.stats_label.pack(side=tk.LEFT, padx=15)
        
        diag_btn = tk.Button(status_bar, text="🔍 Diagnostics", 
                           command=self.show_diagnostics,
                           bg="#3a3a3a", fg="#ffffff", font=("Segoe UI", 8),
                           relief=tk.FLAT, bd=0, padx=8, pady=2,
                           cursor="hand2")
        diag_btn.pack(side=tk.RIGHT, padx=4)
        
        clear_all_btn = tk.Button(status_bar, text="🗑 Clear All", 
                                 command=self.clear_all_consoles,
                                 bg="#3a3a3a", fg="#ffffff", font=("Segoe UI", 8),
                                 relief=tk.FLAT, bd=0, padx=8, pady=2,
                                 cursor="hand2")
        clear_all_btn.pack(side=tk.RIGHT, padx=4)
        
        # Initial port refresh
        self.refresh_ports()
    
    def _on_canvas_configure(self, event):
        """Resize the scrollable frame to match canvas size for proper pane expansion."""
        self.canvas.itemconfig(self.canvas_frame, width=event.width)
        # Also update height so PanedWindow can expand to fill available space
        # Get the natural height of all content above and below the paned window
        self.scrollable_frame.update_idletasks()
        content_height = self.scrollable_frame.winfo_reqheight()
        # Use the larger of content height or canvas height
        new_height = max(content_height, event.height)
        self.canvas.itemconfig(self.canvas_frame, height=new_height)
    
    def _on_frame_configure(self, event):
        """Update scroll region when frame content changes."""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    
    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling."""
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    
    def refresh_ports(self):
        """Refresh available serial ports for both Master and Slave."""
        self.log_master_console("🔄 Scanning for Arduinos...\n", "info")
        ports = self.master_arduino.find_arduino_ports()
        
        # Display identification logs
        if hasattr(self.master_arduino, '_id_logs'):
            for log in self.master_arduino._id_logs:
                self.log_master_console(log + "\n", "info")
            self.master_arduino._id_logs = []
        
        port_list = [f"{p['port']} - {p['desc']}" for p in ports]
        
        # Populate both dropdowns
        self.master_port_combo['values'] = port_list
        self.slave_port_combo['values'] = port_list
        
        if port_list:
            # Try to auto-select based on detected type
            master_idx = 0
            slave_idx = 0
            for i, p in enumerate(ports):
                if p['type'] == 'MASTER':
                    master_idx = i
                elif p['type'] == 'SLAVE' or p['type'] == 'UNKNOWN':
                    slave_idx = i
            
            if len(port_list) > 0:
                self.master_port_combo.current(master_idx)
            if len(port_list) > 1:
                # Make sure slave is different from master
                if slave_idx == master_idx:
                    slave_idx = 1 if master_idx == 0 else 0
                self.slave_port_combo.current(slave_idx)
            elif len(port_list) == 1:
                self.slave_port_combo.current(0)
            
            self.log_master_console(f"✓ Found {len(port_list)} port(s)\n", "info")
            for p in ports:
                self.log_master_console(f"  {p['port']}: {p['type']}\n", "info")
        else:
            self.log_master_console("⚠️ No Arduino ports detected\n", "error")
    
    def refresh_ports_periodically(self):
        """Auto-refresh ports - disabled to prevent spam."""
        pass
    
    def toggle_master_connection(self):
        """Toggle Master Arduino connection."""
        if self.master_arduino.is_connected:
            self.master_arduino.disconnect()
        else:
            selected = self.master_port_combo.get()
            if selected:
                port_name = selected.split(' - ')[0]
                
                # Check if this port is already in use by Slave
                if self.slave_arduino.is_connected:
                    slave_port = self.slave_port_combo.get().split(' - ')[0]
                    if port_name == slave_port:
                        self.log_master_console(f"⚠️ Port {port_name} already in use by Slave!\n", "error")
                        self.log_master_console("Please select a different port for Master.\n", "error")
                        return
                
                self.log_master_console(f"Connecting to {port_name}...\n", "info")
                if self.master_arduino.connect(port_name):
                    self.log_master_console(f"✓ Connected to {port_name}\n", "info")
    
    def toggle_slave_connection(self):
        """Toggle Slave Arduino connection."""
        if self.slave_arduino.is_connected:
            self.slave_arduino.disconnect()
        else:
            selected = self.slave_port_combo.get()
            if selected:
                port_name = selected.split(' - ')[0]
                
                # Check if this port is already in use by Master
                if self.master_arduino.is_connected:
                    master_port = self.master_port_combo.get().split(' - ')[0]
                    if port_name == master_port:
                        self.log_slave_console(f"⚠️ Port {port_name} already in use by Master!\n", "error")
                        self.log_slave_console("Please select a different port for Slave.\n", "error")
                        return
                
                self.log_slave_console(f"Connecting to {port_name}...\n", "info")
                # Slave uses 115200 for USB serial (not the 9600 SoftwareSerial on D2)
                if self.slave_arduino.connect(port_name, baud_rate=115200):
                    self.log_slave_console(f"✓ Connected to {port_name}\n", "info")
    
    def toggle_both_connections(self):
        """Connect or disconnect both Arduinos based on current state."""
        both_connected = self.master_arduino.is_connected and self.slave_arduino.is_connected
        
        if both_connected:
            # Disconnect both
            self.log_master_console("\n🔌 Disconnecting both Arduinos...\n", "info")
            if self.master_arduino.is_connected:
                self.master_arduino.disconnect()
            if self.slave_arduino.is_connected:
                self.slave_arduino.disconnect()
        else:
            # Connect both
            self.auto_connect_both()
    
    def auto_connect_both(self):
        """Auto-detect and connect to both Arduinos."""
        self.log_master_console("\n⚡ Connecting both Arduinos...\n", "info")
        
        # Refresh ports first
        ports = self.master_arduino.find_arduino_ports()
        
        if len(ports) < 2:
            self.log_master_console(f"⚠️ Need 2 ports, found {len(ports)}\n", "error")
            return
        
        # Find master and slave
        master_port = None
        slave_port = None
        
        for p in ports:
            if p['type'] == 'MASTER' and not master_port:
                master_port = p['port']
            elif p['type'] == 'SLAVE' and not slave_port:
                slave_port = p['port']
        
        # Fallback: assign by order if types not detected
        if not master_port:
            master_port = ports[0]['port']
        if not slave_port:
            for p in ports:
                if p['port'] != master_port:
                    slave_port = p['port']
                    break
        
        # Connect master
        if master_port and not self.master_arduino.is_connected:
            self.log_master_console(f"Connecting Master: {master_port}\n", "info")
            self.master_arduino.connect(master_port)
        
        # Connect slave
        if slave_port and not self.slave_arduino.is_connected:
            self.log_slave_console(f"Connecting Slave: {slave_port}\n", "info")
            self.slave_arduino.connect(slave_port)
    
    def on_master_connected(self):
        """Handle successful Master connection."""
        self.master_status_label.config(text="🟢", fg="#00ff00")
        self.master_connect_btn.config(text="Disconnect", bg="#cc0000")
        
        # Enable command buttons
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_btn.config(state=tk.NORMAL)
        self.list_btn.config(state=tk.NORMAL)
        self.dump_selected_btn.config(state=tk.NORMAL)
        
        # Update combined connect button
        self.update_combined_connect_button()
    
    def on_master_disconnected(self):
        """Handle Master disconnection."""
        self.master_status_label.config(text="⚫", fg="#888888")
        self.master_connect_btn.config(text="Connect", bg="#00aa00")
        
        # Disable command buttons
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_btn.config(state=tk.DISABLED)
        self.list_btn.config(state=tk.DISABLED)
        self.dump_selected_btn.config(state=tk.DISABLED)
        
        # Reset tracking
        self.pending_command = None
        self.pending_command_time = None
        self.consecutive_timeouts = 0
        
        self.log_master_console("⚫ Disconnected\n", "info")
        
        # Update combined connect button
        self.update_combined_connect_button()
    
    def on_slave_connected(self):
        """Handle successful Slave connection."""
        self.slave_status_label.config(text="🟢", fg="#00ff00")
        self.slave_connect_btn.config(text="Disconnect", bg="#cc0000")
        
        # Update combined connect button
        self.update_combined_connect_button()
    
    def on_slave_disconnected(self):
        """Handle Slave disconnection."""
        self.slave_status_label.config(text="⚫", fg="#888888")
        self.slave_connect_btn.config(text="Connect", bg="#00aa00")
        self.log_slave_console("⚫ Disconnected\n", "info")
        
        # Update combined connect button
        self.update_combined_connect_button()
    
    def update_combined_connect_button(self):
        """Update the combined connect/disconnect button based on connection state."""
        both_connected = self.master_arduino.is_connected and self.slave_arduino.is_connected
        
        if both_connected:
            # Both connected - show red disconnect button
            self.auto_connect_btn.config(text="🔌 Disconnect Both", bg="#cc0000")
        else:
            # Not both connected - show green connect button
            self.auto_connect_btn.config(text="⚡ Connect Both", bg="#00aa00")
    
    def on_master_data_received(self, data):
        """Handle data from Master Arduino."""
        self.root.after(0, lambda: self._process_master_data(data))
    
    def on_slave_data_received(self, data):
        """Handle data from Slave Arduino."""
        self.root.after(0, lambda: self._process_slave_data(data))
    
    def _process_slave_data(self, data):
        """Process Slave serial data with color coding."""
        self.slave_bytes += len(data) + 1
        self.update_stats()
        
        # Color code based on content
        if data.startswith('RX:'):
            self.log_slave_console(data + "\n", "rx")
        elif 'Processing:' in data or 'CMD:' in data:
            self.log_slave_console(data + "\n", "cmd")
        elif 'error' in data.lower():
            self.log_slave_console(data + "\n", "error")
        else:
            self.log_slave_console(data + "\n")
    
    def log_master_console(self, message, tag=None):
        """Add message to master console."""
        self.master_console.config(state=tk.NORMAL)
        timestamp = datetime.now().strftime("%H:%M:%S")
        if tag:
            self.master_console.insert(tk.END, f"[{timestamp}] {message}", tag)
        else:
            self.master_console.insert(tk.END, f"[{timestamp}] {message}")
        self.master_console.see(tk.END)
        self.master_console.config(state=tk.DISABLED)
        self.master_bytes += len(message)
        self.update_stats()
    
    def log_slave_console(self, message, tag=None):
        """Add message to slave console."""
        self.slave_console.config(state=tk.NORMAL)
        timestamp = datetime.now().strftime("%H:%M:%S")
        if tag:
            self.slave_console.insert(tk.END, f"[{timestamp}] {message}", tag)
        else:
            self.slave_console.insert(tk.END, f"[{timestamp}] {message}")
        self.slave_console.see(tk.END)
        self.slave_console.config(state=tk.DISABLED)
    
    def clear_master_console(self):
        """Clear master console."""
        self.master_console.config(state=tk.NORMAL)
        self.master_console.delete(1.0, tk.END)
        self.master_console.config(state=tk.DISABLED)
        self.master_bytes = 0
        self.update_stats()
    
    def clear_slave_console(self):
        """Clear slave console."""
        self.slave_console.config(state=tk.NORMAL)
        self.slave_console.delete(1.0, tk.END)
        self.slave_console.config(state=tk.DISABLED)
        self.slave_bytes = 0
        self.update_stats()
    
    def clear_all_consoles(self):
        """Clear both consoles."""
        self.clear_master_console()
        self.clear_slave_console()
    
    def update_stats(self):
        """Update the stats label."""
        self.stats_label.config(text=f"Bytes: M={self.master_bytes} | S={self.slave_bytes}")
    
    def _format_file_entry(self, data):
        """Format file entry for display. Input: 'filename|size' or just 'filename'."""
        if '|' in data:
            parts = data.split('|')
            filename = parts[0].strip()
            try:
                size = int(parts[1].strip())
                # Format size in human-readable format
                if size >= 1024 * 1024:
                    size_str = f"{size / (1024 * 1024):.1f} MB"
                elif size >= 1024:
                    size_str = f"{size / 1024:.1f} KB"
                else:
                    size_str = f"{size} B"
                return f"{filename}  ({size_str})"
            except ValueError:
                return filename
        return data.strip()
    
    def _extract_filename(self, display_name):
        """Extract just the filename from display format 'filename  (size)'."""
        if '  (' in display_name:
            return display_name.split('  (')[0].strip()
        return display_name.strip()
    
    def send_command(self, command):
        """Send command to Master Arduino."""
        if self.master_arduino.send_command(command):
            self.log_master_console(f"→ {command}\n", "send")
            # Track pending command for timeout detection
            self.pending_command = command
            self.pending_command_time = time.time()
        else:
            self.log_master_console(f"⚠️ Failed to send: {command}\n", "error")
            self.error_count += 1
    
    def send_led_test(self, led_command):
        """Send LED test command directly to Slave Arduino via USB."""
        # Rate limit to prevent buffer overflow on Arduino
        current_time = time.time()
        if hasattr(self, '_last_led_test_time'):
            elapsed = current_time - self._last_led_test_time
            if elapsed < 0.3:  # Minimum 300ms between LED test commands
                self.log_slave_console(f"⚠️ Too fast! Wait a moment...\n", "error")
                return
        self._last_led_test_time = current_time
        
        # Send directly to Slave (not through Master) to avoid firmware size issues
        if self.slave_arduino.is_connected:
            # For RPM commands, also send a speed > 1 to avoid idle state
            # (LED logic shows idle when speed <= 1, regardless of RPM)
            if led_command.startswith("RPM:"):
                # Send speed first to exit idle state
                self.slave_arduino.send_command("SPD:50")
                self.log_slave_console(f"→ SPD:50 (exit idle)\n", "status")
                time.sleep(0.2)  # Wait for Slave to process before sending RPM
            
            if self.slave_arduino.send_command(led_command):
                self.log_slave_console(f"→ {led_command}\n", "cmd")
            else:
                self.log_slave_console(f"⚠️ Failed to send LED test\n", "error")
        else:
            self.log_slave_console("⚠️ Slave not connected\n", "error")
    
    def on_rpm_slider_change(self, value):
        """Handle RPM slider value change."""
        rpm = int(float(value))
        
        # Update label with color based on RPM
        if rpm < 1000:
            color = "#888888"  # Gray for idle
        elif rpm < 3000:
            color = "#00ff00"  # Green
        elif rpm < 5000:
            color = "#88ff00"  # Yellow-green
        elif rpm < 6000:
            color = "#ffff00"  # Yellow
        elif rpm < 6500:
            color = "#ff8800"  # Orange
        elif rpm < 7000:
            color = "#ff4400"  # Red-orange
        elif rpm < 7500:
            color = "#ff0000"  # Red
        else:
            color = "#ff00ff"  # Magenta for redline
        
        self.rpm_label.config(text=f"RPM: {rpm}", fg=color)
        
        # Send the RPM command to the Slave
        self.send_led_test(f"RPM:{rpm}")
    
    def set_rpm_slider(self, rpm):
        """Set the RPM slider to a specific value."""
        self.rpm_slider.set(rpm)
    
    def list_files(self):
        """List files on SD card."""
        self.file_listbox.delete(0, tk.END)
        self.file_listbox.insert(tk.END, "Requesting file list...")
        self.send_command("I")
    
    def dump_selected_file(self):
        """Dump selected file from list."""
        selection = self.file_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a file to dump")
            return
        
        display_name = self.file_listbox.get(selection[0])
        
        # Skip if it's the placeholder text
        if display_name == "(No files on SD card)" or display_name == "Requesting file list...":
            return
        
        # Extract just the filename (remove size info if present)
        filename = self._extract_filename(display_name)
            
        save_path = filedialog.askdirectory(title="Select folder to save log")
        
        if save_path:
            # First, stop logging if running (Master can't dump while logging)
            self.log_master_console("⏹ Stopping logging before dump...\n", "info")
            self.master_arduino.send_command("X")
            # Wait long enough for OK response to be received and processed
            # This prevents the stop's "OK" from being interpreted as dump completion
            time.sleep(0.8)  # Wait for stop response to flush through
            
            self.dump_buffer = []
            self.dump_mode = True
            self.dump_ignore_first_ok = True  # Flag to ignore OK from stop command
            self.dump_save_path = save_path
            self.dump_file_size = 0
            self.dump_bytes_received = 0
            self.dump_filename = filename
            # Extended timeout: 120 seconds for large files (at 115200 baud, ~10KB/s theoretical)
            self.dump_timeout = time.time() + 120
            self.log_master_console(f"📥 Starting dump of {filename}...\n", "info")
            self.send_command(f"D {filename}")
    
    def request_status(self):
        """Request status using single-letter command."""
        # Use single-letter 'T' for status (sTatus)
        self.send_command("T")
    
    def on_data_received(self, data):
        """Handle data from Arduino - legacy method redirects to master."""
        self.on_master_data_received(data)
    
    def _process_master_data(self, data):
        """Process received data from Master (runs in main thread)."""
        # Update last data time and clear pending command
        self.last_data_time = time.time()
        self.master_bytes += len(data) + 1
        self.update_stats()
        
        # Check if this is a response to our pending command
        if self.pending_command:
            # Clear pending on any meaningful response
            if data.strip() and data not in ["OK"]:
                self.consecutive_timeouts = 0
            if data == "OK" or data.startswith("Files:") or data.startswith("St:") or data.startswith("ERR:"):
                self.pending_command = None
                self.pending_command_time = None
        
        if self.dump_mode:
            # Reset timeout on any data received (keeps connection alive)
            if self.dump_timeout:
                self.dump_timeout = time.time() + 30  # Reset to 30s on each data
            
            # Handle SIZE header from Arduino (file size info)
            if data.startswith("SIZE:"):
                # SIZE header means dump is really starting, clear the ignore flag
                self.dump_ignore_first_ok = False
                try:
                    self.dump_file_size = int(data.split(":")[1])
                    self.log_master_console(f"📊 File size: {self.dump_file_size} bytes\n", "info")
                except ValueError:
                    pass
                return  # Don't add SIZE line to buffer
            
            # Collecting dump data - look for OK to end dump
            if data == "OK":
                # Ignore the first OK which is from the stop command, not the dump
                if self.dump_ignore_first_ok:
                    self.dump_ignore_first_ok = False
                    self.log_master_console("⏹ Logging stopped\n", "info")
                    return  # Skip this OK, wait for the real dump OK
                self.dump_mode = False
                self.dump_ignore_first_ok = False
                self.save_dump_data()
            elif data == "ABORTED":
                self.dump_mode = False
                self.dump_ignore_first_ok = False
                self.log_master_console("⚠️ Dump aborted by user\n", "error")
                self.dump_buffer = []
                self.dump_save_path = None
            elif data.startswith("ERR:") or data.startswith("E:"):
                self.dump_mode = False
                self.dump_ignore_first_ok = False
                if data == "E:B":
                    self.log_master_console("❌ Dump failed: Master is busy (try stopping first with STOP button)\n", "error")
                elif data == "E:NL":
                    self.log_master_console("❌ Dump failed: No log file exists (try START to create one)\n", "error")
                elif data == "E:NF":
                    self.log_master_console("❌ Dump failed: File not found\n", "error")
                elif data == "E:DL":
                    self.log_master_console("❌ Dump failed: Data logger not initialized\n", "error")
                else:
                    self.log_master_console(f"❌ Dump failed: {data}\n", "error")
                self.dump_buffer = []
                self.dump_save_path = None
            else:
                # Any data line means dump is really happening, clear ignore flag
                self.dump_ignore_first_ok = False
                # Collect all data lines and track bytes received
                self.dump_buffer.append(data)
                self.dump_bytes_received += len(data) + 1  # +1 for newline
                
                # Log progress every 10KB
                if self.dump_file_size > 0 and self.dump_bytes_received % 10240 < 100:
                    pct = min(100, int(self.dump_bytes_received * 100 / self.dump_file_size))
                    self.log_master_console(f"📥 Progress: {pct}% ({self.dump_bytes_received}/{self.dump_file_size} bytes)\n", "info")
        elif data.startswith("Files:"):
            # File list response - expecting "Files:0" or filename lines to follow
            if data == "Files:0":
                self.file_listbox.delete(0, tk.END)
                self.file_listbox.insert(tk.END, "(No files on SD card)")
                self.log_master_console(data + "\n")
            else:
                # Files: prefix with first filename on same line
                self.file_listbox.delete(0, tk.END)
                # Initialize file buffer for sorting
                self.file_buffer = []
                # Extract first file info from "Files:FILENAME|SIZE"
                first_file = data.split("Files:")[1].strip()
                if first_file:
                    self.file_buffer.append(first_file)
                self.log_console(data)
                # Mark that we're collecting file list
                self.collecting_files = True
        elif hasattr(self, 'collecting_files') and self.collecting_files:
            # Receiving file list entries
            data_stripped = data.strip()
            if data_stripped == "OK" or data_stripped.startswith("St:"):
                # End of file list - sort and display files (most recent first)
                self.collecting_files = False
                if hasattr(self, 'file_buffer') and self.file_buffer:
                    # Sort files by log number descending (most recent first)
                    def get_log_num(entry):
                        # Extract log number from "LOG_XXXX.CSV|size" or just filename
                        name = entry.split('|')[0] if '|' in entry else entry
                        if name.startswith('LOG_') and len(name) >= 8:
                            try:
                                return int(name[4:8])
                            except ValueError:
                                return -1
                        return -1
                    
                    self.file_buffer.sort(key=get_log_num, reverse=True)
                    
                    # Display sorted files in listbox
                    for file_entry in self.file_buffer:
                        display_name = self._format_file_entry(file_entry)
                        self.file_listbox.insert(tk.END, display_name)
                    
                    self.log_console(f"📁 Loaded {len(self.file_buffer)} files (sorted by newest)")
                    self.file_buffer = []
                
                if data_stripped.startswith("St:"):
                    self._process_status(data_stripped)
                else:
                    self.log_console(data)
            elif '|' in data or data.endswith(".CSV") or data.endswith(".TXT"):
                # This is a filename (with optional size: "filename|size") - buffer it
                if hasattr(self, 'file_buffer'):
                    self.file_buffer.append(data.strip())
                self.log_console(data)
            else:
                # Unknown data during file collection
                self.log_console(data)
        elif data.startswith("DEBUG:"):
            # Debug messages
            self.log_console(f"🔍 {data}")
        else:
            # Regular console output
            self.log_console(data)
    
    def on_status_received(self, status):
        """Handle status updates from Arduino."""
        self.root.after(0, lambda: self._process_status(status))
    
    def _process_status(self, status):
        """Process status update (runs in main thread)."""
        # Parse status: St:R CAN:Y RPM:1234 GPS:Y Sat:5 SD:Y LED:Y
        if 'St:' in status:
            state_char = status.split('St:')[1][0]
            states = {'R': 'RUNNING', 'P': 'PAUSED', 'L': 'LIVE', 'I': 'IDLE'}
            self.current_state = states.get(state_char, 'UNKNOWN')
            self.state_label.config(text=f"System State: {self.current_state}")
        
        self.log_console(status)
    
    def save_dump_data(self):
        """Save dumped data to file."""
        if not self.dump_buffer:
            self.log_console("⚠️ No data received to save")
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"arduino_dump_{timestamp}.csv"
        
        # Use previously selected directory or prompt
        if self.dump_save_path:
            save_dir = self.dump_save_path
            self.dump_save_path = None
        else:
            save_dir = filedialog.askdirectory(title="Select folder to save dump")
            if not save_dir:
                return
        
        filepath = os.path.join(save_dir, filename)
        
        try:
            with open(filepath, 'w') as f:
                for line in self.dump_buffer:
                    f.write(line + '\n')
            
            self.log_console(f"✓ Saved {len(self.dump_buffer)} lines to {filepath}")
        except Exception as e:
            self.log_console(f"❌ Error saving file: {e}")
            messagebox.showerror("Save Error", f"Failed to save file:\n{str(e)}")
        
        self.dump_buffer = []
    
    def log_console(self, message):
        """Add message to master console (legacy compatibility)."""
        if not message.endswith('\n'):
            message += '\n'
        self.log_master_console(message)
    
    def clear_console(self):
        """Clear master console output (legacy compatibility)."""
        self.clear_master_console()
    
    def check_command_timeout(self):
        """Check if a command has timed out without response."""
        if self.master_arduino.is_connected:
            current_time = time.time()
            
            # Check if we have a pending command that's timed out
            if self.pending_command and self.pending_command_time:
                # Skip timeout check for dump commands (they have their own 30s timeout)
                if self.pending_command.startswith('D '):
                    return
                
                elapsed = current_time - self.pending_command_time
                if elapsed > self.command_timeout:
                    self.consecutive_timeouts += 1
                    self.log_console(f"⚠️ TIMEOUT: '{self.pending_command}' no response after {elapsed:.1f}s")
                    
                    if self.consecutive_timeouts >= 3:
                        self.log_console(f"❌ ERROR: Arduino not responding after {self.consecutive_timeouts} timeouts")
                        self.log_console("💡 Try: Disconnect and reconnect, or reset Arduino")
                    
                    self.pending_command = None
                    self.pending_command_time = None
                    self.error_count += 1
            
            # Check if we haven't received any data for a while (Arduino might be frozen)
            time_since_data = current_time - self.last_data_time
            if time_since_data > 60 and self.pending_command is None:  # Extended to 60s
                self.last_data_time = current_time  # Reset to avoid spam
        
        # Schedule next check
        self.root.after(1000, self.check_command_timeout)
    
    def show_diagnostics(self):
        """Show diagnostic information."""
        self.log_console("\n" + "="*50)
        self.log_console("DIAGNOSTICS:")
        self.log_console(f"  Master: {'Connected' if self.master_arduino.is_connected else 'Disconnected'}")
        if self.master_arduino.is_connected:
            self.log_console(f"  Master Port: {self.master_arduino.port_name}")
        self.log_console(f"  Slave: {'Connected' if self.slave_arduino.is_connected else 'Disconnected'}")
        if self.slave_arduino.is_connected:
            self.log_console(f"  Slave Port: {self.slave_arduino.port_name}")
        self.log_console(f"  System State: {self.current_state}")
        self.log_console(f"  Pending Command: {self.pending_command or 'None'}")
        if self.pending_command_time:
            elapsed = time.time() - self.pending_command_time
            self.log_console(f"  Waiting for: {elapsed:.1f}s")
        self.log_console(f"  Error Count: {self.error_count}")
        self.log_console(f"  Consecutive Timeouts: {self.consecutive_timeouts}")
        time_since = time.time() - self.last_data_time
        self.log_console(f"  Last Data: {time_since:.1f}s ago")
        self.log_console("="*50 + "\n")
    
    def on_close(self):
        """Handle window close."""
        if self.master_arduino.is_connected:
            self.master_arduino.disconnect()
        if self.slave_arduino.is_connected:
            self.slave_arduino.disconnect()
        self.root.destroy()


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    print("\n" + "="*70)
    print("MX5-Telemetry Arduino Actions - Dual Monitor")
    print("="*70 + "\n")
    
    root = tk.Tk()
    # Force window to appear in front
    root.lift()
    root.attributes('-topmost', True)
    root.after(100, lambda: root.attributes('-topmost', False))
    root.focus_force()
    app = ArduinoActionsApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
