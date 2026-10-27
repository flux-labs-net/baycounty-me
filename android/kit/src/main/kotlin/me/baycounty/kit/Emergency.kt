package me.baycounty.kit

import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray
import java.net.URLEncoder
import java.time.Instant
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Emergencies and alerts (/emergency) and Hurricane prep (/hurricane-prep). Mirrors the Swift `Emergency`,
 *  site/emergency_page.py, site/hurricane_prep_page.py and api/_emergency_feed.js. */
object Emergency {
    val datasets = listOf("evacuation-zones", "emergency-shelters", "emergency-resources", "emergency-notices")
    val prepDatasets = listOf("hurricane-prep", "disaster-declarations", "rebuild-money")
    const val FEED_PATH = "/api/v1/emergency"

    val kinds = listOf("evacuation", "weather", "shelter", "boil-water", "road", "utility", "storm")

    fun label(kind: String): String = when (kind) {
        "evacuation" -> "Evacuation order"
        "weather" -> "Weather"
        "shelter" -> "Shelter open"
        "boil-water" -> "Boil-water notice"
        "road" -> "Road closure"
        "utility" -> "Water or utility"
        "storm" -> "Storm update"
        else -> "Notice"
    }

    fun symbol(kind: String): String = when (kind) {
        "evacuation" -> "car.side.arrowtriangle.up.fill"
        "weather" -> "cloud.bolt.rain"
        "shelter" -> "house.lodge"
        "boil-water" -> "drop.triangle"
        "road" -> "road.lanes"
        "utility" -> "drop"
        else -> "megaphone"
    }

    private val severityRank = mapOf("extreme" to 0, "severe" to 1, "moderate" to 2, "minor" to 3, "info" to 4)

    /** Most serious first, then newest. */
    fun sorted(notices: List<Row>): List<Row> = notices.sortedWith(
        compareBy<Row> { severityRank[it.string("severity") ?: ""] ?: 5 }
            .thenByDescending { it.string("updated") ?: it.string("issued") ?: "" },
    )

    /** The headline line, the same wording as the site and the API. */
    fun headline(notices: List<Row>): String {
        notices.firstOrNull { it.string("kind") == "evacuation" }?.let { e ->
            val z = e.string("zones")?.let { if (it.contains(",")) " for Zones $it" else " for Zone $it" } ?: ""
            return "Evacuation order in effect$z."
        }
        val weather = notices.filter { it.string("kind") == "weather" }
        weather.firstOrNull { Regex("Warning|Emergency").containsMatchIn(it.string("event") ?: "") }?.let { return "${it.string("event")} in effect." }
        if (weather.isNotEmpty()) return "${weather.size} weather ${if (weather.size == 1) "advisory or watch" else "advisories and watches"} in effect."
        return "No weather warnings or evacuation orders right now."
    }

    data class Feed(val headline: String, val checkedAt: Instant?, val notices: List<Row>, val shelters: List<Row>, val zones: List<Row>,
                    val counts: Map<String, Int>, val live: Boolean = true) {
        val sheltersOpen: Int get() = shelters.count { it.string("status") == "open" }
        fun count(kind: String): Int = counts[kind] ?: notices.count { it.string("kind") == kind }
    }

    private fun rows(o: Map<String, kotlinx.serialization.json.JsonElement>, key: String): List<Row> =
        (o[key]?.arrayValue ?: emptyList()).mapIndexedNotNull { i, v -> v.objectValue?.let { Row(i, it) } }

    fun parseFeed(data: ByteArray): Feed {
        val o = BCJson.parseToJsonElement(data.decodeToString()).objectValue ?: emptyMap()
        val notices = rows(o, "notices")
        val counts = (o["counts"]?.objectValue ?: emptyMap()).mapNotNull { (k, v) -> v.doubleValue?.let { k to it.toInt() } }.toMap()
        return Feed(o["headline"]?.stringValue ?: headline(notices), o["checked_at"]?.stringValue?.let(::parseInstant),
            notices, rows(o, "shelters"), rows(o, "zones"), counts)
    }

