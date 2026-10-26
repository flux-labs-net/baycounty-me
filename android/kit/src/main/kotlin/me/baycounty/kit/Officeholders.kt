package me.baycounty.kit

import java.time.Instant
import java.time.LocalDate
import java.time.ZonedDateTime

/**
 * Who held each elected seat in a fiscal year, from the officeholder-terms dataset.
 * A port of api/_officials.js `inOffice`, so the app's "Who's in charge" matches the government pages.
 */
object Officeholders {
    data class Holder(
        val personName: String,
        val personID: String?,
        val vacant: Boolean,
        val confirmed: Boolean,
        val startDate: String?,
        val endDate: String?,
        val how: String?,
        /** Joined or left during the period, so someone else held the seat for part of it. */
        val partOfPeriod: Boolean,
        val note: String?,
    ) {
        val id: String get() = "$personName|${startDate ?: ""}"
    }

    data class Seat(val seat: String, val appointed: Boolean, val holders: MutableList<Holder>) {
        val id: String get() = seat
    }

    data class Term(
        val government: String, val govID: String, val seat: String, val appointed: Boolean,
        val startDate: String?, val endDate: String?, val how: String?,
    ) {
        val id: String get() = "$govID|$seat|${startDate ?: ""}"
        /** "2016 to 2020", "Since 2022", "Until 2018". */
        val years: String
            get() {
                val s = startDate?.take(4); val e = endDate?.take(4)
                return when {
                    s != null && e != null -> if (s == e) s else "$s to $e"
                    s != null -> "Since $s"
                    e != null -> "Until $e"
                    else -> ""
                }
            }
    }

    /** Fiscal years start in October; the school district's in July. */
    fun fyWindow(gov: String, year: Int): Pair<String, String> {
        val m = if (gov == "schools") 7 else 10
        val lastMonth = if (m == 1) 12 else m - 1
        val end = LocalDate.of(if (m == 1) year - 1 else year, lastMonth, 1).let { it.withDayOfMonth(it.lengthOfMonth()) }
        return String.format("%d-%02d-01", year - 1, m) to end.toString()
    }

    /** A term ends on the day its successor starts, so an end date equal to `from` is out. */
    internal fun overlaps(r: Row, from: String, to: String): Boolean =
        (r.string("start_date")?.let { it <= to } ?: true) && (r.string("end_date")?.let { it > from } ?: true)

    fun fiscalYear(gov: String, date: Instant = Instant.now()): Int {
        val z = ZonedDateTime.ofInstant(date, Dates.chicago)
        return if (z.monthValue >= (if (gov == "schools") 7 else 10)) z.year + 1 else z.year
    }

    /** Fiscal years with terms on record for a government, newest first, from the site's first year (2016). */
    fun years(rows: List<Row>, gov: String, now: Instant = Instant.now()): List<Int> {
        if (rows.none { it.string("gov_id") == gov }) return emptyList()
        return (Cutoff.FIRST_YEAR..fiscalYear(gov, now)).reversed().toList()
    }

    fun inOffice(all: List<Row>, gov: String, year: Int? = null, date: String? = null, today: Instant = Instant.now()): List<Seat> {
        val rows = all.filter { it.string("gov_id") == gov }
        val (from, to) = when {
            date != null -> date to date
            year != null -> fyWindow(gov, year)
            else -> Dates.dayKey(today).let { it to it }
        }
        val order = mutableListOf<String>()
        val seats = HashMap<String, Seat>()
        val sorted = rows.sortedWith(compareBy<Row> { it.number("seat_order") ?: 0.0 }.thenBy { it.number("term_order") ?: 0.0 })
        for (r in sorted) {
            val name = r.string("seat") ?: ""
            if (seats[name] == null) { order.add(name); seats[name] = Seat(name, r.bool("appointed") ?: false, mutableListOf()) }
            if (!overlaps(r, from, to)) continue
            val part = (r.string("start_date")?.let { it > from } ?: false) || (r.string("end_date")?.let { it <= to } ?: false)
            seats[name]!!.holders.add(
                Holder(
                    r.string("person_name") ?: "", r.string("person_id"), r.bool("vacant") ?: false, r.bool("confirmed") != false,
                    r.string("start_date"), r.string("end_date"), r.string("how"), part, r.string("note"),
                )
            )
        }
        return order.mapNotNull { seats[it] }
    }

    /** Every term a person served, newest first. */
    fun terms(all: List<Row>, personID: String): List<Term> =
        all.filter { it.string("person_id") == personID && it.bool("vacant") != true }.map { r ->
            Term(
                r.string("government") ?: Governments.names[r.string("gov_id") ?: ""] ?: "",
                r.string("gov_id") ?: "", r.string("seat") ?: "", r.bool("appointed") ?: false,
                r.string("start_date"), r.string("end_date"), r.string("how"),
            )
        }.sortedByDescending { it.endDate ?: "9999" }
}

/** The site's first year: nothing from 2015 or earlier is shown anywhere (entities/cutoff.py, api/_cutoff.js). */
object Cutoff {
    const val FIRST_YEAR = 2016
}
