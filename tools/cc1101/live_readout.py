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
import math
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
selected_mod = 2          # 0 = 2-FSK (TPMS), 2 = ASK/OOK (key fobs) — fobs are OOK
# RX data rate in bits/s. This gates the SHORTEST pulse the slicer can
# reproduce: this fob's pulses run down to ~26-56 us, but 10 kbps means one bit
# is 100 us, so they come out smeared. Raise this when captures look mangled;
# 38400 is the highest sensible value inside the ~101 kHz channel bandwidth.
selected_drate = 10000
tx_on = False             # second-module test carrier state
sweep_mode = False        # continuous frequency sweep (spectrum view)
scan_data = {}            # spectrum: {freq_mhz: gdo0_edge_count}
scan_history = deque(maxlen=1200)   # [(t, freq, edges), ...] for the time chart
scan_active = False
record_active = False
HERE = os.path.dirname(os.path.abspath(__file__))
CAPTURES_DIR = os.path.join(HERE, "captures")      # runtime output lives here
try:
    os.makedirs(CAPTURES_DIR, exist_ok=True)
except OSError:
    pass
RECORD_PATH = os.path.join(CAPTURES_DIR, "record_log.csv")
ser_handle = None
raw_captures = 0
last_decode = None        # latest decoded transmission: {"hex": ..., "bit_us": ...}
fobburst_at = 0.0         # time.time() when the last Fob Burst was triggered
CAPTURE_PATH = os.path.join(CAPTURES_DIR, "capture_live.txt")
START_TIME = time.time()
IDLE_RUN = 60             # GDO0 runs longer than this are idle gaps between repeats

# --- recording ------------------------------------------------------------
# The record file is kept OPEN and written WITHOUT holding `lock`. It used to
# do an open/write/close per reading while holding the lock, so every reading
# blocked /data on disk I/O: the browser polls /data every 100 ms, so the whole
# UI stalled for as long as the recording was on. Rows are flushed every few
# lines, and Clear (not the Record button) is what truncates the file.
_record_fh = None
_record_pending = 0
RECORD_FLUSH_ROWS = 8
# Worst /data latency seen. If the page ever appears frozen, this says whether
# the server was the slow part or the browser was; 0 is normal (a few ms).
_max_data_ms = 0.0


def _record_close():
    global _record_fh
    if _record_fh is not None:
        try:
            _record_fh.flush()
            _record_fh.close()
        except OSError:
            pass
        _record_fh = None


def _record_append(text):
    """Append one CSV row. No-op when not recording. Never under `lock`."""
    global _record_pending
    if _record_fh is None:
        return
    try:
        _record_fh.write(text)
        _record_pending += 1
        if _record_pending >= RECORD_FLUSH_ROWS:
            _record_fh.flush()
            _record_pending = 0
    except (OSError, ValueError):
        pass


def _record_open():
    """Start recording. APPENDS, so a stray Record press cannot wipe a log."""
    global _record_fh, _record_pending
    _record_close()
    fresh = True
    try:
        fresh = not os.path.exists(RECORD_PATH) or os.path.getsize(RECORD_PATH) == 0
        _record_fh = open(RECORD_PATH, "a", encoding="utf-8")
        if fresh:
            _record_fh.write("kind,t,freq,value\n")
    except OSError:
        _record_fh = None
        return
    _record_pending = 0
    log_setting("session_start", time.strftime("%Y-%m-%d %H:%M:%S"))
    log_current_settings()


def _record_truncate():
    """Drop everything recorded so far. Called by Clear."""
    _record_close()
    try:
        open(RECORD_PATH, "w", encoding="utf-8").close()
    except OSError:
        pass
    if record_active:
        _record_open()

FRAME_GAP = 500           # ~5 ms of silence = a real gap BETWEEN frames, not the
                          # sub-millisecond dropouts the marginal demodulator makes
                          # inside one; used to count how often a device retransmits

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
_ev_codes = {}     # code -> count, tallied while the current event is open
_ev_bursts = 0     # most bursts seen in one capture during this event
_ev_unit_us = None  # shortest pulse measured during this event, in us
EVENT_RISE_DB = 8.0
EVENT_HYST_DB = 4.0
EVENT_MIN_S = 0.1
EVENT_MIN_ABOVE = 3


