import json
import urllib.request

d = json.load(urllib.request.urlopen("http://127.0.0.1:8765/data", timeout=3))
print("mod=%s freq=%s rssi=%s raw_captures=%s port_err=%s" % (
    d["selected_mod"], d["selected_freq"], d["latest"]["rssi"],
    d.get("raw_captures"), d.get("port_error")))
pts = d.get("points", [])
r = [p[1] for p in pts if isinstance(p, (list, tuple)) and len(p) > 1]
print("rssi last 40:", r[-40:])
print("events:", d.get("events", [])[-5:])
