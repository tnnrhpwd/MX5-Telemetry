import json
import time
import urllib.request

def post(path):
    req = urllib.request.Request("http://127.0.0.1:8765" + path, data=b"{}",
                                 headers={"Content-Type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(req, timeout=3))
    except Exception as e:
        return {"err": str(e)}

def get():
    return json.load(urllib.request.urlopen("http://127.0.0.1:8765/data", timeout=3))

print("baseline:", get()["latest"]["rssi"])
print("POST /fobburst ->", post("/fobburst"))
# watch rssi during the burst (it lasts ~250ms total for 3 frames)
vals = []
t0 = time.time()
while time.time() - t0 < 3:
    d = get()
    vals.append((round(time.time() - t0, 2), d["latest"]["rssi"]))
    time.sleep(0.05)
print("rssi during burst window:")
for t, r in vals:
    print("  %.2fs %s" % (t, r))
time.sleep(1)
d = get()
print("events after:", d.get("events", [])[-5:])
