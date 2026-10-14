package com.mx5.remote;

import android.content.Context;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONObject;

/**
 * Link state, the Pi's own screen control, and the connection settings.
 *
 * This is the one screen that works with no connection at all, which is why the
 * address fields live here: if the Pi address is wrong or blank, every other
 * screen is empty and there has to be somewhere to fix that.
 */
public class SystemScreen extends Screen {

    private Host host;
    private Palette palette;
    private Ui.Panel panel;
    private Ui.Stat piState, canState, tpmsState, piScreen, demoState, heapState;
    private EditText addressField, tokenField;
    private TextView piScreenName;
    private TextView transportList;

    @Override
    public String title() {
        return "System";
    }

    @Override
    public String eyebrow() {
        return "Link";
    }

    @Override
    public int piScreen() {
        return 6;
    }

    /** Re-read the transport chain. Called whenever the link state changes. */
    public void refreshTransport() {
        if (transportList == null || host == null) {
            return;
        }
        StringBuilder sb = new StringBuilder();
        for (String line : host.pi().transportReport()) {
            if (sb.length() > 0) {
                sb.append('\n');
            }
            sb.append(line);
        }
        transportList.setText(sb.toString());
    }

    @Override
    public View build(Context c, Palette p, Host h) {
        host = h;
        palette = p;
        panel = new Ui.Panel(c, p, "LINK", "System", p.accent);

        // PI LINK, PI SCREEN and DEMO MODE are only ever filled by the status poll, which
        // needs a live link. Without a seed they render as empty boxes until the first
        // successful connect, which reads as a broken screen rather than a missing link.
        piState = new Ui.Stat(c, p, "PI LINK", "");
        piState.set("SET UP", p.warn);
        canState = new Ui.Stat(c, p, "CAN BUS", "");
        tpmsState = new Ui.Stat(c, p, "TPMS", "");
        panel.body.addView(grid(c, piState, canState, tpmsState));

        piScreen = new Ui.Stat(c, p, "PI SCREEN", "");
        piScreen.set("waiting");
        demoState = new Ui.Stat(c, p, "DEMO MODE", "");
        demoState.set("OFF", p.textDim);
        heapState = new Ui.Stat(c, p, "MEMORY", "MB");
        // Local to the phone, so it is known immediately.
        Runtime rt = Runtime.getRuntime();
        heapState.set(String.valueOf((rt.totalMemory() - rt.freeMemory()) / (1024 * 1024)));
        panel.body.addView(grid(c, piScreen, demoState, heapState));

        // -- Pi display control ---------------------------------------------
        panel.body.addView(section(c, p, "PI DISPLAY"));

        LinearLayout controls = Ui.row(c);
        TextView prev = button(c, p, "\u2191", p.accent);
        prev.setOnClickListener(v -> host.stepPiScreen(false));
        TextView next = button(c, p, "\u2193", p.accent);
        next.setOnClickListener(v -> host.stepPiScreen(true));
        piScreenName = Ui.label(c, 11f, p.textDim);
        piScreenName.setGravity(Gravity.CENTER);
        piScreenName.setText("Stepping the Pi's own screen");

        controls.addView(prev, new LinearLayout.LayoutParams(Ui.dp(c, 44),
                ViewGroup.LayoutParams.WRAP_CONTENT));
        controls.addView(piScreenName, new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        controls.addView(next, new LinearLayout.LayoutParams(Ui.dp(c, 44),
                ViewGroup.LayoutParams.WRAP_CONTENT));
        panel.body.addView(controls);

        // -- actions ---------------------------------------------------------
        panel.body.addView(section(c, p, "ACTIONS"));
        LinearLayout actions = Ui.row(c);
        TextView calibrate = button(c, p, "Zero g-force", p.primary);
        calibrate.setOnClickListener(v -> act("Calibrating", () -> host.pi().calibrateImu(),
                "G-force zero set"));
        TextView wake = button(c, p, "Wake display", p.primary);
        wake.setOnClickListener(v -> act("Waking", () -> host.pi().wake(), "Display awake"));
        actions.addView(calibrate, Ui.cell(c, 2));
        actions.addView(wake, Ui.cell(c, 2));
        panel.body.addView(actions);

        // -- connection ------------------------------------------------------
        panel.body.addView(section(c, p, "CONNECTION"));

        addressField = field(c, p, "Pi address, e.g. 192.168.42.100:5000", false,
                host.piAddress());
        tokenField = field(c, p, "Token, from the Pi's console", true, host.piToken());
        panel.body.addView(addressField);
        panel.body.addView(tokenField);

        TextView apply = button(c, p, "Connect", p.accent);
        apply.setOnClickListener(v -> {
            host.applyConnection(addressField.getText().toString(),
                    tokenField.getText().toString());
            host.toast("Connecting to " + addressField.getText(), false);
        });
        LinearLayout applyRow = Ui.row(c);
        applyRow.addView(apply, Ui.cell(c, 2));
        panel.body.addView(applyRow);

        // -- transport -------------------------------------------------------
        // Which link is carrying the app, and why the others are not. The footer shows the
        // one in use but not the reason a fallback did not happen, which is the thing you
        // actually need when Bluetooth is meant to take over and has not.
        panel.body.addView(section(c, p, "TRANSPORT"));
        transportList = Ui.label(c, 9f, p.textDim);
        transportList.setLineSpacing(0f, 1.35f);
        panel.body.addView(transportList);
        refreshTransport();

        return panel;
    }

    private static TextView section(Context c, Palette p, String text) {
        TextView t = Ui.caps(c, 9f, p.textDim);
        t.setText(text);
        t.setPadding(0, Ui.dp(c, 10), 0, Ui.dp(c, 4));
        return t;
    }

    private static TextView button(Context c, Palette p, String text, int color) {
        TextView t = Ui.label(c, 11f, color);
        t.setText(text);
        t.setGravity(Gravity.CENTER);
        t.setPadding(Ui.dp(c, 10), Ui.dp(c, 8), Ui.dp(c, 10), Ui.dp(c, 8));
        t.setClickable(true);
        t.setFocusable(true);
        t.setBackground(Ui.rounded(c, Palette.alpha(color, 0.18f), 8f));
        return t;
    }

    private static EditText field(Context c, Palette p, String hint, boolean secret, String value) {
        EditText e = new EditText(c);
        e.setHint(hint);
        e.setText(value);
        e.setHintTextColor(p.textDim);
        e.setTextColor(p.text);
        e.setTextSize(11f);
        e.setSingleLine(true);
        e.setBackground(Ui.rounded(c, p.track, 8f));
        e.setPadding(Ui.dp(c, 8), Ui.dp(c, 7), Ui.dp(c, 8), Ui.dp(c, 7));
        if (secret) {
            e.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        }
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.topMargin = Ui.dp(c, 4);
        e.setLayoutParams(lp);
        return e;
    }

    /** Runs one action off the UI thread and reports the outcome. */
    private void act(String progress, Call call, String okMessage) {
        new Thread(() -> {
            try {
                JSONObject r = call.run();
                boolean ok = r.optBoolean("success");
                String msg = ok ? okMessage : r.optString("message", "Rejected");
                panel.post(() -> host.toast(msg, !ok));
            } catch (Exception e) {
                panel.post(() -> host.toast("Could not reach the Pi", true));
            }
            host.refreshNow();
        }).start();
    }

    private interface Call {
        JSONObject run() throws Exception;
    }

    @Override
    public void applyStatus(JSONObject status) {
        boolean live = host.pi().isConfigured();
        piState.set(live ? "UP" : "SET UP", live ? 0xFF22C55E : 0xFFF59E0B);
        demoState.set(status.optBoolean("demo_mode") ? "ON" : "OFF",
                status.optBoolean("demo_mode") ? 0xFFF59E0B : 0xFF22C55E);

        int piNum = status.optInt("screen", -1);
        piScreen.set(piNum >= 0 ? "#" + piNum : "\u2013");
        String name = status.optString("screen_name", "");
        if (!name.isEmpty()) {
            piScreenName.setText("Pi is showing " + name);
        }

        Runtime rt = Runtime.getRuntime();
        heapState.set(String.valueOf((rt.totalMemory() - rt.freeMemory()) / (1024 * 1024)));
    }

    @Override
    public void bind(Telemetry t) {
        canState.set(t.canConnected ? "UP" : "DOWN", t.canConnected ? 0xFF22C55E : 0xFFEF4444);
        tpmsState.set(t.tpmsConnected ? "UP" : "DOWN", t.tpmsConnected ? 0xFF22C55E : 0xFFEF4444);
    }
}
