package me.baycounty.wear

import android.content.Context
import com.google.android.gms.wearable.DataEvent
import com.google.android.gms.wearable.DataEventBuffer
import com.google.android.gms.wearable.DataItem
import com.google.android.gms.wearable.DataMapItem
import com.google.android.gms.wearable.Wearable
import com.google.android.gms.wearable.WearableListenerService
import me.baycounty.kit.WatchBrief

/** Receives the saved home's map point from the phone app (WatchSync there). Nothing else comes over from the phone. */
class PhoneLink : WearableListenerService() {
    override fun onDataChanged(events: DataEventBuffer) {
        for (e in events) {
            if (e.dataItem.uri.path != WatchBrief.Home.PATH) continue
            if (e.type == DataEvent.TYPE_DELETED) WatchData.saveHome(this, null) else apply(this, e.dataItem)
        }
    }

    companion object {
        fun apply(c: Context, item: DataItem) {
            val d = DataMapItem.fromDataItem(item).dataMap
            val m = mapOf("home" to d.getBoolean("home"), "lat" to d.getDouble("lat"), "lon" to d.getDouble("lon"))
            WatchBrief.Home.from(m)?.let { WatchData.saveHome(c, it.getOrNull()) }
        }

        /** Picks up a home the phone sent while this app wasn't listening (first install, phone out of range). */
        fun sync(c: Context, then: () -> Unit) {
            runCatching {
                Wearable.getDataClient(c).dataItems.addOnSuccessListener { items ->
                    items.filter { it.uri.path == WatchBrief.Home.PATH }.forEach { apply(c, it) }
                    items.release()
                    then()
                }
            }
        }
    }
}
