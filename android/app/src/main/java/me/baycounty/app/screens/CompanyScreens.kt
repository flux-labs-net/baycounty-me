package me.baycounty.app.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import me.baycounty.app.Route
import me.baycounty.app.ui.*
import me.baycounty.kit.DatasetSpec
import me.baycounty.kit.Dates
import me.baycounty.kit.DonorContracts
import me.baycounty.kit.Format
import me.baycounty.kit.Governments
import me.baycounty.kit.MoneyMap
import me.baycounty.kit.Period
import me.baycounty.kit.RecordLinks
import me.baycounty.kit.VendorDirectory
import me.baycounty.kit.VoteSummary

/** Kinds of company records, in a fixed order and color, for the Companies list. */
object RecordKind {
    val order = listOf("contract", "change_order", "emergency", "cra", "tdc", "register")
    @Composable fun color(k: String): Color = when (k) {
        "contract" -> Brand.navy; "change_order" -> Brand.blue; "emergency" -> Brand.salmon
        "cra" -> Brand.good; "tdc" -> Brand.amber; else -> Brand.secondary.copy(alpha = 0.45f)
    }
    fun label(k: String) = mapOf("contract" to "Contracts", "change_order" to "Change orders", "emergency" to "Emergency", "register" to "Checks", "tdc" to "Tourism", "cra" to "CRA")[k] ?: k
    fun kind(k: String) = mapOf("contract" to "contracts", "change_order" to "change orders", "emergency" to "emergency purchases",
        "register" to "check register lines", "tdc" to "tourism payments", "cra" to "CRA records")[k] ?: k.replace("_", " ")
}

@Composable
private fun RecordKindBar(records: Map<String, Int>, scale: Double) {
    val total = records.values.sum().toDouble()
    val keys = RecordKind.order.filter { (records[it] ?: 0) > 0 } + records.keys.filter { it !in RecordKind.order }.sorted()
    Row(Modifier.fillMaxWidth().height(7.dp)) {
        Row(Modifier.fillMaxWidth(scale.coerceIn(0.04, 1.0).toFloat()).fillMaxHeight().clip(RoundedCornerShape(3.dp)), horizontalArrangement = Arrangement.spacedBy(1.5.dp)) {
            for (k in keys) Box(Modifier.weight(((records[k] ?: 0) / maxOf(total, 1.0)).toFloat().coerceAtLeast(0.01f)).fillMaxHeight().background(RecordKind.color(k)))
        }
    }
}

@Composable
private fun RecordKindLegend() {
    Flow(spacing = 10.dp) {
        for (k in RecordKind.order) Row(Modifier.clearAndSetSemantics {}, verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(5.dp)) {
            Box(Modifier.size(10.dp).background(RecordKind.color(k), RoundedCornerShape(2.dp)))
            Text(RecordKind.label(k), style = T.caption, color = Brand.secondary)
        }
    }
}

/** Every company paid by a Bay County government, CRA or tourism agency. */
@Composable
fun VendorsScreen() {
    val store = LocalStore.current
    val nav = LocalNav.current
    LaunchedEffect(Unit) { store.loadVendors() }
    var query by rememberSaveable { mutableStateOf("") }
    var gov by rememberSaveable { mutableStateOf<String?>(null) }
    val q = query.lowercase().trim()
    val list = (store.vendors?.vendors ?: emptyList())
        .filter { gov == null || gov in it.gov_ids }
        .filter { v -> q.isEmpty() || q in v.name.lowercase() || v.aliases.any { q in it.lowercase() } }
        .sortedWith(compareByDescending<VendorDirectory.Vendor> { it.recordCount }.thenBy { it.name })
    Screen("Companies", actions = { GovFilterAction(gov) { gov = it } }, spacing = 0) {
        item {
            PageHero("Accountability", "Companies",
                "Every company or organization paid by a Bay County government, CRA or tourism agency, with its contracts, payments, the votes that approved them and gifts from the business to campaigns. A gift near a vote does not show why anyone voted the way they did.",
                "building", Tone.BLUE)
        }
        if (store.vendors == null) { item { AppDataPending("vendors.json", "Couldn't load companies") { store.loadVendors() } }; return@Screen }
        item { Spacer(Modifier.height(16.dp)); FilterField(query, "Look up a company") { query = it } }
        item { Spacer(Modifier.height(14.dp)); RecordKindLegend() }
        item { Spacer(Modifier.height(18.dp)); EyebrowHeader("${Format.number(list.size.toDouble())} companies"); Spacer(Modifier.height(8.dp)) }
        val maxCount = list.firstOrNull()?.recordCount ?: 1
        cardItems(list.take(400), key = { it.id }) { v ->
            Column(
                Modifier.fillMaxWidth().clickable { nav.push(Route.Vendor(v.id)) }.padding(horizontal = 14.dp, vertical = 10.dp)
                    .clearAndSetSemantics { contentDescription = v.name + ": " + v.records.entries.sortedByDescending { it.value }.joinToString(", ") { "${it.value} ${RecordKind.kind(it.key)}" } },
                verticalArrangement = Arrangement.spacedBy(5.dp),
            ) {
                Row {
                    Text(v.name, style = T.subheadBold, color = Brand.text, maxLines = 2, modifier = Modifier.weight(1f))
                    Spacer(Modifier.width(6.dp))
                    Text("${v.recordCount}", style = T.subheadBold, color = Brand.text)
                }
                RecordKindBar(v.records, v.recordCount.toDouble() / maxOf(maxCount, 1))
            }
        }
    }
}

