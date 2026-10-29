package me.baycounty.kit

import java.util.Locale
import kotlin.math.roundToInt

/** Police, fire and the Sheriff (/public-safety), from the safety-agencies, crime-counts and police-staffing datasets.
 *  Mirrors the Swift `PublicSafety` and site/safety_page.py + site/safety_charts.py. Counts only: no incident names a person. */
object PublicSafety {
    val datasets = listOf("safety-agencies", "crime-counts", "police-staffing")
    /** Florida agencies switched from yearly summaries to monthly incident reports (NIBRS) in 2025. */
    const val NEW_SYSTEM = 2025

    enum class Offense(val code: String, val label: String, val noun: String) {
        VIOLENT("V", "Violent crime", "violent"), PROPERTY("P", "Property crime", "property")
    }

    data class Town(val id: String, val name: String, val police: Row?, val fire: Row?)

    private fun Row.year(): Int = (number("year") ?: 0.0).toInt()

    /** Governments in the dataset's order, each with its police and fire department. */
    fun towns(agencies: List<Row>): List<Town> {
        val by = LinkedHashMap<String, MutableMap<String, Row>>()
        for (r in agencies) {
            val g = r.string("gov_id") ?: continue
            val s = r.string("service") ?: continue
            by.getOrPut(g) { mutableMapOf() }[s] = r
        }
        return by.map { (g, m) -> Town(g, (m["police"] ?: m["fire"])?.string("government") ?: g, m["police"], m["fire"]) }
    }

    fun fiscalYear(agencies: List<Row>): String = agencies.firstNotNullOfOrNull { it.string("budget_fiscal_year") } ?: "FY2026"

    data class Totals(val police: Double, val fire: Double, val contracts: Double, val fireDepartments: Int, val officers: Int)

    fun totals(agencies: List<Row>): Totals {
        val pol = agencies.filter { it.string("service") == "police" }
        val fire = agencies.filter { it.string("service") == "fire" }
        val contracts = pol.filter { it.string("agency_gov_id") != it.string("gov_id") && it.string("gov_id") != "county" }
        return Totals(pol.mapNotNull { it.number("budget_amount") }.sum(), fire.mapNotNull { it.number("budget_amount") }.sum(),
            contracts.mapNotNull { it.number("budget_amount") }.sum(), fire.size, pol.mapNotNull { it.number("officers") }.sum().toInt())
    }

    /** Reporting agencies in the order they appear: (id, name). */
    fun agencies(crimes: List<Row>): List<Pair<String, String>> {
        val seen = LinkedHashMap<String, String>()
        for (r in crimes) r.string("agency_id")?.let { if (it !in seen) seen[it] = r.string("agency") ?: it }
        return seen.toList()
    }

    data class Headline(val year: Int, val firstYear: Int, val violent: Int, val property: Int, val violentChange: Int?)

    /** Violent and property crimes in the latest full year before 2025, and the change since the first full year (same agencies). */
    fun headline(crimes: List<Row>): Headline? {
        val years = crimes.mapNotNull { it.number("year")?.toInt() }.toSortedSet().toList()
        if (years.isEmpty()) return null
        val partial = crimes.filter { (it.number("months_reported") ?: 12.0) < 12 }.mapNotNull { it.number("year")?.toInt() }.toSet()
        val full = years.filter { it !in partial && it < 2025 }
        val ky = full.lastOrNull() ?: years.last()
        val first = full.firstOrNull() ?: years.first()
        fun cell(a: String, y: Int, c: String) = crimes.firstOrNull { it.string("agency_id") == a && it.year() == y && it.string("offense_code") == c }
        val ids = agencies(crimes).map { it.first }
        val v = ids.mapNotNull { cell(it, ky, "V")?.number("count") }.sum()
        val p = ids.mapNotNull { cell(it, ky, "P")?.number("count") }.sum()
        val vFirst = ids.filter { cell(it, ky, "V") != null }.mapNotNull { cell(it, first, "V")?.number("count") }.sum()
        return Headline(ky, first, v.toInt(), p.toInt(), if (vFirst > 0) ((v - vFirst) / vFirst * 100).roundToInt() else null)
    }

    /** Full reported years of one offense for one agency: year -> row. */
    fun fullYears(crimes: List<Row>, agency: String, offense: Offense): Map<Int, Row> =
        crimes.filter { it.string("agency_id") == agency && it.string("offense_code") == offense.code && it.number("count") != null
            && it.number("months_reported") == 12.0 && it.number("per_1000") != null }.associateBy { it.year() }

    data class RatePoint(val year: Int, val rate: Double, val florida: Double?, val count: Int)
    data class Trend(val id: String, val name: String, val points: List<RatePoint>)

