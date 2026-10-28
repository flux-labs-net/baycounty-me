package me.baycounty.kit

import java.time.DayOfWeek
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

/** The top of the app's Today tab: a greeting, four "right now" cards (beach flag, active notices, next meeting,
 *  trash day) and this weekend's events. Same rules and wording as the site's home page (site/home.py `_today`).
 *  Mirrors the Swift `TodayBrief`. */
object TodayBrief {
    enum class Target { BEACHES, EMERGENCY, MEETINGS, UTILITIES }

    /** `tone` is blue, teal, amber or salmon, like the site's icon tones. */
    data class Card(val id: String, val symbol: String, val tone: String, val title: String, val detail: String, val target: Target)

    private val central = ZoneId.of("America/Chicago")

    /** "Good morning" before noon, "Good afternoon" until 5 p.m., then "Good evening". */
    fun greeting(hour: Int): String = if (hour < 12) "Good morning" else if (hour < 17) "Good afternoon" else "Good evening"

    /** The hour in Bay County (Central time). */
    fun hour(now: Instant = Instant.now()): Int = now.atZone(central).hour

    /** "Wednesday, Oct 28" for a yyyy-MM-dd day. */
    fun dateLine(day: String): String {
        val d = runCatching { LocalDate.parse(day) }.getOrNull() ?: return day
        return d.format(DateTimeFormatter.ofPattern("EEEE, MMM d", Locale.US))
    }

    /** The four cards. `beach` is the beach-conditions dataset, `notices` emergency-notices, `trashDays` the garbage
     *  pickup days at the saved home when they were looked up. */
    fun cards(beach: List<Row>, notices: List<Row>, meetings: List<Meeting>, trashDays: String?, now: Instant = Instant.now()): List<Card> =
        listOf(beachCard(beach), noticesCard(notices), meetingCard(meetings, now), trashCard(trashDays))

    fun beachCard(rows: List<Row>): Card {
        val now = Outdoors.forecast(rows).firstOrNull()
        val flag = now?.string("flag_color")
        val risk = now?.string("rip_current_risk")
        return Card("beach", "flag", "amber", flag?.let { "$it beach flag" } ?: "Beach flags",
            risk?.let { "$it rip current risk" } ?: "Today's flag at each beach", Target.BEACHES)
    }

    fun noticesCard(rows: List<Row>): Card {
        val active = rows.filter { it.string("status") == "active" }
        if (active.isEmpty()) return Card("notices", "exclamationmark.triangle", "salmon", "No active alerts",
            "Weather, boil-water and road notices", Target.EMERGENCY)
        val known = setOf("weather", "boil-water", "evacuation", "road", "utility")
        val counts = LinkedHashMap<String, Int>()
        for (n in active) {
            val k = n.string("kind")?.takeIf { it in known } ?: "other"
            counts[k] = (counts[k] ?: 0) + 1
        }
        // Most first; ties keep the order they first appeared in (sortedByDescending is stable, like the site's sort).
        val parts = counts.entries.sortedByDescending { it.value }.map { "${it.value} ${it.key}" }
        return Card("notices", "exclamationmark.triangle", "salmon",
            "${active.size} active notice${if (active.size == 1) "" else "s"}", parts.joinToString(", "), Target.EMERGENCY)
    }

    fun meetingCard(meetings: List<Meeting>, now: Instant = Instant.now()): Card {
        val m = Meeting.upcoming(meetings, now).firstOrNull()
        val s = m?.start ?: return Card("meeting", "calendar", "blue", "Meetings", "When every board meets, with agendas", Target.MEETINGS)
        val day = s.atZone(central).format(DateTimeFormatter.ofPattern("EEE MMM d", Locale.US))
        return Card("meeting", "calendar", "blue", "Next meeting · $day", m.boardName, Target.MEETINGS)
    }

    fun trashCard(days: String?): Card =
        if (!days.isNullOrEmpty()) Card("trash", "trash", "teal", "Trash day: $days", "At your home", Target.UTILITIES)
        else Card("trash", "trash", "teal", "Trash day", "Your pickup day and who provides water and power", Target.UTILITIES)

    /** Garbage pickup days from a utilities lookup ("Friday"), or null. */
    fun trashDays(lookup: UtilityLookup?): String? = lookup?.pickup?.firstOrNull { it.service == "garbage" }?.days

    /** The weekend the Today tab shows: today through Sunday on Friday, Saturday and Sunday, else the coming Friday
     *  through Sunday. Both yyyy-MM-dd. */
    fun weekend(today: String): Pair<String, String>? {
        val t = runCatching { LocalDate.parse(today) }.getOrNull() ?: return null
        val sunday = t.plusDays(((7 - t.dayOfWeek.value) % 7).toLong())
        val from = if (t.dayOfWeek in setOf(DayOfWeek.FRIDAY, DayOfWeek.SATURDAY, DayOfWeek.SUNDAY)) t else sunday.minusDays(2)
        return from.toString() to sunday.toString()
    }

    /** One-off events this weekend (not public meetings or repeating programs), community and chamber events first,
     *  one per title, then in date order. */
    fun weekendEvents(rows: List<Row>, today: String, limit: Int = 4): List<Row> {
        val (from, to) = weekend(today) ?: return emptyList()
        val pool = Events.upcoming(rows, today).filter {
            val d = maxOf((it.string("starts") ?: "").take(10), today)
            d in from..to && it.bool("recurring") != true && it.string("category") != "Public meeting"
        }
        val seen = mutableSetOf<String>()
        val picks = mutableListOf<Row>()
        for (r in pool.filter { it.string("category") != "Library" } + pool.filter { it.string("category") == "Library" }) {
            if (seen.add(r.string("title") ?: "")) picks.add(r)
            if (picks.size == limit) break
        }
        return picks.sortedBy { it.string("starts") ?: "" }
    }
}
