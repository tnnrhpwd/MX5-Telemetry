#!/usr/bin/env python3
"""Regression test: a device is identified by its MESSAGE, not by pulse timing.

Timing identification was removed after it repeatedly failed to recognise the
same fob twice. These numbers are all from ONE physical Nissan fob, enrolled six
times:

    long_us    292   293   295   675   850  1246
    short_us   120   122   124    79   130    92
    ratio     2.40  2.52  2.45  5.11  9.75  7.32

That is not a device fingerprint. It records how long the button was held and how
much silence the 45 ms capture window happened to include. A decoded message does
not vary with either: it is the same message or it is a different one.

What is pinned here:

  1. Codes compare the way the decoder emits them - case and leading zeros are
     not differences.
  2. Enrolment needs a decoded message. There is NO fallback to timing, so a
     press that does not decode is refused with an explanation rather than
     stored as a guess.
  3. Enrolling the same message twice is refused, naming the device that has it.
  4. The chip lights the moment the enrolment lands - the reported bug was
     "immediately after I enrol a new device the indicator does not light up".
  5. An enrolment with no code (every device enrolled under the old timing
     model) is INERT: it must go quiet rather than light on a coincidence.

Usage:  python tests/test_device_code_match.py
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


def main():
    saved = dict(L._devices)
    # _enrol() SAVES, so the path is redirected before it is ever called.
    real_path = L.DEVICES_PATH
    L.DEVICES_PATH = os.path.join(tempfile.mkdtemp(prefix="cc1101-code-"),
                                  "devices.json")
    saved_state = (L.last_decode, L.last_device, L._devices_load_error)
    try:
        L._devices_load_error = None
        check("the enrol path under test writes to a temp file",
              L.DEVICES_PATH != real_path, L.DEVICES_PATH)

        # --- 1. how codes compare ---------------------------------------
        check("identical codes match", L._same_code("1A2B", "1A2B"))
        check("case is ignored", L._same_code("1a2b", "1A2B"))
        check("leading zeros are ignored", L._same_code("001A2B", "1A2B"))
        check("different codes do not match", not L._same_code("1A2B", "1A2C"))
        check("an empty code never matches", not L._same_code("", "1A2B"))
        check("a missing code never matches", not L._same_code(None, "1A2B"))

        # --- 2. enrolling needs a message -------------------------------
        check("no name is refused",
              L._enrol_reason("", "1A2B") == "no name given")
        why = L._enrol_reason("x", None)
        check("no decoded code is refused", bool(why), repr(why))
        check("...and the refusal explains itself",
              "decoded" in (why or ""), repr(why))
        check("a decoded code is accepted",
              L._enrol_reason("x", "1A2B3C") is None)

        # --- the round trip ---------------------------------------------
        L._devices.clear()
        check("an unknown message matches nothing",
              L._match_code("1A2B3C") is None)
        check("enrolling succeeds",
              L._enrol("mazda", "#b07fd6", "1A2B3C") is None)
        hit = L._match_code("1A2B3C")
        check("the message now matches its device",
              bool(hit) and hit["name"] == "mazda", repr(hit))
        check("the match carries the code back",
              bool(hit) and hit["code"] == "1A2B3C", repr(hit))
        check("a different message still matches nothing",
              L._match_code("4D5E6F") is None)

        # --- 3. a duplicate message is refused --------------------------
        why = L._enrol("nissan", "#4fd0c0", "1A2B3C")
        check("enrolling the same message twice is refused", bool(why), repr(why))
        check("...and names the device that already has it",
              "mazda" in (why or ""), repr(why))
        check("a second, different message is accepted",
              L._enrol("nissan", "#4fd0c0", "99AABB") is None)
        check("and both messages are recognised",
              L._match_code("1A2B3C")["name"] == "mazda"
              and L._match_code("99AABB")["name"] == "nissan")

        # --- 4. the chip lights the moment the enrolment lands ----------
        L._devices.clear()
        L.last_decode = {"hex": "5A5A01", "bit_us": 100}
        L.last_device = {"name": "stale", "score": 1.0, "t": 0}
        L._refresh_match()
        check("with nothing enrolled, nothing lights", L.last_device is None)
        L._enrol("fresh", "#ffffff", "5A5A01")
        lit = L._fresh_device()
        check("the chip just enrolled lights IMMEDIATELY",
              bool(lit) and lit["name"] == "fresh", repr(lit))
        check("the pre-enrolment match did not survive",
              bool(lit) and lit["name"] != "stale", repr(lit))

        # --- 5. a device with no code is inert --------------------------
        # Every enrolment made under the old timing model is in this state. It
        # must stay dark rather than light on a timing coincidence.
        L._devices.clear()
        L._devices["legacy"] = {"color": "#111111", "sig": {"short_us": 120}}
        L._devices["good"] = {"color": "#222222", "code": "AA11"}
        check("a legacy no-code enrolment matches nothing",
              L._match_code("BB22") is None)
        check("and does not shadow a real one",
              L._match_code("AA11")["name"] == "good")

        # --- no decode, no light ----------------------------------------
        L._devices.clear()
        L._enrol("x", "#333333", "CC33")
        L.last_decode = None
        L._refresh_match()
        check("with no decoded message, nothing lights", L.last_device is None)
    finally:
        L.DEVICES_PATH = real_path
        L.last_decode, L.last_device, L._devices_load_error = saved_state
        L._devices.clear()
        L._devices.update(saved)

    print("\n%s" % ("all checks passed" if ok else "FAILURES above"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
