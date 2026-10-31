package me.baycounty.kit

import kotlinx.serialization.json.JsonObject

/**
 * The links between records that the website draws: a contract's company and the vote that approved it,
 * a person's votes, pay and campaign money. Works on whatever dataset rows are loaded.
 */
object RecordLinks {
    val vendorDatasets = listOf("contracts", "change-orders", "emergency-purchases", "cra-payments", "vendor-payments", "campaign-contributions-2026")
    val personDatasets = listOf(
        "officials-pay", "salary-leaders", "campaign-finance", "candidates-2026", "member-votes", "votes",
        "officeholder-terms", "campaign-history", "business-donor-sunbiz", "owner-gifts",
        "contract-dollar-totals", "member-contract-dollars",
    )

    fun vendorIDs(row: Row): List<String> {
        val ids = row.strings("vendor_ids").toMutableList()
        row.string("vendor_id")?.let { if (it !in ids) ids.add(0, it) }
        return ids
    }

    fun personIDs(row: Row): List<String> {
        val ids = mutableListOf<String>()
        row.string("person_id")?.let { ids.add(it) }
        row.string("candidate_id")?.let { if (it !in ids) ids.add(it) }
        for (m in row["members"]?.arrayValue ?: emptyList()) {
            val p = (m as? JsonObject)?.get("person_id")?.stringValue ?: continue
            if (p !in ids) ids.add(p)
        }
        return ids
    }

    fun voteIDs(row: Row): List<String> = row.strings("vote_ids") + listOfNotNull(row.string("vote_id"))

    fun recordsForVendor(id: String, rows: Map<String, List<Row>>): List<Pair<String, List<Row>>> =
        vendorDatasets.mapNotNull { ds ->
            val hits = newestFirst((rows[ds] ?: emptyList()).filter { id in vendorIDs(it) }, ds)
            if (hits.isEmpty()) null else ds to hits
        }

    fun newestFirst(rows: List<Row>, dataset: String): List<Row> {
        val spec = DatasetSpec.forId(dataset)
        return rows.sortedByDescending { spec.newestKey(it) }
    }

    /** Recorded votes that approved this company's contracts, change orders or emergency purchases. */
    fun votesForVendor(id: String, rows: Map<String, List<Row>>): List<Row> {
        val deals = listOf("contracts", "change-orders", "emergency-purchases").flatMap { rows[it] ?: emptyList() }.filter { id in vendorIDs(it) }
        val ids = deals.flatMap(::voteIDs).toSet()
        val recordIDs = deals.mapNotNull { it.string("record_id") }.toSet()
        return (rows["votes"] ?: emptyList()).filter { v ->
            (v.string("vote_id")?.let { it in ids } ?: false) || v.strings("contract_ids").any { it in recordIDs }
        }.sortedByDescending { it.string("date") ?: "" }
    }

    fun recordsForPerson(id: String, rows: Map<String, List<Row>>): List<Pair<String, List<Row>>> =
        personDatasets.mapNotNull { ds ->
            val hits = newestFirst((rows[ds] ?: emptyList()).filter { id in personIDs(it) }, ds)
            if (hits.isEmpty()) null else ds to hits
        }

    /** How a person voted on one recorded vote (from its roll call). */
    fun voteOf(personID: String, voteRow: Row): String? {
        for (m in voteRow["members"]?.arrayValue ?: emptyList()) {
            val o = m as? JsonObject ?: continue
            if (o["person_id"]?.stringValue == personID) return o["vote"]?.stringValue
        }
        return null
    }

    data class Tally(val yes: Int = 0, val no: Int = 0, val other: Int = 0) {
        val total: Int get() = yes + no + other
    }

    /** The dollars in the contract votes one official cast (dataset contract-dollar-totals, one row per government):
     *  yes on items that passed, yes on items that failed, no, the votes behind each, and what is left out. */
    data class ContractDollars(
        val yes: Double, val yesFailed: Double, val no: Double, val yesVotes: Int, val yesFailedVotes: Int, val noVotes: Int,
        val contractVotes: Int, val consent: Int, val notCounted: Int, val first: String?, val last: String?,
    )

    fun contractDollars(totals: List<Row>): ContractDollars? {
        if (totals.isEmpty()) return null
        fun sum(k: String) = totals.sumOf { it.number(k) ?: 0.0 }
        fun cents(v: Double) = Math.round(v * 100) / 100.0
        val c = ContractDollars(
            yes = cents(sum("yes_total")), yesFailed = cents(sum("yes_failed_total")), no = cents(sum("no_total")),
            yesVotes = sum("yes_votes").toInt(), yesFailedVotes = sum("yes_failed_votes").toInt(), noVotes = sum("no_votes").toInt(),
            contractVotes = sum("contract_votes").toInt(), consent = sum("not_counted_consent").toInt(),
            notCounted = (sum("not_counted_no_amount") + sum("not_counted_unclear") + sum("not_counted_not_spending")).toInt(),
            first = totals.mapNotNull { it.string("first_date") }.minOrNull(), last = totals.mapNotNull { it.string("last_date") }.maxOrNull(),
        )
        return if (c.contractVotes > 0) c else null
    }

    fun tally(memberVotes: List<Row>): Tally {
        var y = 0; var n = 0; var o = 0
        for (r in memberVotes) when ((r.string("vote") ?: "").lowercase()) { "yes" -> y++; "no" -> n++; else -> o++ }
        return Tally(y, n, o)
    }
}
