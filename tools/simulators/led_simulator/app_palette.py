"""The phone app's color schemes, so the simulator can show what the phone would push.

The app owns the LED strip's settings: `MainActivity.pushThemeToPi()` sends a six-stop
ramp plus the shift colour. To preview that in the simulator, the payload has to be the
app's, not a lookalike - so this is a port of
`android/mx5-remote/src/main/java/com/mx5/remote/Palette.java`, and
`palette_parity.py` compiles the real `Palette.java` and diffs the two.

What is ported is the twelve schemes, the dark/light derivation of `accent` and
`primary`, `Palette.ramp()` and `Palette.shiftColor()`. The surface colors (page, panel,
tile...) exist in the Java but not here, because nothing the strip receives uses them.

The ramp and the shift colour are **the engine's**, not the scheme's: they encode rpm, so
they are identical in every scheme and mode, and the scheme only reaches the strip as the
dark-mode dim flag. See `Palette.java` and ISSUE-24 in
`docs/IN_CAR_FINDINGS_2026-11-26.md`.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from typing import List, Sequence, Tuple

RGB = Tuple[int, int, int]

# `Palette.SCHEMES`, in the app's order: id, display name, seed a, seed b. The seeds are
# the app's ints verbatim, alpha byte included.
SCHEMES: Tuple[Tuple[str, str, int, int], ...] = (
    ("aurora", "Aurora", 0xFF00C1C1, 0xFFFF379B),
    ("crimson", "Crimson", 0xFFDC2626, 0xFFF472B6),
    ("emerald", "Emerald", 0xFF10B981, 0xFF06B6D4),
    ("sakura", "Sakura", 0xFFEC4899, 0xFFA78BFA),
    ("midnight", "Midnight", 0xFF3B82F6, 0xFF8B5CF6),
    ("sunset", "Sunset", 0xFFF97316, 0xFFEC4899),
    ("ocean", "Ocean", 0xFF06B6D4, 0xFF3B82F6),
    ("cyberpunk", "Cyberpunk", 0xFFF0E030, 0xFFE040FB),
    ("monokai", "Monokai", 0xFFA6E22E, 0xFF66D9EF),
    ("usa", "USA", 0xFFB22234, 0xFF3C3B6E),
    ("forest", "Forest", 0xFF4D8C57, 0xFF65A30D),
    ("neutral", "Neutral", 0xFF808080, 0xFF808080),
)

# `float amt = 0.18f;` in Palette.of() - how far a seed is lifted or sunk for the mode.
LIFT_AMOUNT = 0.18

# The semantic colors are fixed per Palette instance, not per scheme. They are the alarm
# colors: they mean "something is wrong", so they do not follow the theme, and they are
# used by the indicators that flash rather than by the ramp.
GOOD = 0x22C55E
WARN = 0xF59E0B
BAD = 0xEF4444
ALERT = 0xFF8C32      # "Alert stays orange in every scheme."

# `Palette.RAMP_RPMS`: where each of the six stops sits on the rev range.
RAMP_RPMS: Tuple[int, ...] = (0, 1400, 2800, 4500, 5800, 6800)

# `Palette.ENGINE_RAMP`, verbatim: the engine's colours, identical in every scheme.
# One channel is zero in every stop, so the firmware's RGB interpolation between stops
# cannot lift it and the bar stays at 100% saturation all the way up the rev range.
ENGINE_RAMP: Tuple[int, ...] = (
    0xFF0000FF,   #    0  idle - blue
    0xFF00DCFF,   # 1400  pulling away - cyan
    0xFF00D700,   # 2800  economical cruise - green
    0xFFFFD500,   # 4500  waking up - yellow
    0xFFFF8000,   # 5800  spirited - orange
    0xFFFF0000,   # 6800  redline - red
)

# `Palette.shiftColor()`: red, like the top of the bar.
ENGINE_SHIFT = 0xFFFF0000


def index_of(scheme_id: str) -> int:
    for index, (ident, _name, _a, _b) in enumerate(SCHEMES):
        if ident == scheme_id:
            return index
    return 0


def _f32(value: float) -> float:
    """Round to float32 - Java's `float` is 32-bit, and the derivation is done in it."""
    return struct.unpack("<f", struct.pack("<f", value))[0]


def _java_round(value: float) -> int:
    """Java's `Math.round(float)`: `floor(x + 0.5f)`, in float32.

    Not Python's `round()`, which is banker's rounding on a 64-bit float. The difference is
    visible: 0x3B82F6 lifted by 0.18 has a channel that lands on 152.5, which Java rounds
    up to 153 and Python's round() would take to 152. `palette_parity.py` found exactly
    that in two schemes.
    """
    return int(math.floor(_f32(value + 0.5)))


