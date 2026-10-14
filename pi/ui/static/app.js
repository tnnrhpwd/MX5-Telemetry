// MX5 Remote - client.
// This is a service page, so motion here means "state changed" and nothing else.
// The theme class is painted before first frame by the inline script in
// index.html; initTheme() below is the authority and owns the repaint.

const TOKEN = new URLSearchParams(window.location.search).get('token')
    || localStorage.getItem('mx5_token') || '';
if (TOKEN) {
    localStorage.setItem('mx5_token', TOKEN);
}

const AUTH_HEADERS = {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + TOKEN
};

const SCREENS = ['Overview', 'RPM', 'TPMS', 'Engine', 'G-Force', 'Diagnostics', 'System', 'Settings'];

let socket = null;
let currentScreen = 0;
let roofEditing = false;
let roofSpeedTimer = null;

/* ------------------------------------------------------------------ theme */

function applyTheme(mode) {
    document.body.classList.toggle('light-theme', mode === 'light');
    document.body.classList.toggle('dark-theme', mode !== 'light');
    const btn = document.getElementById('btn-theme');
    if (btn) {
        btn.textContent = mode === 'light' ? 'Dark' : 'Light';
    }
    try {
        localStorage.setItem('mx5_theme', mode);
    } catch (e) {
        /* private mode; the choice simply will not persist */
    }
}

