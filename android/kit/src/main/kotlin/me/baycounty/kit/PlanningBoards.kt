package me.baycounty.kit

import java.time.LocalDate
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Planning and zoning boards on a government's screen, from the planning-boards and planning-board-members datasets.
 *  Mirrors the Swift `PlanningBoards` and site/planning_boards.py: same order, member lines and meeting wording. */
object PlanningBoards {
    val datasets = listOf("planning-boards", "planning-board-members")

    /** A government's boards, in the order the site lists them. */
    fun boards(rows: List<Row>, govID: String): List<Row> = rows.filter { it.string("gov_id") == govID }

    /** One board's members: chair, vice chair, members, alternates (the dataset's sort_order). */
    fun members(rows: List<Row>, boardID: String?): List<Row> =
        rows.filter { it.string("board_id") == boardID }.sortedBy { it.number("sort_order") ?: 99.0 }

    /** "Chair · Post 3 · term ends Jan 8, 2027"; "Member" when there is nothing more to say. */
    fun memberLine(m: Row): String = listOfNotNull(
        m.string("role")?.takeIf { it != "Member" && m.string("seat")?.startsWith(it) != true }, m.string("seat"),
        m.string("term_end")?.let { day(it) }?.let { "term ends $it" },
    ).joinToString(" · ").ifEmpty { "Member" }

    /** "Mon, Nov 9, 2026 at 4 PM", or the date alone when no time is posted. */
    fun meetingLine(iso: String?): String? {
        if (iso.isNullOrBlank()) return null
        if (!iso.contains('T')) return day(iso, withWeekday = true)
        val t = runCatching { OffsetDateTime.parse(iso).toLocalDateTime() }.getOrNull()
            ?: runCatching { LocalDateTime.parse(iso.take(19)) }.getOrNull() ?: return null
        val time = DateTimeFormatter.ofPattern(if (t.minute == 0) "h a" else "h:mm a", Locale.US).format(t)
        return DateTimeFormatter.ofPattern("EEE, MMM d, yyyy", Locale.US).format(t) + " at " + time
    }

    /** "3 members listed" or "Members not published online", for the parts menu. */
    fun summary(boards: List<Row>): String {
        val n = boards.sumOf { (it.number("members_listed") ?: 0.0).toInt() }
        return if (n > 0) "$n member${if (n == 1) "" else "s"} listed" else "Members not published online"
    }

    private fun day(iso: String, withWeekday: Boolean = false): String? = runCatching {
        DateTimeFormatter.ofPattern(if (withWeekday) "EEE, MMM d, yyyy" else "MMM d, yyyy", Locale.US).format(LocalDate.parse(iso.take(10)))
    }.getOrNull()
}
