import json
import time
import urllib.request

def post(path, payload):
    req = urllib.request.Request("http://127.0.0.1:8765" + path,
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=3))

def get():
    return json.load(urllib.request.urlopen("http://127.0.0.1:8765/data", timeout=3))

def rssi_avg(n=5):
    vals = []
    for _ in range(n):
        vals.append(get()["latest"]["rssi"])
        time.sleep(0.3)
    return sum(vals) / len(vals)

print("FSK test:")
post("/mod", {"mod": 0}); time.sleep(1)
print("  fsk floor:", rssi_avg())
post("/tx", {"on": True}); time.sleep(1)
print("  fsk + txon:", rssi_avg())
post("/tx", {"on": False}); time.sleep(1)

print("OOK test:")
post("/mod", {"mod": 2}); time.sleep(1)
print("  ook floor:", rssi_avg())
post("/tx", {"on": True}); time.sleep(1)
print("  ook + txon:", rssi_avg())
post("/tx", {"on": False}); time.sleep(1)
print("  ook + txoff:", rssi_avg())
