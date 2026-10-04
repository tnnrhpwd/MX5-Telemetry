#!/usr/bin/env python3
"""
CC1101 Live RSSI Readout
========================
Reads the Arduino Nano (CC1101 scan sketch) on a serial port and serves a live
chart in the browser. Uses only the Python standard library + pyserial.

Usage:
    python live_readout.py [PORT]

Defaults to COM3 on Windows. Open http://127.0.0.1:8765/ (opened automatically).
"""
import json
import os
import re
import sys
import threading
import time
import webbrowser
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM3"
BAUD = 115200
HTTP_PORT = 8765

# Regexes for the two line shapes the sketch emits:
#   sweep:    F=300.0 MHz   RSSI=-44 dBm
#   monitor:  315.000 MHz   RSSI=-76 dBm
RSSI_RE = re.compile(r"RSSI=(-?\d+)")
FREQ_SCAN_RE = re.compile(r"F=([\d.]+)")
FREQ_MON_RE = re.compile(r"^([\d.]+)\s*MHz")

lock = threading.Lock()
samples = deque(maxlen=600)          # (t, rssi, freq)
latest = {"rssi": None, "freq": None, "t": None}
port_error = None
selected_freq = 315.0
selected_mod = 0          # 0 = 2-FSK (TPMS), 2 = ASK/OOK (key fobs)
tx_on = False             # second-module test carrier state
sweep_mode = False        # continuous frequency sweep (spectrum view)
ser_handle = None
raw_captures = 0
CAPTURE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "capture_live.txt")
START_TIME = time.time()

# --- signal-event detection ----------------------------------------------
# Detects bursts of RSSI well above the (slowly adapting) noise floor and
# records them as "transmissions". No name is assigned here: RSSI is only
# loudness, so these are labelled by time/peak/duration/frequency until we
# decode the bitstream.
events = deque(maxlen=50)
_floor = None
_in_event = False
_ev_start = 0.0
_ev_peak = -200
_ev_freq = None
_below_count = 0
_ev_above = 0
EVENT_RISE_DB = 12.0
EVENT_HYST_DB = 6.0
EVENT_MIN_S = 0.1
EVENT_MIN_ABOVE = 3


def _update_events(rssi, freq, t):
    global _floor, _in_event, _ev_start, _ev_peak, _ev_freq, _below_count, _ev_above
    if _floor is None:
        _floor = float(rssi)
    else:
        _floor = _floor * 0.98 + rssi * 0.02

    if not _in_event:
        if rssi > _floor + EVENT_RISE_DB:
            _in_event = True
            _ev_start = t
            _ev_peak = rssi
            _ev_freq = freq
            _below_count = 0
            _ev_above = 1
    else:
        if rssi > _ev_peak:
            _ev_peak = rssi
        if rssi > _floor + EVENT_RISE_DB:
            _ev_above += 1
        if rssi < _floor + EVENT_HYST_DB:
            _below_count += 1
            if _below_count >= 3:
                duration = t - _ev_start
                if duration >= EVENT_MIN_S and _ev_above >= EVENT_MIN_ABOVE:
                    clock = time.strftime(
                        "%H:%M:%S", time.localtime(START_TIME + _ev_start))
                    etype = "signal" if duration >= 0.25 else "noise"
                    events.append({
                        "t": round(_ev_start, 2),
                        "clock": clock,
                        "peak": _ev_peak,
                        "duration": round(duration, 2),
                        "freq": _ev_freq,
                        "type": etype,
                    })
                _in_event = False
        else:
            _below_count = 0


def handle_line(line):
    global port_error, raw_captures
    line = line.decode("utf-8", "ignore").strip()
    if line.startswith("CAP "):
        try:
            with open(CAPTURE_PATH, "a", encoding="utf-8") as f:
                f.write(line + "\n")
            raw_captures += 1
        except OSError:
            pass
        return
    if "F=" in line:
        # Skip the boot frequency sweep lines; only keep the 315 MHz monitor.
        return
    m = RSSI_RE.search(line)
    if not m:
        return
    rssi = int(m.group(1))
    freq = None
    fm = FREQ_SCAN_RE.search(line) or FREQ_MON_RE.search(line)
    if fm:
        try:
            freq = float(fm.group(1))
        except ValueError:
            freq = None
    t = time.time() - START_TIME
    with lock:
        samples.append((t, rssi, freq))
        latest.update({"rssi": rssi, "freq": freq, "t": t})
        _update_events(rssi, freq, t)


def set_frequency(mhz):
    """Tell the Arduino to retune, and remember the selection."""
    global selected_freq
    selected_freq = float(mhz)
    with lock:
        s = ser_handle
    if s is not None:
        try:
            s.write(("FREQ %.3f\n" % selected_freq).encode("ascii"))
            return True
        except Exception:
            return False
    return False


