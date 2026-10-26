package me.baycounty.kit

import kotlinx.serialization.json.JsonObject

/** The numbers and groupings behind a record list's summary, chart, groups and table. */
object Browse {
    data class Total(val label: String, val note: String?)

    /** Lists where adding up the amount column means something on its own. */
    val totals: Map<String, Total> = mapOf(
        "contracts" to Total("Approved", "Approved amounts, often not-to-exceed. Not proof of payment."),
        "change-orders" to Total("Added", "Added to existing contracts by change orders."),
        "emergency-purchases" to Total("Approved", null),
        "campaign-contributions-2026" to Total("Given", null),
        "fema-michael-projects" to Total("Federal share", "FEMA's share obligated so far, not all paid out."),
        "bed-tax-collections" to Total("Collected", null),
        "vendor-payments" to Total("Paid", null),
    )

    fun noun(datasetID: String): String = mapOf(
        "contracts" to "Contracts", "votes" to "Votes", "member-votes" to "Votes", "change-orders" to "Change orders",
        "emergency-purchases" to "Purchases", "salary-positions" to "Positions", "salary-leaders" to "Positions",
        "fema-michael-projects" to "Projects", "sales-tax-projects" to "Projects", "audit-findings" to "Findings",
        "campaign-contributions-2026" to "Gifts", "cra-payments" to "Records", "bonds" to "Bonds",
    )[datasetID] ?: "Records"

    private val agencies = mapOf(
        "special_district" to "Special districts", "visit_pcb" to "Visit Panama City Beach",
        "destination_pc" to "Destination Panama City", "mb_cdc" to "Mexico Beach CDC", "sheriff" to "Sheriff",
        "airport" to "Airport", "port" to "Port Panama City", "clerk" to "Clerk of Court", "tax_collector" to "Tax Collector",
        "property_appraiser" to "Property Appraiser", "supervisor_of_elections" to "Supervisor of Elections",
    )

    /** Government ids ("pc") become names, codes ("special_district") become words. */
    fun displayName(v: String, column: String = ""): String {
        Governments.names[v]?.let { return it }
        agencies[v]?.let { return it }
        if ("_" in v && v == v.lowercase()) return v.replace("_", " ").capitalizeFirst()
        return v
    }

    fun monthKey(row: Row): String? {
        val d = row.first(Period.eventKeys) ?: return null
        if (d.length < 7 || !d[0].isDigit()) return null
        val k = d.take(7)
        return if (k[4] == '-') k else null
    }

    val monthNames = listOf("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")

    fun monthName(key: String, withYear: Boolean = true): String {
        val m = key.takeLast(2).toIntOrNull()
        if (m == null || m !in 1..12) return key
        return if (withYear) "${monthNames[m - 1]} ${key.take(4)}" else monthNames[m - 1]
    }

    data class Bucket(val key: String, val label: String, val count: Int, val amount: Double) {
        val id: String get() = key
    }

    fun months(rows: List<Row>, spec: DatasetSpec, year: Int, through: Int? = null): List<Bucket> {
        val count = HashMap<Int, Int>(); val amount = HashMap<Int, Double>()
        for (r in rows) {
            val k = monthKey(r) ?: continue
            if (!k.startsWith(year.toString())) continue
            val m = k.takeLast(2).toIntOrNull() ?: continue
            count[m] = (count[m] ?: 0) + 1
            amount[m] = (amount[m] ?: 0.0) + (spec.amount(r) ?: 0.0)
        }
        val maxMonth = through ?: count.keys.maxOrNull() ?: return emptyList()
        return (1..maxOf(maxMonth, count.keys.maxOrNull() ?: 1)).map { m ->
            Bucket(String.format("%04d-%02d", year, m), monthNames[m - 1].take(3), count[m] ?: 0, amount[m] ?: 0.0)
        }
    }

    fun years(rows: List<Row>, spec: DatasetSpec, periods: Map<Int, Period>): List<Bucket> {
        val count = HashMap<Period, Int>(); val amount = HashMap<Period, Double>()
        for (r in rows) {
            val p = periods[r.id] ?: continue
            count[p] = (count[p] ?: 0) + 1
            amount[p] = (amount[p] ?: 0.0) + (spec.amount(r) ?: 0.0)
        }
        return count.keys.sorted().map { Bucket(it.label, it.label, count[it]!!, amount[it] ?: 0.0) }
    }

