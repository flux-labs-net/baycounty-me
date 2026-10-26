package me.baycounty.kit

import java.net.URI

/** A person, company, nonprofit, business or government a record names, with its BayCounty.me profile. */
data class EntityRef(val kind: String, val key: String, val name: String, val label: String) {
    val id: String get() = "$kind:$key"

    /** The profile page, by the site's one link rule. */
    val profilePath: String get() = if (kind == "person") "/people/$key" else "/profile/$kind/$key"

    val profileURL: String
        get() = runCatching { URI("https", "baycounty.me", profilePath, null).toASCIIString() }.getOrDefault("https://baycounty.me$profilePath")

    val symbol: String
        get() = when (kind) {
            "person", "member" -> "person"
            "nonprofit" -> "heart"
            "business", "vendor" -> "building.2"
            "committee" -> "megaphone"
            "gov" -> "building.columns"
            else -> "circle.hexagongrid"
        }

    companion object {
        fun parse(id: String?, name: String?, label: String? = null): EntityRef? {
            if (id == null || name.isNullOrEmpty()) return null
            val i = id.indexOf(':')
            if (i <= 0 || i == id.length - 1) return null
            val kind = id.substring(0, i); val key = id.substring(i + 1)
            return EntityRef(kind, key, Format.orgName(name), label ?: kindLabel(kind))
        }

        fun kindLabel(kind: String): String = mapOf(
            "person" to "Official or candidate", "member" to "Board member", "nonprofit" to "Nonprofit", "business" to "Registered business",
            "vendor" to "Company", "committee" to "Political committee", "gov" to "Government",
        )[kind] ?: kind.capitalizeFirst()
    }
}

/**
 * How a record's detail screen presents one row, worked out from the row alone: the people and organizations it
 * names, its tags, headline numbers, years on file and related records.
 */
object RecordProfile {
    private data class RefCol(val id: String, val name: String, val kind: String)

    private fun refColumns(datasetID: String): List<RefCol> {
        val member = datasetID.startsWith("nonprofit") || datasetID == "charity-registrations"
        val cols = mutableListOf(RefCol("nonprofit_id", "nonprofit", "nonprofit"), RefCol("doc_number", "business", "business"))
        if (member) cols.add(0, RefCol("person_id", "person", "member"))
        if (datasetID == "nonprofit-officials") cols.add(0, RefCol("official_id", "official", "person"))
        return cols
    }

    fun refs(datasetID: String, row: Row): List<EntityRef> {
        val out = mutableListOf<EntityRef>()
        if (datasetID == "entity-connections") {
            for (side in listOf("from", "to")) EntityRef.parse(row.string("${side}_id"), row.string("${side}_name"))?.let { out.add(it) }
            return out
        }
        for (c in refColumns(datasetID)) {
            val key = row.string(c.id) ?: continue
            val name = row.string(c.name) ?: continue
            if (datasetID == "nonprofits" && c.kind == "nonprofit") continue
            val k = if (c.kind == "business") key.lowercase() else key
            out.add(EntityRef(c.kind, k, if (c.kind == "member" || c.kind == "person") name else Format.orgName(name), EntityRef.kindLabel(c.kind)))
        }
        return out
    }

    fun subject(datasetID: String, row: Row): EntityRef? = when (datasetID) {
        "nonprofits", "charity-registrations" -> {
            val id = row.string("nonprofit_id"); val n = row.string("name")
            if (id == null || n == null) null else EntityRef("nonprofit", id, Format.orgName(n), "Nonprofit")
        }
        "entity-profiles" -> EntityRef.parse(row.string("entity_id"), row.string("name"), row.string("kind_label"))
        else -> refs(datasetID, row).firstOrNull { it.kind == "member" || it.kind == "person" }
    }

    fun title(datasetID: String, row: Row): String = DatasetSpec.forId(datasetID).title(row)

    val orgColumns = setOf("nonprofit", "business", "recipient", "grantor", "organization")

    fun roleLine(datasetID: String, row: Row): String? {
        row.string("titles")?.let { return sentenceList(it.split(", ")) }
        return DatasetSpec.forId(datasetID).subtitle(row).ifEmpty { null }
    }

    fun sentenceList(items: List<String>): String {
        val xs = items.map { it.trim() }.filter { it.isNotEmpty() }
        if (xs.size <= 1) return xs.firstOrNull() ?: ""
        return xs.dropLast(1).joinToString(", ") + " and " + xs.last()
    }

    fun initials(datasetID: String, row: Row): String? {
        val titleKey = DatasetSpec.forId(datasetID).titleKeys.firstOrNull()
        val isPerson = titleKey in listOf("person", "official") ||
            (datasetID == "entity-profiles" && (row.string("kind") ?: "") in listOf("person", "member"))
        if (!isPerson) return null
        val words = DatasetSpec.forId(datasetID).title(row).split(" ").filter { it.firstOrNull()?.isLetter() == true }
        val f = words.firstOrNull()?.first() ?: return null
        val l = if (words.size > 1) words.last().first().toString() else ""
        return (f.toString() + l).uppercase()
    }

    enum class Tone { GOOD, ACCENT, NEUTRAL, WARN }
    data class Chip(val text: String, val tone: Tone)

