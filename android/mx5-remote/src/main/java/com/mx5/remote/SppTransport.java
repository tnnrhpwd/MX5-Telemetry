package com.mx5.remote;

import android.bluetooth.BluetoothSocket;
import android.util.Log;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.UUID;

/**
 * Classic Bluetooth SPP: a plain RFCOMM socket.
 *
 * The cheapest of the three transports, because a reply is one write and needs no framing
 * beyond the newline the protocol already uses. It is only available if the Pi published
 * an SDP record for the SPP UUID, since createRfcommSocketToServiceRecord performs an SDP
 * lookup and fails outright if there is no record to find.
 *
 * Reads happen on a reader thread, because a BluetoothSocket cannot be given a read
 * timeout. The thread pushes complete lines into the shared queue, which is what turns a
 * blocking read into the deadline receiveLine actually needs.
 */
final class SppTransport extends BtTransport {

    /** The Serial Port Profile UUID. Android's own SPP constant is this exact value. */
    static final UUID SPP_UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB");

    /**
     * How long the whole create-and-connect may take.
     *
     * Neither createRfcommSocketToServiceRecord (which performs an SDP lookup) nor
     * connect() has a timeout, and both are allowed to take tens of seconds when the
     * peer is powered off or out of range: the RFCOMM page timeout alone is around
     * fifteen. That time was spent on the poll thread, holding PiClient's request lock,
     * so one attempt at a Pi that was not there yet stalled the whole app and looked
     * exactly like a link that needed the app reopened.
     */
    private static final long CONNECT_TIMEOUT_MS = 6000;

    /**
     * How long one request line may take to be written.
     *
     * A BluetoothSocket write blocks until the peer's flow control accepts the bytes, and
     * there is no write timeout to set. A phone whose link died mid-write otherwise sat
     * there for ever with the request lock held, so nothing could recover it.
     */
    private static final long WRITE_TIMEOUT_MS = 2500;

    private final DeviceSource devices;

    private BluetoothSocket socket;
    private InputStream in;
    private OutputStream out;
    private Thread reader;

    /**
     * Whether the insecure socket variant is the one that works with this Pi.
     *
     * Learned once per device. The secure socket resolves the service through SDP and
     * authenticates the link, which is the right default, but a Pi that has been
     * rebooted, had bluetoothd restarted or been re-paired routinely leaves that cached
     * record stale. Retrying the secure path first on every reconnect meant paying a
     * failed SDP lookup, and the extra delay, on every single reconnect for the rest of
     * the session. Nothing is unprotected by the insecure path: the token in `hello` is
     * the real gate.
     */
    private boolean preferInsecure;
    private String learnedFor = "";

    /** A connect that hit the deadline, as opposed to one that failed outright. */
    private static final class Timeout extends IOException {
        Timeout(String message) {
            super(message);
        }
    }

    SppTransport(String token, DeviceSource devices) {
        super(token);
        this.devices = devices;
    }

    @Override
    public String label() {
        return "Bluetooth SPP";
    }

    @Override
    public boolean isReady() {
        return devices.device() != null;
    }

    @Override
    public String unavailableReason() {
        return devices.reason();
    }

    @Override
    protected boolean isOpen() {
        if (socket == null || !socket.isConnected()) {
            return false;
        }
        // isConnected() only reports that connect() once succeeded; it stays true after the
        // Pi drops the link. The reader thread is what actually notices, because its read()
        // returns -1 when the peer closes, so a dead reader means a dead socket. Without
        // this the transport kept reporting itself healthy and every request paid the full
        // three second reply timeout before anything reconnected.
        Thread r = reader;
        return r == null || r.isAlive();
    }

    @Override
    protected void open() throws IOException {
        android.bluetooth.BluetoothDevice device = devices.device();
        if (device == null) {
            throw new IOException(devices.reason());
        }

        // The learned preference belongs to one device: a different Pi may be the one that
        // publishes a clean SDP record, so start it at the secure path again.
        String address = BtDevices.address(device);
        if (!address.equals(learnedFor)) {
            learnedFor = address;
            preferInsecure = false;
        }

        BluetoothSocket s = connect(device);

        socket = s;
        in = s.getInputStream();
        out = s.getOutputStream();
        clearReceived();
        startReader(in);
    }

    /**
     * Create and connect a socket, secure first and insecure if that fails.
     *
     * Only a failure is retried insecurely. A connect that ran out of time is not an SDP
     * problem: it means the Pi is off, asleep or out of range, and trying again over the
     * other variant would double the wait to prove the same thing.
     */
    private BluetoothSocket connect(android.bluetooth.BluetoothDevice device) throws IOException {
        if (preferInsecure) {
            return connectWithin(device, false);
        }
        try {
            return connectWithin(device, true);
        } catch (Timeout e) {
            throw e;
        } catch (IOException secureFailure) {
            // createRfcommSocketToServiceRecord does an SDP lookup on the Pi and needs the
            // cached record to still be right...
            Log.d("MX5Link", "secure SPP connect failed, retrying insecure: " + secureFailure);
            BluetoothSocket s = connectWithin(device, false);
            preferInsecure = true;
            return s;
        }
    }

