# Android Auto control for the Pi: plan

Status: **proposed, nothing built yet.** Written 2026-10-13.

## 1. Goal

From the car, with no internet and no phone hotspot: configure the Pi (roof
controller plus Pi system settings) from the Pioneer AVH's Android Auto screen.

The blocker today is simply that the Pi is unreachable: wireless Android Auto
holds the phone's Wi-Fi radio, so there is no network path from the phone to the
Pi. Everything below is about removing that blocker and then putting a UI on it.

Success looks like: phone in the car, AVH shows one app, that app talks to the Pi
over a cable or Bluetooth, and the roof and system settings are editable.

## 2. What the docs actually say

These four facts shape the whole plan. All from `developer.android.com`,
September 2026 revisions.

| Fact | Consequence |
| --- | --- |
| Android Auto runs **parked apps** (category: Games) directly on the head unit, on phones running **Android 15 (API 35) or higher** | An S25 Ultra qualifies. An older phone would not. |
| "Games are the only parked app category supported by Android Auto at this time" | The loophole requires marking the app as a game. |
| `Allow unknown sources` "applies to media, messaging notifications, and **parked apps** but doesn't apply to apps built using the Android for Cars App Library" | A **parked** app can be sideloaded. A **templated** app cannot. |
| The two no-review Play channels (Internal App Sharing, Internal Test Track) both live inside Play Console | The templated path needs a $25 developer account. The parked path does not. |

Also relevant:

- Declaring Android Auto support for a parked app is one manifest line:
  `<category android:name="android.intent.category.CAR_LAUNCHER" />`.
- Marking the app as a game is one attribute: `android:appCategory="game"`.
- A parked app renders **its own Activity**. It is not templated, so there is no
  fixed widget set and no ban on WebView, images, or animation.
- Canonical AA screen: **800x480, dpi 160** (landscape 16:9, portrait 9:16). That
  matches the Pi display target, so the webapp's 768-900px layout range is the
  one that matters.
- Car quality guidelines are only applied "when submitted to tracks other than
  internal testing", so an internal/sideloaded build never sees that review.

## 3. Two candidate mechanisms

### A. Parked app, the loophole (preferred)

The app is an ordinary Android app with one Activity that declares
`CAR_LAUNCHER` and `android:appCategory="game"`.

```xml
<manifest ...>
  <application android:appCategory="game" ...>
    <activity android:name=".MainActivity" ...>
      <intent-filter>
        <action android:name="android.intent.action.MAIN" />
        <category android:name="android.intent.category.LAUNCHER" />
        <category android:name="android.intent.category.CAR_LAUNCHER" />
      </intent-filter>
    </activity>
  </application>
</manifest>
```

- Install: `adb install`, no Play account, no review.
- Renders its own Activity, therefore **the existing webapp can be reused
  wholesale** inside a WebView.
- Only visible while parked, which is correct for a diagnostics tool anyway.
- Hard requirement: **phone on Android 15+**.

### B. Templated IoT app, the supported path

`androidx.car.app` with `androidx.car.app.category.IOT`, a `CarAppService`, and
`GridTemplate` for the device list. This is the category the docs describe as
"controlling the state of certain devices from within the car", so it is a
genuine fit.

- Install: sideloading is explicitly **not supported**. Needs Play Console,
  Internal App Sharing, $25 one-time, no review.
- UI must be rewritten in templates: no HTML, no custom fonts, no colour scheme
  picker, no sliders. The speed limit becomes `-` / `+` actions.
- Fine-grained control is banned while driving, so the config screen would be
  parked-only regardless.

| | A. Parked (game) | B. Templated IoT |
| --- | --- | --- |
| Sideload with `adb` | likely yes | no |
| Google account needed | no | $25 one-time |
| UI cost | wrap the existing webapp | rewrite in templates |
| Colours / scheme picker | keep | lost |
| Phone requirement | Android 15+ | any AA-capable |
| Visible while driving | no | yes, for simple on/off |
| Honesty | filed as a "game" | correct category |

**Plan assumes A, keeps B as the fallback.**

## 4. Why A is also the cheapest UI

Because a parked app draws its own Activity, the UI can be a WebView pointed at
the Pi's existing Flask app. Everything built for the Pi webapp (the roof
endpoints, the settings panel, the scheme picker, the responsive layout) is
reused as-is. No template port, no second design language.

The Android side then shrinks to: a connect screen (address + transport), a
WebView, and a service to hold the transport open.

