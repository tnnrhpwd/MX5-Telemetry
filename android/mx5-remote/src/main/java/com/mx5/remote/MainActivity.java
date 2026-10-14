package com.mx5.remote;

import android.app.Activity;
import android.content.SharedPreferences;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.DisplayMetrics;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * MX5 Remote on the car screen.
 *
 * Replaces the Pi's HDMI display and covers everything the webapp does. It is a
 * "parked app": filed as a game with the CAR_LAUNCHER category, so Android Auto
 * projects it full screen without it needing Play approval.
 *
 * The shape is a left rail of screens, a content host that swaps between them, and
 * a chase strip at the bottom. A view toolbox builds every tree in code, so a
 * theme or scheme change just rebuilds it.
 *
 * Telemetry is polled rather than pushed. The Pi has a Socket.IO endpoint, but a
 * Socket.IO client for Android is a heavy dependency for a link that is a few
 * hundred microseconds away over the tether, and polling keeps the app entirely on
 * platform classes.
 */
public class MainActivity extends Activity implements Screen.Host {

    private static final String PREFS = "mx5";
    private static final String DEFAULT_ADDRESS = "192.168.42.100:5000";
    private static final int POLL_MS = 250;
    private static final int STATUS_EVERY = 8;
    private static final int ROOF_EVERY = 12;
    /** Fixed height of a vertical rail row, so the rows are uniform and bounded. */
    private static final int RAIL_ROW_DP = 32;

    private final PiClient pi = new PiClient();
    private final Handler handler = new Handler(Looper.getMainLooper());

    private SharedPreferences prefs;
    private Palette palette;
    private String schemeId = "aurora";
    private boolean dark = true;
    private boolean useMph = true;
    private boolean narrow;

    private Screen[] screens;
    private Screen screen;
    private int currentIndex;

    private LinearLayout root;
    private LinearLayout rail;
    private FrameLayout contentHost;
    private TextView linkPill, footerLeft, footerRight, themeButton, schemeButton;
    private final List<TextView> railChips = new ArrayList<>();
    private final List<View> railItems = new ArrayList<>();
    private final List<View> railMarkers = new ArrayList<>();

