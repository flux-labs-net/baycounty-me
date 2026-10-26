package me.baycounty.kit

/** The Tax Dollars calculator (site/tax.js), line for line. */
object TaxCalculator {
    data class Taxable(val school: Double, val other: Double)
    data class Line(val id: String, val name: String, val group: String, val mills: Double, val base: Double, val amount: Double)
    data class GroupAmount(val group: String, val amount: Double)
    data class YearTotal(val fy: String, val total: Double)
    data class Estimate(val lines: List<Line>, val total: Double, val byGroup: List<GroupAmount>, val trend: List<YearTotal>)

    /** Homestead: $25,000 off everything, plus up to the second exemption on value above $50,000 (not school taxes). */
    fun taxable(value: Double, homestead: Boolean, second: Double): Taxable {
        if (!homestead) return Taxable(value, value)
        val first = minOf(value, 25_000.0)
        val secondEx = maxOf(0.0, minOf(value - 50_000, second))
        return Taxable(maxOf(0.0, value - first), maxOf(0.0, value - first - secondEx))
    }

    fun bill(model: TaxModel, district: TaxModel.District, year: Int, taxable: Taxable): List<Line> =
        district.stack.mapNotNull { id ->
            val a = model.auth[id] ?: return@mapNotNull null
            val m = a.m.getOrNull(year) ?: 0.0
            val base = if (a.school) taxable.school else taxable.other
            Line(id, a.n, a.g, m, base, base / 1000 * m)
        }

    fun estimate(model: TaxModel, district: TaxModel.District, value: Double, homestead: Boolean): Estimate {
        val l = model.latest
        val lines = bill(model, district, l, taxable(value, homestead, model.second[l]))
        val shown = lines.filter { it.mills > 0 }
        val total = shown.sumOf { it.amount }
        val byGroup = model.groupIDs.map { g -> GroupAmount(g, shown.filter { it.group == g }.sumOf { it.amount }) }.filter { it.amount > 0 }
        val trend = model.years.indices.map { i ->
            val t = bill(model, district, i, taxable(value, homestead, model.second[i]))
            YearTotal(model.fy[i], t.sumOf { it.amount })
        }
        return Estimate(lines, total, byGroup, trend)
    }

    fun cityName(model: TaxModel, district: TaxModel.District): String =
        district.stack.mapNotNull { model.auth[it] }.firstOrNull { it.g == "city" }?.n ?: "Your city"
}

/** The Amendment 3 calculator (site/amend.js). */
object Amendment3Calculator {
    enum class Kind(val key: String, val label: String) {
        HOME("home", "My homestead (Florida resident before 2027)"),
        NEW("new", "A newer homestead"),
        NON("non", "Not a homestead (rental, second home, business)"),
    }

    data class Scenario(val label: String, val schoolTaxable: Double, val otherTaxable: Double, val lines: List<TaxCalculator.Line>) {
        val total: Double get() = lines.sumOf { it.amount }
        val schoolTotal: Double get() = lines.filter { it.group == "school" }.sumOf { it.amount }
    }

    fun scenarios(model: Amendment3Model, district: TaxModel.District, value: Double, kind: Kind): List<Scenario> {
        val v = value
        val today = if (kind == Kind.NON) v to v
        else maxOf(0.0, v - 25_000) to maxOf(0.0, v - minOf(v, 25_000.0) - maxOf(0.0, minOf(v - 50_000, model.second)))
        val rows: List<Triple<String, Double, Double>> = if (kind == Kind.NON) {
            listOf(Triple("Today", today.first, today.second), Triple("2027 bill", today.first, today.second), Triple("2028 bill and after", today.first, today.second))
        } else {
            val sch = maxOf(0.0, v - 25_000)
            val e27 = if (kind == Kind.NEW) 50_000.0 else 150_000.0
            val e28 = if (kind == Kind.NEW) 51_220.0 else 250_000.0
            listOf(Triple("Today", today.first, today.second), Triple("2027 bill", sch, maxOf(0.0, v - e27)), Triple("2028 bill and after", sch, maxOf(0.0, v - e28)))
        }
        val l = district.total.size - 1
        return rows.map { (label, sch, oth) ->
            val lines = district.stack.mapNotNull { id ->
                val a = model.auth[id] ?: return@mapNotNull null
                val m = a.m.getOrNull(l) ?: 0.0
                val base = if (a.school) sch else oth
                TaxCalculator.Line(id, a.n, if (a.school) "school" else a.g, m, base, base / 1000 * m)
            }.filter { it.mills > 0 }
            Scenario(label, sch, oth, lines)
        }
    }

    fun note(kind: Kind, scenarios: List<Scenario>): String = when (kind) {
        Kind.NON -> "Amendment 3 doesn't lower this property's taxes directly. It slows how fast the taxed value can rise: at most 5% a year instead of 10% for non-school taxes. That only matters if the market value is rising faster than 5%."
        Kind.NEW -> "Newer residents get \$50,000 off non-school taxes for their first four years with a homestead, then the larger exemption in year five."
        Kind.HOME -> if (scenarios.size > 2 && scenarios[2].otherTaxable == 0.0)
            "At this value the home would owe no county, city or special-district property tax, only school tax."
        else "The savings top out once the exemption reaches \$250,000. Above that, every extra dollar of value is taxed as it is today."
    }
}
