package me.baycounty.kit

/**
 * One government's budget in two fiscal years, line by line, from the budget-years dataset.
 * A port of api/_budget.js `compare`, so the app shows the same comparison as /public-money/budget-compare.
 */
object BudgetCompare {
    enum class Basis(val key: String) { ADOPTED("adopted"), ACTUAL("actual") }

    data class Line(val key: String, var name: String, var from: Double?, var to: Double?, val inTotal: Boolean) {
        val id: String get() = key
        val change: Double get() = (to ?: 0.0) - (from ?: 0.0)
        /** Percent change, one decimal, when both years have the line. */
        val pct: Double?
            get() {
                val f = from ?: return null; val t = to ?: return null
                if (f == 0.0) return null
                return Math.round((t - f) / Math.abs(f) * 1000).toDouble() / 10
            }
        val status: String get() = if (from == null) "added" else if (to == null) "removed" else "both"
    }

    data class Section(val key: String, val title: String, val lines: List<Line>)

    data class Result(
        val government: String,
        val govID: String,
        val basis: Basis,
        val from: Int,
        val to: Int,
        val years: List<Int>,
        val detailYears: List<Int>,
        val totals: List<Line>,
        val sections: List<Section>,
        val biggestIncrease: Line?,
        val biggestDecrease: Line?,
        val notes: List<String>,
        val sourcesFrom: List<String>,
        val sourcesTo: List<String>,
        /** Total budget by year, for the trend chart. */
        val history: List<Pair<Int, Double>>,
    )

    private val sectionsFor = mapOf(Basis.ADOPTED to listOf("department", "fund"), Basis.ACTUAL to listOf("spending", "revenue"))
    private val sectionTitles = mapOf(
        "department" to "General Fund, by department", "fund" to "By fund", "service" to "By service",
        "spending" to "Spending", "revenue" to "Revenue",
    )

    private fun fy(r: Row): Int = r.number("fiscal_year")?.toInt() ?: 0

    /** Governments with at least two years on record for a basis, in the site's order. */
    fun governments(rows: List<Row>, basis: Basis = Basis.ADOPTED): List<String> {
        val years = HashMap<String, MutableSet<Int>>()
        for (r in rows) {
            if (r.string("basis") != basis.key) continue
            val g = r.string("gov_id") ?: continue
            val y = r.number("fiscal_year") ?: continue
            years.getOrPut(g) { mutableSetOf() }.add(y.toInt())
        }
        return years.filter { it.value.size >= 2 }.keys.sortedWith(compareBy<String> { Governments.orderIndex(it) }.thenBy { it })
    }

    internal fun lines(
        rows: List<Row>, from: Int, to: Int,
        key: (Row) -> String = { it.string("line_key") ?: "" },
        name: (Row) -> String = { it.string("name") ?: "" },
    ): List<Line> {
        val order = mutableListOf<String>()
        val m = HashMap<String, Line>()
        for (r in rows) {
            val y = r.number("fiscal_year")?.toInt() ?: continue
            if (y != from && y != to) continue
            val k = key(r)
            if (m[k] == null) { order.add(k); m[k] = Line(k, "", null, null, r.bool("in_total") != false) }
            val l = m[k]!!
            val amount = r.number("amount") ?: 0.0
            if (y == to) { l.to = (l.to ?: 0.0) + amount; l.name = name(r) }
            else { l.from = (l.from ?: 0.0) + amount; if (l.name.isEmpty()) l.name = name(r) }
        }
        return order.mapNotNull { m[it] }.withIndex().sortedWith { a, b ->
            val x = a.value; val y = b.value
            when {
                Math.abs(x.change) != Math.abs(y.change) -> Math.abs(y.change).compareTo(Math.abs(x.change))
                (x.to ?: 0.0) != (y.to ?: 0.0) -> (y.to ?: 0.0).compareTo(x.to ?: 0.0)
                else -> a.index.compareTo(b.index)
            }
        }.map { it.value }
    }