    fun top(rows: List<Row>, key: String, spec: DatasetSpec, byAmount: Boolean, limit: Int = 5): List<Bucket> {
        val count = HashMap<String, Int>(); val amount = HashMap<String, Double>()
        for (r in rows) {
            val v = r[key]?.let { Format.value(it, key) } ?: continue
            if (v.isEmpty() || isPlaceholder(v)) continue
            count[v] = (count[v] ?: 0) + 1
            amount[v] = (amount[v] ?: 0.0) + (spec.amount(r) ?: 0.0)
        }
        val ranked = count.keys.sortedWith { a, b ->
            val x = if (byAmount) amount[a] ?: 0.0 else count[a]!!.toDouble()
            val y = if (byAmount) amount[b] ?: 0.0 else count[b]!!.toDouble()
            if (x != y) y.compareTo(x) else a.compareTo(b)
        }
        return ranked.take(limit).map { Bucket(it, displayName(it, key), count[it]!!, amount[it] ?: 0.0) }
    }

    fun isPlaceholder(v: String): Boolean {
        val l = v.lowercase()
        return l.startsWith("not named") || l.startsWith("not stated") || l == "unknown" || l == "n/a"
    }

    // Grouping the list

    sealed class GroupKey {
        object None : GroupKey()
        object Month : GroupKey()
        object Year : GroupKey()
        data class Column(val column: String) : GroupKey()

        val id: String get() = when (this) { None -> "none"; Month -> "month"; Year -> "year"; is Column -> column }
        val label: String get() = when (this) { None -> "None"; Month -> "Month"; Year -> "Year"; is Column -> columnLabel(column) }
    }

    fun columnLabel(c: String): String = when (c) {
        "gov_id", "gov", "government", "employer" -> "Government"
        "vendor", "payee", "contributor" -> "Company"
        else -> Format.label(c)
    }

    data class Group(val key: String, val title: String, val rows: List<Row>, val total: Double) {
        val id: String get() = key
    }

    fun groups(rows: List<Row>, by: GroupKey, spec: DatasetSpec, periods: Map<Int, Period>): List<Group> {
        fun label(r: Row): Pair<String, String>? = when (by) {
            GroupKey.None -> "all" to "All"
            GroupKey.Month -> monthKey(r)?.let { it to monthName(it) }
            GroupKey.Year -> periods[r.id]?.let { String.format("%04d%s", it.year, if (it.fiscal) "F" else "") to it.label }
            is GroupKey.Column -> {
                val v = r[by.column]?.let { Format.value(it, by.column) }
                if (v.isNullOrEmpty()) null else displayName(v, by.column).let { it to it }
            }
        }
        val order = mutableListOf<String>(); val titles = HashMap<String, String>(); val buckets = HashMap<String, MutableList<Row>>()
        val other = mutableListOf<Row>()
        for (r in rows) {
            val l = label(r)
            if (l == null) { other.add(r); continue }
            if (buckets[l.first] == null) { order.add(l.first); titles[l.first] = l.second; buckets[l.first] = mutableListOf() }
            buckets[l.first]!!.add(r)
        }
        var out = order.map { k -> Group(k, titles[k]!!, buckets[k]!!, buckets[k]!!.mapNotNull { spec.amount(it) }.sum()) }
        out = when (by) {
            GroupKey.Month, GroupKey.Year -> out.sortedByDescending { it.key }
            is GroupKey.Column -> out.sortedWith(compareByDescending<Group> { it.rows.size }.thenBy { it.title })
            GroupKey.None -> out
        }
        if (other.isNotEmpty()) {
            out = out + Group("~other", if (by == GroupKey.Month || by == GroupKey.Year) "No date" else "Not stated", other, other.mapNotNull { spec.amount(it) }.sum())
        }
        return out
    }

    fun groupOptions(rows: List<Row>, spec: DatasetSpec, periods: Map<Int, Period>, period: Period?): List<GroupKey> {
        val out = mutableListOf<GroupKey>()
        if (period != null && !period.fiscal && rows.any { monthKey(it) != null }) out.add(GroupKey.Month)
        if (period == null && periods.values.toSet().size > 1) out.add(GroupKey.Year)
        val seen = HashSet<String>()
        for (c in spec.filterKeys + spec.titleKeys.take(1)) {
            if (c in seen || c == "member") continue
            seen.add(c)
            val values = rows.mapNotNull { it.string(c) }.toSet()
            val isTitle = spec.titleKeys.firstOrNull() == c
            if (if (isTitle) values.size >= 2 && values.size < rows.size * 3 / 4 else values.size in 2..20) out.add(GroupKey.Column(c))
            if (out.size >= 4) break
        }
        return out
    }

