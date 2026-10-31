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
| `roof.connect` | | Claim the module and prove it answers. |
| `roof.disconnect` | | Hand the module back to the car and stop touching it. |

### The roof controller's serial port

`roof.status`, `roof.speed`, `roof.auto` and `roof.mode` are ordinary exchanges: the Pi
opens `/dev/ttyACM*`, does that one exchange and closes it again. Nothing keeps the port
open between requests, and that is deliberate.

The RCNC-2 treats an attached host as a configuration session. MX5things' own guide says
the USB cable "must be unplugged from the computer" for normal operation, and that a solid
red status LED means the module is in that USB state rather than operating the roof. A host
left sitting on the module is therefore a roof that will not move until the module is power
cycled, which is the failure that is hardest to diagnose from the driver's seat.

`roof.disconnect` goes further and stops the Pi touching the module at all: while it is
released, every command refuses without opening anything, so the car is left with the
module to itself. `roof.connect` claims it again and proves it answers.

Both `roof.status` and the replies to `roof.speed`, `roof.auto` and `roof.mode` carry
`released`, so a client can tell "the Pi is deliberately leaving this alone" apart from
"the controller is missing". The web panel and the car app's Roof screen both show the
released state as its own condition rather than as a fault, and both offer the same
claim and release actions.

### Authentication

The first request must be `hello` with the access token. Pairing is deliberately **not**
treated as the security boundary: pairing makes a device trusted for the profile, it does
not authorize this application's commands, and the Pi may have other paired devices. The
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

Then set the three `[General]` keys that decide whether a reconnect is quick and whether a
phone can re-pair without being forgotten first. None of them can be set at runtime, and a
Pi missing them looks completely healthy:

```ini
# /etc/bluetooth/main.conf
[General]
FastConnectable = true        # the phone's reconnect is much quicker
AutoEnable = true             # the adapter comes up after a reboot on its own
JustWorksRepairing = always   # a phone can re-pair; no "forget this device" needed

[Policy]
AutoEnable = true
```

```bash
sudo systemctl restart bluetooth
```

`tools/bt/doctor.py` checks all three and prints the exact lines to add. Why they matter:

- Without `FastConnectable`, BlueZ pages on the default 1.28 s interval, so reconnecting
  from the phone can add more than a second before anything is even attempted.
- Without `AutoEnable`, a rebooted Pi comes up with the adapter powered off, which from
  the phone is indistinguishable from a Pi that is not there.
- Without `JustWorksRepairing = always`, a bond that the Pi lost (reflash, a wiped
  `/var/lib/bluetooth`, a re-pair on another phone) cannot be re-established: the phone
  keeps its half, the Pi rejects it, and the only cure is forgetting the Pi on the phone
  and pairing again.

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
| `MX5_BT_IDLE_TIMEOUT` | `300` | Seconds of silence before an SPP session is reclaimed |

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
python3 test_link_protocol.py         # 66 checks: protocol, service, SPP server over TCP
python3 test_bt_ble_server.py         # 10 checks: BLE reply order, stale fragments, chunk sizing
python3 test_web_server_parity.py /tmp/after.json

