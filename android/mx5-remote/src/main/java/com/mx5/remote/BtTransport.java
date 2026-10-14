package com.mx5.remote;

import org.json.JSONException;
import org.json.JSONObject;

import android.bluetooth.BluetoothDevice;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;

/**
 * Shared logic for the two Bluetooth transports.
 *
 * Framing, authentication, request/reply correlation and the mapping from HTTP-shaped
 * paths to protocol ops all live here, so the subclasses only move bytes. That mirrors the
 * split on the Pi side, and it is what makes the two profiles interchangeable rather than
 * two separate implementations of the same thing.
 *
 * The protocol is one JSON object per line, newline terminated. Requests are serialised
 * behind a lock because a Bluetooth link is a single byte stream and there is no room for
 * two requests in flight.
 */
abstract class BtTransport implements LinkTransport {

    private static final long REPLY_TIMEOUT_MS = 3000;

    /** Stray lines tolerated while waiting for our own reply. */
    private static final int MAX_SKIPPED_LINES = 8;

    protected final String token;

    private final Object ioLock = new Object();
    private int nextId = 1;
    private boolean authenticated;

    // Complete lines received, handed over by whichever profile is carrying the link.
    // A queue rather than a plain buffer so receiveLine can honour a real timeout: an
    // RFCOMM read() and a GATT callback both block or arrive whenever they like, and
    // neither can be given a deadline directly.
    private final LinkedBlockingQueue<String> lines = new LinkedBlockingQueue<>();
    private final StringBuilder lineAccumulator = new StringBuilder();

    BtTransport(String token) {
        this.token = token == null ? "" : token.trim();
    }

    /**
     * Supplies the device to connect to, and says why there is not one.
     *
     * Injected rather than read from preferences so the transports stay unaware of how the
     * app stores its settings, and so the "why not" message can be built where the
     * Bluetooth state is actually visible.
     */
    interface DeviceSource {
        BluetoothDevice device();

        String reason();
    }

    // -- the byte pipe, implemented by the subclasses -----------------------

    /** Connect, and do whatever this profile needs before bytes can flow. */
    protected abstract void open() throws IOException;

    /** Write bytes, in order, completely. */
    protected abstract void send(byte[] data) throws IOException;

    /** Whether the pipe is currently usable. */
    protected abstract boolean isOpen();

    /** Drop the connection. Must not throw. */
    protected abstract void closePipe();

    // -- receiving ----------------------------------------------------------

    /**
     * Hand received bytes to the session. Subclasses call this from wherever their bytes
     * arrive: an RFCOMM reads on a reader thread, a GATT notification from its callback.
     * Anything after the last newline is held until the rest of that line turns up, which
     * is what lets a reply be split across BLE notifications.
     */
    protected final void feed(byte[] data) {
        if (data == null || data.length == 0) {
            return;
        }
        synchronized (lineAccumulator) {
            lineAccumulator.append(new String(data, StandardCharsets.UTF_8));
            int nl;
            while ((nl = lineAccumulator.indexOf("\n")) >= 0) {
                String line = lineAccumulator.substring(0, nl).trim();
                lineAccumulator.delete(0, nl + 1);
                if (!line.isEmpty()) {
                    lines.offer(line);
                }
            }
        }
    }

    /** Forget any half-received line and anything queued, for a fresh connection. */
    protected final void clearReceived() {
        synchronized (lineAccumulator) {
            lineAccumulator.setLength(0);
            lines.clear();
        }
    }

