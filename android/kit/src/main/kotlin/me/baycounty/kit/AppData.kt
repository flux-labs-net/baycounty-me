@file:Suppress("PropertyName")

package me.baycounty.kit

import kotlinx.serialization.KSerializer
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement
import java.time.Instant
import java.time.LocalDate

// Files the site publishes for the app in /data/app (written by site/app_data.py).

@Serializable
data class AppDataIndex(val version: Int = 0, val built: String? = null, val files: List<String> = emptyList())

// Tax model (/data/app/tax.json, the Tax Dollars page's data)

@Serializable
data class TaxModel(
    val years: List<Int> = emptyList(),
    val fy: List<String> = emptyList(),
    val second: List<Double> = emptyList(),
    val groups: List<List<String>> = emptyList(),
    val auth: Map<String, Authority> = emptyMap(),
    val districts: List<District> = emptyList(),
    val levy: Map<String, List<Double?>> = emptyMap(),
    val bars: List<Bar> = emptyList(),
    val govs: List<GovBudget> = emptyList(),
    val gaps: List<String>? = null,
) {
    @Serializable
    data class Authority(
        val n: String = "", val g: String = "", val school: Boolean = false,
        val m: List<Double?> = emptyList(), val rb: List<Double?>? = null, val lv: List<Double?>? = null,
    ) {
        val name: String get() = n
        val group: String get() = g
    }

    @Serializable
    data class District(val id: String = "", val label: String = "", val stack: List<String> = emptyList(), val total: List<Double> = emptyList())

    @Serializable
    data class Bar(val n: String = "", val g: String = "", val v: Double = 0.0)

    @Serializable
    data class GovBudget(
        val id: String = "",
        val short: String = "",
        val name: String = "",
        val status: List<String> = emptyList(),
        val total: Double? = null,
        val gf: Double? = null,
        val mills: Double? = null,
        val levy: Double? = null,
        val rev: Map<String, Double>? = null,
        val exp: Map<String, Double>? = null,
        val src: List<List<String?>>? = null,
        val ctx: List<List<String>>? = null,
        val hist: List<List<JsonElement>>? = null,
        val notes: List<String>? = null,
        val next: Next? = null,
        val mix: Map<String, Double>? = null,
        val other: Map<String, Double>? = null,
        val act: List<Actual>? = null,
    ) {
        @Serializable
        data class Next(
            val fy: String = "", val total: Double? = null, val gf: Double? = null, val mills: Double? = null,
            val adopted: Boolean? = null, val excl: Boolean? = null, val src: List<String>? = null,
        )

        @Serializable
        data class Actual(
            val fy: String = "", val rev: Map<String, Double> = emptyMap(), val exp: Map<String, Double> = emptyMap(),
            val pop: Double? = null, val rt: Double? = null, val et: Double? = null, val rs: String? = null, val es: String? = null,
        )

        val statusOK: Boolean get() = status.firstOrNull() == "ok"
        val statusText: String get() = status.getOrNull(1) ?: ""
    }

    val latest: Int get() = years.size - 1
    val groupIDs: List<String> get() = groups.mapNotNull { it.firstOrNull() }
    fun groupName(g: String): String = groups.firstOrNull { it.firstOrNull() == g }?.lastOrNull() ?: g
}

// Amendment 3 (/data/app/amendment3.json)

@Serializable
data class Amendment3Model(
    val districts: List<TaxModel.District> = emptyList(),
    val auth: Map<String, TaxModel.Authority> = emptyMap(),
    val groups: List<List<String>> = emptyList(),
    val second: Double = 0.0,
    val govs: List<Gov> = emptyList(),
    val state: List<Double> = emptyList(),
    /** Election day ("2026-11-03"); older files don't carry it. */
    val vote: String? = null,
) {
    @Serializable
    data class Gov(val n: String = "", val levy: Double = 0.0, val gf: Double? = null, val imp: List<Double> = emptyList()) {
        val id: String get() = n
    }

    /** Revenue Bay County's local governments would lose in one fiscal year (index into [fiscalYears]). */
    fun localImpact(year: Int): Double = govs.mapNotNull { it.imp.getOrNull(year) }.sum()

    /** True until the end of election day, in Bay County time. */
    fun isBeforeVote(now: Instant = Instant.now()): Boolean {
        val v = vote ?: return false
        val day = runCatching { LocalDate.parse(v.take(10)) }.getOrNull() ?: return false
        return now.isBefore(day.plusDays(1).atStartOfDay(Dates.chicago).toInstant())
    }

    companion object {
        val fiscalYears = listOf("FY2028", "FY2029", "FY2030", "FY2031", "FY2032")
    }
}

