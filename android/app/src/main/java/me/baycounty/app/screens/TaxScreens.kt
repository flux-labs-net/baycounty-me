package me.baycounty.app.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import me.baycounty.app.Route
import me.baycounty.app.ui.*
import me.baycounty.kit.Amendment3Calculator
import me.baycounty.kit.BayCountyClient
import me.baycounty.kit.ChartTicks
import me.baycounty.kit.Format
import me.baycounty.kit.TaxCalculator
import me.baycounty.kit.TaxModel

/** A heading over a group of rows, like an iOS List section header. */
@Composable
internal fun FormHeader(text: String) = Text(text, style = T.footnote.copy(fontWeight = FontWeight.SemiBold), color = Brand.secondary, modifier = Modifier.padding(start = 4.dp))

@Composable
internal fun FormSection(title: String?, footer: String? = null, content: @Composable () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        if (title != null) FormHeader(title)
        content()
        if (footer != null) Text(footer, style = T.caption, color = Brand.secondary, modifier = Modifier.padding(horizontal = 4.dp))
    }
}

/** A labelled bar, its amount, and a line under it (Where the tax goes, budget lines). */
@Composable
private fun AmountBar(label: String, value: String, fraction: Double, color: Color, note: String?) {
    Column(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 9.dp).semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(3.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(label, style = T.subhead, color = Brand.text, modifier = Modifier.weight(1f))
            Text(value, style = T.subhead, color = Brand.text)
        }
        Box(Modifier.fillMaxWidth().height(8.dp)) {
            if (fraction > 0) Box(Modifier.fillMaxWidth(fraction.toFloat().coerceIn(0.01f, 1f)).fillMaxHeight().background(color, RoundedCornerShape(3.dp)))
        }
        if (note != null) Text(note, style = T.caption2, color = Brand.secondary)
    }
}

/** Tax Dollars: estimate a property tax bill, see where it goes, and open each government's budget. */
@Composable
fun TaxCalculatorScreen(route: Route.TaxCalculator) {
    val store = LocalStore.current
    LaunchedEffect(Unit) { store.loadTax() }
    var districtID by rememberSaveable { mutableStateOf(route.districtID ?: "") }
    var valueText by rememberSaveable { mutableStateOf(Format.number(Math.rint(route.value ?: 250_000.0))) }
    var homestead by rememberSaveable { mutableStateOf(route.homestead ?: true) }
    val m = store.taxModel
    Screen("Tax Dollars", onRefresh = { store.loadTax() }, spacing = 22) {
        if (m == null || m.districts.isEmpty()) {
            item { val e = store.appError("tax.json"); if (e != null) Unavailable("Couldn't load the calculator", e) else Loading() }
            return@Screen
        }
        val d = m.districts.firstOrNull { it.id == districtID }
            ?: m.districts.firstOrNull { it.id == store.savedDistrict } ?: m.districts.first()
        val e = TaxCalculator.estimate(m, d, typedAmount(valueText), homestead)
        val l = m.latest
        val gname = { g: String -> if (g == "city") TaxCalculator.cityName(m, d) else m.groupName(g) }
        item { PageIntro("/public-money/tax-dollars") }
        item {
            FormSection("Your bill") {
                FieldMenu(
                    "Where the property is", "${d.label} · ${Format.number(d.total[l])} mills",
                    m.districts.map { it.id to "${it.label} · ${Format.number(it.total[l])} mills" }, selected = d.id,
                ) { districtID = it; store.saveDistrict(it) }
                MoneyField("Assessed value", valueText) { valueText = it }
                ToggleRow("Homestead exemption", homestead) { homestead = it }
            }
        }
        item {
            FormSection("Estimate, ${m.fy[l]} rates") {
                Column(Modifier.fillMaxWidth().card(14.dp).padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(Format.money(e.total), style = T.bigNumber, color = Brand.text)
                    Text(
                        if (e.total > 0) "about ${Format.money(e.total / 12)} a month · ${Format.number(d.total[l])} mills in all" else "Enter a value to see your estimate",
                        style = T.caption, color = Brand.secondary,
                    )
                    StackBar(e.byGroup.map { Triple(gname(it.group), it.amount, taxColor(it.group)) })
                    for (g in e.byGroup) {
                        LegendRow(taxColor(g.group), gname(g.group), Format.money(g.amount), if (e.total > 0) "${Math.round(g.amount / e.total * 100)}%" else null)
                    }
                }
            }
        }
        item {
            FormSection("Each taxing authority") {
                CardList {
                    e.lines.forEachIndexed { i, ln ->
                        Column(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 9.dp).semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                Box(Modifier.size(8.dp).background(taxColor(ln.group), CircleShape))
                                Text(ln.name, style = T.subhead, color = Brand.text, modifier = Modifier.weight(1f))
                                Text(Format.money(ln.amount), style = T.subhead, color = Brand.text)
                            }
                            Text("${Format.number(ln.mills)} mills on ${Format.money(ln.base)}", style = T.caption, color = Brand.secondary)
                        }
                        if (i < e.lines.lastIndex) RowDivider()
                    }
                }
                if (d.id == "Panama City Beach") Text("Panama City Beach has no city property tax.", style = T.footnote, color = Brand.secondary)
                if (d.id.startsWith("unincorporated")) Text("No city. The county provides fire service.", style = T.footnote, color = Brand.secondary)
            }
        }
        item {
            FormSection("The same home at each year's rates") {
                val trend = ChartTicks.sinceCutoff(e.trend) { ChartTicks.yearOf(it.fy) }
                Column(Modifier.fillMaxWidth().card(14.dp).padding(14.dp)) {
                    BarChart(trend.map { ChartPoint(it.fy, it.total) }, height = 150.dp, format = Format::compactMoney, maxBars = 40)
                }
            }
        }
        item {
            FormSection("Where all of Bay County's property tax goes, ${m.fy[l]}") {
                val total = m.bars.sumOf { it.v }
                val first = m.bars.firstOrNull()?.v ?: 1.0
                CardList {
                    m.bars.forEachIndexed { i, b ->
                        AmountBar(b.n, Format.compactMoney(b.v), b.v / first, taxColor(b.g), "${Math.round(b.v / maxOf(total, 1.0) * 100)}% of all property tax")
                        if (i < m.bars.lastIndex) RowDivider()
                    }
                }
            }
        }
        item {
            FormSection("Each government's money") {
                CardList {
                    m.govs.forEachIndexed { i, g ->
                        RouteRow(Route.GovBudget(g.id), g.short, value = g.total?.let { Format.compactMoney(it) })
                        if (i < m.govs.lastIndex) RowDivider()
                    }
                }
            }
        }
        m.gaps?.takeIf { it.isNotEmpty() }?.let { gaps ->
            item {
                FormSection("Gaps") {
                    Column(Modifier.fillMaxWidth().card(14.dp).padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        for (g in gaps) Text(g, style = T.footnote, color = Brand.text)
                    }
                }
            }
        }
    }
}

