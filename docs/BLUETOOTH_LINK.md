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

**With no token configured the link refuses to start.** The web server has a safe answer to
a missing token, because it can bind to the loopback address, and a radio has no loopback:
the same omission here would mean that any device which pairs can drive the screen, every
setting, and the roof. So the link logs why and stays shut. `MX5_BT_ALLOW_NO_TOKEN=1` is the
deliberate opt-out, for a bench test over a pipe you trust rather than for a car.

Under systemd the token only arrives if the unit loads it, which is why setup step 3 comes
before pairing.

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

**Do the token first, because nothing works without it.** The unit ships with its
`EnvironmentFile` line commented out, so the display app starts with no token at all: the
web remote quietly falls back to localhost-only, and the Bluetooth link **refuses to start**
(see Authentication below). Create the file and enable it:

```bash
TOKEN=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')
printf 'MX5_WEB_TOKEN=%s\n' "$TOKEN" > ~/MX5-Telemetry/pi/.web-env
chmod 600 ~/MX5-Telemetry/pi/.web-env
sudo sed -i 's|^# *EnvironmentFile=.*|EnvironmentFile=/home/pi/MX5-Telemetry/pi/.web-env|' \
  /etc/systemd/system/mx5-display.service
sudo systemctl daemon-reload
cat ~/MX5-Telemetry/pi/.web-env      # this is the value to type into the phone
```

`pi/.web-env` is gitignored, which is the point: the token is per-install, not per-repo.

Everything below is optional, and also belongs in that environment:

| Variable | Default | Meaning |
| --- | --- | --- |
| `MX5_BT` | `both` | `off`, `spp`, `ble`, or `both` |
| `MX5_BT_TOKEN` | `MX5_WEB_TOKEN` | Access token the link requires |
| `MX5_BT_ALLOW_NO_TOKEN` | unset | `1` lets the link run with **no** token at all. Refused by default. |
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
python3 test_link_protocol.py         # 47 checks: protocol, service, SPP server over TCP
python3 test_web_server_parity.py /tmp/after.json
```

## How it is built

The protocol is split from the transports on both sides, so the profile is the only thing
that differs between SPP and BLE.

**Pi** (`pi/ui/src/`):

| File | Role |
| --- | --- |
| `link_service.py` | Every read and command, with no transport in it |
| `link_protocol.py` | The JSON-line protocol, plus `StreamLink`: bytes in, bytes out |
| `bt_spp_server.py` | RFCOMM server, with an injectable listener so it is testable on a desk |
| `bt_ble_server.py` | GATT server, via `bless` |
| `bt_link.py` | Starts both, configured by environment, contains failures |
| `test_link_protocol.py` | 47 checks that need no Bluetooth at all |

`web_server.py` no longer holds any of this logic: its routes and the Bluetooth link are
two adapters over `LinkService`. Because that meant rewriting a working API, it was proved
safe by capturing every response **and its side effects** before and after — 40 requests
across every endpoint, comparing status, body, and whether the screen actually moved and
the setting actually applied. 40 cases, 0 differing.

**Android** (`android/mx5-remote/src/main/java/com/mx5/remote/`):

| File | Role |
| --- | --- |
| `LinkTransport.java` | One way of reaching the Pi |
| `HttpTransport.java` | The tether |
| `BtTransport.java` | Shared framing, authentication, and path-to-op translation |
| `SppTransport.java` | RFCOMM client |
| `BleTransport.java` | GATT client |
| `BtDevices.java` | Finding the Pi among the paired devices |
| `PiClient.java` | Owns the ordered chain and the failover |

`PiClient`'s public methods are deliberately unchanged from when it was HTTP-only, so no
screen had to be touched. Every request the screens make is still expressed as a path, and
the Bluetooth transports translate that into a protocol op internally.

### How the failover behaves

The chain is ordered `HTTP, SPP, BLE`. The transport that last worked is remembered and
tried first, so the normal case costs one attempt; the rest are only tried after that one
fails. When every transport has failed the client backs off for four seconds, so a poll
loop does not re-walk three dead links twenty times a second.

One distinction matters more than any other. A **refusal** — the Pi answered and said no,
which includes any HTTP status code — must never cause a fallback. If it did, an
out-of-range value would silently move a working link onto a slower transport and nothing
on screen would say so. Refusals are therefore a distinct exception type, and the
Bluetooth transports classify `ok: false` as one.

### Permissions

`BLUETOOTH_CONNECT` is requested once at startup on Android 12 and later; the legacy
`BLUETOOTH`/`BLUETOOTH_ADMIN` pair is capped at API 30. `BLUETOOTH_SCAN` is deliberately
**not** requested: the Pi must be paired before either profile can be used, and connecting
to an already-bonded device needs no scan, so the app never scans. Refusing the permission
is a legitimate choice and is reported rather than nagged about.

## The mimic harness

Iterating a car UI by installing onto a phone and squinting at it is slow, and it needs the
phone held sideways. `android/mimic/` renders the app in a browser at the resolution the
head unit gets, so the design can be screenshotted and measured directly.

```bash
cd android/mimic
python extract_tokens.py          # regenerate tokens.js from the Java sources

