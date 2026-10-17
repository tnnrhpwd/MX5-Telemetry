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

from link_service import LinkService, screen_index, screen_name

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
        # Every read and every command lives in LinkService, so this HTTP surface and the
        # Bluetooth link are two adapters over one implementation. self.roof is kept as
        # an alias because that is the name the controller used to be reachable under.
        self.link = LinkService(display_app)
        self.roof = self.link.roof

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
            return jsonify(self.link.status())
        
        @self.app.route('/api/screen/<int:screen_num>', methods=['POST'])
        @self._require_auth
        def change_screen(screen_num):
            """Change to specific screen"""
            payload, status = self.link.set_screen(screen_num)
            if payload.get('success'):
                # Notify all connected clients
                self.socketio.emit('screen_changed', {'screen': payload['screen']})
            return jsonify(payload), status
        
        @self.app.route('/api/screen/next', methods=['POST'])
        @self._require_auth
        def next_screen():
            """Go to next screen"""
            payload, status = self.link.next_screen()
            self.socketio.emit('screen_changed', {'screen': payload['screen']})
            return jsonify(payload), status
        
        @self.app.route('/api/screen/prev', methods=['POST'])
        @self._require_auth
        def prev_screen():
            """Go to previous screen"""
            payload, status = self.link.prev_screen()
            self.socketio.emit('screen_changed', {'screen': payload['screen']})
            return jsonify(payload), status
        
        @self.app.route('/api/settings/update', methods=['POST'])
        @self._require_auth
        def update_setting():
            """Update any setting"""
            data = request.json
            payload, status = self.link.update_setting(
                data.get('name'), data.get('value'))
            if payload.get('success'):
                # Notify all clients
                self.socketio.emit('setting_changed',
                                   {payload['name']: payload['value']})
            return jsonify(payload), status
        
        @self.app.route('/api/wake', methods=['POST'])
        @self._require_auth
        def wake_display():
            """Wake display from sleep"""
            payload, status = self.link.wake()
            return jsonify(payload), status
        
        @self.app.route('/api/calibrate_imu', methods=['POST'])
        @self._require_auth
        def calibrate_imu():
            """Calibrate IMU gyroscope zero point"""
            payload, status = self.link.calibrate_imu()
            return jsonify(payload), status

        @self.app.route('/api/telemetry')
        @self._require_auth
        def get_telemetry():
            """Full live telemetry snapshot.

            The web page only ever needed the current screen and the settings, so the
            live values went to the ESP32 over serial and were never exposed over HTTP.
            The car app replaces that display, so it needs everything the serial link
            carries. Built by LinkService.telemetry(), which the Bluetooth link shares.
            """
            return jsonify(self.link.telemetry())

        # -- roof controller (MX5things RCNC-2) -------------------------

        @self.app.route('/api/roof/status')
        @self._require_auth
        def roof_status():
            """Current roof controller settings (or connected=False)."""
            return jsonify(self.link.roof_status())

        @self.app.route('/api/roof/speed', methods=['POST'])
        @self._require_auth
        def roof_set_speed():
            """Set the roof speed limit (mph)."""
            return self._roof_apply('speed')

        @self.app.route('/api/roof/auto', methods=['POST'])
        @self._require_auth
        def roof_set_auto():
            """Turn Auto (lower on latch release) on or off."""
            return self._roof_apply('auto')

        @self.app.route('/api/roof/mode', methods=['POST'])
        @self._require_auth
        def roof_set_mode():
            """Set 0=Valet, 1=One Touch, 2=OEM."""
            return self._roof_apply('mode')

        @self.app.route('/api/roof/connect', methods=['POST'])
        @self._require_auth
        def roof_connect():
            """Claim the roof controller and report its state."""
            return self._roof_link(self.link.roof_connect)

        @self.app.route('/api/roof/disconnect', methods=['POST'])
        @self._require_auth
        def roof_disconnect():
            """Hand the module back to the car so the roof keeps working."""
            return self._roof_link(self.link.roof_disconnect)

    def _roof_link(self, action):
        """Run a claim or release and push the resulting state to the web clients."""
        payload, status = action()
        if payload.get('success'):
            self.socketio.emit('roof_changed', payload['roof'])
        return jsonify(payload), status

    def _roof_apply(self, kind):
        """Apply one roof setting from an HTTP body, then notify the web clients."""
        value = (request.get_json(silent=True) or {}).get('value')
        payload, status = self.link.roof_set(kind, value)
        if payload.get('success'):
            self.socketio.emit('roof_changed', payload['roof'])
        return jsonify(payload), status
    
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
                'screen': screen_index(self.display_app),
                'screen_name': screen_name(self.display_app),
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
                'screen': screen_index(self.display_app),
                'screen_name': screen_name(self.display_app),
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
