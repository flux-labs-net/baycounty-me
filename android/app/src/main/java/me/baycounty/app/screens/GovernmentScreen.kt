package me.baycounty.app.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import me.baycounty.app.Route
import me.baycounty.app.ui.*
import me.baycounty.kit.BayCountyClient
import me.baycounty.kit.RecordShare
import me.baycounty.kit.BudgetCompare
import me.baycounty.kit.DatasetSpec
import me.baycounty.kit.Dates
import me.baycounty.kit.Format
import me.baycounty.kit.Government
import me.baycounty.kit.Meeting
import me.baycounty.kit.GovYear
import me.baycounty.kit.GovPart
import me.baycounty.kit.Officeholders
import me.baycounty.kit.Row as DataRow

private val govDatasets = listOf("officeholder-terms", "government-years", "budget-years", "debt", "bonds", "audit-findings", "savings-opportunities", "cra-agencies")

/**
 * One government, in the same order as its page on BayCounty.me: at a glance, who's in charge, the money,
 * how it compares, meetings, debt, audit findings, savings ideas and its redevelopment agency.
 * One fiscal-year picker at the top drives every year-based section, as the Year picker does on the site:
 * a year with no record says so and names the nearest years we have (GovYear).
 */
@Composable
fun GovernmentScreen(govID: String, part: GovPart? = null, startYear: Int? = null) {
    val store = LocalStore.current
    LaunchedEffect(govID) { store.load(govDatasets); store.loadPeople() }
    val g = store.government(govID)
    if (g == null) {
        Screen("Government") { item { if (store.governments.isEmpty()) Loading() else Unavailable("Not found", symbol = "building.columns") } }
        return
    }
    fun rows(id: String) = store.rows[id] ?: emptyList()
    var year by rememberSaveable(govID, part) { mutableStateOf<Int?>(null) }
    val picked = year ?: startYear ?: Officeholders.fiscalYear(govID)
    val yc = YearCtx(govID, g.name, picked)
    val shareURL = g.pageURL ?: "${BayCountyClient.SITE}/governments/${g.slug}"
    Screen(part?.let { "${g.name}: ${it.title}" } ?: g.name, onRefresh = { for (d in govDatasets) store.load(d, force = true) }, actions = {
        ShareMenuButton(g.name, shareURL) {
            RecordShare.page(g.name, listOf("Budget, taxes, debt, votes and who's in charge"), shareURL.removePrefix(BayCountyClient.SITE))
        }
    }) {
        if (part == null) item {
            PageHero("Governments", g.name, g.population?.let { "${Format.number(it)} residents (2025 estimate)" }, badge = { GovBadge(govID, 48.dp) })
        }
        item { MenuPicker("Fiscal year $picked", GovYear.years(govID).map { it to "FY$it" }, "Fiscal year $picked. Changes every section below.") { year = it } }
        if (part == null) {
            item { Glance(g, yc, rows("government-years"), rows("audit-findings")) }
            item { PartsMenu(g, yc, ::rows) }
        } else item {
            when (part) {
                GovPart.WHO -> WhosInCharge(govID, rows("officeholder-terms"), picked)
                GovPart.MONEY -> MoneySection(yc, rows("budget-years"))
                GovPart.COMPARE -> Compared(g)
                GovPart.MEETINGS -> GovMeetings(govID)
                GovPart.DEBT -> DebtSection(yc, rows("debt"), rows("bonds"), rows("government-years"))
                GovPart.AUDITS -> AuditSection(yc, rows("audit-findings"))
                GovPart.SAVINGS -> SavingsSection(govID, rows("savings-opportunities"))
                GovPart.CRA -> CraSection(govID, rows("cra-agencies"))
                GovPart.RECORDS -> RecordsSection(g)
            }
        }
    }
}

/** A city includes its port; the county includes the airport district (as on the site). */
private fun debtIDs(govID: String) = buildSet { add(govID); if (govID == "pc") add("port"); if (govID == "county") add("airport") }

