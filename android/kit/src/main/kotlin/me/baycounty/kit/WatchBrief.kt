package me.baycounty.kit

import java.time.Instant
import java.time.ZoneId
import java.time.format.TextStyle
import java.util.Locale

/** What the watch apps show: active alerts first, then the saved home's trash day, the beach flag and the next
 *  meeting, plus the short lines the watch face complications use. Built from the same live feed and rules as the
 *  phone's Home tab (Emergency, TodayBrief). Mirrors the Swift `WatchBrief`. */
object WatchBrief {
    /** One active alert, already worded for a small screen. `nearHome` = posted by the saved home's city. */
    data class Alert(
        val id: String, val kind: String, val label: String, val symbol: String, val title: String, val summary: String,
        val source: String, val posted: String, val severity: String, val nearHome: Boolean,
    )

    data class Brief(
        /** "Lynn Haven", or "Bay County" without a saved home. */
        val place: String,
        val hasHome: Boolean,
        /** False when the live alert feed couldn't be reached. */
        val alertsLoaded: Boolean,
        val headline: String,
        val alerts: List<Alert>,
        /** The trash card, only on pickup day or from 4 p.m. the day before (TodayBrief.trashCard). */
        val trash: TodayBrief.Card?,
        /** "Next pickup Friday" on the other days, when the home has a set garbage day. */
        val nextPickup: String?,
        val beach: TodayBrief.Card,
        val meeting: TodayBrief.Card,
    ) {
        val alertCount: Int get() = alerts.size
        val alertTitle: String get() = when {
            !alertsLoaded -> "Alerts didn't load"
            alertCount == 0 -> "No active alerts"
            else -> "$alertCount active alert${if (alertCount == 1) "" else "s"}"
        }

        /** The one line on a watch face: alerts first, then a trash reminder, else all clear. */
        val inline: String get() = when {
            alertsLoaded && alertCount > 0 -> alertTitle
            trash != null -> trash.title
            alertsLoaded -> "No active alerts"
            else -> "BayCounty.me"
        }

        /** The small round complication: the alert count, or "0". */
        val circular: String get() = if (alertsLoaded) alertCount.toString() else "–"

        /** The long complication's second line: the trash reminder, else the beach flag. */
        val rectangularDetail: String get() = trash?.title ?: beach.title
    }

    private val central = ZoneId.of("America/Chicago")

    /** `feed` is /api/v1/emergency (null when it couldn't load), `utilities` the saved home's /api/v1/utilities answer. */
    fun make(feed: Emergency.Feed?, utilities: UtilityLookup?, beach: List<Row>, meetings: List<Meeting>,
             now: Instant = Instant.now(), limit: Int = 12): Brief {
        val area = utilities?.area
        val active = Emergency.sorted((feed?.notices ?: emptyList()).filter {
            (it.string("status") ?: "active") == "active" && it.string("same_as").isNullOrEmpty()
        })
        val alerts = active.take(limit).mapIndexed { i, n ->
            val kind = n.string("kind") ?: "other"
            Alert(n.string("notice_id") ?: "n$i", kind, Emergency.label(kind), Emergency.symbol(kind),
                n.string("title") ?: Emergency.label(kind), clean(n.first(listOf("summary", "instruction")) ?: ""),
                n.string("source") ?: "", Emergency.posted(n), n.string("severity") ?: "",
                area != null && n.string("gov_id") == area)
        }
        // Meetings of the home's own government first; the whole county when it has none coming up.
        val own = area?.let { a -> meetings.filter { it.govID == a } } ?: emptyList()
        val meeting = TodayBrief.meetingCard(if (Meeting.upcoming(own, now).isEmpty()) meetings else own, now)
        val trash = TodayBrief.trashCard(utilities, now)
        val next = if (trash == null) TodayBrief.trashDays(utilities)?.let { days ->
            PickupDays.next(days, now.atZone(central).toLocalDate())?.let { "Next pickup " + it.dayOfWeek.getDisplayName(TextStyle.FULL, Locale.US) }
        } else null
        val place = utilities?.let { if (it.area == "county") "Bay County" else it.areaName } ?: "Bay County"
        return Brief(place, utilities != null, feed != null,
            feed?.headline ?: "Couldn't reach BayCounty.me. Check again in a minute.",
            alerts, trash, next, TodayBrief.beachCard(beach), meeting)
    }

    /** Collapses runs of spaces and blank lines so a summary reads as one paragraph on a watch. */
    internal fun clean(s: String): String = s.replace(Regex("\\s+"), " ").trim()

    /** The only thing the phone sends the watch: the saved home's map point. The watch looks up the city and trash
     *  day itself from /api/v1/utilities, and nothing else about the resident leaves the phone. */
    data class Home(val lat: Double, val lon: Double) {
        val point: GeoPoint get() = GeoPoint(x = lon, y = lat)

        companion object {
            /** The Wear data item's path and the phone-to-watch message. No home = cleared. */
            const val PATH = "/home"
            fun message(home: Home?): Map<String, Any> =
                if (home == null) mapOf("home" to false) else mapOf("home" to true, "lat" to home.lat, "lon" to home.lon)

            /** Reads a message: Result(null) when the phone has no saved home, null when it isn't a home message. */
            fun from(m: Map<String, Any?>): Result<Home?>? {
                val has = m["home"] as? Boolean ?: return null
                val lat = m["lat"] as? Double; val lon = m["lon"] as? Double
                return Result.success(if (has && lat != null && lon != null) Home(lat, lon) else null)
            }
        }
    }
}
