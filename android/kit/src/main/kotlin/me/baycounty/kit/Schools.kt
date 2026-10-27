package me.baycounty.kit

import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Public schools (/schools), from the schools, school-calendar and school-enrollment datasets (plus school-grades and
 *  school-spending once the state's files are in). Mirrors the Swift `Schools` and site/schools_page.py. */
object Schools {
    val datasets = listOf("schools", "school-calendar", "school-enrollment", "school-grades", "school-spending")
    val levelOrder = listOf("Elementary", "Middle", "High", "Combined", "Other")

    enum class Filter(val label: String) { ALL("All"), ELEMENTARY("Elementary"), MIDDLE("Middle"), HIGH("High"), COMBINED("K-8 and K-12"), CHARTER("Charter") }

    /** Open schools, by level then name, optionally filtered and searched (name or city). */
    fun open(rows: List<Row>, filter: Filter = Filter.ALL, query: String = ""): List<Row> {
        val q = query.trim().lowercase()
        return rows.filter { r ->
            if (r.string("status") != "Open") return@filter false
            val level = r.string("level") ?: ""
            val ok = when (filter) {
                Filter.ALL -> true
                Filter.CHARTER -> r.bool("charter") == true
                Filter.COMBINED -> level == "Combined"
                else -> level == filter.label
            }
            ok && (q.isEmpty() || "${r.string("name") ?: ""} ${r.string("city") ?: ""}".lowercase().contains(q))
        }.sortedWith(compareBy({ levelOrder.indexOf(it.string("level") ?: "").let { i -> if (i < 0) 9 else i } }, { it.string("name") ?: "" }))
    }

    /** Schools that have closed since 2016, most recently closed first. */
    fun closed(rows: List<Row>): List<Row> =
        rows.filter { it.string("status") == "Closed" }
            .sortedWith(compareByDescending<Row> { it.string("last_year_open") ?: "" }.thenBy { it.string("name") ?: "" })

    /** "Elementary · grades PK-5 · Lynn Haven · Charter" */
    fun subtitle(s: Row): String =
        listOfNotNull(s.string("level"), s.string("grades")?.let { "grades $it" }, s.string("city"), if (s.bool("charter") == true) "Charter" else null)
            .joinToString(" · ")

    enum class Kind(val label: String) {
        ALL("Everything"), OFF("Days off"), MILESTONES("Grading and graduation"), BOARD("School Board");
        fun matches(kind: String): Boolean = when (this) {
            ALL -> true
            OFF -> kind == "no-school" || kind == "break"
            MILESTONES -> kind in setOf("grading", "graduation", "first-day", "last-day", "early-release")
            BOARD -> kind == "board-meeting"
        }
    }

    private val kindLabels = mapOf(
        "no-school" to "No school", "break" to "Break", "board-meeting" to "School Board", "early-release" to "Early release",
        "grading" to "Grading period", "graduation" to "Graduation", "first-day" to "First day", "last-day" to "Last day",
    )
    fun kindLabel(k: String?): String = kindLabels[k ?: ""] ?: "District event"

    /** Calendar entries that haven't ended by `today` (yyyy-MM-dd, local), soonest first. */
    fun upcoming(rows: List<Row>, today: String, kind: Kind = Kind.ALL): List<Row> =
        rows.filter { r ->
            val s = r.string("starts") ?: return@filter false
            (r.string("ends") ?: s).take(10) >= today && kind.matches(r.string("kind") ?: "")
        }.sortedBy { it.string("starts") ?: "" }

    /** The next day off (no school or a break) that starts on or after `today`. */
    fun nextDayOff(rows: List<Row>, today: String): Row? =
        upcoming(rows, today, Kind.OFF).firstOrNull { (it.string("starts") ?: "").take(10) >= today }

    internal fun parse(s: String): LocalDateTime? = when {
        s.length >= 19 -> runCatching { LocalDateTime.parse(s.take(19), DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss")) }.getOrNull()
        s.length >= 16 -> runCatching { LocalDateTime.parse(s.take(16), DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm")) }.getOrNull()
        s.length >= 10 -> runCatching { java.time.LocalDate.parse(s.take(10)).atStartOfDay() }.getOrNull()
        else -> null
    }

    fun date(row: Row): LocalDateTime? = row.string("starts")?.let(::parse)

    private fun fmt(p: String) = DateTimeFormatter.ofPattern(p, Locale.US)

    /** "Tue, Oct 27 · 3 p.m.", "Wednesday, October 28" or "Mon, Nov 23 to Fri, Nov 27". */
    fun whenLabel(row: Row): String {
        val s = row.string("starts") ?: return ""
        val d = parse(s) ?: return ""
        val end = row.string("ends")?.let(::parse)
        if (row.bool("all_day") == true || !s.contains('T')) {
            if (end != null && end.toLocalDate() != d.toLocalDate()) return "${d.format(fmt("EEE, MMM d"))} to ${end.format(fmt("EEE, MMM d"))}"
            return d.format(fmt("EEEE, MMMM d"))
        }
        val t = d.format(fmt(if (d.minute == 0) "h a" else "h:mm a")).replace("AM", "a.m.").replace("PM", "p.m.")
        return "${d.format(fmt("EEE, MMM d"))} · $t"
    }

    /** Every public school's fall enrollment added up, by school year ("2015-16"), oldest first. */
    fun districtEnrollment(rows: List<Row>): List<Pair<String, Double>> {
        val t = sortedMapOf<String, Double>()
        for (r in rows) { val y = r.string("school_year") ?: continue; t[y] = (t[y] ?: 0.0) + (r.number("enrollment") ?: 0.0) }
        return t.toList()
    }

    /** One school's enrollment by school year, oldest first. */
    fun enrollment(rows: List<Row>, school: String): List<Pair<String, Double>> =
        rows.filter { it.string("school_id") == school }
            .mapNotNull { r -> r.string("school_year")?.let { it to (r.number("enrollment") ?: 0.0) } }
            .sortedBy { it.first }

    /** One school's grades, newest first. */
    fun grades(rows: List<Row>, school: String): List<Row> =
        rows.filter { it.string("school_id") == school }.sortedByDescending { it.number("year") ?: 0.0 }

    /** The site path for a school on /schools. */
    fun pagePath(s: Row): String = s.string("page_url") ?: "/schools/"
}
