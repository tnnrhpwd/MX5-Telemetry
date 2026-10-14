package com.mx5.remote;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RectF;
import android.view.View;

/**
 * A battery gauge, drawn rather than borrowed from a glyph.
 *
 * The head unit's font is not ours to choose, and a missing battery character is worse than
 * no readout at all: it reads as a fault rather than an absence. Geometry cannot go missing,
 * and drawing it lets the fill carry the level as well as the number does.
 */
public class BatteryIcon extends View {

    /** Before the platform has reported anything. */
    public static final int UNKNOWN = -1;

    /** Below this the fill turns red, so the level is alarming before the number is read. */
    private static final int LOW_PERCENT = 15;

    private int level = UNKNOWN;
    private boolean charging;

    private int trackColor = 0xFF3A3A40;
    private int fillColor = 0xFFEDEDF0;
    private int lowColor = 0xFFEF4444;
    private int chargeColor = 0xFF22C55E;

    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF body = new RectF();
    private final RectF inner = new RectF();
    private final RectF fill = new RectF();
    private final RectF nub = new RectF();
    private final Path bolt = new Path();

    public BatteryIcon(Context c) {
        super(c);
    }

    /** Colours come from the palette, so the gauge follows the scheme and the theme. */
    public void setColors(int track, int fill, int low, int charge) {
        this.trackColor = track;
        this.fillColor = fill;
        this.lowColor = low;
        this.chargeColor = charge;
        invalidate();
    }

    /** level is 0 to 100, or {@link #UNKNOWN} until the first battery broadcast arrives. */
    public void setLevel(int level, boolean charging) {
        if (this.level == level && this.charging == charging) {
            return;
        }
        this.level = level;
        this.charging = charging;
        invalidate();
    }

    @Override
    protected void onMeasure(int widthSpec, int heightSpec) {
        // Fixed, because this sits inside a row of text and must never nudge it. Sized for a
        // glance from the driver's seat rather than for a status bar: at 34x15 the charging
        // bolt has no room to be a bolt and reads as a smudge in the fill.
        setMeasuredDimension(Ui.dp(getContext(), 40), Ui.dp(getContext(), 18));
    }

    @Override
    protected void onDraw(Canvas canvas) {
        Context c = getContext();
        float w = getWidth();
        float h = getHeight();
        float stroke = Math.max(1f, Ui.dp(c, 1.2f));
        float nubW = Ui.dp(c, 3);
        float radius = Ui.dp(c, 3.5f);

        int ink = level < 0 ? trackColor : inkColor();

        body.set(stroke / 2f, stroke / 2f, w - nubW - stroke / 2f, h - stroke / 2f);

        paint.setStyle(Paint.Style.STROKE);
        paint.setStrokeWidth(stroke);
        paint.setColor(ink);
        canvas.drawRoundRect(body, radius, radius, paint);

        // Without the terminal the shape reads as a rounded box rather than a battery.
        float nubH = h * 0.44f;
        nub.set(body.right + stroke, (h - nubH) / 2f, w, (h + nubH) / 2f);
        paint.setStyle(Paint.Style.FILL);
        canvas.drawRoundRect(nub, Ui.dp(c, 1), Ui.dp(c, 1), paint);

        if (level < 0) {
            return;
        }

        float pad = stroke + Ui.dp(c, 1.5f);
        inner.set(body.left + pad, body.top + pad, body.right - pad, body.bottom - pad);
        if (inner.width() <= 0 || inner.height() <= 0) {
            return;
        }

        int pct = Math.max(0, Math.min(100, level));
        float filled = inner.width() * pct / 100f;
        if (filled > 0.5f) {
            fill.set(inner.left, inner.top, inner.left + filled, inner.bottom);
            paint.setColor(ink);
            canvas.drawRoundRect(fill, Ui.dp(c, 1.5f), Ui.dp(c, 1.5f), paint);
        }

        if (charging) {
            // Punched out of the fill in the chip's own colour, and the box is close to square
            // because the bolt's arms are only ~12% of its width: a wide box flattens it into
            // a wedge. Two light inks laid over each other at this size would be a smudge, so
            // the knockout is the legible option; the fallback ink covers a fill too short to
            // reach the bolt, where a knockout would have nothing to knock out of.
            paint.setColor(filled > 0.45f
                    ? trackColor
                    : fillColor);
            drawBolt(canvas, new RectF(body.left + Ui.dp(c, 10), body.top + Ui.dp(c, 2.5f),
                    body.right - Ui.dp(c, 10), body.bottom - Ui.dp(c, 2.5f)));
        }
    }

    private int inkColor() {
        if (charging) {
            return chargeColor;
        }
        return level <= LOW_PERCENT ? lowColor : fillColor;
    }

    /** The classic seven-point bolt, normalised so it scales with the icon. */
    private void drawBolt(Canvas canvas, RectF box) {
        float x = box.left;
        float y = box.top;
        float w = box.width();
        float h = box.height();
        float[] px = {0.591f, 0.136f, 0.477f, 0.409f, 0.864f, 0.523f};
        float[] py = {0.083f, 0.583f, 0.583f, 0.917f, 0.417f, 0.417f};
        bolt.reset();
        bolt.moveTo(x + px[0] * w, y + py[0] * h);
        for (int i = 1; i < px.length; i++) {
            bolt.lineTo(x + px[i] * w, y + py[i] * h);
        }
        bolt.close();
        canvas.drawPath(bolt, paint);
    }
}
