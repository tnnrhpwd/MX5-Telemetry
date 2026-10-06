import json
import urllib.request

d = json.load(urllib.request.urlopen("http://127.0.0.1:8765/data", timeout=3))
scan = d.get("scan", {})
# show values around 315 and 433
for target in [313, 314, 315, 316, 317, 430, 433, 434, 435]:
    key = str(float(target))
    print("  %s MHz -> %s" % (target, scan.get(key, "n/a")))
print("--- all 310-320 ---")
for f in range(310, 321):
    print("  %d -> %s" % (f, scan.get(str(float(f)), "n/a")))
