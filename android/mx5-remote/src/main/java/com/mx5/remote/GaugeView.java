package com.mx5.remote;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.util.AttributeSet;
import android.view.View;

/**
 * RPM gauge.
 *
 * The zone thresholds are the ones the round display uses: idle below 2000, eco to
 * 3000, normal to 4500, spirited to 5500, then red. The dial is a 270 degree arc
 * starting bottom left, and the scale runs to just past the redline so the red zone is
 * never clipped at the end of the sweep.
 *
 * Three things make it read as an instrument rather than a ring: graduated tick marks
 * inside the arc, a needle, and the readout dropped into the open bottom of the dial
 * so it never collides with the hub.
 */
public class GaugeView extends View {

    private static final float START_ANGLE = 135f;
    private static final float SWEEP_ANGLE = 270f;

    private static final int C_IDLE = 0xFF3B82F6;
    private static final int C_ECO = 0xFF22C55E;
    private static final int C_NORMAL = 0xFFEAB308;
    private static final int C_SPIRITED = 0xFFF97316;
    private static final int C_HIGH = 0xFFEF4444;

    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint stroke = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF box = new RectF();

    private float rpm;
    private float shiftRpm = 6500f;
    private float redlineRpm = 7200f;
    private float scaleMax = 8000f;

    private int textColor = 0xFFF4F7FD;
    private int dimColor = 0xFF9BA1AB;
    private int trackColor = 0xFF3A3A40;
    private int accentColor = 0xFF00FFFF;

    public GaugeView(Context c) {
        super(c);
        init();
    }

    public GaugeView(Context c, AttributeSet a) {
        super(c, a);
        init();
    }

    private void init() {
        stroke.setStyle(Paint.Style.STROKE);
        stroke.setStrokeCap(Paint.Cap.BUTT);
        paint.setTextAlign(Paint.Align.CENTER);
        paint.setTypeface(Typeface.create(Typeface.DEFAULT, Typeface.BOLD));
        // Tabular figures keep the big readout from shifting width as the digits change.
        paint.setFontFeatureSettings("tnum");
    }

    public void setColors(int text, int dim, int track, int accent) {
        this.textColor = text;
        this.dimColor = dim;
        this.trackColor = track;
        this.accentColor = accent;
        invalidate();
    }

    /** Kept for API compatibility with the screens; the gauge now draws its own labels. */
    public void setCaption(String caption, String unit) {
        invalidate();
    }

    public void setValue(float rpm, float shift, float redline) {
        this.rpm = Math.max(0f, rpm);
        this.shiftRpm = Math.max(1f, shift);
        this.redlineRpm = Math.max(shift + 1f, redline);
        this.scaleMax = Math.max(8000f, redlineRpm + 600f);
        invalidate();
    }

    /** The band colour for a given rpm, which the readout and needle also use. */
    public int zoneColor(float value) {
        if (value >= 5500) {
            return C_HIGH;
        }
        if (value >= 4500) {
            return C_SPIRITED;
        }
        if (value >= 3000) {
            return C_NORMAL;
        }
        if (value >= 2000) {
            return C_ECO;
        }
        return C_IDLE;
    }

    private float angleFor(float value) {
        return START_ANGLE + SWEEP_ANGLE * (Math.min(value, scaleMax) / scaleMax);
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);

        float w = getWidth();
        float h = getHeight();
        float size = Math.min(w, h);
        float thickness = size * 0.085f;
        float radius = (size - thickness) / 2f - size * 0.03f;
        float cx = w / 2f;
        float cy = h / 2f;

        box.set(cx - radius, cy - radius, cx + radius, cy + radius);

        // Unfilled dial
        stroke.setStrokeWidth(thickness);
        stroke.setColor(trackColor);
        canvas.drawArc(box, START_ANGLE, SWEEP_ANGLE, false, stroke);

