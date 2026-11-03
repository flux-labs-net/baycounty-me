package me.baycounty.kit

import java.time.Instant
import java.time.LocalDate
import java.util.Locale
import java.time.format.DateTimeFormatter

/**
 * One government's figures for one fiscal year, for the government screen's Year picker. The same year rules and
 * "no data" wording as the government pages on the site (site/gov.js): a year with no record says so, names the
 * nearest years we have, and says why. Mirrors ios/BayCountyKit GovYear.
 */
object GovYear {
    enum class Kind { AUDIT, BUDGET }

    data class Line(val name: String, val amount: Double)

    /** One fiscal year of the budget-years dataset for one government. */
    data class Budget(
        val year: Int, val total: Double?, val generalFund: Double?, val status: String?,
        val funds: List<Line>, val departments: List<Line>, val revenue: List<Line>, val spending: List<Line>,
    ) {
        val hasAdopted: Boolean get() = total != null || generalFund != null
    }

    /** Fiscal years to pick from, newest first: the site's first year (2016) to the current fiscal year. */
    fun years(gov: String, now: Instant = Instant.now()): List<Int> =
        (Cutoff.FIRST_YEAR..Officeholders.fiscalYear(gov, now)).reversed().toList()

    private fun fy(r: Row): Int? = r.number("fiscal_year")?.toInt()

    /** This government's government-years row for the year, if there is one. */
    fun row(rows: List<Row>, gov: String, year: Int): Row? = rows.firstOrNull { it.string("gov_id") == gov && fy(it) == year }

    /** Fiscal years with a value in a government-years column. */
    fun yearsWith(rows: List<Row>, gov: String, column: String): List<Int> =
        rows.filter { it.string("gov_id") == gov && it.number(column) != null }.mapNotNull(::fy).distinct().sorted()

    /** "FY2024 (year ended 2024-09-30)" -> 2024. */
    fun fiscalYearOf(s: String?): Int? = s?.let { Regex("""FY\s*(\d{4})""").find(it)?.groupValues?.get(1)?.toInt() }

    fun budget(rows: List<Row>, gov: String, year: Int): Budget {
        val rs = rows.filter { it.string("gov_id") == gov && fy(it) == year }
        fun lines(basis: String, section: String) = rs.filter { it.string("basis") == basis && it.string("section") == section && it.bool("in_total") != false }
            .mapNotNull { r -> r.number("amount")?.takeIf { it > 0 }?.let { Line(r.string("name") ?: "", it) } }.sortedByDescending { it.amount }
        val total = rs.firstOrNull { it.string("basis") == "adopted" && it.string("line_key") == "total" }
        val gf = rs.firstOrNull { it.string("basis") == "adopted" && it.string("line_key") == "general_fund" }
        return Budget(year, total?.number("amount"), gf?.number("amount"), (total ?: gf)?.string("status"),
            lines("adopted", "fund"), lines("adopted", "department"), lines("actual", "revenue"), lines("actual", "spending"))
    }

    /** Fiscal years with budget-years lines of a basis (and, optionally, one of the sections). */
    fun budgetYears(rows: List<Row>, gov: String, basis: String, sections: Set<String>? = null): List<Int> =
        rows.filter { it.string("gov_id") == gov && it.string("basis") == basis && (sections == null || it.string("section") in sections) }
            .mapNotNull(::fy).distinct().sorted()

    private val shown = DateTimeFormatter.ofPattern("MMM d, yyyy", Locale.US)

    /** "No FY2019 audit on file. Earliest we have: FY2023. The state Auditor General posts …" */
    fun gap(what: String, year: Int, have: List<Int>, kind: Kind, gov: String, short: String, now: Instant = Instant.now()): String {
        val h = have.distinct().sorted()
        val before = h.lastOrNull { it < year }; val after = h.firstOrNull { it > year }
        val near = when {
            before != null && after != null -> "Nearest we have: FY$before and FY$after."
            before != null -> "Latest we have: FY$before."
            after != null -> "Earliest we have: FY$after."
            else -> ""
        }
        val (from, to) = Officeholders.fyWindow(gov, year)
        val today = Dates.dayKey(now)
        val why = when {
            h.isEmpty() -> "We have no $what for $short in any year yet."
            kind == Kind.AUDIT && to >= today -> "FY$year runs to ${LocalDate.parse(to).format(shown)}; audited figures come only after the year ends."
            kind == Kind.AUDIT && year > h.last() -> "Florida gives governments nine months after the year ends to file the audit with the state, and the FY$year one isn't on file here yet."
            kind == Kind.AUDIT && year < h.first() && year > h.last() - 5 -> "We haven't read it in yet; it is among the last five years of audits the state Auditor General posts online."
            kind == Kind.AUDIT && year < h.first() -> "The state Auditor General posts only the last five years of audits; older ones have to come from $short."
            kind == Kind.BUDGET && from > today -> "FY$year hasn't started; $short adopts each budget in September."
            kind == Kind.BUDGET && year < h.first() -> "Not in ${if (short.endsWith("s")) "$short'" else "$short's"} budget documents online or the state audit reports we have."
            else -> "Not in the records we have found yet."
        }
        return listOf("No FY$year $what on file.", near, why).filter { it.isNotEmpty() }.joinToString(" ")
    }
}
