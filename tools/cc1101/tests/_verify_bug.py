"""Throwaway: confirm the pre-fix code raises UnboundLocalError on the same input.

Removes the `global _ev_bursts, _ev_unit_us` line from handle_line() - the LAST
occurrence (the first one belongs to _update_events, and removing that one
proves nothing) - then feeds that copy a capture that decodes while an event is
open.
"""
import pathlib
import sys
import tempfile

CC = pathlib.Path(r"C:\Users\tanne\Documents\Github\MX5-Telemetry\tools\cc1101")
src = (CC / "live_readout.py").read_text(encoding="utf-8")

# rsplit: take the LAST occurrence, which is the one inside handle_line().
head, _, tail = src.rpartition("    global _ev_bursts, _ev_unit_us\n")
assert head, "global line not found"
buggy = head + tail
assert buggy != src, "could not reproduce the buggy version"

d = pathlib.Path(tempfile.mkdtemp())
(d / "live_readout.py").write_text(buggy, encoding="utf-8")
sys.path.insert(0, str(d))
import live_readout as L      # noqa: E402  (the buggy copy)

print("handle_line declares:",
      [l.strip() for l in buggy.splitlines()
       if l.strip().startswith("global port_error")])


def make_cap_line(short=8, long_=20, preamble=14,
                  data=(8, 20, 8, 20, 8, 8, 20, 20, 8, 20,
                        8, 20, 20, 8, 20, 8, 20, 8, 20, 8), total=4800):
    seq = [long_ if i % 2 == 0 else short for i in range(preamble)] + list(data)
    samples, level = [], 1
    for run in seq:
        samples.extend([level] * run)
        level ^= 1
    samples.extend([level] * (total - len(samples)))
    hexs = ""
    for i in range(0, len(samples), 4):
        v = 0
        for b in samples[i:i + 4]:
            v = (v << 1) | b
        hexs += "%X" % v
    return "CAP %d %d %s" % (len(samples), int(len(samples) * 9.33), hexs)


L.CAPTURE_PATH = str(pathlib.Path(tempfile.gettempdir()) / "_buggy_caps.txt")
L._in_event = True
L._ev_codes.clear()
L._ev_bursts = 0
L._ev_unit_us = None
try:
    L.handle_line(make_cap_line().encode("ascii"))
    print("OLD CODE (no global): no exception  <-- unexpected")
except UnboundLocalError as exc:
    print("OLD CODE (no global): UnboundLocalError ->", exc)
    print("   this is what killed the reader and froze the page for 9s")
