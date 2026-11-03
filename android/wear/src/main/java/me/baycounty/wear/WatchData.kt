package me.baycounty.wear

import android.content.ComponentName
import android.content.Context
import androidx.wear.watchface.complications.datasource.ComplicationDataSourceUpdateRequester
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.serialization.json.JsonPrimitive
import me.baycounty.kit.BayCountyClient
import me.baycounty.kit.Emergency
import me.baycounty.kit.Meeting
import me.baycounty.kit.Row
import me.baycounty.kit.UtilityLookup
import me.baycounty.kit.WatchBrief
import java.io.File
import java.time.LocalDateTime
import java.time.ZoneId

/** Loads the watch's brief, for the app and the complication. The saved home's map point comes from the phone
 *  (PhoneLink) and is kept in this watch's preferences only. Mirrors ios/BayCountyWatchShared/WatchData.swift. */
object WatchData {
    private fun prefs(c: Context) = c.getSharedPreferences("watch", Context.MODE_PRIVATE)

    fun home(c: Context): WatchBrief.Home? {
        val p = prefs(c)
        if (!p.contains("lat")) return null
        return WatchBrief.Home(p.getFloat("lat", 0f).toDouble(), p.getFloat("lon", 0f).toDouble())
    }

    /** Saves the phone's home (null clears it) and asks the watch face to redraw the complication. */
    fun saveHome(c: Context, home: WatchBrief.Home?) {
        if (home == home(c)) return
        prefs(c).edit().apply {
            if (home == null) { remove("lat"); remove("lon") }
            // Floats keep about a metre of precision here, which is plenty for a trash-day lookup.
            else { putFloat("lat", home.lat.toFloat()); putFloat("lon", home.lon.toFloat()) }
        }.apply()
        refreshComplications(c)
    }

    fun refreshComplications(c: Context) {
        runCatching { ComplicationDataSourceUpdateRequester.create(c, ComponentName(c, AlertsComplication::class.java)).requestUpdateAll() }
    }

    suspend fun load(c: Context): WatchBrief.Brief = coroutineScope {
        val client = BayCountyClient(cacheDirectory = File(c.cacheDir, "baycounty"))
        val home = home(c)
        val feed = async {
            runCatching { client.get(Emergency.FEED_PATH) }.getOrNull()
                ?.takeIf { it.freshness == BayCountyClient.Freshness.LIVE }
                ?.let { runCatching { Emergency.parseFeed(it.data) }.getOrNull() }
        }
        val utilities = async { home?.let { runCatching { client.utilities(it.point) }.getOrNull() } }
        val beach = async { runCatching { client.rows("beach-conditions").first }.getOrDefault(emptyList()) }
        val meetings = async { runCatching { client.meetings().first }.getOrDefault(emptyList()) }
        WatchBrief.make(feed.await(), utilities.await(), beach.await(), meetings.await())
    }

    /** A made-up day for screenshots and the complication preview (no real people or places beyond the cities). */
    fun demo(clear: Boolean = false): WatchBrief.Brief {
        val feed = """
        {"headline":"No weather warnings or evacuation orders right now.","notices":[
         {"notice_id":"d1","kind":"boil-water","gov_id":"lh","title":"Boil-water notice for the 900 block of Sample Ave","summary":"Bring water to a rolling boil for one minute before drinking or cooking until the city lifts the notice.","source":"City of Lynn Haven","severity":"moderate","issued":"2026-10-30T13:40:00Z","status":"active"},
         {"notice_id":"d2","kind":"road","gov_id":"county","title":"Example Rd closed between 1st and 3rd St","summary":"Drainage work. Use Sample Blvd instead.","source":"Bay County","severity":"minor","issued":"2026-10-30T11:05:00Z","status":"active"}
        ]}
        """.trimIndent()
        val utilities = """
        {"data":{"area":"lh","area_name":"Lynn Haven","services":[],"rates":[],"holidays":[],
         "pickup":[{"service":"garbage","service_label":"Garbage","provider":"City of Lynn Haven","days":"Monday, Thursday"}]}}
        """.trimIndent()
        val beach = Row(0, mapOf("kind" to JsonPrimitive("forecast"), "sort_order" to JsonPrimitive(0),
            "flag_color" to JsonPrimitive("Yellow"), "rip_current_risk" to JsonPrimitive("Moderate")))
        val meeting = Meeting(Row(0, mapOf("board" to JsonPrimitive("lh-commission"), "gov_id" to JsonPrimitive("lh"),
            "start" to JsonPrimitive("2026-11-10T17:00:00-06:00"))))
        val thursday = LocalDateTime.of(2026, 10, 29, 8, 10).atZone(ZoneId.of("America/Chicago")).toInstant()
        val f = if (clear) """{"headline":"No weather warnings or evacuation orders right now.","notices":[]}""" else feed
        return WatchBrief.make(Emergency.parseFeed(f.toByteArray()), UtilityLookup.decode(utilities), listOf(beach), listOf(meeting), thursday)
    }
}
