package com.mx5.remote;

/**
 * The one PiClient for the whole process.
 *
 * Android Auto launches the parked activity with FLAG_ACTIVITY_NEW_TASK |
 * FLAG_ACTIVITY_MULTIPLE_TASK | FLAG_ACTIVITY_CLEAR_TASK, so the car screen gets a second
 * MainActivity instance in a task of its own while the phone keeps the first. Two
 * PiClients would mean two GATT connections to a peripheral that only tolerates one, and
 * each instance's onDestroy() would close the link the other was still using.
 *
 * Sharing one client makes "synchronized request()" serialize both instances, and makes
 * the teardown refcounted: the link is only closed when the last instance goes away.
 *
 * The reference is deliberately not a leak: release() drops it as soon as the count hits
 * zero, so nothing outlives the process' last activity.
 */
public final class PiLink {

    private static PiClient shared;
    private static int live;

    private PiLink() {
    }

    /** Take a reference to the shared client, creating it if this is the first caller. */
    public static synchronized PiClient acquire() {
        if (shared == null) {
            shared = new PiClient();
        }
        live++;
        return shared;
    }

    /**
     * Give a reference back, closing the link on the last one.
     *
     * The client is compared by identity so a reference held by an activity that was
     * destroyed before a later acquire cannot decrement the count twice, or close a link
     * it no longer owns.
     */
    public static void release(PiClient client) {
        boolean last;
        synchronized (PiLink.class) {
            if (client != shared) {
                return;
            }
            live--;
            last = live <= 0;
            if (last) {
                live = 0;
                shared = null;
            }
        }
        if (last) {
            try {
                // Outside the lock: closing a GATT client can block, and a new instance
                // must not be made to wait for it.
                client.close();
            } catch (Exception ignored) {
                // Nothing useful to do while shutting down.
            }
        }
    }
}
