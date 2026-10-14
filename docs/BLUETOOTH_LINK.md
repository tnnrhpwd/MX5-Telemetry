# Bluetooth link: the car app without the USB cable

The car app normally reaches the Pi over the USB tether at
`http://192.168.42.100:5000`. That needs the phone plugged in. This adds a Bluetooth
path so the app still works with the cable out, and the app treats Bluetooth as the
**fallback**: it tries the tether first and drops to Bluetooth when the tether is absent.

Two Bluetooth transports exist, and both carry the same protocol:

| | SPP (RFCOMM) | BLE (GATT) |
| --- | --- | --- |
| Cost of the reply | One write per reply | Several notifications per reply |
| Depends on | An SDP service record (`sdptool`) | Nothing but bluez + `bless` |
| Android API | `BluetoothSocket` | `BluetoothGatt` |
| Status | Preferred | The fallback when SDP is unavailable |

SPP is tried first because a reply is a single write, where BLE has to chunk one to the
negotiated MTU. BLE exists because SPP's weak point, the SDP record, is exactly the part
BlueZ has been moving around. If `sdptool` is gone on your install, BLE still works.

## Why not just HTTP over Bluetooth

Bluetooth PAN would give IP over Bluetooth and let the app keep using HTTP unchanged, but
`BluetoothPan` is `@SystemApi` in Android, so a normal app cannot create one. That leaves
a byte stream, and a byte stream wants a line protocol. Hence the protocol below.

## The protocol

One JSON object per line, newline terminated, UTF-8. Requests carry an id, replies echo it.

```
-> {"id": 7, "op": "telemetry"}
<- {"id": 7, "ok": true, "data": {"rpm": 3200, "coolant_temp_f": 190, ...}}

-> {"id": 8, "op": "setting", "name": "shift_rpm", "value": 6800}
<- {"id": 8, "ok": true, "data": {"success": true, "name": "shift_rpm", "value": 6800}}
```

An op that is accepted but whose command is refused comes back as `ok: true` with
`data.success: false`, mirroring the HTTP API's separation of "the link worked" from
"the command was rejected". A malformed line, an unknown op, or an op that raised comes
back as `ok: false` with `error`, the id preserved, and the link left open.

### Operations

| op | Extra fields | Effect |
| --- | --- | --- |
| `hello` | `token` | Authenticates the session. Must be first. |
| `ping` | | Liveness and protocol version. |
| `status` | | Current screen, sleep/demo flags, all settings. |
| `telemetry` | | The full live snapshot (same fields as `GET /api/telemetry`). |
| `screen` | `value` (0-7) | Select a page. |
| `screen.next` / `screen.prev` | | Step a page, wrapping. |
| `setting` | `name`, `value` | Update one setting. |
| `wake` / `sleep` | | Display sleep state. |
| `calibrate_imu` | | Ask the ESP32 to zero its gyro. |
| `roof.status` | | RCNC-2 settings, or `connected: false`. |
| `roof.speed` / `roof.auto` / `roof.mode` | `value` | Set one roof setting. |

### Authentication

The first request must be `hello` with the access token. Pairing is deliberately **not**
treated as the security boundary: pairing makes a device trusted for the profile, it does
not authorise this application's commands, and the Pi may have other paired devices. The
token is the same `MX5_WEB_TOKEN` the HTTP API uses, so there is one secret to distribute,
not two. Five bad tokens in a row close the link.

## Pi setup

### 1. Make the adapter work

```bash
sudo apt install bluez bluez-tools       # provides hciconfig and sdptool
sudo systemctl enable --now bluetooth
bluetoothctl power on
bluetoothctl discoverable on
bluetoothctl pairable on
hciconfig -a                             # note the BD Address
```

`hciconfig -a` must print a `BD Address`. If it does not, the adapter is down or the
kernel has no driver for it, and nothing below will work.

Bluetooth and the CAN interface do not conflict here: `setup_can_bus.sh` leaves
`dtoverlay=disable-bt` commented out, so the UART is not stolen from Bluetooth. If you
ever enable that line to free the UART, the Bluetooth link stops working.