private val agency = mapOf("visit_pcb" to "Visit Panama City Beach", "destination_pc" to "Destination Panama City", "mb_cdc" to "Mexico Beach CDC",
    "sheriff" to "Sheriff", "airport" to "Airport", "port" to "Port Panama City")

/** One company: its contracts, payments, the votes that approved them and gifts from the business. */
@Composable
fun VendorScreen(vendorID: String) {
    val store = LocalStore.current
    val nav = LocalNav.current
    val o = rememberOpener()
    LaunchedEffect(vendorID) { store.loadVendors(); store.loadDonorContracts(); store.load(RecordLinks.vendorDatasets + "votes") }
    val v = store.vendor(vendorID)
    val subtitle = v?.let {
        val lines = mutableListOf<String>()
        val govs = it.gov_ids.mapNotNull { g -> Governments.names[g] ?: agency[g] }
        if (govs.isNotEmpty()) lines += govs.joinToString(" · ")
        if (it.aliases.isNotEmpty()) lines += "Also spelled: " + it.aliases.take(5).joinToString("; ")
        lines.joinToString("\n").ifEmpty { null }
    }
    val recs = RecordLinks.recordsForVendor(vendorID, store.rows)
    val votes = RecordLinks.votesForVendor(vendorID, store.rows)
    Screen(v?.name ?: "Company", spacing = 22) {
        item { PageHero("Company", v?.name ?: "Company", subtitle, "building", Tone.BLUE) }
        val deals = recs.filter { it.first in listOf("contracts", "change-orders", "emergency-purchases") }.flatMap { it.second }
        if (deals.isNotEmpty()) item {
            val contracts = recs.firstOrNull { it.first == "contracts" }?.second ?: emptyList()
            val spec = DatasetSpec.forId("contracts")
            val approved = contracts.mapNotNull { spec.amount(it) }.sum()
            val govs = deals.mapNotNull { it.string("government") }.toSet().size
            val byYear = sortedMapOf<Int, Double>()
            for (r in contracts) Period.of(r)?.year?.let { y -> byYear[y] = (byYear[y] ?: 0.0) + (spec.amount(r) ?: 0.0) }
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                StatStrip(listOf("Contracts" to "${contracts.size}", "Approved" to Format.compactMoney(approved), (if (govs == 1) "Government" else "Governments") to "$govs"))
                if (byYear.size >= 2) YearBars("Contracts approved each year", byYear.map { it.key.toString() to it.value })
                Text("Approved amounts, often not-to-exceed. Not proof of payment.", style = T.caption2, color = Brand.secondary)
            }
        }
        for ((ds, rows) in recs) item(key = ds) {
            val spec = DatasetSpec.forId(ds)
            val maxAmount = rows.mapNotNull { spec.amount(it) }.maxOrNull() ?: 0.0
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                EyebrowHeader(store.info(ds)?.title ?: Format.label(ds))
                CardList {
                    val shown = rows.take(25)
                    shown.forEachIndexed { i, r ->
                        CompactRecordRow(spec, r, maxAmount, spec.titleKeys.firstOrNull()) { nav.push(Route.Record(ds, r.id)) }
                        if (i < shown.lastIndex) RowDivider()
                    }
                    if (rows.size > 25) { RowDivider(); RouteRow(Route.Dataset(ds, mapOf("vendor_id" to vendorID)), "All ${rows.size}") }
                }
            }
        }
        if (votes.isNotEmpty()) item {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                EyebrowHeader("Votes that approved its contracts")
                CardList {
                    votes.forEachIndexed { i, r ->
                        Box(Modifier.clickable { nav.push(Route.Record("votes", r.id)) }.padding(horizontal = 14.dp, vertical = 10.dp)) { VoteRow(r, VoteSummary(r)) }
                        if (i < votes.lastIndex) RowDivider()
                    }
                }
                Text("Matched from the minutes. A gift near a vote does not show why anyone voted the way they did.", style = T.footnote, color = Brand.secondary)
            }
        }
        val matches = store.donorContracts?.matches?.filter { it.vendor_id == vendorID } ?: emptyList()
        if (matches.isNotEmpty()) item {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                EyebrowHeader("Gifts from the business to campaigns")
                CardList {
                    matches.forEachIndexed { i, m -> DonorMatchRow(m); if (i < matches.lastIndex) RowDivider() }
                }
            }
        }
        if (recs.isEmpty() && votes.isEmpty() && store.loading.isNotEmpty()) item { Loading() }
        item {
            val url = v?.pageURL
            if (url != null) LinkLine("Company page on BayCounty.me", "safari") { o.open(url) }
            else LinkLine("Profile and connections on BayCounty.me", "safari") { o.openSite("/profile/vendor/$vendorID") }
        }
    }
}

