#!/usr/bin/env python3
"""Regression test: device signatures must describe a DEVICE, not a rail.

The indicator the user asked for lights when the most recent transmission
matches an enrolled device's timing signature. That only works if the signature
means something, and the first version did not: it clustered EVERY run,
including the multi-millisecond silence between repeats, so an ambient capture
that was mostly idle enrolled as a device with a 109x short/long ratio. It would
then match nothing, for ever, and look like the feature was broken.

These checks pin both directions:
  - a fob-shaped capture yields a signature matching its real pulse widths
  - a railed capture yields NO signature at all
  - two captures of the same device score high; a different device scores low

Usage:  python tests/test_device_signature.py
"""
import os
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import live_readout as L      # noqa: E402

SAMPLE_US = 9.33


def cap_hex(samples):
    """Pack samples the way the firmware prints them: 4 samples per nibble."""
    out = []
    for i in range(0, len(samples), 4):
        v = 0
        for k in range(4):
            v = (v << 1) | (samples[i + k] if i + k < len(samples) else 0)
        out.append("%X" % v)
    return "".join(out)


def fob_samples(short=8, long_=20, reps=3, gap=600):
    """A PWM/PPM remote burst: alternating preamble, payload, inter-frame silence.

    The gap has to exceed FRAME_GAP, otherwise it is just a long symbol - and a
    long symbol is exactly what the old code mistook for part of the signature.
    """
    bits = [1, 0] * 8 + [1, 1, 0, 1, 0, 0, 1, 1, 0, 1, 0, 0, 1, 0, 1, 1]
    level, samples = 1, []
    for _ in range(reps):
        for b in bits:
            samples.extend([level] * (long_ if b else short))
            level ^= 1
        samples.extend([level] * gap)
    return samples


def sig_of(samples):
    return L._signature(L._cap_runs(cap_hex(samples)), SAMPLE_US)


def check(name, cond, detail=""):
    print("  %-52s %s%s" % (name, "PASS" if cond else "FAIL",
                            "" if cond else "   " + detail))
    return cond


def main():
    ok = True

    # NEVER let this test write the real devices.json. _refine_device() PERSISTS,
    # and an earlier version of this file therefore silently overwrote the user's
    # enrolled devices with its synthetic TestFob - the test passed, the damage
    # was invisible until someone opened the device list, and restoring it needed
    # values that had been read by hand. Redirect the path before anything runs.
    real_path = L.DEVICES_PATH
    L.DEVICES_PATH = os.path.join(tempfile.mkdtemp(prefix="cc1101-test-"),
                                  "devices.json")

    sig = sig_of(fob_samples())
    ok &= check("fob burst yields a signature", sig is not None)
    if sig:
        print("      %s" % sig)
        ok &= check("short pulse ~= 8 samples x 9.33us",
                    60 <= sig["short_us"] <= 95, "got %s" % sig["short_us"])
        ok &= check("long pulse ~= 20 samples x 9.33us",
                    150 <= sig["long_us"] <= 225, "got %s" % sig["long_us"])
        ok &= check("ratio is a plausible 1.5-6x",
                    1.5 <= sig["ratio"] <= 6.0, "got %s" % sig["ratio"])

    railed = L._signature(L._cap_runs("FF" * 600), SAMPLE_US)
    ok &= check("railed (all-ones) capture yields NO signature", railed is None,
                "got %s" % (railed,))

    idle = L._signature(L._cap_runs(cap_hex([1] * 2400 + [0] * 2400)), SAMPLE_US)
    ok &= check("single-transition capture yields NO signature", idle is None,
                "got %s" % (idle,))

    a = sig_of(fob_samples(short=8, long_=20))
    b = sig_of(fob_samples(short=8, long_=21))       # same device, a bit noisy
    other = sig_of(fob_samples(short=22, long_=40))  # a different device
    s_same = L._sig_score(a, b) if a and b else None
    s_diff = L._sig_score(a, other) if a and other else None
    ok &= check("same device scores high (>= 0.75)",
                s_same is not None and s_same >= 0.75, "got %s" % s_same)
    ok &= check("a different device scores low (< 0.75)",
                s_diff is None or s_diff < 0.75, "got %s" % s_diff)

    # Enrolling must be a real round trip: the matched name has to come back.
    saved = dict(L._devices)
    try:
        L._devices.clear()
        L._devices["TestFob"] = {"color": "#fff", "sig": a}
        m = L._match_device(b)
        ok &= check("enrolled device is recognised", m is not None and
                    m["name"] == "TestFob", "got %s" % m)
        m2 = L._match_device(other)
        ok &= check("a different device does NOT match it",
                    m2 is None or m2["name"] != "TestFob", "got %s" % m2)
    finally:
        L._devices.clear()
        L._devices.update(saved)

    # The indicator must be MOMENTARY. Left latching, a device matched once stays
    # lit for ever and the page stops meaning "transmitting now".
    now = L.time.time() - L.START_TIME
    L.last_device = {"name": "TestFob", "score": 1.0, "t": now}
    ok &= check("a just-detected device is reported lit",
                L._fresh_device() is not None)
    L.last_device = {"name": "TestFob", "score": 1.0,
                     "t": now - L.DEVICE_HOLD_S - 0.1}
    ok &= check("it goes out after DEVICE_HOLD_S",
                L._fresh_device() is None, "still lit")
    L.last_device = {"name": "TestFob", "score": 1.0,
                     "t": now - L.DEVICE_HOLD_S + 0.5}
    ok &= check("it is still lit just inside the window",
                L._fresh_device() is not None)
    L.last_device = None
    ok &= check("no match reported as None", L._fresh_device() is None)

    # A single-capture enrolment is a noisy estimate, so later sightings have to
    # pull it toward the device's real timing - otherwise one marginal capture
    # permanently defines the device and the match never fires again.
    saved = dict(L._devices)
    try:
        L._devices.clear()
        L._devices["TestFob"] = {"color": "#fff", "sig": dict(a)}
        before = L._devices["TestFob"]["sig"]["short_us"]
        noisy = dict(b)
        noisy["short_us"] = before + 40          # a sighting 40 us away
        L._refine_device("TestFob", noisy)
        after = L._devices["TestFob"]["sig"]["short_us"]
        ok &= check("a sighting pulls the enrolment toward it",
                    before < after < noisy["short_us"],
                    "before=%s after=%s target=%s" % (before, after,
                                                      noisy["short_us"]))
        ok &= check("it moves only part of the way (no overwrite)",
                    abs(after - noisy["short_us"]) > 1,
                    "jumped straight to the new value")
    finally:
        L._devices.clear()
        L._devices.update(saved)

    L._devices.clear()

    # A test must not be able to damage real state, so assert the redirect held.
    with open(L.DEVICES_PATH, encoding="utf-8") as fh:
        import json as _json
        _ = _json.load(fh)
    ok &= check("test wrote to a temp path, not the real devices.json",
                L.DEVICES_PATH != real_path)

    L.DEVICES_PATH = real_path
    print("\n%s" % ("all checks passed" if ok else "FAILURES above"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
