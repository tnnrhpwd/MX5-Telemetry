"""The phone app's color schemes, so the simulator can show the ramp they produce.

The app owns the LED strip's colors: `MainActivity.pushThemeToPi()` derives a six-stop
ramp from the active `Palette` and pushes it. To preview that in the simulator, the
derivation has to be the app's, not a lookalike - so this is a port of
`android/mx5-remote/src/main/java/com/mx5/remote/Palette.java`, and
`palette_parity.py` compiles the real `Palette.java` and diffs the two.

What is ported is only what the ramp needs: the twelve schemes, the dark/light derivation
of `accent` and `primary`, and `Palette.ramp()`. The surface colors (page, panel, tile...)
exist in the Java but not here, because the ramp does not use them.
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
    seed_b: int
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
    return Palette(scheme=ident, dark=dark, accent=accent, primary=primary,
                   seed_b=seed_b)


def ramp_colors(pal: Palette) -> List[int]:
    """`Palette.ramp()`: all six stop colors, derived from the scheme's own hues.

    The bar belongs to the theme: it runs from the mode-corrected accent up through the
    primary to the vivid seed, so every one of the twelve schemes produces a different
    ramp. None of the alarm colors (warn, bad, alert) appear - those stay fixed across
    themes and are used by the indicators that flash.
    """
    a, b, vivid = pal.accent, pal.primary, pal.seed_b
    return [a,
            mix(a, b, 0.40),
            mix(a, b, 0.75),
            b,
            mix(b, vivid, 0.55),
            vivid]


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
