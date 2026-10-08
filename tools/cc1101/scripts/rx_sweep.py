"""Sweep band and RX data rate through the running webapp while a fob is pressed.

Why a sweep rather than one guess: the captured waveform is a constant-duty
square wave with no symbol structure, so no payload can be read from it. Three
explanations demand different fixes -

  * the band is wrong, so the receiver hears the fob's OSCILLATOR LEAKAGE rather
    than its modulated signal, which would be identical for every fob,
  * it is the fob's own signal and the receiver's data rate is mis-tuned, or
  * it is the receiver's slicer oscillating, in which case the frequency follows
    the RX DATA RATE rather than the fob.

Only a sweep separates them. Each sweep dwells on one rate long enough for
several presses, and the server tags every capture it logs with the rate in
force (`DRATE=`), so nothing needs bookkeeping here - compare afterwards with
`pwm_decode.py --by-drate`.

This talks to the running webapp over HTTP rather than opening COM3, so the
server does not have to be stopped. (scripts/rate_sweep.py is the older
direct-serial variant: it needs COM3 exclusively and analyses run lengths with
the two-cluster timing model this project has since abandoned.)

Usage:
  python rx_sweep.py [dwell_seconds] [rate ...]
"""

import json
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8765"
# 433.92 FIRST. The modules are E07-M1101D-433 parts and 315 MHz sits outside the
# CC1101's 387-464 MHz range, so the 433 band is the higher prior - and if the
# band is the problem, most of the session is then spent on the right one.
FREQS = [433.92, 315.0]
RATES = [2000, 10000, 38400]


def post(path, obj):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(obj).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read().decode())


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=5) as r:
        return json.loads(r.read().decode())


def main():
    args = sys.argv[1:]
    dwell = float(args[0]) if args and args[0].replace(".", "").isdigit() else 10.0
    rates = [int(a) for a in args if a.isdigit() and int(a) > 100] or RATES

    d = get("/data")
    print("start: mod=%s (2=ASK/OOK)  freq=%s MHz"
          % (d.get("selected_mod"), d.get("selected_freq")))
    if int(d.get("selected_mod", 2)) != 2:
        print("!! modulation is not ASK/OOK - select ASK/OOK on the page first")
        return 1

    combos = [(f, r) for f in FREQS for r in rates]
    for i, (freq, rate) in enumerate(combos):
        post("/freq", {"mhz": freq})
        post("/drate", {"bps": rate})
        print("")
        print(">>> %d/%d   %.2f MHz @ %d bps   %.0fs   KEEP PRESSING THE FOB"
              % (i + 1, len(combos), freq, rate, dwell))
        remaining = dwell
        while remaining > 5.0:
            time.sleep(5.0)
            remaining -= 5.0
            print("      ... %.0fs left at %.2f MHz / %d bps"
                  % (remaining, freq, rate))
        time.sleep(max(remaining, 0.0))
    post("/freq", {"mhz": 315.0})
    post("/drate", {"bps": 10000})
    print("")
    print("sweep complete - receiver left at 315 MHz / 10 kbps ASK/OOK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
