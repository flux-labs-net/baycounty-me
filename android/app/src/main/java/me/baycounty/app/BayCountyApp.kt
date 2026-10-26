package me.baycounty.app

import android.app.Application

/** Holds the one AppStore so it survives activity restarts. */
class BayCountyApp : Application() {
    val store: AppStore by lazy { AppStore(this) }
}
