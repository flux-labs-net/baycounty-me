package me.baycounty.app

import android.content.Context
import com.google.android.gms.wearable.PutDataMapRequest
import com.google.android.gms.wearable.Wearable
import me.baycounty.kit.AddressMatch
import me.baycounty.kit.WatchBrief

/** Sends the saved home to the Wear OS app, so the watch can show that home's trash day and city. Only the home's
 *  map point goes over (WatchBrief.Home); the address, account and settings stay on the phone. Mirrors the iOS
 *  WatchSync. Does nothing when no watch is paired. */
object WatchSync {
    fun send(context: Context, home: AddressMatch?) {
        runCatching {
            val m = WatchBrief.Home.message(home?.let { WatchBrief.Home(lat = it.point.y, lon = it.point.x) })
            val req = PutDataMapRequest.create(WatchBrief.Home.PATH).apply {
                dataMap.putBoolean("home", m["home"] as Boolean)
                (m["lat"] as? Double)?.let { dataMap.putDouble("lat", it) }
                (m["lon"] as? Double)?.let { dataMap.putDouble("lon", it) }
            }.asPutDataRequest().setUrgent()
            Wearable.getDataClient(context).putDataItem(req).addOnFailureListener { }
        }
    }
}
