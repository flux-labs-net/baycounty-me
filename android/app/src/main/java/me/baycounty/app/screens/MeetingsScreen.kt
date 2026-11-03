package me.baycounty.app.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import me.baycounty.app.Route
import me.baycounty.app.ui.*
import me.baycounty.kit.AgendaItem
import me.baycounty.kit.BayCountyClient
import me.baycounty.kit.Dates
import me.baycounty.kit.Format
import me.baycounty.kit.Governments
import me.baycounty.kit.Meeting

private fun shortGov(id: String) = when (id) { "county" -> "County"; "schools" -> "Schools"; else -> Governments.names[id] ?: id }

/** The Meetings tab: every upcoming public meeting by day, with chips for each government that has one. */
@Composable
fun MeetingsScreen() {
    val store = LocalStore.current
    val nav = LocalNav.current
    val o = rememberOpener()
    var gov by rememberSaveable { mutableStateOf("all") }
    val upcoming = Meeting.upcoming(store.meetings)
    // Signed in: start on the home's own government (its city, or the County Commission outside city limits), once.
    var settled by rememberSaveable { mutableStateOf(false) }
    var homeEmpty by rememberSaveable { mutableStateOf<String?>(null) }
    val home = me.baycounty.app.Account.me?.home
    LaunchedEffect(home?.govKey, upcoming.isNotEmpty()) {
        if (settled || home == null || upcoming.isEmpty()) return@LaunchedEffect
        settled = true
        if (upcoming.any { it.govID == home.govKey }) gov = home.govKey else homeEmpty = home.town ?: "the County Commission"
    }
    val govs = Governments.order.filter { g -> upcoming.any { it.govID == g } }
    val shown = upcoming.filter { gov == "all" || it.govID == gov }
    val days = shown.groupBy { it.start?.let(Dates::dayKey) ?: "" }.toSortedMap()
    Screen(
        "Meetings",
        actions = {
            ToolbarIcon("calendar.badge.plus", "Subscribe to the meetings calendar") {
                o.open(BayCountyClient.meetingsCalendarURL(gov.takeIf { it != "all" }))
            }
        },
        onRefresh = { store.loadMeetings() },
        spacing = 20,
    ) {
        if (govs.size > 1) item { ChipRow(listOf("all" to "All") + govs.map { it to shortGov(it) }, gov) { gov = it; settled = true; homeEmpty = null } }
        homeEmpty?.let { item { Text("No meetings posted for $it yet. Here's the rest of Bay County.", style = T.subhead, color = Brand.secondary) } }
        item { FreshnessNote("meetings") }
        if (shown.isEmpty()) {
            item {
                if (store.meetings.isEmpty() && store.errors["meetings"] == null) Loading()
                else Box(Modifier.card()) {
                    Unavailable("No meetings posted", "Nothing on the calendar for the next few weeks yet.", symbol = "calendar")
                }
            }
        }
        for ((_, ms) in days) {
            val d = ms.first().start ?: continue
            item(key = Dates.dayKey(d)) {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(Dates.format(d, "EEEE, MMMM d"), style = T.headline, color = Brand.text)
                    CardList {
                        ms.forEachIndexed { i, m ->
                            Box(Modifier.clickable { nav.push(Route.MeetingDetail(m.id)) }) { TodayMeetingRow(m) }
                            if (i < ms.lastIndex) RowDivider(66.dp)
                        }
                    }
                }
            }
        }
        item {
            CardList {
                RouteRow(Route.Dataset("agenda-parties"), "Companies on agendas", "Agenda items that name a company, and whether it gave to the board's members", "list.bullet.rectangle")
                RowDivider(50.dp)
                RouteRow(Route.Overlaps, "Where records overlap", "Votes naming donors, bids and more", "link")
            }
        }
    }
}

private enum class AgendaFilter(val label: String) { ALL("All"), SPENDING("Spending"), HEARINGS("Hearings"), OTHER("Other") }

