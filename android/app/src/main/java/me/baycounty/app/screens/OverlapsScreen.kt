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
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import me.baycounty.app.Route
import me.baycounty.app.ui.*
import me.baycounty.kit.BayCountyClient
import me.baycounty.kit.Format
import me.baycounty.kit.Overlaps
import me.baycounty.kit.Row as DataRow

/** Where records overlap (/connections/overlaps): the same company, organization or person in more than one public record.
 *  Headline numbers and the top few of each overlap, each opening its full list, then the live parts from /api/v1/overlaps.
 *  Same sections as the iOS OverlapsView. A row is two public records side by side, not a finding. */
@Composable
fun OverlapsScreen() {
    val store = LocalStore.current
    var live by remember { mutableStateOf<Map<String, List<DataRow>>?>(null) }
    var liveFailed by remember { mutableStateOf(false) }
    var reload by remember { mutableIntStateOf(0) }
    LaunchedEffect(Unit) { store.load(Overlaps.datasets) }
    LaunchedEffect(reload) {
        runCatching { withContext(Dispatchers.Default) { Overlaps.decodeLive(store.client.get(Overlaps.LIVE_PATH).data) } }
            .onSuccess { live = it; liveFailed = false }.onFailure { liveFailed = true }
    }
    val all = Overlaps.datasets.associateWith { store.rows[it] ?: emptyList() }
    val loaded = all.values.any { it.isNotEmpty() }

    Screen("Overlaps", onRefresh = { Overlaps.datasets.forEach { store.load(it, force = true) }; reload++ }, spacing = 22) {
        item {
            PageHero(
                "Your government · Connections", "Where the records overlap",
                "The same company, organization or person often shows up in more than one public record: a campaign report, the minutes, an agenda, a check register, a state business filing. This is the summary.",
                symbol = "point.3.connected.trianglepath.dotted", tone = Tone.BLUE,
            )
        }
        if (!loaded) {
            item { val e = Overlaps.datasets.firstNotNullOfOrNull { store.errors[it] }; if (e != null) Unavailable("Couldn't load the overlaps", e) else Loading() }
            return@Screen
        }
        item {
            val h = Overlaps.headline(all)
            Grid2(listOf(0, 1, 2, 3)) { i, m ->
                when (i) {
                    0 -> KPICard("Votes naming a donor", Format.number(h.donorVotes), m, "${h.pairs} official and company pairs since 2016", "link", Tone.BLUE)
                    1 -> KPICard("Votes naming a company or group", Format.number(h.mentionVotes), m, "${h.mentionEntities} companies and organizations named", "text.magnifyingglass", Tone.TEAL)
                    2 -> KPICard("Top fundraiser won", "${h.topWon} of ${h.contested}", m, "contested local races with a report and a result", "chart.bar", Tone.AMBER)
                    else -> KPICard("Emergency buys from donors", "${h.emergencyFromDonors} of ${h.emergency}", m, "bought without bidding from a company that gave", "exclamationmark.triangle", Tone.SALMON)
                }
            }
        }
        item {
            PageSection("What an overlap is, and isn't", "info.circle", Tone.BLUE, "The simple version") {
                Column(Modifier.fillMaxWidth().card(14.dp).padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Line("Two records, one name.", "A company that gave to a commissioner's campaign is named in a motion that commissioner voted on. Both facts are public; this lines them up.")
                    Line("It is not a finding.", "Most of these votes passed unanimously, many on a consent agenda with dozens of routine items. A gift near a vote does not show why anyone voted the way they did.")
                }
            }
        }
        item {
            PageSection("Every overlap", "square.grid.2x2", Tone.TEAL, "The top few of each; tap for the full list") {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) { Overlaps.cards(all).forEach { OverlapCard(it) } }
            }
        }
        item { LiveSection(live, liveFailed) }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("Names in votes and agendas are matched to profiles by name. Gifts come from campaign reports filed with the Supervisor of Elections since 2016. Officials, candidates and people who run a registered business are named; individual donors never are.",
                    style = T.footnote, color = Brand.secondary)
                FreshnessNote("donor-votes")
            }
        }
    }
}

@Composable
private fun Line(head: String, body: String) =
    Text(buildAnnotatedString { pushStyle(SpanStyle(fontWeight = FontWeight.SemiBold)); append(head); pop(); append(" $body") }, style = T.subhead, color = Brand.text)

@Composable
private fun OverlapCard(c: Overlaps.Card) {
    val nav = LocalNav.current
    Column(Modifier.fillMaxWidth().card(14.dp).clickable(role = Role.Button) { nav.push(Route.Dataset(c.dataset)) }.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            ToneIcon(c.symbol, Tone.BLUE, 30.dp)
            Text(c.title, style = T.subheadBold, color = Brand.text, modifier = Modifier.weight(1f))
            Chevron()
        }
        Text(c.stat, style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = Brand.text)
        c.items.forEach { Text("• $it", style = T.caption, color = Brand.secondary) }
    }
}

@Composable
private fun LiveSection(live: Map<String, List<DataRow>>?, failed: Boolean) {
    PageSection("Read live", "bolt", Tone.AMBER, "Hand-checked matches and check registers, read from the database") {
        Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
            when {
                live != null -> Overlaps.liveSections.forEach { (key, title, caption) ->
                    val rows = live[key].orEmpty()
                    if (rows.isNotEmpty()) Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text(title, style = T.subheadBold, color = Brand.text)
                        Text(caption, style = T.caption, color = Brand.secondary)
                        CardList {
                            val shown = rows.take(5)
                            shown.forEachIndexed { i, r ->
                                LiveRow(key, r)
                                if (i < shown.lastIndex) RowDivider()
                            }
                        }
                        if (rows.size > 5) Text("${rows.size - 5} more on BayCounty.me", style = T.caption, color = Brand.secondary)
                    }
                }
                failed -> Text("Couldn't load this part right now. Pull to try again.", style = T.subhead, color = Brand.secondary)
                else -> Loading()
            }
            CardList { WebRow("Every overlap on BayCounty.me", "${BayCountyClient.SITE}/connections/overlaps", "Full tables, sorting and sources", "safari") }
        }
    }
}

@Composable
private fun LiveRow(section: String, r: DataRow) {
    val nav = LocalNav.current
    val opener = rememberOpener()
    val l = Overlaps.liveLine(section, r)
    val parts = l.entity?.split(":", limit = 2)
    when {
        parts?.size == 2 && parts[0] == "person" -> Box(Modifier.clickable(role = Role.Button) { nav.push(Route.Person(parts[1])) }) { RowLabel(l.title, l.detail) }
        parts?.size == 2 && parts[0] == "vendor" -> Box(Modifier.clickable(role = Role.Button) { nav.push(Route.Vendor(parts[1])) }) { RowLabel(l.title, l.detail) }
        parts?.size == 2 -> Box(Modifier.clickable(role = Role.Button) { opener.openSite("/profile/${parts[0]}/${parts[1]}") }) { RowLabel(l.title, l.detail) }
        else -> TextRow(l.title, l.detail)
    }
}