def _update_events(rssi, freq, t):
    global _floor, _in_event, _ev_start, _ev_peak, _ev_freq, _below_count, _ev_above
    global _ev_bursts, _ev_unit_us
    if _floor is None:
        _floor = float(rssi)
    else:
        _floor = _floor * 0.98 + rssi * 0.02

    if not _in_event:
        # Trigger on a large deviation EITHER way: depending on the CC1101's
        # AGC reference (PATABLE[0]) a strong signal can read as a spike OR a
        # dip. Both are a real transmission.
        if abs(rssi - _floor) > EVENT_RISE_DB:
            _in_event = True
            _ev_start = t
            _ev_peak = rssi
            _ev_freq = freq
            _below_count = 0
            _ev_above = 1
            _ev_codes.clear()
            _ev_bursts = 0
            _ev_unit_us = None
    else:
        if abs(rssi - _floor) > abs(_ev_peak - _floor):
            _ev_peak = rssi
        if abs(rssi - _floor) > EVENT_RISE_DB:
            _ev_above += 1
        if abs(rssi - _floor) < EVENT_HYST_DB:
            _below_count += 1
            if _below_count >= 3:
                duration = t - _ev_start
                if duration >= EVENT_MIN_S and _ev_above >= EVENT_MIN_ABOVE:
                    clock = time.strftime(
                        "%H:%M:%S", time.localtime(START_TIME + _ev_start))
                    etype = "signal" if duration >= 0.25 else "noise"
                    # Identify the transmission. One press fires several capture
                    # windows, so report the code seen MOST during this event
                    # rather than whatever decode happened to land last.
                    label = None
                    code = None
                    if _ev_codes:
                        code = sorted(_ev_codes.items(),
                                      key=lambda kv: (kv[1], len(kv[0])),
                                      reverse=True)[0][0]
                    elif last_decode and last_decode.get("hex"):
                        code = last_decode["hex"]
                    if fobburst_at and 0 < (START_TIME + _ev_start) - fobburst_at < 3.0:
                        label = "fob (TX test)"
                    # Interval since the previous transmission on this frequency.
                    # A tyre sensor repeats metronomically (typically ~60 s); a
                    # fob press is sporadic. Far more useful than raw strength
                    # for telling your own gear from a city full of other people's.
                    repeat_s = None
                    for prev in reversed(events):
                        pf = prev.get("freq")
                        if pf is not None and _ev_freq is not None and abs(pf - _ev_freq) <= 1.0:
                            repeat_s = round(_ev_start - prev["t"], 1)
                            break
                    events.append({
                        "t": round(_ev_start, 2),
                        "clock": clock,
                        "peak": _ev_peak,
                        "duration": round(duration, 2),
                        "freq": _ev_freq,
                        "type": etype,
                        "label": label,
                        "code": code,
                        "unit_us": round(_ev_unit_us) if _ev_unit_us else None,
                        "repeat_s": repeat_s,
                        "bursts": _ev_bursts or None,
                    })
                _in_event = False
        else:
            _below_count = 0


def _kmeans2(vals):
    """Split a list of numbers into two clusters; return the two centres."""
    a, b = float(min(vals)), float(max(vals))
    for _ in range(50):
        g1 = [v for v in vals if abs(v - a) <= abs(v - b)]
        g2 = [v for v in vals if abs(v - a) > abs(v - b)]
        if not g1 or not g2:
            break
        na, nb = sum(g1) / len(g1), sum(g2) / len(g2)
        if abs(na - a) < 1e-9 and abs(nb - b) < 1e-9:
            break
        a, b = na, nb
    return a, b


