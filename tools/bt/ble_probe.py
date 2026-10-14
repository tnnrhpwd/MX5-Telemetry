#!/usr/bin/env python3
"""Prove the Pi's BLE transport end to end, from any machine that has a Bluetooth radio.

The Android app is the real client, but working out whether the Pi's GATT server actually
answers by perching a phone in a car is slow, and when it fails it cannot tell you which
end is at fault. This speaks the same protocol over the same service, so a success here
narrows anything still wrong to the phone, and a failure here is the Pi's side.

It matters because "the link started" is the Pi's own claim. The app logs that as soon as
one transport comes up, which says nothing about whether a central can connect, write, or
be notified. This is the check that actually exercises those three things.

Two deliberate choices:

* The service is found by UUID, not by name. An adapter's advertised name is the host's
  name (``raspberrypi`` here), not the ``MX5_BT_NAME`` the link sets, so matching on a name
  is the kind of guess that fails for a reason that looks like a real fault.
* It only sends read-only ops. Pointed at a car that is switched on and in use it cannot
  change a setting, move the screen, or reach the roof.

Usage:
    python tools/bt/ble_probe.py                    # takes the token from the Pi itself
    python tools/bt/ble_probe.py --token <token>
    python tools/bt/ble_probe.py --list-only        # just report what this radio can see
    python tools/bt/ble_probe.py --name raspberrypi # fall back to matching a device name
"""

import argparse
import asyncio
import json
import os
import sys
import time

try:
    from bleak import BleakClient, BleakScanner
except ImportError as e:
    # Report the real exception. Catching ImportError and declaring bleak "missing"
    # turned a broken install into a phantom absent one, which is a different fix and a
    # wrong one to chase - the same mistake the rest of these tools were just cured of.
    print("Cannot import the BLE client: %s" % e)
    print()
    print("If bleak really is not installed, install it:")
    print("    pip install bleak")
    print("If it is installed, the error above is the real fault, not a missing package.")
    raise SystemExit(2)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Must match pi/ui/src/bt_ble_server.py. The client writes request lines to RX and is
# notified reply lines on TX; both are newline terminated JSON objects.
SERVICE_UUID = '6d783500-0001-4d58-3535-4d583554454c'
RX_UUID = '6d783500-0002-4d58-3535-4d583554454c'
TX_UUID = '6d783500-0003-4d58-3535-4d583554454c'

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"


# Windows consoles default to cp1252, which cannot encode the glyphs this may print from
# the Pi's output. doctor.py learned this the hard way; do it before anything prints.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def token_from_pi():
    """Return (token, error). Reads the value the app is actually running with.

    Same reasoning as tools/bt/doctor.py: a token that never reached the process is
    invisible from anywhere else, so the running process is the only authoritative place
    to look. It is also the only place that needs no extra copy of the secret on disk.
    """
    try:
        sys.path.insert(0, REPO_ROOT)
        from tools.lib.pi_ssh import connect
    except ImportError as e:
        return None, "cannot import the SSH helper (%s)" % e

    try:
        ssh = connect(timeout=10)
    except Exception as e:
        return None, "cannot reach the Pi (%s)" % e

    try:
        cmd = ("PID=$(pgrep -f 'python.*main.py' | head -1); "
               "if [ -z \"$PID\" ]; then echo __NOPID__; else "
               "tr '\\0' '\\n' < /proc/$PID/environ "
               "| grep -E '^MX5_(WEB_TOKEN|BT_TOKEN)=' | head -1; fi")
        _, out, _ = ssh.exec_command(cmd, timeout=20)
        text = out.read().decode("utf-8", "replace").strip()
    finally:
        ssh.close()

    if "__NOPID__" in text:
        return None, "the display app is not running on the Pi"
    if "=" not in text:
        return None, "the Pi's process environment has no MX5_WEB_TOKEN or MX5_BT_TOKEN"
    return text.split("=", 1)[1].strip(), None


