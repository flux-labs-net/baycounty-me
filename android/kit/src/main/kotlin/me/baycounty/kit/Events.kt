package me.baycounty.kit

import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit
import java.util.Locale

/** Community events (/events and the home page), from the community-events dataset. Mirrors the Swift `Events` and
 *  site/events.js: everything is measured against today's local date. */
object Events {
    const val DATASET = "community-events"
    val kinds = listOf("Community", "Public meeting", "Library", "Chamber")

    private fun day(r: Row) = (r.string("starts") ?: "").take(10)

    /** Events that haven't ended by `today` (yyyy-MM-dd), soonest first. */
    fun upcoming(rows: List<Row>, today: String, town: String? = null, kind: String? = null, oneOff: Boolean = false, query: String = ""): List<Row> {
        val q = query.trim().lowercase()
        return rows.filter { r ->
            val s = r.string("starts") ?: return@filter false
            val end = (r.string("ends") ?: s).take(10)
            val text = listOfNotNull(r.string("title"), r.string("venue"), r.string("source")).joinToString(" ").lowercase()
            end >= today && (town == null || r.string("town") == town) && (kind == null || r.string("category") == kind) &&
                (!oneOff || r.bool("recurring") != true) && (q.isEmpty() || q in text)
        }.sortedBy { it.string("starts") ?: "" }
    }

    /** What's on today (started today or earlier and not over). */
    fun today(rows: List<Row>, today: String, town: String? = null): List<Row> = upcoming(rows, today, town).filter { day(it) <= today }

    /** One-off events after today and up to `until`: community and chamber events first, one per title, then by date. */
    fun featured(rows: List<Row>, today: String, until: String, town: String? = null, limit: Int = 8): List<Row> {
        val pool = upcoming(rows, today, town).filter {
            day(it) > today && day(it) <= until && it.bool("recurring") != true && it.string("category") != "Public meeting"
        }
        val seen = mutableSetOf<String>()
        val picks = mutableListOf<Row>()
        for (r in pool.filter { it.string("category") != "Library" } + pool.filter { it.string("category") == "Library" }) {
            if (seen.add(r.string("title") ?: "")) picks.add(r)
            if (picks.size == limit) break
        }
        return picks.sortedBy { it.string("starts") ?: "" }
    }

    /** Towns with events, busiest first, the county-wide calendar last. */
    fun towns(rows: List<Row>): List<String> {
        val n = rows.mapNotNull { it.string("town") }.groupingBy { it }.eachCount()
        return n.keys.filter { it != "Bay County" }.sortedWith(compareByDescending<String> { n[it] }.thenBy { it }) +
            (if ("Bay County" in n) listOf("Bay County") else emptyList())
    }

    /** Upcoming events grouped by day (an event already under way counts as today). */
    fun byDay(rows: List<Row>, today: String): List<Pair<String, List<Row>>> =
        rows.groupBy { maxOf(day(it), today) }.toSortedMap().map { it.key to it.value }

    /** "Today", "Tomorrow" or "Thursday, Oct 29". */
    fun dayLabel(d: String, today: String): String {
        val a = runCatching { LocalDate.parse(d) }.getOrNull() ?: return d
        val diff = ChronoUnit.DAYS.between(LocalDate.parse(today), a)
        return when (diff) {
            0L -> "Today"
            1L -> "Tomorrow"
            else -> a.format(DateTimeFormatter.ofPattern("EEEE, MMM d", Locale.US))
        }
    }

    /** "9:30 a.m." or "All day". */
    fun time(r: Row): String {
        val s = r.string("starts")
        if (r.bool("all_day") == true || s == null || s.length < 16) return "All day"
        val h = s.substring(11, 13).toIntOrNull() ?: 0
        val m = s.substring(14, 16)
        if (h == 0 && m == "00") return "All day"
        return "${if (h % 12 == 0) 12 else h % 12}${if (m == "00") "" else ":$m"} ${if (h < 12) "a.m." else "p.m."}"
    }

    fun todayKey(): String = LocalDate.now(ZoneId.of("America/Chicago")).toString()
    fun plusDays(n: Long): String = LocalDate.now(ZoneId.of("America/Chicago")).plusDays(n).toString()
}