def clear_history():
    """Clear accumulated samples, events, and raw captures; re-baseline."""
    global _floor, _in_event, raw_captures
    with lock:
        samples.clear()
        events.clear()
        raw_captures = 0
    _floor = None
    _in_event = False
    try:
        open(CAPTURE_PATH, "w", encoding="utf-8").close()
    except OSError:
        pass


def set_modulation(mod):
    """Tell the Arduino to switch modulation (0 = FSK, 2 = ASK/OOK)."""
    global selected_mod
    selected_mod = int(mod)
    with lock:
        s = ser_handle
    if s is not None:
        try:
            s.write(("MOD %d\n" % selected_mod).encode("ascii"))
            return True
        except Exception:
            return False
    return False


def set_tx(on):
    """Turn the second-module test carrier on or off."""
    global tx_on
    tx_on = bool(on)
    with lock:
        s = ser_handle
    if s is not None:
        try:
            s.write(("TXON\n" if tx_on else "TXOFF\n").encode("ascii"))
            return True
        except Exception:
            return False
    return False


def set_sweep(on):
    """Turn continuous frequency sweeping on or off."""
    global sweep_mode
    sweep_mode = bool(on)
    with lock:
        s = ser_handle
    if s is not None:
        try:
            s.write(("SWEEPON\n" if sweep_mode else "SWEEPOFF\n").encode("ascii"))
            return True
        except Exception:
            return False
    return False


def reader():
    global port_error, ser_handle
    ser = None
    while True:
        try:
            ser = serial.Serial(PORT, BAUD, timeout=1)
            port_error = None
            with lock:
                ser_handle = ser
            # Let the Arduino finish its boot sweep, then assert band and modulation.
            time.sleep(1.5)
            set_frequency(selected_freq)
            set_modulation(selected_mod)
            set_tx(tx_on)
            set_sweep(sweep_mode)
            while True:
                line = ser.readline()
                if line:
                    handle_line(line)
        except Exception as exc:          # noqa: BLE001
            port_error = str(exc)
        finally:
            with lock:
                ser_handle = None
            if ser is not None:
                try:
                    ser.close()
                except Exception:
                    pass
                ser = None
            time.sleep(2)


HTML = r"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CC1101 Live RSSI</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0d1117;
         color: #e6edf3; height: 100vh; display: flex; flex-direction: column; }
  header { padding: 14px 20px; border-bottom: 1px solid #21262d;
           display: flex; align-items: baseline; gap: 18px; }
  h1 { font-size: 16px; font-weight: 600; letter-spacing: .3px; }
  #freq { color: #8b949e; font-variant-numeric: tabular-nums; }
  #status { margin-left: auto; font-size: 12px; padding: 3px 10px;
            border-radius: 999px; background: #1f6feb33; color: #58a6ff; }
  #status.err { background: #da363333; color: #f85149; }
  main { flex: 1; display: flex; flex-direction: column; align-items: center;
         justify-content: center; gap: 10px; padding: 16px 20px; }
  #rssi-wrap { text-align: center; }
  #rssi { font-size: 76px; font-weight: 700; font-variant-numeric: tabular-nums;
          line-height: 1; }
  #rssi-label { color: #8b949e; font-size: 13px; margin-top: 6px; }
  #chart-box { width: 100%; max-width: 1000px; flex: 1; min-height: 220px; }
  canvas { width: 100%; height: 100%; display: block; }
  footer { padding: 10px 20px; color: #8b949e; font-size: 12px;
           border-top: 1px solid #21262d; display: flex; gap: 16px; }
  .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%;
         margin-right: 5px; }
</style>
</head>
<body>
<header>
  <h1>CC1101 Live RSSI</h1>
  <span id="freq">freq: --</span>
  <span id="status">connecting&#8230;</span>
</header>
<main>
  <div id="rssi-wrap">
    <div id="rssi">---</div>
    <div id="rssi-label">dBm</div>
  </div>
  <div id="chart-box"><canvas id="c"></canvas></div>
</main>
<footer>
  <span><span class="dot" style="background:#f85149"></span>strong &gt; -60</span>
  <span><span class="dot" style="background:#d29922"></span>elevated -85..-60</span>
  <span><span class="dot" style="background:#3fb950"></span>quiet &lt; -85</span>
</footer>
<script>
var c = document.getElementById('c');
var ctx = c.getContext('2d');
var points = [];
var WINDOW = 20;      // seconds shown
var YMIN = -125, YMAX = -25;
var THRESH = -85;

function colorFor(r) {
  if (r === null || r === undefined) return '#8b949e';
  if (r > -60) return '#f85149';
  if (r > -85) return '#d29922';
  return '#3fb950';
}

function resize() {
  var box = document.getElementById('chart-box');
  var dpr = window.devicePixelRatio || 1;
  c.width = box.clientWidth * dpr;
  c.height = box.clientHeight * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}
window.addEventListener('resize', resize);
resize();

