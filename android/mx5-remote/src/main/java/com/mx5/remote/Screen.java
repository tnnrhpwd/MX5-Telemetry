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

    /**
     * A horizontal row of cells, each taking an equal share of the width.
     * The row carries its own params so a caller that forgets them cannot end up
     * with a wrapper-width row, which collapses to nothing inside a column.
     */
    protected static LinearLayout grid(Context c, View... cells) {
        LinearLayout r = Ui.row(c);
        for (View v : cells) {
            r.addView(v, Ui.cell(c, 3));
        }
        r.setLayoutParams(new LinearLayout.LayoutParams(
                android.view.ViewGroup.LayoutParams.MATCH_PARENT,
                android.view.ViewGroup.LayoutParams.WRAP_CONTENT));
        return r;
    }

    /**
     * Like grid(), but the row claims an equal share of the panel's leftover height and
     * its cells stretch with it. A dashboard whose tiles are pinned to the top of a tall
     * panel leaves a dead field below them; weighted rows distribute instead.
     */
    protected static LinearLayout gridFill(Context c, View... cells) {
        LinearLayout r = Ui.row(c);
        for (View v : cells) {
            r.addView(v, Ui.cellFill(c, 3));
        }
        r.setLayoutParams(Ui.fillHeight());
        return r;
    }

    /** Text showing a value with a trailing unit, or a dash when there is none. */
    protected static String num(double value, String format) {
        return String.format(format, value);
    }
}