    /**
     * Do the create and the connect on a worker thread, with a deadline.
     *
     * Closing the socket is the only way to interrupt either call; there is no
     * cancel, and neither accepts a timeout.
     */
    private BluetoothSocket connectWithin(android.bluetooth.BluetoothDevice device,
                                          boolean secure) throws IOException {
        final Attempt attempt = new Attempt();
        Thread worker = new Thread(() -> {
            try {
                BluetoothSocket s = secure
                        ? device.createRfcommSocketToServiceRecord(SPP_UUID)
                        : device.createInsecureRfcommSocketToServiceRecord(SPP_UUID);
                attempt.socket = s;
                if (attempt.aborted) {
                    closeQuietly(s);
                    return;
                }
                s.connect();
            } catch (IOException e) {
                attempt.error = e;
            } catch (SecurityException e) {
                attempt.error = new IOException("Bluetooth permission denied", e);
            }
        }, "spp-connect");
        worker.setDaemon(true);
        worker.start();

        try {
            worker.join(CONNECT_TIMEOUT_MS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            attempt.aborted = true;
            closeQuietly(attempt.socket);
            throw new IOException("Interrupted while connecting over SPP", e);
        }

        if (worker.isAlive()) {
            attempt.aborted = true;
            closeQuietly(attempt.socket);
            try {
                // Give the worker a moment to observe the abort, then free anything it
                // created at the last instant.
                worker.join(250);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
            closeQuietly(attempt.socket);
            throw new Timeout("SPP connect timed out after " + CONNECT_TIMEOUT_MS + "ms");
        }

        if (attempt.error != null) {
            throw attempt.error;
        }
        if (attempt.socket == null) {
            throw new IOException("SPP connect failed");
        }
        return attempt.socket;
    }

    /** Hand-back between the connecting thread and the worker doing the blocking call. */
    private static final class Attempt {
        volatile BluetoothSocket socket;
        volatile IOException error;
        volatile boolean aborted;
    }

    private void startReader(InputStream input) {
        reader = new Thread(() -> {
            byte[] buf = new byte[512];
            try {
                while (true) {
                    int n = input.read(buf);
                    if (n < 0) {
                        Log.d("MX5Link", "SPP peer closed the link");
                        return;             // peer closed
                    }
                    if (n > 0) {
                        byte[] part = new byte[n];
                        System.arraycopy(buf, 0, part, 0, n);
                        feed(part);
                    }
                }
            } catch (IOException e) {
                // Connection gone. The queue simply stops filling, so a pending
                // receiveLine times out rather than hanging for ever.
                Log.d("MX5Link", "SPP read failed: " + e);
            }
        }, "spp-read");
        reader.setDaemon(true);
        reader.start();
    }

    /**
     * Write a request line, giving up if the stack will not take it.
     *
     * The write runs on a worker so it can be abandoned. Closing the socket is what
     * actually unblocks it: a BluetoothSocket has no write timeout, and a peer whose
     * link died mid-transfer stops accepting bytes without ever reporting it. When that
     * happened inline, the poll thread held PiClient's request lock for ever and nothing
     * in the app could recover except a restart.
     */
    @Override
    protected void send(byte[] data) throws IOException {
        final OutputStream o = out;
        final BluetoothSocket s = socket;
        if (o == null || s == null) {
            throw new IOException("SPP socket is not open");
        }

        final IOException[] failure = new IOException[1];
        Thread writer = new Thread(() -> {
            try {
                o.write(data);
                o.flush();
            } catch (IOException e) {
                failure[0] = e;
            }
        }, "spp-write");
        writer.setDaemon(true);
        writer.start();

        try {
            writer.join(WRITE_TIMEOUT_MS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            closeQuietly(s);
            throw new IOException("Interrupted during an SPP write", e);
        }

        if (writer.isAlive()) {
            closeQuietly(s);
            throw new IOException("SPP write timed out after " + WRITE_TIMEOUT_MS + "ms");
        }
        if (failure[0] != null) {
            throw failure[0];
        }
    }

    @Override
    protected void closePipe() {
        closeQuietly(socket);
        socket = null;
        in = null;
        out = null;
        reader = null;
        clearReceived();
    }

    private static void closeQuietly(BluetoothSocket s) {
        if (s == null) {
            return;
        }
        try {
            s.close();
        } catch (IOException ignored) {
            // Closing an already-dead socket is not an error worth reporting.
        }
    }

    /** Unused, but kept so the encoding decision is in one place if it ever matters. */
    static byte[] utf8(String s) {
        return s.getBytes(StandardCharsets.UTF_8);
    }
}
