import json
import urllib.request
from collections import Counter

d = json.load(urllib.request.urlopen("http://127.0.0.1:8765/data"))
pts = d.get("points", [])
rssi = [p[1] for p in pts if isinstance(p, (list, tuple)) and len(p) > 1]
print("latest:", d.get("latest"))
print("selected_freq:", d.get("selected_freq"), "selected_mod:", d.get("selected_mod"), "port_error:", d.get("port_error"))
print("num points:", len(rssi))
if rssi:
    tail = rssi[-60:]
    print("last 60 values:")
    for v, c in sorted(Counter(tail).items()):
        print("  %d x %d" % (v, c))
    print("min=%d max=%d" % (min(tail), max(tail)))
