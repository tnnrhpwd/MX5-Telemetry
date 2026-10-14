package com.mx5.remote;

import android.content.Context;
import android.content.res.ColorStateList;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.SeekBar;
import android.widget.TextView;

/**
 * A label, a live value and a platform SeekBar.
 *
 * SeekBar progress is always 0 based, so min and step are kept here and mapped in
 * both directions. The value is only posted back when the change came from the
 * user: a value arriving from the Pi must not bounce straight back as a command,
 * or two open clients would fight each other.
 */
public class SliderRow extends LinearLayout {

    public interface OnChange {
        void onChange(int value);
    }

    private final TextView valueText;
    private final SeekBar bar;
    private final int min;
    private final int step;
    private final String unit;
    private final OnChange listener;

    public SliderRow(Context c, Palette p, String label, int min, int max, int step,
                     int initial, String unit, int color, OnChange listener) {
        super(c);
        this.min = min;
        this.step = Math.max(1, step);
        this.unit = unit;
        this.listener = listener;

        setOrientation(VERTICAL);
        // Vertical breathing room, so the row is a comfortable target on a car screen
        // rather than a 30px band.
        setPadding(0, Ui.dp(c, 4), 0, Ui.dp(c, 4));

        LinearLayout head = Ui.row(c);
        TextView name = Ui.label(c, 11f, p.text);
        name.setText(label);
        valueText = Ui.label(c, 11f, color);
        valueText.setTypeface(Ui.bold());
        head.addView(name);
        head.addView(Ui.gap(c));
        head.addView(valueText);
        addView(head, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        bar = new SeekBar(c);
        bar.setMax(Math.max(1, (max - min) / this.step));
        bar.setProgressTintList(ColorStateList.valueOf(color));
        bar.setThumbTintList(ColorStateList.valueOf(color));
        LinearLayout.LayoutParams bp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        bp.topMargin = Ui.dp(c, 3);
        addView(bar, bp);

        // Seed the thumb before the listener is attached, so setting the initial
        // value cannot look like a user edit and bounce straight back to the Pi.
        bar.setProgress(Math.max(0, Math.round((initial - min) / (float) this.step)));
        render(current());

        bar.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override
            public void onProgressChanged(SeekBar seekBar, int progress, boolean fromUser) {
                render(current());
                if (fromUser && SliderRow.this.listener != null) {
                    SliderRow.this.listener.onChange(current());
                }
            }

            @Override
            public void onStartTrackingTouch(SeekBar seekBar) {
            }

            @Override
            public void onStopTrackingTouch(SeekBar seekBar) {
            }
        });
    }

    private int current() {
        return min + bar.getProgress() * step;
    }

    private void render(int value) {
        valueText.setText(value + unit);
    }

    /** Apply a value that came from the Pi. Never fires the change callback. */
    public void setValue(int value) {
        int clamped = Math.max(min, value);
        int progress = Math.round((clamped - min) / (float) step);
        bar.setProgress(progress);
        render(current());
    }
}