function draw() {
  var dpr = window.devicePixelRatio || 1;
  var w = c.width / dpr, h = c.height / dpr;
  ctx.clearRect(0, 0, w, h);

  ctx.font = '11px Segoe UI';
  for (var y = YMIN; y <= YMAX; y += 10) {
    var py = ((YMAX - y) / (YMAX - YMIN)) * h;
    ctx.strokeStyle = '#21262d';
    ctx.beginPath(); ctx.moveTo(0, py); ctx.lineTo(w, py); ctx.stroke();
    ctx.fillStyle = '#8b949e';
    ctx.fillText(String(y), 6, py - 3);
  }

  var ty = ((YMAX - THRESH) / (YMAX - YMIN)) * h;
  ctx.strokeStyle = '#d29922';
  ctx.setLineDash([5, 4]);
  ctx.beginPath(); ctx.moveTo(0, ty); ctx.lineTo(w, ty); ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = '#d29922';
  ctx.fillText('-85', w - 32, ty - 4);

  if (points.length < 2) return;
  var tmax = points[points.length - 1][0];
  var tmin = tmax - WINDOW;
  function xOf(t) { return ((t - tmin) / WINDOW) * w; }
  function yOf(r) { return ((YMAX - r) / (YMAX - YMIN)) * h; }

  ctx.strokeStyle = '#58a6ff';
  ctx.lineWidth = 2;
  ctx.beginPath();
  var started = false;
  for (var i = 0; i < points.length; i++) {
    var t = points[i][0], r = points[i][1];
    if (t < tmin) continue;
    var x = xOf(t), y = yOf(r);
    if (!started) { ctx.moveTo(x, y); started = true; }
    else ctx.lineTo(x, y);
  }
  ctx.stroke();
}

function render() {
  var el = document.getElementById('rssi');
  if (points.length) {
    var last = points[points.length - 1];
    var r = last[1], f = last[2];
    el.textContent = String(r);
    el.style.color = colorFor(r);
    document.getElementById('freq').textContent =
      'freq: ' + (f !== null && f !== undefined ? f.toFixed(1) + ' MHz' : '--');
  }
  draw();
}

function poll() {
  fetch('/data')
    .then(function (res) { return res.json(); })
    .then(function (d) {
      points = d.points;
      var st = document.getElementById('status');
      if (d.port_error) { st.textContent = 'port error'; st.className = 'err'; }
      else { st.textContent = 'live'; st.className = ''; }
      render();
    })
    .catch(function () {
      document.getElementById('status').textContent = 'connecting&#8230;';
    });
  setTimeout(poll, 100);
}
poll();
</script>
</body>
</html>
"""

HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "readout.html")


def load_html():
    """Serve the styled dashboard; fall back to the embedded page if missing."""
    try:
        with open(HTML_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return HTML


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            body = load_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/data":
            with lock:
                pts = [list(p) for p in samples]
                cur = dict(latest)
                evs = [dict(e) for e in events]
            body = json.dumps({"points": pts, "latest": cur, "events": evs,
                               "selected_freq": selected_freq,
                               "selected_mod": selected_mod,
                               "tx_on": tx_on,
                               "sweep_mode": sweep_mode,
                               "raw_captures": raw_captures,
                               "port_error": port_error}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/clear":
            clear_history()
            body = b'{"ok": true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/mod":
            length = int(self.headers.get("Content-Length", 0) or 0)
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8", "ignore"))
                mod = int(data.get("mod"))
            except Exception:
                self.send_response(400)
                self.end_headers()
                return
            ok = set_modulation(mod)
            body = json.dumps({"ok": ok, "mod": selected_mod}).encode("utf-8")
            self.send_response(200 if ok else 503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/tx":
            length = int(self.headers.get("Content-Length", 0) or 0)
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8", "ignore"))
                on = bool(data.get("on"))
            except Exception:
                self.send_response(400)
                self.end_headers()
                return
            ok = set_tx(on)
            body = json.dumps({"ok": ok, "tx_on": tx_on}).encode("utf-8")
            self.send_response(200 if ok else 503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/sweep":
            length = int(self.headers.get("Content-Length", 0) or 0)
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8", "ignore"))
                on = bool(data.get("on"))
            except Exception:
                self.send_response(400)
                self.end_headers()
                return
            ok = set_sweep(on)
            body = json.dumps({"ok": ok, "sweep_mode": sweep_mode}).encode("utf-8")
            self.send_response(200 if ok else 503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        length = int(self.headers.get("Content-Length", 0) or 0)
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8", "ignore"))
            mhz = float(data.get("mhz"))
        except Exception:
            self.send_response(400)
            self.end_headers()
            return
        ok = set_frequency(mhz)
        body = json.dumps({"ok": ok, "mhz": selected_freq}).encode("utf-8")
        self.send_response(200 if ok else 503)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # silence request logs
        pass


def main():
    threading.Thread(target=reader, daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", HTTP_PORT), Handler)
    url = "http://127.0.0.1:%d/" % HTTP_PORT
    print("CC1101 live readout serving at %s (serial: %s)" % (url, PORT))

    def open_browser():
        time.sleep(1.0)
        webbrowser.open(url)

    threading.Thread(target=open_browser, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