    fun years(rows: List<Row>, gov: String, basis: Basis = Basis.ADOPTED): List<Int> =
        rows.filter { it.string("gov_id") == gov && it.string("basis") == basis.key }.mapNotNull { it.number("fiscal_year")?.toInt() }.toSet().sorted()

    /** Compares two years. With no years given: the latest year with line-by-line detail against the detail year before it. */
    fun compare(all: List<Row>, gov: String, basis: Basis = Basis.ADOPTED, from: Int? = null, to: Int? = null): Result? {
        val rows = all.filter { it.string("gov_id")?.lowercase() == gov.lowercase() }
        val first = rows.firstOrNull() ?: return null
        val mine = rows.filter { it.string("basis") == basis.key }
        val years = mine.map(::fy).toSet().sorted()
        val detail = mine.filter { it.string("section") != "total" }.map(::fy).toSet().sorted()
        if (years.size < 2) return null
        val pool = if (detail.size >= 2) detail else years
        val toY = to ?: pool.last()
        val fromY = from ?: (pool.reversed().firstOrNull { it < toY } ?: years.lastOrNull { it < toY }) ?: return null
        if (fromY !in years || toY !in years || fromY == toY) return null
        val yr = mine.filter { fy(it) == fromY || fy(it) == toY }
        fun sec(s: String) = yr.filter { it.string("section") == s }
        val sections = mutableListOf<Section>()
        for (s in sectionsFor[basis]!!) sections.add(Section(s, sectionTitles[s]!!, lines(sec(s), fromY, toY)))
        if (basis == Basis.ADOPTED) {
            val svc = { r: Row -> r.string("service") ?: "Other services" }
            sections.add(Section("service", sectionTitles["service"]!!, lines(sec("department"), fromY, toY, svc, svc)))
        }
        val totalOrder = listOf("total", "general_fund", "revenue_total", "spending_total")
        val totals = lines(sec("total"), fromY, toY).sortedBy { totalOrder.indexOf(it.key) }
        val history = mutableListOf<Pair<Int, Double>>()
        val status = HashMap<Int, String?>()
        for (y in years) {
            val t = mine.filter { fy(it) == y && it.string("section") == "total" }
            status[y] = t.firstOrNull()?.string("status")
            t.firstOrNull { it.string("line_key") == "total" || it.string("line_key") == "spending_total" }?.number("amount")?.let { history.add(y to it) }
        }
        val notes = mutableListOf<String>()
        val main = sections[0].lines
        fun has(y: Int) = main.any { (if (y == fromY) it.from else it.to) != null }
        for (y in listOf(fromY, toY)) if (!has(y)) {
            notes.add("FY$y has only a total on record, no ${if (basis == Basis.ACTUAL) "breakdown" else "fund or department lines"}.")
        }
        if (has(fromY) && has(toY)) {
            val both = main.count { it.status == "both" }
            if (both.toDouble() < main.size.toDouble() / 2) {
                notes.add("Most ${if (basis == Basis.ACTUAL) "lines" else "department names"} differ between the two documents, so compare by service or total.")
            }
        }
        val a = status[fromY]; val b = status[toY]
        if (a != null && b != null && a != b) notes.add("FY$fromY is $a and FY$toY is $b, so they aren't measured the same way.")
        fun src(y: Int): List<String> {
            val seen = HashSet<String>()
            return yr.filter { fy(it) == y }.mapNotNull { it.string("source_url") }.filter { seen.add(it) }
        }
        val moved = main.filter { it.status == "both" && it.inTotal && (it.from ?: 0.0) > 0 && (it.to ?: 0.0) > 0 }
        return Result(
            government = first.string("government") ?: "", govID = first.string("gov_id") ?: gov, basis = basis,
            from = fromY, to = toY, years = years, detailYears = detail, totals = totals, sections = sections,
            biggestIncrease = moved.firstOrNull { it.change > 0 }, biggestDecrease = moved.firstOrNull { it.change < 0 },
            notes = notes, sourcesFrom = src(fromY), sourcesTo = src(toY), history = history,
        )
    }
}
