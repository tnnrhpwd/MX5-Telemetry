"""A faithful Python port of the LED rendering in arduino/src/main.cpp.

Why a port rather than a reimplementation
-----------------------------------------
The simulator's job is to tell you what the strip *will* do, so it has to be the same
program, not a lookalike. Every function here mirrors a specific function in the firmware,
and the arithmetic is kept in the same order with the same types - including float32
rounding via `_f32()`, because `(uint8_t)` truncation after a float multiply lands on a
different integer when the product sits near a whole number.

What is *not* ported: anything that only exists to save cycles on a 16 MHz AVR. The
`currentRPM == lastRenderedRPM` repaint gate, `showIfChanged()` and the haphazard
`stripForceShow` flag are performance hacks with no visual effect, so `frame()` simply
computes the frame. The one place they are visible is the shift light, which changes with
*time* rather than rpm and therefore has to bypass the gate - that is mirrored.

Reference: arduino/src/main.cpp, functions `rampColorAtRpm`, `barRank`, `barSlots`,
`renderBar`, `drawCanOffline`, `drawSelfTest`, `updateErrorAnimation`, `updateLEDs`.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field, replace
from typing import List, Sequence, Tuple

RGB = Tuple[int, int, int]

# -- hardware -----------------------------------------------------------------

# LED_COUNT is a build flag on the Nano (see LED_REVAMP_PLAN.md §12), so it is a
# parameter everywhere rather than a module constant.
DEFAULT_LED_COUNT = 20

# LEDSequence, in the same order and with the same values as the firmware enum.
SEQ_CENTER_OUT = 1
SEQ_LEFT_TO_RIGHT = 2
SEQ_RIGHT_TO_LEFT = 3
SEQ_CENTER_IN = 4

SEQUENCE_NAMES = {
    SEQ_CENTER_OUT: "Center out",
    SEQ_LEFT_TO_RIGHT: "Left to right",
    SEQ_RIGHT_TO_LEFT: "Right to left",
    SEQ_CENTER_IN: "Center in",
}

SELF_TEST_NONE = 0
SELF_TEST_SWEEP = 1
SELF_TEST_IDENTIFY = 2

SELF_TEST_MS = 4000
IDENTIFY_MS = 3000

# The ramp the firmware boots with (`rampStops[]`). The last stop is also the rpm at
# which the strip is completely full.
DEFAULT_RAMP: Tuple[Tuple[int, RGB], ...] = (
    (0, (0, 0, 255)),        # idle - blue
    (1400, (0, 220, 255)),   # pulling away - cyan
    (2800, (50, 215, 130)),  # economical cruise - green
    (4500, (255, 210, 60)),  # waking up - yellow
    (5800, (255, 128, 0)),   # spirited - orange
    (6800, (255, 0, 0)),     # redline - red
)

# `uint8_t scale = themeDim ? 170 : 255;` - dark mode is dimmer by design.
DIM_SCALE = 170

# Where the phone puts each of its six ramp stops inside "full at". Used by
# LedScreen.pushRamp() so the simulator's "Full at" slider produces exactly the RAMP:
# payload the app would send.
STOP_FRACTIONS: Tuple[float, ...] = (0.0, 0.21, 0.41, 0.66, 0.85, 1.0)

# RPM smoothing (RPM_SNAP_DELTA / RPM_ALPHA_RISING / RPM_ALPHA_FALLING).
RPM_SNAP_DELTA = 250
RPM_ALPHA_RISING = 1.0
RPM_ALPHA_FALLING = 0.75


def _f32(value: float) -> float:
    """Round a Python float to float32, which is what a C `float` on the AVR is."""
    return struct.unpack("<f", struct.pack("<f", value))[0]


def _byte(value: float) -> int:
    """C `(uint8_t)` cast: truncate toward zero, then wrap to 0-255."""
    return int(value) & 0xFF


def _u16(value: int) -> int:
    """C `(uint16_t)` cast."""
    return int(value) & 0xFFFF


# -- color -------------------------------------------------------------------


def ramp_color_at_rpm(rpm: int, ramp: Sequence[Tuple[int, RGB]]) -> RGB:
    """Mirror of `rampColorAtRpm()`: piecewise-linear lookup over the stops."""
    rpm = _u16(rpm)
    if not ramp:
        return (0, 0, 0)
    if rpm <= ramp[0][0]:
        return tuple(ramp[0][1])  # type: ignore[return-value]

    for index in range(1, len(ramp)):
        if rpm > ramp[index][0]:
            continue
        a_rpm, a_rgb = ramp[index - 1]
        z_rpm, z_rgb = ramp[index]
        span = z_rpm - a_rpm
        # `float t = span ? (float)(rpm - a.rpm) / (float)span : 1.0f;`
        t = _f32((rpm - a_rpm) / span) if span else 1.0
        out = []
        for channel in range(3):
            start = a_rgb[channel]
            delta = float(z_rgb[channel] - start)
            # (uint8_t)((float)a.r + ((float)((int)z.r - (int)a.r) * t) + 0.5f)
            out.append(_byte(_f32(_f32(start + _f32(delta * t)) + 0.5)))
        return (out[0], out[1], out[2])

    return tuple(ramp[-1][1])  # type: ignore[return-value]


def hex_of(rgb: RGB) -> str:
    return "%02x%02x%02x" % (rgb[0], rgb[1], rgb[2])


def rgb_of_hex(text: str) -> RGB:
    text = text.strip().lstrip("#")
    if len(text) != 6:
        raise ValueError("expected rrggbb, got %r" % text)
    value = int(text, 16)
    return ((value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF)


def parse_ramp(text: str) -> Tuple[Tuple[int, RGB], ...]:
    """Parse the firmware's `RAMP:<rpm>:<rrggbb>,...` payload.

    The same rules the Pi enforces before forwarding: 2-6 stops, a run of digits for the
    rpm, six hex digits for the color. Ordering is *not* checked, because neither the Pi
    nor the firmware checks it - a descending table is legal, just mostly unreachable
    (see `ramp_color_at_rpm`).
    """
    stops = []
    for part in (piece for piece in text.split(",") if piece.strip()):
        rpm_text, _, color = part.strip().partition(":")
        if not rpm_text.isdigit():
            raise ValueError("ramp rpm %r is not a run of digits" % rpm_text)
        stops.append((int(rpm_text), rgb_of_hex(color)))
    if not 2 <= len(stops) <= 6:
        raise ValueError("a ramp needs 2-6 stops, got %d" % len(stops))
    return tuple(stops)


def format_ramp(ramp: Sequence[Tuple[int, RGB]]) -> str:
    return ",".join("%d:%s" % (rpm, hex_of(rgb)) for rpm, rgb in ramp)


def ramp_from_fractions(full_rpm: int,
                        colors: Sequence[RGB]) -> Tuple[Tuple[int, RGB], ...]:
    """The ramp `LedScreen.pushRamp()` builds from "Full at" and six swatches.

    Mirrors the app exactly, including the rounding to 100 rpm and the floor of 100 rpm
    on every stop after the first, so what the simulator shows is what the app sends.
    """
    fractions = STOP_FRACTIONS[:len(colors)]
    stops: List[Tuple[int, RGB]] = []
    for index, color in enumerate(colors):
        rpm = round(full_rpm * fractions[index] / 100.0) * 100
        if index == len(colors) - 1:
            rpm = full_rpm
        if index > 0 and rpm <= 0:
            rpm = 100
        stops.append((int(rpm), tuple(color)))
    return tuple(stops)


# -- geometry -----------------------------------------------------------------


def bar_rank(index: int, sequence: int, led_count: int = DEFAULT_LED_COUNT) -> int:
    """Mirror of `barRank()`: this LED's slot from the root of the fill."""
    half = led_count // 2
    if sequence == SEQ_LEFT_TO_RIGHT:
        return index
    if sequence == SEQ_RIGHT_TO_LEFT:
        return (led_count - 1) - index
    if sequence == SEQ_CENTER_IN:
        return (half - 1 - index) if index < half else (index - half)
    return index if index < half else (led_count - 1) - index


