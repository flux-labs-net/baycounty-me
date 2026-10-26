package me.baycounty.app.screens

import android.content.Intent
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
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
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import me.baycounty.app.Route
import me.baycounty.app.ui.*
import me.baycounty.kit.CRALedger
import me.baycounty.kit.DatasetSpec
import me.baycounty.kit.EntityRef
import me.baycounty.kit.Format
import me.baycounty.kit.Period
import me.baycounty.kit.RecordLinks
import me.baycounty.kit.RecordProfile
import me.baycounty.kit.VoteSummary
import me.baycounty.kit.objectValue
import me.baycounty.kit.stringValue
import me.baycounty.kit.Row as DataRow
import java.net.URI
import kotlin.math.log10

/** What one record of a list is called, for the screen title. */
private val recordNoun = mapOf(
    "nonprofit-board-members" to "Board member", "nonprofits" to "Nonprofit", "nonprofit-board-businesses" to "Board member's business",
    "charity-registrations" to "Charity registration", "nonprofit-grants" to "Grant", "nonprofit-payments" to "Payment",
    "nonprofit-officials" to "Official on a board", "entity-profiles" to "Profile", "entity-connections" to "Connection",
    "contracts" to "Contract", "change-orders" to "Change order", "votes" to "Vote", "member-votes" to "Vote", "cra-payments" to "CRA record",
)

/** "Florida corporate filing (Sunbiz)" for a sunbiz.org link, and so on. */
fun sourceName(url: String): String {
    val host = runCatching { URI(url).host }.getOrNull() ?: ""
    return when {
        "sunbiz" in host -> "Florida corporate filing (Sunbiz)"
        "gt990datalake" in host || "irs.gov" in host -> "IRS return"
        "propublica" in host -> "IRS filings (ProPublica)"
        "fdacs" in host -> "Florida charity registration"
        else -> "Source record"
    }
}

/**
 * One record, laid out as a profile: who or what it is, its tags and headline numbers, the years it covers, the
 * people and organizations it names (each opening its own record or profile), related records and the source.
 */
@Composable
fun RecordScreen(datasetID: String, rowID: Int) {
    val store = LocalStore.current
    val context = LocalContext.current
    LaunchedEffect(datasetID) { store.load(datasetID) }
    val spec = DatasetSpec.forId(datasetID)
    val row = store.rows[datasetID]?.firstOrNull { it.id == rowID }
    val title = recordNoun[datasetID] ?: store.info(datasetID)?.title ?: "Record"
    if (row == null) {
        Screen(title) { item { if (store.rows[datasetID] == null) Loading() else Unavailable("Record not found", symbol = "doc") } }
        return
    }
    LaunchedEffect(datasetID, rowID) {
        store.loadVendors(); store.loadPeople()
        val ids = RecordProfile.groups(datasetID, row).map { it.datasetID }.toMutableSet() - datasetID
        val more = mutableSetOf<String>()
        if (RecordProfile.refs(datasetID, row).any { it.kind == "nonprofit" }) more += "nonprofits"
        if (RecordLinks.voteIDs(row).isNotEmpty() && datasetID != "votes") more += "votes"
        for (id in (ids + more).sorted()) store.load(id)
    }
    val source = DatasetSpec.sourceURL(row)
    Screen(
        title,
        actions = {
            if (source != null) ToolbarIcon("square.and.arrow.up", "Share") {
                val text = listOfNotNull(spec.title(row), spec.amount(row)?.let { Format.money(it) }).joinToString(" · ") + "\n" + source
                val send = Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_SUBJECT, spec.title(row)).putExtra(Intent.EXTRA_TEXT, text)
                context.startActivity(Intent.createChooser(send, null).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            }
        },
        spacing = 16,
    ) {
        item { Hero(datasetID, row, spec) }
        item { FactsGrid(datasetID, row) }
        RecordProfile.years(row)?.let { y -> item { YearsStrip(y) } }
        spec.detail(row)?.takeIf { spec.detailKey != "sources" }?.let { d ->
            item { Text(d, style = T.body, color = Brand.text, modifier = Modifier.fillMaxWidth().card(20.dp).padding(16.dp)) }
        }
        spec.amount(row)?.takeIf { datasetID != "votes" }?.let { a -> item { CompareCard(datasetID, row, a, spec) } }
        item { Connections(datasetID, row) }
        for (g in RecordProfile.groups(datasetID, row)) item { GroupCard(datasetID, g, row) }
        RecordProfile.subject(datasetID, row)?.let { me -> item { ProfileButton(me) } }
        if (row.number("lat") != null) item { RecordsMap(datasetID, listOf(row), Modifier.fillMaxWidth().height(180.dp).card(20.dp)) }
        item { SourceCard(datasetID, row, spec) }
        item { Text("From public records compiled by BayCounty.me. Check the original before relying on a single figure.", style = T.caption, color = Brand.secondary, modifier = Modifier.padding(horizontal = 4.dp)) }
    }
}