private val savingsPattern = Regex("fund balance|reserve|carr(y|ied)|cash carry", RegexOption.IGNORE_CASE)
private fun isSavings(k: String) = savingsPattern.containsMatchIn(k)

/** One government's budget: general fund sources and spending, actual money in and out, and context. */
@Composable
fun GovBudgetScreen(id: String) {
    val store = LocalStore.current
    val o = rememberOpener()
    LaunchedEffect(Unit) { store.loadTax() }
    var year by rememberSaveable { mutableStateOf<String?>(null) }
    val gov = store.taxModel?.govs?.firstOrNull { it.id == id }
    Screen(gov?.short ?: "Budget", spacing = 22) {
        if (gov == null) {
            item { val e = store.appError("tax.json"); if (e != null) Unavailable("Couldn't load this budget", e) else Loading() }
            return@Screen
        }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                CardList {
                    FactRow("Total budget, FY2026", gov.total?.let { Format.compactMoney(it) } ?: "Not published online")
                    RowDivider()
                    FactRow("General fund", gov.gf?.let { Format.compactMoney(it) } ?: "—")
                    RowDivider()
                    FactRow("Property tax levied", if (gov.id == "panama_city_beach") "$0" else gov.levy?.let { Format.compactMoney(it) } ?: "—")
                    RowDivider()
                    FactRow("Tax rate", gov.mills?.let { if (it == 0.0) "None" else "${Format.number(it)} mills" } ?: "—")
                }
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
                    val c = if (gov.statusOK) Brand.good else Brand.amber
                    Icon(icon(if (gov.statusOK) "checkmark.circle" else "exclamationmark.circle"), null, tint = c, modifier = Modifier.size(16.dp))
                    Text(gov.statusText, style = T.footnote, color = c)
                }
            }
        }
        gov.next?.let { n ->
            item {
                FormSection("New budget, ${n.fy}") {
                    CardList {
                        n.total?.let { FactRow("Total", Format.compactMoney(it)); RowDivider() }
                        n.gf?.let { FactRow("General fund", Format.compactMoney(it)); RowDivider() }
                        n.mills?.let { FactRow("Tax rate", if (it == 0.0) "No city property tax" else "${Format.number(it)} mills"); RowDivider() }
                        Text(
                            if (n.adopted == true) "Adopted." else "Final hearing held; adoption not yet confirmed in posted minutes.",
                            style = T.footnote, color = Brand.text, modifier = Modifier.padding(14.dp),
                        )
                        n.src?.takeIf { it.size > 1 }?.let { s -> RowDivider(); WebRow(s[0], s[1], symbol = "doc.text") }
                    }
                }
            }
        }
        gov.mix?.let { mix ->
            item {
                Text(
                    "Across all funds, the schools expect ${Format.compactMoney(mix["Local"] ?: 0.0)} from local sources (mostly property tax), ${Format.compactMoney(mix["State"] ?: 0.0)} from the state and ${Format.compactMoney(mix["Federal"] ?: 0.0)} from the federal government.",
                    style = T.footnote, color = Brand.text, modifier = Modifier.fillMaxWidth().card(14.dp).padding(14.dp),
                )
            }
        }
        item { BudgetBars("Where the general fund money comes from", gov.rev) }
        item { BudgetBars("What the general fund pays for", gov.exp) }
        gov.other?.takeIf { it.isNotEmpty() }?.let { item { BudgetBars("School construction, debt and other funds", it) } }
        gov.act?.takeIf { it.isNotEmpty() }?.let { act ->
            val years = act.map { it.fy }
            val cur = year?.takeIf { it in years } ?: years.lastOrNull { y -> act.firstOrNull { it.fy == y }?.rev?.isNotEmpty() == true } ?: years.last()
            val a = act.first { it.fy == cur }
            item {
                FormSection("What actually came in and went out", "From the audited annual report, all operating funds including utilities.") {
                    ChipRow(years.map { it to it }, cur) { year = it }
                    CardList {
                        val facts = listOfNotNull(
                            a.rt?.let { "Money in" to Format.compactMoney(it) },
                            a.et?.let { "Money out" to Format.compactMoney(it) },
                            a.pop?.let { "Residents" to Format.number(it) },
                        )
                        facts.forEachIndexed { i, (k, v) -> FactRow(k, v); if (i < facts.lastIndex) RowDivider() }
                    }
                }
            }
            item { BudgetBars("Money in, by source, $cur", a.rev) }
            item { BudgetBars("Money out, by service, $cur", a.exp) }
        }
        gov.notes?.takeIf { it.isNotEmpty() }?.let { notes ->
            item {
                Column(Modifier.fillMaxWidth().card(14.dp).padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    for (n in notes) Text(n, style = T.footnote, color = Brand.text)
                }
            }
        }
        gov.ctx?.takeIf { it.isNotEmpty() }?.let { ctx ->
            item {
                FormSection("Worth knowing") {
                    CardList {
                        ctx.forEachIndexed { i, c ->
                            Column(Modifier.fillMaxWidth().padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text(c.firstOrNull() ?: "", style = T.footnote, color = Brand.text)
                                c.getOrNull(1)?.let { u -> Text("Source", style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = Brand.navy, modifier = Modifier.clickable { o.open(u) }) }
                            }
                            if (i < ctx.lastIndex) RowDivider()
                        }
                    }
                }
            }
        }
        gov.src?.let { src ->
            val links = src.mapNotNull { s -> val t = s.getOrNull(0); val u = s.getOrNull(1); if (t != null && u != null) t to u else null }
            if (links.isNotEmpty()) item {
                FormSection("Sources") {
                    CardList {
                        links.forEachIndexed { i, (t, u) -> WebRow(t, u, symbol = "doc.text"); if (i < links.lastIndex) RowDivider(50.dp) }
                    }
                }
            }
        }
    }
}

