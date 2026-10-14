package com.mx5.remote;

import android.content.Context;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * The view toolkit the whole car UI is built from.
 *
 * Two rules from the webapp's frontend standard drive nearly every choice here:
 *
 *   - **Tone before border.** Surfaces separate by being different tones of the same
 *     family, never by a hairline drawn round them. A page of outlined boxes reads as
 *     a spreadsheet; a page of tones reads as a product.
 *   - **A real type scale.** Six sizes with fixed jobs, rather than every call site
 *     picking its own. The eyebrow and caption sizes carry letter spacing so they read
 *     as labels rather than as small text.
 *
 * Everything is built in code because almost every colour is derived from the runtime
 * palette, so a theme or scheme change simply rebuilds the screen.
 *
 * Note on sizing: unlike the webapp there is no `--nav-size` unit here, and that is
 * deliberate. Android's dp and sp already resolve against the panel's real density, so
 * dp IS the portable unit; re-scaling it by canvas size would make the same text land
 * at different physical sizes on an 800x480 head unit and a 1080p one.
 */
public final class Ui {

    private Ui() {
    }

    // ---------------------------------------------------------------- type scale

    /** Screen and shell titles. */
    public static final float TYPE_DISPLAY = 19f;
    /** Panel titles. */
    public static final float TYPE_TITLE = 13f;
    /** The number a tile exists to show. */
    public static final float TYPE_VALUE = 25f;
    /** Body copy and control labels. */
    public static final float TYPE_BODY = 11f;
    /** Secondary labels, bar values. */
    public static final float TYPE_LABEL = 10f;
    /** Uppercase micro-labels: eyebrows, tiles, pills. */
    public static final float TYPE_EYEBROW = 8f;

    /** Letter spacing for the uppercase micro-labels. */
    public static final float TRACK_CAPS = 0.12f;

    // -------------------------------------------------------------- spacing scale

    public static final int S1 = 2;
    public static final int S2 = 4;
    public static final int S3 = 6;
    public static final int S4 = 8;
    public static final int S5 = 12;

    // ------------------------------------------------------------------ primitives