        // Graduations, drawn just inside the ring. Major every 1000, minor every 500.
        float tickOuter = radius - thickness / 2f - size * 0.022f;
        int steps = Math.round(scaleMax / 500f);
        for (int i = 0; i <= steps; i++) {
            float value = i * 500f;
            boolean major = i % 2 == 0;
            float length = major ? size * 0.042f : size * 0.022f;
            stroke.setStrokeWidth(major ? Math.max(1.5f, size * 0.0075f)
                    : Math.max(1f, size * 0.0045f));
            stroke.setColor(Palette.alpha(dimColor, major ? 0.8f : 0.4f));
            double rad = Math.toRadians(angleFor(value));
            float cos = (float) Math.cos(rad);
            float sin = (float) Math.sin(rad);
            canvas.drawLine(cx + cos * tickOuter, cy + sin * tickOuter,
                    cx + cos * (tickOuter - length), cy + sin * (tickOuter - length), stroke);
        }

        // The filled portion, in segments so the colour changes at each zone boundary.
        stroke.setStrokeWidth(thickness);
        float[] bounds = {0f, 2000f, 3000f, 4500f, 5500f, scaleMax};
        int[] colors = {C_IDLE, C_ECO, C_NORMAL, C_SPIRITED, C_HIGH};
        for (int i = 0; i < colors.length; i++) {
            float from = Math.max(bounds[i], 0f);
            float to = Math.min(bounds[i + 1], Math.min(rpm, scaleMax));
            if (to <= from) {
                continue;
            }
            stroke.setColor(colors[i]);
            canvas.drawArc(box, angleFor(from), angleFor(to) - angleFor(from), false, stroke);
        }

        // Redline, so the limit is readable even with the dial empty.
        stroke.setColor(C_HIGH);
        stroke.setStrokeWidth(Math.max(2f, thickness * 0.24f));
        canvas.drawArc(box, angleFor(redlineRpm), 1.5f, false, stroke);

        // Needle. Stopped short of the graduations so it never covers them, and trimmed
        // further than the dial's inner edge so it stays clear of the readout below.
        int zone = zoneColor(rpm);
        double needleAngle = Math.toRadians(angleFor(rpm));
        float needleLen = tickOuter - size * 0.075f;
        stroke.setStrokeCap(Paint.Cap.ROUND);
        stroke.setStrokeWidth(size * 0.02f);
        stroke.setColor(zone);
        canvas.drawLine(cx, cy, cx + (float) Math.cos(needleAngle) * needleLen,
                cy + (float) Math.sin(needleAngle) * needleLen, stroke);
        stroke.setStrokeCap(Paint.Cap.BUTT);

        // Hub, with the zone colour showing through its collar.
        paint.setColor(Palette.alpha(zone, 0.35f));
        canvas.drawCircle(cx, cy, size * 0.05f, paint);
        paint.setColor(zone);
        canvas.drawCircle(cx, cy, size * 0.028f, paint);

        // Labels above the hub, clear of the needle.
        paint.setColor(dimColor);
        paint.setTextSize(size * 0.062f);
        paint.setLetterSpacing(0.12f);
        canvas.drawText("RPM", cx, cy - size * 0.105f, paint);
        paint.setLetterSpacing(0f);

        // Readout, dropped into the open bottom of the dial, below the needle's reach.
        paint.setColor(zone);
        paint.setTextSize(size * 0.22f);
        canvas.drawText(String.valueOf(Math.round(rpm)), cx, cy + size * 0.315f, paint);

        paint.setColor(dimColor);
        paint.setTextSize(size * 0.05f);
        canvas.drawText("shift " + Math.round(shiftRpm) + "  redline " + Math.round(redlineRpm),
                cx, cy + size * 0.44f, paint);

        // Status flag, above the dial where the ring leaves a gap.
        if (rpm >= redlineRpm) {
            paint.setColor(C_HIGH);
            paint.setTextSize(size * 0.072f);
            canvas.drawText("REDLINE", cx, cy - radius - size * 0.045f, paint);
        } else if (rpm >= shiftRpm) {
            paint.setColor(accentColor);
            paint.setTextSize(size * 0.072f);
            canvas.drawText("SHIFT", cx, cy - radius - size * 0.045f, paint);
        }
    }
}