@Composable
private fun Hero(datasetID: String, row: DataRow, spec: DatasetSpec) {
    val org = if (datasetID == "nonprofits") null else RecordProfile.refs(datasetID, row).firstOrNull { it.kind == "nonprofit" }
    val chips = RecordProfile.chips(datasetID, row)
    Column(Modifier.fillMaxWidth().card(20.dp).padding(20.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
            val ini = RecordProfile.initials(datasetID, row)
            if (ini != null) Box(Modifier.size(56.dp).background(Brand.navyFill, CircleShape).clearAndSetSemantics {}, contentAlignment = Alignment.Center) {
                Text(ini, style = T.title3, color = Color.White)
            } else Box(Modifier.size(56.dp).background(Brand.navy.copy(alpha = 0.1f), RoundedCornerShape(16.dp)).clearAndSetSemantics {}, contentAlignment = Alignment.Center) {
                Icon(icon(spec.symbol), null, tint = Brand.navy, modifier = Modifier.size(28.dp))
            }
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(spec.title(row), style = T.title2, color = Brand.text)
                RecordProfile.roleLine(datasetID, row)?.let { Text(it, style = T.subhead, color = Brand.secondary) }
            }
        }
        if (org != null) OrgLink(org) {
            Row(Modifier.heightIn(min = 44.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Icon(icon("building.2"), null, tint = Brand.navy, modifier = Modifier.size(18.dp))
                Text("at ${org.name}", style = T.subhead.copy(fontWeight = FontWeight.Medium), color = Brand.navy)
            }
        }
        spec.amount(row)?.let { a ->
            Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(Format.money(a), style = T.bigNumber.copy(fontSize = 32.sp), color = Brand.text, maxLines = 1)
                spec.amountKey(row)?.let { Text(Format.label(it), style = T.caption, color = Brand.secondary) }
            }
        }
        StatusLine(datasetID, row, spec)
        if (chips.isNotEmpty()) Flow(spacing = 8.dp) { for (c in chips) TagChip(c) }
    }
}

@Composable
private fun StatusLine(datasetID: String, row: DataRow, spec: DatasetSpec) {
    val status = row.string("status")
    when {
        status != null && datasetID == "cra-payments" -> Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Badge(status, statusColor(status)); Text(CRALedger.explain(status), style = T.footnote, color = Brand.secondary)
            }
            if (row.bool("count") == false) Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Icon(icon("minus.circle"), null, tint = Brand.secondary, modifier = Modifier.size(14.dp))
                Text("Left out of totals so no dollar is counted twice.", style = T.footnote, color = Brand.secondary)
            }
        }
        datasetID == "votes" -> {
            val v = VoteSummary(row)
            if (v.hasTally) Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                VoteDots(v, 16.dp)
                Text(when (v.passed) { false -> "Failed ${v.tallyText}"; true -> "Passed ${v.tallyText}"; null -> v.tallyText }, style = T.subheadBold, color = Brand.text)
                if (v.split) Badge("Split", Brand.amber)
            }
        }
        else -> spec.badge(row)?.takeIf { b -> RecordProfile.chips(datasetID, row).none { it.text == b } }?.let { Badge(it, statusColor(it)) }
    }
}

