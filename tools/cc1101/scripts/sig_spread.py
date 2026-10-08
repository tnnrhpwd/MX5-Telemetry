#!/usr/bin/env python3
"""What signatures do the logged captures actually produce?

Answers "why does pressing one fob light the other's chip?" by computing the
signature of every recent CAP line EXACTLY as the server does, grouping the
distinct results, and showing what each one would match, using the server's own
scorer. Pure offline analysis - no serial port, so it can run beside the server.

Usage:  python scripts/sig_spread.py [capture-log] [max-captures]
"""
import collections
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import live_readout as L      # noqa: E402

path = sys.argv[1] if len(sys.argv) > 1 else L.CAPTURE_PATH
maxn = int(sys.argv[2]) if len(sys.argv) > 2 else 150

print("capture log:", path)
print("enrolled:")
for name, dev in (L._devices or {}).items():
    print("   %-12s %s" % (name, (dev or {}).get("sig")))
print()

CAP_RE = re.compile(r"CAP\s+\d+\s+\d+\s+([0-9A-Fa-f]+)")

try:
    with open(path, encoding="utf-8", errors="ignore") as f:
        lines = [ln for ln in f if "CAP" in ln]
except OSError as exc:
    print("cannot read the capture log: %s" % exc)
    sys.exit(1)

lines = lines[-maxn:]
print("captures examined:", len(lines))

groups = collections.OrderedDict()
no_sig = 0
for ln in lines:
    m = CAP_RE.search(ln)
    if not m:
        continue
    try:
        runs = L._cap_runs(m.group(1))
        sig = L._signature(runs, 48.0)
    except Exception as exc:                       # noqa: BLE001
        print("  signature failed: %s" % exc)
        continue
    if not sig:
        no_sig += 1
        continue
    key = (sig["short_us"], sig["long_us"], sig["ratio"], sig["period_syms"])
    if key not in groups:
        groups[key] = {"sig": sig, "n": 0}
    groups[key]["n"] += 1

print("produced no signature:", no_sig)
print("distinct signatures :", len(groups))
print()
print("%-5s %-8s %-8s %-7s %-7s %-6s  %s"
      % ("count", "short", "long", "ratio", "period", "runs", "score vs each device"))
for key, g in sorted(groups.items(), key=lambda kv: -kv[1]["n"]):
    s = g["sig"]
    cells = []
    for name, dev in (L._devices or {}).items():
        sc = L._sig_score(s, (dev or {}).get("sig") or {})
        cells.append("%s=%s" % (name, "n/a" if sc is None else "%.2f" % sc))
    print("%-5d %-8s %-8s %-7s %-7s %-6s  %s"
          % (g["n"], s["short_us"], s["long_us"], s["ratio"],
             s["period_syms"], s["n_runs"], "  ".join(cells)))
