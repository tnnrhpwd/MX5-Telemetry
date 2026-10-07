#!/usr/bin/env python3
"""Regression test: handle_line must survive a capture decoded during an event.

The bug this guards: handle_line() assigns `_ev_bursts` and `_ev_unit_us` but
did not declare them `global`, so they were local. The read at
`if nbursts > _ev_bursts` therefore raised UnboundLocalError - but only on the
branch where a capture decodes WHILE a transmission is in progress, i.e. exactly
when a fob is being held.

The exception escaped handle_line(), the reader's outer handler closed the
serial port, and the reconnect re-soaked for 2+5+2 = 9 seconds. The user saw the
page freeze for ~9 seconds after every fob press.

Exercising that branch needs no radio: set the in-progress flag, feed a
synthetic capture, and check it is parsed instead of exploding.

Usage:  python tests/test_line_handler.py
"""
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import live_readout as L      # noqa: E402


def make_cap_line(short=8, long_=20, preamble=14,
                  data=(8, 20, 8, 20, 8, 8, 20, 20, 8, 20,
                        8, 20, 20, 8, 20, 8, 20, 8, 20, 8),
                  total=4800, sample_us=9.33):
    """Build a `CAP <n> <us> <hex>` line holding a PWM-style burst.

    Long/short runs, opening with an alternating preamble, are what
    decode_cap() looks for. The payload must be long enough to survive
    preamble stripping (decode_cap needs >= 16 symbols after it), otherwise it
    returns None and this test would pass without ever reaching the code that
    used to raise.
    """
    seq = [long_ if i % 2 == 0 else short for i in range(preamble)]
    seq.extend(data)
    samples, level = [], 1
    for run in seq:
        samples.extend([level] * run)
        level ^= 1
    pad = total - len(samples)
    if pad < 0:                       # trim the tail if the burst overflows
        samples = samples[:total]
    else:
        samples.extend([level] * pad)

    hexs = ""
    for i in range(0, len(samples), 4):
        v = 0
        for b in samples[i:i + 4]:
            v = (v << 1) | b
        hexs += "%X" % v
    return "CAP %d %d %s" % (len(samples), int(len(samples) * sample_us), hexs)


def main():
    # Keep the test from appending to the real capture log.
    tmp = pathlib.Path(tempfile.gettempdir()) / "_cc1101_test_captures.txt"
    if tmp.exists():
        tmp.unlink()
    L.CAPTURE_PATH = str(tmp)

    checks = []

    # --- the regression: a capture arriving during a transmission -------------
    L._in_event = True
    L._ev_codes.clear()
    L._ev_bursts = 0
    L._ev_unit_us = None
    try:
        L.handle_line(make_cap_line().encode("ascii"))
        checks.append(("no exception while an event is in progress", True, ""))
    except Exception as exc:                                  # noqa: BLE001
        checks.append(("no exception while an event is in progress", False,
                       "%s: %s" % (type(exc).__name__, exc)))

    checks.append(("code tallied", bool(L._ev_codes), str(dict(L._ev_codes))))
    checks.append(("burst count tallied", L._ev_bursts >= 1, str(L._ev_bursts)))
    checks.append(("pulse width tallied", L._ev_unit_us is not None,
                   str(L._ev_unit_us)))

    # --- and with no event open (the easy path, which always worked) ----------
    L._in_event = False
    try:
        L.handle_line(make_cap_line().encode("ascii"))
        checks.append(("no exception with no event open", True, ""))
    except Exception as exc:                                  # noqa: BLE001
        checks.append(("no exception with no event open", False,
                       "%s: %s" % (type(exc).__name__, exc)))

    # --- malformed input must not raise either -------------------------------
    for bad in (b"CAP 4800 44784\n", b"CAP x y z\n", b"CAP 4800 44784 ZZ\n"):
        try:
            L.handle_line(bad)
            checks.append(("tolerates %r" % bad, True, ""))
        except Exception as exc:                              # noqa: BLE001
            checks.append(("tolerates %r" % bad, False,
                           "%s: %s" % (type(exc).__name__, exc)))

    if tmp.exists():
        tmp.unlink()

    failures = 0
    for name, ok, detail in checks:
        print("  %-46s %s%s" % (name, "PASS" if ok else "FAIL",
                                "" if ok else "  <- " + detail))
        if not ok:
            failures += 1
    print("\n%d/%d passed" % (len(checks) - failures, len(checks)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
