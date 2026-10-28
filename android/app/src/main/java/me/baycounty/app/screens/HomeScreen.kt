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
import androidx.compose.runtime.remember
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import me.baycounty.app.Route
import me.baycounty.app.ui.*
import me.baycounty.kit.Amendment3Model
import me.baycounty.kit.Dates
import me.baycounty.kit.Format
import me.baycounty.kit.Meeting
import me.baycounty.kit.TaxCalculator
import me.baycounty.kit.Events
import me.baycounty.kit.TodayBrief
import me.baycounty.kit.UtilityLookup
import me.baycounty.kit.Row as DataRow
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

/** The Today tab: a greeting, what's going on right now (beach flag, notices, next meeting, trash day), your address,
 *  this weekend's events, what's coming up at city hall, then your tax bill and the big numbers. */
@Composable
fun HomeScreen() {
    val store = LocalStore.current
    val nav = LocalNav.current
    val o = rememberOpener()
    val home = store.home
    var utilities by remember(home?.id) { mutableStateOf(home?.let { store.utilities[it.id] }) }
    LaunchedEffect(Unit) { store.loadTax(); store.loadAmendment3(); store.load(listOf(Events.DATASET, "beach-conditions", "emergency-notices")) }
    // The saved home's trash day. The address isn't logged by the API and the answer isn't kept on disk.
    LaunchedEffect(home?.id) { utilities = home?.let { runCatching { store.loadUtilities(it) }.getOrNull() } }
    Screen(
        "Today",
        navigationIcon = { BayMarkButton { nav.push(Route.About) } },
        actions = {
            ToolbarIcon("magnifyingglass", "Search") { nav.push(Route.Search) }
            ToolbarIcon("bubble.left.and.text.bubble.right", "Ask a question") { o.openSite("/ask") }
            ToolbarIcon("person.crop.circle", if (me.baycounty.app.Account.signedIn) "My home" else "Sign in") { nav.push(Route.MyHome) }
            ToolbarIcon("bell", "Emergencies and alerts") { nav.push(Route.Emergency) }
        },
        onRefresh = { store.refreshAll() },
        spacing = 24,
    ) {
        item { Greeting(utilities) }
        item { BallotBanner() }
        item { RightNow(TodayBrief.trashDays(utilities)) }
        item { AddressCard() }
        item { WeekendSection() }
        item { CityHallSection() }
        item { TaxBillSection() }
        item { NumbersSection() }
        item {
            Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(6.dp)) {
                FreshnessNote()
                PoweredByFlux()
            }
        }
    }
}

/** "Good morning" over "WEDNESDAY, OCT 28 · LYNN HAVEN": the date, and the saved home's city once it's known. */
@Composable
private fun Greeting(utilities: UtilityLookup?) {
    val place = utilities?.let { if (it.area == "county") "Bay County" else it.areaName } ?: "Bay County"
    val date = TodayBrief.dateLine(Events.todayKey())
    Column(Modifier.semantics(mergeDescendants = true) { heading() }, verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text("$date · $place".uppercase(), style = T.caption.copy(fontWeight = FontWeight.SemiBold, letterSpacing = 0.6.sp), color = Brand.secondary)
        Text(TodayBrief.greeting(TodayBrief.hour()), style = T.bigNumber.copy(fontSize = 30.sp, lineHeight = 36.sp), color = Brand.text)
    }
}

/** Beach flag, active notices, next meeting and trash day, two by two. Same cards as the site's home page. */
@Composable
private fun RightNow(trashDays: String?) {
    val store = LocalStore.current
    val nav = LocalNav.current
    val cards = TodayBrief.cards(store.rows["beach-conditions"] ?: emptyList(), store.rows["emergency-notices"] ?: emptyList(), store.meetings, trashDays)
    Grid2(cards) { c, m ->
        val route = when (c.target) {
            TodayBrief.Target.BEACHES -> Route.Beaches
            TodayBrief.Target.EMERGENCY -> Route.Emergency
            TodayBrief.Target.MEETINGS -> Route.Meetings
            TodayBrief.Target.UTILITIES -> Route.Utilities(store.home)
        }
        val tone = when (c.tone) { "teal" -> Tone.TEAL; "amber" -> Tone.AMBER; "salmon" -> Tone.SALMON; else -> Tone.BLUE }
        Column(
            m.heightIn(min = 128.dp).card(16.dp).clickable { nav.push(route) }.padding(14.dp).semantics(mergeDescendants = true) {},
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            ToneIcon(c.symbol, tone, 34.dp)
            Text(c.title, style = T.subheadBold, color = Brand.text)
            Text(c.detail, style = T.caption, color = Brand.secondary)
        }
    }
}

