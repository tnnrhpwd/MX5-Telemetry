import json
import time
import urllib.request

def post(path):
    req = urllib.request.Request("http://127.0.0.1:8765" + path, data=b"{}",
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=3))

def get():
    return json.load(urllib.request.urlopen("http://127.0.0.1:8765/data", timeout=3))

print("POST /scan ->", post("/scan"))
for i in range(60):
    time.sleep(1)
    d = get()
    scan = d.get("scan", {})
    if not d.get("scan_active") and scan:
        break
print("scan points=%d" % len(scan))
peaks = sorted(scan.items(), key=lambda kv: kv[1], reverse=True)[:10]
print("strongest:", [(k, v) for k, v in peaks])
for f in [313, 314, 315, 316, 317, 432, 433, 434]:
    print("  %s -> %s" % (f, scan.get(str(float(f)), "n/a")))
live = {k: v for k, v in scan.items() if v < -20}
print("non-saturated points:", len(live))
print("done")