    /** When the live feed can't be reached: active notices from the last daily archive, and the dataset shelters. */
    fun offlineFeed(notices: List<Row>, shelters: List<Row>, zones: List<Row>): Feed {
        val active = sorted(notices.filter { it.string("status") == "active" })
        val sh = shelters.map { r -> if (r["type"] == null && r["shelter_type"] != null) Row(r.id, r.values + ("type" to r["shelter_type"]!!)) else r }
        return Feed(headline(active), null, active, sh, zones, emptyMap(), live = false)
    }

    data class Order(val title: String, val includesYou: Boolean)
    data class ZoneResult(val found: Boolean, val zone: String?, val address: String?, val whatToDo: String, val orders: List<Order>,
                          val nearestShelters: List<Row>, val lat: Double?, val lng: Double?)

    fun zonePath(address: String): String = "/api/v1/evacuation-zone?address=" + URLEncoder.encode(address, "UTF-8").replace("+", "%20")
    fun zonePath(lat: Double, lng: Double): String = "/api/v1/evacuation-zone?lat=" + String.format(Locale.US, "%.5f", lat) + "&lng=" + String.format(Locale.US, "%.5f", lng)

    fun parseZone(data: ByteArray): ZoneResult {
        val o = BCJson.parseToJsonElement(data.decodeToString()).objectValue ?: emptyMap()
        val addr = o["address"]?.objectValue
        val place = listOfNotNull(addr?.get("address")?.stringValue, addr?.get("community")?.stringValue).joinToString(", ")
        val pt = o["point"]?.objectValue
        val orders = (o["orders_now"]?.arrayValue ?: emptyList()).mapNotNull { it.objectValue }
            .map { Order(it["title"]?.stringValue ?: "", it["includes_you"]?.boolValue ?: false) }
        return ZoneResult(o["found"]?.boolValue ?: false, o["zone"]?.stringValue, place.ifEmpty { o["query"]?.stringValue },
            o["what_to_do"]?.stringValue ?: o["message"]?.stringValue ?: "", orders, rows(o, "nearest_shelters"),
            pt?.get("lat")?.doubleValue, pt?.get("lng")?.doubleValue)
    }

    val shelterTypes = listOf("general", "special-needs", "pet-friendly", "extreme-weather", "mass-care", "recovery", "other")

    fun shelterTypeLabel(t: String): String = when (t) {
        "special-needs" -> "Special needs"
        "general" -> "General population"
        "mass-care" -> "Mass care support"
        "recovery" -> "After the storm"
        "extreme-weather" -> "Overflow and extreme weather"
        "pet-friendly" -> "Pet friendly"
        else -> "Shelter"
    }

    /** Shelters grouped by type, in the order above, open ones first within a group. */
    fun sheltersByType(rows: List<Row>): List<Pair<String, List<Row>>> {
        val typeOf = { r: Row -> r.string("type") ?: r.string("shelter_type") ?: "other" }
        return shelterTypes.mapNotNull { t ->
            rows.filter { typeOf(it) == t }
                .sortedWith(compareBy<Row> { if (it.string("status") == "open") 0 else 1 }.thenBy { it.string("name") ?: "" })
                .takeIf { it.isNotEmpty() }?.let { t to it }
        }
    }

    /** Prep steps grouped by topic, in the dataset's order. */
    fun prepTopics(rows: List<Row>): List<Pair<String, List<Row>>> {
        val ordered = rows.sortedBy { it.number("sort_order") ?: 0.0 }
        return ordered.mapNotNull { it.string("topic") }.distinct().map { t -> t to ordered.filter { it.string("topic") == t } }
    }

    fun prepSymbol(topic: String): String = when (topic) {
        "Before the season" -> "calendar"
        "Sandbags" -> "shield.lefthalf.filled"
        "Generator safety" -> "bolt.trianglebadge.exclamationmark"
        "When a storm is coming" -> "hurricane"
        "After the storm" -> "hammer"
        else -> "info.circle"
    }

    enum class Storm(val label: String) {
        ALL("Every storm"), MICHAEL("Michael (2018)"), SALLY("Sally (2020)"), OTHER("Other flooding");

        fun includes(event: String?): Boolean = when (this) {
            ALL -> true
            MICHAEL -> event == "Hurricane Michael"
            SALLY -> event == "Hurricane Sally"
            OTHER -> event != "Hurricane Michael" && event != "Hurricane Sally"
        }
    }

