package me.baycounty.kit

import java.time.LocalDate

/** Beaches (/beaches) and parks (/parks), from the beach-conditions, beach-water-sites, beach-access, beach-parking,
 *  parks, boat-ramps, trails and recreation-departments datasets. Mirrors the Swift `Outdoors` and site/outdoors_page.py. */
object Outdoors {
    val beachDatasets = listOf("beach-conditions", "beach-water-sites", "beach-access", "beach-parking")
    val parkDatasets = listOf("parks", "boat-ramps", "trails", "recreation-departments")

    /** The latest forecast periods, in order. The first carries the flag color reported that day. */
    fun forecast(rows: List<Row>): List<Row> = rows.filter { it.string("kind") == "forecast" }.sortedBy { it.number("sort_order") ?: 0.0 }

    fun alerts(rows: List<Row>): List<Row> = rows.filter { it.string("kind") == "alert" }

    /** What each flag color means, in the order the site lists them (double red first). */
    fun legend(rows: List<Row>): List<Row> = rows.filter { it.string("kind") == "legend" }.sortedBy { it.number("sort_order") ?: 0.0 }

    /** Today's flag color ("Yellow", "Double red", ...) and what it means, or null when none was reported. */
    fun flag(rows: List<Row>): Pair<String, String>? {
        val c = forecast(rows).firstOrNull()?.string("flag_color") ?: return null
        return c to (legend(rows).firstOrNull { it.string("flag_color") == c }?.string("meaning") ?: "")
    }

    /** The flag's color as RGB, matching the site. */
    fun flagHex(color: String): Long = when (color) {
        "Double red" -> 0xC62828
        "Red" -> 0xE53935
        "Yellow" -> 0xF2C230
        "Green" -> 0x2E9E5B
        "Purple" -> 0x7E57C2
        else -> 0x9AA3AF
    }

    /** Active sampling sites, west to east. */
    fun waterSites(rows: List<Row>): List<Row> = rows.filter { it.bool("active") == true }.sortedBy { it.number("longitude") ?: 0.0 }

    /** Sites whose latest rated sample was Poor within `days` of `today` (yyyy-MM-dd). */
    fun poorNow(rows: List<Row>, today: String, days: Long = 45): List<Row> {
        val cut = runCatching { LocalDate.parse(today).minusDays(days).toString() }.getOrNull() ?: return emptyList()
        return waterSites(rows).filter { it.string("latest_rating") == "Poor" && (it.string("latest_date") ?: "") >= cut }
    }

    enum class AccessFilter(val label: String) { ALL("All"), WHEELCHAIR("Wheelchair"), DRIVE_ON("Drive-on"), PARKING("Parking") }

    /** Beach accesses west to east, filtered and searched by name, number or street. */
    fun accesses(rows: List<Row>, filter: AccessFilter = AccessFilter.ALL, query: String = ""): List<Row> {
        val q = query.trim().lowercase()
        return rows.filter { r ->
            val ok = when (filter) {
                AccessFilter.ALL -> true
                AccessFilter.WHEELCHAIR -> r.bool("wheelchair_access") == true
                AccessFilter.DRIVE_ON -> r.bool("vehicle_access") == true
                AccessFilter.PARKING -> r.bool("parking") == true
            }
            val text = listOfNotNull(r.string("name"), r.string("address"), r.string("area")).joinToString(" ").lowercase()
            ok && (q.isEmpty() || q in text)
        }.sortedBy { it.number("longitude") ?: 0.0 }
    }

    /** The short tags for what's at an access ("Wheelchair", "Drive-on", "Parking (40)", ...). */
    fun accessTags(r: Row): List<String> = buildList {
        if (r.bool("wheelchair_access") == true) add("Wheelchair")
        if (r.bool("vehicle_access") == true) add("Drive-on")
        if (r.bool("parking") == true) add("Parking" + (r.number("parking_spaces")?.let { " (${it.toInt()})" } ?: ""))
        if (r.bool("restroom") == true) add("Restrooms")
        if (r.bool("shower") == true) add("Showers")
        if (r.bool("lifeguard") == true) add("Lifeguard")
    }

    val amenities = listOf(
        "playground" to "Playground", "restroom" to "Restrooms", "pavilion" to "Pavilion", "picnic_tables" to "Picnic tables", "trail" to "Trail",
        "boat_ramp" to "Boat ramp", "boat_dock" to "Dock", "fishing_pier" to "Fishing pier", "beach_access" to "Beach access", "baseball" to "Baseball",
        "basketball" to "Basketball", "football" to "Football", "soccer" to "Soccer", "tennis" to "Tennis", "volleyball" to "Volleyball",
        "community_building" to "Community building",
    )

    enum class ParkFilter(val label: String) {
        ALL("Any park"), PLAYGROUND("Playground"), RESTROOM("Restrooms"), SPORTS("Sports"), WATER("Ramp, dock or pier"), TRAIL("Trail"), BEACH("Beach access")
    }

    fun has(p: Row, f: ParkFilter): Boolean = when (f) {
        ParkFilter.ALL -> true
        ParkFilter.PLAYGROUND -> p.bool("playground") == true
        ParkFilter.RESTROOM -> p.bool("restroom") == true
        ParkFilter.SPORTS -> listOf("baseball", "basketball", "football", "soccer", "tennis", "volleyball").any { p.bool(it) == true }
        ParkFilter.WATER -> listOf("boat_ramp", "boat_dock", "fishing_pier").any { p.bool(it) == true }
        ParkFilter.TRAIL -> p.bool("trail") == true
        ParkFilter.BEACH -> p.bool("beach_access") == true
    }

    /** Parks by name, filtered by amenity, government (gov_id, or "other" for state land) and search text. */
    fun parks(rows: List<Row>, filter: ParkFilter = ParkFilter.ALL, gov: String = "", query: String = ""): List<Row> {
        val q = query.trim().lowercase()
        return rows.filter { p ->
            val g = p.string("gov_id") ?: "other"
            val text = listOfNotNull(p.string("name"), p.string("address")).joinToString(" ").lowercase()
            has(p, filter) && (gov.isEmpty() || g == gov) && (q.isEmpty() || q in text)
        }.sortedBy { it.string("name") ?: "" }
    }

    fun parkTags(p: Row): List<String> = amenities.filter { p.bool(it.first) == true }.map { it.second }

    /** A geo: link to a row's map point, which opens the phone's Maps app with a pin and its name. */
    fun directions(r: Row): String? {
        val lat = r.number("latitude") ?: return null
        val lon = r.number("longitude") ?: return null
        val label = r.string("name")?.let { "(" + java.net.URLEncoder.encode(it, "UTF-8").replace("+", "%20") + ")" } ?: ""
        return "geo:$lat,$lon?q=$lat,$lon$label"
    }

    /** Web fallback for a geo: link when no Maps app is installed (Google Maps directions). */
    fun webDirections(geo: String): String? {
        val m = Regex("""^geo:(-?[\d.]+),(-?[\d.]+)""").find(geo) ?: return null
        return "https://www.google.com/maps/dir/?api=1&destination=${m.groupValues[1]},${m.groupValues[2]}"
    }
}
