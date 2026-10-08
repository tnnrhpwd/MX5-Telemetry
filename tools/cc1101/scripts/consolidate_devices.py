#!/usr/bin/env python3
"""Consolidate repeated enrolments of the same device into one entry.

Re-enrolling one fob produces several entries, and most of them are FRAGMENTS:
a capture that yielded too few pulse runs to be a measurement. They are not
merely clutter. A fragment's stored timings are arbitrary, so they sit within
tolerance of everything and light up on another device's captures - which is
exactly how a Mazda press came to light the Nissan chip.

For each family of names this:

  * drops entries below ENROL_MIN_RUNS as fragments;
  * averages the rest, WEIGHTED by the evidence behind each, so the better
    capture counts for more;
  * keeps the family's shortest name, which also cleans up a typo;
  * reports everything it did.

Names are folded by lowercasing and collapsing repeated letters, so "nisssan
fob 5" and "nissan fob 2" land in the same family without a hardcoded table.

DRY RUN by default. Pass --apply to write. Stop the readout server first, or it
will overwrite the result from memory on its next save.

Usage:  python scripts/consolidate_devices.py [--apply]
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import live_readout as L      # noqa: E402


def norm(name):
    """Lowercase, with runs of the same letter collapsed to one."""
    out = []
    for ch in name.lower():
        if not out or out[-1] != ch:
            out.append(ch)
    return "".join(out)


def family(name):
    """The family key: the folded name with its trailing number removed."""
    parts = norm(name).split()
    while parts and parts[-1].isdigit():
        parts.pop()
    return " ".join(parts)


def show(title, entries):
    print("%s (%d entries):" % (title, len(entries)))
    for name, dev in sorted(entries.items()):
        s = (dev or {}).get("sig") or {}
        print("   %-14s runs=%-4s short=%-7s long=%-8s ratio=%-6s period=%s"
              % (name, s.get("n_runs"), s.get("short_us"), s.get("long_us"),
                 s.get("ratio"), s.get("period_syms")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="write the consolidated file (default: dry run)")
    args = ap.parse_args()

    L._load_devices()
    if L._devices_load_error:
        print("refusing to touch devices.json: %s" % L._devices_load_error)
        return 1

    before = dict(L._devices)
    show("before", before)

    groups = {}
    for name in before:
        groups.setdefault(family(name), []).append(name)

    out, notes = {}, []
    for key, names in sorted(groups.items()):
        if len(names) == 1:
            out[names[0]] = before[names[0]]
            continue
        good = [n for n in names
                if ((before[n] or {}).get("sig") or {}).get("n_runs", 0)
                >= L.ENROL_MIN_RUNS]
        if not good:
            # Nothing trustworthy in the family: keep the strongest single
            # entry rather than inventing an average out of fragments.
            best = max(names, key=lambda n: ((before[n] or {}).get("sig") or {})
                       .get("n_runs", 0))
            out[best] = before[best]
            notes.append("kept %s (no entry in this family had %d runs)"
                         % (best, L.ENROL_MIN_RUNS))
            continue

        keep = min(names, key=len)          # a name carries no evidence
        keep = keep.strip()
        total = sum(((before[n] or {}).get("sig") or {}).get("n_runs", 0)
                    for n in good)
        sig = {"n_runs": total, "period_syms": None, "period_match": 0.0}
        for field in ("short_us", "long_us", "ratio"):
            acc = sum(((before[n] or {}).get("sig") or {}).get(field, 0)
                      * ((before[n] or {}).get("sig") or {}).get("n_runs", 0)
                      for n in good)
            sig[field] = round(acc / total, 2) if total else 0
        # A frame period is only carried over if every contributor agreed on it.
        periods = {((before[n] or {}).get("sig") or {}).get("period_syms")
                   for n in good}
        if len(periods) == 1 and None not in periods:
            sig["period_syms"] = periods.pop()
            sig["period_match"] = min(
                ((before[n] or {}).get("sig") or {}).get("period_match", 0.0)
                for n in good)
        colour = max(good, key=lambda n: ((before[n] or {}).get("sig") or {})
                     .get("n_runs", 0))
        out[keep] = {"color": (before[colour] or {}).get("color")
                     or L._pick_color(keep), "sig": sig}
        dropped = [n for n in names if n not in good]
        notes.append("merged %s <- %s" % (keep, ", ".join(sorted(names))))
        if dropped:
            notes.append("   dropped as fragments (< %d runs): %s"
                         % (L.ENROL_MIN_RUNS, ", ".join(sorted(dropped))))

    print()
    show("after", out)
    print()
    for n in notes:
        print(n)
    print()

    if not args.apply:
        print("DRY RUN - nothing written. Re-run with --apply.")
        return 0

    L._devices = out
    if not L._save_devices(force=True):
        print("WRITE FAILED - the file was left untouched.")
        return 1
    print("written: %s" % L.DEVICES_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main())