/** One row per part with records, with a one-line answer for the year picked; each opens that part on its own screen. */
@Composable
private fun PartsMenu(g: Government, yc: YearCtx, rows: (String) -> List<DataRow>) {
    val store = LocalStore.current
    val govID = yc.govID
    val fy = yc.fy
    val upcoming = Meeting.upcoming(store.meetings).filter { it.govID == govID }.take(3)
    val findings = rows("audit-findings").filter { it.string("gov_id") == govID }
    val ideas = rows("savings-opportunities").filter { it.string("gov_id") == govID || govID in it.strings("gov_ids") }
    val cras = rows("cra-agencies").filter { it.string("gov_id") == govID }
    val related = store.catalog?.records(govID) ?: emptyList()
    val ids = debtIDs(govID)
    fun has(p: GovPart): Boolean = when (p) {
        GovPart.WHO -> Officeholders.years(rows("officeholder-terms"), govID).isNotEmpty()
        GovPart.MONEY -> rows("budget-years").any { it.string("gov_id") == govID }
        GovPart.COMPARE -> true
        GovPart.MEETINGS -> upcoming.isNotEmpty()
        GovPart.DEBT -> rows("debt").any { (it.string("gov_id") ?: "") in ids } || rows("bonds").any { (it.string("gov_id") ?: "") in ids }
        GovPart.AUDITS -> findings.isNotEmpty()
        GovPart.SAVINGS -> ideas.isNotEmpty()
        GovPart.CRA -> cras.isNotEmpty()
        GovPart.RECORDS -> related.isNotEmpty()
    }
    fun summary(p: GovPart): String = when (p) {
        GovPart.WHO -> Officeholders.inOffice(rows("officeholder-terms"), govID, yc.year).size.let { "$it seat${if (it == 1) "" else "s"} in $fy" }
        GovPart.MONEY -> GovYear.budget(rows("budget-years"), govID, yc.year).total?.let { "${Format.compactMoney(it)} $fy budget" } ?: "No $fy budget on file"
        GovPart.COMPARE -> "Per resident, tax rate and debt beside the others"
        GovPart.MEETINGS -> "${upcoming.size} on the calendar"
        GovPart.DEBT -> GovYear.row(rows("government-years"), govID, yc.year)?.number("debt_total")?.let { "${Format.compactMoney(it)} owed, end of $fy" } ?: "What it owes, bonds and loans"
        GovPart.AUDITS -> findings.count { GovYear.fiscalYearOf(it.string("fy")) == yc.year }.let { if (it > 0) "$it finding${if (it == 1) "" else "s"} in $fy" else "Findings from every audit on file" }
        GovPart.SAVINGS -> "${ideas.size} idea${if (ideas.size == 1) "" else "s"} to check"
        GovPart.CRA -> cras.mapNotNull { it.string("cra") }.joinToString(", ")
        GovPart.RECORDS -> "${related.size} datasets with records"
    }
    val parts = GovPart.shown(::has)
    PageSection("Explore ${g.name}", "square.grid.2x2", Tone.TEAL) {
        CardList {
            parts.forEachIndexed { i, p ->
                RouteRow(Route.GovPart(govID, p.id, yc.year), p.title, summary(p), symbol = p.symbol)
                if (i < parts.lastIndex) RowDivider(50.dp)
            }
        }
    }
}

/** The government and fiscal year every year-based section shows. */
private data class YearCtx(val govID: String, val short: String, val year: Int) { val fy: String get() = "FY$year" }

@Composable
private fun YearBars(title: String, cap: String, lines: List<GovYear.Line>) =
    CompareBars(title, lines.take(8).map { BarItem(it.name, it.name, it.amount) }, Format::compactMoney, cap, labelsAbove = true)

@Composable
private fun GapNote(text: String) {
    CardList { Text(text, style = T.caption, color = Brand.secondary, modifier = Modifier.fillMaxWidth().padding(12.dp)) }
}

