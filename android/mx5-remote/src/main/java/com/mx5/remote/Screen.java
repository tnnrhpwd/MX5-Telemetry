package com.mx5.remote;

import android.content.Context;
import android.view.View;
import android.widget.LinearLayout;

/**
 * One page of the car app.
 *
 * A screen builds its view once per theme or scheme change and then only rebinds
 * values on each telemetry poll, so the tree is never rebuilt while driving.
 */
public abstract class Screen {

    /** Callbacks a screen is allowed to make back into the shell. */
    public interface Host {
        PiClient pi();

        void toast(String message, boolean error);

        /** Force an immediate status and telemetry refresh. */
        void refreshNow();

        /** The Pi's current unit preference, so screens format the same way. */
        boolean useMph();

        /** Current connection target, and a way to change it. */
        String piAddress();

        String piToken();

        void applyConnection(String address, String token);

        /** Ask the shell to step the Pi's own display. */
        void stepPiScreen(boolean forward);
    }

    public abstract String title();

    /**
     * A shorter name for the rail when the window is narrow. On a phone the rail
     * becomes a strip of nine items across roughly 400dp, which is about 44dp
     * each, so anything longer than about six characters wraps to three lines.
     */
    public String shortTitle() {
        return title();
    }

    public String eyebrow() {
        return "MX5";
    }

    /** Which palette hue this screen wears: 0 is the scheme accent, 1 the primary. */
    public int hue() {
        return 0;
    }

    /** The Pi's screen index this page mirrors, or -1 when the Pi has no such page. */
    public int piScreen() {
        return -1;
    }

    public abstract View build(Context c, Palette p, Host host);

    public void bind(Telemetry t) {
    }

    /** Called with the payload from GET /api/status whenever it arrives. */
    public void applyStatus(org.json.JSONObject status) {
    }

    protected static int hueColor(Palette p, int hue) {
        return hue == 1 ? p.primary : p.accent;
    }

    /** Below this width the app is on a phone in portrait rather than on a car screen. */
    private static final int NARROW_WIDTH_DP = 600;

    /**
     * Tiles per row on a phone.
     *
     * Four across 380dp leaves each tile about 85dp, which is narrower than its own
     * caption needs, so the caption truncates and the value crowds the unit. Two columns
     * give every tile room for both.
     */
    private static final int NARROW_COLUMNS = 2;

    /** True when the window is a phone in portrait rather than a car screen. */
    public static boolean isNarrow(Context c) {
        return c.getResources().getConfiguration().screenWidthDp < NARROW_WIDTH_DP;
    }

    /** One row of equal-width cells, optionally claiming a share of the height. */
    private static LinearLayout gridRow(Context c, boolean fill, View[] cells) {
        LinearLayout r = Ui.row(c);
        for (View v : cells) {
            r.addView(v, fill ? Ui.cellFill(c, 3) : Ui.cell(c, 3));
        }
        r.setLayoutParams(fill ? Ui.fillHeight() : new LinearLayout.LayoutParams(
                android.view.ViewGroup.LayoutParams.MATCH_PARENT,
                android.view.ViewGroup.LayoutParams.WRAP_CONTENT));
        return r;
    }

    /**
     * Take up to count cells from index, padding with empty views.
     *
     * The padding matters: without it a final row holding one cell would stretch that cell
     * to the full width, so a grid of five tiles would have a double-width tile at the end.
     */
    private static View[] slice(Context c, View[] all, int from, int count) {
        View[] out = new View[count];
        for (int i = 0; i < count; i++) {
            out[i] = (from + i < all.length) ? all[from + i] : new View(c);
        }
        return out;
    }

    /**
     * A horizontal row of cells, each taking an equal share of the width.
     * The row carries its own params so a caller that forgets them cannot end up
     * with a wrapper-width row, which collapses to nothing inside a column.
     *
     * On a phone the same cells become rows of {@link #NARROW_COLUMNS} instead, so every
     * screen becomes phone-shaped without each one having to know about it.
     */
    protected static LinearLayout grid(Context c, View... cells) {
        if (!isNarrow(c) || cells.length <= NARROW_COLUMNS) {
            return gridRow(c, false, cells);
        }
        LinearLayout col = Ui.column(c);
        col.setLayoutParams(new LinearLayout.LayoutParams(
                android.view.ViewGroup.LayoutParams.MATCH_PARENT,
                android.view.ViewGroup.LayoutParams.WRAP_CONTENT));
        for (int i = 0; i < cells.length; i += NARROW_COLUMNS) {
            col.addView(gridRow(c, false, slice(c, cells, i, NARROW_COLUMNS)));
        }
        return col;
    }

    /**
     * Like grid(), but the row claims an equal share of the panel's leftover height and
     * its cells stretch with it. A dashboard whose tiles are pinned to the top of a tall
     * panel leaves a dead field below them; weighted rows distribute instead.
     *
     * On a phone that becomes a weighted column of weighted rows, so the space is shared
     * between the rows rather than each row fighting for all of it.
     */
    protected static LinearLayout gridFill(Context c, View... cells) {
        if (isNarrow(c)) {
            // A phone's panel is around 700dp tall. Distributing that height, which is what
            // makes the car canvas work, would give each tile a quarter of the screen and
            // strand its caption in the middle of a large empty card. Natural height
            // instead, and the leftover stays at the bottom where it reads as margin.
            return grid(c, cells);
        }
        return gridRow(c, true, cells);
    }

    /** Text showing a value with a trailing unit, or a dash when there is none. */
    protected static String num(double value, String format) {
        return String.format(format, value);
    }
}