def decode_cap(hexstr, sample_us=48.0):
    """Decode a raw GDO0 capture into a code.

    Returns (hexstr, unit_samples, bursts) or None. `unit_samples` is the
    shorter pulse cluster (one unit of the PWM encoding, so 1/unit is a rough
    symbol rate); `bursts` is how many separate bursts the capture held.

    Two things matter here:

    1. The firmware prints each captured BYTE as TWO hex characters, so every
       hex character is a 4-BIT NIBBLE = 4 samples, MSB first. Expanding a
       nibble into 8 bits (as this function used to) inserts four bogus zeros
       per nibble, which fabricates a "4 samples on / 4 off" square wave out of
       ANY capture — that phantom pattern is why nothing ever decoded.

    2. This 315 MHz fob is a PWM/PPM OOK remote: its pulses are two widths
       (short and long) and the width carries the bit, opening with an
       alternating long/short preamble. So classify the runs into two clusters
       instead of assuming one fixed bit period.
    """
    samples = []
    for ch in hexstr:
        if ch not in "0123456789abcdefABCDEF":
            continue
        v = int(ch, 16)
        for k in (3, 2, 1, 0):
            samples.append((v >> k) & 1)
    if len(samples) < 64:
        return None

    # Run lengths of identical samples.
    runs = []
    prev = samples[0]
    run = 1
    for s in samples[1:]:
        if s == prev:
            run += 1
        else:
            runs.append(run)
            prev = s
            run = 1
    runs.append(run)

    # Count frames: activity separated by a real inter-frame gap. A fixed-code
    # fob held down retransmits the same frame several times, so this is a
    # "how many times did it repeat" number rather than a fragmentation count.
    frames = 0
    in_frame = False
    for r in runs:
        if r >= FRAME_GAP:
            in_frame = False
        elif not in_frame:
            frames += 1
            in_frame = True

    # Split at the idle gaps between repeats and keep the longest burst.
    bursts, cur = [], []
    for r in runs:
        if r > IDLE_RUN:
            if cur:
                bursts.append(cur)
            cur = []
        else:
            cur.append(r)
    if cur:
        bursts.append(cur)
    if not bursts:
        return None
    burst = max(bursts, key=len)
    if len(burst) < 12:
        return None

    # Classify the pulse widths into short/long; split at their geometric mean
    # so the boundary sits between the two clusters, not inside one.
    short, long_ = _kmeans2(burst)
    if short <= 0 or long_ < short * 1.3:
        return None                       # no clear two-level structure
    thr = math.sqrt(short * long_)
    sym = "".join("1" if r >= thr else "0" for r in burst)

    # A real remote frame opens with an alternating preamble; require one.
    if "101010" not in sym and "010101" not in sym:
        return None

    # Trim to the start of the first sustained alternating preamble so the code
    # begins at the same place every time the same fob is pressed.
    for i in range(len(sym) - 12):
        seg = sym[i:i + 12]
        if seg in ("101010101010", "010101010101"):
            sym = sym[i:]
            break
    # Skip the preamble itself. An uninterrupted alternating run is the
    # carrier/clock preamble, not data: including it makes the code start with a
    # constant 0xAA/0x55 prefix that varies with where the capture happened to
    # cut. Report only the payload, and reject a capture that never got past the
    # preamble (that is how a lone "55" used to be reported as a code).
    j = 1
    while j < len(sym) and sym[j] != sym[j - 1]:
        j += 1
    sym = sym[j:].rstrip("0")
    if len(sym) < 16:
        return None

    hexout = ""
    for j in range(0, len(sym) - 7, 8):
        byte = 0
        for k in range(8):
            byte = (byte << 1) | (1 if sym[j + k] == "1" else 0)
        hexout += "%02X" % byte
    if len(hexout) < 2:
        return None
    # unit = the shorter pulse cluster (1 unit of the PWM encoding, so 1/unit is
    # a rough symbol rate); frames = how many times the device retransmitted
    # within this capture window.
    return hexout, max(short, 1.0), frames


