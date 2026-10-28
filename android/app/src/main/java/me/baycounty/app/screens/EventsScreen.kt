package me.baycounty.app.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import me.baycounty.app.Route
import me.baycounty.app.ui.*
import me.baycounty.kit.Chambers
import me.baycounty.kit.Events
import me.baycounty.kit.Row as DataRow
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Events (/events): what's happening around the county in the next two months. Same as the iOS EventsView. */
@Composable
fun EventsScreen() {
    val store = LocalStore.current
    LaunchedEffect(Unit) { store.load(Events.DATASET) }
    val rows = store.rows[Events.DATASET] ?: emptyList()
    val today = Events.todayKey()
    var town by rememberSaveable { mutableStateOf("") }
    var kind by rememberSaveable { mutableStateOf("") }
    var oneOff by rememberSaveable { mutableStateOf(false) }
    var query by rememberSaveable { mutableStateOf("") }
    var days by rememberSaveable { mutableIntStateOf(7) }
    val list = Events.upcoming(rows, today, town.ifEmpty { null }, kind.ifEmpty { null }, oneOff, query)
    val groups = Events.byDay(list, today)

    Screen("Events", onRefresh = { store.load(Events.DATASET, force = true) }, spacing = 18) {
        item {
            PageHero(
                "Community · Calendar", "Events in Bay County",
                "What's happening around the county, from the county and city calendars, the library system, the visitor bureaus and the chambers.",
                symbol = "calendar", tone = Tone.SALMON,
            )
        }
        if (rows.isEmpty()) {
            item { val e = store.errors[Events.DATASET]; if (e != null) Unavailable("Couldn't load events", e) else Loading() }
            return@Screen
        }
        item {
            val all = Events.upcoming(rows, today)
            val week = Events.plusDays(7)
            Grid2(listOf(0, 1)) { i, m ->
                if (i == 0) KPICard("This week", "${all.count { (it.string("starts") ?: "").take(10) <= week }}", m, "Events in the next seven days", "calendar", Tone.SALMON)
                else KPICard("Public meetings", "${all.count { it.string("category") == "Public meeting" }}", m, "Commissions, boards and workshops", "building.columns", Tone.BLUE)
            }
        }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                ChipRow(listOf("" to "Every town") + Events.towns(rows).map { it to it }, town) { town = it; days = 7 }
                ChipRow(listOf("" to "All kinds") + Events.kinds.map { it to it }, kind) { kind = it; days = 7 }
                OutlinedTextField(
                    query, { query = it }, Modifier.fillMaxWidth(), singleLine = true,
                    placeholder = { Text("Search events, places, organizers", style = T.subhead) },
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                )
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("One-off events only", style = T.subhead, color = Brand.text, modifier = Modifier.weight(1f))
                    Switch(oneOff, { oneOff = it })
                }
            }
        }
        if (groups.isEmpty()) item { Text("No upcoming events match.", style = T.subhead, color = Brand.secondary, modifier = Modifier.fillMaxWidth().card(14.dp).padding(14.dp)) }
        for ((day, rs) in groups.take(days)) {
            item(key = day) {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(Events.dayLabel(day, today), style = T.headline, color = Brand.text, modifier = Modifier.weight(1f))
                        Text("${rs.size}", style = T.caption, color = Brand.secondary)
                    }
                    CardList {
                        rs.forEachIndexed { i, r ->
                            EventRow(r, showSource = true)
                            if (i < rs.lastIndex) RowDivider(86.dp)
                        }
                    }
                }
            }
        }
        if (groups.size > days) item { CardList { ShowMoreRow(false, "Show more days") { days += 7 } } }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Times are local. Details change, so check the organizer's page (tap an event) before you go.", style = T.caption, color = Brand.secondary)
                FreshnessNote(Events.DATASET)
            }
        }
    }
}

/** One event: time, title, place and kind. Opens the organizer's page. */
@Composable
fun EventRow(r: DataRow, showSource: Boolean = false) {
    val opener = rememberOpener()
    Row(
        Modifier.fillMaxWidth().clickable { opener.open(r.url("url")) }.padding(horizontal = 14.dp, vertical = 11.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(Events.time(r), style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = Brand.secondary, modifier = Modifier.width(60.dp))
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Text(r.string("title") ?: "", style = T.subheadBold, color = Brand.text)
            val place = listOfNotNull(r.string("venue"), r.string("town"), if (showSource) r.string("source") else null).joinToString(" · ")
            if (place.isNotEmpty()) Text(place, style = T.caption, color = Brand.secondary)
            Badge(r.string("category") ?: "", eventColor(r.string("category")))
        }
    }
}

@Composable
private fun eventColor(c: String?) = when (c) {
    "Public meeting" -> Brand.navy
    "Library" -> Brand.good
    "Chamber" -> Brand.amber
    else -> Brand.salmon
}

