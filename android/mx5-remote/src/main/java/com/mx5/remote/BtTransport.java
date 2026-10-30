package com.mx5.remote;

import org.json.JSONException;
import org.json.JSONObject;

import android.bluetooth.BluetoothDevice;
import android.util.Log;

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
 * The protocol is one JSON object per line, newline terminated. Requests are serialized
 * behind a lock because a Bluetooth link is a single byte stream and there is no room for
 * two requests in flight.
 */
abstract class BtTransport implements LinkTransport {

    private static final long REPLY_TIMEOUT_MS = 3000;

    /**
     * How long a roof command may take to answer.
     *
     * Those ops open the RCNC-2's serial port, wait 0.35s for it to settle, and then wait
     * up to 2s for a reply, and `roof.connect` may do more than one exchange. Timing one
     * out at the ordinary deadline did more than fail the command: the transport counted
     * as broken, was demoted, and the whole chain was walked again mid-command.
     */
    private static final long ROOF_REPLY_TIMEOUT_MS = 8000;

    /**
     * Stray lines tolerated while waiting for our own reply.
     *
     * Generous on purpose. Over BLE the Pi notifies *every* subscribed central, so a
     * second app on the same phone (the parked dashboard and the in-motion one are
     * separate packages) sees this app's replies as lines that are not ours: about four a
     * second at its own poll rate. The old value of eight meant such a client could burn
     * its allowance and time out on a link that was working perfectly, reconnect, and do
     * it again. The deadline is what bounds the wait now; this only stops a pathological
     * stream from spinning.
     */
    private static final int MAX_SKIPPED_LINES = 128;

    private static final String TAG = "MX5Link";

    protected final String token;

    private final Object ioLock = new Object();
    private int nextId = 1;
    private boolean authenticated;

    /**
     * When the Pi last refused the token.
     *
     * A wrong token is not a reason to walk the chain - none of the transports will be
     * accepted - but it *was* a reason to reconnect several times a second, because every
     * poll opened a fresh RFCOMM socket or GATT client and asked again. That is exactly
     * the hammering that leaves Android's Bluetooth stack refusing connections, so a
     * refusal pauses this transport instead. The pause is cleared by a successful hello
     * and by rebuilding the transports, which is what changing the token does.
     */
    private long authRefusedAt;

    private static final long AUTH_REFUSAL_PAUSE_MS = 10000;

    // Complete lines received, handed over by whichever profile is carrying the link.
    // A queue rather than a plain buffer so receiveLine can honour a real timeout: an
    // RFCOMM read() and a GATT callback both block or arrive whenever they like, and
    // neither can be given a deadline directly.
    private final LinkedBlockingQueue<String> lines = new LinkedBlockingQueue<>();

    // Bytes that have arrived without a newline yet.
    //
    // Bytes, not a String. Decoding each chunk separately corrupted any character whose
    // UTF-8 encoding straddled the boundary, and over BLE the boundary is every 20 bytes
    // when the MTU is at its floor: a reply containing a degree sign or an accented
    // character in an error message came back with a replacement character in it and was
    // then dropped as malformed. Splitting on the newline first and decoding the finished
    // line is the only version that cannot do that.
    private final java.io.ByteArrayOutputStream lineBytes = new java.io.ByteArrayOutputStream();

    /** Ceiling on a line with no newline in it, so a desynced peer cannot grow it. */
    private static final int MAX_LINE_BYTES = 65536;

    /**
     * Ceiling on complete lines waiting to be read.
     *
     * One request consumes its own reply, so the queue is empty at rest. A peer that
     * talks faster than we ask - or a second app whose notifications BlueZ broadcasts to
     * us as well - must not be able to make this grow without bound.
     */
    private static final int MAX_QUEUED_LINES = 32;