@Composable
private fun TagChip(chip: RecordProfile.Chip) {
    val color = when (chip.tone) { RecordProfile.Tone.GOOD -> Brand.good; RecordProfile.Tone.ACCENT -> Brand.navy; RecordProfile.Tone.WARN -> Brand.amber; RecordProfile.Tone.NEUTRAL -> Brand.secondary }
    Row(
        Modifier.heightIn(min = 28.dp).background(if (chip.tone == RecordProfile.Tone.NEUTRAL) Brand.sunken else color.copy(alpha = 0.14f), CircleShape).padding(horizontal = 12.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        if (chip.tone == RecordProfile.Tone.GOOD) Box(Modifier.size(7.dp).background(color, CircleShape))
        Text(chip.text, style = T.footnote.copy(fontWeight = FontWeight.SemiBold), color = color, maxLines = 1)
    }
}

@Composable
private fun FactsGrid(datasetID: String, row: DataRow) {
    val facts = RecordProfile.facts(datasetID, row)
    if (facts.isEmpty()) return
    val perRow = if (facts.size == 4) 2 else facts.size.coerceAtMost(3)
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        for (line in facts.chunked(perRow)) Row(Modifier.fillMaxWidth().height(androidx.compose.foundation.layout.IntrinsicSize.Min), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            for (f in line) Column(Modifier.weight(1f).fillMaxHeight().heightIn(min = 64.dp).card(16.dp).padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(f.value, style = T.title2, color = Brand.text, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(f.label, style = T.caption, color = Brand.secondary)
            }
            repeat(perRow - line.size) { androidx.compose.foundation.layout.Spacer(Modifier.weight(1f)) }
        }
    }
}


/** The years a record covers, as a strip of year cells (filled for the years on file). */
@Composable
private fun YearsStrip(years: IntRange) {
    val lo = minOf(years.first, years.last - 7)
    // Never a cell before 2016, the site's first year.
    val cells = (maxOf(lo, years.last - 11, me.baycounty.kit.Cutoff.FIRST_YEAR)..years.last).toList()
    Column(
        Modifier.fillMaxWidth().card(20.dp).padding(16.dp).clearAndSetSemantics {
            contentDescription = if (years.first == years.last) "On file in ${years.first}" else "On file from ${years.first} to ${years.last}"
        },
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Row {
            Text("Years on file", style = T.subheadBold, color = Brand.text, modifier = Modifier.weight(1f))
            Text(if (years.first == years.last) "${years.first}" else "${years.first}–${years.last}", style = T.footnote, color = Brand.secondary)
        }
        Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            for (y in cells) {
                val on = y in years
                Column(Modifier.weight(1f), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Box(Modifier.fillMaxWidth().height(10.dp).background(if (on) Brand.navyFill else Brand.sunken, CircleShape))
                    Text("’" + (y % 100).toString().padStart(2, '0'), style = T.caption2, color = if (on) Brand.text else Brand.tertiary)
                }
            }
        }
    }
}

