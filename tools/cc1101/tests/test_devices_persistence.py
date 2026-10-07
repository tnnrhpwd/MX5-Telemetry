#!/usr/bin/env python3
"""Regression test: an unreadable devices.json must never be wiped.

devices.json is the ONLY record of an enrolment, and several code paths rewrite
it automatically. The old _load_devices() collapsed every failure into
_devices = {}, and _save_devices() then wrote that empty dict straight over the
file - so a transient read error, or a file left half-written by an interrupted
save, silently destroyed every enrolment. The next enrolment would replace the
file with a one-device version of itself and the rest were simply gone.

Two properties are pinned here, and the second is the one that is easy to get
wrong while "fixing" the first:

  1. A failed load must not authorise an automatic save, and must leave the
     damaged file on disk exactly as it found it.
  2. A DELIBERATE save is still allowed to proceed (otherwise the feature is
     bricked), but only after the unreadable file has been copied aside, so the
     data is recoverable by hand rather than destroyed.

Usage:  python tests/test_devices_persistence.py
"""
import json
import os
import pathlib
import shutil
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import live_readout as L      # noqa: E402

REAL = L.DEVICES_PATH
ok = True


def check(name, cond, detail=""):
    global ok
    print("  %-58s %s%s" % (name, "PASS" if cond else "FAIL",
                            "" if cond else "   " + detail))
    ok = ok and cond


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def main():
    tmp = tempfile.mkdtemp(prefix="cc1101-devtest-")
    try:
        L.DEVICES_PATH = os.path.join(tmp, "devices.json")
        check("test redirected DEVICES_PATH off the real file",
              L.DEVICES_PATH != REAL and os.path.basename(REAL) == "devices.json"
              and L.DEVICES_PATH not in REAL, L.DEVICES_PATH)

        # --- a missing file is a normal empty state -------------------------
        L._load_devices()
        check("missing file loads empty, with no error",
              L._devices == {} and L._devices_load_error is None,
              repr(L._devices_load_error))
        L._devices = {"A": {"color": "#123456", "sig": {"short_us": 80}}}
        check("saving over a missing file works", L._save_devices(force=True) is True)
        check("and it really landed on disk",
              json.loads(read(L.DEVICES_PATH)).get("A") is not None)

        # --- a TRUNCATED file: the data-loss case --------------------------
        damaged = '{"Nissan Fob": {"color": "#4f9de0", "sig": {"sho'
        with open(L.DEVICES_PATH, "w", encoding="utf-8") as f:
            f.write(damaged)
        L._load_devices()
        check("a truncated file is reported as an error",
              L._devices_load_error is not None, "no error recorded")
        check("and loads as empty, so nothing matches", L._devices == {})
        check("the AUTOMATIC save is refused", L._save_devices() is False)
        check("the damaged file is left byte-for-byte on disk",
              read(L.DEVICES_PATH) == damaged, repr(read(L.DEVICES_PATH)[:28]))

        # --- an unreadable path (a directory) is the same story ------------
        asdir = os.path.join(tmp, "a-directory")
        os.mkdir(asdir)
        L.DEVICES_PATH = asdir
        L._load_devices()
        check("an unreadable path is reported as an error",
              L._devices_load_error is not None, "no error recorded")
        check("the automatic save is refused there too", L._save_devices() is False)

        # --- a DELIBERATE save still works, and preserves the old bytes ----
        L.DEVICES_PATH = os.path.join(tmp, "devices.json")
        with open(L.DEVICES_PATH, "w", encoding="utf-8") as f:
            f.write(damaged)
        L._load_devices()                      # fails again, on purpose
        L._devices = {"New Fob": {"color": "#ffffff", "sig": {"short_us": 70}}}
        check("a deliberate save is still allowed", L._save_devices(force=True) is True)
        check("the unreadable file was preserved as .bad",
              os.path.exists(L.DEVICES_PATH + ".bad"))
        check("the preserved bytes are the originals",
              read(L.DEVICES_PATH + ".bad") == damaged)
        check("and the new enrolment is what is now live",
              json.loads(read(L.DEVICES_PATH)).get("New Fob") is not None)

        # --- writes are atomic: no temp file survives ----------------------
        check("no .tmp left behind", not os.path.exists(L.DEVICES_PATH + ".tmp"))
        L._devices = {"B": {"color": "#000000", "sig": {"short_us": 1}}}
        L._save_devices(force=True)
        check("still no .tmp after another save",
              not os.path.exists(L.DEVICES_PATH + ".tmp"))
        check("the file always parses", "B" in json.loads(read(L.DEVICES_PATH)))

        # --- and a transient failure must not be remembered forever --------
        # Once a good load succeeds the error is clear, so later saves work
        # without force - otherwise one bad moment would block saving for the
        # rest of the run.
        L._load_devices()
        check("a good load clears the error",
              L._devices_load_error is None and "B" in L._devices)
        L._devices["C"] = {"color": "#111111", "sig": {"short_us": 2}}
        check("so the automatic save works again", L._save_devices() is True)
    finally:
        L.DEVICES_PATH = REAL
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n%s" % ("all checks passed" if ok else "FAILURES above"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
