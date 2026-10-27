package me.baycounty.app.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
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
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import me.baycounty.app.Route
import me.baycounty.app.ui.*
import me.baycounty.kit.BayCountyClient
import me.baycounty.kit.Format
import me.baycounty.kit.Military
import me.baycounty.kit.Row as DataRow

/** Military and the bases (/military): Tyndall AFB and NSA Panama City, the latest news from their units, and federal
 *  contracts to Bay County companies. Same sections as the iOS MilitaryView. */
@Composable
fun MilitaryScreen() {
    val store = LocalStore.current
    LaunchedEffect(Unit) { store.load(Military.datasets) }
    val bases = store.rows["military-installations"] ?: emptyList()
    val news = store.rows["military-news"] ?: emptyList()
    val years = store.rows["federal-contract-years"] ?: emptyList()
    var base by rememberSaveable { mutableStateOf("") }
    var allNews by rememberSaveable { mutableStateOf(false) }
    var allCompanies by rememberSaveable { mutableStateOf(false) }

    Screen("Military", onRefresh = { Military.datasets.forEach { store.load(it, force = true) } }, spacing = 22) {
        item {
            PageHero(
                "People · Bases and military", "Military and the bases",
                "What Tyndall Air Force Base and NSA Panama City do, the latest news from their units, and federal contracts to Bay County companies.",
                symbol = "shield", tone = Tone.BLUE,
            )
        }
        if (bases.isEmpty()) {
            item {
                val e = Military.datasets.firstNotNullOfOrNull { store.errors[it] }
                if (e != null) Unavailable("Couldn't load the bases", e) else Loading()
            }
            return@Screen
        }
        item { Kpis(news, years) }
        for (b in bases) item { BaseCard(b) }
        item { NewsSection(bases, news, base, allNews, onBase = { base = it; allNews = false }, onMore = { allNews = !allNews }) }
        item { ContractsSection(years) }
        item { CompaniesSection(years, allCompanies) { allCompanies = !allCompanies } }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                CardList {
                    WebRow("Military on BayCounty.me", "${BayCountyClient.SITE}/military", "Biggest contracts and every agency", symbol = "safari")
                    RowDivider(50.dp)
                    RouteRow(Route.Dataset("federal-contracts"), "Every federal contract", symbol = "doc.text")
                }
                FreshnessNote("military-news")
            }
        }
    }
}

@Composable
private fun Kpis(news: List<DataRow>, years: List<DataRow>) {
    val latest = Military.stories(news).firstOrNull()?.string("published")
    Grid2(listOf(0, 1, 2)) { i, m ->
        when (i) {
            0 -> KPICard("News stories", "${news.size}", m, latest?.let { "Latest ${Military.dateLabel(it)}" } ?: "From the units on each base", "newspaper", Tone.BLUE)
            1 -> KPICard("Federal contracts", Format.compactMoney(Military.total(years)), m, "To ${Military.companies(years).size} Bay County companies since 2016", "dollarsign.circle", Tone.TEAL)
            else -> KPICard("From the Defense Department", "${Military.defenseShare(years)}%", m, "Most of the rest is Coast Guard", "shield", Tone.AMBER)
        }
    }
}