/** Businesses that gave to campaigns and also hold local government contracts. */
@Composable
fun DonorContractsScreen() {
    val store = LocalStore.current
    val nav = LocalNav.current
    LaunchedEffect(Unit) { store.loadDonorContracts() }
    var sameOnly by rememberSaveable { mutableStateOf(false) }
    data class Group(val id: String, val name: String, val vendorID: String?, val matches: List<DonorContracts.Match>, val total: Double)
    val all = store.donorContracts?.matches ?: emptyList()
    val list = if (sameOnly) all.filter { it.same_government_as_office == true } else all
    val groups = list.groupBy { it.vendor_id ?: it.contributor ?: "" }.map { (k, ms) ->
        Group(k, ms.first().vendor_name ?: ms.first().vendor ?: ms.first().contributor ?: k, ms.first().vendor_id, ms, ms.mapNotNull { it.contribution_amount }.sum())
    }.sortedByDescending { it.total }
    Screen("Donors with contracts", spacing = 20) {
        item {
            PageHero("Connections", "Donors with contracts",
                "Businesses that gave to a local campaign and also hold a contract, grant or payment from a Bay County government. Individual donors are never named. A gift near a vote does not show why anyone voted the way they did.",
                "link", Tone.SALMON)
        }
        if (store.donorContracts == null) { item { AppDataPending("donor-contracts.json", "Couldn't load donor matches") { store.loadDonorContracts() } }; return@Screen }
        item { ToggleRow("Only where the contract is with the same government", sameOnly) { sameOnly = it } }
        if (groups.isNotEmpty()) item {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                StatStrip(listOf("Gifts" to "${groups.sumOf { it.matches.size }}", "Given" to Format.compactMoney(groups.sumOf { it.total }), "Companies" to "${groups.size}"))
                CompareBars("Biggest givers", groups.take(6).map { BarItem(it.id, it.name, it.total) }, Format::compactMoney)
            }
        }
        for (g in groups) item(key = g.id) {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                val vid = g.vendorID
                Row(if (vid != null) Modifier.clickable { nav.push(Route.Vendor(vid)) } else Modifier, verticalAlignment = Alignment.CenterVertically) {
                    Text(g.name, style = T.headline, color = if (vid != null) Brand.navy else Brand.text, modifier = Modifier.weight(1f))
                    if (vid != null) Chevron()
                }
                CardList { g.matches.forEachIndexed { i, m -> DonorMatchRow(m); if (i < g.matches.lastIndex) RowDivider() } }
            }
        }
        store.donorContracts?.method?.let { m -> item { PageSection("Method") { Text(m, style = T.footnote, color = Brand.secondary) } } }
    }
}