def handle_line(line):
    global port_error, raw_captures, scan_active, last_decode, events
    line = line.decode("utf-8", "ignore").strip()
    if line.startswith("SCAN_START"):
        scan_data.clear()
        scan_history.clear()
        scan_active = True
        return
    if line.startswith("SCAN_END"):
        scan_active = False
        return
    if line.startswith("SCAN "):
        parts = line.split()
        if len(parts) >= 3:
            try:
                f = float(parts[1])
                r = int(parts[2])
                scan_data[round(f, 1)] = r
                scan_history.append((time.time() - START_TIME, round(f, 1), r))
                _record_append("SCAN,%.2f,%.1f,%d\n"
                               % (time.time() - START_TIME, round(f, 1), r))
            except (ValueError, OSError):
                pass
        return
    if line.startswith("CAP "):
        try:
            # Tag each logged capture with the settings it was taken under, so a
            # session spanning modulation / data-rate changes stays analysable
            # (the raw hex alone cannot tell you which mode produced it).
            with open(CAPTURE_PATH, "a", encoding="utf-8") as f:
                f.write("%s MOD=%d DRATE=%d\n"
                        % (line, selected_mod, selected_drate))
            raw_captures += 1
            parts = line.split()
            if len(parts) >= 4:
                # Actual sample period from the CAP line's own timing.
                sample_us = 48.0
                try:
                    sample_us = float(parts[2]) / float(parts[1])
                except (ValueError, ZeroDivisionError):
                    sample_us = 48.0
                d = decode_cap(parts[3], sample_us)
                if d:
                    code, bit_samples, nbursts = d
                    unit_us = bit_samples * sample_us
                    last_decode = {"hex": code, "bit_us": round(unit_us)}
                    # While a transmission is in progress, tally the code against
                    # it - the event reports the most common one when it closes.
                    # Creating a row per capture is what used to fill the table
                    # with duplicates: one 4 s "signal" row surrounded by several
                    # 0.00 s "fob" rows that were just fragments of the same press.
                    if _in_event:
                        _ev_codes[code] = _ev_codes.get(code, 0) + 1
                        if nbursts > _ev_bursts:
                            _ev_bursts = nbursts
                        if _ev_unit_us is None or unit_us < _ev_unit_us:
                            _ev_unit_us = unit_us
                    elif not events or (time.time() - START_TIME) - events[-1]["t"] > 2.0:
                        now = time.time() - START_TIME
                        events.append({
                            "t": round(now, 2),
                            "clock": time.strftime(
                                "%H:%M:%S", time.localtime(START_TIME + now)),
                            "peak": None,
                            "duration": None,
                            "freq": selected_freq,
                            "type": "signal",
                            "label": None,
                            "code": code,
                            "unit_us": round(unit_us),
                            "repeat_s": None,
                            "bursts": nbursts,
                        })
        except OSError:
            pass
        return
    if line.startswith("TXCODE "):
        parts = line.split()
        if len(parts) >= 2:
            last_decode = {"hex": parts[1], "bit_us": 480}
            # The TX burst blocks the Arduino while it transmits, so the RSSI
            # deviation it causes never reaches this reader. Log the event
            # directly from the firmware's own confirmation.
            now = time.time() - START_TIME
            events.append({
                "t": round(now, 2),
                "clock": time.strftime("%H:%M:%S", time.localtime(START_TIME + now)),
                "peak": None,
                "duration": 0.78,
                "freq": selected_freq,
                "type": "signal",
                "label": "fob (TX test)",
                "code": parts[1],
            })
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
    # Written outside the lock - see the note on _record_fh above.
    _record_append("RSSI,%.2f,%s,%d\n"
                   % (t, ("%.1f" % freq) if freq is not None else "", rssi))


def log_setting(name, value):
    """Append a settings-change marker to the current recording.

    A recording is meant to survive band / modulation / data-rate changes, so
    without a marker there is no way to tell which settings a given row was
    taken under (frequency alone does not identify the modulation or rate).
    """
    _record_append("SETTING,%.2f,%s,%s\n"
                   % (time.time() - START_TIME, name, value))


def log_current_settings():
    """Write the active settings so a fresh recording starts self-describing."""
    log_setting("band_mhz", "%g" % selected_freq)
    log_setting("modulation", "FSK" if selected_mod == 0 else "ASK/OOK")
    log_setting("drate_bps", selected_drate)


def set_frequency(mhz):
    """Tell the Arduino to retune, and remember the selection."""
    global selected_freq
    selected_freq = float(mhz)
    log_setting("band_mhz", "%g" % selected_freq)
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
    # The Record button appends rather than truncating (so a stray press cannot
    # wipe a log), so Clear is what starts a fresh recording.
    _record_truncate()


def set_modulation(mod):
    """Tell the Arduino to switch modulation (0 = FSK, 2 = ASK/OOK)."""
    global selected_mod
    selected_mod = int(mod)
    log_setting("modulation", "FSK" if selected_mod == 0 else "ASK/OOK")
    with lock:
        s = ser_handle
    if s is not None:
        try:
            s.write(("MOD %d\n" % selected_mod).encode("ascii"))
            return True
        except Exception:
            return False
    return False


