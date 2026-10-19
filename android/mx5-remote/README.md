# MX5 Remote for Android Auto

The car app. It replaces the Pi's HDMI display and covers everything the webapp does.

It is a **parked app**: filed as a game with the `CAR_LAUNCHER` category, so Android
Auto projects it full screen and it never needs Play approval. It draws its own UI,
which is only possible because it is a parked app rather than a templated one.

## Screens

Nine pages, reached from a rail down the left (or a strip across the bottom when the
window is narrow):

| Screen | What it shows | Mirrors Pi screen |
| --- | --- | --- |
| Overview | Speed, RPM, gear, coolant, fuel, range, battery, MPG, throttle and brake bars | 0 |
| RPM / Speed | The arc gauge with the display's zone bands, shift light and redline tick | 1 |
| Tire Pressure | All four corners: pressure, temperature, when each was last seen | 2 |
| Engine | Coolant, intake, ambient, oil, MAF, fuel, voltage, instant MPG | 3 |
| G-Force | The g scatter with peaks, lap and best lap, cornering load | 4 |
| Diagnostics | Nine warning lamps plus stored fault codes | 5 |
| System | Link state, Pi display stepping, g-force zero, wake, connection setup | 6 |
| Roof | The RCNC-2 roof controller | none, it is a separate serial device |
| Settings | Every setting the webapp exposes | 7 |

Switching to a screen also pushes that screen index to the Pi, so the round display
follows the car screen.

## What it talks to

The Pi's Flask server, over the USB tether. All plain HTTP with a bearer token.

```
GET  /api/status          screen, settings, demo mode, sleep state
GET  /api/telemetry       the full live snapshot
GET  /api/roof/status     RCNC-2 state
POST /api/screen/<n>      also /api/screen/next and /prev
POST /api/settings/update {name, value}
POST /api/roof/speed      also /auto and /mode
POST /api/roof/connect    claim the module; /disconnect hands it back to the car
POST /api/calibrate_imu
POST /api/wake
```

`/api/telemetry` was added for this app. The web page only ever needed the current
screen and the settings, so the live values went to the LED/display firmware over
serial and were never exposed over HTTP. The field names match the attribute names on
`TelemetryData` in `pi/ui/src/main.py`, so adding a field there is a small change here.

Telemetry is **polled at 4 Hz** rather than pushed. The Pi has Socket.IO, but a
Socket.IO client for Android is a heavy dependency for a link that is a few hundred
microseconds away across the tether, and polling keeps this app on platform classes
only. There are no third party dependencies at all: HTTP is `HttpURLConnection` and
JSON is `org.json`.

The polls and the two long-running actions all run off the UI thread, and the poll
loop stops in `onPause`, because a backgrounded app holding a 4 Hz poll open just
drains the phone.

## Setting it up

The app starts with **no connection**, so the System screen is where you fix that. It
is the one page that works with the link down:

1. Plug the phone into the Pi and turn on **USB tethering** on the phone.
2. Find the address the Pi was given (it is the tethered interface's address, usually
   in `192.168.42.x`).
3. On the System screen, enter `192.168.42.<pi>:5000` and the token if the Pi is using
   one, then tap **Connect**.

The default is `192.168.42.100:5000`. Settings persist in `SharedPreferences`.

`android:usesCleartextTraffic="true"` is set in the manifest. That is load bearing:
the Pi serves plain HTTP and API 28+ blocks cleartext by default, which would make
every request fail with no obvious cause.

## Themes and schemes

The webapp's twelve schemes are ported, along with light and dark. **Scheme** cycles
them from the top bar, **Light/Dark** toggles the mode, and both persist.

The webapp derives its palette from two seed hues with OKLCH and CSS `color-mix`.
There is no OKLCH in the Android view toolkit, so `Palette.java` approximates the same
idea with sRGB blends: the scheme supplies two hues, the mode lifts them for dark and
sinks them for light, and the surface colours are fixed per mode. It is close enough
that a scheme is recognisable across both.

Alert stays orange in every scheme, matching the standard's rule that the alert hue
must not follow the decor.

## Layout rules that bit

Two bugs here were the same bug twice, and both came from the same cause: **a
`LinearLayout` only divides space by weight along its own orientation.**

- A child of a **row** needs `width=0dp` + weight and `height=match_parent` or
  `wrap_content`.
- A child of a **column** needs `height=0dp` + weight and `width=match_parent`.

Set the wrong axis to zero and the view collapses to nothing and **disappears from the
UI hierarchy entirely**, which is why it reads as "the screen is blank" rather than as
a layout error. `Ui.cell()` is a child of a row and `Ui.stack()` is a child of a
column, named apart so the two cannot be swapped by accident.

A row added to a column also defaults to `wrap_content` width, which collapses it to
nothing as well, so `Screen.grid()` carries its own `match_parent` params.

The fastest way to find this class of bug is a hierarchy dump, not a screenshot: a
dark empty panel and a dark empty *page* look the same in a screenshot, but the dump
shows the nodes are simply missing.

## Build and install

Two apps come out of this module. Install whichever the car needs — both, usually.

```powershell
$env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk"
& "$env:LOCALAPPDATA\Android\gradle-8.11.1\bin\gradle.bat" -p android :mx5-remote:assembleParkedDebug :mx5-remote:assembleDriveDebug

# MX5 Remote - parked dashboard (game, CAR_LAUNCHER)
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" install -r `
    android\mx5-remote\build\outputs\apk\parked\debug\mx5-remote-parked-debug.apk

# MX5 Drive - templated, stays visible while driving (CarAppService, category.IOT)
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" install -r `
    android\mx5-remote\build\outputs\apk\drive\debug\mx5-remote-drive-debug.apk
```

## Checking it without a car

The phone's display can be temporarily set to the car's canonical canvas, which is
exactly what the head unit gets:

```powershell
adb shell wm size 800x480
adb shell wm density 160
# run and capture
adb shell wm size reset
adb shell wm density reset
```

Two gotchas learned doing this: the screen must be **unlocked and awake** or the dump
returns the lock screen instead of your app, and `uiautomator dump` is a better check
than a screenshot because it gives you the text tree and the bounds of every node.

## Known gaps

- **Not yet verified against a real Pi feed.** Every screen has been checked rendering
  with the link down, which exercises the layout, the theming and the error paths, but
  not live values arriving. That needs the Pi online.
- The Pi's screen index is pushed when the link is up; on an offline Pi the app no
  longer tries, so it does not spam a toast on every tap.
- Lap timing is whatever the Pi reports; there is no lap control on this side.
- Peak g values are per-visit and reset when you leave the screen, deliberately: a
  peak that survives a restart is a number you cannot attribute.
