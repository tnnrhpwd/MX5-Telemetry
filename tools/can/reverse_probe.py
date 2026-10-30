#!/usr/bin/env python3
"""Find the CAN signal that actually means "reverse" on this car.

Why this exists
---------------
The Pi detects reverse from a negative speed in `0x201`, and the car does not do that:
driving backward still reports a positive speed, so the gear estimator picks 1st and
the ESP never shows `R`. Guessing which frame carries reverse is not realistic - the
NC's backup-lamp switch is reported by a body module, not by the engine ECU - so this
tool records the bus twice and reports exactly which bytes changed between the two
states.

Usage (on the Pi, where python-can and the MCP2515s live)
---------------------------------------------------------
    # 1. engine idling, gearbox in neutral, car stationary
    python3 tools/can/reverse_probe.py capture park --seconds 8

    # 2. select reverse and hold it (brake on, car stationary is fine)
    python3 tools/can/reverse_probe.py capture reverse --seconds 8

    # 3. see what differs
    python3 tools/can/reverse_probe.py diff park reverse

A byte that is *stable within* each capture but *different between* them is a candidate;
the tool sorts those first. Add `--json` for machine-readable output.

Captures live in data/ and are safe to attach to a bug report - they contain no GPS,
VIN or personal data, only raw CAN ids and bytes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

# python-can is only needed to *capture*. Diffing two saved captures needs nothing but
# the standard library, and that is the half you run somewhere comfortable with the JSON
# copied off the Pi - so the import happens in capture() rather than at module level.
try:
    import can
except ImportError:
    can = None

# Overridable so the desk test can point at a temporary directory.
DATA_DIR = os.environ.get(
    "MX5_PROBE_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data"),
)
BUSES = (("can1", "HS-CAN 500k"), ("can0", "MS-CAN 125k"))


def _capture_path(label: str) -> str:
    return os.path.join(DATA_DIR, f"reverse_probe_{label}.json")


def capture(label: str, seconds: float) -> None:
    """Record per-byte value histograms for every id on both buses."""
    if can is None:
        sys.exit("python-can is required to capture: pip install python-can "
                 "(diffing saved captures does not need it)")
    result: dict[str, dict[str, dict[str, int]]] = {}
    listeners = []
    for channel, pretty in BUSES:
        try:
            bus = can.Bus(interface="socketcan", channel=channel)
            listeners.append((channel, pretty, bus))
        except Exception as exc:
            print(f"  ! {channel} ({pretty}) unavailable: {exc}")

    if not listeners:
        sys.exit("no CAN interfaces could be opened")

    print(f"Capturing {seconds:.0f}s - keep the car in the state you are recording...")
    deadline = time.time() + seconds
    try:
        while time.time() < deadline:
            for channel, _pretty, bus in listeners:
                msg = bus.recv(timeout=0.05)
                if msg is None:
                    continue
                key = f"0x{msg.arbitration_id:03X}"
                payload = bytes(msg.data[:8])
                bus_hist = result.setdefault(channel, {})
                id_hist = bus_hist.setdefault(key, {})
                for index, value in enumerate(payload):
                    id_hist.setdefault(str(index), {})
                    slot = id_hist[str(index)]
                    text = f"{value:02X}"
                    slot[text] = slot.get(text, 0) + 1
    finally:
        for _channel, _pretty, bus in listeners:
            bus.shutdown()

    os.makedirs(DATA_DIR, exist_ok=True)
    path = _capture_path(label)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"label": label, "seconds": seconds, "buses": result}, handle, indent=1)

    ids = sum(len(v) for v in result.values())
    print(f"Saved {ids} ids to {path}")


def _diff_one(first: dict, second: dict) -> tuple[bool, list[dict]]:
    """Return (candidate, detail) for one id's byte histograms.

    The id is a candidate when *at least one* changed byte is clean, not when all of them
    are. A frame can carry a perfect reverse bit in byte 5 while bytes 0-1 are a live
    counter or the engine speed; requiring every byte to be clean demoted exactly the
    frames worth looking at. The per-byte flags stay in the detail so the report can name
    the byte that actually carries the signal.
    """
    detail = []
    candidate = False
    for byte in sorted(set(first) | set(second)):
        a = first.get(byte, {})
        b = second.get(byte, {})
        set_a, set_b = set(a), set(b)
        changed = set_a != set_b
        # A real signal is *stable* in each capture and takes a different value in each.
        # A byte that flickers through many values, or passes through the same ones, is
        # not evidence either way.
        stable = max(len(set_a), len(set_b)) <= 4 and not (set_a & set_b)
        detail.append({
            "byte": int(byte),
            "park": sorted(set_a),
            "reverse": sorted(set_b),
            "changed": changed,
            "clean": stable,
        })
        if changed and stable:
            candidate = True
    return candidate, detail


def diff(label_a: str, label_b: str, as_json: bool) -> None:
    with open(_capture_path(label_a), encoding="utf-8") as handle:
        first = json.load(handle)["buses"]
    with open(_capture_path(label_b), encoding="utf-8") as handle:
        second = json.load(handle)["buses"]

    findings = []
    for channel in sorted(set(first) | set(second)):
        ids_a = first.get(channel, {})
        ids_b = second.get(channel, {})
        for can_id in sorted(set(ids_a) | set(ids_b)):
            if can_id not in ids_a:
                findings.append({"bus": channel, "id": can_id, "only_in": label_b, "rank": 3})
                continue
            if can_id not in ids_b:
                findings.append({"bus": channel, "id": can_id, "only_in": label_a, "rank": 3})
                continue
            candidate, detail = _diff_one(ids_a[can_id], ids_b[can_id])
            changed_bytes = [d["byte"] for d in detail if d["changed"]]
            if not changed_bytes:
                continue
            findings.append({
                "bus": channel,
                "id": can_id,
                "bytes": changed_bytes,
                "clean": candidate,
                "detail": detail,
                "rank": 0 if candidate else 1,
            })

    findings.sort(key=lambda f: (f["rank"], f["bus"], f["id"]))

    if as_json:
        print(json.dumps(findings, indent=1))
        return

    label = f"{label_a} -> {label_b}"
    print(f"\nCandidates for a reverse signal ({label})")
    print("=" * 72)
    if not findings:
        print("Nothing differs. Either the state did not change, or the module that")
        print("reports reverse is not on these two buses (check the wiring).")
        return

    strong = [f for f in findings if f.get("rank") == 0]
    weak = [f for f in findings if f.get("rank") == 1]
    other = [f for f in findings if f.get("rank") == 3]

    if strong:
        print("\nSTRONG (each byte is stable within a capture and differs between them):")
        for f in strong:
            for d in f["detail"]:
                if d["changed"] and d["clean"]:
                    print(f"  {f['bus']} {f['id']} byte {d['byte']}: "
                          f"{label_a}={d['park']} {label_b}={d['reverse']}")
    if weak:
        print("\nWEAK (differs, but at least one changed byte is noisy in a state):")
        for f in weak[:20]:
            print(f"  {f['bus']} {f['id']}")
            for d in f["detail"]:
                if d["changed"]:
                    print(f"      byte {d['byte']}: {label_a}={d['park']} "
                          f"{label_b}={d['reverse']}")
    if other:
        print("\nPRESENT IN ONLY ONE CAPTURE:")
        for f in other[:20]:
            print(f"  {f['bus']} {f['id']} only in {f['only_in']}")

    print("\nNext: take the strongest candidate, confirm it toggles on/off with the")
    print("reverse switch (not with speed), then wire it into can_handler.py as")
    print("telemetry.is_in_reverse. See docs/KNOWN_ISSUES.md ISSUE-14.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    cap = sub.add_parser("capture", help="record both buses to data/reverse_probe_<label>.json")
    cap.add_argument("label")
    cap.add_argument("--seconds", type=float, default=8.0)

    dif = sub.add_parser("diff", help="compare two captures")
    dif.add_argument("first")
    dif.add_argument("second")
    dif.add_argument("--json", action="store_true")

    args = parser.parse_args()
    if args.command == "capture":
        capture(args.label, args.seconds)
    else:
        diff(args.first, args.second, args.json)


if __name__ == "__main__":
    main()
