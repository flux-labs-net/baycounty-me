package me.baycounty.kit

import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit
import java.util.Locale

/** The app's Home tab ("My home dashboard"): a line about the home, an alert strip when notices are active, and tiles
 *  that each give one answer. Owners lead with their tax bill, renters with their utilities, and a resident who hasn't
 *  said leads with setting up their home. Tapping a tile opens one short screen. Mirrors the Swift `HomeTiles`. */
object HomeTiles {
    /** Own or rent, asked once at setup and changeable in My home. `UNSET` is "visiting or rather not say". */
    enum class Tenure(val key: String, val label: String, val detail: String) {
        OWN("own", "I own it", "Your tax bill, homestead and exemptions up front"),
        RENT("rent", "I rent", "Utilities, services and where public money goes up front"),
        UNSET("unset", "Visiting or rather not say", "A county-wide view");

        companion object { fun of(key: String?): Tenure? = entries.firstOrNull { it.key == key } }
    }

    enum class Target { SETUP, TAX_BILL, UTILITIES, BEACHES, MEETINGS, ELECTION, REPRESENTATIVES, SCHOOLS }

    /** `tone` is blue, teal, amber or salmon, like the site's icon tones. `featured` is the first tile, drawn on navy. */
    data class Tile(val id: String, val symbol: String, val tone: String, val eyebrow: String, val value: String, val detail: String,
                    val target: Target, val featured: Boolean = false)

    data class Alert(val title: String, val detail: String)

    /** The home value the tax tile estimates for until the resident enters their own, like the site's calculator. */
    const val SAMPLE_VALUE = 250_000.0

    private val central = ZoneId.of("America/Chicago")

    /** The tiles, in order: the lead tile, trash (only on pickup day or the evening before), beach, election day (in the
     *  45 days before it), next meeting, who represents you, schools. With an odd count the app lets the lead tile span the row. */
    fun tiles(tenure: Tenure, hasHome: Boolean, utilities: UtilityLookup?, taxTotal: Double?, beach: List<Row>,
              meetings: List<Meeting>, electionDay: String?, now: Instant = Instant.now()): List<Tile> = buildList {
        add(lead(tenure, utilities, taxTotal))
        trash(utilities, now)?.let { add(it) }
        add(beachTile(beach))
        election(electionDay, now)?.let { add(it) }
        add(meeting(meetings, now))
        add(Tile("reps", "person.2", "blue", "Who represents you", if (hasHome) "Your officials" else "Officials",
            "City, county and school board", Target.REPRESENTATIVES))
        add(Tile("schools", "graduationcap", "blue", "Schools", if (hasHome) "Your zoned schools" else "Public schools",
            "Grades, calendar and buses", Target.SCHOOLS))
    }

    fun lead(tenure: Tenure, utilities: UtilityLookup?, taxTotal: Double?): Tile = when (tenure) {
        Tenure.OWN -> Tile("tax", "dollarsign.circle", "blue", "Your tax bill", taxTotal?.let { Format.money(it) } ?: "Estimate",
            "a year · ${Format.compactMoney(SAMPLE_VALUE)} home, homestead", Target.TAX_BILL, featured = true)
        Tenure.RENT -> {
            val n = utilities?.services?.size ?: 0
            Tile("utilities", "bolt", "teal", "Your utilities", "Water, power, trash",
                if (n > 0) "Who provides each of $n services" else "Who to call to set up or report", Target.UTILITIES, featured = true)
        }
        Tenure.UNSET -> Tile("setup", "house", "blue", "Make it yours", "Set up your home",
            "Own or rent? Get answers for your address", Target.SETUP, featured = true)
    }

    /** The trash tile from the Today trash card's rules: only on pickup day, or from 4 p.m. the day before. */
    fun trash(lookup: UtilityLookup?, now: Instant): Tile? {
        val c = TodayBrief.trashCard(lookup, now) ?: return null
        val word = if (c.title.endsWith("today")) "Today" else "Tomorrow"
        val none = c.title.startsWith("No ")
        return Tile("trash", "trash", "teal", "Trash day", if (none) "No pickup" else word,
            if (none) "$word · ${c.detail}" else c.detail, Target.UTILITIES)
    }

    fun beachTile(rows: List<Row>): Tile {
        val f = Outdoors.forecast(rows).firstOrNull()
        return Tile("beach", "flag", "amber", "Beach", f?.string("flag_color")?.let { "$it flag" } ?: "Beach flags",
            f?.string("rip_current_risk")?.let { "$it rip current risk" } ?: "Today's flag at each beach", Target.BEACHES)
    }

    /** Election day, in the 45 days before it (and on the day). */
    fun election(day: String?, now: Instant): Tile? {
        val d = day?.let { runCatching { LocalDate.parse(it.take(10)) }.getOrNull() } ?: return null
        val days = ChronoUnit.DAYS.between(now.atZone(central).toLocalDate(), d)
        if (days < 0 || days > 45) return null
        return Tile("election", "checkmark.seal", "salmon", "Election day",
            if (days == 0L) "Today" else d.format(DateTimeFormatter.ofPattern("EEE, MMM d", Locale.US)),
            "Your ballot and where to vote", Target.ELECTION)
    }

    fun meeting(meetings: List<Meeting>, now: Instant): Tile {
        val m = Meeting.upcoming(meetings, now).firstOrNull()
        val s = m?.start ?: return Tile("meeting", "calendar", "blue", "Meetings", "Public meetings",
            "When every board meets, with agendas", Target.MEETINGS)
        return Tile("meeting", "calendar", "blue", "Next meeting",
            s.atZone(central).format(DateTimeFormatter.ofPattern("EEE, MMM d", Locale.US)), m.boardName, Target.MEETINGS)
    }

    /** The strip above the tiles when notices are active: the most urgent kind first (evacuation, weather, boil water,
     *  road, utility), with the count of that kind. */
    fun alert(notices: List<Row>): Alert? {
        val active = notices.filter { it.string("status") == "active" }
        if (active.isEmpty()) return null
        val kind = listOf("evacuation", "weather", "boil-water", "road", "utility").firstOrNull { k -> active.any { it.string("kind") == k } }
        val n = kind?.let { k -> active.count { it.string("kind") == k } } ?: active.size
        val title = "$n ${kind?.let { "$it " } ?: ""}notice${if (n == 1) "" else "s"} in effect"
        val others = active.size - n
        // "the map" only when one of them has a map to show.
        val next = if (active.any { AlertArea.parse(it.string("geometry")) != null }) "See the map and what to do." else "See what to do."
        return Alert(title, if (others > 0) "$others more active. $next" else next)
    }

    /** "YOUR HOME · PANAMA CITY · RENTING" with a saved home, else "BAY COUNTY". The app shows it in capitals. */
    fun eyebrow(place: String?, tenure: Tenure): String =
        place?.let { "Your home · $it" + if (tenure == Tenure.RENT) " · Renting" else "" } ?: "Bay County"

    /** The tax district for the saved home: its city when the utilities lookup names one, the county's unincorporated
     *  district outside the cities, else the one picked in the tax calculator, else the first. */
    fun taxDistrict(model: TaxModel, utilities: UtilityLookup?, saved: String?): TaxModel.District? {
        if (utilities != null) {
            val id = if (utilities.area == "county") "unincorporated" else utilities.areaName
            model.districts.firstOrNull { it.id == id }?.let { return it }
        }
        return model.districts.firstOrNull { it.id == saved } ?: model.districts.firstOrNull()
    }
}
