package com.mx5.remote;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Typeface;
import android.util.AttributeSet;
import android.view.View;

/**
 * G-force scatter, with a decaying trail.
 *
 * The round display's version tracks orientation too, because it has a gyro and
 * integrates it. Here the Pi only publishes g_lateral and g_longitudinal, so this is
 * the accelerometer scatter: position is the instantaneous g vector, and how hard the
 * car is being pushed is the colour.
 *
 * The trail is what makes it useful rather than just pretty. A single dot at 4 Hz tells
 * you almost nothing about a corner; the last two seconds of it show the shape of the
 * turn. Older points fade and shrink, so the newest reads clearly.
 *
 * Dot position is clamped to the outer ring, because at 1.2g on a bumpy road a clamped
 * dot is far more useful than one that has left the dial.
 */
public class GForceView extends View {

    private static final float RANGE_G = 1.2f;
    private static final int TRAIL = 24;

    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint stroke = new Paint(Paint.ANTI_ALIAS_FLAG);

    private final float[] histLat = new float[TRAIL];
    private final float[] histLong = new float[TRAIL];
    private int histHead;
    private int histCount;

    private float lateral;
    private float longitudinal;

    private int dimColor = 0xFF9BA1AB;
    private int trackColor = 0xFF3A3A40;
    private int accentColor = 0xFF00FFFF;

    public GForceView(Context c) {
        super(c);
        init();
    }

    public GForceView(Context c, AttributeSet a) {
        super(c, a);
        init();
    }

    private void init() {
        stroke.setStyle(Paint.Style.STROKE);
        paint.setTextAlign(Paint.Align.CENTER);
    }

    /** Surface colour for the pad behind the rings. Zero leaves the pad off. */
    private int tileColor = 0;

    public void setColors(int text, int dim, int track, int accent) {
        setColors(text, dim, track, accent, 0);
    }

    /**
     * @param tile a surface colour for the pad behind the rings. Without a pad the dial is
     *             thin circles adrift in a large empty square, which reads as an unfinished
     *             panel rather than as an instrument.
     */
    public void setColors(int text, int dim, int track, int accent, int tile) {
        this.dimColor = dim;
        this.trackColor = track;
        this.accentColor = accent;
        this.tileColor = tile;
        invalidate();
    }

    public void setValue(float lateral, float longitudinal) {
        this.lateral = lateral;
        this.longitudinal = longitudinal;
        histLat[histHead] = lateral;
        histLong[histHead] = longitudinal;
        histHead = (histHead + 1) % TRAIL;
        if (histCount < TRAIL) {
            histCount++;
        }
        invalidate();
    }

    /** Drops the trail, for when the car has been stationary and it would be stale. */
    public void clearTrail() {
        histCount = 0;
        histHead = 0;
        invalidate();
    }

    private float magnitude() {
        return (float) Math.sqrt(lateral * lateral + longitudinal * longitudinal);
    }

    private static int colorFor(float m) {
        if (m >= 0.75f) {
            return 0xFFEF4444;
        }
        if (m >= 0.5f) {
            return 0xFFF97316;
        }
        if (m >= 0.25f) {
            return 0xFFEAB308;
        }
        return 0xFF22C55E;
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);

        float w = getWidth();
        float h = getHeight();
        float size = Math.min(w, h);
        float cx = w / 2f;
        float cy = h / 2f;
        float outer = size * 0.38f;
        float scale = outer / RANGE_G;

        // The pad, before anything else, so the rings and the trail sit on a surface.
        if (tileColor != 0) {
            paint.setStyle(Paint.Style.FILL);
            paint.setColor(tileColor);
            canvas.drawCircle(cx, cy, outer, paint);
        }

        // Inner rings at 0.4 and 0.8, so the spacing reads as g values.
        stroke.setStrokeWidth(Math.max(1.5f, size * 0.008f));
        stroke.setColor(trackColor);
        float[] rings = {0.4f, 0.8f};
        for (float r : rings) {
            canvas.drawCircle(cx, cy, r * scale, stroke);
        }

        // The outer ring is the edge of the pad, so it is drawn heavier and brighter.
        // That edge is what makes the pad read as a surface rather than as a haze.
        stroke.setStrokeWidth(Math.max(2f, size * 0.011f));
        stroke.setColor(Palette.alpha(trackColor, 0.95f));
        canvas.drawCircle(cx, cy, outer, stroke);

        // Crosshair, lighter than the rings so the axes read as guides.
        stroke.setColor(Palette.alpha(trackColor, 0.65f));
        canvas.drawLine(cx - outer, cy, cx + outer, cy, stroke);
        canvas.drawLine(cx, cy - outer, cx, cy + outer, stroke);

        // Axis labels. Forward is up, matching the round display's convention.
        paint.setColor(dimColor);
        paint.setTextSize(size * 0.055f);
        paint.setTypeface(Typeface.create(Typeface.DEFAULT, Typeface.NORMAL));
        canvas.drawText("accel", cx, cy - outer - size * 0.035f, paint);
        canvas.drawText("brake", cx, cy + outer + size * 0.095f, paint);
        paint.setTextAlign(Paint.Align.LEFT);
        canvas.drawText("L", cx - outer - size * 0.075f, cy + size * 0.02f, paint);
        paint.setTextAlign(Paint.Align.RIGHT);
        canvas.drawText("R", cx + outer + size * 0.075f, cy + size * 0.02f, paint);
        paint.setTextAlign(Paint.Align.CENTER);

        // Trail, oldest first, so the newest dot is drawn last and on top.
        for (int i = 0; i < histCount; i++) {
            int index = (histHead - histCount + i + TRAIL * 2) % TRAIL;
            float age = (i + 1) / (float) histCount;
            int color = colorFor((float) Math.hypot(histLat[index], histLong[index]));
            paint.setColor(Palette.alpha(color, 0.06f + 0.30f * age));
            canvas.drawCircle(cx + histLat[index] * scale, cy - histLong[index] * scale,
                    size * 0.012f + size * 0.020f * age, paint);
        }

        // Current position, clamped to the ring.
        float dx = lateral * scale;
        float dy = -longitudinal * scale;
        float off = (float) Math.hypot(dx, dy);
        if (off > outer) {
            dx = dx / off * outer;
            dy = dy / off * outer;
        }
        float px = cx + dx;
        float py = cy + dy;

        int color = colorFor(magnitude());
        float dot = size * 0.045f + size * 0.030f * Math.min(1f, magnitude());

        paint.setColor(Palette.alpha(color, 0.20f));
        canvas.drawCircle(px, py, dot * 2.0f, paint);
        paint.setColor(color);
        canvas.drawCircle(px, py, dot, paint);

        // Current magnitude, in the corner the dial never reaches.
        paint.setColor(color);
        paint.setTextSize(size * 0.10f);
        paint.setTypeface(Typeface.create(Typeface.DEFAULT, Typeface.BOLD));
        paint.setTextAlign(Paint.Align.LEFT);
        paint.setFontFeatureSettings("tnum");
        canvas.drawText(String.format("%.2f g", magnitude()), size * 0.03f, size * 0.13f, paint);

        paint.setColor(dimColor);
        paint.setTextSize(size * 0.055f);
        paint.setTypeface(Typeface.create(Typeface.DEFAULT, Typeface.NORMAL));
        canvas.drawText(String.format("lat %+.2f", lateral), size * 0.03f, size * 0.21f, paint);
        canvas.drawText(String.format("long %+.2f", longitudinal), size * 0.03f, size * 0.28f, paint);
        paint.setTextAlign(Paint.Align.CENTER);
    }
}
