package com.mx5.remote;

import android.Manifest;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothManager;
import android.content.Context;
import android.content.pm.PackageManager;
import android.os.Build;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * Finding the Pi among the phone's paired Bluetooth devices.
 *
 * The app never scans. Scanning needs its own permission and drains the battery, and the
 * Pi has to be paired before either profile can be used anyway, so the paired list is
 * enough. The user picks the device on the System screen; until they do, a name match
 * guesses, which is what makes it work out of the box on a phone that has only ever paired
 * with one Pi.
 *
 * Every call into the Bluetooth stack is wrapped, because on Android 12 and later these
 * need BLUETOOTH_CONNECT at runtime and throw SecurityException rather than returning
 * empty if it has not been granted yet.
 */
final class BtDevices {

    /** Names assumed to be the Pi when nothing has been chosen yet, best first. */
    private static final String[] HINTS = {"mx5pi", "mx5", "raspberrypi"};

    private BtDevices() {
    }

    static BluetoothAdapter adapter(Context c) {
        BluetoothManager m = (BluetoothManager) c.getSystemService(Context.BLUETOOTH_SERVICE);
        return m == null ? null : m.getAdapter();
    }

    /** The runtime permission these calls need on Android 12+, always true before that. */
    static boolean hasPermission(Context c) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            return c.checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT)
                    == PackageManager.PERMISSION_GRANTED;
        }
        return true;
    }

    static String permissionReason(Context c) {
        return hasPermission(c) ? "" : "Needs the Nearby devices permission";
    }

    static boolean isEnabled(Context c) {
        BluetoothAdapter a = adapter(c);
        try {
            return a != null && a.isEnabled();
        } catch (SecurityException e) {
            return false;
        }
    }

    static String address(BluetoothDevice d) {
        try {
            String a = d.getAddress();
            return a == null ? "" : a;
        } catch (SecurityException e) {
            return "";
        }
    }

    static String name(BluetoothDevice d) {
        try {
            String n = d.getName();
            return n == null ? "" : n;
        } catch (SecurityException e) {
            return "";
        }
    }

    /** What to show for a device in a list: its name, or its address if it has no name. */
    static String label(BluetoothDevice d) {
        String n = name(d);
        String a = address(d);
        return n.isEmpty() ? a : n + "  (" + a + ")";
    }

    /** Paired devices. Empty when the permission is missing or Bluetooth is off. */
    static List<BluetoothDevice> bonded(Context c) {
        List<BluetoothDevice> out = new ArrayList<>();
        BluetoothAdapter a = adapter(c);
        if (a == null || !hasPermission(c)) {
            return out;
        }
        try {
            if (a.getBondedDevices() != null) {
                out.addAll(a.getBondedDevices());
            }
        } catch (SecurityException e) {
            // Permission revoked between the check and the call.
        }
        return out;
    }

    /**
     * The device the user picked, or a best guess, or null.
     *
     * The stored value may be a MAC (what the picker saves) or a name the user typed, so
     * both are matched before falling back to the hints.
     */
    static BluetoothDevice find(Context c, String wanted) {
        List<BluetoothDevice> all = bonded(c);
        if (all.isEmpty()) {
            return null;
        }

        String needle = wanted == null ? "" : wanted.trim().toLowerCase(Locale.US);

        if (!needle.isEmpty()) {
            for (BluetoothDevice d : all) {
                if (needle.equals(address(d).toLowerCase(Locale.US))) {
                    return d;
                }
            }
            for (BluetoothDevice d : all) {
                if (name(d).toLowerCase(Locale.US).contains(needle)) {
                    return d;
                }
            }
        }

        for (String hint : HINTS) {
            for (BluetoothDevice d : all) {
                if (name(d).toLowerCase(Locale.US).contains(hint)) {
                    return d;
                }
            }
        }
        return null;
    }

    /** Why no device could be found, for the System screen. */
    static String explain(Context c, String wanted) {
        if (!hasPermission(c)) {
            return "Needs the Nearby devices permission";
        }
        if (!isEnabled(c)) {
            return "Bluetooth is off";
        }
        if (bonded(c).isEmpty()) {
            return "No paired devices: pair the Pi in Android settings first";
        }
        return "No paired device looks like the Pi"
                + (wanted == null || wanted.isEmpty() ? "" : " (looking for " + wanted + ")");
    }
}
