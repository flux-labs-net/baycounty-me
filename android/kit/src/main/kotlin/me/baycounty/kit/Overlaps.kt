package me.baycounty.kit

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject

/** Where records overlap (/connections/overlaps): the headline numbers and the top few of each overlap, and the live parts
 *  from GET /api/v1/overlaps. Mirrors the Swift `Overlaps` and site/overlaps_page.py. A row puts two public records side by
 *  side; it is not a finding. Individual donors are never named. */
object Overlaps {
    val datasets = listOf("donor-votes", "vote-mentions", "agenda-parties", "bid-trail", "emergency-purchase-donors",
        "shared-owner-vendors", "chamber-overlaps", "development-companies", "campaign-results")
    const val LIVE_PATH = "/api/v1/overlaps"

    data class Card(val title: String, val stat: String, val items: List<String>, val dataset: String, val symbol: String)

    private fun money(n: Double?) = Format.compactMoney(n ?: 0.0)

    /** Contested races (two or more candidates with a report and a result): (races, races the top fundraiser won). */
    fun races(results: List<Row>): Pair<Int, Int> {
        val contested = results.groupBy { "${it.string("election_date") ?: ""}|${it.string("office") ?: ""}" }.values.filter { it.size > 1 }
        return contested.size to contested.count { rs -> rs.any { it.number("money_rank") == 1.0 && it.number("vote_rank") == 1.0 } }
    }

    data class Headline(val donorVotes: Int, val pairs: Int, val mentionVotes: Int, val mentionEntities: Int, val contested: Int, val topWon: Int,
                        val emergencyFromDonors: Int, val emergency: Int)

    fun headline(rows: Map<String, List<Row>>): Headline {
        val dv = rows["donor-votes"].orEmpty()
        val vm = rows["vote-mentions"].orEmpty()
        val ep = rows["emergency-purchase-donors"].orEmpty()
        val (contested, won) = races(rows["campaign-results"].orEmpty())
        return Headline(dv.mapNotNull { it.string("vote_id") }.toSet().size, dv.map { "${it.string("member_id")}|${it.string("company_id")}" }.toSet().size,
            vm.mapNotNull { it.string("vote_id") }.toSet().size, vm.mapNotNull { it.string("entity_id") }.toSet().size, contested, won,
            ep.count { it.bool("gave_to_officials_here") == true }, ep.size)
    }

    private fun top(d: Map<String, Set<String>>, n: Int = 3) = d.entries.sortedByDescending { it.value.size }.take(n).map { it.key to it.value.size }

    fun cards(rows: Map<String, List<Row>>): List<Card> {
        val h = headline(rows)
        val dv = rows["donor-votes"].orEmpty()
        val ap = rows["agenda-parties"].orEmpty().filter { it.string("entity_id") != null && it.string("entity_kind") != "gov" }
        val bt = rows["bid-trail"].orEmpty()
        val ep = rows["emergency-purchase-donors"].orEmpty()
        val so = rows["shared-owner-vendors"].orEmpty()
        val ch = rows["chamber-overlaps"].orEmpty()
        val dc = rows["development-companies"].orEmpty()
        val pairs = mutableMapOf<String, MutableSet<String>>()
        for (r in dv) pairs.getOrPut("${r.string("member") ?: ""} on ${r.string("company") ?: ""}") { mutableSetOf() }.add(r.string("vote_id") ?: "")
        val named = mutableMapOf<String, MutableSet<String>>()
        for (r in ap) named.getOrPut(r.string("entity_name") ?: r.string("party") ?: "") { mutableSetOf() }.add(r.string("meeting_date") ?: "")
        val notices = LinkedHashMap<String, String>()
        for (r in bt) r.string("notice_id")?.let { if (it !in notices) notices[it] = r.string("notice_title") ?: r.string("reference") ?: "" }
        val groups = so.groupBy { it.string("group_id") ?: "" }.values.sortedByDescending { g -> g.mapNotNull { it.number("paid_by_this_government") }.sum() }
        val chamberWeight = { r: Row -> (r.number("organization_paid_by_governments") ?: 0.0) + (r.number("organization_gave_to_campaigns") ?: 0.0) }
        val gave = ep.filter { it.bool("gave_to_officials_here") == true }.sortedByDescending { it.number("amount") ?: 0.0 }
        return listOf(
            Card("Votes naming a member's donor", "${Format.number(h.donorVotes)} votes · ${h.pairs} official and company pairs",
                top(pairs).map { "${it.first}: ${it.second} votes" }, "donor-votes", "link"),
            Card("Companies on agendas", "${ap.size} agenda items name a company or group", top(named).map { "${it.first}: ${it.second} meetings" }, "agenda-parties", "list.bullet.rectangle"),
            Card("Bids from notice to award", "${notices.size} bids followed by number", notices.values.take(3), "bid-trail", "doc.text.magnifyingglass"),
            Card("Emergency purchases from donors", "${h.emergencyFromDonors} of ${h.emergency} bought from a company that gave",
                gave.take(3).map { "${it.string("vendor") ?: ""}: ${money(it.number("amount"))}" }, "emergency-purchase-donors", "exclamationmark.triangle"),
            Card("Shared officers among vendors", "${groups.size} groups paid by one government", groups.take(3).map { "${it[0].string("officer") ?: ""}: ${it.size} companies" },
                "shared-owner-vendors", "person.2"),
            Card("Chamber boards", "${ch.size} board members who are officials, donors or vendors",
                ch.sortedByDescending(chamberWeight).take(3).map { "${it.string("person") ?: ""}, ${it.string("chamber") ?: ""}" }, "chamber-overlaps", "storefront"),
            Card("Developers behind projects", "${dc.size} projects named after a business", dc.take(3).map { "${it.string("project") ?: ""}: ${it.string("company") ?: ""}" },
                "development-companies", "building.2"),
            Card("Money raised and votes won", "The top fundraiser won ${h.topWon} of ${h.contested} contested races",
                listOf("${h.contested - h.topWon} races went to a candidate who raised less"), "campaign-results", "chart.bar"),
        )
    }

