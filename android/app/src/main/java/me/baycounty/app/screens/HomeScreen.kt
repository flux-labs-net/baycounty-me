package me.baycounty.app.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
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
import me.baycounty.kit.AlertArea
import me.baycounty.kit.Amendment3Model
import me.baycounty.kit.Emergency
import me.baycounty.kit.Dates
import me.baycounty.kit.Format
import me.baycounty.kit.HomeTiles
import me.baycounty.kit.Meeting
import me.baycounty.kit.TaxCalculator
import me.baycounty.kit.Events
import me.baycounty.kit.TodayBrief
import me.baycounty.kit.UtilityLookup
import me.baycounty.kit.Row as DataRow
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

/** The Home tab ("My home dashboard"): a line about your home, an alert strip when notices are active, then tiles that
 *  each give one answer (HomeTiles). Owners lead with the tax bill, renters with utilities. Each tile opens one short
 *  screen. Then your address and this weekend's events. Mirrors the iOS HomeView. */
@Composable
fun HomeScreen() {
    val store = LocalStore.current
    val nav = LocalNav.current
    val home = store.home
    var utilities by remember(home?.id) { mutableStateOf(home?.let { store.utilities[it.id] }) }
    var showSetup by remember { mutableStateOf(false) }
    // Live notices from /api/v1/emergency (the archive dataset is a day old); null until loaded or when offline.
    var liveNotices by remember { mutableStateOf<List<DataRow>?>(null) }
    LaunchedEffect(Unit) {
        store.loadTax(); store.loadAmendment3(); store.load(listOf(Events.DATASET, "beach-conditions", "emergency-notices"))
        liveNotices = runCatching { Emergency.parseFeed(store.client.get(Emergency.FEED_PATH).data).notices }.getOrNull()
    }
    // The saved home's trash day and city. The address isn't logged by the API and the answer isn't kept on disk.
    LaunchedEffect(home?.id) { utilities = home?.let { runCatching { store.loadUtilities(it) }.getOrNull() } }
    if (showSetup) { HomeSetupScreen { showSetup = false }; return }
    Screen(
        "Home",
        navigationIcon = { BayMarkButton { nav.push(Route.About) } },
        actions = {
            ToolbarIcon("magnifyingglass", "Search") { nav.push(Route.Search) }
            ToolbarIcon("person.crop.circle", if (me.baycounty.app.Account.signedIn) "My home" else "Sign in") { nav.push(Route.MyHome) }
            ToolbarIcon("bell", "Emergencies and alerts") { nav.push(Route.Emergency) }
        },
        onRefresh = { store.refreshAll() },
        spacing = 20,
    ) {
        item { Greeting(utilities) }
        val notices = liveNotices ?: store.rows["emergency-notices"] ?: emptyList()
        HomeTiles.alert(notices)?.let { a -> item { AlertStrip(a) } }
        AlertArea.firstMapped(notices)?.let { (n, area) -> item { AlertMapCard(n, area) } }
        item { TileGrid(utilities) { showSetup = true } }
        item { AddressCard { showSetup = true } }
        item { WeekendSection() }
        item {
            Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(6.dp)) {
                FreshnessNote()
                PoweredByFlux()
            }
        }
    }
}

private val LocalTenure @Composable get() = LocalStore.current.tenure ?: HomeTiles.Tenure.UNSET

/** "YOUR HOME · LYNN HAVEN · RENTING" over "Good morning", or "BAY COUNTY" before a home is saved. */
@Composable
private fun Greeting(utilities: UtilityLookup?) {
    val store = LocalStore.current
    val place = if (store.home == null) null else utilities?.let { if (it.area == "county") "Bay County" else it.areaName } ?: "Bay County"
    Column(Modifier.semantics(mergeDescendants = true) { heading() }, verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(HomeTiles.eyebrow(place, LocalTenure).uppercase(), style = T.caption.copy(fontWeight = FontWeight.SemiBold, letterSpacing = 0.6.sp), color = Brand.secondary)
        Text(TodayBrief.greeting(TodayBrief.hour()), style = T.bigNumber.copy(fontSize = 30.sp, lineHeight = 36.sp, fontWeight = FontWeight.SemiBold), color = Brand.text)
    }
}

/** Active notices, the most urgent kind first; opens Emergencies. */
@Composable
private fun AlertStrip(a: HomeTiles.Alert) {
    val nav = LocalNav.current
    Row(
        Modifier.fillMaxWidth().background(Brand.amber.copy(alpha = 0.16f), RoundedCornerShape(14.dp)).clickable { nav.push(Route.Emergency) }
            .padding(14.dp).semantics(mergeDescendants = true) {},
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Icon(icon("exclamationmark.triangle"), null, tint = Brand.amber, modifier = Modifier.size(22.dp))
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(a.title, style = T.subheadBold, color = Brand.text)
            Text(a.detail, style = T.caption, color = Brand.secondary)
        }
        Chevron()
    }
}

/** Where a live alert applies, when the government drew it on a map; opens Emergencies. */
@Composable
private fun AlertMapCard(n: DataRow, area: AlertArea) {
    val nav = LocalNav.current
    Column(Modifier.fillMaxWidth().card(14.dp).clickable { nav.push(Route.Emergency) }.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(n.string("title") ?: "", style = T.subheadBold, color = Brand.text)
        n.string("source")?.let { Text(it, style = T.caption, color = Brand.secondary) }
        AlertMap(area, Modifier.fillMaxWidth().height(180.dp))
    }
}

