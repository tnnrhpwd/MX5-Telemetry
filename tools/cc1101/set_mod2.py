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

def get():
    return json.load(urllib.request.urlopen("http://127.0.0.1:8765/data", timeout=3))

print("POST /mod 2 ->", post("/mod", {"mod": 2}))
time.sleep(1)
for i in range(8):
    d = get()
    print("mod=%s freq=%s rssi=%s" % (d.get("selected_mod"), d.get("selected_freq"), d.get("latest", {}).get("rssi")))
    time.sleep(1)
