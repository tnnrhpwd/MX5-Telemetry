#!/usr/bin/env python3
"""Regression test: a fragment enrolment must never match anything.

The bug this guards: pressing the Mazda fob lit the Mazda chip and then the
Nissan one. The cause was not the tolerances - it was that the same Nissan fob
had been enrolled five times, and three of those enrolments were FRAGMENTS
(16, 21 and 29 pulse runs against 188-213 for a real capture). A fragment's
stored timings are arbitrary, so they sit within tolerance of everything, and a
noisy capture of the Mazda produced exactly that shape.

So the two properties pinned here are:

  1. A signature too thin to be a measurement cannot be enrolled at all, and
     the refusal says why rather than failing silently.
  2. A device that was enrolled from a fragment is SKIPPED when matching - the
     existing junk in devices.json must go quiet rather than having to be found
     and deleted by hand first.

Plus the ambiguity guard: a capture equally close to two devices lights NEITHER,
because "Mazda, then Nissan" is what picking one arbitrarily looks like.

Usage:  python tests/test_device_matching.py
"""
import os
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import live_readout as L      # noqa: E402

ok = True


def check(name, cond, detail=""):
    global ok
    print("  %-58s %s%s" % (name, "PASS" if cond else "FAIL",
                            "" if cond else "   " + detail))
    ok = ok and cond


def sig(short, long_, ratio, runs, period=None):
    return {"short_us": short, "long_us": long_, "ratio": ratio,
            "period_syms": period, "period_match": 0.0, "n_runs": runs}


def main():
    # SUPERSEDED. This suite tested identification by PULSE TIMING, which has been
    # removed: a device is identified by its decoded message now, and
    # tests/test_device_code_match.py covers that. The file is left in place,
    # empty, rather than deleted, so the record of what was tried is not dropped.
    print("  (superseded by tests/test_device_code_match.py - nothing to do)")
    return 0


