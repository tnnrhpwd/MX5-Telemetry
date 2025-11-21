"""
MX5-Telemetry Arduino Actions - USB Command Interface
======================================================
Interactive GUI for controlling Arduino telemetry system via USB-C.

Features:
- Auto-detect Arduino on USB ports
- Send commands (START, PAUSE, RESUME, LIVE, STOP, etc.)
- Live data streaming viewer
- Dump log files from SD card to computer
- Real-time system status monitoring
- Log file browser and management

Commands:
- START   : Begin logging and LED display
- PAUSE   : Stop logging and LED display
- RESUME  : Continue logging and LED display
- LIVE    : Real-time data streaming (no SD logging)
- STOP    : Exit live mode, return to pause
- DUMP    : Transfer log files to laptop
- STATUS  : Show system diagnostics
- LIST    : List all files on SD card
- HELP    : Show command reference

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
                ports.append({'port': port.device, 'desc': port.description})
            # Also include all USB serial devices
            elif 'USB' in port.description or 'COM' in port.device:
                ports.append({'port': port.device, 'desc': port.description})
        return ports
    
    def connect(self, port_name, baud_rate=115200):
        """Connect to Arduino on specified port."""
        try:
            self.serial_port = serial.Serial(port_name, baud_rate, timeout=1)
            time.sleep(2)  # Wait for Arduino to reset after connection
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
            self.serial_port.write(f"{command}\n".encode())
            self.serial_port.flush()
            return True
        except Exception as e:
            print(f"Error sending command: {e}")
            return False
    
    def _read_loop(self):
        """Background thread for reading serial data."""
        buffer = ""
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
        self.root.resizable(True, False)
        
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
        self.log_files = []
        
        # Create UI
        self.create_ui()
        
        # Cleanup on close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Auto-refresh port list periodically
        self.refresh_ports_periodically()
    
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
                       foreground='#ffffff', borderwidth=0)
        
        self.port_combo = ttk.Combobox(port_frame, width=42, state='readonly', style='TCombobox')
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
        
        btn_row1 = tk.Frame(cmd_frame, bg="#2a2a2a")
        btn_row1.pack(pady=5)
        
        self.start_btn = tk.Button(btn_row1, text="▶ START", 
                                   command=lambda: self.send_command("START"),
                                   bg="#00aa00", fg="#ffffff", 
                                   font=("Segoe UI", 11, "bold"), width=12, height=2,
                                   relief=tk.FLAT, bd=0,
                                   activebackground="#00cc00", activeforeground="#ffffff",
                                   cursor="hand2", state=tk.DISABLED)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.pause_btn = tk.Button(btn_row1, text="⏸ PAUSE", 
                                   command=lambda: self.send_command("PAUSE"),
                                   bg="#ff8800", fg="#ffffff", 
                                   font=("Segoe UI", 11, "bold"), width=12, height=2,
                                   relief=tk.FLAT, bd=0,
                                   activebackground="#ffaa00", activeforeground="#ffffff",
                                   cursor="hand2", state=tk.DISABLED)
        self.pause_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = tk.Button(btn_row1, text="⏹ STOP", 
                                 command=lambda: self.send_command("STOP"),
                                 bg="#cc0000", fg="#ffffff", 
                                 font=("Segoe UI", 11, "bold"), width=12, height=2,
                                 relief=tk.FLAT, bd=0,
                                 activebackground="#ff0000", activeforeground="#ffffff",
                                 cursor="hand2", state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        btn_row2 = tk.Frame(cmd_frame, bg="#2a2a2a")
        btn_row2.pack(pady=5)
        
        self.live_btn = tk.Button(btn_row2, text="📡 LIVE MONITOR", 
                                  command=lambda: self.send_command("LIVE"),
                                  bg="#9900cc", fg="#ffffff", 
                                  font=("Segoe UI", 11, "bold"), width=15, height=2,
                                  relief=tk.FLAT, bd=0,
                                  activebackground="#bb00ff", activeforeground="#ffffff",
                                  cursor="hand2", state=tk.DISABLED)
        self.live_btn.pack(side=tk.LEFT, padx=5)
        
        self.status_btn = tk.Button(btn_row2, text="📊 STATUS", 
                                    command=lambda: self.send_command("STATUS"),
                                    bg="#555555", fg="#ffffff", 
                                    font=("Segoe UI", 11, "bold"), width=15, height=2,
                                    relief=tk.FLAT, bd=0,
                                    activebackground="#777777", activeforeground="#ffffff",
                                    cursor="hand2", state=tk.DISABLED)
        self.status_btn.pack(side=tk.LEFT, padx=5)
        
        self.help_btn = tk.Button(btn_row2, text="❓ HELP", 
                                 command=lambda: self.send_command("HELP"),
                                 bg="#555555", fg="#ffffff", 
                                 font=("Segoe UI", 11, "bold"), width=15, height=2,
                                 relief=tk.FLAT, bd=0,
                                 activebackground="#777777", activeforeground="#ffffff",
                                 cursor="hand2", state=tk.DISABLED)
        self.help_btn.pack(side=tk.LEFT, padx=5)
        
        # Data dump frame
        dump_frame = tk.Frame(self.root, bg="#2a2a2a", relief=tk.FLAT, bd=0)
        dump_frame.pack(pady=8, padx=20, fill=tk.X)
        
        tk.Label(dump_frame, text="DATA MANAGEMENT", font=("Segoe UI", 11, "bold"), 
                fg="#ffffff", bg="#2a2a2a").pack(pady=5)
        
        dump_btn_frame = tk.Frame(dump_frame, bg="#2a2a2a")
        dump_btn_frame.pack(pady=5)
        
        self.list_btn = tk.Button(dump_btn_frame, text="📋 LIST FILES", 
                                 command=self.list_files,
                                 bg="#0066cc", fg="#ffffff", 
                                 font=("Segoe UI", 10, "bold"), width=15,
                                 relief=tk.FLAT, bd=0, pady=8,
                                 activebackground="#0088ff", activeforeground="#ffffff",
                                 cursor="hand2", state=tk.DISABLED)
        self.list_btn.pack(side=tk.LEFT, padx=5)
        
        self.dump_btn = tk.Button(dump_btn_frame, text="💾 DUMP CURRENT LOG", 
                                 command=self.dump_current_log,
                                 bg="#00aa00", fg="#ffffff", 
                                 font=("Segoe UI", 10, "bold"), width=18,
                                 relief=tk.FLAT, bd=0, pady=8,
                                 activebackground="#00cc00", activeforeground="#ffffff",
                                 cursor="hand2", state=tk.DISABLED)
        self.dump_btn.pack(side=tk.LEFT, padx=5)
        
        self.dump_selected_btn = tk.Button(dump_btn_frame, text="📥 DUMP SELECTED", 
                                          command=self.dump_selected_file,
                                          bg="#00aa00", fg="#ffffff", 
                                          font=("Segoe UI", 10, "bold"), width=18,
                                          relief=tk.FLAT, bd=0, pady=8,
                                          activebackground="#00cc00", activeforeground="#ffffff",
                                          cursor="hand2", state=tk.DISABLED)
        self.dump_selected_btn.pack(side=tk.LEFT, padx=5)
        
        # File list frame
        file_frame = tk.Frame(dump_frame, bg="#2a2a2a")
        file_frame.pack(pady=5, padx=10, fill=tk.BOTH, expand=False)
        
        tk.Label(file_frame, text="SD Card Files:", font=("Segoe UI", 9, "bold"), 
                fg="#ffffff", bg="#2a2a2a").pack(anchor=tk.W, pady=3)
        
        self.file_listbox = tk.Listbox(file_frame, height=4, bg="#1a1a1a", fg="#ffffff",
                                       font=("Consolas", 9), selectmode=tk.SINGLE,
                                       relief=tk.FLAT, bd=0, highlightthickness=1,
                                       highlightbackground="#3a3a3a", highlightcolor="#0066cc",
                                       selectbackground="#0066cc", selectforeground="#ffffff")
        self.file_listbox.pack(fill=tk.BOTH, expand=True, pady=2)
        
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
        
        # Clear console button
        clear_btn = tk.Button(console_frame, text="🗑 Clear Console", 
                            command=self.clear_console,
                            bg="#3a3a3a", fg="#ffffff", font=("Segoe UI", 9),
                            relief=tk.FLAT, bd=0, padx=15, pady=5,
                            activebackground="#4a4a4a", activeforeground="#ffffff",
                            cursor="hand2")
        clear_btn.pack(pady=5)
        
        # System state indicator
        self.state_label = tk.Label(self.root, text="System State: IDLE", 
                                   font=("Segoe UI", 11, "bold"), fg="#ffffff", bg="#1a1a1a")
        self.state_label.pack(pady=8)
        
        # Initial port refresh
        self.refresh_ports()
    
    def refresh_ports(self):
        """Refresh available serial ports."""
        ports = self.arduino.find_arduino_ports()
        port_list = [f"{p['port']} - {p['desc']}" for p in ports]
        
        self.port_combo['values'] = port_list
        if port_list:
            self.port_combo.current(0)
            self.log_console(f"Found {len(port_list)} port(s)")
        else:
            self.log_console("⚠️ No Arduino ports detected")
    
    def refresh_ports_periodically(self):
        """Auto-refresh ports every 5 seconds if not connected."""
        if not self.arduino.is_connected:
            self.refresh_ports()
        self.root.after(5000, self.refresh_ports_periodically)
    
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
        self.status_label.config(text=f"🟢 Connected to {self.arduino.port_name}", fg="#ffffff")
        self.connect_btn.config(text="🔌 Disconnect", bg="#cc0000")
        
        # Enable command buttons
        self.start_btn.config(state=tk.NORMAL)
        self.pause_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.NORMAL)
        self.live_btn.config(state=tk.NORMAL)
        self.status_btn.config(state=tk.NORMAL)
        self.help_btn.config(state=tk.NORMAL)
        self.list_btn.config(state=tk.NORMAL)
        self.dump_btn.config(state=tk.NORMAL)
        self.dump_selected_btn.config(state=tk.NORMAL)
        
        # Request initial status
        self.root.after(500, lambda: self.send_command("STATUS"))
    
    def on_disconnected(self):
        """Handle disconnection."""
        self.status_label.config(text="⚫ Disconnected", fg="#ffffff")
        self.connect_btn.config(text="🔌 Connect", bg="#00aa00")
        
        # Disable command buttons
        self.start_btn.config(state=tk.DISABLED)
        self.pause_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.DISABLED)
        self.live_btn.config(state=tk.DISABLED)
        self.status_btn.config(state=tk.DISABLED)
        self.help_btn.config(state=tk.DISABLED)
        self.list_btn.config(state=tk.DISABLED)
        self.dump_btn.config(state=tk.DISABLED)
        self.dump_selected_btn.config(state=tk.DISABLED)
        
        self.log_console("⚫ Disconnected from Arduino")
    
    def send_command(self, command):
        """Send command to Arduino."""
        if self.arduino.send_command(command):
            self.log_console(f"→ {command}")
    
    def list_files(self):
        """List files on SD card."""
        self.file_listbox.delete(0, tk.END)
        self.send_command("LIST")
    
    def dump_current_log(self):
        """Dump current log file from SD card."""
        save_path = filedialog.askdirectory(title="Select folder to save log")
        if save_path:
            self.dump_buffer = []
            self.dump_mode = True
            self.log_console("📥 Starting dump of current log...")
            self.send_command("DUMP")
    
    def dump_selected_file(self):
        """Dump selected file from list."""
        selection = self.file_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a file to dump")
            return
        
        filename = self.file_listbox.get(selection[0])
        save_path = filedialog.askdirectory(title="Select folder to save log")
        
        if save_path:
            self.dump_buffer = []
            self.dump_mode = True
            self.log_console(f"📥 Starting dump of {filename}...")
            self.send_command(f"DUMP {filename}")
    
    def on_data_received(self, data):
        """Handle data from Arduino."""
        # Use after() to update UI from main thread
        self.root.after(0, lambda: self._process_data(data))
    
    def _process_data(self, data):
        """Process received data (runs in main thread)."""
        if self.dump_mode:
            # Collecting dump data
            if data.startswith("END_DUMP"):
                self.dump_mode = False
                self.save_dump_data()
            else:
                self.dump_buffer.append(data)
        elif data.startswith("FILES:"):
            # File list response
            files = data[6:].strip().split(',')
            self.file_listbox.delete(0, tk.END)
            for f in files:
                if f.strip():
                    self.file_listbox.insert(tk.END, f.strip())
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
        
        save_dir = filedialog.askdirectory(title="Select folder to save dump")
        if not save_dir:
            return
        
        filepath = os.path.join(save_dir, filename)
        
        try:
            with open(filepath, 'w') as f:
                for line in self.dump_buffer:
                    f.write(line + '\n')
            
            self.log_console(f"✓ Saved {len(self.dump_buffer)} lines to {filepath}")
            messagebox.showinfo("Dump Complete", f"Successfully saved to:\n{filepath}")
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
    app = ArduinoActionsApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
