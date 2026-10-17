package com.mx5.remote;

import android.content.Context;
import android.view.Gravity;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONObject;

/** The roof controller: the MX5things RCNC-2 on the Pi's serial port. */
public class RoofScreen extends Screen {

    private Host host;
    private Palette palette;
    private Ui.Panel panel;
    private Ui.Stat firmware, port, state;
    private SliderRow speed;
    private Ui.Pill auto;
    private LinearLayout modes;
    private TextView linkButton;
    private boolean released;
    private static final int[] MODE_IDS = {1, 2, 0};
    private static final String[] MODE_NAMES = {"One Touch", "OEM", "Valet"};

    @Override
    public String title() {
        return "Roof";
    }

    @Override
    public String eyebrow() {
        return "RCNC-2";
    }

    /** The Pi has no screen for this, it is a separate device on the serial port. */
    @Override
    public int piScreen() {
        return -1;
    }

    @Override
    public View build(Context c, Palette p, Host h) {
        host = h;
        palette = p;
        panel = new Ui.Panel(c, p, "RCNC-2", "Roof Controller", p.primary);

        // The roof status arrives on its own poll, so seed the tiles: an unseeded one
        // shows as an empty box, which is indistinguishable from a layout fault.
        firmware = new Ui.Stat(c, p, "FIRMWARE", "");
        firmware.set("waiting");
        port = new Ui.Stat(c, p, "PORT", "");
        port.set("waiting");
        state = new Ui.Stat(c, p, "STATE", "");
        state.set("waiting", p.textDim);
        panel.body.addView(grid(c, firmware, port, state));

        speed = new SliderRow(c, p, "Speed limit", 0, 30, 1, 30, " mph", p.accent,
                value -> act(host.pi()::roofSpeed, value, "Speed limit set"));
        panel.body.addView(speed);

        TextView modeLabel = Ui.caps(c, 9f, p.textDim);
        modeLabel.setText("MODE");
        modeLabel.setPadding(0, Ui.dp(c, 8), 0, Ui.dp(c, 3));
        panel.body.addView(modeLabel);

        modes = Ui.row(c);
        for (int i = 0; i < MODE_IDS.length; i++) {
            final int modeId = MODE_IDS[i];
            TextView b = Ui.label(c, 11f, p.text);
            b.setText(MODE_NAMES[i]);
            b.setGravity(Gravity.CENTER);
            b.setPadding(Ui.dp(c, 10), Ui.dp(c, 8), Ui.dp(c, 10), Ui.dp(c, 8));
            b.setClickable(true);
            b.setFocusable(true);
            b.setBackground(Ui.rounded(c, 0x00000000, 8f));
            b.setOnClickListener(v -> act(host.pi()::roofMode, modeId, "Mode set"));
            modes.addView(b, Ui.cell(c, 3));
        }
        panel.body.addView(modes);

        // The commands sit at the bottom of the panel and the readouts at the top, so the
        // leftover height becomes one clean break between them instead of a void under
        // the last row.
        View gap = new View(c);
        gap.setLayoutParams(new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f));
        panel.body.addView(gap);

        LinearLayout autoRow = Ui.row(c);
        autoRow.setPadding(0, Ui.dp(c, 12), 0, 0);
        TextView autoLabel = Ui.label(c, 11f, p.text);
        autoLabel.setText("Auto, lower when the latch is released");
        auto = new Ui.Pill(c, p, p.primary);
        auto.setOnClickListener(v -> {
            auto.setOn(!auto.isOn());
            act(host.pi()::roofAuto, auto.isOn() ? 1 : 0, "Auto updated");
        });
        autoRow.addView(autoLabel);
        autoRow.addView(Ui.gap(c));
        autoRow.addView(auto);
        panel.body.addView(autoRow);

        TextView hint = Ui.label(c, 9f, p.textDim);
        hint.setText("One Touch for normal use. OEM restores the factory limits. "
                + "Valet disables the roof.");
        hint.setPadding(0, Ui.dp(c, 10), 0, 0);
        panel.body.addView(hint);

        // The claim toggle is a maintenance control, so it sits last: handing the module
        // back is what leaves the car free to operate the roof normally.
        linkButton = Ui.label(c, 11f, p.text);
        linkButton.setGravity(Gravity.CENTER);
        linkButton.setPadding(Ui.dp(c, 10), Ui.dp(c, 12), Ui.dp(c, 10), Ui.dp(c, 10));
        linkButton.setClickable(true);
        linkButton.setFocusable(true);
        linkButton.setBackground(Ui.rounded(c, 0x00000000, 8f));
        linkButton.setOnClickListener(v -> toggleLink());
        panel.body.addView(linkButton, Ui.stack(c, 0));
        setLinkLabel();

        return panel;
    }

    /** Flips the Pi between claiming the module and leaving it to the car. */
    private void toggleLink() {
        if (released) {
            act(v -> host.pi().roofConnect(), 0, "Roof controller claimed");
        } else {
            act(v -> host.pi().roofDisconnect(), 0, "Handed back to the car");
        }
    }

    /** The button names the state change it performs, not the state it is in. */
    private void setLinkLabel() {
        if (linkButton == null) {
            return;
        }
        linkButton.setText(released ? "Claim controller" : "Hand back to car");
        linkButton.setTextColor(released ? palette.accent : palette.text);
    }

    /** Runs one command off the UI thread and reports what the Pi said. */
    private void act(Command cmd, int value, String okMessage) {
        new Thread(() -> {
            try {
                JSONObject r = cmd.run(value);
                if (r.optBoolean("success")) {
                    panel.post(() -> host.toast(okMessage, false));
                } else {
                    String err = r.optString("error", "Rejected");
                    panel.post(() -> host.toast(err, true));
                }
            } catch (Exception e) {
                panel.post(() -> host.toast("Roof controller unreachable", true));
            }
            host.refreshNow();
        }).start();
    }

    private interface Command {
        JSONObject run(int value) throws Exception;
    }

    @Override
    public void bind(Telemetry t) {
        // The roof values arrive on their own poll, which MainActivity pushes in
        // through applyRoof(), so nothing here depends on telemetry.
    }

    /** Called by the shell with the payload from GET /api/roof/status. */
    public void applyRoof(JSONObject roof) {
        boolean connected = roof != null && roof.optBoolean("connected");
        // Released is a deliberate state rather than a fault: the Pi is leaving the module
        // alone so the car keeps the roof, which is why it is not painted as an alarm.
        released = roof != null && roof.optBoolean("released");

        if (released) {
            state.set("RELEASED", palette.textDim);
        } else {
            state.set(connected ? "LINKED" : "OFFLINE",
                    connected ? 0xFF22C55E : 0xFFEF4444);
        }
        setLinkLabel();

        // Reaching here at all means the Pi answered, so "no link" is about the RCNC-2
        // itself being unplugged, not about the phone's connection to the Pi.
        firmware.set(connected ? roof.optString("version", "unknown") : "no link");
        port.set(connected ? roof.optString("port", "none") : "no link");

        if (!connected) {
            return;
        }
        speed.setValue(roof.optInt("speed_limit", 30));
        auto.setOn(roof.optInt("auto", 0) == 1);

        int mode = roof.optInt("mode", 1);
        for (int i = 0; i < MODE_IDS.length; i++) {
            boolean on = MODE_IDS[i] == mode;
            TextView b = (TextView) modes.getChildAt(i);
            b.setTextColor(on ? palette.accent : palette.text);
            b.setBackground(Ui.rounded(panel.getContext(), on
                    ? Palette.alpha(palette.accent, 0.24f) : 0x00000000, 8f));
        }
    }
}