/** Where this amount sits among the same list's records from the same year: a dot on a line from smallest to largest. */
@Composable
private fun CompareCard(datasetID: String, row: DataRow, amount: Double, spec: DatasetSpec) {
    val store = LocalStore.current
    val all = store.rows[datasetID] ?: emptyList()
    val idx = Period.Index(all)
    val period = idx.period(row)
    val peers = all.filter { period == null || idx.period(it) == period }.mapNotNull { spec.amount(it) }.sorted()
    if (peers.size < 5) return
    val lo = peers.first(); val hi = peers.last()
    if (hi <= lo) return
    val rank = peers.count { it < amount }
    val pct = Math.round(rank.toDouble() / peers.size * 100).toInt()
    val median = peers[peers.size / 2]
    val sunken = Brand.sunken; val dot = Brand.blue.copy(alpha = 0.25f); val tick = Brand.secondary; val navy = Brand.navy
    Column(Modifier.fillMaxWidth().card(20.dp).padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        EyebrowHeader("How it compares")
        Text(if (pct >= 50) "Larger than $pct% of ${period?.label ?: "all"} records in this list" else "Smaller than ${100 - pct}% of ${period?.label ?: "all"} records in this list",
            style = T.subheadBold, color = Brand.text)
        Canvas(Modifier.fillMaxWidth().height(18.dp).clearAndSetSemantics {}) {
            val span = maxOf(log10(maxOf(hi, 1.0) / maxOf(lo, 1.0)), 0.0001)
            fun x(v: Double) = (size.width * (log10(maxOf(v, 1.0) / maxOf(lo, 1.0)) / span)).toFloat().coerceIn(0f, size.width)
            val cy = size.height / 2
            drawRoundRect(sunken, Offset(0f, cy - 3.dp.toPx()), androidx.compose.ui.geometry.Size(size.width, 6.dp.toPx()), androidx.compose.ui.geometry.CornerRadius(3.dp.toPx()))
            for (v in peers) drawCircle(dot, 3.dp.toPx(), Offset(x(v), cy))
            drawRect(tick, Offset(x(median), 1f), androidx.compose.ui.geometry.Size(1.5.dp.toPx(), size.height - 2f))
            drawCircle(navy, 8.dp.toPx(), Offset(x(amount), cy))
        }
        Row {
            Text("Smallest ${Format.compactMoney(lo)}", style = T.caption2, color = Brand.secondary, modifier = Modifier.weight(1f))
            Text("Middle ${Format.compactMoney(median)}", style = T.caption2, color = Brand.secondary)
            Text("Largest ${Format.compactMoney(hi)}", style = T.caption2, color = Brand.secondary, modifier = Modifier.weight(1f), textAlign = androidx.compose.ui.text.style.TextAlign.End)
        }
    }
}

/** A row on a card that leads somewhere: an icon tile (or initials), a name, a detail line and a chevron. */
@Composable
private fun LinkCardLabel(title: String, detail: String? = null, symbol: String? = null, initials: String? = null, tint: Color = Brand.navy, compact: Boolean = false, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().clickable(onClick = onClick).heightIn(min = 56.dp).padding(horizontal = 14.dp, vertical = if (compact) 8.dp else 12.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        if (initials != null) Box(Modifier.size(36.dp).background(tint.copy(alpha = 0.12f), CircleShape).clearAndSetSemantics {}, contentAlignment = Alignment.Center) {
            Text(initials, style = T.footnote.copy(fontWeight = FontWeight.SemiBold), color = tint)
        } else if (symbol != null) {
            val s = if (compact) 36.dp else 44.dp
            Box(Modifier.size(s).background(tint.copy(alpha = 0.12f), RoundedCornerShape(if (compact) 10.dp else 12.dp)).clearAndSetSemantics {}, contentAlignment = Alignment.Center) {
                Icon(icon(symbol), null, tint = tint, modifier = Modifier.size(if (compact) 20.dp else 24.dp))
            }
        }
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(title, style = T.subheadBold, color = Brand.text)
            if (!detail.isNullOrEmpty()) Text(detail, style = T.caption, color = Brand.secondary, maxLines = 3, overflow = TextOverflow.Ellipsis)
        }
        Chevron()
    }
}

private fun nonprofitRow(store: me.baycounty.app.AppStore, id: String) = store.rows["nonprofits"]?.firstOrNull { it.string("nonprofit_id") == id }

/** A nonprofit opens its own record in the app when the nonprofits list has it, else its web profile. */
@Composable
private fun OrgLink(r: EntityRef, label: @Composable () -> Unit) {
    val store = LocalStore.current
    val nav = LocalNav.current
    val o = rememberOpener()
    val np = nonprofitRow(store, r.key)
    Box(Modifier.clickable { if (np != null) nav.push(Route.Record("nonprofits", np.id)) else o.open(r.profileURL) }) { label() }
}

/** "Nonprofit · Panama City · Active since 2001 · 4 board members" */
private fun nonprofitMeta(store: me.baycounty.app.AppStore, id: String): String? {
    val n = nonprofitRow(store, id) ?: return null
    val parts = mutableListOf(n.string("kind") ?: "Nonprofit")
    n.string("city")?.let { parts += it }
    if (n.string("sunbiz_status") == "Active") n.string("sunbiz_filed")?.let { parts += "Active since ${it.take(4)}" }
    n.number("board_members_listed")?.takeIf { it > 0 }?.let { parts += "${it.toInt()} board member" + if (it == 1.0) "" else "s" }
    return parts.joinToString(" · ")
}