function initTheme() {
    let mode = null;
    try {
        mode = localStorage.getItem('mx5_theme');
    } catch (e) {
        /* ignored */
    }
    if (!mode) {
        mode = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    applyTheme(mode);

    const btn = document.getElementById('btn-theme');
    if (btn) {
        btn.addEventListener('click', () => {
            applyTheme(document.body.classList.contains('light-theme') ? 'dark' : 'light');
        });
    }
}

/* --------------------------------------------------------------- schemes */

/* A scheme is two hues; everything else is derived from them in style.css.
   Keep this list in step with the "body[data-scheme='...']" blocks there.
   Aurora is the default pair, so it is what "nothing chosen" already looks
   like, and it is the dot that lights up on a first visit. */
const SCHEMES = [
    { id: 'aurora', name: 'Aurora', a: '#00c1c1', b: '#ff379b' },
    { id: 'crimson', name: 'Crimson', a: '#dc2626', b: '#f472b6' },
    { id: 'emerald', name: 'Emerald', a: '#10b981', b: '#06b6d4' },
    { id: 'sakura', name: 'Sakura', a: '#ec4899', b: '#a78bfa' },
    { id: 'midnight', name: 'Midnight', a: '#3b82f6', b: '#8b5cf6' },
    { id: 'sunset', name: 'Sunset', a: '#f97316', b: '#ec4899' },
    { id: 'ocean', name: 'Ocean', a: '#06b6d4', b: '#3b82f6' },
    { id: 'cyberpunk', name: 'Cyberpunk', a: '#f0e030', b: '#e040fb' },
    { id: 'monokai', name: 'Monokai', a: '#a6e22e', b: '#66d9ef' },
    { id: 'usa', name: 'USA', a: '#b22234', b: '#3c3b6e' },
    { id: 'forest', name: 'Forest', a: '#4d8c57', b: '#65a30d' },
    { id: 'neutral', name: 'Neutral', a: '#808080', b: '#808080' }
];

let currentScheme = 'aurora';

function applyScheme(id) {
    currentScheme = id;
    document.body.setAttribute('data-scheme', id);
    try {
        localStorage.setItem('mx5_scheme', id);
    } catch (e) {
        /* private mode; the choice simply will not persist */
    }
    document.querySelectorAll('.mx-swatch').forEach((b) => {
        const on = b.dataset.scheme === id;
        b.classList.toggle('is-active', on);
        b.setAttribute('aria-checked', on ? 'true' : 'false');
    });
}

function initScheme() {
    const host = document.getElementById('scheme-picker');
    if (!host) return;

    host.innerHTML = '';
    SCHEMES.forEach((s) => {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'mx-swatch';
        b.dataset.scheme = s.id;
        b.title = s.name;
        b.setAttribute('role', 'radio');
        b.setAttribute('aria-label', s.name);
        b.setAttribute('aria-checked', 'false');
        b.style.background = 'linear-gradient(135deg, ' + s.a + ', ' + s.b + ')';
        b.addEventListener('click', () => applyScheme(s.id));
        host.appendChild(b);
    });

    let stored = null;
    try {
        stored = localStorage.getItem('mx5_scheme');
    } catch (e) {
        /* ignored */
    }
    applyScheme(SCHEMES.some((s) => s.id === stored) ? stored : 'aurora');
}

/* --------------------------------------------------------------- sockets */

function initSocket() {
    socket = io({ auth: { token: TOKEN } });

    socket.on('connect', () => {
        setLinkState('live', 'Linked');
        socket.emit('request_status');
    });

    socket.on('disconnect', () => setLinkState('down', 'Offline'));

    socket.on('status', (data) => {
        if (typeof data.screen === 'number') {
            updateCurrentScreen(data.screen);
        }
        if ('demo_mode' in data) {
            const t = document.getElementById('toggle-demo');
            if (t) t.checked = !!data.demo_mode;
        }
    });

    socket.on('screen_changed', (data) => {
        if (typeof data.screen === 'number') {
            updateCurrentScreen(data.screen);
        }
    });

    socket.on('setting_changed', (data) => {
        if ('demo_mode' in data) {
            const t = document.getElementById('toggle-demo');
            if (t) t.checked = !!data.demo_mode;
        }
    });

    socket.on('roof_changed', (data) => renderRoof(data));
}

function setLinkState(state, text) {
    const el = document.getElementById('link-state');
    if (!el) return;
    el.classList.toggle('is-live', state === 'live');
    el.classList.toggle('is-down', state === 'down');
    const label = document.getElementById('link-state-text');
    if (label) label.textContent = text;
}

/* ---------------------------------------------------------------- screens */

function buildScreens() {
    const list = document.getElementById('screen-list');
    if (!list) return;
    list.innerHTML = '';
    SCREENS.forEach((name, i) => {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'mx-chip';
        b.dataset.screen = String(i);
        b.textContent = name;
        b.addEventListener('click', () => changeScreen(i));
        list.appendChild(b);
    });
    updateCurrentScreen(0);
}

function updateCurrentScreen(screen) {
    currentScreen = screen;
    const title = document.getElementById('display-title');
    if (title) title.textContent = SCREENS[screen] || 'Unknown';
    document.querySelectorAll('#screen-list .mx-chip').forEach((b) => {
        b.classList.toggle('is-active', Number(b.dataset.screen) === screen);
    });
}

function changeScreen(screen) {
    fetch('/api/screen/' + screen, { method: 'POST', headers: AUTH_HEADERS })
        .then((r) => r.json())
        .then((d) => {
            if (d.success) {
                updateCurrentScreen(screen);
                vibrate();
            }
        })
        .catch((err) => console.error('Screen change failed:', err));
}

function stepScreen(delta) {
    const url = delta > 0 ? '/api/screen/next' : '/api/screen/prev';
    fetch(url, { method: 'POST', headers: AUTH_HEADERS })
        .then((r) => r.json())
        .then((d) => {
            if (d.success) {
                updateCurrentScreen(d.screen);
                vibrate();
            }
        })
        .catch((err) => console.error('Screen step failed:', err));
}

/* --------------------------------------------------------------- settings */

const SETTING_IDS = {
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

const LED_NAMES = ['', 'Center out', 'Left to right', 'Right to left', 'Center in'];
const CLUTCH_NAMES = ['Gear number, coloured', 'C for clutch', 'S for shifting', 'Dash for unknown'];

const setters = {};

function initSettings() {
    document.querySelectorAll('.mx-slider:not(#roof-speed)').forEach((el) => {
        setters[el.id] = debounce((v) => postSetting(SETTING_IDS[el.id] || el.id, v), 300);
        el.addEventListener('input', () => {
            const out = document.getElementById(el.id + '-value');
            if (out) out.textContent = el.value;
            setters[el.id](el.value);
        });
    });

    ['led-seq', 'clutch-mode'].forEach((id) => {
        const el = document.getElementById(id);
        if (!el) return;
        el.addEventListener('change', () => {
            const out = document.getElementById(id + '-value');
            const names = id === 'led-seq' ? LED_NAMES : CLUTCH_NAMES;
            if (out) out.textContent = names[Number(el.value)] || el.value;
            postSetting(SETTING_IDS[id], el.value);
        });
    });

    [['toggle-demo', 'demo_mode'], ['toggle-mph', 'use_mph']].forEach(([id, name]) => {
        const el = document.getElementById(id);
        if (!el) return;
        el.addEventListener('change', () => postSetting(name, el.checked ? 1 : 0));
    });

    const cal = document.getElementById('btn-calibrate');
    if (cal) {
        cal.addEventListener('click', () => {
            fetch('/api/calibrate_imu', { method: 'POST', headers: AUTH_HEADERS })
                .then((r) => r.json())
                .then((d) => {
                    if (d.success) {
                        showToast('G-force zero set', 'success');
                        vibrate();
                    } else {
                        showToast(d.message || 'Calibration failed', 'error');
                    }
                })
                .catch(() => showToast('Calibration failed', 'error'));
        });
    }
}

function postSetting(name, value) {
    if (!name) return;
    fetch('/api/settings/update', {
        method: 'POST',
        headers: AUTH_HEADERS,
        body: JSON.stringify({ name: name, value: value })
    })
        .then((r) => r.json())
        .then((d) => {
            if (!d.success) {
                showToast(d.error || 'Setting rejected', 'error');
            }
        })
        .catch((err) => console.error('Setting update failed:', err));
}

/* ------------------------------------------------------------ roof panel */

function initRoof() {
    const slider = document.getElementById('roof-speed');
    const auto = document.getElementById('roof-auto');
    if (!slider || !auto) return;

    slider.addEventListener('input', () => {
        const out = document.getElementById('roof-speed-value');
        if (out) out.textContent = slider.value;
        roofEditing = true;
        clearTimeout(roofSpeedTimer);
        roofSpeedTimer = setTimeout(() => {
            roofEditing = false;
            postRoof('/api/roof/speed', Number(slider.value),
                'Speed limit set to ' + slider.value + ' mph');
        }, 400);
    });

    auto.addEventListener('change', () => {
        postRoof('/api/roof/auto', auto.checked ? 1 : 0,
            auto.checked ? 'Auto enabled' : 'Auto disabled');
    });

    document.querySelectorAll('#roof-modes .mx-chip').forEach((btn) => {
        btn.addEventListener('click', () => {
            postRoof('/api/roof/mode', Number(btn.dataset.mode),
                'Mode ' + btn.textContent.trim());
        });
    });

    const refresh = document.getElementById('roof-refresh');
    if (refresh) refresh.addEventListener('click', () => loadRoofStatus());

    loadRoofStatus();
}

function loadRoofStatus() {
    fetch('/api/roof/status', { headers: AUTH_HEADERS })
        .then((r) => r.json())
        .then((data) => renderRoof(data))
        .catch((err) => {
            console.error('Roof status failed:', err);
            renderRoof({ connected: false, error: 'Could not reach the server.' });
        });
}

function renderRoof(data) {
    const state = document.getElementById('roof-state');
    const controls = document.getElementById('roof-controls');
    const errEl = document.getElementById('roof-error');
    if (!state || !controls) return;

    state.classList.remove('is-live', 'is-down');

    if (data && data.connected) {
        state.classList.add('is-live');
        document.getElementById('roof-state-text').textContent = 'Connected';
        controls.classList.remove('mx-hidden');
        if (errEl) errEl.textContent = '';

        document.getElementById('roof-version').textContent = data.version || '\u2013';
        document.getElementById('roof-port').textContent = data.port || '\u2013';

        if (data.speed_limit !== null && data.speed_limit !== undefined && !roofEditing) {
            document.getElementById('roof-speed').value = data.speed_limit;
            document.getElementById('roof-speed-value').textContent = data.speed_limit;
        }

        document.getElementById('roof-mode-value').textContent = data.mode_name || '\u2013';
        document.querySelectorAll('#roof-modes .mx-chip').forEach((btn) => {
            btn.classList.toggle('is-active', Number(btn.dataset.mode) === data.mode);
        });

        const auto = document.getElementById('roof-auto');
        const want = data.auto === 1;
        if (auto.checked !== want) auto.checked = want;
    } else {
        state.classList.add('is-down');
        document.getElementById('roof-state-text').textContent = 'Not connected';
        controls.classList.add('mx-hidden');
        if (errEl) errEl.textContent = (data && data.error) ? data.error : 'Roof controller not found.';
    }
}

function postRoof(url, value, successMsg) {
    fetch(url, {
        method: 'POST',
        headers: AUTH_HEADERS,
        body: JSON.stringify({ value: value })
    })
        .then((r) => r.json())
        .then((data) => {
            if (data.success) {
                renderRoof(data.roof);
                if (successMsg) showToast(successMsg, 'success');
                vibrate();
            } else {
                showToast(data.error || 'Rejected', 'error');
                loadRoofStatus();
            }
        })
        .catch((err) => {
            console.error('Roof update failed:', err);
            showToast('Roof controller error', 'error');
            loadRoofStatus();
        });
}

/* ---------------------------------------------------------------- helpers */

let toastTimer = null;

function showToast(message, type) {
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.textContent = message;
    toast.className = 'mx-toast is-show' + (type === 'error' ? ' is-bad' : ' is-ok');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toast.className = 'mx-toast'; }, 2600);
}

function vibrate() {
    if ('vibrate' in navigator) navigator.vibrate(40);
}

function debounce(fn, wait) {
    let t = null;
    return function () {
        const args = arguments;
        clearTimeout(t);
        t = setTimeout(() => fn.apply(null, args), wait);
    };
}

/* ------------------------------------------------------------------- boot */

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initScheme();
    buildScreens();
    initSocket();
    initSettings();
    initRoof();

    document.getElementById('btn-prev').addEventListener('click', () => stepScreen(-1));
    document.getElementById('btn-next').addEventListener('click', () => stepScreen(1));

    document.addEventListener('keydown', (e) => {
        const tag = (e.target.tagName || '').toLowerCase();
        if (tag === 'input' || tag === 'select' || tag === 'textarea') return;
        if (e.key === 'ArrowLeft') {
            stepScreen(-1);
        } else if (e.key === 'ArrowRight') {
            stepScreen(1);
        }
    });

    document.body.addEventListener('touchmove', (e) => {
        if (e.touches.length > 1) e.preventDefault();
    }, { passive: false });
});
