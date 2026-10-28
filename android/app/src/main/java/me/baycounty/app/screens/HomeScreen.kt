package me.baycounty.app.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
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
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import me.baycounty.app.Route
import me.baycounty.app.Tab
import me.baycounty.app.ui.*
import me.baycounty.kit.Amendment3Model
import me.baycounty.kit.Dates
import me.baycounty.kit.Format
import me.baycounty.kit.Meeting
import me.baycounty.kit.TaxCalculator
import java.time.Instant

private data class BrowseItem(val title: String, val symbol: String, val route: Route)

private val browse = listOf(
    BrowseItem("Emergencies and alerts", "exclamationmark.triangle", Route.Emergency),
    BrowseItem("Hurricane prep", "hurricane", Route.HurricanePrep),
    BrowseItem("CRA spending", "building.2", Route.CRA),
    BrowseItem("Contracts", "signature", Route.Dataset("contracts")),
    BrowseItem("How they voted", "hand.raised", Route.Dataset("votes")),
    BrowseItem("Companies", "building", Route.Vendors),
    BrowseItem("Campaign money", "chart.bar", Route.Dataset("campaign-finance")),
    BrowseItem("Accountability console", "checklist", Route.Accountability),
    BrowseItem("Beaches", "beach.umbrella", Route.Beaches),
    BrowseItem("Parks, ramps and trails", "tree", Route.Parks),
    BrowseItem("Glossary", "character.book.closed", Route.Glossary),
    BrowseItem("What's new", "sparkles", Route.Updates),
)

/** The Today tab: what's coming up this week, the ballot, your tax bill, the big numbers, and a list to browse. */
@Composable
fun HomeScreen() {
    val store = LocalStore.current
    val nav = LocalNav.current
    val o = rememberOpener()
    LaunchedEffect(Unit) { store.loadTax(); store.loadAmendment3() }
    Screen(
        "Today",
        navigationIcon = { BayMarkButton { nav.push(Route.About) } },
        actions = {
            ToolbarIcon("bubble.left.and.text.bubble.right", "Ask a question") { o.openSite("/ask") }
            ToolbarIcon("person.crop.circle", if (me.baycounty.app.Account.signedIn) "My home" else "Sign in") { nav.push(Route.MyHome) }
            ToolbarIcon("bell", "Emergencies and alerts") { nav.push(Route.Emergency) }
        },
        onRefresh = { store.refreshAll() },
        spacing = 24,
    ) {
        item { SearchField { nav.push(Route.Search) } }
        item { BallotBanner() }
        item { AddressCard() }
        item { HomeEventsSection() }
        item { MeetingsSection() }
        item { TaxBillSection() }
        item { NumbersSection() }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                SectionHeader("Browse", "All public money") { nav.select(Tab.MONEY) }
                CardList {
                    browse.forEachIndexed { i, b ->
                        RouteRow(b.route, b.title, symbol = b.symbol)
                        if (i < browse.lastIndex) RowDivider(50.dp)
                    }
                }
            }
        }
        item {
            Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(6.dp)) {
                FreshnessNote()
                PoweredByFlux()
            }
        }
    }
}

@Composable
fun SearchField(onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().height(46.dp).card(14.dp).clickable(onClick = onClick).padding(horizontal = 14.dp).semantics { contentDescription = "Search" },
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Icon(icon("magnifyingglass"), null, tint = Brand.secondary)
        Text("Search people, contracts, votes", style = T.body, color = Brand.secondary)
    }
}

