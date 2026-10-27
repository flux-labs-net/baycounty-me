package me.baycounty.app.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import me.baycounty.app.Route
import me.baycounty.app.ui.*
import me.baycounty.kit.BayCountyClient
import me.baycounty.kit.Format

private data class MoneyItem(val title: String, val symbol: String, val detail: String, val route: Route? = null, val site: String? = null)

private enum class MoneySection(val title: String) {
    PAY("What you pay"), GOES("Where it goes"), ACCOUNTABILITY("Accountability"), CONNECTIONS("Connections"), ELECTIONS("Elections")
}

private val moneyItems: Map<MoneySection, List<MoneyItem>> = mapOf(
    MoneySection.PAY to listOf(
        MoneyItem("Tax calculator", "percent", "Your property tax bill, slice by slice", Route.TaxCalculator()),
        MoneyItem("Fees on your tax bill", "doc.plaintext", "Fire, stormwater and other flat fees", Route.Dataset("fees-assessments")),
        MoneyItem("Exemptions", "house", "Homestead, veterans, seniors and more", Route.Dataset("property-tax-exemptions")),
        MoneyItem("Amendment 3", "checklist", "What the ballot amendment would change", Route.Amendment3()),
        MoneyItem("Tourist tax", "bed.double", "The 5% bed tax visitors pay", Route.Dataset("bed-tax-collections")),
        MoneyItem("Tax rates by year", "chart.line.uptrend.xyaxis", "Every taxing authority, 2020 to 2025", Route.Dataset("property-tax-rates")),
    ),
    MoneySection.GOES to listOf(
        MoneyItem("Budgets", "chart.pie", "Each budget by fund and department", Route.Dataset("budget-detail")),
        MoneyItem("Budget compare", "arrow.left.arrow.right", "One government's budget, two years side by side", Route.BudgetCompare()),
        MoneyItem("Cost per resident", "person.2", "Each service, per resident", Route.Dataset("budget-per-resident")),
        MoneyItem("CRA spending", "building.2", "What redevelopment agencies paid for", Route.CRA),
        MoneyItem("CRA tax increment", "percent", "Property tax that goes to the CRAs instead", Route.CRAIncrement),
        MoneyItem("Sales tax projects", "road.lanes", "Half-cent projects: promised vs built", Route.Dataset("sales-tax-projects")),
        MoneyItem("Hurricane Michael", "hurricane", "Every FEMA rebuilding project", Route.Dataset("fema-michael-projects")),
    ),
    MoneySection.ACCOUNTABILITY to listOf(
        MoneyItem("Accountability console", "checklist", "Projects from budget to close-out, with open questions", Route.Accountability),
        MoneyItem("Savings finder", "dollarsign.arrow.circlepath", "Where governments could spend less", Route.Dataset("savings-opportunities")),
        MoneyItem("Contracts", "signature", "Who wins contracts, and how", Route.Dataset("contracts")),
        MoneyItem("Companies", "building", "Every company paid, with its contracts and votes", Route.Vendors),
        MoneyItem("How they voted", "hand.raised", "Every recorded vote on money decisions", Route.Dataset("votes")),
        MoneyItem("Tourism payments", "dollarsign.circle", "Who the tourism agencies paid", Route.Dataset("vendor-payments")),
        MoneyItem("Change orders", "arrow.triangle.2.circlepath", "How much contracts grew", Route.Dataset("change-orders")),
        MoneyItem("Emergency purchases", "exclamationmark.triangle", "Bought without bidding", Route.Dataset("emergency-purchases")),
        MoneyItem("Debt", "creditcard", "What each government owes", Route.Dataset("debt")),
        MoneyItem("Bonds and loans", "banknote", "Every bond, note and loan", Route.Dataset("bonds")),
        MoneyItem("Audit findings", "magnifyingglass", "What outside auditors flagged", Route.Dataset("audit-findings")),
    ),
    MoneySection.CONNECTIONS to listOf(
        MoneyItem("Network", "point.3.filled.connected.trianglepath.dotted", "Who every government paid, and who gave to officials", site = "/connections"),
        MoneyItem("Campaign gifts", "chart.bar", "What each official raised, and from whom", Route.Dataset("campaign-finance")),
        MoneyItem("Donors with contracts", "link", "Businesses that gave and also hold contracts", Route.DonorContracts),
        MoneyItem("Money map", "point.3.connected.trianglepath.dotted", "Donors, officials and votes on their contracts", Route.MoneyMap),
        MoneyItem("Shared owners", "person.2", "Businesses with a shared owner that gave to the same candidate", site = "/connections/shared-owners"),
        MoneyItem("Nonprofits", "heart.text.square", "Every local nonprofit, its public money, and its board", Route.Dataset("nonprofits")),
        MoneyItem("Nonprofit boards", "person.3", "Who sits on each nonprofit's board", Route.Dataset("nonprofit-board-members")),
        MoneyItem("Chambers of commerce", "storefront", "Boards, events and public money", Route.Chambers),
        MoneyItem("Restaurant inspections", "fork.knife", "Every inspection, warning and closure since 2016", Route.Dataset("restaurants")),
        MoneyItem("New businesses", "storefront", "Companies filed in Bay County since 2016", Route.Dataset("new-businesses")),
        MoneyItem("Business ties", "briefcase", "Officials' and candidates' businesses", site = "/connections/business-ties"),
    ),
    MoneySection.ELECTIONS to listOf(
        MoneyItem("2026 candidates", "checkmark.seal", "Who's running, and what they raised", Route.Dataset("candidates-2026")),
        MoneyItem("Gifts from organizations", "envelope", "2026 contributions from businesses and groups", Route.Dataset("campaign-contributions-2026")),
        MoneyItem("Past elections", "clock.arrow.circlepath", "Every local race from 2016 to 2025, with what each raised", Route.Dataset("campaign-history")),
        MoneyItem("Gifts in past races", "tray.full", "Business and group gifts to 2016 to 2025 campaigns", Route.Dataset("campaign-contributions-history")),
        MoneyItem("Business owners who gave", "person.text.rectangle", "Gifts from people who run a registered business", Route.Dataset("owner-gifts")),
    ),
)