    private volatile boolean alive = true;
    private Thread poller;
    private volatile boolean online;
    private final Telemetry latest = new Telemetry();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        // A car screen has no system status bar to share with, and on a phone
        // preview that bar would otherwise sit across the title row.
        getWindow().setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN,
                WindowManager.LayoutParams.FLAG_FULLSCREEN);
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);

        schemeId = prefs.getString("scheme", "aurora");
        dark = prefs.getBoolean("dark", true);
        useMph = prefs.getBoolean("use_mph", true);
        currentIndex = prefs.getInt("screen", 0);

        pi.configure(prefs.getString("address", DEFAULT_ADDRESS), prefs.getString("token", ""));

        DisplayMetrics dm = getResources().getDisplayMetrics();
        narrow = Math.round(dm.widthPixels / dm.density) < 600;

        screens = new Screen[]{
                new OverviewScreen(),
                new RpmScreen(),
                new TpmsScreen(),
                new EngineScreen(),
                new GForceScreen(),
                new DiagnosticsScreen(),
                new SystemScreen(),
                new RoofScreen(),
                new SettingsScreen()
        };

        rebuildUi();
    }

    // ------------------------------------------------------------------- shell

    private void rebuildUi() {
        palette = Palette.of(schemeId, dark);

        root = Ui.column(this);
        // A scheme tint at the top gives the page an atmosphere. A fully flat page
        // reads as unbranded and makes the panels look pasted on rather than placed.
        root.setBackground(new GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM,
                new int[]{palette.pageGlow(), palette.page}));
        root.setPadding(Ui.dp(this, Ui.S4), Ui.dp(this, Ui.S3),
                Ui.dp(this, Ui.S4), Ui.dp(this, Ui.S3));

        root.addView(buildTopBar());

        LinearLayout middle = Ui.row(this);
        middle.setOrientation(narrow ? LinearLayout.VERTICAL : LinearLayout.HORIZONTAL);
        middle.setGravity(Gravity.TOP);

        rail = narrow ? Ui.row(this) : Ui.column(this);
        buildRail();

        contentHost = new FrameLayout(this);

        if (narrow) {
            // On a phone the rail becomes a strip under the content, because a
            // 130dp sidebar on a 400dp-wide screen leaves nothing to read.
            middle.addView(contentHost, new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
            middle.addView(rail, new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        } else {
            middle.addView(rail, new LinearLayout.LayoutParams(
                    Ui.dp(this, 136), ViewGroup.LayoutParams.MATCH_PARENT));
            middle.addView(contentHost, new LinearLayout.LayoutParams(
                    0, ViewGroup.LayoutParams.MATCH_PARENT, 1f));
        }

        root.addView(middle, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        root.addView(buildFooter());

        setContentView(root);
        showScreen(currentIndex, false);
        updateLink();
    }

    private View buildTopBar() {
        LinearLayout bar = Ui.row(this);
        bar.setPadding(0, 0, 0, Ui.dp(this, Ui.S1));

        TextView title = Ui.label(this, Ui.TYPE_DISPLAY, palette.accent);
        title.setTypeface(Ui.bold());
        title.setLetterSpacing(-0.01f);
        title.setText("MX5 Remote");

        linkPill = Ui.caps(this, Ui.TYPE_EYEBROW, palette.textDim);
        linkPill.setPadding(Ui.dp(this, 10), Ui.dp(this, 4), Ui.dp(this, 10), Ui.dp(this, 4));
        LinearLayout.LayoutParams pillParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        pillParams.leftMargin = Ui.dp(this, Ui.S4);

        schemeButton = topButton("Scheme");
        schemeButton.setOnClickListener(v -> {
            schemeId = Palette.SCHEMES[(Palette.indexOf(schemeId) + 1) % Palette.SCHEMES.length].id;
            prefs.edit().putString("scheme", schemeId).apply();
            rebuildUi();
        });

        themeButton = topButton(dark ? "Light" : "Dark");
        themeButton.setOnClickListener(v -> {
            dark = !dark;
            prefs.edit().putBoolean("dark", dark).apply();
            rebuildUi();
        });

        bar.addView(title);
        bar.addView(linkPill, pillParams);
        bar.addView(Ui.gap(this));
        bar.addView(schemeButton);
        bar.addView(themeButton);
        return bar;
    }

    private TextView topButton(String text) {
        TextView b = Ui.caps(this, Ui.TYPE_EYEBROW, palette.text);
        b.setText(text);
        b.setPadding(Ui.dp(this, 12), Ui.dp(this, 6), Ui.dp(this, 12), Ui.dp(this, 6));
        b.setClickable(true);
        b.setFocusable(true);
        b.setBackground(Ui.rounded(this, palette.track, 99f));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.leftMargin = Ui.dp(this, Ui.S2);
        b.setLayoutParams(lp);
        return b;
    }

    private void buildRail() {
        railChips.clear();
        railItems.clear();
        railMarkers.clear();
        rail.removeAllViews();

        for (int i = 0; i < screens.length; i++) {
            final int index = i;

            LinearLayout item = Ui.row(this);
            item.setClickable(true);
            item.setFocusable(true);
            item.setOnClickListener(v -> showScreen(index, true));

            // The marker sits OUTSIDE the pill rather than inside it. Inside, a square
            // 3dp bar would poke through the pill's rounded corner.
            View marker = new View(this);
            LinearLayout pill = Ui.row(this);
            pill.setBackground(Ui.rounded(this, 0x00000000, 9f));

            TextView text = Ui.label(this,
                    narrow ? Ui.TYPE_EYEBROW : Ui.TYPE_LABEL, palette.textDim);
            text.setText(narrow ? screens[i].shortTitle() : screens[i].title());
            text.setGravity(narrow ? Gravity.CENTER : Gravity.CENTER_VERTICAL);
            text.setSingleLine(true);

            if (narrow) {
                pill.setPadding(Ui.dp(this, Ui.S3), Ui.dp(this, Ui.S4),
                        Ui.dp(this, Ui.S3), Ui.dp(this, Ui.S4));
                pill.addView(text, Ui.fillWidth());
                item.addView(pill, new LinearLayout.LayoutParams(
                        0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
            } else {
                pill.setPadding(Ui.dp(this, Ui.S4), Ui.dp(this, Ui.S4),
                        Ui.dp(this, Ui.S3), Ui.dp(this, Ui.S4));
                pill.addView(text, Ui.fillWidth());

                LinearLayout.LayoutParams mp = new LinearLayout.LayoutParams(
                        Ui.dp(this, 3), ViewGroup.LayoutParams.MATCH_PARENT);
                mp.topMargin = Ui.dp(this, Ui.S3);
                mp.bottomMargin = Ui.dp(this, Ui.S3);
                item.addView(marker, mp);

                LinearLayout.LayoutParams pp = Ui.fillWidth();
                pp.leftMargin = Ui.dp(this, Ui.S1 + 2);
                item.addView(pill, pp);
            }

            // The row needs an EXPLICIT height. The marker inside it is MATCH_PARENT, and
            // a wrap_content parent with a match_parent child measures to the whole
            // available space, so the first row would eat the entire rail and push the
            // other eight past the bottom edge, where they are never laid out at all.
            LinearLayout.LayoutParams ip = narrow
                    ? new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
                    : new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                    Ui.dp(this, RAIL_ROW_DP));
            ip.bottomMargin = Ui.dp(this, narrow ? 0 : Ui.S2);
            ip.leftMargin = Ui.dp(this, narrow ? Ui.S1 : 0);
            ip.rightMargin = Ui.dp(this, narrow ? Ui.S1 : 0);
            rail.addView(item, ip);

            railItems.add(pill);
            railMarkers.add(marker);
            railChips.add(text);
        }
        updateRail();
    }

    private void updateRail() {
        for (int i = 0; i < railChips.size(); i++) {
            boolean on = i == currentIndex;
            railChips.get(i).setTextColor(on ? palette.accent : palette.textDim);
            railChips.get(i).setTypeface(on ? Ui.bold() : null);
            railItems.get(i).setBackground(
                    Ui.rounded(this, on ? palette.accentWash() : 0x00000000, 9f));
            if (!narrow) {
                railMarkers.get(i).setBackground(on
                        ? Ui.rounded(this, palette.accent, 2f) : null);
            }
        }
    }

    private View buildFooter() {
        LinearLayout wrap = Ui.column(this);

        LinearLayout.LayoutParams hp = Ui.lp(ViewGroup.LayoutParams.MATCH_PARENT, 1);
        hp.topMargin = Ui.dp(this, Ui.S3);
        wrap.addView(Ui.hairline(this, palette.hairline), hp);

        LinearLayout bar = Ui.row(this);
        bar.setPadding(0, Ui.dp(this, Ui.S2), 0, 0);

        footerLeft = Ui.label(this, Ui.TYPE_EYEBROW, palette.textDim);
        footerRight = Ui.tnum(Ui.caps(this, Ui.TYPE_EYEBROW, palette.primary));
        footerRight.setTypeface(Ui.bold());

        bar.addView(footerLeft);
        bar.addView(Ui.gap(this));
        bar.addView(footerRight);
        wrap.addView(bar);
        return wrap;
    }

    // ----------------------------------------------------------------- screens

    private void showScreen(int index, boolean notifyPi) {
        currentIndex = Math.floorMod(index, screens.length);
        screen = screens[currentIndex];

        contentHost.removeAllViews();
        View content = screen.build(this, palette, this);
        contentHost.addView(content, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        updateRail();
        prefs.edit().putInt("screen", currentIndex).apply();

        if (notifyPi && screen.piScreen() >= 0 && online) {
            pushPiScreen(screen.piScreen());
        }
        if (screen instanceof RoofScreen) {
            refreshRoof();
        }
        screen.bind(latest);
    }

    private void pushPiScreen(int piScreen) {
        new Thread(() -> {
            try {
                pi.setScreen(piScreen);
            } catch (Exception e) {
                handler.post(() -> toast("Pi did not accept the screen change", true));
            }
        }).start();
    }

    // ----------------------------------------------------------------- polling

    private void startPolling() {
        if (poller != null) {
            return;
        }
        poller = new Thread(() -> {
            int tick = 0;
            while (alive) {
                if (pi.isConfigured()) {
                    try {
                        Telemetry t = Telemetry.from(pi.telemetry());
                        online = true;
                        handler.post(() -> {
                            copyInto(t);
                            screen.bind(latest);
                            updateLink();
                        });
                        if (tick % STATUS_EVERY == 0) {
                            JSONObject status = pi.status();
                            handler.post(() -> {
                                applyStatus(status);
                                online = true;
                                updateLink();
                            });
                        }
                        if (tick % ROOF_EVERY == 0 && screen instanceof RoofScreen) {
                            JSONObject roof = pi.roofStatus();
                            handler.post(() -> ((RoofScreen) screen).applyRoof(roof));
                        }
                    } catch (Exception e) {
                        if (online) {
                            online = false;
                            handler.post(this::updateLink);
                        }
                    }
                }
                tick++;
                try {
                    Thread.sleep(POLL_MS);
                } catch (InterruptedException e) {
                    return;
                }
            }
        }, "pi-poll");
        poller.start();
    }

    /** Telemetry is a fresh object per poll, so copy it into the long-lived one. */
    private void copyInto(Telemetry t) {
        latest.rpm = t.rpm;
        latest.speedKmh = t.speedKmh;
        latest.gear = t.gear;
        latest.gearEstimated = t.gearEstimated;
        latest.clutchEngaged = t.clutchEngaged;
        latest.recommendedGear = t.recommendedGear;
        latest.gearColor = t.gearColor;
        latest.inNeutral = t.inNeutral;
        latest.inReverse = t.inReverse;
        latest.throttlePercent = t.throttlePercent;
        latest.brakePercent = t.brakePercent;
        latest.coolantTempF = t.coolantTempF;
        latest.intakeTempF = t.intakeTempF;
        latest.ambientTempF = t.ambientTempF;
        latest.maf = t.maf;
        latest.fuelLevelPercent = t.fuelLevelPercent;
        latest.voltage = t.voltage;
        latest.tirePressure.clear();
        latest.tirePressure.addAll(t.tirePressure);
        latest.tireTemp.clear();
        latest.tireTemp.addAll(t.tireTemp);
        latest.tpmsUpdated.clear();
        latest.tpmsUpdated.addAll(t.tpmsUpdated);
        latest.tpmsConnected = t.tpmsConnected;
        latest.gLateral = t.gLateral;
        latest.gLongitudinal = t.gLongitudinal;
        latest.lapTimeMs = t.lapTimeMs;
        latest.bestLapMs = t.bestLapMs;
        latest.instantMpg = t.instantMpg;
        latest.averageMpg = t.averageMpg;
        latest.rangeMiles = t.rangeMiles;
        latest.checkEngine = t.checkEngine;
        latest.absWarning = t.absWarning;
        latest.tractionControlActive = t.tractionControlActive;
        latest.tractionControlOff = t.tractionControlOff;
        latest.oilWarning = t.oilWarning;
        latest.batteryWarning = t.batteryWarning;
        latest.doorAjar = t.doorAjar;
        latest.seatbeltWarning = t.seatbeltWarning;
        latest.airbagWarning = t.airbagWarning;
        latest.brakeWarning = t.brakeWarning;
        latest.headlightsOn = t.headlightsOn;
        latest.highBeamsOn = t.highBeamsOn;
        latest.fogLightOn = t.fogLightOn;
        latest.dtcCodes.clear();
        latest.dtcCodes.addAll(t.dtcCodes);
        latest.dtcCount = t.dtcCount;
        latest.canConnected = t.canConnected;
        latest.demoMode = t.demoMode;
        latest.sleeping = t.sleeping;
    }

    private void applyStatus(JSONObject status) {
        JSONObject settings = status.optJSONObject("settings");
        if (settings != null) {
            useMph = settings.optBoolean("use_mph", useMph);
            prefs.edit().putBoolean("use_mph", useMph).apply();
        }
        screen.applyStatus(status);
    }

    private void refreshRoof() {
        new Thread(() -> {
            try {
                JSONObject roof = pi.roofStatus();
                handler.post(() -> {
                    if (screen instanceof RoofScreen) {
                        ((RoofScreen) screen).applyRoof(roof);
                    }
                });
            } catch (Exception e) {
                handler.post(() -> {
                    if (screen instanceof RoofScreen) {
                        ((RoofScreen) screen).applyRoof(null);
                    }
                });
            }
        }).start();
    }

    private void updateLink() {
        String text;
        int color;
        if (!pi.isConfigured()) {
            text = "SET UP";
            color = palette.warn;
        } else if (online) {
            text = "LINKED";
            color = palette.good;
        } else {
            text = "OFFLINE";
            color = palette.bad;
        }
        if (linkPill != null) {
            linkPill.setText(text);
            linkPill.setTextColor(color);
            linkPill.setBackground(Ui.rounded(this, palette.washOf(color), 99f));
        }
        if (footerLeft != null) {
            footerLeft.setText(pi.isConfigured() ? pi.baseUrl() : "No Pi address set, see System");
        }
        if (footerRight != null) {
            String state = !online ? "OFFLINE"
                    : latest.sleeping ? "PI ASLEEP"
                    : latest.demoMode ? "DEMO" : "LIVE";
            footerRight.setText(String.format(Locale.US, "%s  \u00b7  %d rpm", state, latest.rpm));
        }
    }

    // -------------------------------------------------------------------- host

    @Override
    public PiClient pi() {
        return pi;
    }

    @Override
    public void toast(String message, boolean error) {
        Toast.makeText(this, message, error ? Toast.LENGTH_LONG : Toast.LENGTH_SHORT).show();
    }

    @Override
    public void refreshNow() {
        new Thread(() -> {
            try {
                JSONObject status = pi.status();
                handler.post(() -> {
                    online = true;
                    applyStatus(status);
                    updateLink();
                });
            } catch (Exception e) {
                // the poll loop owns marking the link offline
            }
        }).start();
        refreshRoof();
    }

    @Override
    public boolean useMph() {
        return useMph;
    }

    @Override
    public String piAddress() {
        return prefs.getString("address", DEFAULT_ADDRESS);
    }

    @Override
    public String piToken() {
        return prefs.getString("token", "");
    }

    @Override
    public void applyConnection(String address, String token) {
        pi.configure(address, token);
        prefs.edit().putString("address", address).putString("token", token).apply();
        refreshNow();
    }

    @Override
    public void stepPiScreen(boolean forward) {
        new Thread(() -> {
            try {
                pi.stepScreen(forward);
            } catch (Exception e) {
                handler.post(() -> toast("Pi did not respond", true));
            }
            refreshNow();
        }).start();
    }

    // ---------------------------------------------------------------- lifecycle

    @Override
    protected void onResume() {
        super.onResume();
        startPolling();
        refreshNow();
    }

    @Override
    protected void onPause() {
        super.onPause();
        // Stop the poll loop while hidden: a backgrounded app holding a 4Hz poll
        // open on the tether just drains the phone.
        if (poller != null) {
            poller.interrupt();
            poller = null;
        }
    }

    @Override
    protected void onDestroy() {
        alive = false;
        if (poller != null) {
            poller.interrupt();
            poller = null;
        }
        super.onDestroy();
    }

    @Override
    public void onConfigurationChanged(android.content.res.Configuration newConfig) {
        super.onConfigurationChanged(newConfig);
        DisplayMetrics dm = getResources().getDisplayMetrics();
        boolean nowNarrow = Math.round(dm.widthPixels / dm.density) < 600;
        if (nowNarrow != narrow) {
            narrow = nowNarrow;
            rebuildUi();
        }
    }
}