/** The fiscal year's figures (government-years); a figure with no record that year says so, never another year's number. */
@Composable
private fun Glance(g: Government, yc: YearCtx, gy: List<DataRow>, audits: List<DataRow>) {
    data class K(val title: String, val value: String, val caption: String? = null)
    val r = GovYear.row(gy, yc.govID, yc.year)
    val fy = yc.fy
    fun has(c: String) = GovYear.yearsWith(gy, yc.govID, c).isNotEmpty()
    val findings = audits.filter { it.string("gov_id") == yc.govID && GovYear.fiscalYearOf(it.string("fy")) == yc.year }
    // the four headline figures first, the rest behind "All N figures", so the parts list below stays in reach
    val cards = listOfNotNull(
        r?.number("budget_total")?.let { K("Total budget", Format.compactMoney(it), "$fy · ${r.string("budget_status") ?: "adopted"}") }
            ?: if (has("budget_total")) K("Total budget", "No data", "No $fy budget on file") else null,
        r?.number("millage")?.let { K("Tax rate (mills)", Format.number(it), "Per \$1,000 of taxable value") }
            ?: if (has("millage")) K("Tax rate (mills)", "No data", "No $fy rate on file") else null,
        r?.number("debt_total")?.let { K("Debt", Format.compactMoney(it), "Audited, end of $fy") }
            ?: if (has("debt_total")) K("Debt", "No data", "No audited total for $fy") else null,
        r?.number("employees_fte")?.let { K("Employees", Format.number(it), "$fy budget, staff positions") },
        r?.number("budget_per_resident")?.let { K("Budget per resident", Format.money(Math.rint(it))) },
        r?.number("general_fund")?.let { K("General fund", Format.compactMoney(it)) },
        r?.number("property_tax_levy")?.let { K("Property tax levied", Format.compactMoney(it)) },
        if (findings.isNotEmpty()) K("Audit findings", "${findings.size}", "$fy · ${findings.count { it.bool("repeat") == true }} repeat") else null,
        g.votesRecorded?.let { K("Votes recorded", "$it", (g.splitVotes?.let { s -> "$s split · " } ?: "") + "all years") },
        g.typicalUtilityBill?.let { K("Typical utility bill", Format.money(it), "Per month, today's rates") },
        g.femaMichael?.let { K("FEMA, Hurricane Michael", Format.compactMoney(it)) },
    )
    var all by rememberSaveable(yc.govID) { mutableStateOf(false) }
    val shown = if (all) cards else cards.take(4)
    PageSection("At a glance", "gauge.with.dots.needle.33percent", Tone.BLUE, "Fiscal year ${yc.year}" + (r?.string("period")?.let { " · $it" } ?: "")) {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Grid2(shown) { k, m -> KPICard(k.title, k.value, m, k.caption?.takeIf { it.isNotEmpty() }) }
            if (cards.size > 4) CardList { ShowMoreRow(all, "All ${cards.size} figures") { all = !all } }
        }
    }
}

/** "2024-11-19" to "Nov 2024". */
fun shortMonth(d: String): String = Dates.parse(d)?.let { Dates.format(it, "MMM yyyy") } ?: d