# then open, no server needed:
#   index.html?screen=rpm&scheme=ocean&mode=light
#   index.html?all=1              # all nine screens at half scale, for consistency
#   index.html?narrow=1&drawer=1  # the phone shell, drawer open
#   index.html?battery=8          # battery states; also &charging=1 and &clock=14:32
```

It renders two canvases, because the app has two shells: 800x480 for the car, and 400x832
when you pass `narrow=1`. Rendering the phone shell in the car's frame clips the drawer and
makes a working layout look broken, which is worth remembering before believing a
screenshot.

`battery`, `charging` and `clock` exist so a screenshot is reproducible. A real clock in a
screenshot makes two runs differ for no reason, which is how a real regression gets missed.

`extract_tokens.py` reads the twelve schemes, both mode palettes, the fixed alert colours,
the four blend fractions, the type scale and the spacing ramp **out of `Palette.java` and
`Ui.java`**, and `mimic.js` reimplements Java's `mix`/`lift`/`sink`/`alpha` to derive the
rest. Nothing is hand-copied, so a palette change cannot leave the harness behind. Re-run it
after touching either file.

**What it cannot do.** The DOM is hand-written to mirror the Java view code, and that is the
one place the two can disagree. The harness is a design tool, not a substitute: the Java
stays the source of truth and the device stays the final check. It is also a browser, so it
says nothing about Android's own measurement or drawing.

## One command instead of five

Stages 0-4 below are five separate SSH commands, and each one is a place to misread a
result. `tools/bt/doctor.py` runs them all in a single pass, from the machine you are
sitting at:

```bash
python tools/bt/doctor.py                     # the configured Pi
python tools/bt/doctor.py --host 10.62.26.67   # the hotspot address
```

It reports PASS / WARN / FAIL per check alongside the command it ran, so a failure is
attributable instead of re-derived. Two checks are worth knowing about:

- It reads the token out of the **running process's own environment**, not out of a config
  file. A token that never reached the app is invisible from everywhere else, and it fails
  silently in two different ways (the web remote drops to localhost-only, the link refuses
  to start).
- It separates `sdptool` being missing from the SDP record being missing, because those
  have the same symptom and different fixes.

Run it first. If it is clean, start the full test at Stage 4.

## Full system test

Run this when the car is available and the Pi is reachable. It is written to be done in
order, because each stage depends on the one before it, and it tests the failure and
recovery paths as well as the happy one — a link that only works on the first attempt is
not a link you can rely on in a car.

```bash
PI=pi@192.168.1.23          # or pi@mx5pi.local, or the tether address
BRANCH=main
```

### Stage 0 — the Pi is healthy before any of this is about Bluetooth

```bash
ssh $PI 'uptime; vcgencmd measure_temp; systemctl is-active mx5-display'
ssh $PI 'ip -brief addr show | grep -v "^lo"'      # expect usb0 when tethered
ssh $PI 'journalctl -u mx5-display -n 30 --no-pager'
```

Confirm the CAN interfaces are up and the display app is running first. If the app is not
running nothing below can work, and you would otherwise spend the time blaming Bluetooth.

### Stage 1 — deploy

```bash
ssh $PI "cd ~/MX5-Telemetry && git fetch && git checkout $BRANCH && git pull"
ssh $PI 'cd ~/MX5-Telemetry && pip install -r requirements.txt'
ssh $PI 'sudo apt install -y bluez bluez-tools'
ssh $PI 'sudo systemctl restart mx5-display'
sleep 5
ssh $PI 'journalctl -u mx5-display -n 40 --no-pager | grep -iE "bluetooth|SPP|BLE|link"'
```

Expect `✓ Bluetooth link started (mode=both)` plus the per-transport detail. If it says the
link did not start, the reason is printed — `no token configured`, `sdptool not found`,
`Could not bind RFCOMM channel`, `bless not installed` — and the matching row of the table
below applies. **Fix it here rather than continuing**, because every later stage assumes it.

### Stage 2 — the protocol, with no radio involved

This separates the protocol from Bluetooth, so that a later failure is definitely about
Bluetooth.

```bash
ssh $PI 'cd ~/MX5-Telemetry/pi/ui/src && python3 test_link_protocol.py'
```

Expect `47/47 passed`.

### Stage 3 — the SDP record, which is the fragile part

```bash
ssh $PI 'sdptool browse local | grep -B2 -A8 -i "Serial Port"'
```

Expect a record with Service Class ID `Serial Port` and `Channel: 3`. **If that is empty,
SPP will not work from Android**, because `createRfcommSocketToServiceRecord` performs a
lookup for it before it will connect. Do not go to the phone yet: try
`sudo sdptool add --channel=3 SP` and re-check, and if your BlueZ version has removed
`sdptool`, use the BLE transport, which needs no SDP at all.

### Stage 4 — pair

```bash
ssh $PI 'bluetoothctl show | grep -E "Powered|Discoverable|Pairable"'
```

Pair from the phone's Bluetooth settings, then confirm on the Pi:

```bash
ssh $PI 'bluetoothctl info'      # expect the phone, Paired: yes, Trusted: yes
```

If it will not pair, that is a Pi or OS problem and nothing downstream can work.
`bluetoothctl` interactively with `agent on`, `default-agent`, `scan on` is the fallback.

### Stage 5 — the link, on the phone, with the cable out

Unplug the USB cable. That is the whole point: the app must not need it.

On the app's **System** screen, the footer should stop showing
`http://192.168.42.100:5000` and start showing `Bluetooth SPP` (or `Bluetooth LE`), and
the pill should read **LINKED** rather than OFFLINE.