def _blend(ca: int, cb: int, u: float, t: float) -> int:
    """One channel of `Palette.mix()`, in the same order and precision as the Java."""
    return _java_round(_f32(_f32(ca * u) + _f32(cb * t)))


def mix(a: int, b: int, t: float) -> int:
    """Palette.mix(): per-channel blend, alpha included, rounded the Java way."""
    t32 = _f32(t)
    u = _f32(1.0 - t32)
    return _argb(_blend(_alpha(a), _alpha(b), u, t32),
                 _blend(_red(a), _red(b), u, t32),
                 _blend(_green(a), _green(b), u, t32),
                 _blend(_blue(a), _blue(b), u, t32))


def lift(color: int, t: float) -> int:
    return mix(color, 0xFFFFFFFF, t)


def sink(color: int, t: float) -> int:
    return mix(color, 0xFF000000, t)


def _argb(a: int, r: int, g: int, b: int) -> int:
    return ((a & 0xFF) << 24) | ((r & 0xFF) << 16) | ((g & 0xFF) << 8) | (b & 0xFF)


def _alpha(color: int) -> int:
    return (color >> 24) & 0xFF


def _red(color: int) -> int:
    return (color >> 16) & 0xFF


def _green(color: int) -> int:
    return (color >> 8) & 0xFF


def _blue(color: int) -> int:
    return color & 0xFF


@dataclass(frozen=True)
class Palette:
    """The resolved colors for one scheme in one mode."""

    scheme: str
    dark: bool
    accent: int
    primary: int
    good: int = GOOD
    warn: int = WARN
    bad: int = BAD
    alert: int = ALERT

    def role(self, name: str) -> int:
        return getattr(self, name)


def palette(scheme_id: str = "aurora", dark: bool = True) -> Palette:
    """`Palette.of(schemeId, dark)`: seeds lifted for dark, sunk for light."""
    ident, _name, seed_a, seed_b = SCHEMES[index_of(scheme_id)]
    amount = LIFT_AMOUNT
    accent = lift(seed_a, amount) if dark else sink(seed_a, amount)
    primary = lift(seed_b, amount) if dark else sink(seed_b, amount)
    return Palette(scheme=ident, dark=dark, accent=accent, primary=primary)


def ramp_colors(pal: Palette) -> List[int]:
    """`Palette.ramp()`: the six stop colors.

    The engine's colors, not the scheme's: blue at idle through to red at the redline, the
    same in all twelve schemes and both modes. They mean rpm, so a theme cannot own them -
    deriving them from the palette is what produced a washed-out bar, schemes with no red
    anywhere, and a pink "redline".

    `pal` is accepted because every caller keys off a scheme; the answer no longer depends
    on it.
    """
    del pal
    return list(ENGINE_RAMP)


def ramp_for(pal: Palette) -> Tuple[Tuple[int, RGB], ...]:
    """`MainActivity.ledRampFor()`: the six stops the phone would push.

    Note the rpms are the app's *fixed* table, not a fraction of "full at" - so applying a
    theme always ends the ramp at 6800 and therefore sets the strip's full-illumination rpm
    to 6800. That is what the car does today; the simulator reproduces it rather than
    quietly doing something nicer.
    """
    return tuple((rpm, (_red(color), _green(color), _blue(color)))
                 for rpm, color in zip(RAMP_RPMS, ramp_colors(pal)))


def ramp_text(scheme_id: str = "aurora", dark: bool = True) -> str:
    """The `RAMP:` payload the phone would send for this scheme."""
    return ",".join("%d:%02x%02x%02x" % (rpm, rgb[0], rgb[1], rgb[2])
                    for rpm, rgb in ramp_for(palette(scheme_id, dark)))


def shift_color(pal: Palette) -> int:
    """`Palette.shiftColor()`: the color the shift light flashes.

    Red, in every scheme. The shift light is an alarm, not decoration, and a scheme-lifted
    hue is how it used to end up pink. The fault patterns (CAN offline, the error scanner)
    stay orange and red too, for the same reason.

    `pal` is accepted because every caller keys off a scheme; the answer no longer depends
    on it.
    """
    del pal
    return ENGINE_SHIFT


def shift_text(scheme_id: str = "aurora", dark: bool = True) -> str:
    """The `led_shift_color` payload the phone would send for this scheme."""
    return "%06x" % (shift_color(palette(scheme_id, dark)) & 0xFFFFFF)