    public static int dp(Context c, float v) {
        return Math.round(TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v,
                c.getResources().getDisplayMetrics()));
    }

    public static GradientDrawable rounded(Context c, int color, float radiusDp) {
        GradientDrawable d = new GradientDrawable();
        d.setShape(GradientDrawable.RECTANGLE);
        d.setColor(color);
        d.setCornerRadius(dp(c, radiusDp));
        return d;
    }

    public static GradientDrawable roundedTop(Context c, int color, float radiusDp) {
        GradientDrawable d = new GradientDrawable();
        d.setShape(GradientDrawable.RECTANGLE);
        d.setColor(color);
        float r = dp(c, radiusDp);
        d.setCornerRadii(new float[]{r, r, r, r, 0, 0, 0, 0});
        return d;
    }

    /**
     * Tabular figures. Without this a live number changes width as its digits change,
     * so a speed readout visibly jitters every update. It is the single cheapest thing
     * that makes a dashboard look considered.
     */
    public static TextView tnum(TextView t) {
        t.setFontFeatureSettings("tnum");
        return t;
    }

    public static TextView label(Context c, float sp, int color) {
        TextView t = new TextView(c);
        t.setTextSize(sp);
        t.setTextColor(color);
        t.setIncludeFontPadding(false);
        return t;
    }

    /** An uppercase, letter-spaced micro-label. */
    public static TextView caps(Context c, float sp, int color) {
        TextView t = label(c, sp, color);
        t.setAllCaps(true);
        t.setLetterSpacing(TRACK_CAPS);
        t.setSingleLine(true);
        return t;
    }

    public static LinearLayout column(Context c) {
        LinearLayout l = new LinearLayout(c);
        l.setOrientation(LinearLayout.VERTICAL);
        return l;
    }

    public static LinearLayout row(Context c) {
        LinearLayout l = new LinearLayout(c);
        l.setOrientation(LinearLayout.HORIZONTAL);
        l.setGravity(Gravity.CENTER_VERTICAL);
        return l;
    }

    /** A horizontal spacer that eats the leftover width. */
    public static View gap(Context c) {
        View v = new View(c);
        v.setLayoutParams(new LinearLayout.LayoutParams(0, 1, 1f));
        return v;
    }

    /** A tone-change separator. Use sparingly; prefer surface tones. */
    public static View hairline(Context c, int color) {
        View v = new View(c);
        v.setBackgroundColor(color);
        v.setLayoutParams(lp(ViewGroup.LayoutParams.MATCH_PARENT, Math.max(1, dp(c, 1))));
        return v;
    }

    public static LinearLayout.LayoutParams lp(int w, int h) {
        return new LinearLayout.LayoutParams(w, h);
    }

    public static LinearLayout.LayoutParams wex(float weight, int h) {
        return new LinearLayout.LayoutParams(0, h, weight);
    }

    public static Typeface bold() {
        return Typeface.create(Typeface.DEFAULT, Typeface.BOLD);
    }

    // ---------------------------------------------------------------- layout params

    // Split by axis on purpose. A LinearLayout only divides space by weight along its
    // OWN orientation, so the two directions need opposite treatment and naming them
    // apart stops the two being confused: cell() is a child of a row, stack() is a
    // child of a column. Set the wrong axis to zero and the view vanishes entirely.

    /** A cell in a horizontal row: an equal share of the width, natural height. */
    public static LinearLayout.LayoutParams cell(Context c, int marginDp) {
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        p.setMargins(dp(c, marginDp), dp(c, marginDp), dp(c, marginDp), dp(c, marginDp));
        return p;
    }

    /** A cell that also fills the height of its row. */
    public static LinearLayout.LayoutParams cellFill(Context c, int marginDp) {
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.MATCH_PARENT, 1f);
        p.setMargins(dp(c, marginDp), dp(c, marginDp), dp(c, marginDp), dp(c, marginDp));
        return p;
    }

    /** An item stacked in a vertical column: full width, natural height. */
    public static LinearLayout.LayoutParams stack(Context c, int marginDp) {
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        p.setMargins(dp(c, marginDp), dp(c, marginDp), dp(c, marginDp), dp(c, marginDp));
        return p;
    }

    /** Fills the leftover height of a vertical parent. */
    public static LinearLayout.LayoutParams fillHeight() {
        return new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f);
    }

    /** Fills the leftover width of a horizontal parent. */
    public static LinearLayout.LayoutParams fillWidth() {
        return new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.MATCH_PARENT, 1f);
    }

    public static LinearLayout.LayoutParams withTop(Context c, int topDp) {
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        p.topMargin = dp(c, topDp);
        return p;
    }

    // ---------------------------------------------------------------------- parts

    /**
     * A titled surface. The head is an accent wash, so each panel announces its own
     * colour and the eye can find a panel without reading it.
     */
    public static class Panel extends LinearLayout {

        public final LinearLayout body;
        private final LinearLayout head;
        private final Palette palette;
        private final TextView eyebrow;
        private final TextView title;
        private int accent;

        public Panel(Context c, Palette p, String eyebrowText, String titleText, int accentColor) {
            super(c);
            accent = accentColor;
            palette = p;
            setOrientation(VERTICAL);
            setBackground(rounded(c, p.panel, 12f));

            head = row(c);
            head.setBackground(roundedTop(c,
                    Palette.mix(p.panel, accentColor, p.dark ? 0.26f : 0.16f), 12f));
            head.setPadding(dp(c, 10), dp(c, 7), dp(c, 10), dp(c, 7));

            LinearLayout titles = column(c);
            eyebrow = caps(c, TYPE_EYEBROW, p.textDim);
            eyebrow.setText(eyebrowText);
            title = label(c, TYPE_TITLE, accentColor);
            title.setTypeface(bold());
            title.setText(titleText);
            titles.addView(eyebrow);
            titles.addView(title);
            head.addView(titles, wex(1f, ViewGroup.LayoutParams.WRAP_CONTENT));
            addView(head, lp(ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.WRAP_CONTENT));

            body = column(c);
            body.setPadding(dp(c, 10), dp(c, 10), dp(c, 10), dp(c, 10));
            addView(body, fillHeight());
        }

        public void setTitle(String text) {
            title.setText(text);
        }

        public void setEyebrow(String text) {
            eyebrow.setText(text);
        }

        /**
         * Recolours the head and its title. A panel that reports status has to be able to
         * change its mind: an orange head announcing "all clear" reads as a warning.
         */
        public void setAccent(int accentColor) {
            accent = accentColor;
            title.setTextColor(accentColor);
            head.setBackground(roundedTop(getContext(),
                    Palette.mix(palette.panel, accentColor, palette.dark ? 0.26f : 0.16f), 12f));
        }

        public int accent() {
            return accent;
        }
    }

    /**
     * A big number with a caption. The caption sits above and the value below, because
     * the value is the thing being glanced at and should own the strong position.
     */
    public static class Stat extends LinearLayout {

        /** Severity of a value, for colouring it from the palette. */
        public static final int OK = 0, CAUTION = 1, FAULT = 2;

        private final TextView value;
        private final TextView unit;
        private final TextView caption;
        private final int normalColor;
        private final int cautionColor;
        private final int faultColor;

        public Stat(Context c, Palette p, String captionText, String unitText) {
            super(c);
            setOrientation(VERTICAL);
            // Centres the caption and value as a block, so a tile that has been given
            // extra height reads as a card rather than as text stuck to the top.
            setGravity(Gravity.CENTER_VERTICAL);
            setBackground(rounded(c, p.tile, 9f));
            setPadding(dp(c, 9), dp(c, 7), dp(c, 9), dp(c, 7));
            normalColor = p.text;
            cautionColor = p.warn;
            faultColor = p.bad;

            caption = caps(c, TYPE_EYEBROW, p.textDim);
            caption.setText(captionText);

            LinearLayout valueRow = row(c);
            valueRow.setGravity(Gravity.BOTTOM);
            value = tnum(label(c, TYPE_VALUE, p.text));
            value.setTypeface(bold());
            unit = label(c, TYPE_LABEL, p.textDim);
            unit.setText(unitText);
            LinearLayout.LayoutParams up = lp(ViewGroup.LayoutParams.WRAP_CONTENT,
                    ViewGroup.LayoutParams.WRAP_CONTENT);
            up.leftMargin = dp(c, 3);
            up.bottomMargin = dp(c, 4);
            valueRow.addView(value);
            valueRow.addView(unit, up);

            LinearLayout.LayoutParams vp = lp(ViewGroup.LayoutParams.WRAP_CONTENT,
                    ViewGroup.LayoutParams.WRAP_CONTENT);
            vp.topMargin = dp(c, 1);
            addView(caption);
            addView(valueRow, vp);
        }

        public void set(String text) {
            value.setText(text);
        }

        public void set(String text, int color) {
            value.setTextColor(color);
            value.setText(text);
        }

        /**
         * Sets the value and colours it by severity, drawing the colours from the palette.
         * A value coloured with a hardcoded white is legible on the dark theme and
         * invisible on the light one, so severity rather than colour is what callers say.
         */
        public void setLevel(String text, int severity) {
            value.setTextColor(severity == FAULT ? faultColor
                    : severity == CAUTION ? cautionColor : normalColor);
            value.setText(text);
        }

        public void setUnit(String text) {
            unit.setText(text);
        }
    }

    /** A label, a number and a bar. Used for anything with a 0..1 range. */
    public static class Bar extends LinearLayout {

        private final TextView value;
        private final View fill;
        private final View rest;
        private final Context ctx;
        private final int baseColor;

        public Bar(Context c, Palette p, String labelText, int color) {
            super(c);
            ctx = c;
            baseColor = color;
            setOrientation(VERTICAL);

            LinearLayout head = row(c);
            TextView label = label(c, TYPE_LABEL, p.textDim);
            label.setText(labelText);
            value = tnum(label(c, TYPE_LABEL, color));
            value.setTypeface(bold());
            head.addView(label);
            head.addView(gap(c));
            head.addView(value);
            addView(head, lp(ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.WRAP_CONTENT));

            // The fill and the remainder are sibling weights, so setting a value is
            // two LayoutParams writes and never touches the view tree.
            LinearLayout track = row(c);
            track.setBackground(rounded(c, p.track, 99f));
            fill = new View(c);
            fill.setBackground(rounded(c, color, 99f));
            rest = new View(c);
            track.addView(fill, wex(1f, ViewGroup.LayoutParams.MATCH_PARENT));
            track.addView(rest, wex(9f, ViewGroup.LayoutParams.MATCH_PARENT));
            LinearLayout.LayoutParams tp = lp(ViewGroup.LayoutParams.MATCH_PARENT, dp(c, 5));
            tp.topMargin = dp(c, 4);
            addView(track, tp);

            set(0f, "");
        }

        public void set(float fraction, String valueText) {
            set(fraction, valueText, baseColor);
        }

        public void set(float fraction, String valueText, int color) {
            float f = Math.max(0f, Math.min(1f, fraction));
            int weight = Math.max(1, Math.round(f * 100f));
            fill.setBackground(rounded(ctx, color, 99f));
            fill.setLayoutParams(wex(weight, ViewGroup.LayoutParams.MATCH_PARENT));
            rest.setLayoutParams(wex(Math.max(1, 100 - weight),
                    ViewGroup.LayoutParams.MATCH_PARENT));
            value.setTextColor(color);
            value.setText(valueText);
        }
    }

    /** A tap target that reads as on or off. */
    public static class Pill extends TextView {

        private final Palette palette;
        private final int onColor;
        private final Context ctx;
        private boolean on = true;

        public Pill(Context c, Palette p, int color) {
            super(c);
            ctx = c;
            palette = p;
            onColor = color;
            setTextSize(TYPE_EYEBROW);
            setTypeface(bold());
            setLetterSpacing(TRACK_CAPS);
            setPadding(dp(c, 11), dp(c, 10), dp(c, 11), dp(c, 10));
            setClickable(true);
            setFocusable(true);
            render();
        }

        public boolean isOn() {
            return on;
        }

        public void setOn(boolean value) {
            on = value;
            render();
        }

        private void render() {
            setText(isOn() ? "ON" : "OFF");
            setTextColor(on ? onColor : palette.textDim);
            setBackground(rounded(ctx, on ? palette.washOf(onColor) : palette.track, 99f));
        }
    }
}
