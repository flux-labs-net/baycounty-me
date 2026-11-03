package me.baycounty.app.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import me.baycounty.app.Route
import me.baycounty.app.ui.*
import me.baycounty.kit.BayCountyClient
import me.baycounty.kit.RecordShare
import me.baycounty.kit.Dates
import me.baycounty.kit.Format
import me.baycounty.kit.Governments
import me.baycounty.kit.Officeholders
import me.baycounty.kit.PeopleDirectory
import me.baycounty.kit.PeopleEra
import me.baycounty.kit.PeopleKind
import me.baycounty.kit.Period
import me.baycounty.kit.RecordLinks
import me.baycounty.kit.Row as DataRow

/** Officials, department leaders and candidates since 2016, grouped by government and in title then last-name order like the site, with the site's filter chips. */
@Composable
fun PeopleScreen() {
    val store = LocalStore.current
    val nav = LocalNav.current
    LaunchedEffect(Unit) { store.loadPeople() }
    var query by rememberSaveable { mutableStateOf("") }
    var kind by rememberSaveable { mutableStateOf(PeopleKind.EVERYONE) }
    var era by rememberSaveable { mutableStateOf(PeopleEra.ALL) }
    val all = store.people?.people ?: emptyList()
    val q = query.lowercase()
    val people = all.filter { kind.includes(it) && era.includes(it) && (q.isEmpty() || q in it.name.lowercase()) }
    val counts = PeopleKind.entries.associateWith { k -> all.count { k.includes(it) } }
    val eraCounts = PeopleEra.entries.associateWith { e -> all.count { e.includes(it) } }
    Screen("People", spacing = 20) {
        item {
            PageHero("Connections · People", "Officials and candidates",
                "Every elected official, department leader and local candidate since 2016 in these records. Rank-and-file employees appear only by job title, never by name.",
                "person.3", Tone.TEAL)
        }
        if (store.people == null) { item { AppDataPending("people.json", "Couldn't load people") { store.loadPeople() } }; return@Screen }
        item { FilterField(query, "Find a person") { query = it } }
        item { ChipRow(PeopleKind.entries.map { it to it.label }, kind, counts) { kind = it } }
        item { ChipRow(PeopleEra.entries.map { it to it.label }, era, eraCounts) { era = it } }
        for ((title, list) in PeopleDirectory.grouped(people)) {
            item(key = title) {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Row(verticalAlignment = Alignment.Bottom) {
                        Text(title, style = T.headline, color = Brand.text, modifier = Modifier.weight(1f))
                        Text("${list.size}", style = T.subhead, color = Brand.secondary)
                    }
                    // Current, then Past; each already in the site's order (title, then last name)
                    for ((label, sorted) in listOf("CURRENT" to list.filter { !it.isPast }, "PAST" to list.filter { it.isPast })) {
                        if (sorted.isEmpty()) continue
                        Text(label, style = T.caption, color = Brand.secondary)
                        CardList {
                            sorted.forEachIndexed { i, p ->
                                PersonRow(p) { nav.push(Route.Person(p.id)) }
                                if (i < sorted.lastIndex) RowDivider(64.dp)
                            }
                        }
                    }
                }
            }
        }
        if (all.isNotEmpty() && people.isEmpty()) item { Text("No one matches.", style = T.subhead, color = Brand.secondary) }
    }
}

private data class Campaign(
    val id: String, val year: Int, val title: String, val detail: String, val outcome: String?,
    val raised: Double?, val spent: Double?, val report: String?,
)

/** Every campaign: the 2026 race and latest winning race, then every race since 2016 not already listed. */
private fun campaignList(byDS: Map<String, List<DataRow>>): List<Campaign> {
    val out = mutableListOf<Campaign>()
    for (r in (byDS["candidates-2026"] ?: emptyList()) + (byDS["campaign-finance"] ?: emptyList())) {
        val election = r.first(listOf("election")) ?: "2026"
        val year = election.take(4).toIntOrNull() ?: 2026
        out += Campaign("c${r.id}-$election", year, r.first(listOf("office", "race")) ?: election, election,
            if (year >= 2026) "On the ballot" else null, r.number("total_raised"), r.number("total_spent"), r.url("report_url") ?: r.url("finance_report_url"))
    }
    val have = out.map { it.year }.toSet()
    for (r in byDS["campaign-history"] ?: emptyList()) {
        val year = r.number("election_year")?.toInt() ?: 0
        if (year in have) continue
        out += Campaign("h${r.id}", year, r.string("office") ?: "Campaign", r.string("election") ?: "$year",
            r.string("outcome"), r.number("total_raised"), r.number("total_spent"), r.url("source_url"))
    }
    return out.sortedByDescending { it.year }
}

