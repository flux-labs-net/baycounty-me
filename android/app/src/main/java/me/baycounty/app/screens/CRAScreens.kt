package me.baycounty.app.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
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
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import me.baycounty.app.Route
import me.baycounty.app.ui.*
import me.baycounty.kit.BayCountyClient
import me.baycounty.kit.CRAIncrement
import me.baycounty.kit.CRALedger
import me.baycounty.kit.Format

/** CRA Spending: what Bay County's redevelopment agencies paid for, mapped. */
@Composable
fun CRAScreen() {
    val store = LocalStore.current
    val nav = LocalNav.current
    val id = "cra-payments"
    LaunchedEffect(Unit) { store.load(id) }
    val rows = store.rows[id] ?: emptyList()
    Screen("CRA Spending", onRefresh = { store.load(id, force = true) }, spacing = 22) {
        item {
            PageHero(
                "Where it goes", "CRA spending",
                "Community Redevelopment Agencies keep a share of property tax growth in their districts. This is what they spent it on.",
                symbol = "building.2", tone = Tone.TEAL,
            )
        }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Grid2(listOf(0, 1)) { i, m ->
                    if (i == 0) KPICard("Paid out", Format.compactMoney(CRALedger.paidOut(rows)), m, "Reported spent", "checkmark.circle", Tone.TEAL)
                    else KPICard("Committed or budgeted", Format.compactMoney(CRALedger.pending(rows)), m, "Not proof of payment", "clock", Tone.AMBER)
                }
                FreshnessNote(id)
            }
        }
        if (rows.isEmpty()) {
            item { val e = store.errors[id]; if (e != null) Unavailable("Couldn't load CRA spending", e) else Loading() }
            return@Screen
        }
        item {
            PageSection("On the map", "map", Tone.BLUE) {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    RecordsMap(id, rows, Modifier.fillMaxWidth().height(280.dp)) { nav.push(Route.Record(id, it.id)) }
                    Flow(12.dp) {
                        for (s in listOf("Spent", "Committed", "Budgeted", "Proposed")) {
                            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                                Box(Modifier.size(8.dp).background(statusColor(s), CircleShape))
                                Text(s, style = T.caption, color = Brand.secondary)
                            }
                        }
                    }
                }
            }
        }
        val summaries = CRALedger.summaries(rows)
        item {
            PageSection("By agency", "chart.bar", Tone.AMBER) {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    AgencyBars(summaries)
                    CardList {
                        summaries.forEachIndexed { i, s ->
                            Row(
                                Modifier.fillMaxWidth().clickable { nav.push(Route.Dataset(id, mapOf("cra" to s.agency))) }.padding(horizontal = 14.dp, vertical = 10.dp),
                                verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp),
                            ) {
                                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                    Text(s.agency, style = T.subheadBold, color = Brand.text)
                                    Text("${s.records} records", style = T.caption, color = Brand.secondary)
                                }
                                Column(horizontalAlignment = Alignment.End, verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                    Text(Format.compactMoney(s.paidOut), style = T.subheadBold.copy(fontWeight = FontWeight.Bold), color = Brand.text)
                                    if (s.pending > 0) Text("+${Format.compactMoney(s.pending)} planned", style = T.caption, color = Brand.secondary)
                                }
                                Chevron()
                            }
                            if (i < summaries.lastIndex) RowDivider()
                        }
                    }
                }
            }
        }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                CardList {
                    RouteRow(Route.Dataset(id), "All ${rows.size} records", symbol = "list.bullet")
                    RowDivider(50.dp)
                    RouteRow(Route.CRAIncrement, "How much tax goes to the CRAs", symbol = "percent")
                }
                Text(
                    "Totals count each dollar once. Records that are parts of a listed total, possible duplicates and non-CRA money stay in the list but are left out of totals.",
                    style = T.caption, color = Brand.secondary,
                )
                CardList { WebRow("CRA Spending on BayCounty.me", "${BayCountyClient.SITE}/public-money/cra-spending", symbol = "safari") }
            }
        }
    }
}