// Address lookup tables (/data/app/address.json)

@Serializable
data class AddressModel(
    val taxdist: Map<String, String> = emptyMap(),
    val craAgency: Map<String, String> = emptyMap(),
    val cra: Map<String, CRATotal> = emptyMap(),
    val districts: Map<String, District> = emptyMap(),
    val auth: Map<String, Auth> = emptyMap(),
    val groups: List<List<String>> = emptyList(),
    val fy: String = "",
    val second2026: Double = 0.0,
    val navLabel: Map<String, String> = emptyMap(),
    val shards: Map<String, Int> = emptyMap(),
    val govs: Map<String, GovLink> = emptyMap(),
    val craId: Map<String, String> = emptyMap(),
    /** Government key -> [[member name as in recorded votes, yes count, no count]] */
    val members: Map<String, List<List<JsonElement>>> = emptyMap(),
    val elections: Boolean? = null,
) {
    @Serializable data class District(val label: String = "", val stack: List<String> = emptyList(), val total: Double = 0.0)
    @Serializable data class Auth(val n: String = "", val g: String = "", val school: Boolean = false, val m: Double = 0.0)
    @Serializable data class CRATotal(val spent: Double = 0.0, val n: Int = 0)
    @Serializable data class GovLink(val s: String = "", val slug: String = "", val c: String? = null, val f: String? = null, val cra: String? = null, val b: Boolean = false)
}

// Glossary, pages, updates

@Serializable
data class Glossary(val groups: List<Group> = emptyList(), val terms: List<Term> = emptyList()) {
    @Serializable data class Group(val id: String = "", val name: String = "")

    @Serializable
    data class Term(
        val id: String = "", val group: String = "", val term: String = "", val simple: String = "",
        val more: String? = null, val example: String? = null,
    ) {
        /** "Community Redevelopment Agency (CRA)" -> ["Community Redevelopment Agency", "CRA"]. */
        val matchWords: List<String>
            get() {
                val out = mutableListOf(term.replace(Regex("\\s*\\([^)]*\\)"), ""))
                Regex("\\(([^)]+)\\)").find(term)?.let { out.add(it.groupValues[1]) }
                return out.filter { it.length >= 3 }
            }
    }

    /** Glossary terms that appear in a piece of text, in the order they first appear. */
    fun termsIn(text: String): List<Term> {
        val lower = text.lowercase()
        return terms.mapNotNull { t ->
            for (w in t.matchWords) {
                val wl = w.lowercase()
                var i = lower.indexOf(wl)
                while (i >= 0) {
                    if (isWordBoundary(lower, i, i + wl.length)) return@mapNotNull t to i
                    i = lower.indexOf(wl, i + 1)
                    break
                }
            }
            null
        }.sortedBy { it.second }.map { it.first }
    }

    companion object {
        fun isWordBoundary(s: String, start: Int, end: Int): Boolean {
            fun ok(c: Char?) = c == null || !c.isLetterOrDigit()
            return ok(s.getOrNull(start - 1)) && ok(s.getOrNull(end))
        }
    }
}

@Serializable
data class PageInfo(
    val path: String = "/",
    val title: String = "",
    val description: String = "",
    val lede: String? = null,
    val explainer: Explainer? = null,
) {
    @Serializable data class Explainer(val heading: String = "", val paragraphs: List<String> = emptyList())
    val id: String get() = path
    val url: String get() = BayCountyClient.SITE + (if (path == "/") "/" else path)
}

@Serializable
data class SiteUpdate(val date: String = "", val title: String = "", val text: String = "", val pages: List<String> = emptyList()) {
    val id: String get() = date + title
}

// Companies and people

@Serializable
data class VendorDirectory(val about: String? = null, val vendors: List<Vendor> = emptyList()) {
    @Serializable
    data class Vendor(
        val id: String = "", val name: String = "", val aliases: List<String> = emptyList(),
        val gov_ids: List<String> = emptyList(), val records: Map<String, Int> = emptyMap(),
        val type: String? = null, val page: String? = null,
    ) {
        val recordCount: Int get() = records.values.sum()
        val pageURL: String? get() = page?.let { BayCountyClient.absolute(it) }
    }
}