/**
 * One official, leader or candidate: where they serve, the terms they held, pay, every campaign since 2016
 * with its money, gifts from businesses and business owners, and their recorded votes.
 */
@Composable
fun PersonScreen(personID: String) {
    val store = LocalStore.current
    val nav = LocalNav.current
    val o = rememberOpener()
    LaunchedEffect(personID) { store.loadPeople(); store.loadDonorContracts(); store.load(RecordLinks.personDatasets) }
    val p = store.person(personID)
    val byDS = RecordLinks.recordsForPerson(personID, store.rows).toMap()
    var allGifts by rememberSaveable(personID) { mutableStateOf(false) }
    Screen(p?.name ?: "Person", actions = {
        ShareMenuButton(p?.name ?: "Person", "${BayCountyClient.SITE}/people/$personID") {
            RecordShare.page(p?.name ?: "Person", listOf(p?.headline), "/people/$personID")
        }
    }) {
        item { PageHero(p?.label ?: "People", p?.name ?: "Person", p?.headline, badge = { PersonInitials(p?.name ?: "?", 52.dp, p?.photoUrl) }) }
        val main = p?.mainRoles ?: emptyList()
        if (main.size > 1) item {
            PageSection("Where they serve", "building.columns", Tone.BLUE) {
                CardList {
                    main.forEachIndexed { i, r ->
                        TextRow(r.role?.replaceFirstChar { it.uppercase() } ?: "Role",
                            listOfNotNull(r.gov_id?.let { Governments.names[it] }, r.seat?.let { "Seat $it" }).joinToString(" · "))
                        if (i < main.lastIndex) RowDivider()
                    }
                }
            }
        }
        val terms = Officeholders.terms(byDS["officeholder-terms"] ?: emptyList(), personID)
        if (terms.isNotEmpty()) item {
            PageSection("Terms in office", "person.badge.clock", Tone.TEAL, "Each seat they held since 2016, newest first.") {
                CardList {
                    terms.forEachIndexed { i, t ->
                        Row(Modifier.padding(start = 14.dp), verticalAlignment = Alignment.CenterVertically) {
                            GovBadge(t.govID)
                            TextRow(t.seat + if (t.appointed) " (appointed)" else "",
                                listOfNotNull(t.government, t.years, t.how?.let(Format::label)).filter { it.isNotEmpty() }.joinToString(" · "))
                        }
                        if (i < terms.lastIndex) RowDivider(66.dp)
                    }
                }
            }
        }
        val payRows = (byDS["officials-pay"] ?: emptyList()) + (byDS["salary-leaders"] ?: emptyList())
        if (payRows.isNotEmpty()) item {
            PageSection("Pay", "dollarsign.circle", Tone.AMBER) {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    val byLabel = HashMap<String, Double>()
                    for (r in byDS["officials-pay"] ?: emptyList()) {
                        val v = r.firstNumber(listOf("annual", "salary")) ?: continue
                        val per = Period.of(r)?.takeIf { it.fiscal } ?: continue
                        byLabel[per.label] = maxOf(byLabel[per.label] ?: 0.0, v)
                    }
                    if (byLabel.size >= 2) YearBars("Pay by year", byLabel.keys.sorted().map { it to byLabel.getValue(it) })
                    CardList {
                        payRows.forEachIndexed { i, r ->
                            FactRow(r.first(listOf("title", "employer")) ?: "Pay", Format.money(r.firstNumber(listOf("annual", "salary"))), r.first(listOf("year", "as_of")))
                            if (i < payRows.lastIndex) RowDivider()
                        }
                    }
                }
            }
        }
        val campaigns = campaignList(byDS)
        if (campaigns.isNotEmpty()) item {
            PageSection("Campaigns", "flag", Tone.SALMON, "Every local race since 2016, with what the campaign raised and spent.") {
                CardList {
                    campaigns.forEachIndexed { i, c ->
                        Column(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 11.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                Text(c.title, style = T.subheadBold, color = Brand.text, modifier = Modifier.weight(1f))
                                c.outcome?.let { Badge(Format.label(it), when (it) { "won" -> Brand.good; "lost" -> Brand.salmon; else -> Brand.amber }) }
                            }
                            Text(c.detail, style = T.caption, color = Brand.secondary)
                            c.raised?.let { r ->
                                val spent = c.spent ?: 0.0
                                val maxV = maxOf(r, spent, 1.0)
                                MoneyBar("Raised", r, r / maxV)
                                if (c.spent != null) MoneyBar("Spent", spent, spent / maxV)
                            }
                            c.report?.let { u -> Text("Campaign finance reports", style = T.caption.copy(fontWeight = androidx.compose.ui.text.font.FontWeight.SemiBold), color = Brand.navy, modifier = Modifier.clickable { o.open(u) }.padding(vertical = 4.dp)) }
                        }
                        if (i < campaigns.lastIndex) RowDivider()
                    }
                }
            }
        }
        val giftRows = byDS["business-donor-sunbiz"] ?: emptyList()
        if (giftRows.isNotEmpty()) item {
            data class Giver(val name: String, var amount: Double = 0.0, var gifts: Int = 0, var vendor: String? = null)
            val sums = LinkedHashMap<String, Giver>()
            for (r in giftRows) {
                val k = r.string("contributor") ?: "Unknown"
                val g = sums.getOrPut(k) { Giver(k) }
                g.amount += r.number("contribution_amount") ?: 0.0
                g.gifts += (r.number("contribution_items") ?: 1.0).toInt()
                if (g.vendor == null) g.vendor = r.string("vendor_id")
            }
            val givers = sums.values.sortedByDescending { it.amount }
            val shown = if (allGifts) givers else givers.take(10)
            PageSection("Campaign gifts from businesses and groups", "envelope", Tone.AMBER,
                "${givers.size} businesses and groups gave ${Format.compactMoney(givers.sumOf { it.amount })} across their campaigns. Gifts from private individuals are never named.") {
                CardList {
                    shown.forEachIndexed { i, g ->
                        val n = "${g.gifts} gift${if (g.gifts == 1) "" else "s"}"
                        val v = g.vendor
                        if (v != null) RecordLinkRow(Route.Vendor(v), g.name, "$n · holds local contracts", Format.compactMoney(g.amount))
                        else TextRow(g.name, n, Format.compactMoney(g.amount))
                        if (i < shown.lastIndex) RowDivider()
                    }
                    if (givers.size > 10) { RowDivider(); ShowMoreRow(allGifts, "All ${givers.size} givers") { allGifts = !allGifts } }
                }
            }
        }
        val owners = (byDS["owner-gifts"] ?: emptyList()).sortedByDescending { it.number("amount") ?: 0.0 }
        if (owners.isNotEmpty()) item {
            PageSection("Business owners who gave", "person.text.rectangle", Tone.BLUE,
                "Donors whose name and street address match an officer, manager or registered agent of a Florida business.") {
                CardList {
                    val top = owners.take(15)
                    top.forEachIndexed { i, r ->
                        TextRow(r.string("donor") ?: "", listOfNotNull(r.string("businesses"), r.string("election")).joinToString(" · "), shortMoney(r.number("amount")))
                        if (i < top.lastIndex) RowDivider()
                    }
                    if (owners.size > 15) { RowDivider(); RouteRow(Route.Dataset("owner-gifts", mapOf("candidate_id" to personID)), "All ${owners.size}") }
                }
            }
        }
        // The dollars in the contract votes they cast (site/vote_dollars.py): yes on items that passed, no, and the votes behind them.
        val cd = RecordLinks.contractDollars(byDS["contract-dollar-totals"] ?: emptyList())
        if (cd != null) item {
            val rows = byDS["member-contract-dollars"] ?: emptyList()
            val latest = rows.sortedByDescending { it.string("date") ?: "" }.take(10)
            val span = listOfNotNull(cd.first, cd.last).mapNotNull { d -> Dates.parse(d)?.let { Dates.display(it, false) } }.joinToString(" to ")
            fun votes(n: Int) = "$n vote${if (n == 1) "" else "s"}"
            PageSection("Contract dollars they voted on", "dollarsign.square", Tone.TEAL, caption = "Contract and purchase votes with one clear dollar figure in the minutes, since 2016.") {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Column(Modifier.fillMaxWidth().card(14.dp).padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text("Voted yes, and it passed", style = T.caption, color = Brand.secondary)
                        Text(Format.money(cd.yes), style = T.bigNumber, color = Brand.text)
                        Text(votes(cd.yesVotes) + if (span.isEmpty()) "" else " · $span", style = T.caption, color = Brand.secondary)
                        Text("Voted no: ${Format.money(cd.no)} (${votes(cd.noVotes)})", style = T.subhead, color = Brand.text, modifier = Modifier.padding(top = 6.dp))
                        if (cd.yesFailedVotes > 0) Text("Voted yes, but it failed: ${Format.money(cd.yesFailed)} (${votes(cd.yesFailedVotes)})", style = T.subhead, color = Brand.text)
                        Text("Not totaled: ${cd.consent} consent agendas (many items in one vote) and ${cd.notCounted} votes without one clear dollar figure or that aren\u2019t new spending. So this is a floor.",
                            style = T.caption, color = Brand.secondary, modifier = Modifier.padding(top = 6.dp))
                    }
                    if (latest.isNotEmpty()) CardList {
                        latest.forEachIndexed { i, r ->
                            Row(Modifier.fillMaxWidth().clickable { nav.push(Route.Record("member-contract-dollars", r.id)) }.padding(horizontal = 14.dp, vertical = 10.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                    Text(r.string("headline") ?: "Vote", style = T.subhead, color = Brand.text, maxLines = 2)
                                    Text(listOfNotNull(r.string("date")?.let { Dates.parse(it) }?.let { Dates.display(it, false) }, Format.money(r.number("amount"))).joinToString(" · "),
                                        style = T.caption, color = Brand.secondary)
                                }
                                VoteMark(voteChoice(r.string("vote")))
                            }
                            if (i < latest.lastIndex) RowDivider()
                        }
                        if (rows.size > latest.size) { RowDivider(); RouteRow(Route.Dataset("member-contract-dollars", mapOf("person_id" to personID)), "All ${rows.size} votes behind these totals") }
                    }
                }
            }
        }
        val mv = byDS["member-votes"] ?: emptyList()
        if (mv.isNotEmpty()) item {
            val t = RecordLinks.tally(mv)
            val latest = mv.sortedByDescending { it.string("date") ?: "" }.take(25)
            PageSection("Recorded votes on money decisions", "hand.raised", Tone.TEAL) {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Column(Modifier.fillMaxWidth().card(14.dp).padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("${t.total} recorded votes", style = T.subheadBold, color = Brand.text)
                        ShareBar(listOf(Triple("Yes", t.yes.toDouble(), Brand.good), Triple("No", t.no.toDouble(), Brand.salmon), Triple("Absent", t.other.toDouble(), Brand.secondary.copy(alpha = 0.35f))))
                    }
                    CardList {
                        latest.forEachIndexed { i, r ->
                            Row(Modifier.fillMaxWidth().clickable { nav.push(Route.Record("member-votes", r.id)) }.padding(horizontal = 14.dp, vertical = 10.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                    Text(r.string("headline") ?: "Vote", style = T.subhead, color = Brand.text, maxLines = 2)
                                    Text(r.string("date")?.let { Dates.parse(it) }?.let { Dates.display(it, false) } ?: "", style = T.caption, color = Brand.secondary)
                                }
                                VoteMark(voteChoice(r.string("vote")))
                            }
                            if (i < latest.lastIndex) RowDivider()
                        }
                        if (mv.size > latest.size) { RowDivider(); RouteRow(Route.Dataset("member-votes", mapOf("person_id" to personID)), "All ${mv.size} votes") }
                    }
                }
            }
        }
        val gifts = store.donorContracts?.matches?.filter { it.person_id == personID } ?: emptyList()
        if (gifts.isNotEmpty()) item {
            PageSection("Business donors that hold local contracts", "link", Tone.SALMON, "A gift near a vote does not show why anyone voted the way they did.") {
                CardList {
                    gifts.forEachIndexed { i, m ->
                        DonorMatchRow(m, showCandidate = false)
                        if (i < gifts.lastIndex) RowDivider()
                    }
                }
            }
        }
        item { LinkLine("Profile and connections on BayCounty.me", "point.3.connected.trianglepath.dotted") { o.openSite("/people/$personID") } }
    }
}

@Suppress("unused") private val keepPeopleDirectory: PeopleDirectory? = null
