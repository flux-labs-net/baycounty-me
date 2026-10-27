package me.baycounty.kit

import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Chambers of commerce (/chambers), from the chambers, chamber-leaders and chamber-events datasets. Mirrors the
 *  Swift `Chambers` and site/chambers_page.py: same groups, order and "coming up" rule. */
object Chambers {
    val datasets = listOf("chambers", "chamber-leaders", "chamber-events")

    /** Board groups in the order the site shows them; staff last. Past chairs are listed separately. */
    val groups = listOf("Executive committee", "Board", "Ex officio (non-voting)", "Honorary", "Staff")

    fun groupLabel(g: String): String = when (g) {
        "Board" -> "Directors"
        "Honorary" -> "Honorary members"
        else -> g
    }

    /** Each group of one chamber's leaders that has anyone in it, in site order. */
    fun leaders(rows: List<Row>, chamber: String): List<Pair<String, List<Row>>> {
        val mine = rows.filter { it.string("chamber_id") == chamber }.sortedBy { it.number("sort_order") ?: 0.0 }
        return groups.mapNotNull { g -> mine.filter { it.string("role_group") == g }.takeIf { it.isNotEmpty() }?.let { g to it } }
    }

    /** Past chairs since 2016, newest first. */
    fun pastChairs(rows: List<Row>, chamber: String): List<Row> =
        rows.filter { it.string("chamber_id") == chamber && it.string("role_group") == "Past chairs" }
            .sortedByDescending { it.number("year") ?: 0.0 }

    /** Board seats (everyone but staff and past chairs). */
    fun boardSeats(rows: List<Row>, chamber: String? = null): Int = rows.count { r ->
        val g = r.string("role_group") ?: ""
        g != "Staff" && g != "Past chairs" && (chamber == null || r.string("chamber_id") == chamber)
    }

    enum class Kind(val label: String) { ALL("All events"), CHAMBER("Chamber events"), COMMUNITY("Community events") }

    /** Events that haven't ended by `today` (yyyy-MM-dd, local), soonest first, optionally for one chamber and kind. */
    fun upcoming(rows: List<Row>, today: String, chamber: String? = null, kind: Kind = Kind.ALL): List<Row> =
        rows.filter { r ->
            val s = r.string("starts")
            if (r.string("kind") != "event" || s == null) return@filter false
            val end = (r.string("ends") ?: s).take(10)
            val isChamber = r.bool("chamber_event") == true
            end >= today && (chamber == null || r.string("chamber_id") == chamber) &&
                (kind == Kind.ALL || (kind == Kind.CHAMBER) == isChamber)
        }.sortedBy { it.string("starts") ?: "" }

    fun programs(rows: List<Row>, chamber: String): List<Row> =
        rows.filter { it.string("kind") == "program" && it.string("chamber_id") == chamber }
            .sortedBy { it.number("sort_order") ?: 0.0 }

    /** The official's id when a leader is linked to an official's profile (opened natively), else null. */
    fun personID(leader: Row): String? =
        leader.string("person_entity_id")?.takeIf { it.startsWith("person:") }?.removePrefix("person:")

    /** The site path of a leader's or organization's profile (`person_url` / `organization_url` / `page_url`). */
    fun profilePath(row: Row, key: String): String? = row.string(key)?.takeIf { it.startsWith("/") }

    fun date(row: Row): LocalDateTime? = row.string("starts")?.let(::parse)

    internal fun parse(s: String): LocalDateTime? =
        runCatching { LocalDateTime.parse(s.take(19), DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss")) }.getOrNull()

    private fun fmt(p: String) = DateTimeFormatter.ofPattern(p, Locale.US)

    /** "Tue, Oct 27 · 8 a.m." style label for an event's start (all-day events show only the date). */
    fun whenLabel(row: Row): String {
        val d = row.string("starts")?.let(::parse) ?: return ""
        val end = row.string("ends")?.let(::parse)
        val allDay = row.bool("all_day") == true || (d.hour == 0 && d.minute == 0)
        if (allDay) {
            if (end != null && end.toLocalDate() != d.toLocalDate()) return "${d.format(fmt("MMM d"))} to ${end.format(fmt("MMM d"))}"
            return d.format(fmt("EEEE, MMMM d"))
        }
        val t = d.format(fmt(if (d.minute == 0) "h a" else "h:mm a")).replace("AM", "a.m.").replace("PM", "p.m.")
        return "${d.format(fmt("EEE, MMM d"))} · $t"
    }
}
