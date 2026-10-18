package com.mx5.remote;

import android.Manifest;
import android.app.Activity;
import android.bluetooth.BluetoothDevice;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.drawable.GradientDrawable;
import android.os.BatteryManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.DisplayMetrics;
import android.util.Log;
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
import java.util.Calendar;
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
    /** Lifecycle only. Link failures log under MX5Link, Bluetooth under MX5Ble. */
    private static final String TAG = "MX5Life";
    private static final String DEFAULT_ADDRESS = "192.168.42.100:5000";    private static final int POLL_MS = 250;
    private static final int STATUS_EVERY = 8;
    private static final int ROOF_EVERY = 12;
    /** Fixed height of a vertical rail row, so the rows are uniform and bounded. */
    private static final int RAIL_ROW_DP = 32;

    /** Request code for the one-off Nearby devices prompt. */
    private static final int REQ_BLUETOOTH = 1001;

    /**
     * Shared with the other instance Android Auto may have running, and assigned in
     * onCreate(). Not created here: a second instance must join the existing link rather
     * than open a competing GATT connection, and must not close it when it goes away.
     */
    private PiClient pi;
    private final Handler handler = new Handler(Looper.getMainLooper());

    /**
     * Where the Bluetooth transports get their device, and why they cannot have one.
     *
     * The transports are handed this rather than reaching into preferences themselves, so
     * that the "why not" message can be built where the Bluetooth state is visible.
     */
    private final BtTransport.DeviceSource btDevices = new BtTransport.DeviceSource() {
        @Override
        public BluetoothDevice device() {
            return BtDevices.find(MainActivity.this, prefs.getString("bt_device", ""));
        }

        @Override
        public String reason() {
            return BtDevices.explain(MainActivity.this, prefs.getString("bt_device", ""));
        }
    };

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

    /** Phone-only overlay drawer: the scrim, and the panel that slides under the header. */
    private FrameLayout drawerHost;
    private View drawerScrim, drawerPanel;

    /** The drawer's destination rows, indexed by screen, so "you are here" can be moved. */
    private TextView[] drawerDestViews;

    // What a system bar would tell you. A parked app draws full-bleed, so there is no bar to
    // read the time or the charge from, and no chrome to leave the app with either.
    private BatteryIcon batteryIcon;
    private TextView batteryPct, clockText;
    private Handler clockHandler;
    private BroadcastReceiver batteryReceiver;

    /**
     * The drawer's groups, by screen index.
     *
     * Nine flat destinations is a list; three named groups is a map. The reference project
     * groups its drawer the same way, and it is the one thing a drawer can do that a row of
     * tabs cannot.
     */
    private static final int[][] DRAWER_GROUPS = {
            {0, 1, 2, 3, 4},
            {5, 6},
            {7, 8}
    };
    private static final String[] DRAWER_GROUP_NAMES = {"Live", "Status", "Control"};

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

        pi = PiLink.acquire();
        pi.configure(prefs.getString("address", DEFAULT_ADDRESS), prefs.getString("token", ""));
        // Only the instance that created the shared client builds the Bluetooth chain. A
        // second instance rebuilding it would drop the transport that is already carrying
        // the link, and leave its GATT connection open but unreachable.
        if (!pi.bluetoothConfigured()) {
            pi.setBluetooth(this, btDevices, prefs.getString("token", ""));
        }
        requestBluetoothPermission();

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

        if (!narrow) {
            // Only the car. A phone has a system bar with both of these already on it, and a
            // second copy of a clock an inch from the real one is just noise.
            registerBattery();
            startClock();
        }
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
            // No rail and no strip on a phone: the drawer carries navigation, which is what
            // the reference project does and what stops nine destinations being squeezed
            // into a scrolling row where half of them start off-screen.
            middle.addView(contentHost, new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        } else {
            middle.addView(rail, new LinearLayout.LayoutParams(
                    Ui.dp(this, 136), ViewGroup.LayoutParams.MATCH_PARENT));
            middle.addView(contentHost, new LinearLayout.LayoutParams(
                    0, ViewGroup.LayoutParams.MATCH_PARENT, 1f));
        }

        root.addView(middle, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        root.addView(buildFooter());

        if (narrow) {
            // The drawer covers the whole shell, so it needs a container above `root`
            // rather than a slot inside it. On the car the rail makes it unnecessary.
            FrameLayout shell = new FrameLayout(this);
            shell.addView(root, new FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.MATCH_PARENT));
            shell.addView(buildDrawer(), new FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.MATCH_PARENT));
            setContentView(shell);
        } else {
            setContentView(root);
            // Drop the phone-only views so a build is never holding two shells.
            drawerHost = null;
            drawerScrim = null;
            drawerPanel = null;
            drawerDestViews = null;
        }
        showScreen(currentIndex, false);
        updateLink();
    }

    // ------------------------------------------------------------------ drawer

    /**
     * The phone's navigation drawer.
     *
     * A dropdown in the header rather than a rail or a strip, grouped so nine screens read
     * as three purposes. Built here rather than from a layout file because the whole shell is
     * built in code, and drawn from the palette so it follows the theme and the scheme like
     * everything else.
     */
    private View buildDrawer() {
        drawerHost = new FrameLayout(this);

        // Tapping anywhere outside closes it, which is what makes a dropdown feel
        // dismissible rather than modal.
        drawerScrim = new View(this);
        drawerScrim.setBackgroundColor(0x99000000);
        drawerScrim.setOnClickListener(v -> closeDrawer());
        drawerHost.addView(drawerScrim, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));

        drawerPanel = Ui.column(this);
        LinearLayout panel = (LinearLayout) drawerPanel;
        panel.setBackground(Ui.rounded(this, palette.panel, 14f));
        panel.setPadding(Ui.dp(this, Ui.S4), Ui.dp(this, Ui.S5),
                Ui.dp(this, Ui.S4), Ui.dp(this, Ui.S5));
        // Swallow taps so they do not fall through to the scrim and close the drawer.
        panel.setClickable(true);

        drawerDestViews = new TextView[screens.length];
        for (int g = 0; g < DRAWER_GROUPS.length; g++) {
            TextView group = Ui.caps(this, Ui.TYPE_EYEBROW, palette.textDim);
            group.setText(DRAWER_GROUP_NAMES[g]);
            group.setPadding(0, Ui.dp(this, g == 0 ? Ui.S2 : Ui.S4), 0, Ui.dp(this, Ui.S2));
            panel.addView(group);

            for (int idx : DRAWER_GROUPS[g]) {
                final int index = idx;
                TextView item = drawerRow(screens[index].title(), palette.text);
                drawerDestViews[index] = item;
                item.setOnClickListener(v -> {
                    closeDrawer();
                    showScreen(index, true);
                });
                panel.addView(item);
            }
        }

        // The display controls live here rather than in the header. That is where the
        // reference project keeps the chrome, and it is what lets the phone header stay a
        // single uncluttered line: a title, the link state, and this button.
        TextView display = Ui.caps(this, Ui.TYPE_EYEBROW, palette.textDim);
        display.setText("Display");
        display.setPadding(0, Ui.dp(this, Ui.S4), 0, Ui.dp(this, Ui.S2));
        panel.addView(display);

        TextView scheme = drawerRow(
                "Scheme: " + Palette.SCHEMES[Palette.indexOf(schemeId)].name, palette.accent);
        scheme.setOnClickListener(v -> {
            schemeId = Palette.SCHEMES[(Palette.indexOf(schemeId) + 1)
                    % Palette.SCHEMES.length].id;
            prefs.edit().putString("scheme", schemeId).apply();
            rebuildUi();
        });
        panel.addView(scheme);

        TextView theme = drawerRow(dark ? "Theme: dark" : "Theme: light", palette.accent);
        theme.setOnClickListener(v -> {
            dark = !dark;
            prefs.edit().putBoolean("dark", dark).apply();
            rebuildUi();
        });
        panel.addView(theme);

        TextView appGroup = Ui.caps(this, Ui.TYPE_EYEBROW, palette.textDim);
        appGroup.setText("App");
        appGroup.setPadding(0, Ui.dp(this, Ui.S4), 0, Ui.dp(this, Ui.S2));
        panel.addView(appGroup);

        TextView quit = drawerRow("Exit", palette.bad);
        quit.setOnClickListener(v -> exitApp());
        panel.addView(quit);

        int width = (int) (getResources().getDisplayMetrics().widthPixels * 0.72);
        FrameLayout.LayoutParams pp = new FrameLayout.LayoutParams(
                width, ViewGroup.LayoutParams.WRAP_CONTENT);
        pp.gravity = Gravity.TOP | Gravity.END;
        pp.topMargin = Ui.dp(this, 52);
        pp.rightMargin = Ui.dp(this, Ui.S4);
        drawerHost.addView(panel, pp);

        // GONE rather than INVISIBLE: an invisible view still takes part in layout, and a
        // full-size scrim would then swallow every tap on the page behind it.
        drawerHost.setVisibility(View.GONE);
        return drawerHost;
    }

    /** One row in the drawer. Full width, so the whole line is the target. */
    private TextView drawerRow(String text, int color) {
        TextView row = Ui.label(this, Ui.TYPE_BODY, color);
        row.setText(text);
        row.setPadding(Ui.dp(this, Ui.S3), Ui.dp(this, Ui.S5),
                Ui.dp(this, Ui.S3), Ui.dp(this, Ui.S5));
        row.setBackground(Ui.ripple(this, Ui.haze(palette.accent), 0x00000000, 9f));
        row.setClickable(true);
        row.setFocusable(true);
        return row;
    }

    /**
     * The hamburger. Three drawn bars rather than a glyph: U+2630 depends on the font the
     * head unit happens to ship, and a missing glyph is a box.
     */
    private View hamburgerButton() {
        LinearLayout b = Ui.column(this);
        b.setGravity(Gravity.CENTER);
        b.setPadding(Ui.dp(this, Ui.S3), Ui.dp(this, Ui.S4),
                Ui.dp(this, Ui.S3), Ui.dp(this, Ui.S4));
        // The bars alone come to about 28dp. A control you tap with a thumb needs to be
        // nearer 48, so the target is padded out even though the glyph stays small.
        b.setMinimumWidth(Ui.dp(this, 48));
        b.setMinimumHeight(Ui.dp(this, 48));
        b.setClickable(true);
        b.setFocusable(true);
        b.setBackground(Ui.ripple(this, Ui.haze(palette.text), palette.track, 99f));
        b.setOnClickListener(v -> toggleDrawer());
        for (int i = 0; i < 3; i++) {
            View bar = new View(this);
            bar.setBackground(Ui.rounded(this, palette.text, 99f));
            LinearLayout.LayoutParams bp = new LinearLayout.LayoutParams(
                    Ui.dp(this, 16), Ui.dp(this, 2));
            bp.topMargin = Ui.dp(this, i == 0 ? 0 : 3);
            b.addView(bar, bp);
        }
        return b;
    }

    /**
     * Whether the OS is asking for less movement.
     *
     * Android's equivalent of `prefers-reduced-motion`. The standard expects the setting to be
     * honoured rather than treated as a preference, and a head unit that has it off is asking
     * for a still screen.
     */
    private boolean reduceMotion() {
        return android.provider.Settings.Global.getFloat(getContentResolver(),
                android.provider.Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f;
    }

    private void toggleDrawer() {
        if (drawerHost == null) {
            return;
        }
        if (drawerHost.getVisibility() == View.VISIBLE) {
            closeDrawer();
            return;
        }
        boolean still = reduceMotion();
        drawerScrim.setAlpha(still ? 1f : 0f);
        drawerPanel.setAlpha(still ? 1f : 0f);
        drawerPanel.setTranslationY(still ? 0f : -Ui.dp(this, 12));
        drawerHost.setVisibility(View.VISIBLE);
        if (still) {
            return;
        }
        drawerScrim.animate().alpha(1f).setDuration(160).start();
        drawerPanel.animate().alpha(1f).translationY(0f).setDuration(180).start();
    }

    private void closeDrawer() {
        if (drawerHost == null || drawerHost.getVisibility() != View.VISIBLE) {
            return;
        }
        if (reduceMotion()) {
            drawerHost.setVisibility(View.GONE);
            return;
        }
        drawerScrim.animate().alpha(0f).setDuration(140).start();
        drawerPanel.animate().alpha(0f).translationY(-Ui.dp(this, 12)).setDuration(140)
                .withEndAction(() -> drawerHost.setVisibility(View.GONE)).start();
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
        if (narrow) {
            // Scheme and theme have moved into the drawer, so the phone header is one line:
            // the title, the link state, and the way in. No battery or clock here either, for
            // the same reason no other phone app draws them: the OS already does.
            bar.addView(hamburgerButton());
        } else {
            bar.addView(buildStatusChip());
            bar.addView(schemeButton);
            bar.addView(themeButton);
            bar.addView(buildExitButton());
        }
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

    /**
     * Battery and clock, in the corner a system bar would have used.
     *
     * They share one chip because they are one thought, and because a chip reads as an
     * instrument while two loose readouts read as debris.
     */
    private View buildStatusChip() {
        LinearLayout chip = Ui.row(this);
        chip.setGravity(Gravity.CENTER_VERTICAL);
        chip.setPadding(Ui.dp(this, 10), Ui.dp(this, 6), Ui.dp(this, 10), Ui.dp(this, 6));
        chip.setBackground(Ui.rounded(this, palette.track, 99f));

        batteryIcon = new BatteryIcon(this);
        batteryIcon.setColors(palette.track, palette.text, palette.bad, palette.good);
        chip.addView(batteryIcon);

        batteryPct = Ui.caps(this, Ui.TYPE_EYEBROW, palette.textDim);
        batteryPct.setText("--%");
        LinearLayout.LayoutParams bp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        bp.leftMargin = Ui.dp(this, Ui.S2);
        chip.addView(batteryPct, bp);

        clockText = Ui.label(this, Ui.TYPE_BODY, palette.text);
        clockText.setTypeface(Ui.bold());
        // Tabular figures. Without them the clock's own width changes as the digits change,
        // and on a dashboard a readout that shivers once a minute is the loudest thing there.
        clockText.setFontFeatureSettings("tnum");
        clockText.setText("--:--");
        LinearLayout.LayoutParams cp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        cp.leftMargin = Ui.dp(this, Ui.S4);
        chip.addView(clockText, cp);

        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.leftMargin = Ui.dp(this, Ui.S2);
        chip.setLayoutParams(lp);
        return chip;
    }

    /**
     * The way out.
     *
     * Tinted with the alert colour rather than the neutral chip, because it is the one control
     * in this row that is not a cosmetic toggle and should not be mistaken for one. It sits at
     * the far right edge, which is both the conventional place for a close and the easiest
     * target to reach without looking away from the road.
     */
    private TextView buildExitButton() {
        TextView b = Ui.caps(this, Ui.TYPE_EYEBROW, palette.bad);
        b.setText("Exit");
        b.setPadding(Ui.dp(this, 14), Ui.dp(this, 6), Ui.dp(this, 14), Ui.dp(this, 6));
        b.setClickable(true);
        b.setFocusable(true);
        b.setBackground(Ui.ripple(this, Ui.haze(palette.bad), palette.washOf(palette.bad), 99f));
        b.setOnClickListener(v -> exitApp());
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        // A wider gap than the other controls: this one should not be one slip away from Theme.
        lp.leftMargin = Ui.dp(this, Ui.S5);
        b.setLayoutParams(lp);
        return b;
    }

    /**
     * Leave the app.
     *
     * finishAffinity rather than finish, so the whole task goes and the head unit gets its own
     * home screen back. There is exactly one activity here, but a partly finished task on
     * Android Auto can leave a blank canvas behind, which looks like a crash.
     */
    private void exitApp() {
        finishAffinity();
    }

    /**
     * Follow the battery from here on.
     *
     * ACTION_BATTERY_CHANGED is sticky, so registering hands us the current value at once and
     * there is deliberately no separate "read it once" path that could disagree with it.
     */
    private void registerBattery() {
        batteryReceiver = new BroadcastReceiver() {
            @Override
            public void onReceive(Context context, Intent intent) {
                int raw = intent.getIntExtra(BatteryManager.EXTRA_LEVEL, -1);
                int scale = intent.getIntExtra(BatteryManager.EXTRA_SCALE, -1);
                int status = intent.getIntExtra(BatteryManager.EXTRA_STATUS, -1);
                boolean charging = status == BatteryManager.BATTERY_STATUS_CHARGING
                        || status == BatteryManager.BATTERY_STATUS_FULL;
                int pct = (raw < 0 || scale <= 0)
                        ? BatteryIcon.UNKNOWN : Math.round(raw * 100f / scale);

                if (batteryIcon != null) {
                    batteryIcon.setLevel(pct, charging);
                }
                if (batteryPct != null) {
                    batteryPct.setText(pct < 0 ? "--%" : pct + "%");
                }
            }
        };
        IntentFilter filter = new IntentFilter(Intent.ACTION_BATTERY_CHANGED);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(batteryReceiver, filter, Context.RECEIVER_NOT_EXPORTED);
        } else {
            registerReceiver(batteryReceiver, filter);
        }
    }

    private void startClock() {
        if (clockHandler != null) {
            return;
        }
        clockHandler = new Handler(Looper.getMainLooper());
        clockHandler.post(clockTick);
    }

    private void stopClock() {
        if (clockHandler != null) {
            clockHandler.removeCallbacks(clockTick);
            clockHandler = null;
        }
    }

    /**
     * The clock, rescheduled to the next minute boundary rather than polled.
     *
     * A minute display has nothing to do for the other fifty-nine and a half seconds, and this
     * runs on a phone sitting in a car cradle with no charger.
     */
    private final Runnable clockTick = new Runnable() {
        @Override
        public void run() {
            if (clockText != null) {
                Calendar now = Calendar.getInstance();
                clockText.setText(String.format(Locale.US, "%02d:%02d",
                        now.get(Calendar.HOUR_OF_DAY), now.get(Calendar.MINUTE)));
            }
            if (clockHandler != null) {
                long now = System.currentTimeMillis();
                clockHandler.postDelayed(this, 60000L - (now % 60000L) + 250L);
            }
        }
    };

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
                pill.setPadding(Ui.dp(this, Ui.S5), Ui.dp(this, Ui.S4),
                        Ui.dp(this, Ui.S5), Ui.dp(this, Ui.S4));
                // A minimum width keeps short labels like "RPM" a comfortable target. The
                // text is added plainly rather than with fillWidth(): a weight-1 child of a
                // wrap_content parent measures to zero, so the label would disappear.
                text.setMinWidth(Ui.dp(this, 56));
                pill.addView(text);
                item.addView(pill, new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.WRAP_CONTENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT));
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
                    ? new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT,
                    ViewGroup.LayoutParams.WRAP_CONTENT)
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
            railItems.get(i).setBackground(Ui.ripple(this, Ui.haze(palette.accent),
                    on ? palette.accentWash() : 0x00000000, 9f));
            if (!narrow) {
                railMarkers.get(i).setBackground(on
                        ? Ui.rounded(this, palette.accent, 2f) : null);
            }
        }
    }

    /**
     * Marks the current screen in the drawer.
     *
     * Deliberately the same three cues the rail uses: accent text, bold, and the accent wash.
     * A phone and a car showing the same app should not disagree about where you are.
     */
    private void updateDrawer() {
        if (drawerDestViews == null) {
            return;
        }
        for (int i = 0; i < drawerDestViews.length; i++) {
            TextView row = drawerDestViews[i];
            if (row == null) {
                continue;
            }
            boolean here = i == currentIndex;
            row.setTextColor(here ? palette.accent : palette.text);
            row.setTypeface(here ? Ui.bold() : null);
            // Wrapped in the ripple rather than a plain fill, because this is the one method
            // that runs after every navigation and would otherwise strip the press feedback.
            row.setBackground(Ui.ripple(this, Ui.haze(palette.accent),
                    here ? palette.accentWash() : 0x00000000, 9f));
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
        updateDrawer();
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

    /**
     * Which poll loop is the current one.
     *
     * onPause() cannot simply interrupt the thread and forget it: interrupt is cooperative,
     * so the old thread can still be inside a two second Bluetooth write when onResume()
     * starts the next loop. Bumping this makes the stale loop and any frames it had already
     * queued no-ops, which matters because both instances now share one PiClient.
     */
    private volatile int pollGen;

    private void startPolling() {
        if (poller != null) {
            return;
        }
        final int gen = ++pollGen;
        poller = new Thread(() -> {
            int tick = 0;
            while (alive && gen == pollGen) {
                if (pi.isConfigured()) {
                    try {
                        Telemetry t = Telemetry.from(pi.telemetry());
                        online = true;
                        handler.post(() -> {
                            if (!alive || gen != pollGen) {
                                return;
                            }
                            copyInto(t);
                            screen.bind(latest);
                            updateLink();
                        });
                        if (tick % STATUS_EVERY == 0) {
                            JSONObject status = pi.status();
                            handler.post(() -> {
                                if (!alive || gen != pollGen) {
                                    return;
                                }
                                applyStatus(status);
                                online = true;
                                updateLink();
                            });
                        }
                        if (tick % ROOF_EVERY == 0 && screen instanceof RoofScreen) {
                            JSONObject roof = pi.roofStatus();
                            handler.post(() -> {
                                if (!alive || gen != pollGen) {
                                    return;
                                }
                                ((RoofScreen) screen).applyRoof(roof);
                            });
                        }
                    } catch (Exception e) {
                        // Refresh even when the link has never been up. This used to be gated
                        // on a previous success, so a link that had never worked showed
                        // OFFLINE with an empty transport list and no reason anywhere on the
                        // screen, which reads as the app doing nothing at all.
                        String reason = e.getMessage() == null ? "" : e.getMessage();
                        if (online || !reason.equals(lastLinkReason)) {
                            online = false;
                            lastLinkReason = reason;
                            handler.post(() -> {
                                if (alive && gen == pollGen) {
                                    updateLink();
                                }
                            });
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

    /** Supersede the running poll loop and drop the reference to it. */
    private void stopPolling() {
        pollGen++;
        if (poller != null) {
            poller.interrupt();
            poller = null;
        }
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

    /** The last failure reason already rendered, so the poll loop does not redraw it. */
    private String lastLinkReason = "";

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
            footerLeft.setText(pi.isConfigured() ? linkSummary() : "No Pi set up, see System");
        }
        if (footerRight != null) {
            String state = !online ? "OFFLINE"
                    : latest.sleeping ? "PI ASLEEP"
                    : latest.demoMode ? "DEMO" : "LIVE";
            footerRight.setText(String.format(Locale.US, "%s  \u00b7  %d rpm", state, latest.rpm));
        }
        // The System screen lists the whole chain, and the link state is exactly when that
        // list changes, so it is refreshed from here rather than left to go stale.
        if (screen instanceof SystemScreen) {
            ((SystemScreen) screen).refreshTransport();
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

    /**
     * Back closes the drawer before it leaves the app.
     *
     * A dropdown that swallows back would exit the app with it still on screen, which reads
     * as a crash rather than a dismissal.
     */
    @Override
    @SuppressWarnings("deprecation")
    public void onBackPressed() {
        if (drawerHost != null && drawerHost.getVisibility() == View.VISIBLE) {
            closeDrawer();
            return;
        }
        super.onBackPressed();
    }

    /**
     * Ask for Nearby devices on Android 12 and later.
     *
     * Asked once, not nagged: the transports already report "needs the Nearby devices
     * permission" as their reason, and refusing is a legitimate choice for someone who
     * only ever uses the cable. The System screen shows the state either way.
     */
    private void requestBluetoothPermission() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S) {
            return;         // install-time permission before Android 12
        }
        if (checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT)
                == PackageManager.PERMISSION_GRANTED) {
            return;
        }
        requestPermissions(new String[]{Manifest.permission.BLUETOOTH_CONNECT}, REQ_BLUETOOTH);
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions,
                                          int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != REQ_BLUETOOTH) {
            return;
        }
        // Rebuild the chain either way: the transports cache their readiness, so a grant
        // would otherwise not take effect until the next launch.
        pi.setBluetooth(this, btDevices, prefs.getString("token", ""));
        updateLink();
    }

    /**
     * What the footer says the link is, so which transport is carrying it is never a
     * mystery. The address is meaningless once the tether is out, so say the profile then.
     */
    private String linkSummary() {
        String via = pi.activeTransport();
        if (via.isEmpty()) {
            return pi.baseUrl().isEmpty() ? "Bluetooth" : pi.baseUrl();
        }
        if ("USB tether".equals(via)) {
            return pi.baseUrl();
        }
        return via;
    }

    @Override
    protected void onResume() {
        super.onResume();
        Log.i(TAG, "resume " + describeThis());
        startPolling();
        refreshNow();
    }

    @Override
    protected void onPause() {
        super.onPause();
        Log.i(TAG, "pause " + describeThis());
        // Stop the poll loop while hidden: a backgrounded app holding a 4Hz poll
        // open on the tether just drains the phone.
        stopPolling();
    }

    @Override
    protected void onDestroy() {
        Log.i(TAG, "destroy " + describeThis() + " finishing=" + isFinishing());
        alive = false;
        stopPolling();
        stopClock();
        if (batteryReceiver != null) {
            unregisterReceiver(batteryReceiver);
            batteryReceiver = null;
        }
        // Release any Bluetooth socket rather than leaving it to the process teardown: an
        // RFCOMM connection left open keeps the Pi's listener occupied. Refcounted, because
        // the car screen and the phone can both have an instance and only the last one may
        // take the link down.
        if (pi != null) {
            PiLink.release(pi);
        }
        super.onDestroy();
    }

    /**
     * Which instance and which display this is, for the lifecycle log.
     *
     * The Android Auto loop was invisible in logcat because the app logged no lifecycle at
     * all, so "the app closed" had no trace anywhere. These lines make the next one
     * readable from a laptop: two different hashes or task ids on one launch means the
     * car screen and the phone are running separate instances, which is now expected, and
     * a rapid alternation of them would mean something is still recreating the activity.
     */
    private String describeThis() {
        // getWindowManager().getDefaultDisplay() rather than Activity#getDisplay(): the
        // latter is API 30 and this app still supports 26.
        android.view.Display d = getWindowManager().getDefaultDisplay();
        int display = d == null ? -1 : d.getDisplayId();
        return Integer.toHexString(System.identityHashCode(this))
                + " display=" + display
                + " task=" + getTaskId();
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