    /** Where the last newline search stopped, so a growing buffer is not rescanned. */
    private int scanned;

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
        synchronized (lineBytes) {
            lineBytes.write(data, 0, data.length);
            if (lineBytes.size() > MAX_LINE_BYTES) {
                Log.w(TAG, "dropping " + lineBytes.size() + " bytes with no newline in them");
                lineBytes.reset();
                scanned = 0;
                return;
            }

            byte[] buf = lineBytes.toByteArray();
            int start = 0;
            for (int i = scanned; i < buf.length; i++) {
                if (buf[i] != '\n') {
                    continue;
                }
                String line = new String(buf, start, i - start, StandardCharsets.UTF_8).trim();
                start = i + 1;
                if (!line.isEmpty()) {
                    lines.offer(line);
                    while (lines.size() > MAX_QUEUED_LINES) {
                        lines.poll();       // drop the oldest; it is already stale
                    }
                }
            }
            scanned = buf.length;

            // Keep only the unfinished tail: everything before `start` has been consumed.
            if (start > 0) {
                lineBytes.reset();
                lineBytes.write(buf, start, buf.length - start);
                scanned -= start;
            }
        }
    }

    /** Forget any half-received line and anything queued, for a fresh connection. */
    protected final void clearReceived() {
        synchronized (lineBytes) {
            lineBytes.reset();
            scanned = 0;
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
            long timeout = timeoutFor(path);

            // One retry, used only when the Pi says the session is not authenticated.
            for (int attempt = 0; ; attempt++) {
                ensureAuthenticated();

                int id = nextId++;
                JSONObject req;
                try {
                    req = buildRequest(id, path, body);
                } catch (JSONException e) {
                    throw new IOException("Bad request for " + path + ": " + e.getMessage(), e);
                }

                JSONObject reply = exchange(id, req, path, timeout);

                if (reply.optBoolean("ok", false)) {
                    JSONObject data = reply.optJSONObject("data");
                    return data == null ? "{}" : data.toString();
                }

                String error = reply.optString("error", "Refused by the Pi");
                if (attempt == 0 && isAuthFailure(error)) {
                    // The Pi dropped the session but the phone never saw the link go: a
                    // BLE central that reconnected without BlueZ reporting the disconnect,
                    // or a display app that was restarted underneath us. Logging in again
                    // is both safe and invisible; reporting it as a refusal is neither,
                    // because there is nothing the driver could do about it.
                    Log.d(TAG, "the Pi did not recognise the session, authenticating again");
                    authenticated = false;
                    closePipe();
                    continue;
                }
                throw new LinkTransport.Refused(error);
            }
        }
    }

    /**
     * Send one request and return the reply that carries its id.
     *
     * The deadline covers the whole wait, not each line. It used to be applied per line,
     * so a peer that kept sending lines that were not ours - a second client on the same
     * session, or a half-received reply after a reconnect - could hold this thread for
     * eight times the reply timeout before giving up.
     */
    private JSONObject exchange(int id, JSONObject req, String path, long timeout)
            throws IOException {
        try {
            send((req.toString() + "\n").getBytes(StandardCharsets.UTF_8));
        } catch (IOException e) {
            // The write itself failed, so the connection is gone.
            closePipe();
            authenticated = false;
            throw e;
        }

        long deadline = System.currentTimeMillis() + timeout;
        for (int i = 0; i <= MAX_SKIPPED_LINES; i++) {
            long remaining = deadline - System.currentTimeMillis();
            if (remaining <= 0) {
                break;
            }
            String line = receiveLine(remaining);
            JSONObject reply;
            try {
                reply = new JSONObject(line);
            } catch (JSONException e) {
                continue;               // not JSON at all: skip and keep waiting
            }
            if (reply.optInt("id", -1) != id) {
                continue;               // a reply to something else
            }
            return reply;
        }

        // A timeout here is ambiguous: the peer may be gone or merely slow. Drop the
        // connection so the next attempt starts clean.
        closePipe();
        authenticated = false;
        throw new IOException("No reply from the Pi for " + path);
    }

    /** The reply wait for one path. Roof commands are allowed longer; see the constant. */
    private static long timeoutFor(String path) {
        return path != null && path.startsWith("/api/roof/")
                ? ROOF_REPLY_TIMEOUT_MS
                : REPLY_TIMEOUT_MS;
    }

    /** Whether the Pi's error means "this session is not logged in". */
    private static boolean isAuthFailure(String error) {
        return error != null && error.toLowerCase(java.util.Locale.US).contains("authenticat");
    }

    // -- session ------------------------------------------------------------

    private void ensureAuthenticated() throws IOException {
        long since = System.currentTimeMillis() - authRefusedAt;
        if (authRefusedAt != 0 && since < AUTH_REFUSAL_PAUSE_MS) {
            throw new LinkTransport.Refused(
                    "The Pi refused the token " + (since / 1000) + "s ago");
        }
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
     * profile rather than authorized for this application's commands, and the Pi may have
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

        long deadline = System.currentTimeMillis() + REPLY_TIMEOUT_MS;
        for (int i = 0; i <= MAX_SKIPPED_LINES; i++) {
            long remaining = deadline - System.currentTimeMillis();
            if (remaining <= 0) {
                break;
            }
            JSONObject reply;
            try {
                reply = new JSONObject(receiveLine(remaining));
            } catch (JSONException e) {
                continue;
            }
            if (reply.optInt("id", -1) != id) {
                continue;
            }
            if (!reply.optBoolean("ok", false)) {
                // A bad token is not a reason to try the other profile with the same token.
                closePipe();
                authRefusedAt = System.currentTimeMillis();
                throw new LinkTransport.Refused(
                        reply.optString("error", "Link refused the token"));
            }
            authenticated = true;
            authRefusedAt = 0;
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
        } else if ("/api/roof/connect".equals(path)) {
            req.put("op", "roof.connect");
        } else if ("/api/roof/disconnect".equals(path)) {
            req.put("op", "roof.disconnect");
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
