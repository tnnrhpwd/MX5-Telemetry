// MX5 Remote Control - Client-side JavaScript

let socket;
let currentScreen = 0;
const screenNames = [
    'Overview', 'RPM', 'TPMS', 'Engine', 
    'G-Force', 'Diagnostics', 'System', 'Settings'
];

// Initialize WebSocket connection
function initSocket() {
    socket = io();
    
    socket.on('connect', () => {
        console.log('Connected to MX5 display');
        updateConnectionStatus(true);
        socket.emit('request_status');
    });
    
    socket.on('disconnect', () => {
        console.log('Disconnected from MX5 display');
        updateConnectionStatus(false);
    });
    
    socket.on('status', (data) => {
        console.log('Status update:', data);
        updateUI(data);
    });
    
    socket.on('screen_changed', (data) => {
        console.log('Screen changed:', data);
        currentScreen = data.screen;
        updateCurrentScreen(data.screen);
    });
    
    socket.on('setting_changed', (data) => {
        console.log('Setting changed:', data);
        if ('demo_mode' in data) {
            document.getElementById('toggle-demo').checked = data.demo_mode;
        }
    });
}

// Update connection status indicator
function updateConnectionStatus(connected) {
    const statusEl = document.getElementById('connection-status');
    const statusText = document.getElementById('status-text');
    
    if (connected) {
        statusEl.classList.add('connected');
        statusText.textContent = 'Connected';
    } else {
        statusEl.classList.remove('connected');
        statusText.textContent = 'Disconnected';
    }
}

// Update UI with current status
function updateUI(data) {
    currentScreen = data.screen;
    updateCurrentScreen(data.screen);
    
    // Update all settings if provided
    if (data.settings) {
        updateSettingsUI(data.settings);
    }
}

// Update all settings UI elements
function updateSettingsUI(settings) {
    // Toggles
    if ('demo_mode' in settings) {
        document.getElementById('toggle-demo').checked = settings.demo_mode;
    }
    if ('use_mph' in settings) {
        document.getElementById('toggle-mph').checked = settings.use_mph;
    }
    
    // Sliders
    if ('brightness' in settings) {
        document.getElementById('brightness').value = settings.brightness;
        document.getElementById('brightness-value').textContent = settings.brightness;
    }
    if ('volume' in settings) {
        document.getElementById('volume').value = settings.volume;
        document.getElementById('volume-value').textContent = settings.volume;
    }
    if ('shift_rpm' in settings) {
        document.getElementById('shift-rpm').value = settings.shift_rpm;
        document.getElementById('shift-rpm-value').textContent = settings.shift_rpm;
    }
    if ('redline_rpm' in settings) {
        document.getElementById('redline-rpm').value = settings.redline_rpm;
        document.getElementById('redline-rpm-value').textContent = settings.redline_rpm;
    }
    if ('tire_low_psi' in settings) {
        document.getElementById('tire-psi').value = settings.tire_low_psi;
        document.getElementById('tire-psi-value').textContent = settings.tire_low_psi;
    }
    if ('tire_high_psi' in settings) {
        document.getElementById('tire-high-psi').value = settings.tire_high_psi;
        document.getElementById('tire-high-psi-value').textContent = settings.tire_high_psi;
    }
    if ('coolant_warn_f' in settings) {
        document.getElementById('coolant-warn').value = settings.coolant_warn_f;
        document.getElementById('coolant-warn-value').textContent = settings.coolant_warn_f;
    }
    if ('oil_warn_f' in settings) {
        document.getElementById('oil-warn').value = settings.oil_warn_f;
        document.getElementById('oil-warn-value').textContent = settings.oil_warn_f;
    }
    if ('led_sequence' in settings) {
        const ledSeqNames = ['', 'Center Out', 'Left to Right', 'Right to Left', 'Center In'];
        document.getElementById('led-seq').value = settings.led_sequence;
        document.getElementById('led-seq-value').textContent = ledSeqNames[settings.led_sequence] || 'Unknown';
    }
    if ('clutch_display_mode' in settings) {
        const clutchModeNames = ['Gear# (Colored)', "'C' for Clutch", "'S' for Shifting", "'-' for Unknown"];
        document.getElementById('clutch-mode').value = settings.clutch_display_mode;
        document.getElementById('clutch-mode-value').textContent = clutchModeNames[settings.clutch_display_mode] || 'Unknown';
    }
}

