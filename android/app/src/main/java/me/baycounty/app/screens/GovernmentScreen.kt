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
import me.baycounty.kit.BudgetCompare
import me.baycounty.kit.DatasetSpec
import me.baycounty.kit.Dates
import me.baycounty.kit.Format
import me.baycounty.kit.Government
import me.baycounty.kit.Meeting
import me.baycounty.kit.Officeholders
import me.baycounty.kit.Row as DataRow

private val govDatasets = listOf("officeholder-terms", "budget-years", "debt", "bonds", "audit-findings", "savings-opportunities", "cra-agencies")

/**
 * One government, in the same order as its page on BayCounty.me: at a glance, who's in charge, the money,
 * how it compares, meetings, debt, audit findings, savings ideas and its redevelopment agency.
 */
@Composable
fun GovernmentScreen(govID: String) {
    val store = LocalStore.current
    LaunchedEffect(govID) { store.load(govDatasets); store.loadPeople() }
    val g = store.government(govID)
    if (g == null) {
        Screen("Government") { item { if (store.governments.isEmpty()) Loading() else Unavailable("Not found", symbol = "building.columns") } }
        return
    }
    fun rows(id: String) = store.rows[id] ?: emptyList()
    Screen(g.name, onRefresh = { for (d in govDatasets) store.load(d, force = true) }) {
        item {
            PageHero("Governments", g.name, g.population?.let { "${Format.number(it)} residents (2025 estimate)" }, badge = { GovBadge(govID, 48.dp) })
        }
        item { Glance(g) }
        item { WhosInCharge(govID, rows("officeholder-terms")) }
        item { MoneySection(govID, rows("budget-years")) }
        item { Compared(g) }
        item { GovMeetings(govID) }
        item { DebtSection(govID, rows("debt"), rows("bonds")) }
        item { AuditSection(govID, rows("audit-findings")) }
        item { SavingsSection(govID, rows("savings-opportunities")) }
        item { CraSection(govID, rows("cra-agencies")) }
        item { RecordsSection(g) }
    }
}

@Composable
private fun Glance(g: Government) {
    data class K(val title: String, val value: String, val caption: String? = null)
    val cards = listOfNotNull(
        g.budgetTotal?.let { K("Total budget", Format.compactMoney(it), g.budgetStatus) },
        g.budgetPerResident?.let { K("Budget per resident", Format.money(Math.rint(it))) },
        g.generalFund?.let { K("General fund", Format.compactMoney(it)) },
        g.propertyTaxLevy?.let { K("Property tax levied", Format.compactMoney(it)) },
        g.millage?.let { K("Tax rate (mills)", Format.number(it), "Per \$1,000 of taxable value") },
        g.debtTotal?.let { K("Debt", Format.compactMoney(it), g.debtPerResident?.let { p -> "${Format.money(Math.rint(p))} per resident" }) },
        g.auditFindings?.let { K("Audit findings", "$it", listOfNotNull(g.auditYear, g.repeatFindings?.let { r -> "$r repeat" }).joinToString(" · ")) },
        g.votesRecorded?.let { K("Votes recorded", "$it", g.splitVotes?.let { s -> "$s split" }) },
        g.typicalUtilityBill?.let { K("Typical utility bill", Format.money(it), "Per month") },
        g.femaMichael?.let { K("FEMA, Hurricane Michael", Format.compactMoney(it)) },
    )
    PageSection("At a glance", "gauge.with.dots.needle.33percent", Tone.BLUE) {
        Grid2(cards) { k, m -> KPICard(k.title, k.value, m, k.caption?.takeIf { it.isNotEmpty() }) }
    }
}

/** "2024-11-19" to "Nov 2024". */
fun shortMonth(d: String): String = Dates.parse(d)?.let { Dates.format(it, "MMM yyyy") } ?: d

@Composable
private fun WhosInCharge(govID: String, terms: List<DataRow>) {
    val store = LocalStore.current
    val nav = LocalNav.current
    val years = Officeholders.years(terms, govID)
    var year by rememberSaveable(govID) { mutableStateOf<Int?>(null) }
    val picked = year ?: years.firstOrNull() ?: return
    val seats = Officeholders.inOffice(terms, govID, picked)
    PageSection("Who's in charge", "person.3", Tone.TEAL, "Who held each seat in fiscal year $picked. Pick another year to see who served then.") {
        MenuPicker("FY$picked", years.map { it to "FY$it" }, "Fiscal year $picked") { year = it }
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
                        Row(
                            (if (linked != null) Modifier.clickable { nav.push(Route.Person(linked)) } else Modifier).fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                val empty = h.vacant || h.personName.isEmpty()
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
private fun MoneySection(govID: String, budgets: List<DataRow>) {
    val latest = BudgetCompare.compare(budgets, govID)
    PageSection("Money in, money out", "chart.pie", Tone.AMBER, latest?.let { "Adopted budget, FY${it.to}, and how it changed from FY${it.from}." }) {
        val funds = latest?.sections?.firstOrNull { it.key == "fund" }
        if (latest != null && funds != null && funds.lines.any { it.to != null }) {
            val top = funds.lines.filter { (it.to ?: 0.0) > 0 }.sortedByDescending { it.to ?: 0.0 }.take(6)
            CompareBars("Where the money is budgeted, by fund", top.map { BarItem(it.key, it.name, it.to ?: 0.0) }, Format::compactMoney,
                "Top ${top.size} funds, FY${latest.to}", labelsAbove = true)
        }
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
private fun DebtSection(govID: String, debtRows: List<DataRow>, bondRows: List<DataRow>) {
    val ids = buildSet { add(govID); if (govID == "pc") add("port"); if (govID == "county") add("airport") }
    val debt = debtRows.filter { (it.string("gov_id") ?: "") in ids }
    val bonds = bondRows.filter { (it.string("gov_id") ?: "") in ids }.sortedByDescending { it.number("outstanding") ?: 0.0 }
    if (debt.isEmpty() && bonds.isEmpty()) return
    var all by rememberSaveable(govID) { mutableStateOf(false) }
    PageSection("Debt", "creditcard", Tone.SALMON, "What it owes, from its latest audit, and every bond, note and loan behind it.") {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
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
private fun AuditSection(govID: String, rows: List<DataRow>) {
    val nav = LocalNav.current
    val findings = rows.filter { it.string("gov_id") == govID }.sortedByDescending { it.string("fy") ?: "" }
    if (findings.isEmpty()) return
    var all by rememberSaveable(govID) { mutableStateOf(false) }
    val shown = if (all) findings else findings.take(4)
    PageSection("What the auditors found", "magnifyingglass", Tone.AMBER, "Findings from the outside audits, newest first, in plain English.") {
        CardList {
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
    val related = (store.catalog?.datasets ?: emptyList()).filter { it.id !in DatasetSpec.ownScreens && it.column("gov_id") != null }
    PageSection("Every record", "tray.full", Tone.BLUE, "Each dataset, filtered to ${g.name}.") {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            CardList {
                related.forEachIndexed { i, d ->
                    RouteRow(Route.Dataset(d.id, mapOf("gov_id" to g.govID)), d.title, symbol = DatasetSpec.forId(d.id).symbol)
                    if (i < related.lastIndex) RowDivider(50.dp)
                }
            }
            g.pageURL?.let { url -> LinkLine("Full profile on BayCounty.me", "safari") { o.open(url) } }
        }
    }
}
