"""
MX5 Telemetry Web Remote Control

Provides a mobile web interface for controlling the display system when parked.
Replaces the need for steering wheel control integration.

Usage:
    1. Connect phone to Pi's hotspot (or same network)
    2. Open http://192.168.1.23:5000 in browser
    3. Navigate screens and change settings remotely

Features:
    - Screen navigation (8 screens)
    - Settings control (demo mode, etc.)
    - Real-time sync via WebSocket
    - Mobile-optimized UI
"""

import functools
import hmac
import logging
import os
import secrets
import threading
import time

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------

def _data_dir():
    """Repo `data/` directory (persistent storage, gitignored for secrets)."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data'))


def _load_or_create_secret_key():
    """Return a stable, per-install Flask SECRET_KEY.

    Prefers the MX5_WEB_SECRET_KEY environment variable, then a persisted file
    under data/, generating and storing a fresh random key on first run.
    """
    env_key = os.environ.get('MX5_WEB_SECRET_KEY', '').strip()
    if env_key:
        return env_key

    key_path = os.path.join(_data_dir(), 'web_secret_key')
    try:
        with open(key_path, 'r') as f:
            existing = f.read().strip()
            if existing:
                return existing
    except OSError:
        pass

    new_key = secrets.token_hex(32)
    try:
        os.makedirs(os.path.dirname(key_path), exist_ok=True)
        with open(key_path, 'w') as f:
            f.write(new_key)
        if os.name != 'nt':
            os.chmod(key_path, 0o600)
    except OSError:
        logger.warning("Could not persist web secret key; using ephemeral key")
    return new_key


def _get_access_token():
    """Access token (PIN) required for network-exposed control. Empty = disabled."""
    return os.environ.get('MX5_WEB_TOKEN', '').strip()


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
        self.app.config['SECRET_KEY'] = _load_or_create_secret_key()
        self._token = _get_access_token()

        # Restrict cross-origin access. Empty list => same-origin only.
        cors_env = os.environ.get('MX5_WEB_CORS', '').strip()
        self._cors = [o.strip() for o in cors_env.split(',') if o.strip()] if cors_env else []
        self.socketio = SocketIO(self.app, cors_allowed_origins=self._cors)
        self.display_app = display_app

        # Per-IP auth failure tracking for basic brute-force throttling.
        self._auth_failures = {}
        self._auth_lock = threading.Lock()
        
        self._running = False
        self._thread = None
        
        # Setup routes
        self._setup_routes()
        self._setup_socketio()

    # -- authentication -----------------------------------------------------

    def _extract_token(self):
        """Extract the access token from Authorization / X-Auth-Token / query / body."""
        auth = request.headers.get('Authorization', '')
        if auth.startswith('Bearer '):
            return auth[len('Bearer '):].strip()

        header = request.headers.get('X-Auth-Token')
        if header:
            return header.strip()

        query = request.args.get('token')
        if query:
            return query.strip()

        if request.is_json:
            data = request.get_json(silent=True) or {}
            body = data.get('token')
            if body:
                return str(body).strip()
        return ''

    def _token_valid(self, token):
        if not self._token:
            return False
        return bool(token) and hmac.compare_digest(
            token.encode('utf-8'), self._token.encode('utf-8'))

    def _client_ip(self):
        return request.remote_addr or 'unknown'

    def _authorized_http(self):
        """Return True if the request is authorized.

        With a configured token, the request must present it. Without one,
        only loopback clients are accepted (the server is localhost-only).
        """
        if not self._token:
            return self._client_ip() in ('127.0.0.1', '::1')
        return self._token_valid(self._extract_token())

    def _rate_limited(self):
        now = time.time()
        with self._auth_lock:
            window = [t for t in self._auth_failures.get(self._client_ip(), []) if now - t < 300]
        return len(window) >= 20

    def _record_auth_failure(self):
        now = time.time()
        with self._auth_lock:
            ip = self._client_ip()
            window = [t for t in self._auth_failures.get(ip, []) if now - t < 300]
            window.append(now)
            self._auth_failures[ip] = window

    def _require_auth(self, f):
        """Decorator that enforces token authentication (fail closed)."""
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            if self._rate_limited():
                return jsonify({'success': False, 'error': 'Too many requests'}), 429
            if not self._authorized_http():
                self._record_auth_failure()
                return jsonify({'success': False, 'error': 'Unauthorized'}), 401
            return f(*args, **kwargs)
        return wrapper

    def _setup_routes(self):
        """Setup Flask REST API routes"""
        
        @self.app.route('/')
        def index():
            """Serve main remote control page"""
            return render_template('index.html')
        
        @self.app.route('/api/status')
        @self._require_auth
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
                    'led_sequence': self.display_app.settings.led_sequence,
                    'clutch_display_mode': self.display_app.settings.clutch_display_mode
                }
            })
        
        @self.app.route('/api/screen/<int:screen_num>', methods=['POST'])
        @self._require_auth
        def change_screen(screen_num):
            """Change to specific screen"""
            if 0 <= screen_num < 8:
                self.display_app.change_screen(screen_num)
                # Notify all connected clients
                self.socketio.emit('screen_changed', {'screen': screen_num})
                return jsonify({'success': True, 'screen': screen_num})
            return jsonify({'success': False, 'error': 'Invalid screen number'}), 400
        
        @self.app.route('/api/screen/next', methods=['POST'])
        @self._require_auth
        def next_screen():
            """Go to next screen"""
            new_screen = (self.display_app.current_screen + 1) % 8
            self.display_app.change_screen(new_screen)
            self.socketio.emit('screen_changed', {'screen': new_screen})
            return jsonify({'success': True, 'screen': new_screen})
        
        @self.app.route('/api/screen/prev', methods=['POST'])
        @self._require_auth
        def prev_screen():
            """Go to previous screen"""
            new_screen = (self.display_app.current_screen - 1) % 8
            self.display_app.change_screen(new_screen)
            self.socketio.emit('screen_changed', {'screen': new_screen})
            return jsonify({'success': True, 'screen': new_screen})
        
        @self.app.route('/api/settings/update', methods=['POST'])
        @self._require_auth
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
                elif name == 'clutch_display_mode':
                    self.display_app.settings.clutch_display_mode = int(value)
                else:
                    return jsonify({'success': False, 'error': 'Unknown setting'}), 400
                
                # Sync to ESP32 if available
                if self.display_app.esp32_handler:
                    self.display_app._sync_settings_to_esp32()
                
                # Notify all clients
                self.socketio.emit('setting_changed', {name: value})
                return jsonify({'success': True, 'name': name, 'value': value})
                
            except Exception:
                logger.exception("Failed to update setting %r", name)
                return jsonify({'success': False, 'error': 'Internal error'}), 500
        
        @self.app.route('/api/wake', methods=['POST'])
        @self._require_auth
        def wake_display():
            """Wake display from sleep"""
            if self.display_app.sleeping:
                self.display_app.sleeping = False
                self.display_app.last_activity = time.time()
            return jsonify({'success': True})
        
        @self.app.route('/api/calibrate_imu', methods=['POST'])
        @self._require_auth
        def calibrate_imu():
            """Calibrate IMU gyroscope zero point"""
            try:
                # Send calibration command to ESP32
                if self.display_app.esp32_handler:
                    self.display_app.esp32_handler.send_calibrate_imu()
                    return jsonify({'success': True, 'message': 'Calibration command sent'})
                else:
                    return jsonify({'success': False, 'message': 'ESP32 not connected'}), 503
            except Exception:
                logger.exception("Failed to calibrate IMU")
                return jsonify({'success': False, 'message': 'Internal error'}), 500
    
    def _setup_socketio(self):
        """Setup WebSocket event handlers"""
        
        @self.socketio.on('connect')
        def handle_connect(auth=None):
            """Client connected - send current status (requires valid token when configured)"""
            token = ''
            if isinstance(auth, dict):
                token = auth.get('token', '')
            if self._token and not self._token_valid(token):
                return False
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
    
    def start(self, host=None, port=5000):
        """Start web server in background thread.

        Host selection is fail-closed:
          - MX5_WEB_HOST env var wins if set.
          - With a token (MX5_WEB_TOKEN) configured, bind 0.0.0.0 for LAN use.
          - Otherwise bind to loopback only (safe default).
        """
        if self._running:
            return

        if not host:
            host = os.environ.get('MX5_WEB_HOST', '').strip()

        if not host:
            if self._token:
                host = '0.0.0.0'
            else:
                host = '127.0.0.1'
                print("WARNING: MX5_WEB_TOKEN not set - web remote is localhost-only.")
                print("         Set MX5_WEB_TOKEN to enable phone access (see pi/start_display.sh).")

        if host not in ('127.0.0.1', 'localhost', '::1') and not self._token:
            raise RuntimeError(
                "Refusing to expose the web remote on %s without MX5_WEB_TOKEN. "
                "Set MX5_WEB_TOKEN to a secret PIN/token." % host
            )

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