@Composable
private fun WhosInCharge(govID: String, terms: List<DataRow>, picked: Int) {
    val store = LocalStore.current
    val nav = LocalNav.current
    if (Officeholders.years(terms, govID).isEmpty()) return
    val seats = Officeholders.inOffice(terms, govID, picked)
    PageSection("Who's in charge", "person.3", Tone.TEAL, "Who held each seat in fiscal year $picked. Pick another year at the top to see who served then.") {
        CardList {
            seats.forEachIndexed { i, s ->
                Column(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 11.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(s.seat + if (s.appointed) " (appointed)" else "", style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = Brand.secondary)
                    if (s.holders.isEmpty()) Text("No one on record", style = T.subhead, color = Brand.secondary)
                    for (h in s.holders) {
                        val parts = mutableListOf<String>()
                        if (h.partOfPeriod) {
                            val range = listOfNotNull(h.startDate?.let { "from ${shortMonth(it)}" }, h.endDate?.let { "until ${shortMonth(it)}" })
                            parts += "Part of the year" + if (range.isEmpty()) "" else ", " + range.joinToString(" ")
                        }
                        if (!h.confirmed) parts += "Not confirmed from the records found"
                        val linked = h.personID?.takeIf { store.person(it) != null }
                        val empty = h.vacant || h.personName.isEmpty()
                        Row(
                            (if (linked != null) Modifier.clickable { nav.push(Route.Person(linked)) } else Modifier).fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp),
                        ) {
                            // their official photo (official-photos), or initials, like the site's "Who's in charge" cards
                            if (!empty) PersonInitials(h.personName, 36.dp, h.personID?.let { store.person(it) }?.photoUrl)
                            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                Text(if (h.vacant) "Vacant" else h.personName.ifEmpty { "Not confirmed" }, style = T.subheadBold, color = if (empty) Brand.secondary else Brand.text)
                                if (parts.isNotEmpty()) Text(parts.joinToString(" · "), style = T.caption, color = Brand.secondary)
                            }
                            if (linked != null) Chevron()
                        }
                    }
                }
                if (i < seats.lastIndex) RowDivider()
            }
        }
        LinkLine("Everyone in office and on the ballot", "person.3") { nav.push(Route.People) }
    }
}

@Composable
private fun MoneySection(yc: YearCtx, budgets: List<DataRow>) {
    val govID = yc.govID
    val fy = yc.fy
    val b = GovYear.budget(budgets, govID, yc.year)
    val caption = if (b.hasAdopted) "$fy ${b.status ?: "adopted"} budget" + (b.total?.let { " " + Format.compactMoney(it) } ?: "") + (b.generalFund?.let { " · general fund " + Format.compactMoney(it) } ?: "") else fy
    PageSection("Money in, money out", "chart.pie", Tone.AMBER, caption) {
        if (!b.hasAdopted) GapNote(GovYear.gap("adopted budget", yc.year, GovYear.budgetYears(budgets, govID, "adopted", setOf("total")), GovYear.Kind.BUDGET, govID, yc.short))
        if (b.revenue.isNotEmpty()) YearBars("Where the money came from", "Audited, all funds, $fy", b.revenue)
        else GapNote(GovYear.gap("audited revenue", yc.year, GovYear.budgetYears(budgets, govID, "actual", setOf("revenue")), GovYear.Kind.AUDIT, govID, yc.short))
        if (b.departments.isNotEmpty()) YearBars("What the general fund pays for", "Adopted $fy budget, by department", b.departments)
        else if (b.spending.isNotEmpty()) YearBars("What it spent the money on", "Audited, all funds, $fy, by service", b.spending)
        if (b.funds.isNotEmpty()) YearBars("Where the money is budgeted, by fund", "$fy, largest funds", b.funds)
        CardList {
            RouteRow(Route.BudgetCompare(govID), "Compare two budget years", symbol = "arrow.left.arrow.right")
            RowDivider(50.dp)
            RouteRow(Route.Dataset("budget-detail", mapOf("gov_id" to govID)), "Every budget line", symbol = "list.bullet.rectangle")
            RowDivider(50.dp)
            RouteRow(Route.TaxCalculator(), "Your property tax bill", symbol = "percent")
        }
    }
}

@Composable
private fun Compared(g: Government) {
    val store = LocalStore.current
    PageSection("Compared with the others", "chart.bar.xaxis", Tone.BLUE) {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            for (m in listOf(GovMetric.PER_RESIDENT, GovMetric.MILLAGE, GovMetric.DEBT)) {
                val items = m.items(store.governments)
                if (items.any { it.id == g.govID }) CompareBars(m.title, items, m::format, m.caption, highlight = g.govID)
            }
            val v = g.votesRecorded; val sv = g.splitVotes
            if (v != null && sv != null && v > 0) {
                Column(Modifier.fillMaxWidth().card(12.dp).padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Recorded votes", style = T.subheadBold, color = Brand.text)
                    ShareBar(listOf(Triple("Unanimous", (v - sv).toDouble(), Brand.good), Triple("Split", sv.toDouble(), Brand.amber)))
                }
            }
        }
    }
}

