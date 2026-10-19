package com.mx5.remote;

import androidx.annotation.NonNull;
import androidx.car.app.CarAppService;
import androidx.car.app.Session;
import androidx.car.app.validation.HostValidator;

/**
 * The drive-flavor entry point.
 *
 * The parked build is declared as a "game", which Android Auto deliberately greys out
 * while the car is moving, and android:appCategory applies to the whole package - so the
 * two surfaces cannot share an APK. This service only exists in the "drive" build
 * (src/drive/AndroidManifest.xml), where the package has no appCategory at all and the
 * host is therefore willing to keep it on screen at speed.
 *
 * The category in that manifest is androidx.car.app.category.IOT. That is not a
 * preference: IOT, NAVIGATION, POI, WEATHER and the messaging/media categories are the
 * only documented values, and an app declaring anything else is not listed by the host.
 * A telemetry reader fits IOT - it reports the state of a connected device.
 */
public class Mx5CarAppService extends CarAppService {

    @NonNull
    @Override
    public Session onCreateSession() {
        return new Mx5CarSession();
    }

    /**
     * Trust every host.
     *
     * The default validator only trusts the Android Auto host plus the hosts named in the
     * app's allowlist, which is how a Play-distributed app is prevented from being driven
     * by an unknown host. This app is sideloaded and is the only consumer of its own
     * templates, so an allowlist would only serve to break it on a head unit that reports
     * a different package name than expected.
     */
    @NonNull
    @Override
    public HostValidator createHostValidator() {
        return HostValidator.ALLOW_ALL_HOSTS_VALIDATOR;
    }
}
