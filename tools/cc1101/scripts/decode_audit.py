"""Run the live decoder over every logged capture and show what it emits.

The complaint this answers: two physically different fobs reported the SAME
code. Either the decoder is finding a real shared structure, or it is emitting a
constant regardless of input. Those two explanations need opposite fixes, and
the per-capture table tells them apart at a glance - if a column of wildly
different inputs all produce one output, the decoder is degenerate, not clever.

Usage:
  python decode_audit.py [path-to-capture-log]
"""

import collections
import os
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import live_readout as L      # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LOG = os.path.join(HERE, "..", "captures", "capture_live.txt")


def main():
    log = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_LOG
    caps = []
    with open(log, "r", errors="ignore") as f:
        for line in f:
            m = re.search(r"CAP\s+(\d+)\s+(\d+)\s+([0-9A-Fa-f]+)", line)
            if m:
                caps.append((int(m.group(1)), int(m.group(2)), m.group(3)))
    print("read %d CAP lines from %s" % (len(caps), log))
    print("")
    print("%-5s %-7s %-8s %-10s %-12s" % ("idx", "runs", "high%", "code", "bit_us"))

    codes = collections.Counter()
    for i, (total, total_us, hexstr) in enumerate(caps):
        sample_us = float(total_us) / float(total)
        runs = L._cap_runs(hexstr)
        high = 100.0 * sum(1 for c in hexstr for k in (3, 2, 1, 0)
                           if (int(c, 16) >> k) & 1) / (4 * len(hexstr))
        d = L.decode_cap(hexstr, sample_us)
        if d:
            code, unit_samples, nbursts = d
            codes[code] += 1
            print("%-5d %-7d %-8.1f %-10s %-12d  (%d frames)"
                  % (i, len(runs), high, code, round(unit_samples * sample_us),
                     nbursts))
        else:
            codes["(no decode)"] += 1
            print("%-5d %-7d %-8.1f %-10s" % (i, len(runs), high, "-"))

    print("")
    print("distinct outputs: %d" % len(codes))
    for code, n in codes.most_common(10):
        print("  %-12s x%d" % (code, n))


if __name__ == "__main__":
    main()