/** Paid out (navy) and committed or budgeted (light navy) for each agency, one line each. */
@Composable
private fun AgencyBars(summaries: List<CRALedger.Summary>) {
    val maxV = summaries.maxOfOrNull { it.total }?.takeIf { it > 0 } ?: 1.0
    Column(Modifier.fillMaxWidth().card(12.dp).padding(14.dp), verticalArrangement = Arrangement.spacedBy(9.dp)) {
        for (s in summaries) {
            Row(
                Modifier.semantics { contentDescription = "${s.agency}: ${Format.compactMoney(s.paidOut)} paid out, ${Format.compactMoney(s.pending)} committed or budgeted" },
                verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text(s.agency.replace(" CRA", ""), style = T.caption, color = Brand.text, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.width(104.dp))
                Row(Modifier.weight(1f).height(10.dp)) {
                    val paid = (s.paidOut / maxV).toFloat().coerceIn(0f, 1f)
                    val pend = (s.pending / maxV).toFloat().coerceIn(0f, 1f - paid)
                    if (paid > 0) Box(Modifier.weight(paid).fillMaxHeight().background(Brand.navy, RoundedCornerShape(topStart = 5.dp, bottomStart = 5.dp)))
                    if (pend > 0) Box(Modifier.weight(pend).fillMaxHeight().background(Brand.navy.copy(alpha = 0.35f), RoundedCornerShape(topEnd = 5.dp, bottomEnd = 5.dp)))
                    val rest = 1f - paid - pend
                    if (rest > 0.001f) Spacer(Modifier.weight(rest))
                }
                Text(Format.compactMoney(s.total), style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = Brand.text, textAlign = TextAlign.End, maxLines = 1, modifier = Modifier.width(58.dp))
            }
        }
        Flow(14.dp) {
            Swatch(Brand.navy, "Paid out")
            Swatch(Brand.navy.copy(alpha = 0.35f), "Committed or budgeted")
        }
    }
}

@Composable
private fun Swatch(color: Color, label: String) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(5.dp)) {
        Box(Modifier.size(10.dp).background(color, RoundedCornerShape(2.dp)))
        Text(label, style = T.caption, color = Brand.secondary)
    }
}