### 2. Install

```bash
cd ~/MX5-Telemetry && git pull
pip install -r requirements.txt
sudo apt install python3-dbus python3-gi      # only needed for the BLE transport
pip install bless                             # only needed for the BLE transport
```

SPP needs no pip package; it uses the stdlib Bluetooth socket.

### 3. Configure

All optional, set in the service environment:

| Variable | Default | Meaning |
| --- | --- | --- |
| `MX5_BT` | `both` | `off`, `spp`, `ble`, or `both` |
| `MX5_BT_TOKEN` | `MX5_WEB_TOKEN` | Access token the link requires |
| `MX5_BT_SPP_CHANNEL` | `3` | RFCOMM channel, must match the SDP record |
| `MX5_BT_ADDRESS` | auto | Local adapter MAC, if `hciconfig` cannot be read |
| `MX5_BT_NAME` | `MX5 Pi Link` | Name advertised over BLE |

### 4. Pair the phone

The link starts with the display app, so:

```bash
sudo systemctl restart mx5-display
journalctl -u mx5-display -n 40 | grep -i -e bluetooth -e SPP -e BLE
```

A healthy start prints a line like `✓ Bluetooth link started (mode=both)` and the
per-transport detail from `describe()`. Then pair from Android's Bluetooth settings and
enter the same token on the app's System screen.

## Verifying each transport on the Pi

Do this before involving the phone, so a failure is attributable.

**SPP.** The SDP record is the fragile part, so check it directly:

```bash
sdptool browse local | grep -A3 -i "Serial Port"
# expect: a record with Service Class ID "Serial Port" and Channel: 3
```

If that is empty, `sdptool add --channel=3 SP` did not take, and Android will not connect.
The startup log says so explicitly if `sdptool` is missing entirely.

**BLE.** Confirm the service is advertised:

```bash
bluetoothctl
  menu advertise      # inspect, then back
```

**Protocol, without Bluetooth at all.** The framing, authentication and every op are
covered by tests that need no Bluetooth stack:

```bash
cd pi/ui/src
python3 test_link_protocol.py         # 46 checks: protocol, service, SPP server over TCP
python3 test_web_server_parity.py /tmp/after.json
```

## Android side

The app exposes a transport abstraction with three implementations: HTTP over the tether,
SPP, and BLE. On start it probes the configured HTTP address; if that fails it falls back
to Bluetooth, preferring SPP and then BLE. The System screen shows which transport is live
and lets you pin one instead of letting it choose.

## When it does not work

| Symptom | Cause |
| --- | --- |
| `sdptool not found` in the log | `bluez-tools` not installed. SPP cannot publish its SDP record; use BLE. |
| `Could not bind RFCOMM channel` | No adapter address found. Check `hciconfig`; or set `MX5_BT_ADDRESS`. |
| `AF_BLUETOOTH is unavailable` | This Python has no Bluetooth socket support. |
| BLE never starts, `bless not installed` | `pip install bless` (plus `python3-dbus`, `python3-gi`). |
| Phone pairs, then every command is refused | Token mismatch. The app's token must equal `MX5_WEB_TOKEN`. |
| Phone connects, then drops after five requests | Five bad tokens closed the link. Check the token, then reconnect. |
| Works over SPP but telemetry is slow over BLE | Expected: a ~1 KB snapshot becomes several notifications. |

## What is verified, and what is not

Verified on a desk, with no Bluetooth hardware:

- The protocol, authentication and every operation (46 checks).
- The whole SPP accept/serve/connection-isolation loop, driven over a TCP socket through
  the server's own injected listener. Only the three lines that create the Bluetooth
  socket are untested.
- That the web API is byte-for-byte unchanged after sharing its logic with this link:
  40 requests across every endpoint, comparing status, body and side effects.
- That a machine with no Bluetooth at all reports both transports as unavailable and
  keeps everything else running.

**Not verified, because it needs the Pi and a phone:**

- That `sdptool add` publishes a record Android will find on your BlueZ version.
- That the BLE GATT server registers and advertises under the real BlueZ.
- Anything at all on the app side of the link.