private enum class MapMode(val label: String) { OFFICIALS("Officials"), DONORS("Donors"), HEAT("By government"), VOTES("Votes") }

/** Money Map: which businesses gave to which officials, and the votes on those donors' contracts. */
@Composable
fun MoneyMapScreen() {
    val store = LocalStore.current
    LaunchedEffect(Unit) { store.loadMoneyMap(); store.loadPeople() }
    var mode by rememberSaveable { mutableStateOf(MapMode.OFFICIALS) }
    var gov by rememberSaveable { mutableStateOf<String?>(null) }
    Screen("Money map", actions = { GovFilterAction(gov) { gov = it } }, spacing = 20) {
        item {
            PageHero("Connections", "Money map",
                "Gifts from businesses and organizations to the campaigns of current officials, and where those donors hold local government contracts. Individual donors are never named. A gift near a vote does not show why anyone voted the way they did.",
                "point.3.connected.trianglepath.dotted", Tone.AMBER)
        }
        item { ChipRow(MapMode.entries.map { it to it.label }, mode) { mode = it } }
        val mm = store.moneyMap
        if (mm == null) { item { AppDataPending("money-map.json", "Couldn't load the money map") { store.loadMoneyMap() } }; return@Screen }
        when (mode) {
            MapMode.OFFICIALS -> for (off in mm.officials.filter { gov == null || it.g == gov }) item(key = "o${off.id}") { OfficialGifts(mm, off) }
            MapMode.DONORS -> {
                val ds = mm.donors.filter { d -> gov == null || mm.giftsFromDonor(d.id).any { mm.official(it.o)?.g == gov } }.sortedByDescending { it.tot ?: 0.0 }
                item { EyebrowHeader("${ds.size} donors") }
                item { CardList { ds.take(150).forEachIndexed { i, d -> DonorDisclosure(mm, d); if (i < minOf(ds.size, 150) - 1) RowDivider() } } }
            }
            MapMode.HEAT -> item { Heat(mm) }
            MapMode.VOTES -> item {
                val vs = mm.vgroups.filter { gov == null || it.g == gov }.take(60)
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    EyebrowHeader("Votes on a donor's contract")
                    CardList {
                        vs.forEachIndexed { i, v ->
                            Column(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text(v.h ?: "Vote", style = T.subhead.copy(fontWeight = FontWeight.Medium), color = Brand.text)
                                Text(listOfNotNull(mm.donor(v.d)?.n, Dates.parse(v.date)?.let { Dates.display(it, false) }, v.tally, v.amount?.let(Format::compactMoney)).joinToString(" · "),
                                    style = T.caption, color = Brand.secondary)
                                for (m in v.roll.filter { it.gift != null }) {
                                    val w = m.giftWhen(v.date).let { if (it.isEmpty()) "" else " $it" }
                                    Text("${m.n} voted ${m.vote ?: "—"} · got ${Format.money(m.gift ?: 0.0)} from the donor$w", style = T.caption2, color = Brand.text)
                                }
                            }
                            if (i < vs.lastIndex) RowDivider()
                        }
                    }
                    Text("Each vote approved a contract with a business that gave to at least one member's campaign.", style = T.footnote, color = Brand.secondary)
                }
            }
        }
    }
}

@Composable
private fun OfficialGifts(mm: MoneyMap, off: MoneyMap.Official) {
    val store = LocalStore.current
    val nav = LocalNav.current
    val pid = store.people?.people?.firstOrNull { it.name.equals(off.n, ignoreCase = true) }?.id
    val gifts = mm.giftsToOfficial(off.id)
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Column(if (pid != null) Modifier.clickable { nav.push(Route.Person(pid)) } else Modifier) {
            Text(off.n, style = T.headline, color = if (pid != null) Brand.navy else Brand.text)
            Text(listOfNotNull(off.off, off.raised?.let { "raised ${Format.compactMoney(it)}" }).joinToString(" · "), style = T.caption, color = Brand.secondary)
        }
        CardList {
            val shown = gifts.take(8)
            shown.forEachIndexed { i, g ->
                mm.donor(g.d)?.let { d ->
                    Row(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        NameWithBadge(d.n, d.holdsContracts, Modifier.weight(1f))
                        Text(Format.money(g.a), style = T.subhead, color = Brand.text)
                    }
                }
                if (i < shown.lastIndex) RowDivider()
            }
            if (gifts.size > 8) { RowDivider(); Text("and ${gifts.size - 8} more", style = T.caption, color = Brand.secondary, modifier = Modifier.padding(14.dp)) }
            if (gifts.isEmpty()) Text("No business or organization gifts on file.", style = T.caption, color = Brand.secondary, modifier = Modifier.padding(14.dp))
        }
    }
}