// Update current screen display and highlight active button
function updateCurrentScreen(screen) {
    document.getElementById('current-screen').textContent = screenNames[screen];
    
    // Highlight active screen button
    document.querySelectorAll('.btn-screen').forEach((btn, index) => {
        if (index === screen) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
}

// Navigation functions
function changeScreen(screen) {
    fetch(`/api/screen/${screen}`, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log(`Changed to screen ${screen}`);
                vibrate();
            }
        })
        .catch(err => console.error('Error changing screen:', err));
}

function nextScreen() {
    fetch('/api/screen/next', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log('Next screen');
                vibrate();
            }
        })
        .catch(err => console.error('Error:', err));
}

function prevScreen() {
    fetch('/api/screen/prev', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log('Previous screen');
                vibrate();
            }
        })
        .catch(err => console.error('Error:', err));
}

// Settings state and debouncing
let settingsDebounceTimers = {};

// Update slider display value and send to backend
function updateSlider(settingId) {
    const slider = document.getElementById(settingId);
    const valueDisplay = document.getElementById(`${settingId}-value`);
    const value = slider.value;
    
    // Update display immediately
    valueDisplay.textContent = value;
    
    // Debounce the API call (wait for user to stop moving slider)
    clearTimeout(settingsDebounceTimers[settingId]);
    settingsDebounceTimers[settingId] = setTimeout(() => {
        sendSettingUpdate(settingId, value);
    }, 300);
}

// Update select dropdown and send to backend
function updateSelect(settingId) {
    const select = document.getElementById(settingId);
    const valueDisplay = document.getElementById(`${settingId}-value`);
    const value = select.value;
    const text = select.options[select.selectedIndex].text;
    
    // Update display immediately
    valueDisplay.textContent = text;
    
    // Send immediately (no debounce needed for select)
    sendSettingUpdate(settingId, value);
}

// Send setting update to backend
function sendSettingUpdate(setting, value) {
    const settingMap = {
        'brightness': 'brightness',
        'volume': 'volume',
        'shift-rpm': 'shift_rpm',
        'redline-rpm': 'redline_rpm',
        'tire-psi': 'tire_low_psi',
        'tire-high-psi': 'tire_high_psi',
        'coolant-warn': 'coolant_warn',
        'oil-warn': 'oil_warn',
        'led-seq': 'led_sequence',
        'clutch-mode': 'clutch_display_mode'
    };
    
    const apiSetting = settingMap[setting] || setting;
    
    fetch('/api/settings/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            name: apiSetting,
            value: value 
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log(`${apiSetting} = ${value}`);
                vibrate();
            }
        })
        .catch(err => console.error('Error updating setting:', err));
}

// Toggle settings (checkboxes)
function toggleSetting(settingName) {
    let enabled;
    
    if (settingName === 'demo_mode') {
        enabled = document.getElementById('toggle-demo').checked;
    } else if (settingName === 'use_mph') {
        enabled = document.getElementById('toggle-mph').checked;
    }
    
    fetch('/api/settings/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            name: settingName,
            value: enabled ? '1' : '0'
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log(`${settingName} = ${enabled}`);
                vibrate();
            }
        })
        .catch(err => console.error('Error:', err));
}

// Haptic feedback (if supported)
function vibrate() {
    if ('vibrate' in navigator) {
        navigator.vibrate(50);
    }
}

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowLeft') {
        prevScreen();
    } else if (e.key === 'ArrowRight') {
        nextScreen();
    } else if (e.key >= '0' && e.key <= '7') {
        changeScreen(parseInt(e.key));
    }
});

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initSocket();
    
    // Prevent pull-to-refresh on mobile
    document.body.addEventListener('touchmove', (e) => {
        if (e.touches.length > 1) {
            e.preventDefault();
        }
    }, { passive: false });
});
