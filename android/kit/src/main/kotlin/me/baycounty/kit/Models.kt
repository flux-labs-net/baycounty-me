package me.baycounty.kit

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject
import java.time.Instant
import java.time.LocalDate

/** Local governments the site covers, keyed the way the data keys them (`gov_id`). */
object Governments {
    val names = mapOf(
        "county" to "Bay County", "schools" to "Bay District Schools", "pc" to "Panama City", "pcb" to "Panama City Beach",
        "lh" to "Lynn Haven", "cw" to "Callaway", "sp" to "Springfield", "parker" to "Parker", "mb" to "Mexico Beach",
    )

    val order = listOf("county", "schools", "pc", "pcb", "lh", "cw", "sp", "parker", "mb")

    /** Board names as the site lists them, shortened for phone screens. */
    val boards = mapOf(
        "county" to "Bay County Commission", "county-planning" to "Bay County Planning Commission",
        "schools" to "Bay District School Board", "pc" to "Panama City Commission", "pc-cra" to "Panama City CRA Board",
        "pcb" to "Panama City Beach City Council", "lh" to "Lynn Haven City Commission", "lh-cra" to "Lynn Haven CRA Board",
        "cw" to "Callaway City Commission", "cw-cra" to "Callaway CRA Board", "sp" to "Springfield City Commission",
        "parker" to "Parker City Council", "mb" to "Mexico Beach City Council",
    )

    /** Two letters for a government's badge. */
    fun initials(govID: String): String {
        val known = mapOf("county" to "BC", "schools" to "SB", "pc" to "PC", "pcb" to "PB", "lh" to "LH", "cw" to "CW", "sp" to "SP", "parker" to "PK", "mb" to "MB")
        return known[govID] ?: govID.take(2).uppercase()
    }

    /** Meeting board id ("lh-cra", "county-planning", "pc") to a readable name. */
    fun boardName(board: String): String {
        boards[board]?.let { return it }
        val parts = board.split("-", limit = 2)
        val gov = names[parts.firstOrNull() ?: ""] ?: board
        if (parts.size < 2) return gov
        return if (parts[1] == "cra") "$gov CRA Board" else "$gov ${Format.label(parts[1])}"
    }

    fun orderIndex(id: String): Int = order.indexOf(id).let { if (it < 0) 99 else it }
}

/** One government profile (`government-profiles` dataset). */
data class Government(val row: Row) {
    val id: String get() = govID
    val govID: String get() = row.string("gov_id") ?: slug
    val name: String get() = row.string("government") ?: "Government"
    val kind: String get() = row.string("kind") ?: ""
    val pageURL: String? get() = row.url("page")
    val slug: String get() = row.string("slug") ?: pageURL?.substringAfterLast('/') ?: name.lowercase()

    val population: Double? get() = row.number("population_2025")
    val budgetTotal: Double? get() = row.number("budget_total")
    val generalFund: Double? get() = row.number("general_fund")
    val budgetStatus: String? get() = row.string("budget_status")
    val millage: Double? get() = row.number("millage")
    val propertyTaxLevy: Double? get() = row.number("property_tax_levy")
    val debtTotal: Double? get() = row.number("debt_total")
    val debtYear: String? get() = row.string("debt_year")
    val auditYear: String? get() = row.string("audit_year")
    val auditFindings: Int? get() = row.number("audit_findings")?.toInt()
    val repeatFindings: Int? get() = row.number("repeat_findings")?.toInt()
    val votesRecorded: Int? get() = row.number("votes_recorded")?.toInt()
    val splitVotes: Int? get() = (row.number("split_votes") ?: row.number("split_vote"))?.toInt()
    val employees: Double? get() = row.number("employees_fte")
    val typicalUtilityBill: Double? get() = row.number("typical_utility_bill")
    val femaMichael: Double? get() = row.number("fema_michael_obligated")

    val budgetPerResident: Double?
        get() { val b = budgetTotal ?: return null; val p = population ?: return null; return if (p > 0) b / p else null }
    val debtPerResident: Double?
        get() { val d = debtTotal ?: return null; val p = population ?: return null; return if (p > 0) d / p else null }
}

/** One public meeting (`meetings` dataset). */
data class Meeting(val row: Row) {
    val id: String get() = "$board|${row.string("start") ?: ""}|$title"
    val board: String get() = row.string("board") ?: ""
    val boardName: String get() = Governments.boardName(board)
    val govID: String get() = row.string("gov_id") ?: board.split("-").first()
    val title: String get() = row.string("title") ?: "Meeting"
    val start: Instant? get() = row.string("start")?.let { Dates.parse(it) }
    val hasTime: Boolean get() = (row.string("start") ?: "").length > 10
    val location: String? get() = row.string("location")
    val agendaURL: String? get() = row.url("agenda_url")
    val packetURL: String? get() = row.url("packet_url")
    val minutesURL: String? get() = row.url("minutes_url")
    val detailURL: String? get() = row.url("detail_url")
    val isPast: Boolean get() = row.bool("past") ?: false
    val isCancelled: Boolean get() = row.bool("cancelled") ?: false
    /** Not posted yet; inferred from the board's regular schedule. */
    val isExpected: Boolean get() = row.bool("expected") ?: false

    /** Agenda items that mention money (`items`), with the first dollar amount in each title. */
    val moneyItems: List<AgendaItem>
        get() = (row["items"]?.arrayValue ?: emptyList()).mapNotNull { v ->
            val o = v as? JsonObject ?: return@mapNotNull null
            val t = o["title"]?.stringValue
            if (t.isNullOrEmpty()) return@mapNotNull null
            AgendaItem(t, o["amount"]?.stringValue?.let { AgendaItem.parseAmount(it) })
        }