def set_drate(bps):
    """Tell the Arduino to change the RX data rate (bits/s)."""
    global selected_drate
    try:
        bps = int(bps)
    except (TypeError, ValueError):
        return False
    if not 600 <= bps <= 500000:
        return False
    selected_drate = bps
    log_setting("drate_bps", selected_drate)
    with lock:
        s = ser_handle
    if s is not None:
        try:
            s.write(("DRATE %d\n" % selected_drate).encode("ascii"))
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


def set_fobburst():
    """Tell the Arduino to transmit a fob-like OOK burst from the TX module."""
    global fobburst_at
    fobburst_at = time.time()
    with lock:
        s = ser_handle
    if s is not None:
        try:
            s.write(b"FOBBURST\n")
            return True
        except Exception:
            return False
    return False


def set_scan():
    """Toggle the continuous frequency sweep on the Arduino (SCAN command)."""
    with lock:
        s = ser_handle
    if s is not None:
        try:
            s.write(b"SCAN\n")
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
            # Let the Arduino finish its boot, then give the CC1101 a full
            # FSK RX soak (~5 s) before switching to OOK. Switching to OOK
            # too early leaves the RSSI register pinned at its floor (-138);
            # after a 5 s soak + 3 s OOK settle the 315 MHz OOK floor reads a
            # clean -99..-101 dBm (fobs are OOK).
            time.sleep(5.0)
            set_frequency(selected_freq)
            set_modulation(selected_mod)
            set_drate(selected_drate)
            set_tx(tx_on)
            set_sweep(sweep_mode)
            # The boot floor takes a moment to settle (the CC1101 AGC warms up
            # from a saturated -12 to its quiet -108 floor). Re-baseline here so
            # that warm-up transition isn't logged as a false "signal" event.
            time.sleep(2.0)
            clear_history()
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

HTML_PATH = os.path.join(HERE, "readout.html")


def load_html():
    """Serve the styled dashboard; fall back to the embedded page if missing."""
    try:
        with open(HTML_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return HTML


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # `global` is required: this method assigns to it below, and without
        # this line the assignment makes it function-local, so reading it here
        # raises UnboundLocalError on every request.
        global _max_data_ms
        if self.path == "/":
            body = load_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/data":
            _t0 = time.perf_counter()
            with lock:
                pts = [list(p) for p in samples]
                cur = dict(latest)
                evs = [dict(e) for e in events]
                scan = dict(scan_data)
                shist = [list(h) for h in scan_history]
                scan_on = scan_active
            # How stale the newest reading is. If the serial reader stalls, the
            # chart simply stops moving, which looks identical to a frozen UI;
            # this lets the page say which of the two it is.
            age = None
            if cur.get("t") is not None:
                age = round((time.time() - START_TIME) - cur["t"], 1)
            body = json.dumps({"points": pts, "latest": cur, "events": evs,
                               "selected_freq": selected_freq,
                               "selected_mod": selected_mod,
                               "selected_drate": selected_drate,
                               "tx_on": tx_on,
                               "sweep_mode": sweep_mode,
                               "scan": scan,
                               "scan_history": shist,
                               "scan_active": scan_on,
                               "record_active": record_active,
                               "raw_captures": raw_captures,
                               "last_decode": dict(last_decode) if last_decode else None,
                               "sample_age": age,
                               "max_data_ms": round(_max_data_ms, 1),
                               "port_error": port_error}).encode("utf-8")
            _elapsed = (time.perf_counter() - _t0) * 1000
            if _elapsed > _max_data_ms:
                _max_data_ms = _elapsed
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

        if self.path == "/drate":
            length = int(self.headers.get("Content-Length", 0) or 0)
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8", "ignore"))
                bps = int(data.get("bps"))
            except Exception:
                self.send_response(400)
                self.end_headers()
                return
            ok = set_drate(bps)
            body = json.dumps({"ok": ok, "bps": selected_drate}).encode("utf-8")
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

        if self.path == "/fobburst":
            ok = set_fobburst()
            body = json.dumps({"ok": ok}).encode("utf-8")
            self.send_response(200 if ok else 503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/scan":
            ok = set_scan()
            body = json.dumps({"ok": ok}).encode("utf-8")
            self.send_response(200 if ok else 503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/record":
            global record_active
            record_active = not record_active
            if record_active:
                _record_open()
            else:
                _record_close()
            body = json.dumps({"ok": True, "record_active": record_active}).encode("utf-8")
            self.send_response(200)
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