    private String receiveLine(long timeoutMs) throws IOException {
        String line;
        try {
            line = lines.poll(timeoutMs, TimeUnit.MILLISECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IOException("Interrupted while waiting for the Pi", e);
        }
        if (line == null) {
            throw new IOException("Timed out waiting for a reply from the Pi");
        }
        return line;
    }

    // -- LinkTransport ------------------------------------------------------

    @Override
    public void onFailure() {
        synchronized (ioLock) {
            // A failed exchange leaves the connection in an unknown state and the id
            // sequence possibly out of step with the Pi, so start over rather than guess.
            closePipe();
            authenticated = false;
        }
    }

    @Override
    public void close() {
        synchronized (ioLock) {
            closePipe();
            authenticated = false;
        }
    }

    @Override
    public String request(String method, String path, String body) throws IOException {
        synchronized (ioLock) {
            ensureAuthenticated();

            int id = nextId++;
            JSONObject req;
            try {
                req = buildRequest(id, path, body);
            } catch (JSONException e) {
                throw new IOException("Bad request for " + path + ": " + e.getMessage(), e);
            }

            try {
                send((req.toString() + "\n").getBytes(StandardCharsets.UTF_8));
            } catch (IOException e) {
                // The write itself failed, so the connection is gone.
                closePipe();
                authenticated = false;
                throw e;
            }

            for (int i = 0; i <= MAX_SKIPPED_LINES; i++) {
                String line = receiveLine(REPLY_TIMEOUT_MS);
                JSONObject reply;
                try {
                    reply = new JSONObject(line);
                } catch (JSONException e) {
                    continue;               // not JSON at all: skip and keep waiting
                }
                if (reply.optInt("id", -1) != id) {
                    continue;               // a reply to something else
                }
                if (!reply.optBoolean("ok", false)) {
                    throw new LinkTransport.Refused(
                            reply.optString("error", "Refused by the Pi"));
                }
                JSONObject data = reply.optJSONObject("data");
                return data == null ? "{}" : data.toString();
            }
            // A timeout here is ambiguous: the peer may be gone or merely slow. Drop the
            // connection so the next attempt starts clean.
            closePipe();
            authenticated = false;
            throw new IOException("No reply from the Pi for " + path);
        }
    }

    // -- session ------------------------------------------------------------

    private void ensureAuthenticated() throws IOException {
        if (isOpen() && authenticated) {
            return;
        }
        if (!isOpen()) {
            open();
        }
        authenticate();
    }

    /**
     * Send hello and check the answer.
     *
     * Pairing is not treated as the security boundary: it makes a device trusted for the
     * profile rather than authorised for this application's commands, and the Pi may have
     * other paired devices. The token is the same one the HTTP API uses.
     */
    private void authenticate() throws IOException {
        int id = nextId++;
        JSONObject hello = new JSONObject();
        try {
            hello.put("id", id);
            hello.put("op", "hello");
            hello.put("token", token);
        } catch (JSONException e) {
            throw new IOException("Could not build hello: " + e.getMessage(), e);
        }

        send((hello.toString() + "\n").getBytes(StandardCharsets.UTF_8));

        for (int i = 0; i <= MAX_SKIPPED_LINES; i++) {
            JSONObject reply;
            try {
                reply = new JSONObject(receiveLine(REPLY_TIMEOUT_MS));
            } catch (JSONException e) {
                continue;
            }
            if (reply.optInt("id", -1) != id) {
                continue;
            }
            if (!reply.optBoolean("ok", false)) {
                // A bad token is not a reason to try the other profile with the same token.
                closePipe();
                throw new LinkTransport.Refused(
                        reply.optString("error", "Link refused the token"));
            }
            authenticated = true;
            return;
        }
        closePipe();
        throw new IOException("No answer to hello");
    }

    // -- path to op ---------------------------------------------------------

    /**
     * Translate one HTTP-shaped request into a protocol op.
     *
     * The screens express requests as paths because that is what the tether speaks, so the
     * translation lives here rather than being pushed up into every caller. An unknown
     * path is an error rather than a silent no-op.
     */
    private static JSONObject buildRequest(int id, String path, String body)
            throws JSONException, IOException {
        JSONObject req = new JSONObject();
        req.put("id", id);

        if ("/api/status".equals(path)) {
            req.put("op", "status");
        } else if ("/api/telemetry".equals(path)) {
            req.put("op", "telemetry");
        } else if ("/api/roof/status".equals(path)) {
            req.put("op", "roof.status");
        } else if ("/api/screen/next".equals(path)) {
            req.put("op", "screen.next");
        } else if ("/api/screen/prev".equals(path)) {
            req.put("op", "screen.prev");
        } else if (path.startsWith("/api/screen/")) {
            req.put("op", "screen");
            req.put("value", Integer.parseInt(path.substring("/api/screen/".length())));
        } else if ("/api/settings/update".equals(path)) {
            JSONObject b = new JSONObject(body == null ? "{}" : body);
            req.put("op", "setting");
            req.put("name", b.optString("name"));
            req.put("value", b.opt("value"));
        } else if ("/api/roof/speed".equals(path)) {
            req.put("op", "roof.speed");
            req.put("value", valueOf(body));
        } else if ("/api/roof/auto".equals(path)) {
            req.put("op", "roof.auto");
            req.put("value", valueOf(body));
        } else if ("/api/roof/mode".equals(path)) {
            req.put("op", "roof.mode");
            req.put("value", valueOf(body));
        } else if ("/api/calibrate_imu".equals(path)) {
            req.put("op", "calibrate_imu");
        } else if ("/api/wake".equals(path)) {
            req.put("op", "wake");
        } else {
            throw new IOException("No Bluetooth op for " + path);
        }
        return req;
    }

    /** The single "value" field those requests carry. */
    private static Object valueOf(String body) throws JSONException {
        JSONObject b = new JSONObject(body == null ? "{}" : body);
        return b.opt("value");
    }
}