    /** Every agenda item, each with its dollar amount when the money list has one. */
    val agenda: List<AgendaItem>
        get() {
            val money = moneyItems
            val titles = row.strings("agenda_items").filter { !AgendaItem.isProcedural(it) }
            if (titles.isEmpty()) return money
            val amounts = HashMap<String, Double>()
            for (m in money) m.amount?.let { amounts[AgendaItem.key(m.title)] = it }
            val out = titles.map { AgendaItem(it, amounts[AgendaItem.key(it)]) }.toMutableList()
            val seen = out.map { AgendaItem.key(it.title) }.toSet()
            out += money.filter { it.amount != null && AgendaItem.key(it.title) !in seen }
            return out
        }

    /** Dollars in the agenda's money items. */
    val moneyTotal: Double get() = moneyItems.mapNotNull { it.amount }.sum()

    val whenText: String get() = start?.let { Dates.display(it, hasTime) } ?: "Date not set"

    companion object {
        /** Upcoming, not cancelled, soonest first. */
        fun upcoming(all: List<Meeting>, now: Instant = Instant.now()): List<Meeting> {
            val startOfDay = LocalDate.now(Dates.chicago).atStartOfDay(Dates.chicago).toInstant()
            return all.filter { m ->
                val s = m.start
                !m.isPast && !m.isCancelled && s != null && (s >= startOfDay || (m.hasTime && s >= now))
            }.sortedBy { it.start ?: Instant.MAX }
        }
    }
}

/** One item on a meeting agenda. */
data class AgendaItem(val title: String, val amount: Double?) {
    enum class Kind(val label: String) { SPENDING("Spending"), HEARING("Public hearing"), OTHER("Business") }

    val id: String get() = title

    val kind: Kind
        get() = when {
            amount != null -> Kind.SPENDING
            hearingWords.containsMatchIn(title) -> Kind.HEARING
            else -> Kind.OTHER
        }

    /** The title without "Consideration of approval of…" and the trailing period, for scanning. */
    val shortTitle: String
        get() {
            var t = title.trim()
            val cut = lead.replaceFirst(t, "")
            if (cut.length >= 8) t = cut.take(1).uppercase() + cut.drop(1)
            if (t.endsWith(".")) t = t.dropLast(1)
            return t
        }

    companion object {
        private val hearingWords = Regex(
            "\\b(ordinance|public hearing|rezon\\w*|zoning|land use|quasi|variance|special exception|annex\\w*|comprehensive plan)\\b",
            RegexOption.IGNORE_CASE)
        private val lead = Regex(
            "^(discussion,? and )?(consideration|request)(,? (and )?possible)?(,? and)?( approval)?(,? approval,? and authorization)?( of| to| for)?( the)?( approval( of| for)?| approve| award of)?[\\s,:]*",
            RegexOption.IGNORE_CASE)
        private val procedural = Regex(
            "^(agenda\\b|opening prayer|invocation|pledge|audience participation|public (comment|participation)|motion to adjourn|adjourn)",
            RegexOption.IGNORE_CASE)

        /** Section headings ("Consent Agenda") and procedural steps, which the agenda list leaves out. */
        fun isProcedural(t: String): Boolean {
            if (t.split(" ").filter { it.isNotEmpty() }.size <= 4) return true
            return procedural.containsMatchIn(t)
        }

        /** "$6,173,449.43" -> 6173449.43 */
        fun parseAmount(s: String): Double? {
            val digits = s.filter { it.isDigit() || it == '.' }
            val v = digits.toDoubleOrNull() ?: return null
            if (v <= 0) return null
            val lower = s.lowercase()
            return if (lower.contains("million") || lower.endsWith("m")) v * 1_000_000 else v
        }

        /** Matches an item between the full agenda and the money list. */
        fun key(t: String): String = t.lowercase().filter { it.isLetterOrDigit() }.take(80)
    }
}

/** CRA spending, with the site's counting rules: only rows with `count` true go into totals, and
 * "paid out" (Spent) is kept apart from money that is only committed or budgeted. */
object CRALedger {
    data class Summary(val agency: String, val paidOut: Double, val pending: Double, val records: Int) {
        val id: String get() = agency
        val total: Double get() = paidOut + pending
    }

    fun isCounted(row: Row): Boolean = row.bool("count") ?: false
    fun status(row: Row): String = row.string("status") ?: ""

    fun paidOut(rows: List<Row>): Double =
        rows.filter { isCounted(it) && status(it) == "Spent" }.mapNotNull { it.number("amount") }.sum()

    fun pending(rows: List<Row>): Double =
        rows.filter { isCounted(it) && status(it) in listOf("Committed", "Budgeted") }.mapNotNull { it.number("amount") }.sum()

    fun summaries(rows: List<Row>): List<Summary> =
        rows.groupBy { it.string("cra") ?: "Other" }
            .map { (k, v) -> Summary(k, paidOut(v), pending(v), v.size) }
            .sortedByDescending { it.total }

    /** What each status means, in plain words (matches the site's data rules). */
    fun explain(status: String): String = when (status) {
        "Spent" -> "Reported paid."
        "Committed" -> "Awarded or under contract, not fully paid."
        "Budgeted" -> "Set aside in a budget. A plan, not proof of payment."
        "Proposed" -> "Requested or proposed. No award confirmed."
        "Incoming" -> "Money coming in to the CRA, not spending."
        "Not CRA-funded" -> "Tied to a CRA project but paid with other money."
        else -> ""
    }
}

/** One hit from `/api/v1/search`. */
@Serializable
data class SearchResult(val type: String? = null, val title: String? = null, val summary: String? = null, val url: String? = null) {
    val id: String get() = (url ?: "") + (title ?: "")
}

@Serializable
internal data class SearchResponse(val total: Int? = null, val data: List<SearchResult> = emptyList())