/** The organization, companies, officials, votes and government the record names, each as a tappable row. */
@Composable
private fun Connections(datasetID: String, row: DataRow) {
    val store = LocalStore.current
    val nav = LocalNav.current
    val o = rememberOpener()
    val me = if (datasetID == "entity-connections") null else RecordProfile.subject(datasetID, row)
    val refs = RecordProfile.refs(datasetID, row).filter { it.kind != "member" && it != me }
    val vendors = RecordLinks.vendorIDs(row)
    val people = if (datasetID in RecordLinks.personDatasets && datasetID != "votes") RecordLinks.personIDs(row) else emptyList()
    val voteIDs = RecordLinks.voteIDs(row).toSet()
    val votes = if (datasetID == "votes") emptyList() else (store.rows["votes"] ?: emptyList()).filter { v -> v.string("vote_id")?.let { it in voteIDs } ?: false }
    val gov = row.string("gov_id")?.let { store.government(it) }
    Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
        if (refs.isNotEmpty() || vendors.isNotEmpty() || people.isNotEmpty() || votes.isNotEmpty() || gov != null) {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                EyebrowHeader(if (refs.any { it.kind == "nonprofit" } && refs.size == 1) "Organization" else "Connected to")
                val items = mutableListOf<@Composable () -> Unit>()
                for (r in refs) items += {
                    val tint = if (r.kind == "nonprofit") Brand.good else Brand.navy
                    val detail = if (r.kind == "nonprofit") nonprofitMeta(store, r.key) ?: r.label else r.label
                    LinkCardLabel(r.name, detail, r.symbol, tint = tint) {
                        when {
                            r.kind == "nonprofit" -> nonprofitRow(store, r.key)?.let { nav.push(Route.Record("nonprofits", it.id)) } ?: o.open(r.profileURL)
                            r.kind == "person" && store.person(r.key) != null -> nav.push(Route.Person(r.key))
                            r.kind == "vendor" && store.vendor(r.key) != null -> nav.push(Route.Vendor(r.key))
                            r.kind == "gov" && store.government(r.key) != null -> nav.push(Route.Gov(r.key))
                            else -> o.open(r.profileURL)
                        }
                    }
                }
                for (id in vendors) items += { LinkCardLabel(store.vendor(id)?.name ?: "Company", "Company", "building.2") { nav.push(Route.Vendor(id)) } }
                for (id in people) store.person(id)?.let { p -> items += { LinkCardLabel(p.name, p.headline, "person") { nav.push(Route.Person(id)) } } }
                for (v in votes) items += { LinkCardLabel(v.string("headline") ?: "Vote", "Recorded vote", "hand.raised", tint = Brand.amber) { nav.push(Route.Record("votes", v.id)) } }
                if (gov != null) items += { LinkCardLabel(gov.name, "Government", "building.columns") { nav.push(Route.Gov(gov.govID)) } }
                Column(Modifier.fillMaxWidth().card(20.dp)) {
                    items.forEachIndexed { i, it -> if (i > 0) RowDivider(70.dp); it() }
                }
            }
        }
        val roll = if (datasetID == "votes") (row["members"]?.let { it as? kotlinx.serialization.json.JsonArray } ?: emptyList()).mapNotNull { m ->
            val obj = m.objectValue ?: return@mapNotNull null
            val n = obj["name"]?.stringValue ?: return@mapNotNull null
            Triple(n, obj["person_id"]?.stringValue, obj["vote"]?.stringValue)
        } else emptyList()
        if (roll.isNotEmpty()) Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            EyebrowHeader("How each member voted")
            CardList {
                roll.forEachIndexed { i, (name, pid, vote) ->
                    if (i > 0) RowDivider()
                    Row(
                        (if (pid != null) Modifier.clickable { nav.push(Route.Person(pid)) } else Modifier).fillMaxWidth().heightIn(min = 48.dp).padding(horizontal = 16.dp),
                        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Text(name, style = T.body, color = Brand.text, modifier = Modifier.weight(1f))
                        VoteMark(voteChoice(vote))
                        if (pid != null) Chevron()
                    }
                }
            }
        }
    }
}