If the footer shows a Bluetooth profile but the pill is OFFLINE, the profile connected and
the protocol failed, which is a token problem: check the token on the System screen
against `MX5_WEB_TOKEN`. And on the Pi:

```bash
ssh $PI 'journalctl -u mx5-display -n 20 --no-pager | grep -i "SPP peer"'
```

Expect `SPP peer connected`.

### Stage 6 — telemetry, Pi to phone

With the cable still out, **Overview**, **RPM** and **Engine** must show live values that
move with the engine, not zeros. Compare a couple against the Pi's own source:

```bash
ssh $PI 'curl -s -H "Authorization: Bearer $MX5_WEB_TOKEN" http://127.0.0.1:5000/api/telemetry | head -c 400'
```

The point is not that numbers appear, it is that **the same numbers** appear. A link
carrying stale or zeroed telemetry looks identical to a working one until you drive.

### Stage 7 — settings, head unit to phone to Pi

This is the direction that is easy to get wrong, and the one that proves the loop.

1. On the **Pioneer**, change something with a visible effect: **Shift at**, or
   **Brightness**.
2. Confirm it actually took, rather than merely being logged:

```bash
ssh $PI 'curl -s -H "Authorization: Bearer $MX5_WEB_TOKEN" http://127.0.0.1:5000/api/status'
```

