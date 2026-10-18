package com.mx5.remote;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.util.AttributeSet;
import android.view.View;

/**
 * Gear ladder: what the engine would turn in each gear at the current road speed.
 *
 * The current gear tells you where you are; this tells you where the other five would
 * put you. At 40mph 4th sits at 2270 and 5th at 1910, so the ladder says "you are in the
 * wrong gear before you can hear it". That is the whole point of the widget.
 *
 * Why a custom View rather than twelve TextViews in two rows of LinearLayouts:
 *
 *   - **One layout pass, one draw pass.** A TextView pair per gear is twelve measures
 *     and twelve draw calls per frame for six numbers.
 *   - **No allocation, ever.** The paints, the font metrics, the rect and the digit
 *     buffers are all fields, and digits are drawn straight from char[] via
 *     Canvas.drawText(char[], ...). Not one object is created in onDraw, in setValue or
 *     in the maths.
 *   - **The maths runs once per change, not per frame.** RPM ratio as a function of road
 *     speed is a straight line through the origin, so the per-gear slope is a constant
 *     and the whole bar is six multiplies. Those slopes are computed in a static
 *     initialiser, so even the first bind does no trigonometry.
 *   - **Steady state costs nothing at all.** bind() runs four times a second; at a
 *     constant speed, or stopped, setValue() returns before it touches anything, and a
 *     speed that drifts without changing a single rounded RPM does not invalidate.
 *
 * The driveline constants are the ones GearEstimator uses on the Pi, so the ladder and
 * the gear the Pi reports agree with each other.
 */
public class GearRpmView extends View {

    private static final int GEARS = 6;

    /** MX5 NC 6-speed (2006-2015). Index 0 is unused so gear numbers index directly. */
    private static final float[] RATIO =
            {0f, 3.760f, 2.269f, 1.645f, 1.187f, 1.000f, 0.843f};
    private static final float FINAL_DRIVE = 4.10f;
    /** 205/45R17. */
    private static final float TYRE_DIAMETER_IN = 24.3f;
    private static final float INCHES_PER_MILE = 63360f;
    private static final float KM_PER_MILE = 1.609344f;

    /**
     * Engine RPM per unit of road speed, per gear, for the life of the process.
     *
     * rpm = ratio * final_drive * 63360 * speed / (circumference * 60)
     *     = ratio * speed * slope, where slope is constant per unit system and gear.
     * Both unit systems are precomputed so switching MPH/KMH costs an array swap.
     */
    private static final float[] RPM_PER_MPH = new float[GEARS + 1];
    private static final float[] RPM_PER_KMH = new float[GEARS + 1];

    static {
        float circumference = (float) Math.PI * TYRE_DIAMETER_IN;
        float base = (FINAL_DRIVE * INCHES_PER_MILE) / (circumference * 60f);
        for (int g = 1; g <= GEARS; g++) {
            RPM_PER_MPH[g] = RATIO[g] * base;
            RPM_PER_KMH[g] = RPM_PER_MPH[g] / KM_PER_MILE;
        }
    }

    /** Above this a downshift would over-rev. */
    private static final int OVER_REV = 7000;
    /** The band worth being in when you are choosing a gear. */
    private static final int SWEET_LOW = 2400;
    private static final int SWEET_HIGH = 4500;
    /** Below this the engine would labour. */
    private static final int LUG_BELOW = 1200;

    private final Paint capsule = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint gearPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint rpmPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint.FontMetrics metrics = new Paint.FontMetrics();
    private final RectF box = new RectF();

    private final int[] rpm = new int[GEARS + 1];
    /**
     * RPM labels live as raw chars, drawn with Canvas.drawText(char[], ...).
     * String.format or Integer.toString here would allocate on every speed change, and
     * String.valueOf(g) would allocate six times per frame just to draw "1".."6".
     */
    private final char[][] label = new char[GEARS + 1][8];
    private final int[] labelLen = new int[GEARS + 1];
    private static final char[] GEAR_DIGIT =
            {'\u2013', '1', '2', '3', '4', '5', '6'};

    private boolean mph = true;
    private float lastSpeed = -1f;
    private int currentGear;
    private boolean usable;
    private boolean stale = true;

    private int textColor = 0xFFF4F7FD;
    private int dimColor = 0xFF9BA1AB;
    private int surfaceColor = 0xFF2A2A2E;
    private int accentColor = 0xFF00C1C1;
    private int accentWashColor = 0x3300C1C1;
    private int goodColor = 0xFF22C55E;
    private int badColor = 0xFFEF4444;

    public GearRpmView(Context c) {
        super(c);
        init();
    }

    public GearRpmView(Context c, AttributeSet a) {
        super(c, a);
        init();
    }

    private void init() {
        gearPaint.setTextAlign(Paint.Align.CENTER);
        gearPaint.setTypeface(Typeface.create(Typeface.DEFAULT, Typeface.BOLD));
        rpmPaint.setTextAlign(Paint.Align.CENTER);
        rpmPaint.setTypeface(Typeface.create(Typeface.DEFAULT, Typeface.BOLD));
        // Tabular figures: without them the ladder shivers as digits change width.
        rpmPaint.setFontFeatureSettings("tnum");
        for (int g = 0; g <= GEARS; g++) {
            rpm[g] = -1;
            labelLen[g] = 0;
        }
    }

    /** Colours are resolved by the caller, so this view knows nothing about themes. */
    public void setColors(int text, int dim, int surface, int accent, int accentWash,
                          int good, int bad) {
        textColor = text;
        dimColor = dim;
        surfaceColor = surface;
        accentColor = accent;
        accentWashColor = accentWash;
        goodColor = good;
        badColor = bad;
        stale = true;
        invalidate();
    }