cd ..                                 # pi/
python3 test_bt_agent.py              # 17 checks: the agent's own decisions
```

## How it is built

The protocol is split from the transports on both sides, so the profile is the only thing
that differs between SPP and BLE.

**Pi** (`pi/ui/src/`):

| File | Role |
| --- | --- |
| `link_service.py` | Every read and command, with no transport in it |
| `link_protocol.py` | The JSON-line protocol, plus `StreamLink`: bytes in, bytes out |
| `bt_spp_server.py` | RFCOMM server: concurrent peers, idle reaping, injectable listener so it is testable on a desk |
| `bt_ble_server.py` | GATT server, via `bless` |
| `bt_link.py` | Starts both, configured by environment, contains failures |
| `test_link_protocol.py` | 66 checks that need no Bluetooth at all |
| `test_bt_ble_server.py` | 10 checks for BLE reply ordering, stale fragments and chunk sizing |
| `../test_bt_agent.py` | 17 checks for the agent's own decisions, with D-Bus stubbed out |

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
| `BtDevices.java` | Finding the Pi among the paired devices, and the device source both surfaces share |
| `PiClient.java` | Owns the ordered chain and the failover |

`PiClient`'s public methods are deliberately unchanged from when it was HTTP-only, so no
screen had to be touched. Every request the screens make is still expressed as a path, and
the Bluetooth transports translate that into a protocol op internally.

### Staying connected

A link that only works on the first attempt is not a link you can rely on in a car, and
every fault below used to present as **"close and reopen the app"** or **"forget the Pi and
pair it again"**. Each one is now either impossible or self-healing, and each is named here
so a later change does not reintroduce it by accident.

| Fault | What it looked like | What stops it now |
| --- | --- | --- |
| The SPP server served one peer inline, inside `recv()` | The phone reconnected and got no answer; only restarting the display app cleared it | Each peer gets its own thread and its own session, so an abandoned socket cannot block anyone |
| A peer vanished without a clean disconnect | A zombie session held the only slot | Sessions are read with a 1 s timeout and reclaimed after `MX5_BT_IDLE_TIMEOUT` (300 s) of silence; a newcomer reclaims the longest-idle session rather than being refused |
| RFCOMM `connect()` and `write()` have no timeout | A Pi that was off, or a link that died mid-write, held the poll thread for ever and nothing could recover it | Both run on a worker with a deadline (6 s connect, 2.5 s write), and the socket is closed to break the call |
| `bluetoothd` restarting dropped the SDP record, and nothing noticed | Every SPP connect failed with "service discovery failed" over a healthy radio | `mx5-bt-agent` checks for the record every 60 s and republishes it |
| The agent restarted `mx5-display` whenever no BLE advertisement existed | On a Pi configured `MX5_BT=spp` the advertisement never exists, so a working SPP link was dropped every 90 s, three times | The watchdog only acts when the app was actually asked to run BLE, read from the running process's own environment |
| A new GATT client opened while the old one was still connected | Status 133, then 133 on every attempt afterwards until the process died | `open()` waits for the retired client's disconnect before connecting again |
| A wrong token reopened the socket several times a second | A connect storm that left the stack refusing connections | A refused `hello` pauses that transport for 10 s; editing the token rebuilds the transports and clears it |
| The phone slept through the Pi rebooting | The next request wrote into a half-open socket and paid the reply timeout first | Links unproven for 60 s are closed before the next attempt, so it reconnects instead of waiting |
| Only force-stopping the app would clear a stuck link | All of the above | **Reconnect** on the System screen closes every transport and forgets the failure history |
| The in-motion app had **no Bluetooth at all** | "--" for every value the moment the cable was out, in the one app that exists for driving | Both surfaces build the chain now, through the shared `BtDevices.source()`; the drive app previously only ever got it from its phone activity, which a head-unit launch never runs |
| A token typed on the System screen worked on the cable and was refused over Bluetooth | The transports hold the token they were built with, so the new one never reached them | `applyConnection` rebuilds the Bluetooth transports as well, and `setBluetooth` closes the old ones instead of dropping the reference |
| One dropped poll after a BLE reconnect | A fragment left by the vanished central was spliced onto the next request, which was then discarded as malformed | A fragment that has sat for `PEER_GAP_SECONDS` is dropped and the session starts fresh |
| An occasional malformed reply on BLE | Two replies' notification chunks interleaved when the MTU was small | One writer task drains a queue, so a reply's chunks are never spliced with another's |
| A reply containing a non-ASCII character was dropped as malformed | Each incoming chunk was decoded as UTF-8 on its own, splitting characters that straddled a 20-byte boundary | Framing is done on bytes and each finished line is decoded whole |
| After a Pi-side restart of the display app the phone reported a refusal and stayed dead | The Pi had forgotten the session; the app treated "not authenticated" as a refusal | It re-sends `hello` once instead, which is invisible and always correct |
| The Pi showed nothing on its display for up to 35 s at boot | The Bluetooth link was started inside `PiDisplayApp.__init__` and waits up to 35 s for the BLE advertisement | The link starts on its own thread, so the first frame is never held behind it |
| A slow roof command demoted a working link | One reply deadline covered every op, and a roof exchange is 0.35 s of settle plus up to 2 s of reply, sometimes twice | `/api/roof/*` gets its own 8 s deadline |
| A missing `bluez-tools` silently stopped **every** watchdog | `hciconfig` is used to hold the adapter class, and its absence raised out of the agent's timer, which PyGObject then removes: no class, no advertisement watch, no SDP republish, for the life of the process | Each step of the tick is isolated, and the missing tool is reported once |
| A phone that left the MTU at its default got truncated BLE replies | Notifications were always 180 bytes, and nothing in the Python API reports the negotiated MTU | A refused notification halves the chunk down to 20 bytes and the reply is delivered whole |
| **One field JSON could not encode disconnected the phone, for ever** | `json.dumps` raised out of the protocol, which closed the SPP peer and surfaced as an opaque ATT error over BLE, so every retry was dropped the same way | The reply becomes `ok: false` with its id and the reason, and the session carries on; `LinkSession` is a backstop for anything else that escapes |
| A peer that stopped sending newlines grew the Pi's buffer without limit | The size cap only applied to *complete* lines, so a desynced stream could exhaust the Pi's memory | The cap covers the unfinished line too, is reported once, and discards to the next newline so the following request is answered rather than spliced onto the garbage |
| Both apps polling at once starved each other's replies | BlueZ notifies every subscribed central, so each app sees the other's replies as foreign lines; the allowance was eight, which a 4 Hz neighbour fills in two seconds | The wait is bounded by the deadline instead, with a much larger sanity cap |
| `stop()` then `start()` left the SPP server permanently deaf | `stop()` closed the listener but kept the reference, and `start()` only binds when there is none, so the second accept loop died on its first call | The listener is forgotten when the server owns it, so a restart binds a fresh one |

### How the failover behaves

The chain is ordered `HTTP, SPP, BLE`. The transport that last worked is remembered and
tried first, so the normal case costs one attempt; the rest are only tried after that one
fails. When every transport has failed the client backs off, so a poll loop does not
re-walk three dead links twenty times a second.

One distinction matters more than any other. A **refusal** — the Pi answered and said no,
which includes any HTTP status code — must never cause a fallback. If it did, an
out-of-range value would silently move a working link onto a slower transport and nothing
on screen would say so. Refusals are therefore a distinct exception type, and the
Bluetooth transports classify `ok: false` as one.

Two smaller rules exist so that a hiccup is not mistaken for a dead link:

- **The candidate order is by recency, not by the fixed chain.** After a dropped exchange
  the next request tries whichever transport answered most recently, so a Bluetooth
  link that stuttered is retried before the tether's connect timeout. Transports that
  have never answered keep their chain order.
- **One request may only spend 6 s walking the chain**, and each transport bounds its own
  connect as well: 6 s for SPP's create-and-connect, 9 s for the whole of a BLE open. Failing
  a poll quickly is better than holding the poll thread through three connects, because the
  poll loop is what draws the link state: a request that takes fifteen seconds looks exactly
  like a hung app.

### Permissions

`BLUETOOTH_CONNECT` is requested once at startup on Android 12 and later; the legacy
`BLUETOOTH`/`BLUETOOTH_ADMIN` pair is capped at API 30. `BLUETOOTH_SCAN` is deliberately
**not** requested: the Pi must be paired before either profile can be used, and connecting
to an already-bonded device needs no scan, so the app never scans. Refusing the permission
is a legitimate choice and is reported rather than nagged about.

**The two installs are separate packages, and a permission grant is per package.** MX5
Remote (`com.mx5.remote`) and MX5 Drive (`com.mx5.remote.drive`) each need their own. The
in-motion screen is drawn by a `CarAppService` with no activity of its own, and a car Screen
cannot raise a permission dialog, so the grant has to come from the phone activity in the
same package: **open MX5 Drive once on the phone** after installing it. Until then that
app's Bluetooth transports report "Needs the Nearby devices permission" on the System
screen, and only the USB tether will work. Both apps now build the Bluetooth chain
themselves, so this is the only step that cannot be skipped.

## The mimic harness

Iterating a car UI by installing onto a phone and squinting at it is slow, and it needs the
phone held sideways. `android/mimic/` renders the app in a browser at the geometry the head
unit gets, so the design can be screenshotted and measured directly.

```bash
cd android/mimic
python extract_tokens.py          # regenerate tokens.js from the Java sources

# then open, no server needed:
#   index.html?screen=rpm&scheme=ocean&mode=light
#   index.html?all=1              # all nine screens at half scale, for consistency
#   index.html?narrow=1&drawer=1  # the phone shell, drawer open
#   index.html?battery=8          # battery states; also &charging=1 and &clock=14:32
#   index.html?headunit=1&edge=0  # the head unit's own button bar, over the left edge
#   index.html?edge=88            # move the shell clear of that bar, as the EDGE chip does
#   index.html?canvas=800x480     # the old, too-tall canvas, for a comparison
```

It renders two canvases, because the app has two shells: **700x367 for the car**, and 400x832
when you pass `narrow=1`. Rendering the phone shell in the car's frame clips the drawer and
makes a working layout look broken, which is worth remembering before believing a
screenshot.

700x367 is the number that matters: the AVH reports **919x480 at 209dpi**, which is
700x367dp, and `Ui.java` lays out in dp. The harness used to render 800x480, which is 113dp
taller than the car, and three pages looked complete in a browser while being clipped in the
car. `?canvas=800x480` brings the old frame back for a side-by-side.

`headunit=1` draws the Pioneer's own strip of on-screen buttons over the left of the
projection - it is the head unit's UI, not Android Auto's, and nothing in the app can detect
it. `edge=<dp>` is the inset the app carries to stay out from under it, and `bar=<px>` sets
how wide the drawn bar is.

`battery`, `charging` and `clock` exist so a screenshot is reproducible. A real clock in a
screenshot makes two runs differ for no reason, which is how a real regression gets missed.

`extract_tokens.py` reads the twelve schemes, both mode palettes, the fixed alert colors,
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
attributable instead of re-derived. Three checks are worth knowing about:

- It reads the token out of the **running process's own environment**, not out of a config
  file. A token that never reached the app is invisible from everywhere else, and it fails
  silently in two different ways (the web remote drops to localhost-only, the link refuses
  to start).
- It separates `sdptool` being missing from the SDP record being missing, because those
  have the same symptom and different fixes.
- It reads `/etc/bluetooth/main.conf` for `FastConnectable`, `AutoEnable` and
  `JustWorksRepairing`, and prints the lines to add. Those three decide how quickly the
  phone reconnects and whether it can re-pair at all, and no running process reveals them.

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

Expect `66/66 passed`.

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

Then exercise the release path, because released is the state the car is meant to be left
in and an untested release is not a release:

```bash
ssh $PI 'curl -s -X POST -H "Authorization: ******" http://127.0.0.1:5000/api/roof/disconnect'
ssh $PI 'curl -s -H "Authorization: ******" http://127.0.0.1:5000/api/roof/status'
ssh $PI 'curl -s -X POST -H "Authorization: ******" http://127.0.0.1:5000/api/roof/connect'
```

After the release, status must come back `connected: false` with `released: true` and an
error naming the release; after `connect` it must be `connected: true` again. The same two
actions are on the web panel's **Roof** box and the car app's **Roof** screen, where the
released state shows as `Released` rather than as an alarm. What the release is for is
covered under **The roof controller's serial port** above.

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
| `sudo systemctl restart bluetooth` on the Pi | SPP's SDP record is republished by the agent within a couple of minutes and the phone reconnects; nothing needs repairing |
| Leave the app hidden for five minutes, then reopen it | The first poll reconnects rather than timing out on a socket the Pi has already forgotten |
| Press **Reconnect** on the System screen | Drops both Bluetooth sockets and comes back with a fresh `hello`; no app restart |
| `sudo systemctl restart mx5-display` with the app connected | The app re-authenticates by itself instead of reporting a refusal; no restart of the app |
| Launch **MX5 Drive** from the head unit with the cable out, after opening it once on the phone | Live values over Bluetooth, not `--` |

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
| The phone lists the Pi as `raspberrypi`, or as an unnamed BLE device | `bluetoothd` reset the adapter alias to the hostname, which it does whenever it re-initialises the adapter (a restart, or a crash). `mx5-bt-agent` polls the alias every 10 s and puts `MX5_BT_NAME` back, so this should repair itself within one tick; if it does not, `bluetoothctl show` will still read `Alias: raspberrypi` and the agent's log will say why it could not write it. Note the BLE *name* rides in the scan response, so a scan that does not wait for it shows the same device with no name even when the alias is right. |
| Bluetooth disappears for a minute or two, then comes back | `bluetoothd` crashed - check `journalctl -u bluetooth` for `code=killed, status=11/SEGV`. Everything it was holding goes with it: the GATT application, the advertisement, the SDP record, and the adapter alias and class. Recovery is layered: `bt_ble_server` retries the registration for 60 s (longer than BlueZ's 25 s D-Bus activation timeout), `mx5-bt-agent` re-asserts the class and name every 10 s, and after 90 s with no advertisement the agent restarts the display service. |
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
| **The app only reconnects if it is closed and reopened** | Fixed in three places, so check which one you are on. On the Pi, the SPP server used to serve one peer at a time and could wedge for ever on an abandoned socket (`journalctl -u mx5-display \| grep 'SPP:'` shows `reclaiming` or `refusing` if that is happening). In the app, `Reconnect` on the System screen now does what reopening did, without the restart. |
| In-motion app shows `--` for every value, but the parked app works over Bluetooth | The two apps are separate packages and the permission grant is per package. Open **MX5 Drive** once on the phone to grant Nearby devices; a head-unit launch cannot ask for it. |
| A token typed on the System screen works on the cable but not over Bluetooth | It now reaches both: `applyConnection` rebuilds the Bluetooth transports. On an older build it did not, and only an app restart applied it. |
| **The phone has to be unpaired and paired again** | A lost bond cannot be re-established unless BlueZ is willing to repair. Set `JustWorksRepairing = always` under `[General]` in `/etc/bluetooth/main.conf` and restart `bluetooth`. `tools/bt/doctor.py` reports it. |
| **Connecting takes several seconds every time** | Two causes. Without `FastConnectable = true` BlueZ pages on a 1.28 s interval. And a cold start used to try the tether first, which costs a 1.5 s connect timeout with no cable; the app now remembers the transport that last worked and starts there. |
| The link drops at intervals of about 90 s | `mx5-bt-agent` was restarting `mx5-display` because no BLE advertisement existed. On a Pi configured `MX5_BT=spp` that is normal and the watchdog no longer acts on it. Update the agent and restart it. |
| `BLE connect failed (133)` | The stack still holds a client for the previous connection. The app now waits for the retired client's disconnect first; if 133 persists, `btmon` will show whether the disconnect ever reached the Pi. |
| Every SPP connect fails with "service discovery failed", but the Pi is fine | The SDP record is gone, which happens after any `bluetoothd` restart. `sudo sdptool add --channel=3 SP`, or let `mx5-bt-agent` republish it within a minute. |

## What is verified, and what is not

Verified on a desk, with no Bluetooth hardware and no car:

- The protocol, authentication and every operation (66 checks).
- That a payload the encoder cannot handle costs **a reply, not the session**: the error
  comes back with its id, and the next request on the same session still works. This is
  the fault that once stopped every Bluetooth request when a `Screen` enum reached
  `json.dumps`, and it is pinned from both layers now.
- That a peer which never sends a newline cannot exhaust the Pi's memory, that the
  overflow is reported once rather than per chunk, and that the first request after the
  garbage's newline is answered rather than spliced onto it.
- That an SPP server can be stopped and started again and still serve a client, which it
  could not before: the second start reused the closed listener and died silently.
- The agent's own decisions (17 checks): which transport mode it reads out of the running
  process, the three-way answer from the SDP server (present, missing, unreachable), that
  it republishes only when a listener is actually behind the record and backs off instead
  of shouting every minute, and that a missing `hciconfig` cannot take the whole timer
  down with it.
- The BLE server's own bookkeeping (10 checks): replies are drained one at a time in order,
  a fragment left by a vanished central cannot eat the next request, a fragment belonging
  to a live request is not dropped, the reply queue is bounded, and a notification the
  stack refuses is retried smaller until it fits.
- The whole SPP accept/serve/connection-isolation loop, driven over a TCP socket through
  the server's own injected listener. Only the three lines that create the Bluetooth
  socket are untested. That includes the failure paths this link used to need a restart
  for: a silent peer cannot block the next one, an idle peer is reclaimed, and a newcomer
  takes the slot from a stale session instead of being refused.
- That the link **refuses to start with no token**, and that `MX5_BT_ALLOW_NO_TOKEN=1`
  switches that refusal off. Pinned from both sides, and confirmed to fail against the
  previous behavior rather than passing vacuously.
- That the web API is byte-for-byte unchanged after sharing its logic with this link:
  40 requests across every endpoint, comparing status, body and side effects.
- That a machine with no Bluetooth at all reports both transports as unavailable and keeps
  everything else running.
- That the Android app compiles, installs, runs, and still reaches the Pi over the tether
  after the transport chain replaced the old single HTTP client.
- The Android chrome that carries the link's state: the System screen's address and token
  fields persist, and the footer names the active transport once it is not the tether.

**Not verified without a phone and a Pi.** The two socket deadlines (a 6 s SPP connect and a
2.5 s write), the BLE MTU request and the re-authentication retry are only compiled and
reasoned about: Android's own behaviour there is what they are compensating for, so Stage 9
and Stage 10 are what settle them. The `Reconnect` button, and the in-motion app's Bluetooth
chain, are likewise compiled only - the latter needs the drive package installed on the
phone and granted Nearby devices to test at all.

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
  **66/66**, run on the Pi rather than on a desk.

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
