package com.mx5.remote;

import android.bluetooth.BluetoothSocket;

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

    private final DeviceSource devices;

    private BluetoothSocket socket;
    private InputStream in;
    private OutputStream out;
    private Thread reader;

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
        return socket != null && socket.isConnected();
    }

    @Override
    protected void open() throws IOException {
        android.bluetooth.BluetoothDevice device = devices.device();
        if (device == null) {
            throw new IOException(devices.reason());
        }

        BluetoothSocket s;
        try {
            s = device.createRfcommSocketToServiceRecord(SPP_UUID);
        } catch (SecurityException e) {
            throw new IOException("Bluetooth permission denied", e);
        } catch (IOException e) {
            throw new IOException("Could not create an SPP socket: " + e.getMessage(), e);
        }

        try {
            s.connect();
        } catch (IOException e) {
            closeQuietly(s);
            // The usual cause on a Pi is that the SDP record was never published, which
            // reads as "service not found" here.
            throw new IOException("SPP connect failed: " + e.getMessage(), e);
        }

        socket = s;
        in = s.getInputStream();
        out = s.getOutputStream();
        clearReceived();
        startReader(in);
    }

    private void startReader(InputStream input) {
        reader = new Thread(() -> {
            byte[] buf = new byte[512];
            try {
                while (true) {
                    int n = input.read(buf);
                    if (n < 0) {
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
            }
        }, "spp-read");
        reader.setDaemon(true);
        reader.start();
    }

    @Override
    protected void send(byte[] data) throws IOException {
        OutputStream o = out;
        if (o == null) {
            throw new IOException("SPP socket is not open");
        }
        o.write(data);
        o.flush();
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