@Serializable
data class PeopleDirectory(val about: String? = null, val people: List<Person> = emptyList()) {
    companion object {
        /**
         * The People list as the site shows it: one heading per government, each in government then title then last-name order.
         * Without the order fields (an older people.json) it falls back to the first government and the name.
         */
        fun grouped(list: List<Person>): List<Pair<String, List<Person>>> {
            val out = linkedMapOf<String, MutableList<Person>>()
            for (p in list.sortedWith(compareBy<Person>({ it.order ?: Int.MAX_VALUE }, { it.name }))) {
                val title = p.group ?: Governments.names[p.gov ?: p.gov_ids.firstOrNull() ?: ""] ?: "Other offices"
                out.getOrPut(title) { mutableListOf() } += p
            }
            return out.map { it.key to it.value }
        }
    }

    @Serializable
    data class Person(
        val id: String = "",
        val name: String = "",
        val district: String? = null,
        val gov_ids: List<String> = emptyList(),
        /** The site's one line about them. */
        val subtitle: String? = null,
        /** Elected official, Department leader, Candidate, Former official or Past candidate. */
        val label: String? = null,
        /** The People page's filter groups: elected, candidate, staff, past. */
        val kinds: List<String>? = null,
        /** Path of their official photo on the site ("/photos/people/<id>.webp", dataset official-photos); null shows initials. */
        val photo: String? = null,
        /**
         * The People list's order (site/people_pages.py directory_order): the government they are listed under,
         * its name (the list's heading), their title rank (0 mayor or chair ... 8 past candidate) and their position.
         */
        val gov: String? = null,
        val group: String? = null,
        val rank: Int? = null,
        val order: Int? = null,
        val roles: List<Role> = emptyList(),
    ) {
        val photoUrl: String? get() = photo?.let { BayCountyClient.SITE + it }

        @Serializable data class Role(val role: String? = null, val gov_id: String? = null, val seat: String? = null)

        /** Roles with the duplicates removed (see the iOS kit for the reasoning). */
        val mainRoles: List<Role>
            get() {
                fun generic(r: Role): Boolean { val t = (r.role ?: "").lowercase(); return t == "board member" || t.startsWith("officeholder:") }
                fun pastRace(r: Role): Boolean { val t = r.role ?: ""; return Regex("^20\\d\\d candidate:").containsMatchIn(t) && !t.startsWith("2026 candidate") }
                fun norm(r: Role): String {
                    var t = (r.role ?: "").lowercase()
                    for (w in listOf("city of ", "bay district ", "residential golf ")) t = t.replace(w, "")
                    return t.replace("commissioner, ward", "commission, ward")
                }
                val out = mutableListOf<Role>()
                val govs = mutableListOf<String?>()
                for (r in roles) if (r.gov_id !in govs) govs.add(r.gov_id)
                for (g in govs) {
                    val here = roles.filter { it.gov_id == g }
                    val specific = here.filter { !generic(it) }
                    var keep = if (specific.isEmpty()) here else specific
                    if (keep.any { !pastRace(it) }) keep = keep.filter { !pastRace(it) }
                    if (specific.isEmpty() && keep.any { (it.role ?: "").lowercase().startsWith("officeholder:") }) {
                        keep = keep.filter { (it.role ?: "").lowercase().startsWith("officeholder:") }
                    }
                    val texts = keep.map(::norm)
                    val seen = HashSet<String>()
                    for (r in keep) {
                        val t = norm(r)
                        if (texts.any { it != t && it.startsWith(t) }) continue
                        if (seen.add(t)) out.add(r)
                    }
                }
                return out
            }

        val headline: String
            get() {
                if (!subtitle.isNullOrEmpty()) return subtitle
                val main = mainRoles
                val r = main.firstOrNull { val t = it.role ?: ""; !t.startsWith("former") && !t.startsWith("2026 candidate") }
                    ?: main.firstOrNull { !(it.role ?: "").startsWith("former") } ?: main.firstOrNull()
                val gov = (r?.gov_id ?: gov_ids.firstOrNull())?.let { Governments.names[it] } ?: ""
                val role = (r?.role ?: "").capitalizeFirst()
                return listOf(role, gov).filter { it.isNotEmpty() }.joinToString(", ")
            }
    }
}

@Serializable
data class DonorContracts(val as_of: String? = null, val method: String? = null, val matches: List<Match> = emptyList()) {
    @Serializable
    data class Match(
        val contributor: String? = null,
        val vendor: String? = null,
        /** The company's one name on the site (record spellings in [vendor] can differ: "TK Vandy LLC" / "T K Vandy LLC"). */
        val vendor_name: String? = null,
        val vendor_id: String? = null,
        val candidate: String? = null,
        val person_id: String? = null,
        val office: String? = null,
        val office_gov_id: String? = null,
        val election: String? = null,
        val contribution_amount: Double? = null,
        val contribution_dates: List<String>? = null,
        val contract_ids_or_descriptions: List<String>? = null,
        val record_ids: List<String>? = null,
        val contract_source_urls: List<String>? = null,
        val contract_government: String? = null,
        val contract_gov_id: String? = null,
        /** Every government that paid the company (one row per gift, so a gift is counted once). */
        val contract_governments: List<String>? = null,
        val contract_gov_ids: List<String>? = null,
        val match_confidence: String? = null,
        val note: String? = null,
        val campaign_report_url: String? = null,
        val same_government_as_office: Boolean? = null,
    ) {
        val id: String get() = listOfNotNull(contributor, candidate, election, (record_ids ?: emptyList()).joinToString(",")).joinToString("|")
    }
}

