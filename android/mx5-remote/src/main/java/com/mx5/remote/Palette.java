package com.mx5.remote;

/**
 * The webapp's twelve color schemes, ported, plus the resolved colors the UI
 * actually paints with.
 *
 * The webapp derives everything from two seed hues with OKLCH and CSS
 * color-mix. There is no OKLCH in the Android view toolkit, so the same idea is
 * approximated here with simple sRGB blends: the scheme supplies two hues, the
 * mode decides whether they are lifted (dark) or sunk (light), and the surface
 * colors stay fixed per mode. It is close enough that a scheme is recognizable
 * across the webapp and the car, which is the point.
 *
 * Alert stays orange in every scheme. That mirrors the standard's rule that the
 * alert hue must not follow the decor. That rule covers the things that report a
 * fault - the alert, bad and warn roles, and the strip's CAN-offline and error
 * patterns - and it covers the strip's rpm ramp and shift light too: those report
 * the engine, so they use the same colors in every scheme; see {@link #ramp()}.
 */
public final class Palette {

    public static final class Scheme {
        public final String id;
        public final String name;
        public final int a;
        public final int b;

        Scheme(String id, String name, int a, int b) {
            this.id = id;
            this.name = name;
            this.a = a;
            this.b = b;
        }
    }

    public static final Scheme[] SCHEMES = {
            new Scheme("aurora", "Aurora", 0xFF00C1C1, 0xFFFF379B),
            new Scheme("crimson", "Crimson", 0xFFDC2626, 0xFFF472B6),
            new Scheme("emerald", "Emerald", 0xFF10B981, 0xFF06B6D4),
            new Scheme("sakura", "Sakura", 0xFFEC4899, 0xFFA78BFA),
            new Scheme("midnight", "Midnight", 0xFF3B82F6, 0xFF8B5CF6),
            new Scheme("sunset", "Sunset", 0xFFF97316, 0xFFEC4899),
            new Scheme("ocean", "Ocean", 0xFF06B6D4, 0xFF3B82F6),
            new Scheme("cyberpunk", "Cyberpunk", 0xFFF0E030, 0xFFE040FB),
            new Scheme("monokai", "Monokai", 0xFFA6E22E, 0xFF66D9EF),
            new Scheme("usa", "USA", 0xFFB22234, 0xFF3C3B6E),
            new Scheme("forest", "Forest", 0xFF4D8C57, 0xFF65A30D),
            new Scheme("neutral", "Neutral", 0xFF808080, 0xFF808080)
    };

    public static int indexOf(String id) {
        for (int i = 0; i < SCHEMES.length; i++) {
            if (SCHEMES[i].id.equals(id)) {
                return i;
            }
        }
        return 0;
    }

    public final boolean dark;
    public final int page;
    public final int panel;
    public final int panelStroke;
    public final int panelHead;
    public final int accent;
    public final int primary;
    public final int alert;
    public final int good;
    public final int bad;
    public final int warn;
    public final int text;
    public final int textDim;
    public final int track;
    /** A surface raised inside a panel, for tiles and fields. */
    public final int tile;
    /** A neutral tone-change edge. Not a border to decorate with. */
    public final int hairline;

    private Palette(boolean dark, Scheme scheme, int accent, int primary) {
        this.dark = dark;
        if (dark) {
            page = 0xFF141416;
            panel = 0xFF212124;
            panelStroke = 0xFF333338;
            tile = 0xFF2A2A2E;
            hairline = 0xFF333338;
            text = 0xFFF4F7FD;
            textDim = 0xFF9BA1AB;
            track = 0xFF3A3A40;
        } else {
            page = 0xFFEEF2F9;
            panel = 0xFFFFFFFF;
            panelStroke = 0xFFE2E7F0;
            tile = 0xFFF4F7FD;
            hairline = 0xFFE2E7F0;
            text = 0xFF16223A;
            textDim = 0xFF5B6478;
            track = 0xFFD7DDEA;
        }
        this.accent = accent;
        this.primary = primary;
        panelHead = mix(panel, accent, dark ? 0.22f : 0.14f);
        alert = 0xFFFF8C32;
        good = 0xFF22C55E;
        bad = 0xFFEF4444;
        warn = 0xFFF59E0B;
    }

    public static Palette of(String schemeId, boolean dark) {
        Scheme s = SCHEMES[indexOf(schemeId)];
        // Dark pages want brighter seeds, light pages want deeper ones, exactly as
        // the webapp's per-mode lightness targets do.
        float amt = 0.18f;
        int accent = dark ? lift(s.a, amt) : sink(s.a, amt);
        int primary = dark ? lift(s.b, amt) : sink(s.b, amt);
        return new Palette(dark, s, accent, primary);
    }

    /**
     * The stop rpms of the LED strip's ramp: where each color sits on the rev range.
     *
     * Fixed rather than scaled to a "full at" the owner picks, so the ramp can be
     * generated without knowing the car. The last stop is therefore also the rpm at
     * which the strip is completely lit.
     */
    public static final int[] RAMP_RPMS = {0, 1400, 2800, 4500, 5800, 6800};