The `settings` block must show the new value. The response body is the evidence; a log
line is not, because a rejected setting logs too.

3. Change the **screen** from the head unit and confirm the Pi's own display follows. That
   proves commands travel the same path as settings.

### Stage 8 — the roof, if the RCNC-2 is connected

The roof is the one device at the far end of the Pi, so it proves the whole chain: head
unit → phone → Pi → serial port.

Switch the mode to **Valet** and back on the app's **Roof** screen, then:

```bash
ssh $PI 'ls -l /dev/ttyACM* /dev/ttyUSB*'
ssh $PI 'curl -s -H "Authorization: Bearer $MX5_WEB_TOKEN" http://127.0.0.1:5000/api/roof/status'
```

`connected` must be true and `mode` must match what you set. A `503` here means the Pi
cannot see the controller, which is a serial problem, not a Bluetooth one.

### Stage 9 — failure and recovery, which is the point of a fallback

Do these deliberately. A fallback that has never been exercised is a fallback you do not
have.

| Do this | Expect |
| --- | --- |
| Plug the cable back in | Within a few seconds the footer returns to the address; the tether is preferred again |
| Unplug it again | Falls back to Bluetooth on its own, without restarting the app |
| `sudo systemctl stop bluetooth` on the Pi | App goes OFFLINE with a reason, and recovers when Bluetooth starts again |
| Pair a second phone and connect both | Each gets its own session and authenticates separately; neither sees the other's replies |
| Enter a bad token on the System screen | Refused, and after five attempts the link closes rather than retrying for ever |
| Send an out-of-range setting | Refused **without** the footer changing transport |
| Leave the app open and drive out of range | Goes OFFLINE, then reconnects on return without a restart |
| Reboot the Pi with the app connected | The app recovers once the display app and the link come back |

That last row finds the bugs, because the adapter and the SDP record both have to come back
in the right order.

### Stage 10 — in the car, on the road

Everything above can pass on a desk. This is the only stage that tests the radio in the
presence of a car.

- Rev the engine and watch the tachometer keep up. BLE will be visibly slower than SPP, and
  SPP slower than the cable.
- Drive out of range and back, and confirm recovery without touching the phone.
- **Measure the drain rather than estimating it.** The header now shows the phone's own
  charge level, which is what makes this measurable: note it when you start, leave the app
  open for an hour with the cable out, and note it again. A 4 Hz poll over Bluetooth is not
  free, and one hour of it is the number worth having. Take the same measurement on the
  tether, and once more with the app closed, so that you know what **the link** costs rather
  than what the phone costs.
- Check the phone's temperature after the same hour. A phone in a car cradle in summer is
  already hot, and this is the stage that tells you whether the link makes it worse.
- Confirm the head unit still treats it as a parked app and does not dim or block it once
  the car is moving.

## When it does not work