    data class ZipTotal(val zip: String, val name: String, val femaAid: Double = 0.0, val households: Int = 0, val floodPaid: Double = 0.0, val claims: Int = 0) {
        val total: Double get() = femaAid + floodPaid
        val label: String get() = if (zip == "other") "Other" else zip
    }

    /** FEMA housing aid and flood insurance paid per ZIP code for one storm (or all), largest first, "other" last. */
    fun rebuild(rows: List<Row>, storm: Storm = Storm.ALL): List<ZipTotal> {
        val by = linkedMapOf<String, ZipTotal>()
        for (r in rows) {
            if (!storm.includes(r.string("event"))) continue
            val z = r.string("zip") ?: continue
            val t = by[z] ?: ZipTotal(z, r.string("area_name") ?: "")
            val paid = r.number("amount_paid") ?: 0.0
            val n = (r.number("count") ?: 0.0).toInt()
            by[z] = if ((r.string("program") ?: "").startsWith("FEMA")) t.copy(femaAid = t.femaAid + paid, households = t.households + n)
                    else t.copy(floodPaid = t.floodPaid + paid, claims = t.claims + n)
        }
        return by.values.filter { it.total > 0 }.sortedWith(compareBy<ZipTotal> { if (it.zip == "other") 1 else 0 }.thenByDescending { it.total })
    }

    fun declarations(rows: List<Row>): List<Row> = rows.sortedByDescending { it.string("declared") ?: "" }

    data class Topic(val id: String, val label: String, val detail: String)

    val pushTopics = listOf(
        Topic("weather", "Weather warnings", "Hurricane, tropical storm, tornado, flood and surge warnings"),
        Topic("evacuation", "Evacuation orders", "When an order names a zone"),
        Topic("shelters", "Shelter openings", "When the county opens shelters"),
        Topic("water", "Boil-water notices", "For the cities you pick, or all"),
        Topic("roads", "Full road closures", "State roads and city closures"),
        Topic("agenda", "Agenda items near me", "Items on a meeting agenda near the place you save"),
    )
    val defaultTopics = setOf("weather", "evacuation", "shelters", "water")
    val pushGovs = listOf(
        "county" to "Unincorporated Bay County", "pc" to "Panama City", "pcb" to "Panama City Beach", "lh" to "Lynn Haven",
        "cw" to "Callaway", "sp" to "Springfield", "parker" to "Parker", "mb" to "Mexico Beach",
    )
    val radiusChoices = listOf(0.25, 0.5, 1.0, 2.0, 5.0)

    /** The sign-up body for POST /api/push. The saved place is a point only (rounded on the server); no address is sent. */
    fun pushBody(token: String, platform: String, topics: Set<String>, govs: List<String>, lat: Double?, lng: Double?, radius: Double, appVersion: String?): String =
        buildJsonObject {
            put("token", token); put("platform", platform); put("place", "fl-bay"); put("radius_mi", radius)
            putJsonArray("topics") { topics.sorted().forEach { add(JsonPrimitive(it)) } }
            putJsonArray("govs") { govs.forEach { add(JsonPrimitive(it)) } }
            if (lat != null && lng != null) { put("lat", lat); put("lng", lng) }
            if (appVersion != null) put("app_version", appVersion)
        }.toString()

    fun unregisterBody(token: String, platform: String): String =
        JsonObject(mapOf("token" to JsonPrimitive(token), "platform" to JsonPrimitive(platform), "action" to JsonPrimitive("unregister"))).toString()

    internal fun parseInstant(s: String): Instant? =
        runCatching { Instant.parse(s) }.getOrNull()
            ?: runCatching { LocalDateTime.parse(s.take(16), DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm")).atZone(ZoneId.of("America/Chicago")).toInstant() }.getOrNull()

    /** "Oct 27, 2:05 PM" in Central time. */
    fun whenLabel(s: String?): String {
        val i = s?.let(::parseInstant) ?: return ""
        return DateTimeFormatter.ofPattern("MMM d, h:mm a", Locale.US).withZone(ZoneId.of("America/Chicago")).format(i)
    }

}
