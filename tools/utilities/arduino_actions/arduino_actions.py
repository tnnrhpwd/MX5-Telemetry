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
        self.root.geometry("1000x750")
        self.root.configure(bg='#1a1a1a')
        self.root.resizable(True, True)
        
        # Arduino connection
        self.arduino = ArduinoConnection()
        self.arduino.set_callback('on_data', self.on_data_received)
        self.arduino.set_callback('on_status', self.on_status_received)
        self.arduino.set_callback('on_connect', self.on_connected)
        self.arduino.set_callback('on_disconnect', self.on_disconnected)
        
        # State
        self.current_state = "IDLE"
        self.dump_mode = False
        self.dump_buffer = []
        self.dump_save_path = None
        self.dump_timeout = None
        self.dump_file_size = 0  # Expected file size from Arduino
        self.dump_bytes_received = 0  # Bytes received so far
        self.dump_filename = None  # Name of file being dumped
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
        
        # Create UI
        self.create_ui()
        
        # Cleanup on close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Auto-refresh port list periodically
        self.refresh_ports_periodically()
        
        # Start watchdog for command timeouts
        self.check_command_timeout()
    
    def create_ui(self):
        """Create the user interface."""
        
        # Title
        title = tk.Label(self.root, text="Arduino Actions - USB Control Interface", 
                        font=("Segoe UI", 20, "bold"), fg="#ffffff", bg="#1a1a1a")
        title.pack(pady=10)
        
        # Connection frame
        conn_frame = tk.Frame(self.root, bg="#2a2a2a", relief=tk.FLAT, bd=0)
        conn_frame.pack(pady=8, padx=20, fill=tk.X)
        
        tk.Label(conn_frame, text="ARDUINO CONNECTION", font=("Segoe UI", 11, "bold"), 
                fg="#ffffff", bg="#2a2a2a").pack(pady=5)
        
        port_frame = tk.Frame(conn_frame, bg="#2a2a2a")
        port_frame.pack(pady=8)
        
        tk.Label(port_frame, text="Port:", font=("Segoe UI", 10), 
                fg="#ffffff", bg="#2a2a2a").pack(side=tk.LEFT, padx=5)
        
        # Style the combobox
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TCombobox', fieldbackground='#3a3a3a', background='#3a3a3a', 
                       foreground="#2600ff", borderwidth=0)
        
        self.port_combo = ttk.Combobox(port_frame, width=60, state='readonly', style='TCombobox')
        self.port_combo.pack(side=tk.LEFT, padx=5)
        
        self.refresh_btn = tk.Button(port_frame, text="🔄 Refresh", 
                                     command=self.refresh_ports,
                                     bg="#3a3a3a", fg="#ffffff", font=("Segoe UI", 9),
                                     relief=tk.FLAT, bd=0, padx=15, pady=5,
                                     activebackground="#4a4a4a", activeforeground="#ffffff",
                                     cursor="hand2")
        self.refresh_btn.pack(side=tk.LEFT, padx=5)
        
        self.connect_btn = tk.Button(port_frame, text="🔌 Connect", 
                                     command=self.toggle_connection,
                                     bg="#00aa00", fg="#ffffff", 
                                     font=("Segoe UI", 10, "bold"), width=12,
                                     relief=tk.FLAT, bd=0, padx=10, pady=8,
                                     activebackground="#00cc00", activeforeground="#ffffff",
                                     cursor="hand2")
        self.connect_btn.pack(side=tk.LEFT, padx=5)
        
        self.status_label = tk.Label(conn_frame, text="⚫ Disconnected", 
                                     font=("Segoe UI", 10), fg="#ffffff", bg="#2a2a2a")
        self.status_label.pack(pady=5)
        
        # Command buttons frame
        cmd_frame = tk.Frame(self.root, bg="#2a2a2a", relief=tk.FLAT, bd=0)
        cmd_frame.pack(pady=8, padx=20, fill=tk.X)
        
        tk.Label(cmd_frame, text="COMMANDS", font=("Segoe UI", 11, "bold"), 
            fg="#ffffff", bg="#2a2a2a").pack(pady=5)
        
        btn_row = tk.Frame(cmd_frame, bg="#2a2a2a")
        btn_row.pack(pady=5)
        
        self.start_btn = tk.Button(btn_row, text="▶ START", 
                       command=lambda: self.send_command("S"),
                       bg="#00aa00", fg="#ffffff", 
                       font=("Segoe UI", 11, "bold"), width=12, height=2,
                       relief=tk.FLAT, bd=0,
                       activebackground="#00cc00", activeforeground="#ffffff",
                       cursor="hand2", state=tk.DISABLED)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = tk.Button(btn_row, text="⏹ STOP", 
                     command=lambda: self.send_command("X"),
                     bg="#cc0000", fg="#ffffff", 
                     font=("Segoe UI", 11, "bold"), width=12, height=2,
                     relief=tk.FLAT, bd=0,
                     activebackground="#ff0000", activeforeground="#ffffff",
                     cursor="hand2", state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        self.status_btn = tk.Button(btn_row, text="📊 STATUS", 
                        command=self.request_status,
                        bg="#555555", fg="#ffffff", 
                        font=("Segoe UI", 11, "bold"), width=15, height=2,
                        relief=tk.FLAT, bd=0,
                        activebackground="#777777", activeforeground="#ffffff",
                        cursor="hand2", state=tk.DISABLED)
        self.status_btn.pack(side=tk.LEFT, padx=5)
        
        # Data dump frame
        dump_frame = tk.Frame(self.root, bg="#2a2a2a", relief=tk.FLAT, bd=0)
        dump_frame.pack(pady=8, padx=20, fill=tk.BOTH, expand=True)
        
        tk.Label(dump_frame, text="SD CARD DATA", font=("Segoe UI", 11, "bold"), 
                fg="#ffffff", bg="#2a2a2a").pack(pady=(5, 8))
        
        # File list frame with scrollbar - make it prominent
        file_frame = tk.Frame(dump_frame, bg="#1a1a1a", relief=tk.FLAT, bd=0)
        file_frame.pack(pady=5, padx=10, fill=tk.BOTH, expand=True)
        
        # Header row with label
        file_header = tk.Frame(file_frame, bg="#1a1a1a")
        file_header.pack(fill=tk.X, padx=5, pady=(5, 2))
        
        tk.Label(file_header, text="📁 Files on SD Card:", font=("Segoe UI", 10, "bold"), 
                fg="#888888", bg="#1a1a1a").pack(side=tk.LEFT)
        
        # Listbox with scrollbar
        listbox_frame = tk.Frame(file_frame, bg="#1a1a1a")
        listbox_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        scrollbar = tk.Scrollbar(listbox_frame, orient=tk.VERTICAL, bg="#3a3a3a", 
                                 troughcolor="#1a1a1a", activebackground="#555555")
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.file_listbox = tk.Listbox(listbox_frame, height=10, bg="#0d0d0d", fg="#00ff88",
                                       font=("Consolas", 11), selectmode=tk.SINGLE,
                                       relief=tk.FLAT, bd=0, highlightthickness=2,
                                       highlightbackground="#333333", highlightcolor="#0066cc",
                                       selectbackground="#0066cc", selectforeground="#ffffff",
                                       yscrollcommand=scrollbar.set)
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.file_listbox.yview)
        
        # Button row below the file list
        dump_btn_frame = tk.Frame(dump_frame, bg="#2a2a2a")
        dump_btn_frame.pack(pady=8)
        
        self.list_btn = tk.Button(dump_btn_frame, text="🔄 REFRESH FILES", 
                                 command=self.list_files,
                                 bg="#0066cc", fg="#ffffff", 
                                 font=("Segoe UI", 11, "bold"), width=16,
                                 relief=tk.FLAT, bd=0, pady=10,
                                 activebackground="#0088ff", activeforeground="#ffffff",
                                 cursor="hand2", state=tk.DISABLED)
        self.list_btn.pack(side=tk.LEFT, padx=8)
        
        self.dump_selected_btn = tk.Button(dump_btn_frame, text="💾 DOWNLOAD SELECTED", 
                                          command=self.dump_selected_file,
                                          bg="#00aa00", fg="#ffffff", 
                                          font=("Segoe UI", 11, "bold"), width=20,
                                          relief=tk.FLAT, bd=0, pady=10,
                                          activebackground="#00cc00", activeforeground="#ffffff",
                                          cursor="hand2", state=tk.DISABLED)
        self.dump_selected_btn.pack(side=tk.LEFT, padx=8)
        
        # Console output frame
        console_frame = tk.Frame(self.root, bg="#2a2a2a", relief=tk.FLAT, bd=0)
        console_frame.pack(pady=8, padx=20, fill=tk.BOTH, expand=True)
        
        tk.Label(console_frame, text="CONSOLE OUTPUT", font=("Segoe UI", 11, "bold"), 
                fg="#ffffff", bg="#2a2a2a").pack(pady=5)
        
        self.console = scrolledtext.ScrolledText(console_frame, height=15, 
                                                bg="#0d0d0d", fg="#ffffff",
                                                font=("Consolas", 9), wrap=tk.WORD,
                                                state=tk.DISABLED, relief=tk.FLAT, bd=0,
                                                highlightthickness=1, highlightbackground="#3a3a3a")
        self.console.pack(pady=5, padx=10, fill=tk.BOTH, expand=True)
        
        # Console control buttons
        console_btn_frame = tk.Frame(console_frame, bg="#2a2a2a")
        console_btn_frame.pack(pady=5)
        
        clear_btn = tk.Button(console_btn_frame, text="🗑 Clear Console", 
                            command=self.clear_console,
                            bg="#3a3a3a", fg="#ffffff", font=("Segoe UI", 9),
                            relief=tk.FLAT, bd=0, padx=15, pady=5,
                            activebackground="#4a4a4a", activeforeground="#ffffff",
                            cursor="hand2")
        clear_btn.pack(side=tk.LEFT, padx=5)
        
        diag_btn = tk.Button(console_btn_frame, text="🔍 Diagnostics", 
                           command=self.show_diagnostics,
                           bg="#3a3a3a", fg="#ffffff", font=("Segoe UI", 9),
                           relief=tk.FLAT, bd=0, padx=15, pady=5,
                           activebackground="#4a4a4a", activeforeground="#ffffff",
                           cursor="hand2")
        diag_btn.pack(side=tk.LEFT, padx=5)
        
        # System state indicator
        self.state_label = tk.Label(self.root, text="System State: IDLE", 
                                   font=("Segoe UI", 11, "bold"), fg="#ffffff", bg="#1a1a1a")
        self.state_label.pack(pady=8)
        
        # Initial port refresh
        self.refresh_ports()
    
    def refresh_ports(self):
        """Refresh available serial ports."""
        self.log_console("\n🔄 Scanning for Arduinos...")
        ports = self.arduino.find_arduino_ports()
        
        # Display identification logs
        if hasattr(self.arduino, '_id_logs'):
            for log in self.arduino._id_logs:
                self.log_console(log)
            self.arduino._id_logs = []
        
        port_list = [f"{p['port']} - {p['desc']}" for p in ports]
        
        self.port_combo['values'] = port_list
        if port_list:
            self.port_combo.current(0)
            self.log_console(f"✓ Found {len(port_list)} port(s)\n")
            
            # Log summary
            for p in ports:
                self.log_console(f"  {p['port']}: {p['type']}")
        else:
            self.log_console("⚠️ No Arduino ports detected")
    
    def refresh_ports_periodically(self):
        """Auto-refresh ports every 5 seconds if not connected."""
        # Disabled to prevent spam - user can manually refresh
        # if not self.arduino.is_connected:
        #     self.refresh_ports()
        # self.root.after(5000, self.refresh_ports_periodically)
        pass
    
    def toggle_connection(self):
        """Toggle Arduino connection."""
        if self.arduino.is_connected:
            self.arduino.disconnect()
        else:
            selected = self.port_combo.get()
            if selected:
                port_name = selected.split(' - ')[0]
                self.log_console(f"Connecting to {port_name}...")
                if self.arduino.connect(port_name):
                    self.log_console(f"✓ Connected to {port_name}")
    
    def on_connected(self):
        """Handle successful connection."""
        self.status_label.config(text=f"🟢 Connected to {self.arduino.port_name}", fg="#00ff88")
        self.connect_btn.config(text="🔌 Disconnect", bg="#cc0000")
        
        # Enable command buttons
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_btn.config(state=tk.NORMAL)
        self.list_btn.config(state=tk.NORMAL)
        self.dump_selected_btn.config(state=tk.NORMAL)
        
        # Don't auto-request status to avoid GPS interference
        # self.root.after(500, lambda: self.send_command("STATUS"))
    
    def on_disconnected(self):
        """Handle disconnection."""
        self.status_label.config(text="⚫ Disconnected", fg="#888888")
        self.connect_btn.config(text="🔌 Connect", bg="#00aa00")
        
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
        
        self.log_console("⚫ Disconnected from Arduino")
    
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
        """Send command to Arduino."""
        if self.arduino.send_command(command):
            self.log_console(f"→ {command}")
            # Track pending command for timeout detection
            self.pending_command = command
            self.pending_command_time = time.time()
        else:
            self.log_console(f"⚠️ Failed to send: {command}")
            self.error_count += 1
    
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
            self.dump_buffer = []
            self.dump_mode = True
            self.dump_save_path = save_path
            self.dump_file_size = 0
            self.dump_bytes_received = 0
            self.dump_filename = filename
            # Extended timeout: 120 seconds for large files (at 115200 baud, ~10KB/s theoretical)
            self.dump_timeout = time.time() + 120
            self.log_console(f"📥 Starting dump of {filename}...")
            self.send_command(f"D {filename}")
    
    def request_status(self):
        """Request status using single-letter command."""
        # Use single-letter 'T' for status (sTatus)
        self.send_command("T")
    
    def on_data_received(self, data):
        """Handle data from Arduino."""
        # Use after() to update UI from main thread
        self.root.after(0, lambda: self._process_data(data))
    
    def _process_data(self, data):
        """Process received data (runs in main thread)."""
        # Update last data time and clear pending command
        self.last_data_time = time.time()
        
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
                try:
                    self.dump_file_size = int(data.split(":")[1])
                    self.log_console(f"📊 File size: {self.dump_file_size} bytes")
                except ValueError:
                    pass
                return  # Don't add SIZE line to buffer
            
            # Collecting dump data - look for OK to end dump
            if data == "OK":
                self.dump_mode = False
                self.save_dump_data()
            elif data == "ABORTED":
                self.dump_mode = False
                self.log_console("⚠️ Dump aborted by user")
                self.dump_buffer = []
                self.dump_save_path = None
            elif data.startswith("ERR:"):
                self.dump_mode = False
                self.log_console(f"❌ Dump failed: {data}")
                self.dump_buffer = []
                self.dump_save_path = None
            else:
                # Collect all data lines and track bytes received
                self.dump_buffer.append(data)
                self.dump_bytes_received += len(data) + 1  # +1 for newline
                
                # Log progress every 10KB
                if self.dump_file_size > 0 and self.dump_bytes_received % 10240 < 100:
                    pct = min(100, int(self.dump_bytes_received * 100 / self.dump_file_size))
                    self.log_console(f"📥 Progress: {pct}% ({self.dump_bytes_received}/{self.dump_file_size} bytes)")
        elif data.startswith("Files:"):
            # File list response - expecting "Files:0" or filename lines to follow
            if data == "Files:0":
                self.file_listbox.delete(0, tk.END)
                self.file_listbox.insert(tk.END, "(No files on SD card)")
                self.log_console(data)
            else:
                # Files: prefix with first filename on same line
                self.file_listbox.delete(0, tk.END)
                # Extract first file info from "Files:FILENAME|SIZE"
                first_file = data.split("Files:")[1].strip()
                if first_file:
                    display_name = self._format_file_entry(first_file)
                    self.file_listbox.insert(tk.END, display_name)
                self.log_console(data)
                # Mark that we're collecting file list
                self.collecting_files = True
        elif hasattr(self, 'collecting_files') and self.collecting_files:
            # Receiving file list entries
            if data == "OK" or data.startswith("St:"):
                # End of file list
                self.collecting_files = False
                if data.startswith("St:"):
                    self._process_status(data)
                else:
                    self.log_console(data)
            elif '|' in data or data.endswith(".CSV") or data.endswith(".TXT"):
                # This is a filename (with optional size: "filename|size")
                display_name = self._format_file_entry(data)
                self.file_listbox.insert(tk.END, display_name)
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
        """Add message to console."""
        self.console.config(state=tk.NORMAL)
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.console.insert(tk.END, f"[{timestamp}] {message}\n")
        self.console.see(tk.END)
        self.console.config(state=tk.DISABLED)
    
    def clear_console(self):
        """Clear console output."""
        self.console.config(state=tk.NORMAL)
        self.console.delete(1.0, tk.END)
        self.console.config(state=tk.DISABLED)
    
    def check_command_timeout(self):
        """Check if a command has timed out without response."""
        if self.arduino.is_connected:
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
        self.log_console(f"  Connection: {'Connected' if self.arduino.is_connected else 'Disconnected'}")
        if self.arduino.is_connected:
            self.log_console(f"  Port: {self.arduino.port_name}")
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
        if self.arduino.is_connected:
            self.arduino.disconnect()
        self.root.destroy()

# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    print("\n" + "="*70)
    print("MX5-Telemetry Arduino Actions - Starting...")
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