@Composable
private fun BudgetBars(title: String, obj: Map<String, Double>?) {
    val ent = (obj ?: emptyMap()).filter { it.value > 0 }.entries
        .sortedWith(compareBy({ if (isSavings(it.key)) 1 else 0 }, { -it.value }))
    FormSection(title) {
        if (ent.isEmpty()) {
            Text("This government does not post a budget online with this detail.", style = T.footnote, color = Brand.secondary, modifier = Modifier.fillMaxWidth().card(14.dp).padding(14.dp))
        } else {
            val max = ent.maxOf { it.value }
            val total = ent.filter { !isSavings(it.key) }.sumOf { it.value }
            CardList {
                ent.forEachIndexed { i, (k, v) ->
                    val s = isSavings(k)
                    AmountBar(k, Format.compactMoney(v), v / max, if (s) Brand.amber else Brand.blue, if (s) "Savings, not new money or spending" else "${Math.round(v / maxOf(total, 1.0) * 100)}%")
                    if (i < ent.lastIndex) RowDivider()
                }
            }
        }
    }
}

/** Amendment 3: the bill before and after, and what local governments would collect. */
@Composable
fun Amendment3Screen(route: Route.Amendment3) {
    val store = LocalStore.current
    LaunchedEffect(Unit) { store.loadAmendment3() }
    var districtID by rememberSaveable { mutableStateOf(route.districtID ?: "") }
    var valueText by rememberSaveable { mutableStateOf(Format.number(Math.rint(route.value ?: 300_000.0))) }
    var kind by rememberSaveable { mutableStateOf(if (route.homestead == false) Amendment3Calculator.Kind.NON else Amendment3Calculator.Kind.HOME) }
    val m = store.amendment3
    Screen("Amendment 3", onRefresh = { store.loadAmendment3() }, spacing = 22) {
        if (m == null || m.districts.isEmpty()) {
            item { val e = store.appError("amendment3.json"); if (e != null) Unavailable("Couldn't load the calculator", e) else Loading() }
            return@Screen
        }
        val d = m.districts.firstOrNull { it.id == districtID } ?: m.districts.firstOrNull { it.id == store.savedDistrict } ?: m.districts.first()
        val s = Amendment3Calculator.scenarios(m, d, typedAmount(valueText), kind)
        val today = s.firstOrNull()?.total ?: 0.0
        item { PageIntro("/public-money/amendment-3") }
        item {
            FormSection("Your property") {
                FieldMenu("Where it is", d.label, m.districts.map { it.id to it.label }, selected = d.id) { districtID = it; store.saveDistrict(it) }
                MoneyField("Value before exemptions", valueText) { valueText = it }
                RadioList(Amendment3Calculator.Kind.entries.map { it to it.label }, kind) { kind = it }
            }
        }
        item {
            FormSection("Your bill, before and after", Amendment3Calculator.note(kind, s)) {
                CardList {
                    s.forEachIndexed { i, sc ->
                        Column(Modifier.fillMaxWidth().padding(14.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(sc.label, style = T.subheadBold, color = Brand.text, modifier = Modifier.weight(1f))
                                Text(Format.money(sc.total), style = T.number, color = Brand.text)
                            }
                            val save = today - sc.total
                            Text(
                                if (i == 0) "per year" else if (save > 0.5) "${Format.money(save)} less (${Math.round(save / maxOf(today, 1.0) * 100)}%)" else "No change",
                                style = T.caption, color = if (i > 0 && save > 0.5) Brand.good else Brand.secondary,
                            )
                            StackBar(listOf(Triple("County, city and districts", sc.total - sc.schoolTotal, Brand.blue), Triple("Schools", sc.schoolTotal, Brand.navy)))
                            Text("Schools taxed on ${Format.money(sc.schoolTaxable)}; everything else on ${Format.money(sc.otherTaxable)}", style = T.caption2, color = Brand.secondary)
                        }
                        if (i < s.lastIndex) RowDivider()
                    }
                }
                Flow(14.dp) {
                    for ((label, c) in listOf("County, city and districts" to Brand.blue, "Schools" to Brand.navy)) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(5.dp)) {
                            Box(Modifier.size(10.dp).background(c, RoundedCornerShape(2.dp)))
                            Text(label, style = T.caption, color = Brand.secondary)
                        }
                    }
                }
            }
        }
        item {
            FormSection(
                "What local governments would collect less, FY2029",
                "State Revenue Estimating Conference estimates for the first full year. Schools lose nothing, because school taxes aren't covered.",
            ) {
                val first = m.govs.firstOrNull()?.imp?.getOrNull(1)?.takeIf { it > 0 } ?: 1.0
                CardList {
                    m.govs.forEachIndexed { i, g ->
                        val imp = g.imp.getOrNull(1) ?: 0.0
                        AmountBar(
                            g.n, if (imp > 0) "−" + Format.compactMoney(imp) else "$0", if (imp > 0) imp / first else 0.0, Brand.blue,
                            if (g.levy > 0) "${Math.round(imp / g.levy * 100)}% of its FY2026 property tax levy" else "No property tax levy",
                        )
                        if (i < m.govs.lastIndex) RowDivider()
                    }
                }
            }
        }
        item {
            CardList { WebRow("Officials' statements and the arguments, on BayCounty.me", "${BayCountyClient.SITE}/public-money/amendment-3", symbol = "safari") }
        }
    }
}