def _superseded_main():
    saved = dict(L._devices)
    # _enrol() SAVES, so DEVICES_PATH has to be redirected before it is ever
    # called - the same trap that once let a test destroy the real
    # devices.json, and the reason this redirect is asserted below.
    real_path = L.DEVICES_PATH
    L.DEVICES_PATH = os.path.join(tempfile.mkdtemp(prefix="cc1101-match-"),
                                  "devices.json")
    saved_state = (L.last_signature, L.last_signature_t, L.last_device,
                   L._devices_load_error)
    try:
        L._devices_load_error = None
        check("enrol path under test writes to a temp file",
              L.DEVICES_PATH != real_path, L.DEVICES_PATH)

        # --- 1. what may be enrolled --------------------------------------
        check("no name is refused", L._enrol_reason("", sig(144, 441, 3.1, 213))
              == "no name given")
        check("no signal is refused", L._enrol_reason("x", None)
              == "nothing received yet")
        thin = L._enrol_reason("x", sig(130, 1246, 9.75, 16))
        check("a 16-run fragment is refused", bool(thin), repr(thin))
        check("the refusal names the evidence, not just 'failed'",
              "16" in (thin or "") and str(L.ENROL_MIN_RUNS) in (thin or ""),
              repr(thin))
        check("a 21-run fragment is refused",
              bool(L._enrol_reason("x", sig(44, 264, 6.03, 21))))
        check("a 29-run fragment is refused",
              bool(L._enrol_reason("x", sig(79, 850, 10.8, 29))))
        check("a 65-run slice is refused (it slipped past a floor of 60)",
              bool(L._enrol_reason("x", sig(88, 643, 7.29, 65))))
        check("a 90-run slice is refused",
              bool(L._enrol_reason("x", sig(60, 400, 6.6, 90))))
        check("a 120-run capture is accepted",
              L._enrol_reason("x", sig(120, 300, 2.5, 120)) is None)
        check("a 188-run capture is accepted",
              L._enrol_reason("x", sig(120, 295, 2.45, 188)) is None)
        check("a 213-run capture is accepted",
              L._enrol_reason("x", sig(144, 441, 3.11, 213)) is None)

        # --- 2. a fragment enrolment must not match anything --------------
        # This is the exact failure: the same signature that was enrolled from
        # a fragment comes back and would previously have scored 1.00.
        L._devices.clear()
        L._devices["junk"] = {"color": "#111111", "sig": sig(130, 1246, 9.75, 16)}
        check("a fragment enrolment does NOT match its own signature",
              L._match_device(sig(130, 1246, 9.75, 16)) is None,
              repr(L._match_device(sig(130, 1246, 9.75, 16))))
        check("...nor a nearby fragment",
              L._match_device(sig(129, 1200, 9.5, 18)) is None)

        # --- 3. a good enrolment matches, and wins outright ---------------
        L._devices.clear()
        L._devices["mazda"] = {"color": "#222222",
                               "sig": sig(144, 441, 3.11, 213, 96)}
        hit = L._match_device(sig(144, 441, 3.11, 213, 96))
        check("a good enrolment matches its own signature",
              bool(hit) and hit["name"] == "mazda", repr(hit))
        check("and reports the score", bool(hit) and hit["score"] == 1.0,
              repr(hit))

        # --- 4. two devices equally close -> light NEITHER ----------------
        L._devices["nissan"] = {"color": "#333333",
                                "sig": sig(144, 441, 3.11, 213, 96)}
        check("an exact tie lights nothing (not the first one)",
              L._match_device(sig(144, 441, 3.11, 213, 96)) is None,
              repr(L._match_device(sig(144, 441, 3.11, 213, 96))))

        # --- 5. a clear winner still wins ---------------------------------
        L._devices["nissan"] = {"color": "#333333",
                                "sig": sig(400, 1600, 4.0, 200)}
        hit = L._match_device(sig(144, 441, 3.11, 213, 96))
        check("with a clear winner, the right chip lights",
              bool(hit) and hit["name"] == "mazda", repr(hit))

        # --- 6. the real pair, from the live enrolments -------------------
        # Mazda 144/441/3.11 and the trustworthy Nissan 122/292/2.35 are close
        # enough that this is worth pinning: neither may match the other.
        L._devices.clear()
        L._devices["mazda fob"] = {"color": "#b07fd6",
                                   "sig": sig(144, 441, 3.11, 213, 96)}
        L._devices["nissan fob 2"] = {"color": "#4fd0c0",
                                      "sig": sig(124, 290, 2.35, 198)}
        m = L._match_device(sig(144, 441, 3.11, 213, 96))
        n = L._match_device(sig(124, 290, 2.35, 198))
        check("a Mazda capture lights mazda and only mazda",
              bool(m) and m["name"] == "mazda fob", repr(m))
        check("a Nissan capture lights nissan and only nissan",
              bool(n) and n["name"] == "nissan fob 2", repr(n))
        check("neither matches the other",
              L._match_device(sig(124, 290, 2.35, 198))["name"] != "mazda fob",
              repr(L._match_device(sig(124, 290, 2.35, 198))))

        # --- 7. changing the device set re-attributes the last signal -----
        # Reported as "immediately after I enrol a new device the indicator does
        # not light up correctly". The match was computed ONLY when a new
        # CAPTURE arrived, so the chip just enrolled from the current signature
        # stayed dark until the next press - at the one moment the user is
        # looking at it for confirmation. A renamed or deleted chip could
        # equally stay lit with nothing behind it.
        good = sig(144, 441, 3.11, 213, 96)
        L._devices.clear()
        L.last_signature = good
        L.last_signature_t = L.time.time() - L.START_TIME
        L.last_device = {"name": "stale", "score": 1.0, "t": 0}
        L._refresh_match()
        check("with nothing enrolled, nothing lights", L.last_device is None,
              repr(L.last_device))

        L.last_device = {"name": "stale", "score": 1.0, "t": 0}
        err = L._enrol("mazda fob", "#b07fd6", good)
        check("enrolling succeeds", err is None, repr(err))
        lit = L._fresh_device()
        check("the chip just enrolled lights IMMEDIATELY",
              bool(lit) and lit["name"] == "mazda fob", repr(lit))
        check("and reports a perfect score",
              bool(lit) and lit["score"] == 1.0, repr(lit))
        check("the pre-enrolment match did not survive",
              bool(lit) and lit["name"] != "stale", repr(lit))
        check("it is stamped now, not at the capture",
              bool(L.last_device) and L.last_device["t"] > 0,
              repr(L.last_device))

        # A second, identical device makes the capture ambiguous - and lighting
        # one of them arbitrarily is the bug reported earlier.
        L._enrol("mazda fob 2", "#b07fd6", good)
        L._refresh_match()
        check("an ambiguous set lights neither chip", L.last_device is None,
              repr(L.last_device))

        # A signature that is no longer recent must not be attributed at all.
        L._devices.clear()
        L._devices["mazda fob"] = {"color": "#b07fd6", "sig": good}
        L.last_signature_t = (L.time.time() - L.START_TIME
                              - L.ENROL_CONFIRM_S - 1)
        L._refresh_match()
        check("a stale signal is attributed to nothing",
              L.last_device is None, repr(L.last_device))

        # ...and once it is fresh again, deleting the device takes the light
        # with it rather than leaving a chip lit with nothing behind it.
        L.last_signature_t = L.time.time() - L.START_TIME
        L._refresh_match()
        check("a fresh signal lights again", bool(L._fresh_device()))
        L._devices.clear()
        L._refresh_match()
        check("with every device gone, nothing lights",
              L.last_device is None and L._fresh_device() is None)

        check("the test never wrote the real devices.json",
              not os.path.exists(os.path.join(os.path.dirname(real_path),
                                              "devices.json.tmp")))
    finally:
        L.DEVICES_PATH = real_path
        (L.last_signature, L.last_signature_t, L.last_device,
         L._devices_load_error) = saved_state
        L._devices.clear()
        L._devices.update(saved)

    print("\n%s" % ("all checks passed" if ok else "FAILURES above"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