@Composable
private fun BallotBanner() {
    val store = LocalStore.current
    val nav = LocalNav.current
    val a3 = store.amendment3 ?: return
    if (!a3.isBeforeVote()) return
    val day = a3.vote?.let { Dates.parse(it) } ?: return
    val year = 1 // FY2029, the year the site leads with
    Row(
        Modifier.fillMaxWidth().background(Brand.salmon.copy(alpha = 0.12f), RoundedCornerShape(16.dp)).clickable { nav.push(Route.Amendment3()) }.padding(14.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Column(Modifier.size(46.dp).background(Brand.salmonFill, RoundedCornerShape(12.dp)), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
            Text(Dates.format(day, "MMM").uppercase(), style = T.caption2.copy(fontWeight = FontWeight.Bold), color = Color.White)
            Text(Dates.format(day, "d"), style = T.number, color = Color.White)
        }
        Column(Modifier.weight(1f)) {
            Text("Amendment 3 is on the ballot", style = T.subheadBold.copy(fontWeight = FontWeight.Bold), color = Brand.text)
            Text("−${Format.compactMoney(a3.localImpact(year))} to local budgets by ${Amendment3Model.fiscalYears[year]} · needs 60%", style = T.caption, color = Brand.secondary)
        }
        Icon(icon("chevron.right"), null, tint = Brand.salmon, modifier = Modifier.size(18.dp))
    }
}

/** The saved home address (tax estimate, representatives, schools, flood zone), or a prompt to look one up. */
@Composable
private fun AddressCard() {
    val store = LocalStore.current
    val nav = LocalNav.current
    val home = store.home
    CardList {
        if (home != null) {
            AddressCardRow("house.fill", "My Address", home.display, "Tax estimate, representatives, schools, flood zone") { nav.push(Route.Address(home)) }
            RowDivider(62.dp)
            Row(
                Modifier.fillMaxWidth().clickable { nav.push(Route.MyAddress) }.padding(horizontal = 14.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Icon(icon("magnifyingglass"), null, tint = Brand.navy, modifier = Modifier.size(18.dp))
                Text("Look up another address", style = T.subhead.copy(fontWeight = FontWeight.Medium), color = Brand.navy)
            }
        } else {
            AddressCardRow("mappin.and.ellipse", "My Address", "What applies to your address?",
                "Property tax estimate, who represents you, schools, flood and evacuation zones") { nav.push(Route.MyAddress) }
        }
    }
}

@Composable
private fun AddressCardRow(symbol: String, eyebrow: String, title: String, detail: String, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().clickable(onClick = onClick).padding(14.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Box(Modifier.size(36.dp).background(Brand.navy.copy(alpha = 0.1f), RoundedCornerShape(10.dp)), contentAlignment = Alignment.Center) {
            Icon(icon(symbol), null, tint = Brand.navy, modifier = Modifier.size(20.dp))
        }
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(eyebrow, style = T.caption, color = Brand.secondary)
            Text(title, style = T.headline, color = Brand.text)
            Text(detail, style = T.caption, color = Brand.secondary)
        }
        Chevron()
    }
}

private data class MeetingDay(val key: String, val date: Instant, val meetings: List<Meeting>)

@Composable
private fun MeetingsSection() {
    val store = LocalStore.current
    val nav = LocalNav.current
    val limit = Instant.now().plusSeconds(14 * 86_400)
    val soon = Meeting.upcoming(store.meetings).filter { (it.start ?: Instant.MAX) < limit }
    val grouped = soon.groupBy { it.start?.let(Dates::dayKey) ?: "" }
    val days = grouped.keys.sorted().take(4).mapNotNull { k -> grouped[k]?.firstOrNull()?.start?.let { MeetingDay(k, it, grouped[k]!!) } }
    if (days.isEmpty()) return
    var picked by rememberSaveable { mutableStateOf<String?>(null) }
    val current = days.firstOrNull { it.key == picked } ?: days[0]
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        SectionHeader("Meetings coming up", "See all") { nav.push(Route.Meetings) }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            for (d in days) {
                val on = d.key == current.key
                Column(
                    Modifier.weight(1f).heightIn(min = 64.dp)
                        .then(if (on) Modifier.background(Brand.navyFill, RoundedCornerShape(14.dp)) else Modifier.card(14.dp))
                        .clickable { picked = d.key }.padding(vertical = 6.dp)
                        .semantics { contentDescription = "${Dates.display(d.date, false)}, ${d.meetings.size} meetings" },
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    val fg = if (on) Color.White else Brand.text
                    Text(Dates.format(d.date, "EEE").uppercase(), style = T.caption2.copy(fontWeight = FontWeight.SemiBold), color = fg)
                    Text(Dates.format(d.date, "d"), style = T.number, color = fg)
                    Text(if (d.meetings.size == 1) "1 mtg" else "${d.meetings.size} mtgs", style = T.caption2, color = if (on) Color.White.copy(alpha = 0.8f) else Brand.secondary)
                }
            }
        }
        CardList {
            current.meetings.forEachIndexed { i, m ->
                Box(Modifier.clickable { nav.push(Route.MeetingDetail(m.id)) }) { TodayMeetingRow(m) }
                if (i < current.meetings.lastIndex) RowDivider(66.dp)
            }
        }
    }
}