| Symptom | Cause |
| --- | --- |
| The Pi passes every check, but the phone still shows OFFLINE | Check the app's build before the link. `BleTransport.java` is recent, so a build from before it has no BLE transport, and SPP cannot work on this Pi, leaving the app no route to the Pi however healthy the Pi looks. An HCI capture settles it: a real client sends an ATT **MTU request** and a **CCCD write** (handle `0x2902`), and a phone that sends neither is not running this transport. |
| `sdptool not found` in the log | `bluez-tools` not installed. SPP cannot publish its SDP record; use BLE. |
| `sdptool browse local` shows no Serial Port record | The record was never published, so Android will not connect over SPP. Use BLE. |
| `RFCOMM channel N is already in use` | Something else holds that channel. On stock BlueZ `bluetoothd` reserves **channel 3** for its SAP plugin, so the shipped default collides with the daemon and SPP can never start. Choose a free channel with `MX5_BT_SPP_CHANNEL`; do not set `MX5_BT_ADDRESS` for this, the address is not the problem. |
| `Could not bind RFCOMM channel`, with no address in the message | No adapter address found. Check `hciconfig`; or set `MX5_BT_ADDRESS`. |
| `sdptool add ... exited 255`, or `sdptool browse local` cannot reach the SDP server | The local SDP server is unreachable, so no record was published and Android's SDP lookup will fail no matter how healthy RFCOMM looks. No setting fixes this; use BLE, which needs no SDP. |
| `AF_BLUETOOTH is unavailable` | This Python has no Bluetooth socket support. |
| BLE never starts, `bless not installed` | `pip install bless` (plus `python3-dbus`, `python3-gi`). |
| `pip install bless` stalls, or `packaging dbus-fast` never finishes | Current `bless` wants `bleak>=0.19`, and that bleak wants `dbus-fast`, which pip compiles from source on the Pi. Install `bless==0.2.6` with `bleak==0.18.0` instead: 0.2.x uses `dbus-next` (pure Python) and exposes the same `BlessServer` API. |
| Link does not start, log says `no token configured` | The unit has no `EnvironmentFile`, so `MX5_WEB_TOKEN` never reached the display app. See setup step 3. |
| Every command is accepted with no token entered | `MX5_BT_ALLOW_NO_TOKEN=1` is set. Remove it, or set a token. |
| Phone pairs, then every command is refused | Token mismatch. The app's token must equal `MX5_WEB_TOKEN`. |
| Phone connects, then drops after five requests | Five bad tokens closed the link. Check the token, then reconnect. |
| Footer still shows the tether address with the cable out | The app has not fallen back: check that a Bluetooth permission was granted and that a device is paired. |
| Works over SPP but telemetry is slow over BLE | Expected: a ~1 KB snapshot becomes several notifications. SPP is preferred for this reason. |
| BLE starts, but no phone ever sees `MX5 Pi Link` | The adapter is not discoverable, or BlueZ's `DiscoverableTimeout` (default 180 s) has expired. Set `DiscoverableTimeout = 0` in `/etc/bluetooth/main.conf`. To check the app rather than the radio, ask BlueZ: `busctl get-property org.bluez /org/bluez/hci0 org.bluez.LEAdvertisingManager1 ActiveInstances` — `y 1` means a registered advertisement, `y 0` means nothing is broadcasting however healthy the process looks. |
| Phone says "Could not connect", or the Pi logs `org.bluez.Error.Rejected` | The adapter is advertising a profile the phone prefers. PulseAudio's `module-bluetooth-discover` registers Headset/Headset AG, so the phone opens a headset connection instead of this service. Comment it and `module-bluetooth-policy` out of `/etc/pulse/default.pa`, unload them, and restart; the adapter should then advertise only GAP/GATT/PnP plus this UUID. |
| Pairing fails on a passkey: `No agent available for request type 2` | No pairing agent is registered. Install `bluez-tools` and run `bt-agent`. Under systemd it reads its confirmation from **stdin**, and stdin is `/dev/null`, so it must be fed: `ExecStart=/bin/bash -c 'yes yes | /usr/bin/bt-agent --capability=NoInputNoOutput'`. It also ignores SIGTERM, so stopping it needs `pkill -9`. |
| `Failed to register advertisement`, right after a restart | The previous instance's advertisement had not been released yet, so BlueZ refused the new registration. `BleServer.start()` now waits for registration and raises on failure rather than returning optimistically. Stopping the app and starting it again clears it. |
| A screen or setting never updates over Bluetooth, and the log shows `Object of type Screen is not JSON serializable` | The app's `Screen` enum reached `json.dumps` un-unwrapped. Use `link_service.screen_index()` / `screen_name()` wherever a screen number is wanted. |
| The startup line claims success for a transport that is not working | Both transports used to report `start()` success without checking. SPP now fails when its SDP record could not be published, and BLE fails when the advertisement could not be registered, so the banner names only what is actually listening. |
| Everything worked, then stopped after a config edit | `dtoverlay=disable-bt` was enabled, which takes the UART from Bluetooth. |

