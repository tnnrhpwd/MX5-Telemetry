package com.mx5.remote;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Handler;
import android.os.Looper;

import androidx.annotation.NonNull;
import androidx.car.app.CarContext;
import androidx.car.app.Screen;
import androidx.car.app.model.Action;
import androidx.car.app.model.Pane;
import androidx.car.app.model.PaneTemplate;
import androidx.car.app.model.Row;
import androidx.car.app.model.Template;
import androidx.lifecycle.Lifecycle;
import androidx.lifecycle.LifecycleEventObserver;

/**
 * The in-motion view.
 *
 * This exists because a parked "game" app is hidden by Android Auto as soon as the car
 * moves. A templated session is allowed to stay up, but only through host-rendered
 * templates: the app supplies text, the host decides the layout, the font sizes and how
 * much may be shown at once. That is deliberate - it is what keeps the screen glanceable
 * instead of turning the head unit into a second instrument cluster.
 *
 * The content mirrors the Android app's Overview page, minus the things that need
 * looking at rather than glancing at (the shift ladder, the fuel bar). Values come first
 * and labels second because the host draws the row title large: at a red light the eye
 * should land on "42 mph", not on the word "Speed".
 *
 * Six rows, in the order a driver would want them, and no more. A `Pane` scrolls when it
 * does not fit, and on this head unit it does not: the projected display is 919x480 at
 * 209dpi, which is 367dp tall, and a pane row plus the template header leaves room for
 * about six. Battery volts and average MPG fitted at 800x480 in the mock and would sit
 * below the fold in the car, where reaching them needs a scroll - which is exactly what a
 * driving surface must not ask for. They stay on the parked dashboard.
 */
public class Mx5CarScreen extends Screen {

    private static final String PREFS = "mx5";
    private static final String DEFAULT_ADDRESS = "192.168.42.100:5000";
    private static final long POLL_MS = 1000;

    private final PiClient pi;
    private final SharedPreferences prefs;
    private final Handler handler = new Handler(Looper.getMainLooper());

    /** Last successful reading, or null before the first one arrives. */
    private volatile Telemetry latest;

    /** True while a fetch is in flight, so a slow link cannot pile up requests.
     *  Volatile: written by the worker thread and read by the main-thread poll, and a
     *  stale `true` here would stop polling for the rest of the session. */
    private volatile boolean fetching;

    /** Set when the host is done with this screen. See fetchOnce(): a reply that lands
     *  after teardown must not ask a destroyed screen to redraw. */
    private volatile boolean destroyed;

    private final Runnable poll = new Runnable() {
        @Override
        public void run() {
            fetchOnce();
            handler.postDelayed(this, POLL_MS);
        }
    };

    public Mx5CarScreen(@NonNull CarContext context) {
        super(context);

        SharedPreferences prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        this.prefs = prefs;
        pi = PiLink.acquire();
        // Only configure the shared client when nobody has yet. configure() rebuilds the
        // transport chain, and the parked dashboard may be mid-request on the same client.
        if (!pi.isConfigured()) {
            pi.configure(prefs.getString("address", DEFAULT_ADDRESS),
                    prefs.getString("token", ""));
        }

        // Build the Bluetooth half of the chain here too.
        //
        // This is the in-motion app, and it is a separate package with its own process:
        // the phone activity in *this* package is the only other thing that ever set the
        // link up. So car sessions started from the head unit alone - which is the normal
        // way to use this one - had a chain of exactly one transport, HTTP over the USB
        // tether, and showed "--" for everything the moment the cable was out. That is the
        // one situation this app exists for.
        //
        // Constructing the transports needs no permission: they report "Needs the Nearby
        // devices permission" until it is granted, and a car Screen cannot ask for it. The
        // phone activity in this package does ask, so opening MX5 Drive once on the phone
        // is what enables Bluetooth here.
        if (!pi.bluetoothConfigured()) {
            pi.setBluetooth(context, BtDevices.source(context, prefs),
                    prefs.getString("token", ""));
            pi.preferTransport(prefs.getString(MainActivity.KEY_LAST_TRANSPORT, ""));
        }

        // Screen has no onDestroy() of its own in 1.4.0; its lifecycle is the hook.
        // Polling only runs while the screen is visible, and the shared client is
        // released when the host is finished with this screen.
        getLifecycle().addObserver((LifecycleEventObserver) (source, event) -> {
            if (event == Lifecycle.Event.ON_START) {
                // A car session can start long after the last attempt failed, so the
                // reason for backing off no longer holds. Keeps the sticky transport.
                pi.clearBackoff();
                handler.removeCallbacks(poll);
                handler.post(poll);
            } else if (event == Lifecycle.Event.ON_STOP) {
                handler.removeCallbacks(poll);
            } else if (event == Lifecycle.Event.ON_DESTROY) {
                destroyed = true;
                handler.removeCallbacksAndMessages(null);
                PiLink.release(pi);
            }
        });
    }

    private void fetchOnce() {
        if (fetching || !pi.isConfigured()) {
            return;
        }
        fetching = true;
        new Thread(() -> {
            Telemetry fetched = null;
            try {
                fetched = Telemetry.from(pi.telemetry());
            } catch (Exception ignored) {
                // Offline: keep the previous reading rather than blanking the screen.
            } finally {
                fetching = false;
            }
            if (fetched != null && !destroyed) {
                latest = fetched;
                handler.post(Mx5CarScreen.this::invalidate);
            }
        }, "car-poll").start();
    }

    @NonNull
    @Override
    public Template onGetTemplate() {
        Telemetry t = latest;
        // Re-read every time rather than caching at session start: the units toggle
        // lives on the phone, and a stale copy here would show mph until the car
        // session is restarted. SharedPreferences reads are served from memory.
        boolean mph = prefs.getBoolean("use_mph", true);
        String unit = mph ? "mph" : "km/h";

        Pane pane = new Pane.Builder()
                .addRow(row(value(t == null ? null : t.speedForDisplay(mph) + " " + unit),
                           "Speed"))
                .addRow(row(value(t == null ? null : String.valueOf(t.rpm)), "RPM"))
                .addRow(row(value(t == null ? null : gearText(t)), "Gear"))
                .addRow(row(value(t == null ? null : t.coolantTempF + " \u00b0F"), "Coolant"))
                .addRow(row(value(t == null ? null : Math.round(t.fuelLevelPercent) + "%"), "Fuel"))
                .addRow(row(value(t == null ? null : t.rangeMiles + " mi"), "Range"))
                // Until the first reading arrives the host shows its own progress indicator
                // rather than six rows of "--", which is indistinguishable from a link that
                // will never work.
                .setLoading(t == null)
                .build();

        return new PaneTemplate.Builder(pane)
                .setTitle("MX5")
                .setHeaderAction(Action.APP_ICON)
                .build();
    }

    private static String value(String v) {
        return v == null ? "--" : v;
    }

    /** Value first, label second: the host draws the title large. */
    private static Row row(String value, String label) {
        return new Row.Builder()
                .setTitle(value)
                .addText(label)
                .build();
    }

    private static String gearText(Telemetry t) {
        if (t.inNeutral) {
            return "N";
        }
        if (t.inReverse) {
            return "R";
        }
        return t.gear <= 0 ? "--" : String.valueOf(t.gear);
    }
}