def bar_slots(sequence: int, led_count: int = DEFAULT_LED_COUNT) -> int:
    """Mirror of `barSlots()`: how many LEDs the fill has to cross."""
    if sequence in (SEQ_LEFT_TO_RIGHT, SEQ_RIGHT_TO_LEFT):
        return led_count
    return led_count // 2


def fill_units(rpm: int, slots: int, full_rpm: int) -> float:
    """Fill length in LED units: 1 at idle, `slots` at full_rpm. Fractional on purpose."""
    rpm = min(rpm, full_rpm)
    return _f32(1.0 + _f32(_f32(rpm * (slots - 1)) / full_rpm))


# -- rendering ----------------------------------------------------------------


@dataclass
class LedConfig:
    """A mirror of the Nano's live LED state (the `CFG:`/`RAMP:` settings)."""

    led_count: int = DEFAULT_LED_COUNT
    sequence: int = SEQ_CENTER_OUT
    color_mode: int = 0            # 0 = gradient (per-LED), 1 = wash (whole bar)
    full_rpm: int = 6800
    theme_dim: bool = False
    enabled: bool = True
    brightness: int = 255
    shift_rpm: int = 6300          # 0 disables the shift light
    shift_hz: int = 8
    shift_color: RGB = (255, 0, 0)
    ramp: Tuple[Tuple[int, RGB], ...] = DEFAULT_RAMP

    def with_ramp_from_colours(self, colors: Sequence[RGB]) -> "LedConfig":
        return replace(self, ramp=ramp_from_fractions(self.full_rpm, colors))