## What is verified, and what is not

Verified on a desk, with no Bluetooth hardware and no car:

- The protocol, authentication and every operation (47 checks).
- The whole SPP accept/serve/connection-isolation loop, driven over a TCP socket through
  the server's own injected listener. Only the three lines that create the Bluetooth
  socket are untested.
- That the link **refuses to start with no token**, and that `MX5_BT_ALLOW_NO_TOKEN=1`
  switches that refusal off. Pinned from both sides, and confirmed to fail against the
  previous behaviour rather than passing vacuously.
- That the web API is byte-for-byte unchanged after sharing its logic with this link:
  40 requests across every endpoint, comparing status, body and side effects.
- That a machine with no Bluetooth at all reports both transports as unavailable and keeps
  everything else running.
- That the Android app compiles, installs, runs, and still reaches the Pi over the tether
  after the transport chain replaced the old single HTTP client.
- The Android chrome that carries the link's state: the System screen's address and token
  fields persist, and the footer names the active transport once it is not the tether.

**Settled on the car's own Pi (2026-10-14).** Three of the questions below are now answered,
and two of them answered badly:

- The display app **does** receive the token under systemd, once the unit loads an
  `EnvironmentFile`. This was the whole reason the link refused to start, and it was
  invisible from every other angle: no token file existed anywhere, and the process
  environment was the only place the answer lived.
- `sdptool add` **does not** publish a record on this install, and choosing a different
  channel cannot rescue it. The local SDP server is unreachable — `/var/run/sdp` is absent,
  `sdptool add` exits **255**, and `sdptool browse local` reports that it cannot connect.
  So SPP fails here for two independent reasons: the daemon's own claim on channel 3, and
  a missing SDP server. That is the argument for having written the BLE transport at all.
- The protocol, authentication and every operation pass unmodified on the real hardware:
  **47/47**, run on the Pi rather than on a desk.

**Settled over the air, from a laptop (2026-10-14).** The BLE transport was driven end to end
by `tools/bt/ble_probe.py`, a client that scans, connects, authenticates and calls the
operations, so no phone was involved:

- The GATT server **does** register and advertise under the real BlueZ, and the Pi's own
transcript agrees: `ActiveInstances` was `y 1` while the probe ran, and `btmon` showed a
connectable `ADV_IND` carrying the name and this service UUID.
- A central **does** connect, negotiate MTU 517, subscribe to the notify characteristic, and
exchange the line protocol: `hello`, `ping`, `status`, `telemetry` and `roof.status` all
answered. `10 checks: 9 pass, 1 warn, 0 fail`.
- The one warning is on the client's side and is not the Pi: Windows' stack reports
`GATT Protocol Error: Unlikely Error` on the write while the Pi replies normally. The reply
is the evidence that matters.

Two of those answers close unknowns that the desk tests could not reach. The whole GATT
peripheral was untested code until this run, and it was wrong in three separate ways that all
failed **silently** — the wrong write callback signature, async callbacks that bless never
awaits, and an `await` on a synchronous `get_characteristic`. Replying to a write without any
of the three fixes looked exactly like working code from the client's side.

**Not verified, because it needs the Pi, a phone and a car.** Each line names the stage that
settles it, so this doubles as the test's own checklist: tick a line off as it is answered,
and leave it standing if you skipped that stage.

| Unknown | Settled by |
| --- | --- |
| That a phone can be paired and the token typed on it matches | Stage 4, 5 |
| Anything about the Android Bluetooth client against real hardware | Stage 5 |
| That a phone can connect and reach the Pi without the cable | Stage 5 |
| That settings travel head unit to phone to Pi, and not merely get logged | Stage 7 |
| That the failover's ordering and its refusal rule hold in practice | Stage 9 |
| That the app recovers from a Pi reboot without being restarted | Stage 9 |
| Whether a 4 Hz poll over Bluetooth is a tolerable battery cost | Stage 10 |
| The mimic harness's fidelity to Android's own measurement and drawing | never; it is a design tool |