@Composable
private fun GroupCard(datasetID: String, g: RecordProfile.Group, row: DataRow) {
    val store = LocalStore.current
    val nav = LocalNav.current
    val rows = RecordProfile.members(g, store.rows[g.datasetID] ?: emptyList(), row.id, g.datasetID == datasetID)
    if (rows.isEmpty()) return
    val people = g.datasetID == "nonprofit-board-members" && g.column != "person_id"
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.weight(1f)) { EyebrowHeader(g.title) }
            Text("${rows.size}", style = T.footnote.copy(fontWeight = FontWeight.SemiBold), color = Brand.secondary)
        }
        CardList {
            rows.take(6).forEachIndexed { i, r ->
                if (i > 0) RowDivider(64.dp)
                val t = RecordProfile.groupRowTitle(g, r)
                val d = RecordProfile.groupRowDetail(g, r)
                val open = { nav.push(Route.Record(g.datasetID, r.id)) }
                if (people) LinkCardLabel(t, d, initials = initialsOf(t), compact = true, onClick = open)
                else LinkCardLabel(t, d, if (g.datasetID == "nonprofit-board-members") "heart" else DatasetSpec.forId(g.datasetID).symbol, tint = Brand.good, compact = true, onClick = open)
            }
            if (rows.size > 6) { RowDivider(); RouteRow(Route.Dataset(g.datasetID, mapOf(g.column to g.value)), "See all ${rows.size}") }
        }
    }
}

private fun initialsOf(name: String): String {
    val w = name.split(" ").filter { it.firstOrNull()?.isLetter() == true }
    return ((w.firstOrNull()?.take(1) ?: "") + (if (w.size > 1) w.last().take(1) else "")).uppercase()
}

@Composable
private fun ProfileButton(me: EntityRef) {
    val o = rememberOpener()
    Row(
        Modifier.fillMaxWidth().heightIn(min = 64.dp).background(Brand.navyFill, RoundedCornerShape(20.dp)).clickable { o.open(me.profileURL) }.padding(horizontal = 18.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Icon(icon("point.3.connected.trianglepath.dotted"), null, tint = Color.White)
        Column(Modifier.weight(1f)) {
            Text("${me.name}: profile and connections", style = T.subheadBold, color = Color.White)
            Text("People, money and links on one map", style = T.caption, color = Color.White.copy(alpha = 0.85f))
        }
        Icon(icon("chevron.right"), null, tint = Color.White, modifier = Modifier.size(18.dp))
    }
}

@Composable
private fun SourceCard(datasetID: String, row: DataRow, spec: DatasetSpec) {
    val store = LocalStore.current
    val fields = RecordProfile.otherFields(datasetID, row, store.info(datasetID)?.columns ?: emptyList())
    var open by rememberSaveable { mutableStateOf(false) }
    CardList {
        DatasetSpec.sourceURL(row)?.let { url ->
            WebRow(row.string("source_title") ?: sourceName(url), url, symbol = "doc.text.magnifyingglass")
            RowDivider(50.dp)
        }
        WebRow("Send a correction", "https://baycounty.me/about?page=${spec.page?.let { "/$it" } ?: "/"}#contact", symbol = "exclamationmark.bubble")
        if (fields.isNotEmpty()) {
            RowDivider(50.dp)
            Row(Modifier.fillMaxWidth().clickable { open = !open }.heightIn(min = 50.dp).padding(horizontal = 14.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Icon(icon("list.bullet.rectangle"), null, tint = Brand.navy, modifier = Modifier.size(22.dp))
                Text("All fields", style = T.body, color = Brand.text, modifier = Modifier.weight(1f))
                Text("${fields.size}", style = T.footnote, color = Brand.secondary)
                Icon(icon(if (open) "chevron.up" else "chevron.down"), null, tint = Brand.tertiary, modifier = Modifier.size(18.dp))
            }
            if (open) SelectionContainer {
                Column(Modifier.padding(start = 14.dp, end = 14.dp, bottom = 14.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    for ((label, value) in fields) Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                        Text(label, style = T.caption, color = Brand.secondary)
                        Text(value, style = T.subhead, color = Brand.text)
                    }
                }
            }
        }
    }
}
