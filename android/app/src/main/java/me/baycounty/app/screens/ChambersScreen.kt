package me.baycounty.app.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
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
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import me.baycounty.app.Route
import me.baycounty.app.ui.*
import me.baycounty.kit.BayCountyClient
import me.baycounty.kit.Chambers
import me.baycounty.kit.Format
import me.baycounty.kit.Row as DataRow
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Chambers of commerce (/chambers): the two chambers, what's coming up, regular programs, and who leads them.
 *  Same sections as the iOS ChambersView. */
@Composable
fun ChambersScreen() {
    val store = LocalStore.current
    LaunchedEffect(Unit) { store.load(Chambers.datasets) }
    val chambers = store.rows["chambers"] ?: emptyList()
    val leaders = store.rows["chamber-leaders"] ?: emptyList()
    val events = store.rows["chamber-events"] ?: emptyList()
    val today = LocalDate.now(ZoneId.of("America/Chicago")).toString()
    var chamber by rememberSaveable { mutableStateOf("") }
    var kind by rememberSaveable { mutableStateOf(Chambers.Kind.ALL) }
    var showAll by rememberSaveable { mutableStateOf(false) }
    var boardChamber by rememberSaveable { mutableStateOf("bay-chamber") }

    Screen("Chambers", onRefresh = { Chambers.datasets.forEach { store.load(it, force = true) } }, spacing = 22) {
        item {
            PageHero(
                "People · Business community", "Chambers of commerce",
                "Who leads the Bay County and Panama City Beach chambers, what's coming up, and the public money they get.",
                symbol = "storefront", tone = Tone.TEAL,
            )
        }
        if (chambers.isEmpty()) {
            item {
                val e = Chambers.datasets.firstNotNullOfOrNull { store.errors[it] }
                if (e != null) Unavailable("Couldn't load the chambers", e) else Loading()
            }
            return@Screen
        }
        item { Kpis(chambers, leaders, events, today) }
        item { SimpleVersion() }
        for (c in chambers) item { ChamberCard(c, leaders) }
        item {
            EventsSection(chambers, events, today, chamber, kind, showAll,
                onChamber = { chamber = it; showAll = false }, onKind = { kind = it; showAll = false }, onMore = { showAll = !showAll })
        }
        item { ProgramsSection(chambers, events) }
        item { BoardSection(chambers, leaders, boardChamber) { boardChamber = it } }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                CardList {
                    RouteRow(Route.Dataset("nonprofits"), "All nonprofits", symbol = "heart.text.square")
                    RowDivider(50.dp)
                    WebRow("Chambers on BayCounty.me", "${BayCountyClient.SITE}/chambers", "Board members' businesses and public money", symbol = "safari")
                }
                FreshnessNote("chamber-events")
            }
        }
    }
}

@Composable
private fun Kpis(chambers: List<DataRow>, leaders: List<DataRow>, events: List<DataRow>, today: String) {
    val up = Chambers.upcoming(events, today)
    val staff = leaders.count { it.string("role_group") == "Staff" }
    val money = chambers.sumOf { it.number("public_money_total") ?: 0.0 }
    val revenue = chambers.sumOf { it.number("revenue") ?: 0.0 }
    Grid2(listOf(0, 1, 2, 3)) { i, m ->
        when (i) {
            0 -> KPICard("Board seats", "${Chambers.boardSeats(leaders)}", m, "Across both chambers, plus $staff staff", "person.3", Tone.BLUE)
            1 -> KPICard("Coming up", "${up.size}", m, "${up.count { it.bool("chamber_event") == true }} chamber events, the rest community events", "calendar", Tone.SALMON)
            2 -> KPICard("Paid by tourism agencies", Format.compactMoney(money), m, "Event fees and sponsorships, FY2024 to FY2026", "sun.max", Tone.AMBER)
            else -> KPICard("Revenue", Format.compactMoney(revenue), m, "Both chambers, latest IRS filings", "chart.bar", Tone.TEAL)
        }
    }
}

@Composable
private fun SimpleVersion() {
    PageSection("The simple version", "lightbulb", Tone.AMBER) {
        Column(Modifier.fillMaxWidth().card(14.dp).padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            for ((b, rest) in listOf(
                "A private group of businesses." to " Members pay dues to belong. A chamber is a nonprofit business league, not a government agency.",
                "It connects, promotes and speaks up." to " Networking events, leadership classes, a member directory, and positions on local issues.",
                "Why it's here." to " Their boards bring together business owners, public agency heads and military leaders, and the tourism agencies pay them for events and sponsorships.",
            )) {
                Text(buildAnnotatedString { withStyle(SpanStyle(fontWeight = FontWeight.SemiBold)) { append(b) }; append(rest) }, style = T.subhead, color = Brand.text)
            }
        }
    }
}