/** Two tiles a row; with an odd count the lead tile spans the first row. */
@Composable
private fun TileGrid(utilities: UtilityLookup?, onSetup: () -> Unit) {
    val store = LocalStore.current
    val nav = LocalNav.current
    val o = rememberOpener()
    val m = store.taxModel
    val district = m?.let { HomeTiles.taxDistrict(it, utilities, store.savedDistrict) }
    val taxTotal = if (m != null && district != null) TaxCalculator.estimate(m, district, HomeTiles.SAMPLE_VALUE, true).total else null
    val election = store.amendment3?.takeIf { it.isBeforeVote() }?.vote
    val tiles = HomeTiles.tiles(LocalTenure, store.home != null, utilities, taxTotal, store.rows["beach-conditions"] ?: emptyList(), store.meetings, election)
    fun open(t: HomeTiles.Target) = when (t) {
        HomeTiles.Target.SETUP -> onSetup()
        HomeTiles.Target.TAX_BILL -> nav.push(Route.TaxBill(district?.id))
        HomeTiles.Target.UTILITIES -> nav.push(Route.Utilities(store.home))
        HomeTiles.Target.BEACHES -> nav.push(Route.Beaches)
        HomeTiles.Target.MEETINGS -> nav.push(Route.Meetings)
        HomeTiles.Target.ELECTION -> o.openSite("/elections/voting")
        HomeTiles.Target.REPRESENTATIVES -> nav.push(store.home?.let { Route.Address(it) } ?: Route.People)
        HomeTiles.Target.SCHOOLS -> nav.push(Route.Schools)
    }
    val lead = if (tiles.size % 2 == 1) tiles.take(1) else emptyList()
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        for (t in lead) HomeTile(t, Modifier.fillMaxWidth(), wide = true) { open(t.target) }
        for (pair in tiles.drop(lead.size).chunked(2)) {
            Row(Modifier.fillMaxWidth().height(IntrinsicSize.Min), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                for (t in pair) HomeTile(t, Modifier.weight(1f).fillMaxHeight()) { open(t.target) }
                if (pair.size == 1) Spacer(Modifier.weight(1f))
            }
        }
    }
}

/** One tile: a label with its icon, one big answer, and a line under it. The lead tile is navy. */
@Composable
private fun HomeTile(t: HomeTiles.Tile, modifier: Modifier, wide: Boolean = false, onClick: () -> Unit) {
    val tone = when (t.tone) { "teal" -> Brand.good; "amber" -> Brand.amber; "salmon" -> Brand.salmon; else -> Brand.navy }
    val box = if (t.featured) modifier.background(Brand.navyFill, RoundedCornerShape(16.dp)) else modifier.card(16.dp)
    Column(
        box.clickable(onClick = onClick).then(if (wide) Modifier else Modifier.heightIn(min = 118.dp)).padding(14.dp).semantics(mergeDescendants = true) {},
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            Icon(icon(t.symbol), null, tint = if (t.featured) Color.White.copy(alpha = 0.9f) else tone, modifier = Modifier.size(16.dp))
            Text(t.eyebrow, style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = if (t.featured) Color.White.copy(alpha = 0.9f) else tone)
        }
        Text(t.value, style = T.bigNumber.copy(fontSize = 22.sp, lineHeight = 28.sp, fontWeight = FontWeight.SemiBold), color = if (t.featured) Color.White else Brand.text, maxLines = 2)
        Text(t.detail, style = T.caption, color = if (t.featured) Color.White.copy(alpha = 0.85f) else Brand.secondary)
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
    fun pick(rs: List<DataRow>): Pair<Boolean, List<DataRow>> {
        val w = TodayBrief.weekendEvents(rs, today)
        return if (w.isEmpty()) false to Events.featured(rs, today, Events.plusDays(21)).take(4) else true to w
    }
    // Signed in: the home's town first; with nothing listed there, say so and show the rest of the county.
    val town = me.baycounty.app.Account.me?.home?.town
    val mine = town?.let { t -> pick(rows.filter { it.string("town") == t }) }
    val elsewhere = town != null && mine?.second?.isEmpty() == true
    val (isWeekend, picks) = mine?.takeIf { it.second.isNotEmpty() } ?: pick(rows)
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        SectionHeader((if (isWeekend) "This weekend" else "Coming up") + (if (town != null && !elsewhere) " in $town" else ""), "All events") { nav.push(Route.Events) }
        if (elsewhere) Text("Nothing listed in $town yet. Here's the rest of Bay County.", style = T.subhead, color = Brand.secondary)
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

/** Everything for the saved home (tax estimate, representatives, schools, flood zone), or a prompt to set one. */
@Composable
private fun AddressCard(onSetup: () -> Unit) {
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
            RowDivider()
            Row(
                Modifier.fillMaxWidth().clickable(onClick = onSetup).padding(horizontal = 14.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text("Own or rent", style = T.subhead.copy(fontWeight = FontWeight.Medium), color = Brand.text, modifier = Modifier.weight(1f))
                Text(store.tenure?.takeIf { it != HomeTiles.Tenure.UNSET }?.label ?: "Not set", style = T.subhead, color = Brand.secondary)
                Chevron()
            }
        } else {
            AddressCardRow("mappin.and.ellipse", "My Address", "What applies to your address?",
                "Trash day, who represents you, schools, flood and evacuation zones", onSetup)
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

