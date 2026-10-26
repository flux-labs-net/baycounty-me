package me.baycounty.kit

/**
 * How much property tax goes to the redevelopment agencies (CRAs), from the cra-agencies, cra-tax-increment and
 * cra-increment-checks datasets. The same figures as /public-money/cra-tax-increment.
 */
object CRAIncrement {
    enum class Scenario(val key: String, val label: String) { LOW("low", "Low 3%"), MID("mid", "Middle 6%"), HIGH("high", "High 9%") }

    enum class Payer(val key: String, val label: String) {
        ALL("all", "All payers"), COUNTY("county", "Bay County"), CITIES("cities", "Cities");

        fun amount(r: Row): Double = when (this) {
            ALL -> r.number("increment") ?: 0.0
            COUNTY -> r.number("county_amount") ?: 0.0
            CITIES -> r.number("city_amount") ?: 0.0
        }
    }

    data class Headline(
        val lastYear: Int, val firstYear: Int, val total: Double, val county: Double, val frontBeachRoad: Double,
        val agencies: Int, val paidOnRecord: Double, val countyOnRecord: Double, val toComeLow: Double, val toComeHigh: Double,
    )

    data class YearTotal(val fiscalYear: Int, val amount: Double, val projected: Boolean)

    val shortNames = mapOf(
        "pcb-fbr" to "Front Beach Road", "pcb-pier" to "Pier Park", "pc" to "Panama City", "lh" to "Lynn Haven",
        "callaway" to "Callaway", "springfield" to "Springfield", "parker" to "Parker",
    )

    private fun fy(r: Row): Int = r.number("fiscal_year")?.toInt() ?: 0
    private fun sum(rows: List<Row>, key: String): Double = rows.mapNotNull { it.number(key) }.sum()

    fun headline(agencies: List<Row>, years: List<Row>): Headline? {
        val h = years.filter { it.string("scenario") == "history" }
        val last = h.maxOfOrNull(::fy) ?: return null
        val first = h.minOf(::fy)
        val y = h.filter { fy(it) == last }
        return Headline(
            last, first, sum(y, "increment"), sum(y, "county_amount"),
            sum(y.filter { it.string("cra_id") == "pcb-fbr" }, "increment"), agencies.size,
            sum(h, "increment"), sum(h, "county_amount"), sum(agencies, "to_come_low"), sum(agencies, "to_come_high"),
        )
    }

    /** Yearly totals: reported years, then the chosen growth scenario until each CRA's sunset. */
    fun byYear(years: List<Row>, scenario: Scenario = Scenario.MID, payer: Payer = Payer.ALL): List<YearTotal> {
        val h = years.filter { it.string("scenario") == "history" }
        val lastH = h.maxOfOrNull(::fy) ?: 0
        val rows = h + years.filter { it.string("scenario") == scenario.key }
        val by = HashMap<Int, Double>()
        for (r in rows) by[fy(r)] = (by[fy(r)] ?: 0.0) + payer.amount(r)
        return by.keys.sorted().map { YearTotal(it, by[it]!!, it > lastH) }
    }

    fun toCome(agency: Row, scenario: Scenario): Double? = agency.number("to_come_${scenario.key}")
}