    /**
     * The engine's own ramp, byte-for-byte the firmware's default table.
     *
     * The strip's colors mean rpm, so they cannot be derived from a scheme. Deriving
     * them made 5000 rpm green on one theme and orange on another, left most schemes
     * with no red anywhere on the bar, and - blended 18% toward white for dark mode -
     * produced the washed-out bar and the pink "redline" the owner reported.
     *
     * Matching the firmware default exactly also means the strip looks the same
     * whether or not the phone has ever pushed a ramp to it.
     *
     * Every stop is fully saturated - one channel is zero - because `renderBar()`
     * interpolates between stops in RGB. A stop with a lifted channel drags the whole
     * segment around it toward grey: the previous green (0x32d782, 77%) and yellow
     * (0xffd23c, 76%) made the bar measure 50% saturation at 3300 rpm. With a zero
     * channel on both ends of every segment the interpolation keeps it at zero, so the
     * bar is 100% saturated everywhere. `palette_parity.py` fails if that stops being
     * true.
     */
    private static final int[] ENGINE_RAMP = {
            0xFF0000FF,   //    0  idle - blue
            0xFF00DCFF,   // 1400  pulling away - cyan
            0xFF00D700,   // 2800  economical cruise - green
            0xFFFFD500,   // 4500  waking up - yellow
            0xFFFF8000,   // 5800  spirited - orange
            0xFFFF0000,   // 6800  redline - red
    };

    /**
     * The six colors the strip climbs through.
     *
     * These are the engine's colors, identical in every scheme and mode: blue at idle,
     * cyan, green through the economical band, yellow, orange, and red at the redline.
     * The theme still reaches the strip through brightness - `led_theme_dim` dims the
     * bar in dark mode, and dimming scales all three channels equally, so it darkens a
     * color without desaturating it.
     *
     * See {@link #shiftColor()} for the one alarm, and why the fault patterns are fixed.
     */
    public int[] ramp() {
        return ENGINE_RAMP.clone();
    }

    /**
     * The color the shift light flashes.
     *
     * Red, like the top of the bar: a shift light is an alarm, not decor, so it must not
     * change meaning with the theme (and a scheme-lifted hue is how a shift flash ended
     * up pink). The firmware flashes the whole strip, so a full bar still blinks visibly.
     *
     * The *fault* patterns stay fixed too: the CAN-offline pair is orange and the error
     * scanner red in every scheme. They mean the electronics are broken rather than that
     * the engine is at the shift point.
     */
    public int shiftColor() {
        return 0xFFFF0000;
    }

    public static Palette of(int schemeIndex, boolean dark) {
        return of(SCHEMES[Math.floorMod(schemeIndex, SCHEMES.length)].id, dark);
    }

    /** Blend toward white. */
    public static int lift(int c, float t) {
        return mix(c, 0xFFFFFFFF, t);
    }

    /** Blend toward black. */
    public static int sink(int c, float t) {
        return mix(c, 0xFF000000, t);
    }

    /**
     * Blend two ARGB colors.
     *
     * Plain bit arithmetic rather than {@code android.graphics.Color}: this class holds
     * no state and touches no Android API, so the LED ramp can be compiled and asserted
     * with a plain {@code javac} outside a device build. The maths is identical to
     * {@code Color.argb / red / green / blue}.
     */
    public static int mix(int a, int b, float t) {
        float u = 1f - t;
        int alpha = Math.round(((a >>> 24) & 0xFF) * u + ((b >>> 24) & 0xFF) * t);
        int r = Math.round(((a >> 16) & 0xFF) * u + ((b >> 16) & 0xFF) * t);
        int g = Math.round(((a >> 8) & 0xFF) * u + ((b >> 8) & 0xFF) * t);
        int bl = Math.round((a & 0xFF) * u + (b & 0xFF) * t);
        return ((alpha & 0xFF) << 24) | ((r & 0xFF) << 16) | ((g & 0xFF) << 8) | (bl & 0xFF);
    }

    /** A translucent version of a color, for washes and glows. */
    public static int alpha(int c, float a) {
        return ((Math.round(255 * a) & 0xFF) << 24) | (c & 0x00FFFFFF);
    }

    /** The accent as a wash, for an active chip or a selected rail row. */
    public int accentWash() {
        return alpha(accent, dark ? 0.20f : 0.14f);
    }

    /** A wash of any accent at the right weight for this mode. */
    public int washOf(int c) {
        return alpha(c, dark ? 0.20f : 0.14f);
    }

    /**
     * The top of the page gradient: the page color nudged toward the scheme
     * accent. A flat page reads as unbranded; a 10% lift gives the app an
     * atmosphere without competing with the panels.
     */
    public int pageGlow() {
        return mix(page, accent, dark ? 0.10f : 0.07f);
    }
}