async def scan(seconds):
    """Return [(device, service_uuids)] for everything advertising nearby.

    bleak changed the shape of discover()'s result between versions, so cope with both
    rather than pinning the probe to one.
    """
    try:
        found = await BleakScanner.discover(timeout=seconds, return_adv=True)
    except TypeError:
        found = await BleakScanner.discover(timeout=seconds)

    if isinstance(found, dict):
        return [(dev, list(getattr(adv, "service_uuids", None) or []))
                for dev, adv in found.values()]
    return [(dev, []) for dev in found]


def describe_scan(seen):
    """Print what was seen. A discovery failure should be attributable, not mysterious."""
    if not seen:
        print("       (nothing advertising at all)")
        return
    for dev, uuids in seen:
        print("       %-40s %s" % (dev.name or "(unnamed)", dev.address))
        for u in uuids:
            print("           services: %s" % u)


async def find_pi(seconds, name_hint):
    """Find the Pi by service UUID, falling back to a name match with a warning."""
    seen = await scan(seconds)

    matches = [(d, u) for d, u in seen
               if any(x.lower() == SERVICE_UUID for x in u)]
    if matches:
        return matches[0][0], seen, "advertises the MX5 service"

    if name_hint:
        by_name = [(d, u) for d, u in seen
                   if (d.name or "").lower() == name_hint.lower()]
        if by_name:
            return by_name[0][0], seen, "matched by name %r, not by service UUID" % name_hint

    return None, seen, None


class Link(object):
    """The JSON-line protocol over GATT, with request ids correlated to replies.

    Notifications arrive in MTU-sized chunks, so a reply may take several of them. The
    buffer accumulates until a newline appears, which is the framing the server relies on.
    """

    def __init__(self, client, write_with_response=True):
        self.client = client
        self.write_with_response = write_with_response
        self._buffer = bytearray()
        self._lines = asyncio.Queue()
        self._next_id = 0

    def _on_notify(self, _characteristic, data):
        self._buffer.extend(bytes(data))
        while b"\n" in self._buffer:
            line, _, rest = bytes(self._buffer).partition(b"\n")
            self._buffer = bytearray(rest)
            self._lines.put_nowait(line)

    async def start(self):
        await self.client.start_notify(TX_UUID, self._on_notify)

    async def request(self, op, timeout=8.0, **fields):
        self._next_id += 1
        request_id = self._next_id
        message = {"id": request_id, "op": op}
        message.update(fields)

        await self.client.write_gatt_char(
            RX_UUID, (json.dumps(message) + "\n").encode("utf-8"),
            response=self.write_with_response)

        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise asyncio.TimeoutError(
                    "no reply to id=%d op=%s within %.1fs"
                    % (request_id, op, timeout))
            line = await asyncio.wait_for(self._lines.get(), remaining)
            try:
                reply = json.loads(line.decode("utf-8", "replace"))
            except ValueError:
                # A blank line or a fragment; the next chunk completes it.
                continue
            if reply.get("id") == request_id:
                return reply


