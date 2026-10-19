package com.mx5.remote;

import androidx.annotation.NonNull;
import androidx.car.app.CarAppService;
import androidx.car.app.Session;
import androidx.car.app.validation.HostValidator;

/**
 * The driving-category entry point.
 *
 * The parked activity (MainActivity) is declared as a "game", which Android Auto
 * deliberately greys out while the car is moving. This service is the supported way to
 * be usable in motion: the Car App Library renders its UI with templates that the host
 * already knows how to keep glanceable, instead of the app drawing a full dashboard.
 *
 * Both mechanisms can live in one APK. The host picks whichever surface the user opens.
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
