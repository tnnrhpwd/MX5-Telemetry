package com.mx5.remote;

import android.content.Intent;

import androidx.annotation.NonNull;
import androidx.car.app.Session;

/** One driving session: a single screen that shows the numbers worth glancing at. */
public class Mx5CarSession extends Session {

    @NonNull
    @Override
    public androidx.car.app.Screen onCreateScreen(@NonNull Intent intent) {
        return new Mx5CarScreen(getCarContext());
    }
}
