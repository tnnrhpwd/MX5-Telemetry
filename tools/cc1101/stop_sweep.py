import json
import time
import urllib.request

def post(path, payload):
    req = urllib.request.Request("http://127.0.0.1:8765" + path,
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(req, timeout=3))
    except Exception as e:
        return {"err": str(e)}

# stop sweep and force back to 315 OOK
print("sweep off ->", post("/sweep", {"on": False}))
time.sleep(0.5)
print("mod 2 ->", post("/mod", {"mod": 2}))
time.sleep(0.5)
print("freq 315 ->", post("/freq", {"mhz": 315.0}))
time.sleep(2)

d = json.load(urllib.request.urlopen("http://127.0.0.1:8765/data", timeout=3))
pts = d.get("points", [])
r = [p[1] for p in pts if isinstance(p, (list, tuple)) and len(p) > 1]
print("rssi last 20:", r[-20:])
print("sweep_mode:", d.get("sweep_mode"))