/** One meeting: when and where, the money on its agenda, every agenda item, and its documents. */
@Composable
fun MeetingDetailScreen(id: String) {
    val store = LocalStore.current
    val o = rememberOpener()
    val m = store.meetings.firstOrNull { it.id == id }
    if (m == null) {
        Screen("Meeting") { item { if (store.meetings.isEmpty()) Loading() else Unavailable("Meeting not found", "It may have been removed from the calendar.", symbol = "calendar") } }
        return
    }
    val agenda = m.agenda
    val money = m.moneyItems.filter { it.amount != null }.sortedByDescending { it.amount }
    var filter by rememberSaveable { mutableStateOf(if (money.isNotEmpty()) AgendaFilter.SPENDING else AgendaFilter.ALL) }
    fun matches(a: AgendaItem, f: AgendaFilter) = when (f) {
        AgendaFilter.ALL -> true
        AgendaFilter.SPENDING -> a.kind == AgendaItem.Kind.SPENDING
        AgendaFilter.HEARINGS -> a.kind == AgendaItem.Kind.HEARING
        AgendaFilter.OTHER -> a.kind == AgendaItem.Kind.OTHER
    }
    val counts = AgendaFilter.entries.associateWith { f -> agenda.count { matches(it, f) } }
    Screen(m.boardName, spacing = 22) {
        item {
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(Governments.names[m.govID]?.uppercase() ?: "", style = T.caption.copy(fontWeight = FontWeight.Bold), color = Brand.salmon)
                Text(m.title, style = T.title2, color = Brand.text)
                Text(m.whenText, style = T.subheadBold, color = Brand.text)
                m.location?.let { Text(it, style = T.subhead, color = Brand.secondary) }
                if (m.isExpected) Text("Expected from the board's regular schedule. The agenda isn't posted yet.", style = T.footnote, color = Brand.amber)
                Row(Modifier.padding(top = 6.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Button(
                        onClick = { o.open(BayCountyClient.meetingsCalendarURL(m.govID)) },
                        colors = ButtonDefaults.buttonColors(containerColor = Brand.navyFill, contentColor = Color.White),
                    ) {
                        Icon(icon("calendar.badge.plus"), null, Modifier.size(18.dp)); Text("  Add to Calendar", style = T.subheadBold)
                    }
                    m.agendaURL?.let { url ->
                        OutlinedButton(onClick = { o.open(url) }, border = BorderStroke(1.dp, Brand.hairline)) {
                            Text("Agenda", style = T.subheadBold, color = Brand.navy)
                        }
                    }
                }
            }
        }
        if (money.isNotEmpty()) item {
            val total = m.moneyTotal
            val top = money.take(3)
            val rest = total - top.sumOf { it.amount ?: 0.0 }
            val colors = listOf(Brand.navy, Brand.blue, Brand.salmon)
            val parts = top.mapIndexed { i, a -> Triple(a.shortTitle, a.amount ?: 0.0, colors[i]) } +
                (if (rest > 0) listOf(Triple("Everything else", rest, Brand.tertiary)) else emptyList())
            Column(Modifier.fillMaxWidth().card(18.dp).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("Money on the agenda", style = T.caption, color = Brand.secondary)
                Text(Format.money(total), style = T.bigNumber, color = Brand.text)
                StackBar(parts)
                parts.forEach { (label, v, c) -> LegendRow(c, label, Format.compactMoney(v)) }
            }
        }
        if (agenda.isNotEmpty()) item {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("Agenda", style = T.title3, color = Brand.text)
                ChipRow(AgendaFilter.entries.filter { it == AgendaFilter.ALL || counts[it]!! > 0 }.map { it to it.label }, filter, counts) { filter = it }
                val items = agenda.filter { matches(it, filter) }
                CardList {
                    items.forEachIndexed { i, a ->
                        TextRow(a.shortTitle, value = a.amount?.let { Format.compactMoney(it) },
                            badge = if (a.kind == AgendaItem.Kind.HEARING) a.kind.label to Brand.amber else null)
                        if (i < items.lastIndex) RowDivider()
                    }
                }
                Text("From the posted agenda. Amounts are the first dollar figure in each item.", style = T.footnote, color = Brand.secondary)
            }
        }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("Documents", style = T.title3, color = Brand.text)
                CardList {
                    val docs = listOfNotNull(
                        m.agendaURL?.let { Triple("Agenda", it, "doc.text") },
                        m.packetURL?.let { Triple("Agenda packet", it, "doc.richtext") },
                        m.minutesURL?.let { Triple("Minutes", it, "text.alignleft") },
                        m.detailURL?.let { Triple("Meeting page", it, "safari") },
                        Triple("Email alerts", BayCountyClient.SITE + "/alerts", "bell"),
                    )
                    docs.forEachIndexed { i, (t, u, s) ->
                        WebRow(t, u, symbol = s)
                        if (i < docs.lastIndex) RowDivider(50.dp)
                    }
                }
            }
        }
    }
}