@Composable
private fun BaseCard(b: DataRow) {
    val tone = if (b.string("branch") == "Navy") Tone.TEAL else Tone.BLUE
    Column(Modifier.fillMaxWidth().card(18.dp).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            ToneIcon("shield", tone, 44.dp)
            Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(b.string("name") ?: "", style = T.headline, color = Brand.text)
                Text(listOfNotNull(b.string("branch"), b.string("host_unit")).joinToString(" · "), style = T.caption, color = Brand.secondary)
            }
        }
        Text(b.string("mission") ?: "", style = T.subhead, color = Brand.text)
        b.string("storm")?.let { Text(it, style = T.footnote, color = Brand.secondary) }
        b.string("commander")?.let { c ->
            Text(buildAnnotatedString {
                withStyle(SpanStyle(fontWeight = FontWeight.SemiBold)) { append("In command: ") }
                append("$c, ${b.string("commander_title") ?: ""}, since ${Military.dateLabel(b.string("commander_since"))}")
            }, style = T.footnote, color = Brand.text)
        }
        val facts = listOfNotNull(
            b.number("opened")?.let { "Opened" to "${it.toInt()}" },
            b.number("acres")?.let { "Acres" to Format.number(it) },
            b.number("personnel")?.let { "People" to "About ${Format.number(it)}" },
            "Stories" to "${(b.number("stories") ?: 0.0).toInt()}",
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            for ((k, v) in facts) Fact(k, v, Modifier.weight(1f))
        }
        CardList {
            WebRow("Base website", b.url("website"), symbol = "globe")
            RowDivider(50.dp)
            WebRow("All its news on DVIDS", b.url("dvids_url"), symbol = "newspaper")
        }
    }
}

@Composable
private fun Fact(label: String, value: String, modifier: Modifier) {
    Column(modifier.background(Brand.hairline.copy(alpha = 0.35f), RoundedCornerShape(12.dp)).padding(horizontal = 10.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(label, style = T.caption2, color = Brand.secondary, maxLines = 1)
        Text(value, style = T.subheadBold, color = Brand.text, maxLines = 1)
    }
}

@Composable
private fun NewsSection(bases: List<DataRow>, news: List<DataRow>, base: String, showAll: Boolean, onBase: (String) -> Unit, onMore: () -> Unit) {
    val opener = rememberOpener()
    val chips = listOf("" to "Both bases") + bases.map { (it.string("installation_id") ?: "") to (it.string("short_name") ?: "") }
    val list = Military.stories(news, base)
    val shown = if (showAll) list else list.take(6)
    PageSection("Latest news", "newspaper", Tone.BLUE, "Stories by each unit's public affairs office. They open on DVIDS.") {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            ChipRow(chips, base) { onBase(it) }
            CardList {
                shown.forEachIndexed { i, s ->
                    TextRow(
                        s.string("title") ?: "",
                        listOf(Military.dateLabel(s.string("published")), s.string("unit") ?: "").filter { it.isNotEmpty() }.joinToString(" · "),
                        badge = (s.string("installation") ?: "") to (if (s.string("installation_id") == "nsa-panama-city") Brand.good else Brand.navy),
                        modifier = Modifier.clickable { opener.open(s.url("url")) },
                    )
                    if (i < shown.lastIndex) RowDivider()
                }
                if (list.size > 6) {
                    RowDivider(0.dp)
                    ShowMoreRow(showAll, "Show ${list.size - shown.size} more stories", onMore)
                }
            }
        }
    }
}

@Composable
private fun ContractsSection(years: List<DataRow>) {
    val series = Military.byYear(years)
    PageSection("Federal contracts by year", "chart.bar", Tone.TEAL, "Money obligated to companies with a business address in Bay County. The work can happen anywhere.") {
        Column(Modifier.fillMaxWidth().card(14.dp).padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            BarChart(series.map { ChartPoint(it.first.toString(), it.second + it.third) }, height = 150.dp, defaultColor = Brand.good)
        }
    }
}

@Composable
private fun CompaniesSection(years: List<DataRow>, showAll: Boolean, onMore: () -> Unit) {
    val opener = rememberOpener()
    val list = Military.companies(years)
    val shown = if (showAll) list.take(100) else list.take(10)
    PageSection("Local companies", "building.2", Tone.AMBER, "Since 2016, biggest first. Tap a company for its profile.") {
        CardList {
            shown.forEachIndexed { i, c ->
                TextRow(
                    c.name, "${c.topAgency} · ${c.defenseShare}% defense", Format.compactMoney(c.total),
                    modifier = Modifier.clickable { Military.profilePath(c.url)?.let { opener.openSite(it) } },
                )
                if (i < shown.lastIndex) RowDivider()
            }
            if (list.size > 10) {
                RowDivider(0.dp)
                ShowMoreRow(showAll, "Show more companies", onMore)
            }
        }
    }
}
