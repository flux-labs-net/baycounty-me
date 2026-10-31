package me.baycounty.staff

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import me.baycounty.kit.Staff
import me.baycounty.kit.StaffBoard
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

/** An elected official's board dashboard (GET /api/gov?action=official): next meetings and what's on each agenda,
 *  their voting record and the budget. Read only, like the web dashboard; the PDF reports are on the web. */
@Composable
fun BoardScreen(model: StaffModel) {
    val b = model.board ?: return Screen { if (model.loading) CircularProgressIndicator(color = Brand.navy); ErrorLine(model.error) }
    val uri = LocalUriHandler.current
    Screen {
        b.official?.let { o ->
            Column {
                Text(o.name, style = T.number.copy(fontSize = 21.sp, lineHeight = 26.sp), color = Brand.text)
                Text(listOfNotNull(o.seat, o.body, o.since?.let { "since " + Staff.whenOf(it) }).joinToString(" · "), style = T.subhead, color = Brand.secondary)
            }
        }
        val next = b.nextMeeting
        val v = b.votes
        val tiles = mutableListOf<@Composable (Modifier) -> Unit>(
            { m -> ValueTile(next?.let { shortDay(it.date) } ?: "None set", "Next meeting", m) },
            { m -> ValueTile("${b.meetings.upcoming.size}", "Meetings in the next 90 days", m) },
        )
        if (v != null) {
            tiles += { m -> ValueTile("%,d".format(v.count.votes), "Votes on record", m) }
            tiles += { m -> ValueTile("${v.count.split}", "Split votes, ${v.count.onLosingSide} on the losing side", m) }
        }
        b.latestBudget?.let { y -> tiles += { m -> ValueTile(StaffBoard.money(y.total ?: y.generalFund), "FY${y.fiscalYear} adopted budget", m) } }
        tiles += { m -> ValueTile(StaffBoard.money(b.numbers?.contracts?.total), "Contracts, last 12 months", m) }
        TileGrid(tiles)
        Column {
            Eyebrow("Coming up")
            if (b.meetings.upcoming.isEmpty()) Card { Text("No meetings on the calendar for the next 90 days.", style = T.subhead, color = Brand.secondary, modifier = Modifier.padding(14.dp)) }
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) { b.meetings.upcoming.take(4).forEach { MeetingCard(it) } }
        }
        b.numbers?.budget?.history?.takeIf { it.isNotEmpty() }?.let { years ->
            Column {
                Eyebrow("Adopted budget")
                Divided(years.size) { i ->
                    val y = years.reversed()[i]
                    Row(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 11.dp), verticalAlignment = Alignment.CenterVertically) {
                        Text("FY${y.fiscalYear}", style = T.body, color = Brand.text, modifier = Modifier.weight(1f))
                        Text(StaffBoard.money(y.total ?: y.generalFund), style = T.bodyBold, color = Brand.text)
                    }
                }
            }
        }
        Card { RowLink({ uri.openUri("https://baycounty.me/staff#board") }, {
            Text("PDF reports", style = T.bodyBold, color = Brand.navy)
            Text("Meeting briefing, agendas, voting record and numbers, on the web workspace.", style = T.footnote, color = Brand.secondary)
        }) }
        Text("Public record, read from agendas, minutes and budgets. It can't be changed here; flag anything that looks wrong.", style = T.footnote, color = Brand.secondary)
        ErrorLine(model.error)
    }
}

@Composable
private fun MeetingCard(m: StaffBoard.Meeting) {
    val uri = LocalUriHandler.current
    Card {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(longDay(m), style = T.bodyBold, color = Brand.text)
            Text(listOfNotNull(m.boardName, m.location).joinToString(" · "), style = T.footnote, color = Brand.secondary, maxLines = 2, overflow = TextOverflow.Ellipsis)
            m.statusLabel?.let { Chip(it, if (m.status == "cancelled") Brand.salmon else Brand.navy) }
            m.items.take(5).forEach { i ->
                Text("• " + i.title + (i.amount?.let { "  $it" } ?: ""), style = T.subhead, color = Brand.text, maxLines = 3, overflow = TextOverflow.Ellipsis)
            }
            if (m.items.size > 5) Text("And ${m.items.size - 5} more items", style = T.footnote, color = Brand.secondary)
            Row(horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                m.agendaUrl?.let { u -> Text("Agenda", style = T.bodyBold, color = Brand.navy, modifier = Modifier.padding(top = 4.dp).clickable { uri.openUri(u) }) }
                m.packetUrl?.let { u -> Text("Full packet", style = T.bodyBold, color = Brand.navy, modifier = Modifier.padding(top = 4.dp).clickable { uri.openUri(u) }) }
            }
        }
    }
}

/** The official's votes: counts, then the latest motions with how they voted. */
@Composable
fun VotesScreen(model: StaffModel) {
    val b = model.board ?: return Screen { if (model.loading) CircularProgressIndicator(color = Brand.navy); ErrorLine(model.error) }
    val v = b.votes ?: return Screen { Text("No seat on record is tied to this account yet.", style = T.subhead, color = Brand.secondary) }
    val uri = LocalUriHandler.current
    Screen {
        val c = v.count
        TileGrid(listOf(
            { m -> ValueTile("%,d".format(c.yes), "Yes", m) },
            { m -> ValueTile("%,d".format(c.no), "No", m) },
            { m -> ValueTile("%,d".format(c.absent + c.abstain), "Absent or abstained", m) },
            { m -> ValueTile(v.presentRate?.let { "${it}%" } ?: "—", "Present", m) },
        ))
        Column {
            Eyebrow("Latest votes")
            Divided(minOf(v.recent.size, 60)) { i ->
                val x = v.recent[i]
                RowLink(x.sourceUrl?.let { u -> { uri.openUri(u) } }, {
                    Text(x.headline ?: "Motion", style = T.subhead, color = Brand.text, maxLines = 3, overflow = TextOverflow.Ellipsis)
                    Text(listOfNotNull(x.date?.let { Staff.whenOf(it) }, x.result.ifEmpty { null }, x.amount?.let { StaffBoard.money(it) }).joinToString(" · "),
                        style = T.caption, color = Brand.secondary)
                }) { Chip(x.voteLabel, when (x.vote) { "yes" -> Brand.good; "no" -> Brand.salmon; else -> Brand.secondary }) }
            }
        }
        Text("From the official minutes and hand-checked money votes. The full record and a PDF are on the web workspace.", style = T.footnote, color = Brand.secondary)
    }
}

@Composable
fun ValueTile(value: String, label: String, modifier: Modifier = Modifier) {
    Card(modifier, radius = 14.dp) {
        Column(Modifier.padding(14.dp)) {
            Text(value, style = T.number, color = Brand.text, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text(label, style = T.footnote, color = Brand.secondary, minLines = 2, maxLines = 2, overflow = TextOverflow.Ellipsis)
        }
    }
}


private fun shortDay(d: String) = runCatching { java.time.LocalDate.parse(d).format(DateTimeFormatter.ofPattern("MMM d", Locale.US)) }.getOrDefault(d)
private fun longDay(m: StaffBoard.Meeting): String = runCatching {
    OffsetDateTime.parse(m.start).atZoneSameInstant(ZoneId.of("America/Chicago")).format(DateTimeFormatter.ofPattern("EEEE, MMM d, h:mm a", Locale.US))
}.getOrElse { runCatching { java.time.LocalDate.parse(m.date).format(DateTimeFormatter.ofPattern("EEEE, MMM d", Locale.US)) }.getOrDefault(m.date) }
