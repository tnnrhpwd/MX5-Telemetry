package com.mx5.remote;

import android.content.Context;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.List;

/** A row of mutually exclusive chips, each carrying its own value. */
public class Chips extends LinearLayout {

    public interface OnPick {
        void onPick(int value);
    }

    private final List<TextView> buttons = new ArrayList<>();
    private final int[] values;
    private final Context ctx;
    private final Palette palette;
    private final int color;

    public Chips(Context c, Palette p, String[] names, int[] values, int color, OnPick onPick) {
        super(c);
        this.ctx = c;
        this.palette = p;
        this.values = values;
        this.color = color;
        setOrientation(Screen.isNarrow(c) ? VERTICAL : HORIZONTAL);

        // Four chips across half of a phone is about 45dp each, which breaks "Center out"
        // and "C for clutch" across three lines mid-word. Two per row instead.
        int perRow = Screen.isNarrow(c) ? 2 : names.length;
        LinearLayout row = null;

        for (int i = 0; i < names.length; i++) {
            if (perRow > 0 && i % perRow == 0) {
                row = Ui.row(c);
                addView(row, new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT));
            }
            final int value = values[i];
            TextView b = Ui.label(c, 10f, p.text);
            b.setText(names[i]);
            b.setGravity(Gravity.CENTER);
            b.setPadding(Ui.dp(c, 6), Ui.dp(c, 12), Ui.dp(c, 6), Ui.dp(c, 12));
            b.setClickable(true);
            b.setFocusable(true);
            b.setBackground(Ui.rounded(c, 0x00000000, 8f));
            b.setOnClickListener(v -> {
                select(value);
                onPick.onPick(value);
            });
            row.addView(b, Ui.cell(c, 2));
            buttons.add(b);
        }
    }

    /** Highlight the chip carrying this value, clearing the rest. */
    public void select(int value) {
        for (int i = 0; i < buttons.size(); i++) {
            boolean on = values[i] == value;
            TextView b = buttons.get(i);
            b.setTextColor(on ? color : palette.text);
            b.setBackground(Ui.rounded(ctx, on ? Palette.alpha(color, 0.24f) : 0x00000000, 8f));
        }
    }
}