@Composable
private fun ChamberCard(c: DataRow, leaders: List<DataRow>) {
    val id = c.string("chamber_id") ?: ""
    val tone = if (id == "pcb-chamber") Tone.TEAL else Tone.BLUE
    Column(Modifier.fillMaxWidth().card(18.dp).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            ToneIcon("storefront", tone, 44.dp)
            Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(c.string("name") ?: "", style = T.headline, color = Brand.text)
                Text(listOfNotNull(c.string("tagline"), c.number("founded")?.let { "Since ${it.toInt()}" }).joinToString(" · "), style = T.caption, color = Brand.secondary)
            }
        }
        Text(c.string("about") ?: "", style = T.subhead, color = Brand.text)
        Text("Serves ${c.string("serves") ?: ""}.", style = T.footnote, color = Brand.secondary)
        c.string("board_meets")?.let { Text(it, style = T.footnote, color = Brand.secondary) }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Fact("Revenue" + (c.number("latest_return_year")?.let { ", ${it.toInt()}" } ?: ""), Format.compactMoney(c.number("revenue") ?: 0.0), Modifier.weight(1f))
            Fact("IRS staff", c.number("employees")?.let { "${it.toInt()}" } ?: "—", Modifier.weight(1f))
            Fact("Board seats", "${Chambers.boardSeats(leaders, id)}", Modifier.weight(1f))
        }
        CardList {
            WebRow("Website", c.url("website"), symbol = "globe")
            RowDivider(50.dp)
            WebRow("Member directory", c.url("directory_url"), symbol = "person.2")
            RowDivider(50.dp)
            WebRow("Events calendar", c.url("events_url"), symbol = "calendar")
            RowDivider(50.dp)
            WebRow("Profile and connections", Chambers.profilePath(c, "page_url")?.let { BayCountyClient.SITE + it }, symbol = "point.3.connected.trianglepath.dotted")
        }
    }
}

@Composable
private fun Fact(label: String, value: String, modifier: Modifier) {
    Column(modifier.background(Brand.hairline.copy(alpha = 0.35f), RoundedCornerShape(12.dp)).padding(horizontal = 10.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(label, style = T.caption2, color = Brand.secondary, maxLines = 1)
        Text(value, style = T.subheadBold, color = Brand.text)
    }
}

@Composable
private fun EventsSection(
    chambers: List<DataRow>, events: List<DataRow>, today: String, chamber: String, kind: Chambers.Kind, showAll: Boolean,
    onChamber: (String) -> Unit, onKind: (Chambers.Kind) -> Unit, onMore: () -> Unit,
) {
    val chips = listOf("" to "Both") + chambers.map { (it.string("chamber_id") ?: "") to (it.string("short_name") ?: "") }
    val list = Chambers.upcoming(events, today, chamber.ifEmpty { null }, kind)
    val shown = if (showAll) list else list.take(6)
    PageSection("Coming up", "calendar", Tone.SALMON, "From each chamber's public calendar. Check the chamber's page before you go.") {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            ChipRow(chips, chamber) { onChamber(it) }
            ChipRow(Chambers.Kind.entries.map { it to it.label }, kind) { onKind(it) }
            if (list.isEmpty()) {
                Text(
                    if (chamber == "bay-chamber") "The Bay County Chamber's calendar can't be read automatically yet. See its events calendar and regular programs."
                    else "No upcoming events match.",
                    style = T.subhead, color = Brand.secondary, modifier = Modifier.fillMaxWidth().card(14.dp).padding(14.dp),
                )
            } else {
                CardList {
                    shown.forEachIndexed { i, ev ->
                        EventRow(ev)
                        if (i < shown.lastIndex) RowDivider(72.dp)
                    }
                    if (list.size > 6) {
                        RowDivider(0.dp)
                        ShowMoreRow(showAll, "Show ${list.size - shown.size} more", onMore)
                    }
                }
            }
        }
    }
}

private val month = DateTimeFormatter.ofPattern("MMM", Locale.US)
private val dayNum = DateTimeFormatter.ofPattern("d", Locale.US)
private val weekday = DateTimeFormatter.ofPattern("EEE", Locale.US)