/** One-off events this weekend (the coming Friday to Sunday, or the rest of it), or the next few weeks when the
 *  weekend has nothing listed. */
@Composable
private fun WeekendSection() {
    val store = LocalStore.current
    val nav = LocalNav.current
    val rows = store.rows[Events.DATASET] ?: return
    val today = Events.todayKey()
    val weekend = TodayBrief.weekendEvents(rows, today)
    val picks = weekend.ifEmpty { Events.featured(rows, today, Events.plusDays(21)).take(4) }
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        SectionHeader(if (weekend.isEmpty()) "Coming up" else "This weekend", "All events") { nav.push(Route.Events) }
        if (picks.isEmpty()) {
            Text("Nothing listed yet.", style = T.subhead, color = Brand.secondary, modifier = Modifier.fillMaxWidth().card(14.dp).padding(14.dp))
        } else {
            CardList {
                picks.forEachIndexed { i, r ->
                    WeekendEventRow(r)
                    if (i < picks.lastIndex) RowDivider(74.dp)
                }
            }
        }
    }
}

private val weekdayShort = DateTimeFormatter.ofPattern("EEE", Locale.US)

/** An event on the Today tab: a day tile (SAT 31), the title, and when and where. Opens the event's page. */
@Composable
private fun WeekendEventRow(r: DataRow) {
    val opener = rememberOpener()
    val day = runCatching { LocalDate.parse((r.string("starts") ?: "").take(10)) }.getOrNull()
    val c = if (r.string("category") != "Library") Brand.salmon else Brand.navy
    Row(
        Modifier.fillMaxWidth().clickable { opener.open(r.url("url")) }.padding(horizontal = 14.dp, vertical = 11.dp).semantics(mergeDescendants = true) {},
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Column(Modifier.size(46.dp, 50.dp).background(c.copy(alpha = 0.12f), RoundedCornerShape(12.dp)), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
            Text(day?.format(weekdayShort)?.uppercase() ?: "", style = T.caption2.copy(fontWeight = FontWeight.Bold), color = c)
            Text(day?.dayOfMonth?.toString() ?: "", style = T.number.copy(fontWeight = FontWeight.SemiBold), color = c)
        }
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(r.string("title") ?: "", style = T.subheadBold, color = Brand.text)
            val time = Events.time(r).takeIf { it != "All day" }
            Text(listOfNotNull(time, r.string("venue"), r.string("town")).joinToString(" · "), style = T.caption, color = Brand.secondary)
        }
        Chevron()
    }
}

/** The next three public meetings. */
@Composable
private fun CityHallSection() {
    val store = LocalStore.current
    val nav = LocalNav.current
    val next = Meeting.upcoming(store.meetings).take(3)
    if (next.isEmpty()) return
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        SectionHeader("At city hall", "Meetings") { nav.push(Route.Meetings) }
        CardList {
            next.forEachIndexed { i, m ->
                Box(Modifier.clickable { nav.push(Route.MeetingDetail(m.id)) }) { TodayMeetingRow(m, showDay = true) }
                if (i < next.lastIndex) RowDivider(66.dp)
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

/** A meeting on the Today tab: government badge, board, time and place, and the dollars on its agenda. */
@Composable
fun TodayMeetingRow(meeting: Meeting, showDay: Boolean = false) {
    val place = meeting.location?.let { loc -> loc.split(" - ").first().split(",").first().trim() }
    val day = if (showDay) meeting.start?.let { Dates.format(it, "EEE, MMM d") } else null
    val time = if (meeting.hasTime) meeting.start?.let { Dates.format(it, "h:mm a") } else if (showDay) null else "Time not posted"
    Row(Modifier.fillMaxWidth().heightIn(min = 64.dp).padding(horizontal = 14.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        GovBadge(meeting.govID)
        Column(Modifier.weight(1f)) {
            Text(meeting.boardName, style = T.subheadBold, color = Brand.text, maxLines = 1)
            Text(listOfNotNull(day, time, place).joinToString(" · "), style = T.caption, color = Brand.secondary, maxLines = 1)
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