def render_bar(rpm: int, cfg: LedConfig) -> List[RGB]:
    """Mirror of `renderBar()`: the flowing color bar."""
    if rpm > cfg.full_rpm:
        rpm = cfg.full_rpm

    slots = bar_slots(cfg.sequence, cfg.led_count)
    # `float fill = 1.0f + ((float)rpm * (float)(slots - 1)) / (float)rpmFull;`
    fill = fill_units(rpm, slots, cfg.full_rpm)
    full = int(fill)
    frac = _f32(fill - full)
    span = _f32(fill - 1.0) if fill > 1.0 else 1.0
    scale = DIM_SCALE if cfg.theme_dim else 255

    frame: List[RGB] = [(0, 0, 0)] * cfg.led_count
    for index in range(cfg.led_count):
        rank = bar_rank(index, cfg.sequence, cfg.led_count)
        if rank < full:
            level = 1.0
        elif rank == full and frac > 0.05:
            level = frac
        else:
            continue

        p = _f32(rank / span)
        if p > 1.0:
            p = 1.0

        # Position mode samples each LED's share of the current rpm, so the gradient
        # flows; wash mode paints the whole bar the color of the present rpm.
        looked_up = rpm if cfg.color_mode else _u16(int(_f32(p * rpm)))
        r, g, b = ramp_color_at_rpm(looked_up, cfg.ramp)

        # (uint8_t)((uint16_t)r * level * scale / 255)
        frame[index] = (
            _byte(_f32(_f32(r * level) * scale) / 255),
            _byte(_f32(_f32(g * level) * scale) / 255),
            _byte(_f32(_f32(b * level) * scale) / 255),
        )
    return frame