    /** The live sections, in the site's order: (key, title, caption). */
    val liveSections = listOf(
        Triple("official_business_votes", "Votes on an official's own business", "Hand-checked matches: an official's registered business named in a motion they voted on"),
        Triple("nonprofit_board_money", "Nonprofits with an official on the board", "Payments from that official's government and their votes naming it"),
        Triple("checkbook_donors", "Checkbook payees that gave to campaigns", "From each city's check register"),
        Triple("split_purchases", "Payments just under a threshold", "Two or more payments to one payee within 30 days, each just under a purchasing limit"),
    )

    /** {section: rows} from the /api/v1/overlaps answer ({data: {section: {rows, error}}}). */
    fun decodeLive(bytes: ByteArray): Map<String, List<Row>> {
        val top = (BCJson.parseToJsonElement(bytes.decodeToString()) as? JsonObject)?.get("data") as? JsonObject ?: return emptyMap()
        return top.mapValues { (_, v) -> ((v as? JsonObject)?.get("rows") as? JsonArray).orEmpty().mapIndexedNotNull { i, x -> (x as? JsonObject)?.let { Row(i, it) } } }
    }

    data class LiveLine(val title: String, val detail: String, val entity: String?)

    fun liveLine(section: String, r: Row): LiveLine = when (section) {
        "official_business_votes" -> LiveLine("${r.string("official") ?: ""} · ${r.string("business") ?: ""}",
            listOfNotNull(r.string("date"), r.string("headline"), r.string("official_vote")?.let { "Voted $it" }).joinToString(" · "), r.string("business_id"))
        "nonprofit_board_money" -> {
            val votes = r["votes"]?.arrayValue?.size ?: 0
            LiveLine("${r.string("official") ?: ""} · ${r.string("nonprofit") ?: ""}",
                listOfNotNull(r.number("paid_by_own_government")?.let { "${money(it)} from ${r.string("payers") ?: "their government"}" },
                    if (votes > 0) "$votes votes naming it" else "No vote naming it on file").joinToString(" · "), r.string("nonprofit_id"))
        }
        "checkbook_donors" -> LiveLine(r.string("payee") ?: "",
            "Paid ${money(r.number("paid"))} by ${r.string("government") ?: r.string("gov_id") ?: ""} · gave ${money(r.number("gave_to_campaigns"))} to campaigns", r.string("payee_id"))
        else -> LiveLine(r.string("payee") ?: "",
            "${(r.number("payments") ?: 0.0).toInt()} payments just under ${money(r.number("threshold"))} · ${money(r.number("total"))} total · ${r.string("government") ?: ""}", r.string("payee_id"))
    }
}