@Composable
private fun DonorDisclosure(mm: MoneyMap, d: MoneyMap.Donor) {
    val nav = LocalNav.current
    var open by rememberSaveable(d.id) { mutableStateOf(false) }
    Column {
        Row(Modifier.fillMaxWidth().clickable { open = !open }.padding(horizontal = 14.dp, vertical = 11.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            NameWithBadge(d.n, d.holdsContracts, Modifier.weight(1f))
            Text(Format.compactMoney(d.tot ?: 0.0), style = T.subhead, color = Brand.text)
            androidx.compose.material3.Icon(icon(if (open) "chevron.up" else "chevron.down"), null, tint = Brand.tertiary, modifier = Modifier.size(18.dp))
        }
        if (open) Column(Modifier.padding(start = 24.dp, end = 14.dp, bottom = 10.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            for (g in mm.giftsFromDonor(d.id)) mm.official(g.o)?.let { off ->
                Row { Text(off.n, style = T.caption, color = Brand.text, modifier = Modifier.weight(1f)); Text(Format.money(g.a), style = T.caption, color = Brand.text) }
            }
            for (c in mm.contractsForDonor(d.id)) Text((Governments.names[c.g] ?: c.g) + ": " + (c.items ?: emptyList()).take(2).joinToString("; "), style = T.caption2, color = Brand.secondary)
            d.vp?.let { vp -> Text("Company page", style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = Brand.navy, modifier = Modifier.clickable { nav.push(Route.Vendor(vp)) }.padding(vertical = 4.dp)) }
        }
    }
}

/** Each top donor with a bar per government whose officials it gave to. Fits the screen width (no sideways scrolling). */
@Composable
private fun Heat(mm: MoneyMap) {
    val h = mm.heat(15)
    val maxCell = h.cells.values.flatMap { it.values }.maxOrNull() ?: 1.0
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        EyebrowHeader("Who gave to which government's officials, top 15 donors")
        CardList {
            h.donors.forEachIndexed { i, d ->
                val cells = h.govs.mapNotNull { g -> (h.cells[d.id]?.get(g) ?: 0.0).takeIf { it > 0 }?.let { g to it } }.sortedByDescending { it.second }
                Column(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Row {
                        Text(d.n, style = T.subheadBold, color = Brand.text, maxLines = 2, modifier = Modifier.weight(1f))
                        Text(Format.compactMoney(cells.sumOf { it.second }), style = T.subheadBold.copy(fontWeight = FontWeight.Bold), color = Brand.text)
                    }
                    for ((g, a) in cells) Row(
                        Modifier.clearAndSetSemantics { contentDescription = "${d.n} to ${Governments.names[g] ?: g}: ${Format.money(a)}" },
                        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Text(Governments.names[g]?.replace("Bay District ", "") ?: g, style = T.caption, color = Brand.text, maxLines = 1, modifier = Modifier.width(110.dp))
                        MagnitudeBar(a / maxCell, 8.dp, Modifier.weight(1f))
                        Text(Format.compactMoney(a), style = T.caption, color = Brand.text, textAlign = TextAlign.End, modifier = Modifier.width(56.dp))
                    }
                }
                if (i < h.donors.lastIndex) RowDivider()
            }
        }
    }
}

@Suppress("unused") private fun Modifier.unused() = this.semantics { }

@Composable
private fun NameWithBadge(name: String, holdsContracts: Boolean, modifier: Modifier) {
    Row(modifier, verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(name, style = T.subhead, color = Brand.text, modifier = Modifier.weight(1f, fill = false))
        if (holdsContracts) Badge("Holds contracts", Brand.salmon)
    }
}