@Composable
private fun GovMeetings(govID: String) {
    val store = LocalStore.current
    val nav = LocalNav.current
    val upcoming = Meeting.upcoming(store.meetings).filter { it.govID == govID }.take(3)
    if (upcoming.isEmpty()) return
    PageSection("Upcoming meetings", "calendar", Tone.SALMON) {
        CardList {
            upcoming.forEachIndexed { i, m ->
                Box(Modifier.clickable { nav.push(Route.MeetingDetail(m.id)) }) { TodayMeetingRow(m) }
                if (i < upcoming.lastIndex) RowDivider(66.dp)
            }
        }
    }
}

@Composable
private fun DebtSection(yc: YearCtx, debtRows: List<DataRow>, bondRows: List<DataRow>, gy: List<DataRow>) {
    val govID = yc.govID
    val ids = debtIDs(govID)
    val debt = debtRows.filter { (it.string("gov_id") ?: "") in ids }
    val bonds = bondRows.filter { (it.string("gov_id") ?: "") in ids }.sortedByDescending { it.number("outstanding") ?: 0.0 }
    if (debt.isEmpty() && bonds.isEmpty()) return
    var all by rememberSaveable(govID) { mutableStateOf(false) }
    PageSection("Debt", "creditcard", Tone.SALMON, "What it owes, from its latest audit, and every bond, note and loan behind it.") {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            val dYears = GovYear.yearsWith(gy, govID, "debt_total")
            val total = GovYear.row(gy, govID, yc.year)?.number("debt_total")
            if (total != null) CardList { FactRow("End of ${yc.fy}", shortMoney(total), "Audited total for the year picked") }
            else if (dYears.isNotEmpty()) GapNote(GovYear.gap("audited debt total", yc.year, dYears, GovYear.Kind.AUDIT, govID, yc.short)
                + " The details below are from the FY${dYears.last()} audit, the latest we have.")
            if (debt.isNotEmpty()) CardList {
                debt.forEachIndexed { i, d ->
                    FactRow(d.string("government") ?: "Total debt", shortMoney(d.number("total_debt")), d.string("fy"))
                    if (i < debt.lastIndex) RowDivider()
                }
            }
            if (bonds.isNotEmpty()) {
                val shown = if (all) bonds else bonds.take(5)
                CardList {
                    shown.forEachIndexed { i, b ->
                        RecordLinkRow(
                            Route.Record("bonds", b.id), b.string("series") ?: b.string("issuer") ?: "Bond",
                            listOfNotNull(b.string("type")?.let(Format::label), b.string("interest_rate"), b.string("final_maturity")?.let { "matures $it" }).joinToString(" · "),
                            shortMoney(b.number("outstanding") ?: b.number("par_amount")),
                        )
                        if (i < shown.lastIndex) RowDivider()
                    }
                    if (bonds.size > 5) { RowDivider(); ShowMoreRow(all, "All ${bonds.size} bonds and loans") { all = !all } }
                }
            }
        }
    }
}