/** The Money Map page's data: business donors, the officials they gave to, their contracts and the votes on them. */
@Serializable
data class MoneyMap(
    val officials: List<Official> = emptyList(),
    val donors: List<Donor> = emptyList(),
    val gifts: List<Gift> = emptyList(),
    val contracts: List<Contract> = emptyList(),
    val vgroups: List<VoteGroup> = emptyList(),
    val govs: Map<String, String>? = null,
    val as_of: String? = null,
) {
    @Serializable
    data class Official(val id: Int = 0, val n: String = "", val off: String? = null, val g: String = "", val raised: Double? = null, val ind: Double? = null, val indn: Int? = null, val url: String? = null)

    @Serializable
    data class Donor(val id: Int = 0, val n: String = "", val t: String? = null, val vp: String? = null, val k: Boolean? = null, val tot: Double? = null) {
        val holdsContracts: Boolean get() = k ?: false
    }

    @Serializable data class Gift(val d: Int = 0, val o: Int = 0, val a: Double = 0.0, val same: Boolean? = null, val dates: List<String>? = null)
    @Serializable data class Contract(val d: Int = 0, val g: String = "", val a: Double? = null, val items: List<String>? = null, val urls: List<String>? = null, val ent: String? = null)

    @Serializable
    data class VoteGroup(
        val d: Int = 0, val g: String = "", val date: String = "", val h: String? = null, val amount: Double? = null,
        val outcome: String? = null, val tally: String? = null, val consent: Boolean? = null, val url: String? = null,
        val roll: List<Member> = emptyList(),
    ) {
        @Serializable data class Member(val n: String = "", val vote: String? = null, val o: Int? = null, val gift: Double? = null, val `when`: String? = null)
        val id: String get() = "$d|$date|${h ?: ""}"
    }

    fun donor(id: Int): Donor? = donors.firstOrNull { it.id == id }
    fun official(id: Int): Official? = officials.firstOrNull { it.id == id }
    fun giftsToOfficial(id: Int): List<Gift> = gifts.filter { it.o == id }.sortedByDescending { it.a }
    fun giftsFromDonor(id: Int): List<Gift> = gifts.filter { it.d == id }.sortedByDescending { it.a }
    fun contractsForDonor(id: Int): List<Contract> = contracts.filter { it.d == id }

    data class Heat(val donors: List<Donor>, val govs: List<String>, val cells: Map<Int, Map<String, Double>>)

    /** Total business giving to each government's officials, per donor: the heat map's cells. */
    fun heat(topDonors: Int = 15): Heat {
        val cells = HashMap<Int, HashMap<String, Double>>()
        for (g in gifts) {
            val o = official(g.o) ?: continue
            val m = cells.getOrPut(g.d) { HashMap() }
            m[o.g] = (m[o.g] ?: 0.0) + g.a
        }
        val top = donors.filter { cells[it.id] != null }
            .sortedByDescending { cells[it.id]?.values?.sum() ?: 0.0 }
            .take(topDonors)
        val govs = officials.map { it.g }.toSet().sortedBy { Governments.orderIndex(it) }
        return Heat(top, govs, cells)
    }
}

/** Decodes an app data file. */
suspend fun <T> BayCountyClient.appData(name: String, serializer: KSerializer<T>): Pair<T, BayCountyClient.Freshness> {
    val r = get("/data/app/$name")
    return BCJson.decodeFromString(serializer, r.data.decodeToString()) to r.freshness
}

/** The People list's filter groups, the same chips as the site's /people page. */
enum class PeopleKind(val key: String, val label: String) {
    EVERYONE("everyone", "Everyone"),
    ELECTED("elected", "Elected"),
    CANDIDATE("candidate", "2026 candidates"),
    STAFF("staff", "Department leaders"),
    PAST("past", "Past candidates");

    fun includes(p: PeopleDirectory.Person): Boolean = this == EVERYONE || (p.kinds ?: listOf("elected")).contains(key)
}
