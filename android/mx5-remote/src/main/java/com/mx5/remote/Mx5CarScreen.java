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
 * moves. A DRIVING-category session is allowed to stay up, but only through host-rendered
 * templates: the app supplies text, the host decides the layout, the font sizes and how
 * much may be shown at once. That is deliberate - it is what keeps the screen glanceable
 * instead of turning the head unit into a second instrument cluster.
 *
 * Four values, one pane. Anything that needs more than a glance belongs on the parked
 * screen, where the driver is stopped.
 */
public class Mx5CarScreen extends Screen {

    private static final String PREFS = "mx5";
    private static final String DEFAULT_ADDRESS = "192.168.42.100:5000";
    private static final long POLL_MS = 1000;

    private final PiClient pi;
    private final Handler handler = new Handler(Looper.getMainLooper());

    /** Last successful reading, or null before the first one arrives. */
    private volatile Telemetry latest;

    /** True while a fetch is in flight, so a slow link cannot pile up requests. */
    private boolean fetching;

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
        pi = PiLink.acquire();
        pi.configure(prefs.getString("address", DEFAULT_ADDRESS), prefs.getString("token", ""));

        // Screen has no onDestroy() of its own in 1.4.0; its lifecycle is the hook.
        // Polling only runs while the screen is visible, and the shared client is
        // released when the host is finished with this screen.
        getLifecycle().addObserver((LifecycleEventObserver) (source, event) -> {
            if (event == Lifecycle.Event.ON_START) {
                handler.removeCallbacks(poll);
                handler.post(poll);
            } else if (event == Lifecycle.Event.ON_STOP) {
                handler.removeCallbacks(poll);
            } else if (event == Lifecycle.Event.ON_DESTROY) {
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
            if (fetched != null) {
                latest = fetched;
                handler.post(Mx5CarScreen.this::invalidate);
            }
        }, "car-poll").start();
    }

    @NonNull
    @Override
    public Template onGetTemplate() {
        Telemetry t = latest;

        Pane pane = new Pane.Builder()
                .addRow(row("Speed", t == null ? "--" : Math.round(t.speedFor(1)) + " mph"))
                .addRow(row("Gear", t == null ? "--" : gearText(t)))
                .addRow(row("RPM", t == null ? "--" : String.valueOf(t.rpm)))
                .addRow(row("Fuel", t == null ? "--" : Math.round(t.fuelLevelPercent) + "%"))
                .build();

        return new PaneTemplate.Builder(pane)
                .setTitle("MX5")
                .setHeaderAction(Action.APP_ICON)
                .build();
    }

    private static Row row(String label, String value) {
        return new Row.Builder()
                .setTitle(label)
                .addText(value)
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