    fun governmentColumn(spec: DatasetSpec, rows: List<Row>): String? {
        for (c in listOf("government", "gov", "employer", "applicant", "authority", "board", "cra", "issuer", "gov_id")) {
            if (rows.any { it.string(c) != null }) return c
        }
        return null
    }

    private val shortGov = mapOf(
        "Bay County BOCC" to "County", "Bay County" to "County", "City of Panama City Beach" to "PCB",
        "Panama City Beach" to "PCB", "City of Panama City" to "Panama City", "City of Lynn Haven" to "Lynn Haven",
        "City of Callaway" to "Callaway", "City of Springfield" to "Springfield", "City of Parker" to "Parker",
        "City of Mexico Beach" to "Mexico Bch", "Bay District Schools" to "Schools", "Bay District School Board" to "Schools",
    )

    fun shortGovernment(s: String): String {
        shortGov[s]?.let { return it }
        Governments.names[s]?.let { return shortGovernment(it) }
        if ("_" in s && s == s.lowercase()) return displayName(s, "")
        return s.replace("City of ", "")
    }

    data class MeetingVotes(val date: String, val board: String, val votes: List<Row>) {
        val id: String get() = "$date|$board"
    }

    /** Votes grouped by the meeting they were taken at, newest meeting first, agenda order kept inside. */
    fun meetings(votes: List<Row>): List<MeetingVotes> {
        val order = mutableListOf<String>(); val rows = HashMap<String, MutableList<Row>>()
        for (v in votes) {
            val k = (v.string("date") ?: "") + "|" + (v.string("board") ?: "")
            if (rows[k] == null) { order.add(k); rows[k] = mutableListOf() }
            rows[k]!!.add(v)
        }
        return order.map { k ->
            val parts = k.split("|", limit = 2)
            MeetingVotes(parts[0], parts.getOrElse(1) { "" }, rows[k]!!)
        }.sortedWith(compareByDescending<MeetingVotes> { it.date }.thenBy { it.board })
    }
}

/** One recorded vote's roll call, read from its members (or its tally text when no roll call was published). */
class VoteSummary(row: Row) {
    enum class Choice { YES, NO, OTHER }
    data class Member(val name: String, val personID: String?, val choice: Choice) {
        val id: String get() = personID ?: name
    }

    val members: List<Member>
    val yes: Int
    val no: Int
    val other: Int
    /** True when it passed, false when it failed, null when the outcome isn't published yet. */
    val passed: Boolean?
    val split: Boolean

    init {
        val ms = mutableListOf<Member>()
        for (m in row["members"]?.arrayValue ?: emptyList()) {
            val o = m as? JsonObject ?: continue
            val v = (o["vote"]?.stringValue ?: "").lowercase()
            ms.add(Member(o["name"]?.stringValue ?: "Member", o["person_id"]?.stringValue,
                if (v == "yes") Choice.YES else if (v == "no") Choice.NO else Choice.OTHER))
        }
        members = ms
        if (ms.isNotEmpty()) {
            yes = ms.count { it.choice == Choice.YES }; no = ms.count { it.choice == Choice.NO }; other = ms.count { it.choice == Choice.OTHER }
        } else {
            val digits = (row.string("tally") ?: "").split(Regex("[^0-9]+")).filter { it.isNotEmpty() }.take(2).mapNotNull { it.toIntOrNull() }
            yes = digits.getOrElse(0) { 0 }; no = digits.getOrElse(1) { 0 }; other = 0
        }
        val outcome = (row.string("outcome") ?: "").lowercase()
        passed = if (outcome.startsWith("passed") || outcome.startsWith("adopted") || outcome.startsWith("approved")) true
        else if (outcome.startsWith("failed") || outcome.startsWith("denied") || outcome.startsWith("rejected")) false else null
        split = row.bool("split") ?: (yes > 0 && no > 0)
    }

    val hasTally: Boolean get() = yes + no + other > 0
    val tallyText: String get() = if (other > 0) "$yes–$no, $other absent" else "$yes–$no"
}