/** The Money tab: the website's Public Money menu, with native screens where the app has them. */
@Composable
fun MoneyScreen() {
    val store = LocalStore.current
    val nav = LocalNav.current
    val listState = rememberLazyListState()
    val scope = rememberCoroutineScope()
    var picked by rememberSaveable { mutableStateOf(MoneySection.PAY) }
    LaunchedEffect(Unit) { store.loadAmendment3() }

    fun total(v: List<Double>): String? = v.sum().takeIf { it > 0 }?.let { Format.compactMoney(it) }
    fun value(item: MoneyItem): String? {
        val g = store.governments
        return when (item.title) {
            "Amendment 3" -> store.amendment3?.localImpact(1)?.takeIf { it > 0 }?.let { "−" + Format.compactMoney(it) }
            "Hurricane Michael" -> total(g.mapNotNull { it.femaMichael })
            "Debt" -> total(g.mapNotNull { it.debtTotal })
            "Audit findings" -> g.mapNotNull { it.auditFindings }.sum().takeIf { it > 0 }?.toString()
            else -> null
        }
    }

    Screen("Money", onRefresh = { store.loadGovernments() }, listState = listState, spacing = 22) {
        item { LevyCard() }
        item {
            ChipRow(MoneySection.entries.map { it to it.title }, picked) { s ->
                picked = s
                scope.launch { listState.animateScrollToItem(2 + s.ordinal) }
            }
        }
        for (s in MoneySection.entries) item(key = s.name) {
            val items = moneyItems.getValue(s)
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                SectionHeader(s.title)
                CardList {
                    items.forEachIndexed { i, it ->
                        if (it.route != null) RouteRow(it.route, it.title, it.detail, it.symbol, value(it))
                        else WebRow(it.title, BayCountyClient.SITE + it.site, it.detail, it.symbol)
                        if (i < items.lastIndex) RowDivider(50.dp)
                    }
                }
            }
        }
        item {
            CardList {
                RouteRow(Route.Explore, "Every dataset", symbol = "square.grid.2x2")
                RowDivider(50.dp)
                WebRow("Sales tax projects map", "${BayCountyClient.SITE}/public-money/sales-tax-projects", symbol = "map")
            }
        }
    }
}

/** Property tax levied this year across every government, split by who levies it. */
@Composable
private fun LevyCard() {
    val g = LocalStore.current.governments
    val nav = LocalNav.current
    val county = g.filter { it.kind == "county" }.mapNotNull { it.propertyTaxLevy }.sum()
    val schools = g.filter { it.kind == "schools" }.mapNotNull { it.propertyTaxLevy }.sum()
    val cities = g.filter { it.kind == "city" }.mapNotNull { it.propertyTaxLevy }.sum()
    val total = county + schools + cities
    if (total <= 0) return
    val parts = listOf(
        Triple("Schools", schools, Color(0.56f, 0.70f, 0.89f)),
        Triple("County", county, Color(1f, 0.55f, 0.51f)),
        Triple("Cities", cities, Color(1f, 0.765f, 0.42f)),
    )
    Column(
        Modifier.fillMaxWidth().background(Brand.navyFill, RoundedCornerShape(18.dp)).clickable { nav.push(Route.TaxCalculator()) }.padding(18.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Text("Property tax levied this year", style = T.footnote, color = Color.White.copy(alpha = 0.8f))
        Text(Format.compactMoney(total), style = T.bigNumber.copy(fontSize = T.bigNumber.fontSize * 1.25f), color = Color.White)
        StackBar(parts)
        Flow(14.dp) {
            for (p in parts) Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(5.dp)) {
                Box(Modifier.size(8.dp).background(p.third, RoundedCornerShape(2.dp)))
                Text("${p.first} ${Math.round(p.second / total * 100)}%", style = T.caption, color = Color.White.copy(alpha = 0.8f))
            }
        }
    }
}
