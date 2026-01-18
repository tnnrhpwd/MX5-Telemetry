"""
MX5 Telemetry Web Remote Control

Provides a mobile web interface for controlling the display system when parked.
Replaces the need for steering wheel control integration.

Usage:
    1. Connect phone to Pi's hotspot (or same network)
    2. Open http://192.168.1.28:5000 in browser
    3. Navigate screens and change settings remotely

Features:
    - Screen navigation (8 screens)
    - Settings control (demo mode, etc.)
    - Real-time sync via WebSocket
    - Mobile-optimized UI
"""

import threading
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import time

class WebRemoteServer:
    """Web-based remote control for MX5 display system"""
    
    def __init__(self, display_app):
        """
        Args:
            display_app: Main display application instance (has screen, settings, etc.)
        """
        self.app = Flask(__name__, 
                        static_folder='../static',
                        template_folder='../templates')
        self.app.config['SECRET_KEY'] = 'mx5-telemetry-2026'
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        self.display_app = display_app
        
        self._running = False
        self._thread = None
        
        # Setup routes
        self._setup_routes()
        self._setup_socketio()
    
    def _setup_routes(self):
        """Setup Flask REST API routes"""
        
        @self.app.route('/')
        def index():
            """Serve main remote control page"""
            return render_template('index.html')
        
        @self.app.route('/api/status')
        def get_status():
            """Get current system status"""
            return jsonify({
                'screen': self.display_app.current_screen,
                'screen_name': self.display_app.screen_names[self.display_app.current_screen],
                'demo_mode': self.display_app.settings.demo_mode,
                'sleeping': self.display_app.sleeping,
                'nav_locked': self.display_app.swc_handler.nav_locked if self.display_app.swc_handler else False,
                'settings': {
                    'demo_mode': self.display_app.settings.demo_mode,
                    'brightness': self.display_app.settings.brightness,
                    'volume': self.display_app.settings.volume,
                    'shift_rpm': self.display_app.settings.shift_rpm,
                    'redline_rpm': self.display_app.settings.redline_rpm,
                    'use_mph': self.display_app.settings.use_mph,
                    'tire_low_psi': self.display_app.settings.tire_low_psi,
                    'tire_high_psi': self.display_app.settings.tire_high_psi,
                    'coolant_warn_f': self.display_app.settings.coolant_warn_f,
                    'led_sequence': self.display_app.settings.led_sequence
                }
            })
        
        @self.app.route('/api/screen/<int:screen_num>', methods=['POST'])
        def change_screen(screen_num):
            """Change to specific screen"""
            if 0 <= screen_num < 8:
                self.display_app.change_screen(screen_num)
                # Notify all connected clients
                self.socketio.emit('screen_changed', {'screen': screen_num})
                return jsonify({'success': True, 'screen': screen_num})
            return jsonify({'success': False, 'error': 'Invalid screen number'}), 400
        
        @self.app.route('/api/screen/next', methods=['POST'])
        def next_screen():
            """Go to next screen"""
            new_screen = (self.display_app.current_screen + 1) % 8
            self.display_app.change_screen(new_screen)
            self.socketio.emit('screen_changed', {'screen': new_screen})
            return jsonify({'success': True, 'screen': new_screen})
        
        @self.app.route('/api/screen/prev', methods=['POST'])
        def prev_screen():
            """Go to previous screen"""
            new_screen = (self.display_app.current_screen - 1) % 8
            self.display_app.change_screen(new_screen)
            self.socketio.emit('screen_changed', {'screen': new_screen})
            return jsonify({'success': True, 'screen': new_screen})
        
        @self.app.route('/api/settings/update', methods=['POST'])
        def update_setting():
            """Update any setting"""
            data = request.json
            name = data.get('name')
            value = data.get('value')
            
            if not name:
                return jsonify({'success': False, 'error': 'Missing setting name'}), 400
            
            try:
                # Handle each setting type appropriately
                if name == 'demo_mode':
                    self.display_app.settings.demo_mode = (value == '1' or value == True)
                    # Reinitialize data sources if demo mode changed
                    self.display_app._init_data_sources()
                elif name == 'brightness':
                    self.display_app.settings.brightness = int(value)
                elif name == 'volume':
                    self.display_app.settings.volume = int(value)
                    self.display_app.sound.set_volume(self.display_app.settings.volume)
                elif name == 'shift_rpm':
                    self.display_app.settings.shift_rpm = int(value)
                elif name == 'redline_rpm':
                    self.display_app.settings.redline_rpm = int(value)
                elif name == 'use_mph':
                    self.display_app.settings.use_mph = (value == '1' or value == True)
                elif name == 'tire_low_psi':
                    self.display_app.settings.tire_low_psi = float(value)
                elif name == 'tire_high_psi':
                    self.display_app.settings.tire_high_psi = float(value)
                elif name == 'coolant_warn':
                    self.display_app.settings.coolant_warn_f = int(value)
                elif name == 'led_sequence':
                    self.display_app.settings.led_sequence = int(value)
                    # Send LED sequence change to Arduino using the app's method
                    if hasattr(self.display_app, '_send_led_sequence_to_arduino'):
                        self.display_app._send_led_sequence_to_arduino()
                else:
                    return jsonify({'success': False, 'error': 'Unknown setting'}), 400
                
                # Sync to ESP32 if available
                if self.display_app.esp32_handler:
                    self.display_app._sync_settings_to_esp32()
                
                # Notify all clients
                self.socketio.emit('setting_changed', {name: value})
                return jsonify({'success': True, 'name': name, 'value': value})
                
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/wake', methods=['POST'])
        def wake_display():
            """Wake display from sleep"""
            if self.display_app.sleeping:
                self.display_app.sleeping = False
                self.display_app.last_activity = time.time()
            return jsonify({'success': True})
    
    def _setup_socketio(self):
        """Setup WebSocket event handlers"""
        
        @self.socketio.on('connect')
        def handle_connect():
            """Client connected - send current status"""
            print("Web remote client connected")
            emit('status', {
                'screen': self.display_app.current_screen,
                'screen_name': self.display_app.screen_names[self.display_app.current_screen],
                'demo_mode': self.display_app.settings.demo_mode
            })
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Client disconnected"""
            print("Web remote client disconnected")
        
        @self.socketio.on('request_status')
        def handle_status_request():
            """Client requesting status update"""
            emit('status', {
                'screen': self.display_app.current_screen,
                'screen_name': self.display_app.screen_names[self.display_app.current_screen],
                'demo_mode': self.display_app.settings.demo_mode
            })
    
    def notify_screen_change(self, screen_num):
        """Notify all connected clients of screen change"""
        self.socketio.emit('screen_changed', {
            'screen': screen_num,
            'screen_name': self.display_app.screen_names[screen_num]
        })
    
    def notify_setting_change(self, setting_name, value):
        """Notify all connected clients of setting change"""
        self.socketio.emit('setting_changed', {setting_name: value})
    
    def start(self, host='0.0.0.0', port=5000):
        """Start web server in background thread"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(
            target=self._run_server,
            args=(host, port),
            daemon=True
        )
        self._thread.start()
        print(f"Web remote control started at http://{host}:{port}")
    
    def _run_server(self, host, port):
        """Run Flask server (called in background thread)"""
        self.socketio.run(self.app, host=host, port=port, debug=False, use_reloader=False)
    
    def stop(self):
        """Stop web server"""
        self._running = False
        # Note: Flask/SocketIO doesn't have a clean shutdown method
        # The daemon thread will terminate when main program exits
