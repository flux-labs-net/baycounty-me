package me.baycounty.kit

import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Volunteer and nonprofit needs board (/volunteer), from the volunteer-needs and volunteer-orgs datasets. Mirrors the
 *  Swift `Volunteer` and site/volunteer_page.py: same causes, order, "still open" rule and date labels. */
object Volunteer {
    val datasets = listOf("volunteer-needs", "volunteer-orgs")

    /** Plain causes in the order the site's filter shows them (site/volunteer_data.py CAUSES). */
    val causes = listOf(
        "Kids and mentoring", "Schools and reading", "Food and basic needs", "Health and hospice", "Seniors",
        "Disaster and emergency", "Housing and neighborhoods", "Animals", "Arts and culture", "Environment",
        "Veterans and service clubs", "Sports and recreation", "Events and fundraisers", "Faith", "Other",
    )

    /** The causes that appear in either list, in filter order. */
    fun causesIn(needs: List<Row>, orgs: List<Row>): List<String> {
        val used = (needs + orgs).mapNotNull { it.string("cause") }.toSet()
        return causes.filter { it in used }
    }

    /** Needs still open on `today` (yyyy-MM-dd): dated ones soonest first, then ongoing, by cause and organization. */
    fun open(needs: List<Row>, today: String, cause: String? = null, nonprofit: String? = null): List<Row> =
        needs.filter { r ->
            val until = r.string("closes") ?: r.string("ends") ?: "9999"
            until >= today && (cause == null || r.string("cause") == cause) && (nonprofit == null || r.string("nonprofit_id") == nonprofit)
        }.sortedWith(compareBy<Row>({ it.string("starts") == null }, { it.string("starts") ?: "" },
            { causes.indexOf(it.string("cause")).let { i -> if (i < 0) 99 else i } }, { it.string("organization") ?: "" }))

    /** Nonprofits for one cause (or all): open needs first, then by volunteers reported. */
    fun orgs(rows: List<Row>, cause: String? = null): List<Row> =
        rows.filter { cause == null || it.string("cause") == cause }
            .sortedWith(compareBy<Row>({ -(it.number("open_needs") ?: 0.0) }, { -(it.number("volunteers_reported") ?: 0.0) }, { it.string("name") ?: "" }))

    private fun day(s: String?): LocalDate? = s?.take(10)?.let { runCatching { LocalDate.parse(it) }.getOrNull() }

    /** "Ongoing", "Multiple shifts", "Thu, Dec 3" or "Nov 1 to Nov 8". */
    fun whenLabel(r: Row): String {
        if (r.string("schedule") == "Shifts") return "Multiple shifts"
        val s = day(r.string("starts")) ?: return "Ongoing"
        val e = day(r.string("ends"))
        val f = { p: String -> DateTimeFormatter.ofPattern(p, Locale.US) }
        return if (e != null && e != s) "${s.format(f("MMM d"))} to ${e.format(f("MMM d"))}" else s.format(f("EEE, MMM d"))
    }

    /** Where a need happens: its city, "Remote or from home", or "Location varies". */
    fun whereLabel(r: Row): String = r.string("city") ?: if (r.bool("remote") == true) "Remote or from home" else "Location varies"

    /** The site path of the organization's profile, when the board's name matched a local nonprofit. */
    fun profilePath(r: Row, key: String): String? = r.string(key)?.takeIf { it.startsWith("/") }
}
