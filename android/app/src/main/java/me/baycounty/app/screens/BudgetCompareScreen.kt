package me.baycounty.app.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import me.baycounty.app.ui.*
import me.baycounty.kit.BayCountyClient
import me.baycounty.kit.BudgetCompare
import me.baycounty.kit.Cutoff
import me.baycounty.kit.Format
import me.baycounty.kit.Governments
import kotlin.math.abs

/** One government's budget in two fiscal years, line by line (/public-money/budget-compare). */
@Composable
fun BudgetCompareScreen(startGov: String?) {
    val store = LocalStore.current
    val id = "budget-years"
    LaunchedEffect(Unit) { store.load(id) }
    var govID by rememberSaveable { mutableStateOf(startGov ?: "county") }
    var basis by rememberSaveable { mutableStateOf(BudgetCompare.Basis.ADOPTED) }
    var from by rememberSaveable { mutableStateOf<Int?>(null) }
    var to by rememberSaveable { mutableStateOf<Int?>(null) }
    var expanded by rememberSaveable { mutableStateOf(setOf<String>()) }
    val rows = store.rows[id] ?: emptyList()
    fun reset() { from = null; to = null; expanded = emptySet() }

    Screen("Budget compare", onRefresh = { store.load(id, force = true) }, spacing = 22) {
        item {
            PageHero(
                "Where it goes", "Budget compare", "Pick a government and two years to see what grew, what shrank and what's new.",
                symbol = "arrow.left.arrow.right", tone = Tone.BLUE,
            )
        }
        if (rows.isEmpty()) {
            item { val e = store.errors[id]; if (e != null) Unavailable("Couldn't load budgets", e) else Loading() }
        } else {
            val r = BudgetCompare.compare(rows, govID, basis, from, to)?.takeIf { it.from >= Cutoff.FIRST_YEAR }
            item {
                val govs = BudgetCompare.governments(rows, basis)
                val years = BudgetCompare.years(rows, govID, basis).filter { it >= Cutoff.FIRST_YEAR }
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    ChipRow(govs.map { it to (Governments.names[it]?.replace("Bay District ", "") ?: it) }, govID) { govID = it; reset() }
                    ChipRow(listOf(BudgetCompare.Basis.ADOPTED to "Adopted budgets", BudgetCompare.Basis.ACTUAL to "Audited actuals"), basis) { basis = it; reset() }
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        FieldMenu("From", r?.from?.let { "FY$it" } ?: "Pick", years.filter { it != r?.to }.reversed().map { it to "FY$it" }, Modifier.weight(1f), r?.from) { from = it }
                        Icon(icon("arrow.right"), null, tint = Brand.secondary, modifier = Modifier.size(18.dp))
                        FieldMenu("To", r?.to?.let { "FY$it" } ?: "Pick", years.filter { it != r?.from }.reversed().map { it to "FY$it" }, Modifier.weight(1f), r?.to) { to = it }
                    }
                }
            }
            if (r == null) item {
                Text("There aren't two years on record to compare for this government yet.", style = T.subhead, color = Brand.secondary)
            } else {
                item {
                    Grid2(r.totals.take(4)) { t, m ->
                        KPICard(t.name, shortMoney(t.to), m, changeText(t, r), "chart.bar", if (t.change >= 0) Tone.TEAL else Tone.SALMON)
                    }
                }
                if (r.biggestIncrease != null || r.biggestDecrease != null) item {
                    CardList {
                        r.biggestIncrease?.let { FactRow("Grew the most", "+" + Format.compactMoney(it.change), it.name) }
                        if (r.biggestIncrease != null && r.biggestDecrease != null) RowDivider()
                        r.biggestDecrease?.let { FactRow("Shrank the most", "−" + Format.compactMoney(abs(it.change)), it.name) }
                    }
                }
                if (r.notes.isNotEmpty()) item {
                    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        for (n in r.notes) Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            Icon(icon("info.circle"), null, tint = Brand.secondary, modifier = Modifier.size(16.dp))
                            Text(n, style = T.footnote, color = Brand.secondary)
                        }
                    }
                }
                val history = r.history.filter { it.first >= Cutoff.FIRST_YEAR }
                if (history.size >= 2) item {
                    YearBars("Total by year", history.map { "'" + it.first.toString().takeLast(2) to it.second })
                }
                for (s in r.sections.filter { it.lines.isNotEmpty() }) item(key = "section-${s.key}") {
                    PageSection(s.title, sectionSymbol(s.key), sectionTone(s.key), "FY${r.from} to FY${r.to}, biggest changes first") {
                        val open = s.key in expanded
                        val shown = if (open) s.lines else s.lines.take(10)
                        CardList {
                            shown.forEachIndexed { i, l ->
                                LineRow(l, r)
                                if (i < shown.lastIndex) RowDivider()
                            }
                            if (s.lines.size > 10) {
                                RowDivider()
                                ShowMoreRow(open, "Show all ${s.lines.size}") { expanded = if (open) expanded - s.key else expanded + s.key }
                            }
                        }
                    }
                }
                item {
                    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        r.sourcesFrom.firstOrNull()?.let { SourceLink(it, "FY${r.from} source") }
                        r.sourcesTo.firstOrNull()?.let { SourceLink(it, "FY${r.to} source") }
                    }
                }
            }
        }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                CardList { WebRow("Budget compare on BayCounty.me", "${BayCountyClient.SITE}/public-money/budget-compare", symbol = "safari") }
                FreshnessNote(id)
            }
        }
    }
}

@Composable
private fun LineRow(l: BudgetCompare.Line, r: BudgetCompare.Result) {
    Row(
        Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 11.dp).semantics(mergeDescendants = true) {},
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Text(l.name, style = T.subheadBold, color = Brand.text)
            Text("${shortMoney(l.from)} → ${shortMoney(l.to)}", style = T.caption, color = Brand.secondary)
            if (l.status != "both") Badge(if (l.status == "added") "New in FY${r.to}" else "Not in FY${r.to}", Brand.amber)
        }
        Column(horizontalAlignment = Alignment.End, verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(
                (if (l.change >= 0) "+" else "−") + Format.compactMoney(abs(l.change)),
                style = T.subheadBold.copy(fontWeight = FontWeight.Bold), color = if (l.change >= 0) Brand.good else Brand.salmon,
            )
            l.pct?.let { Text("${if (it >= 0) "+" else ""}${Format.number(it)}%", style = T.caption, color = Brand.secondary) }
        }
    }
}

private fun changeText(l: BudgetCompare.Line, r: BudgetCompare.Result): String {
    if (l.from == null) return "FY${r.to}"
    val sign = if (l.change >= 0) "+" else "−"
    return "$sign${Format.compactMoney(abs(l.change))} from FY${r.from}" + (l.pct?.let { " (${if (it >= 0) "+" else ""}${Format.number(it)}%)" } ?: "")
}

private fun sectionSymbol(key: String): String =
    mapOf("department" to "building.columns", "fund" to "tray.2", "service" to "square.grid.2x2", "spending" to "arrow.up.right", "revenue" to "arrow.down.left")[key] ?: "list.bullet"

private fun sectionTone(key: String): Tone =
    mapOf("department" to Tone.BLUE, "fund" to Tone.TEAL, "service" to Tone.AMBER, "spending" to Tone.SALMON, "revenue" to Tone.TEAL)[key] ?: Tone.BLUE
