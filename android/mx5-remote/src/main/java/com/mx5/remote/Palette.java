package com.mx5.remote;

import android.graphics.Color;

/**
 * The webapp's twelve colour schemes, ported, plus the resolved colours the UI
 * actually paints with.
 *
 * The webapp derives everything from two seed hues with OKLCH and CSS
 * color-mix. There is no OKLCH in the Android view toolkit, so the same idea is
 * approximated here with simple sRGB blends: the scheme supplies two hues, the
 * mode decides whether they are lifted (dark) or sunk (light), and the surface
 * colours stay fixed per mode. It is close enough that a scheme is recognisable
 * across the webapp and the car, which is the point.
 *
 * Alert stays orange in every scheme. That mirrors the standard's rule that the
 * alert hue must not follow the decor.
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

    private Palette(boolean dark, int accent, int primary) {
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
        return new Palette(dark, accent, primary);
    }

    public static Palette of(int schemeIndex, boolean dark) {
        return of(SCHEMES[Math.floorMod(schemeIndex, SCHEMES.length)].id, dark);
    }

    /** Blend toward white. */
    public static int lift(int c, float t) {
        return mix(c, Color.WHITE, t);
    }

    /** Blend toward black. */
    public static int sink(int c, float t) {
        return mix(c, Color.BLACK, t);
    }

    public static int mix(int a, int b, float t) {
        float u = 1f - t;
        return Color.argb(
                Math.round(Color.alpha(a) * u + Color.alpha(b) * t),
                Math.round(Color.red(a) * u + Color.red(b) * t),
                Math.round(Color.green(a) * u + Color.green(b) * t),
                Math.round(Color.blue(a) * u + Color.blue(b) * t));
    }

    /** A translucent version of a colour, for washes and glows. */
    public static int alpha(int c, float a) {
        return Color.argb(Math.round(255 * a), Color.red(c), Color.green(c), Color.blue(c));
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
     * The top of the page gradient: the page colour nudged toward the scheme
     * accent. A flat page reads as unbranded; a 10% lift gives the app an
     * atmosphere without competing with the panels.
     */
    public int pageGlow() {
        return mix(page, accent, dark ? 0.10f : 0.07f);
    }
}