async def run(args):
    results = []

    def record(status, name, detail="", hint=""):
        results.append(status)
        print("[%s] %s" % (status, name))
        if detail:
            for line in str(detail).splitlines():
                print("       " + line)
        if hint:
            print("       -> " + hint)

    print("MX5 BLE link probe")
    print("=" * 70)

    if args.list_only:
        print("Scanning for %.0fs..." % args.scan)
        seen = await scan(args.scan)
        describe_scan(seen)
        return 0

    # -- token -----------------------------------------------------------------
    token = args.token or os.environ.get("MX5_WEB_TOKEN", "").strip()
    if token:
        record(PASS, "Access token", "supplied, %d chars (value not printed)" % len(token))
    else:
        token, error = token_from_pi()
        if token:
            record(PASS, "Access token", "read from the Pi's running app, %d chars" % len(token))
        else:
            record(FAIL, "Access token", error or "no token",
                   "pass --token, set MX5_WEB_TOKEN, or start the display app on the Pi")
            return 1

    # -- discovery -------------------------------------------------------------
    print("Scanning for %.0fs..." % args.scan)
    device, seen, reason = await find_pi(args.scan, args.name)
    if device is None:
        record(FAIL, "Pi advertising the MX5 service",
               "not found among %d advertising device(s)" % len(seen))
        describe_scan(seen)
        print("       -> check the app logged 'Bluetooth link started' (tools/bt/doctor.py),")
        print("          and that the Pi is advertising: busctl get-property org.bluez")
        print("          /org/bluez/hci0 org.bluez.LEAdvertisingManager1 ActiveInstances")
        return 1
    record(PASS, "Pi advertising the MX5 service",
           "%s (%s), %s" % (device.name or "(unnamed)", device.address, reason))

    if reason and "by name" in reason:
        record(WARN, "Matched by name rather than service UUID",
               "the service is not in its advertisement, so this may be the wrong device")

    # -- connect ---------------------------------------------------------------
    # Write with response, matching the Android client's WRITE_TYPE_DEFAULT.
    async with BleakClient(device) as client:
        record(PASS, "Connected over BLE", "mtu=%s" % getattr(client, "mtu_size", "?"))

        link = Link(client, write_with_response=True)
        try:
            await link.start()
            record(PASS, "Subscribed to replies (TX)", TX_UUID)
        except Exception as e:
            record(FAIL, "Subscribed to replies (TX)", str(e),
                   "the reply characteristic or its CCCD is missing; check bt_ble_server.py")
            return 1

        # -- authenticate ------------------------------------------------------
        try:
            reply = await link.request("hello", token=token)
        except asyncio.TimeoutError as e:
            record(FAIL, "hello accepted", str(e),
                   "the Pi accepted the write but never replied; check the journal for "
                   "'BLE link'")
            return 1
        except Exception as e:
            record(FAIL, "hello accepted", str(e),
                   "the write was refused; the Android client writes with response, so "
                   "this is what it would see too")
            return 1

        if reply.get("ok") and reply.get("data", {}).get("ok", True):
            record(PASS, "hello accepted", "authenticated")
        else:
            record(FAIL, "hello accepted", json.dumps(reply),
                   "the token does not match the Pi's MX5_WEB_TOKEN")
            return 1

        # -- the read-only ops -------------------------------------------------
        for op, summarise in (
            ("ping", lambda d: "pong" if d else json.dumps(d)),
            ("status", lambda d: "screen=%s sleep=%s demo=%s settings=%d"
                                 % (d.get("screen"), d.get("sleep"), d.get("demo"),
                                    len(d.get("settings") or {}))),
            ("telemetry", lambda d: "rpm=%s coolant=%s speed=%s"
                                    % (d.get("rpm"), d.get("coolant_temp_f"),
                                       d.get("speed_mph"))),
        ):
            try:
                reply = await link.request(op)
            except Exception as e:
                record(FAIL, "%s answered" % op, str(e))
                continue

            if not reply.get("ok", False):
                record(FAIL, "%s answered" % op, json.dumps(reply))
                continue

            data = reply.get("data") or {}
            record(PASS, "%s answered" % op, summarise(data))

    print("=" * 70)
    fails = results.count(FAIL)
    print("%d checks: %d pass, %d warn, %d fail"
          % (len(results), results.count(PASS), results.count(WARN), fails))
    if fails:
        print("\nThe Pi's BLE transport is not serving. It is the Pi's side, not the "
              "phone's.")
    else:
        print("\nThe Pi's GATT server connects, authenticates and answers. Anything left "
              "is the phone's side.")
    return 1 if fails else 0


def main():
    parser = argparse.ArgumentParser(description="Prove the Pi's BLE transport end to end")
    parser.add_argument("--token", help="access token; otherwise read from the Pi")
    parser.add_argument("--name", default=None,
                        help="device name to fall back on if the service UUID is not "
                             "advertised")
    parser.add_argument("--scan", type=float, default=8.0,
                        help="scan duration in seconds (default 8)")
    parser.add_argument("--list-only", action="store_true",
                        help="report what this radio can see, then stop")
    args = parser.parse_args()

    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