    /** Small multiples: each agency with a full year of this offense, its rate per 1,000 people by year. */
    fun trends(crimes: List<Row>, offense: Offense): List<Trend> = agencies(crimes).mapNotNull { (id, name) ->
        val fy = fullYears(crimes, id, offense)
        if (fy.isEmpty()) null else Trend(id, shortName(name), fy.keys.sorted().map { y ->
            val r = fy.getValue(y)
            RatePoint(y, r.number("per_1000") ?: 0.0, r.number("florida_per_1000"), (r.number("count") ?: 0.0).toInt())
        })
    }.sortedBy { if (it.id == "mb-police") 1 else 0 }

    fun trendMax(t: List<Trend>): Double = t.flatMap { tr -> tr.points.flatMap { listOf(it.rate, it.florida ?: 0.0) } }.maxOrNull() ?: 1.0

    data class Solved(val name: String, val share: Double, val cleared: Int, val count: Int, val span: String)

    /** Share cleared over each agency's latest three full yearly reports (before 2025), highest first; fewer than 20 crimes left out. */
    fun solved(crimes: List<Row>, offense: Offense): List<Solved> = agencies(crimes).mapNotNull { (id, name) ->
        val fy = fullYears(crimes, id, offense)
        val ys = fy.keys.filter { it < NEW_SYSTEM }.sorted().takeLast(3)
        val n = ys.mapNotNull { fy[it]?.number("count") }.sum()
        val c = ys.mapNotNull { fy[it]?.number("cleared") }.sum()
        if (n < 20 || ys.isEmpty()) null else Solved(shortName(name), c / n, c.toInt(), n.toInt(), if (ys.first() == ys.last()) "${ys.first()}" else "${ys.first()}–${ys.last()}")
    }.sortedByDescending { it.share }

    data class PerResident(val name: String, val police: Double?, val fire: Double?)

    fun perResident(agencies: List<Row>): List<PerResident> = towns(agencies).mapNotNull { t ->
        val p = t.police?.number("cost_per_resident")
        val f = t.fire?.number("cost_per_resident")
        if (p == null && f == null) null else PerResident(t.name, p, f)
    }

    data class TownCrime(val agencyName: String, val year: Int?, val violent: Row?, val property: Row?, val sheriffCovers: Boolean)

    fun townCrime(town: Town, crimes: List<Row>): TownCrime {
        val pol = town.police
        val own = pol?.takeIf { it.string("fbi_ori") != null && it.string("agency_gov_id") == it.string("gov_id") }?.string("agency_id")
        val aid = own ?: "bcso"
        val name = if (own != null) pol?.string("agency") ?: "" else "the Sheriff's Office"
        val v = fullYears(crimes, aid, Offense.VIOLENT)
        val p = fullYears(crimes, aid, Offense.PROPERTY)
        var ly = v.keys.maxOrNull()
        if (ly == NEW_SYSTEM && v.containsKey(NEW_SYSTEM - 1)) ly = NEW_SYSTEM - 1
        return TownCrime(name, ly, ly?.let { v[it] }, ly?.let { p[it] }, aid == "bcso" && town.id != "county")
    }

    /** "about the same as Florida", "1.4 times Florida's rate" or "30% below Florida's rate". */
    fun versusFlorida(r: Row): String? {
        val rate = r.number("per_1000") ?: return null
        val fl = r.number("florida_per_1000")?.takeIf { it > 0 } ?: return null
        val ratio = rate / fl
        return when {
            ratio in 0.9..1.1 -> "about the same as Florida"
            ratio > 1.1 -> String.format(Locale.US, "%.1f times Florida's rate", ratio)
            else -> "${(100 * (1 - ratio)).roundToInt()}% below Florida's rate"
        }
    }

    fun staffing(staff: List<Row>, agency: String): Row? = staff.filter { it.string("agency_id") == agency }.maxByOrNull { it.number("year") ?: 0.0 }

    data class Staff(val id: String, val name: String, val year: Int, val officers: Int, val civilians: Int, val firstYear: Int, val firstOfficers: Int)

    fun staffingSummary(staff: List<Row>): List<Staff> = staff.mapNotNull { it.string("agency_id") }.distinct().mapNotNull { a ->
        val rows = staff.filter { it.string("agency_id") == a }.sortedBy { it.number("year") ?: 0.0 }
        val f = rows.firstOrNull() ?: return@mapNotNull null
        val l = rows.last()
        Staff(a, f.string("agency") ?: a, l.year(), (l.number("officers") ?: 0.0).toInt(), (l.number("civilians") ?: 0.0).toInt(), f.year(), (f.number("officers") ?: 0.0).toInt())
    }

    /** 'Panama City Police Department' -> 'Panama City police'. */
    fun shortName(name: String): String = name.replace(" Police Department (reported until 2019)", " police (until 2019)")
        .replace(" Police Department", " police").replace("Bay County Sheriff's Office", "Sheriff's Office")

    /** $74.4M / $812K, like the site. */
    fun money(n: Double?): String = when {
        n == null -> "—"
        n >= 1e6 -> String.format(Locale.US, "$%.1fM", n / 1e6)
        else -> "$${Format.number(Math.round(n / 1e3).toDouble())}K"
    }
}