/** How much property tax goes to the redevelopment agencies (/public-money/cra-tax-increment). */
@Composable
fun CRAIncrementScreen() {
    val store = LocalStore.current
    val ids = listOf("cra-agencies", "cra-tax-increment", "cra-increment-checks")
    LaunchedEffect(Unit) { store.load(ids) }
    var scenario by rememberSaveable { mutableStateOf(CRAIncrement.Scenario.MID) }
    var payer by rememberSaveable { mutableStateOf(CRAIncrement.Payer.ALL) }
    val agencies = store.rows["cra-agencies"] ?: emptyList()
    val years = store.rows["cra-tax-increment"] ?: emptyList()
    val checks = store.rows["cra-increment-checks"] ?: emptyList()
    val h = CRAIncrement.headline(agencies, years)
    fun pct(a: Double, b: Double): Int = if (b > 0) Math.round(a / b * 100).toInt() else 0

    Screen("CRA tax increment", onRefresh = { ids.forEach { store.load(it, force = true) } }, spacing = 22) {
        item {
            PageHero(
                "Where it goes", "CRA tax increment",
                "Property tax on growth inside each redevelopment district goes to its CRA instead of the county or city budget.",
                symbol = "percent", tone = Tone.AMBER,
            )
        }
        if (h == null) {
            item {
                if (ids.any { store.errors[it] != null }) Unavailable("Couldn't load the CRA figures") else Loading()
            }
        } else {
            item {
                val cards = listOf(
                    Triple("Tax increment, FY${h.lastYear}", Format.compactMoney(h.total), "All ${h.agencies} CRAs. ${pct(h.frontBeachRoad, h.total)}% is Front Beach Road"),
                    Triple("Paid by Bay County, FY${h.lastYear}", Format.compactMoney(h.county), "${pct(h.county, h.total)}% of the total; the cities paid ${Format.compactMoney(h.total - h.county)}"),
                    Triple("Paid on record, FY${h.firstYear} to FY${h.lastYear}", Format.compactMoney(h.paidOnRecord), "${Format.compactMoney(h.countyOnRecord)} from the county. Early years are missing for several CRAs"),
                    Triple("Still to come, to each sunset", "${Format.compactMoney(h.toComeLow)} to ${Format.compactMoney(h.toComeHigh)}", "Low to high growth"),
                )
                val looks = listOf("percent" to Tone.AMBER, "building.columns" to Tone.BLUE, "clock" to Tone.TEAL, "chart.line.uptrend.xyaxis" to Tone.SALMON)
                Grid2(cards.indices.toList()) { i, m ->
                    KPICard(cards[i].first, cards[i].second, m, cards[i].third, looks[i].first, looks[i].second)
                }
            }
            item {
                PageSection("The simple version", "lightbulb", Tone.AMBER) {
                    Column(Modifier.fillMaxWidth().card(14.dp).padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        for ((lead, rest) in listOf(
                            "A CRA starts with a base value." to " The county and the city keep collecting tax on the value the district had in its base year.",
                            "Growth above the base is the increment." to " Each year they pay 95% of what their tax rate raises on that growth into the CRA's trust fund. The CRA can spend it only inside the district.",
                            "So the money isn't gone, it's set aside." to " Without a CRA the county and city could spend it anywhere. Schools and the water management district pay nothing.",
                        )) {
                            Text(buildAnnotatedString { withStyle(SpanStyle(fontWeight = FontWeight.Bold)) { append(lead) }; append(rest) }, style = T.subhead, color = Brand.text)
                        }
                    }
                }
            }
            item {
                val series = CRAIncrement.byYear(years, scenario, payer)
                PageSection(
                    "Tax increment by year", "chart.bar", Tone.BLUE,
                    "Reported through FY${h.lastYear}, then projected to each CRA's sunset. Front Beach Road is held to its \$30M yearly cap.",
                ) {
                    Column(Modifier.fillMaxWidth().card(14.dp).padding(14.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        ChipRow(CRAIncrement.Scenario.entries.map { it to it.label }, scenario) { scenario = it }
                        ChipRow(CRAIncrement.Payer.entries.map { it to it.label }, payer) { payer = it }
                        val navy = Brand.navy
                        val amber = Brand.amber
                        BarChart(
                            series.map { ChartPoint(it.fiscalYear.toString(), it.amount, if (it.projected) amber else navy) },
                            height = 170.dp, maxBars = 200,
                        )
                        Flow(14.dp) { Swatch(navy, "Reported"); Swatch(amber, "Projected") }
                    }
                }
            }
            item {
                val sorted = agencies.sortedByDescending { it.number("increment_fy2025") ?: 0.0 }
                PageSection("Each CRA at a glance", "building.2", Tone.TEAL, "FY2025, the last year reported for all seven") {
                    CardList {
                        sorted.forEachIndexed { i, a ->
                            val share = Math.round((a.number("county_share_fy2025") ?: 0.0) * 100)
                            Column(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 11.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Text(a.string("cra") ?: "CRA", style = T.subheadBold, color = Brand.text, modifier = Modifier.weight(1f))
                                    Text(shortMoney(a.number("increment_fy2025")), style = T.subheadBold.copy(fontWeight = FontWeight.Bold), color = Brand.text)
                                }
                                Text(
                                    listOfNotNull(a.string("city"), a.string("base_year")?.let { if (it.contains("base")) it else "base year $it" }, "$share% paid by the county").joinToString(" · "),
                                    style = T.caption, color = Brand.secondary,
                                )
                                val sunset = a.number("sunset_fy")?.toInt()?.toString() ?: "?"
                                val assumed = if (a.bool("sunset_assumed") == true) " (assumed)" else ""
                                Text(
                                    "Paid on record ${shortMoney(a.number("paid_on_record"))} · still to come ${shortMoney(CRAIncrement.toCome(a, scenario))} by FY$sunset$assumed",
                                    style = T.caption, color = Brand.secondary,
                                )
                            }
                            if (i < sorted.lastIndex) RowDivider()
                        }
                    }
                }
            }
            if (checks.isNotEmpty()) item {
                PageSection("Checked against official figures", "checkmark.seal", Tone.TEAL) {
                    CardList {
                        checks.forEachIndexed { i, c ->
                            Column(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 11.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text(c.string("figure") ?: "", style = T.subhead, color = Brand.text)
                                val diff = c.number("difference_pct")?.let { " · ${Format.number(it)}% apart" } ?: ""
                                Text("Official ${shortMoney(c.number("official_figure"))} · our estimate ${shortMoney(c.number("estimate"))}$diff", style = T.caption, color = Brand.secondary)
                                SourceLink(c.url("source_url"))
                            }
                            if (i < checks.lastIndex) RowDivider()
                        }
                    }
                }
            }
        }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                CardList {
                    RouteRow(Route.CRA, "What the CRAs spent it on", symbol = "building.2")
                    RowDivider(50.dp)
                    WebRow("CRA tax increment on BayCounty.me", "${BayCountyClient.SITE}/public-money/cra-tax-increment", symbol = "safari")
                }
                FreshnessNote("cra-tax-increment")
            }
        }
    }
}