## 5. Phases

### Phase 0 - toolchain (half a day, one time)

This machine already has **JDK 21** on PATH. It has **no Android SDK, no `adb`,
no Gradle, no Android Studio.**

- Install Android SDK command-line tools, then
  `sdkmanager "platform-tools" "platforms;android-35" "build-tools;35.0.0"`,
  and accept licences. ~150 MB.
- Use the Gradle **wrapper** so Gradle needs no separate install.
- Verify with `adb version` and `adb devices`.
- Alternative: install Android Studio (much larger, but brings the emulator and
  a working DHU setup).

### Phase 1 - the go/no-go experiment (an evening)

Build two throwaway apps and find out which one the AVH will show.

- **`aa-parked-test`** - manifest exactly as in section 3A, one Activity showing
  a WebView that loads a hardcoded URL. Proves the loophole.
- **`aa-template-test`** - minimal `category.IOT` CarAppService with one
  `GridTemplate`. Proves the documented path.

Test each in this order: Desktop Head Unit first (free, instant, no car), then
`adb install` on the phone with the AVH connected.

**Decision gate:**

| Result | What we do |
| --- | --- |
| Parked app appears on the AVH | Proceed with A. No money, reuse the webapp. |
| Only the templated app appears | Either pay $25 for Internal App Sharing, or stop. |
| Neither appears | Fall back to Phase 2 plus a phone browser. Still useful. |

Nothing else gets built until this gate is answered.

### Phase 2 - transport (an evening)

The Android Auto app does **not** remove the network problem; it has the same
one. So solve transport independently of the UI.

- **USB tether, do this first.** Phone cabled to the Pi, Android USB tethering
  gives the Pi an IP, the app (or a browser) hits `http://<pi>:5000`. No BT
  pairing, no custom protocol, no Wi-Fi contention with wireless AA, and it
  charges the phone. Verify the Pi gets `usb0` and an address.
- **Bluetooth SPP, later, if the cable is unacceptable.** `BluetoothPan` is
  `@SystemApi`, so there is no free IP-over-Bluetooth: this means a line protocol
  on the Pi, not HTTP. Follows the pattern already proven by the RNC-2 console.
- **Pi-hosted Wi-Fi AP: ruled out.** One Wi-Fi radio, and wireless AA holds it.

### Phase 3 - the app

- Connect screen: transport choice, Pi address, test connection.
- WebView onto the existing webapp.
- Parked-only by construction.
- Landscape 16:9 is the target; the 800x480 canonical size is the one to check.

### Phase 4 - repo integration

- New `android/` folder alongside `arduino/`, `display/`, `pi/`.
- Pi side unchanged: the `/api/*` contract is already the right seam, and
  `roof_controller.py` is transport-agnostic by design.
- A doc under `docs/` describing how to install and pair.

## 6. Risks and unknowns

- **The loophole is inferred, not confirmed.** The docs say unknown sources
  covers parked apps, and that a parked app is a normal Activity, which is why
  this should work. It has not been tested on this AVH. Phase 1 exists precisely
  to settle it.
- **Android 15+ is a hard floor** for AA parked apps. Confirm the phone's
  version before Phase 1; if it is below 15, mechanism A is dead on arrival.
- **Enforcement lives in the Android Auto phone app**, which has changed
  behaviour across releases. A documented "yes" can stop being true.
- **WebView in a car app** is outside the parked-app quality guidance. While
  parked it is very likely fine; treat it as something to verify in Phase 1
  rather than assume.
- **USB tethering to a Linux host** usually needs CDC-NCM/ECM support on the Pi.
  Raspberry Pi OS normally brings `usb0` up on its own, but this is worth
  checking early in Phase 2.
- **The AVH renders at 800x480**, and AA screens are narrow in general. The
  webapp has been checked down to 320px, so this should be comfortable.

## 7. Open questions

1. Is the S25 Ultra on Android 15 or newer? (Settings, About phone.)
2. Cable to the Pi for tethering, or Bluetooth SPP? The first is 30 minutes, the
   second is a new Pi-side service.
3. Command-line SDK or full Android Studio?

## 8. Environment today

| Tool | Status |
| --- | --- |
| JDK | 21.0.10 (Microsoft OpenJDK), on PATH |
| Android SDK | not installed |
| `adb` | not installed |
| Gradle | not installed (wrapper will supply it) |
| Android Studio | not installed |