    fun chips(datasetID: String, row: Row): List<Chip> {
        val out = mutableListOf<Chip>()
        row.bool("current")?.let { out.add(Chip(if (it) "Current" else "Past", if (it) Tone.GOOD else Tone.NEUTRAL)) }
        val role = row.string("role")
        if (role != null && (!role.lowercase().startsWith("past") || row.bool("current") == null)) {
            out.add(Chip(role.replace("Past ", "").capitalizeFirst(), Tone.ACCENT))
        }
        for (s in (row.string("sources") ?: "").split(", ")) if (s.isNotEmpty() && !s.startsWith("http")) out.add(Chip(s, Tone.NEUTRAL))
        val spec = DatasetSpec.forId(datasetID)
        for (key in listOf("status", "sunbiz_status", "fdacs_status", "kind", "match")) {
            if (key == spec.badgeKey || key in spec.subtitleKeys) continue
            val v = row.string(key) ?: continue
            if (v.length < 32) {
                val t = Format.value(row[key]!!, key)
                if (out.none { it.text == t }) out.add(Chip(t, Tone.NEUTRAL))
            }
        }
        return out
    }

    data class Fact(val value: String, val label: String)

    fun facts(datasetID: String, row: Row): List<Fact> {
        val out = mutableListOf<Fact>()
        row.number("compensation")?.takeIf { it > 0 }?.let { pay ->
            out.add(Fact(Format.compactMoney(pay), "Reported pay" + (row.number("compensation_year")?.let { " (${it.toInt()})" } ?: "")))
        }
        row.number("hours_per_week")?.takeIf { it > 0 }?.let { out.add(Fact(Format.number(it), "Hours a week")) }
        val y = years(row)
        if (y != null && out.size < 2) {
            out.add(Fact(y.first.toString(), "On file since"))
            val n = y.last - y.first + 1
            if (out.size < 2) out.add(Fact(n.toString(), if (n == 1) "Year on file" else "Years on file"))
        }
        row.number("other_current_boards")?.let { out.add(Fact(Format.number(it), if (it == 1.0) "Other local board" else "Other local boards")) }
        val counts = listOf(
            "board_members_listed" to "Board members", "shares_board_with" to "Share a board member", "returns_on_file" to "IRS returns",
            "employees" to "Employees", "connections" to "Connections", "records" to "Records", "officers_listed" to "Officers listed",
        )
        for ((k, label) in counts) if (out.size < 4) row.number(k)?.takeIf { it > 0 }?.let { out.add(Fact(Format.number(it), label)) }
        val money = listOf("total_revenue" to "Revenue", "total_assets" to "Assets", "gov_dollars_in_records" to "From governments")
        val amountKey = DatasetSpec.forId(datasetID).amountKey(row)
        for ((k, label) in money) if (out.size < 4 && k != amountKey) row.number(k)?.takeIf { it != 0.0 }?.let { out.add(Fact(Format.compactMoney(it), label)) }
        return out.take(4)
    }

    fun years(row: Row): IntRange? {
        val a = (row.number("first_year") ?: row.number("last_year"))?.toInt() ?: return null
        val b = row.number("last_year")?.toInt() ?: a
        return minOf(a, b)..maxOf(a, b)
    }

    data class Group(val title: String, val datasetID: String, val column: String, val value: String)

    fun groups(datasetID: String, row: Row): List<Group> {
        fun g(title: String, ds: String, col: String, from: String? = null) = row.string(from ?: col)?.let { Group(title, ds, col, it) }
        return when (datasetID) {
            "nonprofit-board-members" -> listOfNotNull(g("Other boards", datasetID, "person_id"), g("Also on this board", datasetID, "nonprofit_id"))
            "nonprofit-board-businesses" -> listOfNotNull(g("Their nonprofit boards", "nonprofit-board-members", "person_id"), g("Their businesses", datasetID, "person_id"))
            "nonprofits", "charity-registrations" -> listOfNotNull(g("Board", "nonprofit-board-members", "nonprofit_id"))
            else -> emptyList()
        }
    }

    fun members(group: Group, rows: List<Row>, excluding: Int?, sameDataset: Boolean): List<Row> =
        rows.filter { it.string(group.column) == group.value && !(sameDataset && it.id == excluding) }
            .sortedWith(compareByDescending<Row> { it.bool("current") ?: false }.thenByDescending { it.number("last_year") ?: 0.0 })

    fun groupRowTitle(group: Group, row: Row): String {
        if (group.datasetID == "nonprofit-board-members") {
            return if (group.column == "person_id") Format.orgName(row.string("nonprofit") ?: "Nonprofit") else (row.string("person") ?: "Board member")
        }
        return title(group.datasetID, row)
    }

    fun groupRowDetail(group: Group, row: Row): String {
        val parts = mutableListOf<String>()
        row.string("titles")?.let { parts.add(sentenceList(it.split(", "))) }
        years(row)?.let { parts.add(if (it.first == it.last) it.first.toString() else "${it.first}–${it.last}") }
        if (row.bool("current") == false) parts.add("past")
        if (parts.isEmpty()) parts.add(DatasetSpec.forId(group.datasetID).subtitle(row))
        return parts.joinToString(" · ")
    }

    val shownColumns = setOf(
        "person", "nonprofit", "titles", "role", "current", "first_year", "last_year", "sources", "other_current_boards",
        "compensation", "compensation_year", "hours_per_week", "county", "nonprofit_id", "doc_number", "entity_id",
        "from_id", "to_id", "from_url", "to_url", "from_kind", "to_kind", "page_url", "link_id",
    )

    fun otherFields(datasetID: String, row: Row, columns: List<DatasetInfo.Column>): List<Pair<String, String>> {
        val titleKey = DatasetSpec.forId(datasetID).titleKeys.firstOrNull { row.string(it) != null }
        val names = if (columns.isEmpty()) row.values.keys.sorted() else columns.map { it.name }
        return names.mapNotNull { name ->
            if (name == titleKey || name in shownColumns || name in DatasetSpec.hiddenColumns || name.endsWith("_url")) return@mapNotNull null
            val v = row[name] ?: return@mapNotNull null
            if (v.isEmptyValue) return@mapNotNull null
            val s = Format.value(v, name)
            Format.label(name) to (if (name in orgColumns) Format.orgName(s) else s)
        }
    }
}