@Composable
private fun AuditSection(yc: YearCtx, rows: List<DataRow>) {
    val govID = yc.govID
    val nav = LocalNav.current
    val every = rows.filter { it.string("gov_id") == govID }
    if (every.isEmpty()) return
    val findings = every.filter { GovYear.fiscalYearOf(it.string("fy")) == yc.year }
    var all by rememberSaveable(govID) { mutableStateOf(false) }
    val shown = if (all) findings else findings.take(4)
    PageSection("What the auditors found", "magnifyingglass", Tone.AMBER, "Findings from the ${yc.fy} audit, in plain English.") {
        if (findings.isEmpty()) GapNote(GovYear.gap("audit findings", yc.year, every.mapNotNull { GovYear.fiscalYearOf(it.string("fy")) }, GovYear.Kind.AUDIT, govID, yc.short))
        else CardList {
            shown.forEachIndexed { i, f ->
                Row(Modifier.fillMaxWidth().clickable { nav.push(Route.Record("audit-findings", f.id)) }.padding(horizontal = 14.dp, vertical = 11.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text((f.string("fy") ?: "").take(6), style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = Brand.secondary)
                            if (f.bool("repeat") == true) Badge("Repeat", Brand.salmon)
                        }
                        Text(f.string("plain_english") ?: f.string("finding") ?: "", style = T.subhead, color = Brand.text, maxLines = 4)
                    }
                    Chevron()
                }
                if (i < shown.lastIndex) RowDivider()
            }
            if (findings.size > 4) { RowDivider(); ShowMoreRow(all, "All ${findings.size} findings") { all = !all } }
        }
    }
}

@Composable
private fun SavingsSection(govID: String, rows: List<DataRow>) {
    val ideas = rows.filter { it.string("gov_id") == govID || govID in it.strings("gov_ids") }
    if (ideas.isEmpty()) return
    PageSection("Where it could spend less", "dollarsign.arrow.circlepath", Tone.TEAL, "Estimates from the public records, with the next step to check each one.") {
        CardList {
            ideas.forEachIndexed { i, r ->
                val low = r.number("savings_low"); val high = r.number("savings_high")
                RecordLinkRow(
                    Route.Record("savings-opportunities", r.id), r.string("title") ?: "Savings idea",
                    listOfNotNull(r.string("lever"), r.string("confidence")?.let { "$it confidence" }).joinToString(" · "),
                    low?.let { l -> high?.let { "${Format.compactMoney(l)}–${Format.compactMoney(it)}" } ?: Format.compactMoney(l) },
                )
                if (i < ideas.lastIndex) RowDivider()
            }
        }
    }
}

@Composable
private fun CraSection(govID: String, rows: List<DataRow>) {
    val cras = rows.filter { it.string("gov_id") == govID }
    if (cras.isEmpty()) return
    PageSection("Redevelopment (CRA)", "building.2", Tone.BLUE, "Property tax on growth inside the district goes to the CRA instead of the general budget.") {
        CardList {
            for (c in cras) {
                FactRow(c.string("cra") ?: "CRA", shortMoney(c.number("increment_fy2025")), "Tax increment, FY2025 · base year ${c.string("base_year") ?: "?"}")
                RowDivider()
            }
            RouteRow(Route.Dataset("cra-payments", mapOf("gov_id" to govID)), "What it spent the money on", symbol = "list.bullet")
            RowDivider(50.dp)
            RouteRow(Route.CRAIncrement, "Tax increment for every CRA", symbol = "percent")
        }
    }
}

@Composable
private fun RecordsSection(g: Government) {
    val store = LocalStore.current
    val o = rememberOpener()
    val related = store.catalog?.records(g.govID) ?: emptyList()
    // only datasets with rows for this government; the first few, then the rest behind "All N"
    var all by rememberSaveable(g.govID) { mutableStateOf(false) }
    val shown = if (all) related else related.take(6)
    PageSection("Every record", "tray.full", Tone.BLUE, "${related.size} datasets with records for ${g.name}.") {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            CardList {
                shown.forEachIndexed { i, d ->
                    RouteRow(Route.Dataset(d.id, mapOf("gov_id" to g.govID)), d.title, symbol = DatasetSpec.forId(d.id).symbol)
                    if (i < shown.lastIndex) RowDivider(50.dp)
                }
                if (related.size > 6) { RowDivider(); ShowMoreRow(all, "All ${related.size} datasets") { all = !all } }
            }
            g.pageURL?.let { url -> LinkLine("Full profile on BayCounty.me", "safari") { o.open(url) } }
        }
    }
}