/** A meeting on the Today tab: government badge, board, time and place, and the dollars on its agenda. */
@Composable
fun TodayMeetingRow(meeting: Meeting) {
    val place = meeting.location?.let { loc -> loc.split(" - ").first().split(",").first().trim() }
    val time = if (meeting.hasTime) meeting.start?.let { Dates.format(it, "h:mm a") } else "Time not posted"
    Row(Modifier.fillMaxWidth().heightIn(min = 64.dp).padding(horizontal = 14.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        GovBadge(meeting.govID)
        Column(Modifier.weight(1f)) {
            Text(meeting.boardName, style = T.subheadBold, color = Brand.text, maxLines = 1)
            Text(listOfNotNull(time, place).joinToString(" · "), style = T.caption, color = Brand.secondary, maxLines = 1)
        }
        if (meeting.moneyTotal > 0) {
            Text(
                Format.compactMoney(meeting.moneyTotal), style = T.caption.copy(fontWeight = FontWeight.Bold), color = Brand.good,
                modifier = Modifier.background(Brand.good.copy(alpha = 0.14f), CircleShape).padding(horizontal = 8.dp, vertical = 4.dp)
                    .semantics { contentDescription = "${Format.compactMoney(meeting.moneyTotal)} on the agenda" },
            )
        } else if (meeting.isExpected) Badge("Expected", Brand.amber)
        Chevron()
    }
}

@Composable
private fun TaxBillSection() {
    val store = LocalStore.current
    val nav = LocalNav.current
    val m = store.taxModel ?: return
    val d = m.districts.firstOrNull { it.id == store.savedDistrict } ?: m.districts.firstOrNull() ?: return
    val value = 250_000.0
    val e = TaxCalculator.estimate(m, d, value, true)
    fun name(g: String) = if (g == "city") "City" else m.groupName(g)
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        SectionHeader("Your tax bill", "Change") { nav.push(Route.TaxCalculator(d.id)) }
        Column(
            Modifier.fillMaxWidth().card(18.dp).clickable { nav.push(Route.TaxCalculator(d.id, value, true)) }.padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Row(verticalAlignment = Alignment.Bottom) {
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text("${d.label} · ${Format.compactMoney(value)} home, homestead", style = T.caption, color = Brand.secondary)
                    Text(buildAnnotatedString {
                        withStyle(SpanStyle(fontFamily = Poppins, fontWeight = FontWeight.Bold, fontSize = T.bigNumber.fontSize * 1.2f, color = Brand.text)) { append(Format.money(e.total)) }
                        withStyle(SpanStyle(fontSize = T.subhead.fontSize, color = Brand.secondary)) { append(" / yr") }
                    })
                }
                Text("Every line", style = T.subheadBold, color = Brand.navy)
            }
            StackBar(e.byGroup.map { Triple(name(it.group), it.amount, taxColor(it.group)) })
            for (row in e.byGroup.take(6).chunked(3)) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    for (g in row) Column(Modifier.weight(1f)) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(5.dp)) {
                            Box(Modifier.size(8.dp).background(taxColor(g.group), RoundedCornerShape(2.dp)))
                            Text(name(g.group), style = T.caption, color = Brand.secondary, maxLines = 1)
                        }
                        Text(Format.money(g.amount), style = T.subheadBold.copy(fontWeight = FontWeight.Bold), color = Brand.text)
                    }
                    repeat(3 - row.size) { Spacer(Modifier.weight(1f)) }
                }
            }
        }
        val home = store.home
        if (home != null) LinkLine("Exact estimate for ${home.display}", "house.fill") { nav.push(Route.Address(home)) }
        else LinkLine("Use your address for an exact estimate", "mappin.and.ellipse") { nav.push(Route.MyAddress) }
    }
}

@Composable
private fun NumbersSection() {
    val g = LocalStore.current.governments
    if (g.isEmpty()) return
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("By the numbers", style = T.title3, color = Brand.text)
        data class Tile(val value: String, val label: String, val bars: List<Double>, val color: Color, val route: Route)
        val tiles = listOf(
            Tile(Format.compactMoney(g.mapNotNull { it.propertyTaxLevy }.sum()), "Property tax levied", g.mapNotNull { it.propertyTaxLevy }, Brand.navy, Route.TaxCalculator()),
            Tile(Format.compactMoney(g.mapNotNull { it.femaMichael }.sum()), "FEMA after Michael", g.mapNotNull { it.femaMichael }, Brand.blue, Route.Dataset("fema-michael-projects")),
            Tile(Format.compactMoney(g.mapNotNull { it.debtTotal }.sum()), "Owed by governments", g.mapNotNull { it.debtTotal }, Brand.salmon, Route.Dataset("debt")),
            Tile(Format.number(g.mapNotNull { it.auditFindings }.sum()), "Audit findings", g.mapNotNull { it.auditFindings?.toDouble() }, Brand.amber, Route.Dataset("audit-findings")),
        )
        Grid2(tiles) { t, mod -> NumberTile(t.value, t.label, t.bars, t.color, t.route, mod) }
        Text("County, school district and the seven cities.", style = T.caption, color = Brand.secondary)
    }
}

