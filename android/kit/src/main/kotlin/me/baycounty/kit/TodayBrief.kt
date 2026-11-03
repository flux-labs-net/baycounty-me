package me.baycounty.kit

import java.time.DayOfWeek
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

/** The top of the app's Today tab: a greeting, the "right now" cards (trash pickup only around pickup day, beach
 *  flag, active notices, next meeting) and this weekend's events. Same rules and wording as the site's home page (site/home.py `_today`).
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

    /** The "right now" cards. `beach` is the beach-conditions dataset, `notices` emergency-notices, `utilities` the
     *  saved home's utilities lookup. The trash card leads, and only on pickup day (or the evening before). */
    fun cards(beach: List<Row>, notices: List<Row>, meetings: List<Meeting>, utilities: UtilityLookup?, now: Instant = Instant.now()): List<Card> =
        listOfNotNull(trashCard(utilities, now), beachCard(beach), noticesCard(notices), meetingCard(meetings, now))

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

    /** The trash card for the saved home, or null: shown on garbage pickup day, and from 4 p.m. the day before
     *  ("put it out tonight"). A holiday with no pickup says so instead. Same rules as the site's home.js `BCTrashCard`. */
    fun trashCard(lookup: UtilityLookup?, now: Instant = Instant.now()): Card? =
        lookup?.let { trashCard(trashDays(it), it.holidays, now) }

    fun trashCard(days: String?, holidays: List<UtilityLookup.Holiday>, now: Instant): Card? {
        if (days.isNullOrEmpty()) return null
        val local = now.atZone(central)
        val today = local.toLocalDate()
        fun runs(d: LocalDate) = Regex("\\b${weekdays[d.dayOfWeek.value % 7]}\\b", RegexOption.IGNORE_CASE).containsMatchIn(days)
        fun card(d: LocalDate, word: String, detail: String): Card {
            val h = holidays.firstOrNull { Regex("^(no pickup|moved)", RegexOption.IGNORE_CASE).containsMatchIn(it.garbage ?: "") && isOn(it.whenObserved, d) }
                ?: return Card("trash", "trash", "teal", "Trash pickup $word", detail, Target.UTILITIES)
            // "No pickup; in 2025 Thursday's route moved to Saturday, December 27": a note about another year is left off.
            val note = (h.garbage ?: "").replace(Regex("^no pickup[;,.]?\\s*", RegexOption.IGNORE_CASE), "")
            val rest = if (Regex("\\b20\\d\\d\\b").findAll(note).any { it.value.toInt() != d.year }) "" else note
            return Card("trash", "trash", "teal", "No trash pickup $word",
                if (rest.isEmpty()) h.holiday else "${h.holiday} · ${rest.replaceFirstChar { it.uppercase() }}", Target.UTILITIES)
        }
        if (runs(today)) return card(today, "today", "At your home")
        if (local.hour >= 16 && runs(today.plusDays(1))) return card(today.plusDays(1), "tomorrow", "Put it out tonight")
        return null
    }

    private val weekdays = listOf("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")
    private val months = listOf("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")

    /** Whether a holiday's "when" falls on the day: "January 1", "4th Thursday in November", "Last Monday in May". */
    fun isOn(whenText: String?, d: LocalDate): Boolean {
        val parts = (whenText ?: "").split(" ")
        val month = d.monthValue - 1
        if (parts.size == 2) { val n = parts[1].toIntOrNull() ?: return false; return months.indexOf(parts[0]) == month && n == d.dayOfMonth }
        if (parts.size != 4 || parts[2].lowercase() != "in" || months.indexOf(parts[3]) != month || weekdays.indexOf(parts[1]) != d.dayOfWeek.value % 7) return false
        if (parts[0].lowercase() == "last") return d.dayOfMonth + 7 > d.lengthOfMonth()
        val n = parts[0].takeWhile { it.isDigit() }.toIntOrNull() ?: return false
        return (d.dayOfMonth + 6) / 7 == n
    }

    /** Garbage pickup days from a utilities lookup ("Friday"), or null. */
    fun trashDays(lookup: UtilityLookup?): String? = lookup?.pickup?.firstOrNull { it.service == "garbage" && !it.days.isNullOrEmpty() }?.days

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
