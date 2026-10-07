# CC1101 bench test

A 315 MHz receive bench: an Arduino Nano with two CC1101 modules (one receiver,
one transmitter as a test source), a webapp that shows the signal live, and the
firmware and diagnostics for finding and decoding 315/433 MHz devices.

Design notes, wiring and the RF background live in
[`../../docs/CC1101_BENCH_TEST.md`](../../docs/CC1101_BENCH_TEST.md).

## Layout

| Path | What it is |
| --- | --- |
| `live_readout.py` | The webapp: reads COM3, decodes captures, serves the page on <http://127.0.0.1:8765/> |
| `readout.html` | The page `live_readout.py` serves |
| `firmware/pio_unified/` | **The active firmware.** Live level + raw burst capture on one serial port |
| `firmware/pio_nano/` | Earlier sketch, and the vendored `SmartRC-CC1101-Driver-Lib` |
| `firmware/pio_capture/` | Capture-only sketch |
| `firmware/pio_loopback/` | TX/RX loopback test |
| `firmware/cc1101_scan/` | Arduino-IDE sketch from the original bench test |
| `scripts/` | Reusable diagnostics and helpers |
| `tests/` | Check scripts that drive the running webapp over HTTP |
| `captures/` | Recorded sessions and logs |

`firmware/` holds several projects, but only one is current. `pio_unified` is
the one to flash; the rest are kept for reference. `pio_nano` cannot be deleted,
because `pio_unified/platformio.ini` resolves its library with
`lib_extra_dirs = ../pio_nano/lib`.

## Run the webapp

```powershell
venv\Scripts\python.exe tools\cc1101\live_readout.py    # defaults to COM3
```

Then open <http://127.0.0.1:8765/>. The page polls `/data` ten times a second, so
the serial reader is the thing that decides how alive it feels.

Runtime output goes to `captures/capture_live.txt` (raw captures, one per line)
and `captures/record_log.csv` (whatever the Record button logs). Both are
gitignored. The Record button appends; **Clear** is what starts a fresh
recording.

## Flash the firmware

```powershell
pio run -d tools\cc1101\firmware\pio_unified                    # build
pio run -d tools\cc1101\firmware\pio_unified --target upload     # build + flash
pio device monitor -b 115200                                     # watch it
```

Stop the webapp first: it holds COM3.

## Scripts

| Script | Use |
| --- | --- |
| `scripts/probe_boot.py` | Boot diagnostic count, idle level and capture rate. Use it to A/B a config change |
| `scripts/rate_sweep.py` | Steps the RX data rate and reports which one reproduces the signal cleanest. Needs the fob held for the whole run |
| `scripts/analyze_capture.py` | Decode the pulse structure of a saved capture log |
| `scripts/compare_tags.py` | Group the capture log by its `MOD=` tag and compare pulse widths, short/long separation and decode rate. This is how you compare two RX configs on the same fob |
| `scripts/compare_press.py` | Check whether captures from one press share a common frame, i.e. fixed code versus rolling code. Works on decoded payloads, so it is only as good as the framing |
| `scripts/find_frame.py` | Framing-independent version of the above: aligns the raw run-length sequences of every capture pair and compares the result against a **shuffled control**, because "best match over all offsets" is a maximum statistic that beats a median even on pure noise. Use this one to decide whether a repeating frame was captured at all |
| `scripts/capture.py` | Dump raw serial to a file |
| `scripts/dump_regs.py` | Read back the RX registers |
| `scripts/check_*.py` | One-line status probes against the running webapp |
| `scripts/set_mod2.py`, `scripts/stop_sweep.py` | Toggle modulation / stop a sweep from the command line |

Note that the CC1101's registers cannot be read back reliably on this board: the
two modules share MISO, so `dump_regs.py` and the firmware's `DUMP` command
return bit-shifted garbage. Verify a config change behaviourally instead.

## Tests

`tests/` drives the running webapp over HTTP, so start `live_readout.py` first
and then run one directly, for example:

```powershell
venv\Scripts\python.exe tools\cc1101\tests\test_fsk_vs_ook.py
```

They exercise the FSK/ASK toggle, the TX burst, the sweep and the scan, and
print what they observed rather than asserting.

Two of them do not need the radio at all, and both guard a real bug:

| Test | Guards |
| --- | --- |
| `tests/check_module_globals.py` | A function that reads a module-level name before assigning it. `py_compile` and the editor both call this valid, but it raises `UnboundLocalError` at runtime |
| `tests/test_line_handler.py` | `handle_line()` surviving a capture that decodes *while a transmission is in progress* - the path that once killed the reader and froze the page for 9 seconds |
