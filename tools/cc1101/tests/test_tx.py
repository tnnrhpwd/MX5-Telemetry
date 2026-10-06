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

print("baseline rssi:", get()["latest"]["rssi"])
print("TXON ->", post("/tx", {"on": True}))
time.sleep(1)
for i in range(5):
    print("  rssi (tx on):", get()["latest"]["rssi"])
    time.sleep(0.4)
print("TXOFF ->", post("/tx", {"on": False}))
time.sleep(1)
for i in range(5):
    print("  rssi (tx off):", get()["latest"]["rssi"])
    time.sleep(0.4)
