package me.baycounty.kit

import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Military and the bases (/military), from the military-installations, military-news and federal-contract-years
 *  datasets. Mirrors the Swift `Military` and site/military_page.py. The app leaves out federal-contracts (one row per
 *  contract, several MB) and links to the site for single contracts. */
object Military {
    val datasets = listOf("military-installations", "military-news", "federal-contract-years")

    /** News stories, newest first, optionally for one base. */
    fun stories(rows: List<Row>, base: String? = null): List<Row> =
        rows.filter { base.isNullOrEmpty() || it.string("installation_id") == base }.sortedByDescending { it.string("published") ?: "" }

    data class Company(val id: String, val name: String, val url: String?, val total: Double, val defense: Double, val byAgency: Map<String, Double>) {
        val topAgency: String get() = byAgency.maxByOrNull { it.value }?.key ?: ""
        val defenseShare: Int get() = if (total > 0) Math.round(100 * defense / total).toInt() else 0
    }

    /** Companies by money obligated since 2016, biggest first (net cuts below zero left out, as on the site). */
    fun companies(years: List<Row>): List<Company> =
        years.groupBy { it.string("recipient_entity_id") ?: it.string("recipient") ?: "" }.map { (id, rs) ->
            val agency = mutableMapOf<String, Double>()
            for (r in rs) agency.merge(r.string("sub_agency") ?: r.string("agency") ?: "", r.number("obligated") ?: 0.0, Double::plus)
            Company(id, Format.orgName(rs[0].string("recipient") ?: ""), rs[0].string("recipient_url"),
                rs.sumOf { it.number("obligated") ?: 0.0 }, rs.filter { it.bool("defense") == true }.sumOf { it.number("obligated") ?: 0.0 }, agency)
        }.filter { it.total > 0 }.sortedByDescending { it.total }

    /** Money obligated per calendar year: (year, defense, other agencies). */
    fun byYear(years: List<Row>): List<Triple<Int, Double, Double>> =
        years.filter { it.number("year") != null }.groupBy { it.number("year")!!.toInt() }.toSortedMap().map { (y, rs) ->
            Triple(y, rs.filter { it.bool("defense") == true }.sumOf { it.number("obligated") ?: 0.0 }, rs.filter { it.bool("defense") != true }.sumOf { it.number("obligated") ?: 0.0 })
        }

    fun total(years: List<Row>): Double = years.sumOf { it.number("obligated") ?: 0.0 }

    fun defenseShare(years: List<Row>): Int {
        val t = total(years)
        return if (t > 0) Math.round(100 * years.filter { it.bool("defense") == true }.sumOf { it.number("obligated") ?: 0.0 } / t).toInt() else 0
    }

    private val label = DateTimeFormatter.ofPattern("MMM d, yyyy", Locale.US)

    /** "Sep 17, 2026" for a story's published time. */
    fun dateLabel(s: String?): String = try {
        if (s == null) "" else LocalDate.parse(s.take(10)).format(label)
    } catch (_: Exception) { "" }

    fun profilePath(path: String?): String? = path?.takeIf { it.startsWith("/") }
}