@Composable
private fun EventRow(ev: DataRow) {
    val opener = rememberOpener()
    val d = Chambers.date(ev)
    val isChamber = ev.bool("chamber_event") == true
    Row(
        Modifier.fillMaxWidth().clickable { opener.open(ev.url("url")) }.padding(horizontal = 14.dp, vertical = 11.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Column(
            Modifier.width(48.dp).background(Brand.surface, RoundedCornerShape(10.dp)).border(1.dp, Brand.hairline, RoundedCornerShape(10.dp)),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                d?.format(month)?.uppercase() ?: "", style = T.caption2.copy(fontWeight = FontWeight.Bold), color = Color.White, textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth().background(Brand.salmonFill, RoundedCornerShape(topStart = 10.dp, topEnd = 10.dp)).padding(vertical = 2.dp),
            )
            Text(d?.format(dayNum) ?: "", style = T.number, color = Brand.text)
            Text(d?.format(weekday) ?: "", style = T.caption2, color = Brand.secondary, modifier = Modifier.padding(bottom = 4.dp))
        }
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Text(ev.string("title") ?: "", style = T.subheadBold, color = Brand.text)
            Text(Chambers.whenLabel(ev), style = T.caption, color = Brand.secondary)
            val place = listOfNotNull(ev.string("venue"), ev.string("city")).joinToString(", ")
            if (place.isNotEmpty()) Text(place, style = T.caption, color = Brand.secondary)
            Badge(
                if (isChamber) ev.string("chamber") ?: "Chamber" else "Community event",
                if (isChamber) (if (ev.string("chamber_id") == "pcb-chamber") Brand.good else Brand.navy) else Brand.secondary,
            )
        }
    }
}

@Composable
private fun ProgramsSection(chambers: List<DataRow>, events: List<DataRow>) {
    val opener = rememberOpener()
    PageSection("Regular programs", "repeat", Tone.AMBER, "Monthly meetings, yearly events and leadership classes") {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            for (c in chambers) {
                val ps = Chambers.programs(events, c.string("chamber_id") ?: "")
                if (ps.isEmpty()) continue
                Text(c.string("short_name") ?: "", style = T.subheadBold, color = Brand.secondary)
                CardList {
                    ps.forEachIndexed { i, p ->
                        TextRow(
                            p.string("title") ?: "", listOfNotNull(p.string("schedule"), p.string("about")).joinToString(" · "),
                            modifier = Modifier.clickable { opener.open(p.url("url")) },
                        )
                        if (i < ps.lastIndex) RowDivider()
                    }
                }
            }
        }
    }
}

@Composable
private fun BoardSection(chambers: List<DataRow>, leaders: List<DataRow>, boardChamber: String, onPick: (String) -> Unit) {
    val chips = chambers.map { (it.string("chamber_id") ?: "") to (it.string("short_name") ?: "") }
    val groups = Chambers.leaders(leaders, boardChamber)
    val past = Chambers.pastChairs(leaders, boardChamber)
    PageSection("Who leads them", "person.3", Tone.BLUE, "As listed on each chamber's website. Tap a name for every other board, business and record it appears in.") {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            ChipRow(chips, boardChamber) { onPick(it) }
            for ((g, rows) in groups) {
                Text(Chambers.groupLabel(g), style = T.subheadBold, color = Brand.secondary)
                CardList {
                    rows.forEachIndexed { i, r ->
                        LeaderRow(r)
                        if (i < rows.lastIndex) RowDivider(64.dp)
                    }
                }
            }
            if (past.isNotEmpty()) {
                Text("Past chairs since 2016", style = T.subheadBold, color = Brand.secondary)
                CardList {
                    past.forEachIndexed { i, r ->
                        LeaderRow(r, r.number("year")?.toInt()?.toString())
                        if (i < past.lastIndex) RowDivider(64.dp)
                    }
                }
            }
        }
    }
}

@Composable
private fun LeaderRow(r: DataRow, detail: String? = null) {
    val nav = LocalNav.current
    val opener = rememberOpener()
    val name = r.string("person_name") ?: ""
    val sub = detail ?: listOfNotNull(r.string("title"), r.string("organization")).joinToString(" · ")
    val pid = Chambers.personID(r)
    val path = Chambers.profilePath(r, "person_url")
    Row(
        Modifier.fillMaxWidth()
            .clickable { if (pid != null) nav.push(Route.Person(pid)) else if (path != null) opener.openSite(path) }
            .padding(horizontal = 14.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        PersonInitials(name, 38.dp, Chambers.profilePath(r, "photo")?.let { BayCountyClient.SITE + it })
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(name, style = T.subheadBold, color = Brand.text)
            if (sub.isNotEmpty()) Text(sub, style = T.caption, color = Brand.secondary)
        }
        Chevron()
    }
}
