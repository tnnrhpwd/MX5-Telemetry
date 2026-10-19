# android/

The Android Auto side of the project. One module, two apps:

| Module | What it is |
| --- | --- |
| `mx5-remote` | The car app. Replaces the Pi's HDMI display and covers everything the webapp does. |

It builds twice from one source set: **MX5 Remote** (`parked` flavor) for the full
dashboard while stopped, and **MX5 Drive** (`drive` flavor) for the templated view that
Android Auto keeps on screen while the car is moving.

See [`mx5-remote/README.md`](./mx5-remote/README.md) for the app's screens, the Pi
endpoints it uses, theming, and how to point it at the Pi.

## Toolchain

JDK 21, AGP 8.7.3, Gradle 8.11.1, compileSdk/targetSdk 35, minSdk 26.
Gradle lives at `%LOCALAPPDATA%\Android\gradle-8.11.1` and the SDK at
`%LOCALAPPDATA%\Android\Sdk`.

The one dependency is `androidx.car.app:app:1.4.0` (Car App Library). It is what
makes the drive-accessible surface possible — see below.

The module builds **two apps**, one per flavor:

| Flavor | applicationId | Name | Car entry point |
| --- | --- | --- | --- |
| `parked` | `com.mx5.remote` | MX5 Remote | `CAR_LAUNCHER` activity, `appCategory=game` |
| `drive` | `com.mx5.remote.drive` | MX5 Drive | `CarAppService`, `category.IOT` |

```powershell
$env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk"
& "$env:LOCALAPPDATA\Android\gradle-8.11.1\bin\gradle.bat" -p android :mx5-remote:assembleParkedDebug :mx5-remote:assembleDriveDebug
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" install -r `
    android\mx5-remote\build\outputs\apk\parked\debug\mx5-remote-parked-debug.apk
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" install -r `
    android\mx5-remote\build\outputs\apk\drive\debug\mx5-remote-drive-debug.apk
```

`assembleDebug` now builds both flavors; the per-flavor tasks exist because
`adb install` wants one file at a time.

## The parked-app gate, and what it settled

Phase 1 of `docs/ANDROID_AUTO_PLAN.md` asked one question: **what will the AVH actually
list?** It was answered with two throwaway probe apps, which have since been deleted.
The result is kept here because it decides the app's whole architecture.

Answer, measured on the S25 Ultra (Android 16, Android Auto 17.8.663874):

**Both mechanisms are accepted.** Android Auto enumerated the launcher icon of every
one of the probe apps, alongside real AA apps (Spotify, Teams, Meet, and Tuya's
`SceneManualCarAppService`, which also declares `category.IOT`):

```
GH.IconLoader / GH.AppIconFactory:
  com.mx5.aatest.parked/com.mx5.aatest.parked.MainActivity
  com.mx5.aatest.template/...MyCarAppService
```

The parked probe also went to the foreground while AA was connected, displacing Maps:

```
AppUsageDataProvider: MOVE_TO_BACKGROUND package = com.google.android.apps.maps,
                      currentFgApp = com.mx5.aatest.parked
```

That **contradicted the expectation** that a sideloaded Car App Library app stays
invisible. It may be AA's developer mode, or the unknown-sources toggle covering more
than the documentation implies. Either way the parked path was chosen: no Play account
needed, and the UI is a real dashboard rather than a set of templates.

⚠️ **What this does not prove.** The DHU from `extras;google;auto` is
`Build: 2022-03-30`, version `2.0-windows`, which predates parked apps entirely (they
need Android 15, from 2025). It cannot render a parked app, so none of the above shows
the UI on a car screen. The car is still the only real test on that point.

## Facts worth not rediscovering

- **Two surfaces, two packages.** `MainActivity` is the parked dashboard (declared as a
  game, `CAR_LAUNCHER`). `Mx5CarAppService` is a `androidx.car.app.CarAppService` and
  ships in its own app, `com.mx5.remote.drive`, declaring
  `androidx.car.app.category.IOT` — that is what the host is willing to show while the
  car is moving. They cannot be one package: `android:appCategory` is application-wide,
  so a "game" package is hidden in motion no matter which component the user opened.
  The proof that the split is needed is the probe result above: the two entry points
  that the AVH enumerated were themselves two different packages.
- **`category.DRIVING` does not exist.** It is not in the documented set
  (`NAVIGATION`, `POI`, `IOT`, `WEATHER`, plus the messaging/media categories), and the
  AOSP library carries no constant for it — `androidx.car.app` has no `category` package
  at all. An earlier revision of this app declared it and the host never listed the
  service. `IOT` is the documented fit for reading a connected device's state, and the
  probe notes above record a real AA app (Tuya) using exactly that category.
- **Driving means templates.** A templated session may only return host-rendered
  templates (`PaneTemplate` here). Custom `View` hierarchies — which is what the parked
  dashboard is — are not available in motion. Anything added to the drive surface must
  stay glanceable: a few labelled rows, no lists to scroll, no interaction needed to
  reach a critical number.
- **Parked categories.** Games work on Android Auto *and* Automotive OS. Video and
  Browsers are Automotive-only. Games are the only AA-supported parked category.
- **The declaration** is two things: `android:appCategory="game"` on `<application>`,
  and `<category android:name="android.intent.category.CAR_LAUNCHER" />` in an
  activity's intent filter that also has `MAIN`.
- **`android:appCategory="game"` compiles to `0`.** `ApplicationInfo.CATEGORY_GAME` is
  `0` and `CATEGORY_UNDEFINED` is `-1`, which matches AAPT2's own enum table
  `[accessibility=8, audio=1, game=0, ...]`. A compiled `0` in the manifest is correct,
  not a missing value. `dumpsys package` confirms it as `category=manifest: 0`.
- **The phone needs Android 15+** for parked apps.
- **Android Auto developer settings** are required, and all of it is behind tapping the
  version row in AA settings ten times. Then the overflow menu (top right) gives
  `Developer settings`, which holds **`Unknown sources`** (the toggle the whole
  experiment turns on) and **`Start head unit server`**.
- **The head unit server cannot be started with adb.** Android Auto 17.8 declares no
  `HeadUnitServerService` because it is registered at runtime, so
  `am start-service -n` answers "Not found". It has to be the menu item.

## Testing without a car

```powershell
adb shell wm size 800x480
adb shell wm density 160
# run, then dump and screenshot
adb shell wm size reset
adb shell wm density reset
```

800x480 at 160dpi is Android Auto's canonical canvas, and the app's own probe reports
`800x480 @160` when it gets it.

The DHU accepts commands typed into the terminal it runs in. `keycode home` returns to
the AA app grid, `keycode back` steps back, `quit` shuts it down, `screenshot out.png`
saves a frame. `Alt+Q` also quits but needs the window focused.

⚠️ Two traps that cost time here: the phone must be **unlocked and awake** or
`uiautomator dump` returns the *lock screen* instead of your app, and a UI hierarchy
dump is a far better check than a screenshot for layout problems, because a collapsed
view is simply **absent** from the dump while a screenshot just looks dark.
