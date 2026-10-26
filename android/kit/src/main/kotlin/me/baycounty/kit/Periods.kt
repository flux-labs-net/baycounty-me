package me.baycounty.kit

import java.time.Instant
import java.time.ZonedDateTime

/**
 * The year a record belongs to, so lists can open on the latest year and step back through earlier ones.
 * Records with a single date use the calendar year of that date. Records that cover a fiscal year use that
 * fiscal year, named for the year it ends.
 */
data class Period(val year: Int, val fiscal: Boolean) : Comparable<Period> {
    val id: String get() = label
    val label: String get() = if (fiscal) "FY$year" else year.toString()

    override fun compareTo(other: Period): Int =
        if (year == other.year) (if (fiscal == other.fiscal) 0 else if (fiscal) -1 else 1) else year.compareTo(other.year)

    /** How one list's records map to years (see the iOS kit for the rules). */
    class Index(rows: List<Row>) {
        val fiscal: Boolean
        val periods: List<Period>
        val datedShare: Double

        init {
            val raw = rows.mapNotNull { of(it) }
            fiscal = raw.count { it.fiscal } * 2 > raw.size
            datedShare = if (rows.isEmpty()) 0.0 else raw.size.toDouble() / rows.size
            periods = rows.mapNotNull { period(it, fiscal) }.toSet().sortedDescending()
        }

        fun period(row: Row): Period? = period(row, fiscal)

        /** The year the list opens on, or null to show every year. */
        fun defaultPeriod(now: Instant = Instant.now()): Period? {
            if (periods.size <= 1 || datedShare < 0.75) return null
            return defaultPeriod(periods, now)
        }

        companion object {
            fun period(row: Row, fiscal: Boolean): Period? {
                val p = of(row) ?: return null
                if (p.fiscal == fiscal) return p
                if (fiscal) {
                    val date = row.first(eventKeys + "date_end")
                    return Period(fiscalYearOfDate(date) ?: p.year, true)
                }
                return Period(yearIn(row.string("date_start")) ?: p.year, false)
            }
        }
    }

    companion object {
        private fun chicagoNow(now: Instant) = ZonedDateTime.ofInstant(now, Dates.chicago)

        /** Bay County governments run October to September; FY2027 began Oct 1, 2026. */
        fun currentFiscalYear(now: Instant = Instant.now()): Int = chicagoNow(now).let { if (it.monthValue >= 10) it.year + 1 else it.year }
        fun currentYear(now: Instant = Instant.now()): Int = chicagoNow(now).year

        /** The first four-digit year (19xx or 20xx) in a string such as "2026-03-10", "FY2024" or "2024 primary". */
        fun yearIn(s: String?): Int? {
            if (s == null || s.length < 4) return null
            for (i in 0..(s.length - 4)) {
                val w = s.substring(i, i + 4)
                if ((w.startsWith("19") || w.startsWith("20")) && w.all { it.isDigit() } &&
                    (i == 0 || !s[i - 1].isDigit()) && (i + 4 == s.length || !s[i + 4].isDigit())
                ) return w.toInt()
            }
            return null
        }

        val eventKeys = listOf("date", "dated_date", "last_obligated", "as_of")
        val fiscalKeys = listOf("fy", "fiscal_year", "date_or_fy", "year")
        val yearKeys = listOf("tax_year", "election")
        private val spanRe = Regex("\\d{4}-\\d{2}(?![\\d-])")

        fun parse(v: String?): Period? {
            val y = yearIn(v) ?: return null
            if (spanRe.containsMatchIn(v!!)) return Period(y + 1, true)
            return Period(y, v.startsWith("FY"))
        }

        fun fiscalYearOfDate(v: String?): Int? {
            if (v == null || v.length < 7) return null
            val y = v.take(4).toIntOrNull() ?: return null
            val m = v.substring(5, 7).toIntOrNull() ?: return null
            return if (m >= 10) y + 1 else y
        }

        /** The year this record belongs to, or null when it carries no date. */
        fun of(row: Row): Period? {
            for (k in eventKeys) parse(row.string(k))?.let { return it }
            val end = row.string("date_end")
            if (end != null) yearIn(end)?.let { return Period(it, row.string("date_start") != end) }
            for (k in fiscalKeys) parse(row.string(k))?.let { return Period(it.year, true) }
            for (k in yearKeys) yearIn(row.string(k))?.let { return Period(it, false) }
            return null
        }

        fun all(rows: List<Row>): List<Period> = Index(rows).periods
        fun defaultPeriodFor(rows: List<Row>, now: Instant = Instant.now()): Period? = Index(rows).defaultPeriod(now)

        fun defaultPeriod(periods: List<Period>, now: Instant = Instant.now()): Period? {
            val newest = periods.firstOrNull() ?: return null
            val current = if (newest.fiscal) currentFiscalYear(now) else currentYear(now)
            val wanted = Period(current, newest.fiscal)
            if (wanted in periods) return wanted
            return periods.firstOrNull { it.year <= current } ?: newest
        }
    }
}

/** A sortable key, newest last: the record's date when it has one, else its period. */
fun DatasetSpec.newestKey(row: Row): String {
    val d = row.first(Period.eventKeys + "date_end")
    if (d != null && d.firstOrNull()?.isDigit() == true) return d
    return Period.of(row)?.let { String.format("%04d-99", it.year) } ?: (sortDate(row) ?: "")
}
