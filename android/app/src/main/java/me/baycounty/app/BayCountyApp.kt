package me.baycounty.app

import android.app.Application

/** Holds the one AppStore so it survives activity restarts. */
class BayCountyApp : Application() {
    val store: AppStore by lazy { AppStore(this) }

    override fun onCreate() {
        super.onCreate()
        Push.setUp(this)
        Account.load(this)
        // The watch app gets the saved home on every launch, in case it was installed after the home was saved.
        WatchSync.send(this, store.home)
    }
}
