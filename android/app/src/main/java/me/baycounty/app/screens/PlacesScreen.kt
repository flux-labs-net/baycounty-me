package me.baycounty.app.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
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
import me.baycounty.kit.Format
import me.baycounty.kit.Government

/** Ways to compare the governments side by side. */
enum class GovMetric(val short: String, val title: String, val caption: String?) {
    PER_RESIDENT("Per resident", "Budget per resident", "Total budget divided by 2025 population"),
    BUDGET("Budget", "Total budget", null),
    MILLAGE("Tax rate", "Property tax rate", "Mills: dollars per $1,000 of taxable value"),
    DEBT("Debt", "Debt per resident", null);

    fun value(g: Government): Double? = when (this) {
        PER_RESIDENT -> g.budgetPerResident
        BUDGET -> g.budgetTotal
        MILLAGE -> g.millage
        DEBT -> g.debtPerResident
    }

    fun format(v: Double): String = when (this) {
        PER_RESIDENT, DEBT -> Format.money(Math.rint(v))
        BUDGET -> Format.compactMoney(v)
        MILLAGE -> Format.number(v)
    }

    fun items(govs: List<Government>): List<BarItem> =
        govs.mapNotNull { g -> value(g)?.let { BarItem(g.govID, g.name, it) } }.sortedByDescending { it.value }
}

/** The Places tab: compare the governments, open any one of them, and find the people. */
@Composable
fun PlacesScreen() {
    val store = LocalStore.current
    val nav = LocalNav.current
    var metric by rememberSaveable { mutableStateOf(GovMetric.PER_RESIDENT) }
    Screen("Places", onRefresh = { store.loadGovernments() }, spacing = 24) {
        if (store.governments.isEmpty()) {
            item {
                val e = store.errors["government-profiles"]
                if (e != null) Unavailable("Couldn't load governments", e) else Loading()
            }
        } else {
            item {
                val items = metric.items(store.governments)
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    ChipRow(GovMetric.entries.map { it to it.short }, metric) { metric = it }
                    CompareBars(metric.title, items, metric::format, metric.caption, highlight = items.firstOrNull()?.id) { nav.push(Route.Gov(it)) }
                }
            }
            item {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    SectionHeader("Every government")
                    CardList {
                        store.governments.forEachIndexed { i, g ->
                            Row(
                                Modifier.fillMaxWidth().heightIn(min = 64.dp).clickable { nav.push(Route.Gov(g.govID)) }.padding(horizontal = 14.dp, vertical = 8.dp),
                                verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp),
                            ) {
                                GovBadge(g.govID)
                                Column(Modifier.weight(1f)) {
                                    Text(g.name, style = T.subheadBold, color = Brand.text)
                                    Text(govSubtitle(g), style = T.caption, color = Brand.secondary, maxLines = 2)
                                }
                                g.budgetTotal?.let { Text(Format.compactMoney(it), style = T.subheadBold.copy(fontWeight = FontWeight.Bold), color = Brand.text) }
                                Chevron()
                            }
                            if (i < store.governments.lastIndex) RowDivider(66.dp)
                        }
                    }
                }
            }
        }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                SectionHeader("People")
                CardList {
                    RouteRow(Route.People, "Officials, leaders and candidates", symbol = "person.3")
                    RowDivider(50.dp)
                    RouteRow(Route.Dataset("officials-pay"), "What officials are paid", symbol = "person.text.rectangle")
                    RowDivider(50.dp)
                    RouteRow(Route.BudgetCompare(), "Budget compare", symbol = "arrow.left.arrow.right")
                    RowDivider(50.dp)
                    WebRow("Compare side by side", "${BayCountyClient.SITE}/compare", symbol = "chart.bar.xaxis")
                }
            }
        }
        item { FreshnessNote("government-profiles") }
    }
}

fun govSubtitle(g: Government): String = listOfNotNull(
    if (g.kind == "schools") "School district" else Format.label(g.kind),
    g.population?.let { "${Format.number(it)} residents" },
    g.millage?.takeIf { it > 0 }?.let { "${Format.number(it)} mills" },
).filter { it.isNotEmpty() }.joinToString(" · ")