    /**
     * @param roadSpeed current speed already expressed in the caller's unit system
     * @param useMph    which precomputed slope table to read
     * @param gear      the gear actually engaged, or anything outside 1..6 for "none"
     * @param reverse   reverse makes the whole ladder meaningless
     */
    public void setValue(float roadSpeed, boolean useMph, int gear, boolean reverse) {
        boolean nowUsable = !reverse && roadSpeed >= 0.5f;
        int g = (gear >= 1 && gear <= GEARS) ? gear : 0;

        // Hot path. At a steady speed there is not one pixel to change, and this is most
        // of the time: four binds a second against a speed that moves every few seconds.
        if (!stale && roadSpeed == lastSpeed && useMph == mph
                && g == currentGear && nowUsable == usable) {
            return;
        }

        // A speed that drifts by a fraction of a unit usually leaves every rounded RPM
        // identical. Recomputing is free; invalidating is not, so track whether any
        // pixel would actually differ before asking for a redraw.
        boolean visualChange = stale || g != currentGear || useMph != mph || nowUsable != usable;

        stale = false;
        lastSpeed = roadSpeed;
        mph = useMph;
        currentGear = g;
        usable = nowUsable;

        if (!nowUsable) {
            for (int i = 1; i <= GEARS; i++) {
                // Not `rpm[i] != -1`: rpm starts at -1, so that test would skip the very
                // first paint and leave the capsules blank instead of showing a dash.
                if (rpm[i] != -1 || labelLen[i] != 1) {
                    rpm[i] = -1;
                    label[i][0] = '\u2013';
                    labelLen[i] = 1;
                    visualChange = true;
                }
            }
        } else {
            float[] slope = useMph ? RPM_PER_MPH : RPM_PER_KMH;
            for (int i = 1; i <= GEARS; i++) {
                int v = Math.round(roadSpeed * slope[i]);
                if (v != rpm[i]) {
                    rpm[i] = v;
                    labelLen[i] = formatInto(v, label[i]);
                    visualChange = true;
                }
            }
        }

        if (visualChange) {
            invalidate();
        }
    }

    /**
     * Writes an RPM value as digits into {@code out} and returns the length.
     * Nothing but digits and a '.' or 'k' is emitted, and nothing is allocated.
     */
    private int formatInto(int v, char[] out) {
        if (v < 0) {
            out[0] = '\u2013';
            return 1;
        }
        int n = 0;
        if (v >= 10000) {
            int thousands = v / 1000;
            out[n++] = (char) ('0' + thousands / 10);
            out[n++] = (char) ('0' + thousands % 10);
            out[n++] = '.';
            out[n++] = (char) ('0' + (v % 1000) / 100);
            out[n++] = 'k';
        } else {
            if (v >= 1000) out[n++] = (char) ('0' + v / 1000);
            if (v >= 100) out[n++] = (char) ('0' + (v / 100) % 10);
            if (v >= 10) out[n++] = (char) ('0' + (v / 10) % 10);
            out[n++] = (char) ('0' + v % 10);
        }
        return n;
    }

    @Override
    protected void onMeasure(int widthSpec, int heightSpec) {
        // Two stacked lines plus padding. Natural height, because the parent stacks this
        // under a fixed set of tiles and a weighted height would starve them.
        int h = Ui.dp(getContext(), 44);
        setMeasuredDimension(MeasureSpec.getSize(widthSpec), resolveSize(h, heightSpec));
    }

    @Override
    protected void onDraw(Canvas canvas) {
        final int w = getWidth();
        final int h = getHeight();
        if (w <= 0 || h <= 0) {
            return;
        }

        final float colW = (float) w / GEARS;
        final float padX = colW * 0.07f;
        final float padY = h * 0.05f;
        final float radius = Math.min(colW, h) * 0.18f;
        final float innerTop = padY;
        final float innerH = h - 2f * padY;
        final float gearY = innerTop + innerH * 0.30f;
        final float rpmY = innerTop + innerH * 0.74f;

        gearPaint.setTextSize(h * 0.30f);
        rpmPaint.setTextSize(h * 0.27f);

        for (int g = 1; g <= GEARS; g++) {
            final boolean current = (g == currentGear);
            final float left = (g - 1) * colW + padX;
            final float right = g * colW - padX;

            capsule.setColor(current ? accentWashColor : surfaceColor);
            box.set(left, padY, right, h - padY);
            canvas.drawRoundRect(box, radius, radius, capsule);

            // Gear numbers are quiet; the RPM is the reading. An engaged gear lifts the
            // whole capsule instead, so it does not have to shout over the others.
            gearPaint.setColor(current ? accentColor : dimColor);
            drawCentred(canvas, GEAR_DIGIT, g, 1, (left + right) * 0.5f, gearY, gearPaint);

            rpmPaint.setColor(current ? accentColor : rpmColorFor(rpm[g]));
            drawCentred(canvas, label[g], 0, labelLen[g], (left + right) * 0.5f, rpmY, rpmPaint);
        }
    }

    private int rpmColorFor(int v) {
        if (v < 0) {
            return dimColor;
        }
        if (v > OVER_REV) {
            return badColor;
        }
        if (v >= SWEET_LOW && v <= SWEET_HIGH) {
            return goodColor;
        }
        if (v < LUG_BELOW) {
            return dimColor;
        }
        return textColor;
    }

    /** Vertically centred on the given line centre, using a reused FontMetrics. */
    private void drawCentred(Canvas canvas, char[] text, int index, int count,
                             float cx, float cy, Paint paint) {
        if (count <= 0) {
            return;
        }
        paint.getFontMetrics(metrics);
        float baseline = cy - (metrics.ascent + metrics.descent) * 0.5f;
        canvas.drawText(text, index, count, cx, baseline, paint);
    }
}
