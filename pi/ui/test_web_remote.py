#!/usr/bin/env python3
"""
Test Web Remote Server - Local Development

Runs the web remote interface locally for testing without Pi hardware.
Simulates the display app with mock data.

Usage:
    python test_web_remote.py
    Then open: http://localhost:5000
"""

import sys
import os
import secrets

# Add parent directory to path to import web_server
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit

from roof_controller import RoofController, RoofControllerError
import time
import webbrowser
import threading

# Mock display app
class MockDisplayApp:
    def __init__(self):
        self.current_screen = 0
        self.screen_names = [
            'OVERVIEW', 'RPM_SPEED', 'TPMS', 'ENGINE',
            'GFORCE', 'DIAGNOSTICS', 'SYSTEM', 'SETTINGS'
        ]
        self.settings = MockSettings()
        self.sleeping = False
        self.swc_handler = MockSWCHandler()
    
    def change_screen(self, screen_index):
        """Change to specific screen"""
        if 0 <= screen_index < 8:
            self.current_screen = screen_index
            print(f"✓ Screen changed to {screen_index}: {self.screen_names[screen_index]}")
            return True
        return False

class MockSettings:
    def __init__(self):
        self.demo_mode = True
    
    def save_settings(self):
        print("✓ Settings saved")

class MockSWCHandler:
    def __init__(self):
        self.nav_locked = False

# Create Flask app
app = Flask(__name__,
           static_folder='static',
           template_folder='templates')
app.config['SECRET_KEY'] = secrets.token_hex(16)
socketio = SocketIO(app, cors_allowed_origins=[])

# Create mock display app
display_app = MockDisplayApp()

# Real roof controller when one is plugged in, so the preview shows live data.
roof = RoofController()

# Routes
@app.route('/')
def index():
    """Serve main remote control page"""
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    """Get current system status"""
    return jsonify({
        'screen': display_app.current_screen,
        'screen_name': display_app.screen_names[display_app.current_screen],
        'demo_mode': display_app.settings.demo_mode,
        'sleeping': display_app.sleeping,
        'nav_locked': display_app.swc_handler.nav_locked
    })

@app.route('/api/screen/<int:screen_num>', methods=['POST'])
def change_screen(screen_num):
    """Change to specific screen"""
    if display_app.change_screen(screen_num):
        # Notify all connected clients
        socketio.emit('screen_changed', {
            'screen': screen_num,
            'screen_name': display_app.screen_names[screen_num]
        })
        return jsonify({'success': True, 'screen': screen_num})
    return jsonify({'success': False, 'error': 'Invalid screen number'}), 400

@app.route('/api/screen/next', methods=['POST'])
def next_screen():
    """Go to next screen"""
    new_screen = (display_app.current_screen + 1) % 8
    display_app.change_screen(new_screen)
    socketio.emit('screen_changed', {
        'screen': new_screen,
        'screen_name': display_app.screen_names[new_screen]
    })
    return jsonify({'success': True, 'screen': new_screen})

@app.route('/api/screen/prev', methods=['POST'])
def prev_screen():
    """Go to previous screen"""
    new_screen = (display_app.current_screen - 1) % 8
    display_app.change_screen(new_screen)
    socketio.emit('screen_changed', {
        'screen': new_screen,
        'screen_name': display_app.screen_names[new_screen]
    })
    return jsonify({'success': True, 'screen': new_screen})

@app.route('/api/settings/demo', methods=['POST'])
def toggle_demo():
    """Toggle demo mode"""
    data = request.json
    enabled = data.get('enabled', not display_app.settings.demo_mode)
    display_app.settings.demo_mode = enabled
    display_app.settings.save_settings()
    
    # Notify all clients
    socketio.emit('setting_changed', {'demo_mode': enabled})
    return jsonify({'success': True, 'demo_mode': enabled})

@app.route('/api/wake', methods=['POST'])
def wake_display():
    """Wake display from sleep"""
    if display_app.sleeping:
        display_app.sleeping = False
    print("✓ Display woken")
    return jsonify({'success': True})

# -- roof controller (MX5things RCNC-2) ------------------------------------

def _roof_status_payload():
    try:
        info = roof.status()
    except RoofControllerError as e:
        return {'connected': False, 'released': roof.released, 'error': str(e)}
    info['connected'] = True
    return info


def _roof_apply(kind, value):
    if value is None:
        return jsonify({'success': False, 'error': 'Missing value'}), 400
    try:
        if kind == 'speed':
            roof.set_speed(value)
        elif kind == 'auto':
            roof.set_auto(value)
        else:
            roof.set_mode(value)
    except RoofControllerError as e:
        return jsonify({'success': False, 'error': str(e)}), 503
    payload = _roof_status_payload()
    socketio.emit('roof_changed', payload)
    return jsonify({'success': True, 'roof': payload})


@app.route('/api/roof/status')
def roof_status():
    return jsonify(_roof_status_payload())


@app.route('/api/roof/speed', methods=['POST'])
def roof_set_speed():
    return _roof_apply('speed', (request.get_json(silent=True) or {}).get('value'))


@app.route('/api/roof/auto', methods=['POST'])
def roof_set_auto():
    return _roof_apply('auto', (request.get_json(silent=True) or {}).get('value'))


@app.route('/api/roof/mode', methods=['POST'])
def roof_set_mode():
    return _roof_apply('mode', (request.get_json(silent=True) or {}).get('value'))


@app.route('/api/roof/connect', methods=['POST'])
def roof_connect():
    try:
        info = roof.connect()
    except RoofControllerError as e:
        return jsonify({'success': False, 'error': str(e)}), 503
    info['connected'] = True
    socketio.emit('roof_changed', info)
    return jsonify({'success': True, 'roof': info})


@app.route('/api/roof/disconnect', methods=['POST'])
def roof_disconnect():
    roof.disconnect()
    payload = _roof_status_payload()
    socketio.emit('roof_changed', payload)
    return jsonify({'success': True, 'roof': payload})

# WebSocket handlers
@socketio.on('connect')
def handle_connect():
    """Client connected - send current status"""
    print("🌐 Web client connected")
    emit('status', {
        'screen': display_app.current_screen,
        'screen_name': display_app.screen_names[display_app.current_screen],
        'demo_mode': display_app.settings.demo_mode
    })

@socketio.on('disconnect')
def handle_disconnect():
    """Client disconnected"""
    print("🌐 Web client disconnected")

@socketio.on('request_status')
def handle_status_request():
    """Client requesting status update"""
    emit('status', {
        'screen': display_app.current_screen,
        'screen_name': display_app.screen_names[display_app.current_screen],
        'demo_mode': display_app.settings.demo_mode
    })

def open_browser():
    """Open browser after short delay"""
    time.sleep(1.5)
    webbrowser.open('http://localhost:5000')

if __name__ == '__main__':
    print("=" * 60)
    print("🏎️  MX5 Web Remote - Test Server")
    print("=" * 60)
    print()
    print("Server starting at: http://localhost:5000")
    print()
    print("Test the web interface:")
    print("  • Navigate between screens")
    print("  • Toggle demo mode")
    print("  • See real-time sync")
    print()
    print("Press Ctrl+C to stop")
    print("=" * 60)
    print()
    
    # Open browser in background
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Start server
    socketio.run(app, host='localhost', port=5000, debug=False)
