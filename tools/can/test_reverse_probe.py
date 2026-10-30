#!/usr/bin/env python3
"""Desk test for tools/can/reverse_probe.py - the analysis half, with no car involved.

ISSUE-14 ("reverse reports a positive speed and gear 1") is blocked on one thing only:
capturing the bus in neutral and in reverse, then reading the difference. The capture
needs the car; the *reading* does not, and that is the half that decides which frame to
trust. This pins down that reading against synthetic captures, so the answer is settled
by the tool rather than by squinting at JSON at the side of the road.

Runs as a plain script and under pytest:

    python3 tools/can/test_reverse_probe.py
"""

import importlib.util
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _load_probe(data_dir):
    """Import reverse_probe with MX5_PROBE_DIR pointed at a temporary directory."""
    os.environ["MX5_PROBE_DIR"] = data_dir
    spec = importlib.util.spec_from_file_location(
        "reverse_probe", os.path.join(HERE, "reverse_probe.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _capture(buses):
    return {"label": "synthetic", "seconds": 1.0, "buses": buses}


def _write(probe, label, buses):
    with open(probe._capture_path(label), "w", encoding="utf-8") as handle:
        json.dump(_capture(buses), handle)


def _diff_json(probe, a, b):
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        probe.diff(a, b, as_json=True)
    return json.loads(buffer.getvalue())


# -- the regression that mattered --------------------------------------------

def test_a_clean_bit_inside_a_noisy_frame_is_still_strong():
    """0x201 carries rpm, so most of it changes constantly - but byte 5 may be the bit.

    Judging the whole frame on its noisiest byte demoted exactly the frames worth
    looking at, which is why this case exists.
    """
    with tempfile.TemporaryDirectory() as tmp:
        probe = _load_probe(tmp)
        # bytes 0-1: a live value that passes through the same readings in both states.
        # byte 5: 0x00 parked, 0x80 in reverse, and nothing else.
        _write(probe, "park", {"can1": {"0x201": {
            "0": {"02": 5, "03": 5, "04": 5},
            "1": {"10": 5, "11": 5},
            "5": {"00": 40},
        }}})
        _write(probe, "reverse", {"can1": {"0x201": {
            "0": {"03": 5, "04": 5, "05": 5},
            "1": {"11": 5, "12": 5},
            "5": {"80": 40},
        }}})

        findings = _diff_json(probe, "park", "reverse")

    assert len(findings) == 1, findings
    assert findings[0]["rank"] == 0, "a clean changed byte must not be demoted"
    assert findings[0]["id"] == "0x201"
    assert findings[0]["bytes"] == [0, 1, 5]
    clean = [d for d in findings[0]["detail"] if d["clean"]]
    assert [d["byte"] for d in clean] == [5]
    assert clean[0]["park"] == ["00"]
    assert clean[0]["reverse"] == ["80"]


def test_a_noisy_byte_that_changes_demotes_the_frame_to_weak():
    with tempfile.TemporaryDirectory() as tmp:
        probe = _load_probe(tmp)
        _write(probe, "park", {"can1": {"0x212": {"2": {"00": 1, "01": 1, "02": 1,
                                                       "03": 1, "04": 1, "05": 1}}}})
        _write(probe, "reverse", {"can1": {"0x212": {"2": {"10": 1, "11": 1, "12": 1,
                                                           "13": 1, "14": 1, "15": 1}}}})

        findings = _diff_json(probe, "park", "reverse")

    assert len(findings) == 1
    assert findings[0]["rank"] == 1, "a byte flickering through six values is not evidence"
    assert findings[0]["clean"] is False


def test_an_identical_frame_is_not_reported_at_all():
    with tempfile.TemporaryDirectory() as tmp:
        probe = _load_probe(tmp)
        same = {"can1": {"0x231": {"0": {"00": 30}, "1": {"40": 30}}}}
        _write(probe, "park", same)
        _write(probe, "reverse", same)

        findings = _diff_json(probe, "park", "reverse")

    assert findings == []


def test_a_frame_present_in_only_one_state_is_listed_but_ranked_last():
    """A module that only talks in reverse is a real candidate, but the weakest kind."""
    with tempfile.TemporaryDirectory() as tmp:
        probe = _load_probe(tmp)
        _write(probe, "park", {"can0": {"0x300": {"0": {"00": 20}}}})
        _write(probe, "reverse", {
            "can0": {"0x300": {"0": {"00": 20}}, "0x3A8": {"0": {"01": 20}}},
        })

        findings = _diff_json(probe, "park", "reverse")

    assert len(findings) == 1, findings
    assert findings[0]["rank"] == 3
    assert findings[0]["id"] == "0x3A8"
    assert findings[0]["only_in"] == "reverse"


def test_strong_candidates_sort_before_weak_ones():
    with tempfile.TemporaryDirectory() as tmp:
        probe = _load_probe(tmp)
        _write(probe, "park", {"can1": {
            "0x212": {"2": {"00": 1, "01": 1, "02": 1, "03": 1, "04": 1, "05": 1}},
            "0x2A0": {"7": {"00": 40}},
        }})
        _write(probe, "reverse", {"can1": {
            "0x212": {"2": {"10": 1, "11": 1, "12": 1, "13": 1, "14": 1, "15": 1}},
            "0x2A0": {"7": {"40": 40}},
        }})

        findings = _diff_json(probe, "park", "reverse")

    assert [f["id"] for f in findings] == ["0x2A0", "0x212"]
    assert [f["rank"] for f in findings] == [0, 1]


# -- the tool must be usable without the capture hardware ---------------------

def test_diffing_saved_captures_needs_no_python_can():
    """Captures are read off the Pi; the analysis usually happens on a laptop."""
    with tempfile.TemporaryDirectory() as tmp:
        probe = _load_probe(tmp)
        assert probe.can is None or hasattr(probe.can, "Bus")
        # Force the "not installed" state and prove the analysis half still works.
        saved, probe.can = probe.can, None
        try:
            _write(probe, "park", {"can1": {"0x2A0": {"7": {"00": 10}}}})
            _write(probe, "reverse", {"can1": {"0x2A0": {"7": {"40": 10}}}})
            findings = _diff_json(probe, "park", "reverse")
        finally:
            probe.can = saved

    assert len(findings) == 1
    assert findings[0]["rank"] == 0


def test_capturing_without_python_can_explains_itself():
    with tempfile.TemporaryDirectory() as tmp:
        probe = _load_probe(tmp)
        saved, probe.can = probe.can, None
        try:
            try:
                probe.capture("x", 0.1)
            except SystemExit as exit_error:
                message = str(exit_error)
            else:
                raise AssertionError("capture should refuse without python-can")
        finally:
            probe.can = saved

    assert "python-can" in message
    assert "diffing saved captures" in message


# -- runner ------------------------------------------------------------------

def main():
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failures = []
    for name, fn in tests:
        try:
            fn()
            print("  PASS  %s" % name)
        except Exception as exc:
            failures.append((name, exc))
            print("  FAIL  %s: %s: %s" % (name, type(exc).__name__, exc))

    print("\n%d/%d passed" % (len(tests) - len(failures), len(tests)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