def idle_frame(sequence: int, led_count: int = DEFAULT_LED_COUNT) -> List[RGB]:
    """Mirror of the `currentRPM == 0` branch: one blue pixel per fill direction."""
    frame: List[RGB] = [(0, 0, 0)] * led_count
    if sequence == SEQ_LEFT_TO_RIGHT:
        frame[0] = (0, 0, 255)
    elif sequence == SEQ_RIGHT_TO_LEFT:
        frame[led_count - 1] = (0, 0, 255)
    elif sequence == SEQ_CENTER_IN:
        frame[led_count // 2] = (0, 0, 255)
    else:
        frame[0] = (0, 0, 255)
        frame[led_count - 1] = (0, 0, 255)
    return frame


def shift_frame(now_ms: int, cfg: LedConfig) -> List[RGB]:
    """Mirror of the shift-light overlay: the whole strip blinks as one."""
    half_period = 500 // (cfg.shift_hz if cfg.shift_hz else 1)
    on = ((now_ms // half_period) & 1) == 0
    color = tuple(cfg.shift_color) if on else (0, 0, 0)
    return [color] * cfg.led_count  # type: ignore[list-item]


def can_offline_frame(now_ms: int, led_count: int = DEFAULT_LED_COUNT) -> List[RGB]:
    """Mirror of `drawCanOffline()`: two orange edge pixels, blinking at 1 Hz."""
    frame: List[RGB] = [(0, 0, 0)] * led_count
    if ((now_ms // 500) & 1) != 0:
        frame[0] = (255, 80, 0)
        frame[led_count - 1] = (255, 80, 0)
    return frame


def self_test_frame(elapsed_ms: int, mode: int,
                    led_count: int = DEFAULT_LED_COUNT) -> List[RGB]:
    """Mirror of `drawSelfTest()`: a white sweep, or the identify blink."""
    frame: List[RGB] = [(0, 0, 0)] * led_count
    if mode == SELF_TEST_IDENTIFY:
        color: RGB = (255, 0, 255) if ((elapsed_ms // 125) & 1) == 0 else (0, 0, 0)
        return [color] * led_count
    if mode == SELF_TEST_SWEEP:
        lit = int((elapsed_ms * led_count) / SELF_TEST_MS) + 1
        for index in range(led_count):
            if index < lit:
                frame[index] = (255, 255, 255)
    return frame


def error_frame(now_ms: int, position: int, direction: int,
                led_count: int = DEFAULT_LED_COUNT) -> Tuple[List[RGB], int, int]:
    """Mirror of the scanner drawing in `updateErrorAnimation()`.

    Returns (frame, position, direction) so a caller that only wants the picture does not
    have to thread the animation state itself.
    """
    base = 20 + 30 * (1 if (now_ms // 100) % 10 > 5 else 0)
    frame: List[RGB] = [(0, 0, 0)] * led_count
    for index in range(led_count):
        distance = abs(index - position)
        if distance == 0:
            frame[index] = (255, 80, 40)
        elif distance <= 3:
            trail = 200 - distance * 50
            frame[index] = (trail, trail // 8, 0)
        else:
            frame[index] = (base, 0, 0)
    return frame, position, direction


def advance_scanner(now_ms: int, last_ms: int, position: int, direction: int,
                    led_count: int = DEFAULT_LED_COUNT) -> Tuple[int, int, int]:
    """The 30 ms step of `updateErrorAnimation()`. Returns (last_ms, position, direction)."""
    if now_ms - last_ms < 30:
        return last_ms, position, direction
    position += direction
    if position >= led_count - 1:
        position = led_count - 1
        direction = -1
    elif position == 0:
        direction = 1
    return now_ms, position, direction


def apply_brightness(frame: Sequence[RGB], brightness: int) -> List[RGB]:
    """What `show()` transmits after `setBrightness()`.

    The library stores `b + 1` and scales `(v * stored) >> 8`, with the whole scale step
    skipped when the stored value is 0 - which is what `b = 255` produces, so 255 is
    "no scaling" rather than "almost no scaling".
    """
    stored = (brightness + 1) & 0xFF
    if stored == 0:
        return [tuple(rgb) for rgb in frame]  # type: ignore[misc]
    return [((r * stored) >> 8, (g * stored) >> 8, (b * stored) >> 8)
            for r, g, b in frame]


def smooth_rpm(smoothed: float, reading: float) -> float:
    """Mirror of the asymmetric filter in `readCANMessages()`."""
    if smoothed == 0.0:
        return reading
    delta = _f32(reading - smoothed)
    abs_delta = -delta if delta < 0.0 else delta
    if abs_delta >= RPM_SNAP_DELTA:
        return reading
    alpha = RPM_ALPHA_RISING if delta >= 0.0 else RPM_ALPHA_FALLING
    return _f32(smoothed + _f32(alpha * delta))


# -- stateful engine ----------------------------------------------------------


@dataclass
class LedEngine:
    """Stateful mirror of `updateLEDs()` plus the state it reads.

    `frame()` is the whole of `updateLEDs()`: test pattern, enable, CAN state, error
    animation, shift light, idle, then the bar - in that order, because that order is
    the precedence the firmware documents in LED_REVAMP_PLAN.md §6.1.
    """

    cfg: LedConfig = field(default_factory=LedConfig)
    can_initialized: bool = True
    error_mode: bool = False
    rpm: int = 0
    smoothed_rpm: float = 0.0
    self_test_mode: int = SELF_TEST_NONE
    self_test_started: int = 0
    _scan_position: int = 0
    _scan_direction: int = 1
    _scan_last: int = 0

    # -- driving the thing ---------------------------------------------------

    def feed_rpm(self, reading: int) -> None:
        """Mirror of one 0x201 decode, including the smoothing filter."""
        self.smoothed_rpm = smooth_rpm(self.smoothed_rpm, float(reading))
        self.rpm = int(self.smoothed_rpm + 0.5)

    def set_rpm(self, rpm: int) -> None:
        """Jump the rpm filter straight to a value - what a slider drag should do."""
        self.rpm = int(rpm)
        self.smoothed_rpm = float(rpm)

    def start_self_test(self, mode: int, now_ms: int) -> None:
        self.self_test_mode = mode
        self.self_test_started = now_ms

    def _self_test_running(self, now_ms: int) -> bool:
        if self.self_test_mode == SELF_TEST_NONE:
            return False
        elapsed = now_ms - self.self_test_started
        limit = IDENTIFY_MS if self.self_test_mode == SELF_TEST_IDENTIFY else SELF_TEST_MS
        if elapsed > limit:
            self.self_test_mode = SELF_TEST_NONE
            return False
        return True

    # -- the frame -----------------------------------------------------------

    def frame(self, now_ms: int) -> List[RGB]:
        cfg = self.cfg
        count = cfg.led_count

        if self._self_test_running(now_ms):
            return self_test_frame(now_ms - self.self_test_started,
                                   self.self_test_mode, count)

        if not cfg.enabled:
            return [(0, 0, 0)] * count

        if not self.can_initialized:
            return can_offline_frame(now_ms, count)

        if self.error_mode:
            self._scan_last, self._scan_position, self._scan_direction = advance_scanner(
                now_ms, self._scan_last, self._scan_position, self._scan_direction, count)
            frame, _, _ = error_frame(now_ms, self._scan_position,
                                      self._scan_direction, count)
            return frame

        if cfg.shift_rpm != 0 and self.rpm >= cfg.shift_rpm:
            return shift_frame(now_ms, cfg)

        if self.rpm == 0:
            return idle_frame(cfg.sequence, count)

        return render_bar(self.rpm, cfg)

    def shown(self, now_ms: int) -> List[RGB]:
        """The frame as transmitted: the same pixels after the brightness scale."""
        return apply_brightness(self.frame(now_ms), self.cfg.brightness)

    def describe(self, now_ms: int) -> dict:
        """The numbers behind the current frame, for the simulator's readouts."""
        cfg = self.cfg
        slots = bar_slots(cfg.sequence, cfg.led_count)
        fill = fill_units(min(self.rpm, cfg.full_rpm), slots, cfg.full_rpm)
        shifting = cfg.shift_rpm != 0 and self.rpm >= cfg.shift_rpm
        return {
            "rpm": self.rpm,
            "smoothed": self.smoothed_rpm,
            "slots": slots,
            "fill": fill,
            "filled_units": int(fill),
            "fraction_of_full": (min(self.rpm, cfg.full_rpm) / cfg.full_rpm
                                 if cfg.full_rpm else 0.0),
            "tip_colour": ramp_color_at_rpm(min(self.rpm, cfg.full_rpm), cfg.ramp),
            "shifting": shifting,
            "sequence": SEQUENCE_NAMES.get(cfg.sequence, "?"),
            "mode": "wash" if cfg.color_mode else "gradient",
        }
