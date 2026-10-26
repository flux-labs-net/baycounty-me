package me.baycounty.kit

import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonObject
import java.time.Instant
import java.time.ZoneOffset
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Everything My Address shows for one address. Built by [AddressReport.load], which runs every lookup at once. */
data class AddressReport(
    val match: AddressMatch,
    val parcel: GISClient.Feature?,
    /** The 2026 roll's [school taxable, non-school taxable, homestead, additional homestead, other exemptions]. */
    val exemptions: List<Double>?,
    /** Flat fees on the FY2026 tax bill: (levy code, dollars). null = couldn't load. */
    val fees: List<Pair<String, Double>>?,
    val cityName: String?,
    val cra: GISClient.Feature?,
    val craChecked: Boolean,
    val commission: GISClient.Feature?,
    val cityCouncil: GISClient.Feature?,
    val schoolBoard: GISClient.Feature?,
    val floridaHouse: GISClient.Feature?,
    val floridaSenate: GISClient.Feature?,
    val usHouse: GISClient.Feature?,
    val elementary: String?,
    val middle: String?,
    val high: String?,
    val flood: GISClient.Flood?,
    val floodChecked: Boolean,
    val evacuationZone: String?,
    val mosquito: GISClient.Feature?,
    val touristTaxArea: String?,
    val fireStation: Pair<GISClient.Feature, Double>?,
    val library: Pair<GISClient.Feature, Double>?,
    val park: Pair<GISClient.Feature, Double>?,
    val development: Development?,
) {
    val govKey: String get() = govKey(cityName)

    data class TaxParts(
        val homestead: Boolean, val assessed: Double, val just: Double, val exempt: Double,
        val schoolTaxable: Double, val otherTaxable: Double, val homesteadAmount: Double,
        val additionalHomestead: Double, val otherExemptions: Double, val fromRoll: Boolean, val fullyExempt: Boolean,
    )

    data class TaxEstimate(
        val districtID: String, val districtLabel: String, val mills: Double,
        /** The tax district came from the parcel record (not inferred from the city on the map). */
        val exact: Boolean, val parts: TaxParts, val lines: List<TaxCalculator.Line>,
    ) {
        val total: Double get() = lines.sumOf { it.amount }
        fun byGroup(groups: List<String>): List<TaxCalculator.GroupAmount> =
            groups.map { g -> TaxCalculator.GroupAmount(g, lines.filter { it.group == g }.sumOf { it.amount }) }.filter { it.amount > 0.5 }
        val cityName: String? get() = lines.firstOrNull { it.group == "city" }?.name
    }

    fun taxEstimate(m: AddressModel): TaxEstimate? {
        val p = parcel ?: return null
        val code = (p.s("DTAXDIST") ?: "").trim()
        var id = m.taxdist[code]
        val exact = id != null
        if (id == null) id = cityName?.takeIf { m.districts[it] != null } ?: "unincorporated"
        val d = m.districts[id] ?: return null
        val t = taxParts(p, exemptions, m.second2026)
        val lines = d.stack.mapNotNull { aid ->
            val a = m.auth[aid] ?: return@mapNotNull null
            if (a.m <= 0) return@mapNotNull null
            val base = if (a.school) t.schoolTaxable else t.otherTaxable
            TaxCalculator.Line(aid, a.n, a.g, a.m, base, base / 1000 * a.m)
        }
        return TaxEstimate(id, d.label, d.total, exact, t, lines)
    }

    /** Amendment 3 savings for a homestead: (savings, owes nothing outside school tax). */
    fun amendment3Savings(m: AddressModel): Pair<Double, Boolean>? {
        val e = taxEstimate(m) ?: return null
        if (!e.parts.homestead) return null
        val d = m.districts[e.districtID] ?: return null
        val nonM = d.stack.mapNotNull { m.auth[it] }.filter { !it.school }.sumOf { it.m }
        val after = maxOf(0.0, e.parts.assessed - 250_000 - e.parts.otherExemptions)
        return (e.parts.otherTaxable - after) / 1000 * nonM to (after == 0.0)
    }

    /** Florida DOR land-use codes where someone could live and claim a homestead. */
    val isResidential: Boolean get() = Regex("^0[12458]").containsMatchIn(parcel?.s("DORAPPCODE") ?: "")

    data class Development(
        val zoning: String?, val futureLandUse: String?, val projects: List<Project>, val rezonings: List<Rezoning>,
        val conditionalUses: List<String>, val failed: Boolean,
    ) {
        data class Project(
            val name: String, val detail: String?, val status: String?, val `when`: String?, val address: String?,
            val miles: Double?, val source: String, val time: Double,
        ) { val id: String get() = "$source|$name|$time" }

        data class Rezoning(val ordinance: String, val time: Double, val changes: List<String>) { val id: String get() = ordinance }
    }

    data class MemberMatch(val name: String, val yes: Int, val no: Int)

    companion object {
        fun govKey(cityName: String?): String {
            val c = cityName ?: return "county"
            return Governments.names.entries.firstOrNull { it.value == c }?.key ?: "county"
        }

        fun taxParts(p: GISClient.Feature, ex: List<Double>?, second2026: Double): TaxParts {
            val assessed = p.n("VASTOTAL") ?: 0.0; val just = p.n("VASJUST") ?: 0.0
            if (ex != null && ex.size >= 5) {
                val (tsd, tnsd, h1, h2, oth) = ex
                val exempt = h1 + h2 + oth
                return TaxParts(h1 > 0, assessed, just, exempt, tsd, tnsd, h1, h2, oth, true, tsd == 0.0 && tnsd == 0.0 && exempt > 0)
            }
            val codes = p.s("DEXEMPTS") ?: ""
            val hx = Regex("\\bHX\\b").containsMatchIn(codes)
            val exempt = p.n("VASEXEMPT") ?: 0.0; val taxable = p.n("VASTAXABLE") ?: 0.0
            val second = if (hx) minOf(maxOf(assessed - 50_000, 0.0), second2026) else 0.0
            val other = if (hx) maxOf(0.0, exempt - minOf(assessed, 25_000.0) - second) else exempt
            val fullEx = taxable == 0.0 && Regex("\\b(13|14|VT|96)\\b").containsMatchIn(codes)
            val school = if (fullEx) 0.0 else if (hx) maxOf(0.0, taxable + second) else maxOf(0.0, just - exempt)
            return TaxParts(hx, assessed, just, exempt, school, taxable, if (hx) minOf(assessed, 25_000.0) else 0.0, second, other, false, fullEx)
        }

        internal fun normName(s: String): List<String> =
            s.lowercase().replace(Regex("[.,]"), " ").split(" ").filter { it.length > 1 && it !in setOf("jr", "sr", "ii", "iii", "iv") }

        /** A representative's name from GIS matched to the name in recorded votes (one clear match or none). */
        fun matchMember(rep: String, gov: String, model: AddressModel): MemberMatch? {
            val a = normName(rep)
            if (a.size < 2) return null
            val hits = (model.members[gov] ?: emptyList()).filter { row ->
                val n = row.firstOrNull()?.stringValue ?: return@filter false
                val b = normName(n)
                b.size > 1 && b.last() == a.last() && (b[0].startsWith(a[0]) || a[0].startsWith(b[0]))
            }
            if (hits.size != 1) return null
            val n = hits[0].firstOrNull()?.stringValue ?: return null
            return MemberMatch(n, hits[0].getOrNull(1)?.doubleValue?.toInt() ?: 0, hits[0].getOrNull(2)?.doubleValue?.toInt() ?: 0)
        }

        /** One parcel's entry from a split per-parcel file. null = couldn't load; Loaded(null) = parcel not in the file. */
        class Loaded(val value: JsonElement?)

        internal suspend fun shardRaw(client: BayCountyClient, kind: String, pid: String?, m: AddressModel): Loaded? {
            if (pid == null) return null
            val n = m.shards[kind] ?: return null
            val r = runCatching { client.get("/data/$kind/${parcelShard(pid, n)}.json") }.getOrNull() ?: return null
            val obj = runCatching { BCJson.parseToJsonElement(r.data.decodeToString()).jsonObject }.getOrNull() ?: return null
            return Loaded(obj[pid]?.takeIf { it !is JsonNull })
        }

        suspend fun load(match: AddressMatch, gis: GISClient = GISClient(), client: BayCountyClient, model: AddressModel): AddressReport = coroutineScope {
            val pt = match.point
            val parcelQ = async {
                val r = match.renum
                if (!r.isNullOrEmpty()) runCatching { gis.query(GISClient.COUNTY, "Admin_A12/MapServer/6", mapOf("where" to "A1RENUM='${r.replace("'", "")}'")) }.getOrNull()?.firstOrNull()
                else gis.atPoint("Admin_A12/MapServer/6", pt)?.firstOrNull()
            }
            val cityQ = async { gis.atPoint("Admin_A12/MapServer/26", pt) }
            val craQ = async { gis.atPoint("Admin_A12/MapServer/27", pt) }
            val commQ = async { gis.atPoint("Admin_A12/MapServer/28", pt) }
            val localQ = async { gis.atPoint("Admin_A12/MapServer/30", pt) }
            val mosqQ = async { gis.atPoint("Admin_A12/MapServer/34", pt) }
            val floodQ = async { gis.flood(pt) }
            val evacQ = async { gis.atPoint("Admin_A12/MapServer/80", pt) }
            val tdcQ = async { gis.atPoint("Admin_A12/MapServer/84", pt) }
            val sbQ = async { gis.atPoint("ElectionAdministration/MapServer/2", pt) }
            val houseQ = async { gis.atPoint("ElectionAdministration/MapServer/3", pt) }
            val senateQ = async { gis.atPoint("ElectionAdministration/MapServer/4", pt) }
            val ushQ = async { gis.atPoint("ElectionAdministration/MapServer/5", pt) }
            val esQ = async { gis.atPoint("SchoolAttendanceZones/MapServer/0", pt) }
            val msQ = async { gis.atPoint("SchoolAttendanceZones/MapServer/1", pt) }
            val hsQ = async { gis.atPoint("SchoolAttendanceZones/MapServer/2", pt) }
            val fireQ = async { gis.nearest(42, pt) }
            val libQ = async { gis.nearest(39, pt) }
            val parkQ = async { gis.nearest(41, pt) }

            val parcel = parcelQ.await()
            val pid = parcel?.s("A1RENUM")
            val exQ = async { shardRaw(client, "ex", pid, model)?.value?.arrayValue?.mapNotNull { it.doubleValue } }
            val navQ = async { shardRaw(client, "nav", pid, model) }

            val city = cityQ.await()
            val cityName = city?.mapNotNull { it.s("NAME") }?.firstOrNull { !it.lowercase().contains("unincorp") }
            val devQ = async { development(gis, pt, cityName) }

            val fees = navQ.await()?.let { got ->
                (got.value?.arrayValue ?: emptyList()).mapNotNull { item ->
                    val a = item.arrayValue ?: return@mapNotNull null
                    if (a.size < 2) return@mapNotNull null
                    val c = a[0].stringValue ?: return@mapNotNull null
                    val v = a[1].doubleValue ?: return@mapNotNull null
                    c to v
                }
            }
            val flood = floodQ.await()
            val cra = craQ.await()
            AddressReport(
                match, parcel, exQ.await(), fees, cityName, cra?.firstOrNull(), cra != null,
                commQ.await()?.firstOrNull(), localQ.await()?.firstOrNull(), sbQ.await()?.firstOrNull(),
                houseQ.await()?.firstOrNull(), senateQ.await()?.firstOrNull(), ushQ.await()?.firstOrNull(),
                esQ.await()?.firstOrNull()?.s("NAME"), msQ.await()?.firstOrNull()?.s("NAME"), hsQ.await()?.firstOrNull()?.s("NAME"),
                flood, flood != null, evacQ.await()?.firstOrNull()?.s("EZONE"), mosqQ.await()?.firstOrNull(), tdcQ.await()?.firstOrNull()?.s("ID"),
                fireQ.await(), libQ.await(), parkQ.await(), devQ.await(),
            )
        }

        private val jurisdictions = mapOf(
            "BC" to "county code", "LH" to "Lynn Haven code", "PC" to "Panama City code", "PCB" to "Panama City Beach code", "CW" to "Callaway code",
            "SF" to "Springfield code", "SP" to "Springfield code", "PK" to "Parker code", "MB" to "Mexico Beach code",
        )

        internal fun codeLabel(v: String?): String {
            var s = (v ?: "").replace(Regex("^v\\s+", RegexOption.IGNORE_CASE), "")
            Regex("\\s*\\(([A-Z]+)\\)\\s*$").find(s)?.let { m ->
                jurisdictions[m.groupValues[1]]?.let { name -> s = s.substring(0, m.range.first) + " ($name)" }
            }
            return s.trim()
        }

        internal fun bareCode(v: String?): String = codeLabel(v).replace(Regex(" \\([^)]*code\\)$"), "")

        /** ArcGIS dates come as epoch milliseconds or ISO strings. */
        internal fun time(v: JsonElement?): Double {
            val p = v as? JsonPrimitive ?: return 0.0
            if (!p.isString) p.doubleValue?.let { return it }
            val s = p.stringValue ?: return 0.0
            return Dates.parse(s.take(10))?.toEpochMilli()?.toDouble() ?: 0.0
        }

        private val monthYearF = DateTimeFormatter.ofPattern("MMM yyyy", Locale.US).withZone(ZoneOffset.UTC)

        internal fun monthYear(ms: Double): String {
            if (ms <= 0) return ""
            val d = Instant.ofEpochMilli(ms.toLong())
            return if (ZonedDateTime.ofInstant(d, ZoneOffset.UTC).year < 1990) "" else monthYearF.format(d)
        }

        private class RZ(val z: String, val zc: String?, val o: String, val t: Double, val prev: String)

        internal suspend fun development(gis: GISClient, pt: GeoPoint, cityName: String?): Development = coroutineScope {
            val half = mapOf("distance" to "0.5", "units" to "esriSRUnit_StatuteMile")
            val fiveYears = Instant.now().minusSeconds((5 * 365.25 * 86400).toLong())
            val since = Dates.dayKey(fiveYears)
            val inPC = cityName == "Panama City"; val inPCB = cityName == "Panama City Beach"
            suspend fun q(base: String, path: String, p: Map<String, String>): List<GISClient.Feature>? {
                val params = mutableMapOf(
                    "geometry" to "${pt.x},${pt.y}", "geometryType" to "esriGeometryPoint", "inSR" to "4326", "outSR" to "4326",
                    "spatialRel" to "esriSpatialRelIntersects",
                )
                params.putAll(p)
                return runCatching { gis.query(base, path, params) }.getOrNull()
            }
            val c = GISClient.COUNTY; val pc = GISClient.PANAMA_CITY; val ago = GISClient.AGOL
            val zon = async { q(c, "LandUsePlanning/MapServer/1", mapOf("outFields" to "ZONING,Label,ORD_NUM,ORD_DATE")) }
            val flu = async { q(c, "LandUsePlanning/MapServer/2", mapOf("outFields" to "FLU_CODE,Label,ORD_NUM,ORD_DATE")) }
            val pcz = async { if (inPC) q(pc, "Zoning_CPC/FeatureServer/0", mapOf("outFields" to "LABEL,ZONE_TYPE,ordinance,ordinancedate")) else null }
            val pcf = async { if (inPC) q(pc, "FutureLandUse_CPC/FeatureServer/0", mapOf("outFields" to "LANDUSE")) else null }
            val pcbf = async { if (inPCB) q(c, "PanamaCityBeach/PanamaCityBeachPublic/MapServer/8", mapOf("outFields" to "FLU_CODE,Label")) else null }
            val dos = async { q(c, "Departmental/Planning/MapServer/18", half + mapOf("outFields" to "NAME,NUMBER,DESCRIPTION,SIZE,LOCATION,APPLICATION_RECEIVED,DO_ISSUED,TYPE", "returnGeometry" to "true")) }
            val lhd = async { q(ago, "LH_Development_Planning_Projects/FeatureServer/0", half + mapOf("outFields" to "Project,Number_of_Units,Acres,Address,DO_Status,City_Commission_Approval_Date,DO_Expires", "returnGeometry" to "true")) }
            val pcbd = async { q(ago, "PCB_Planning_Projects_Editing/FeatureServer/0", half + mapOf("outFields" to "TYPE,Name,SIZE,DEVTYPE,DateApplied,DateIssued", "returnGeometry" to "true")) }
            val rez = async { q(c, "LandUsePlanning/MapServer/1", half + mapOf("where" to "ORD_DATE >= DATE '$since'", "outFields" to "ZONING,Label,ORD_NUM,ORD_DATE,COMMENTS", "orderByFields" to "ORD_DATE DESC")) }
            val pcr = async { if (inPC) q(pc, "Zoning_CPC/FeatureServer/0", half + mapOf("where" to "ordinancedate >= DATE '$since'", "outFields" to "LABEL,ZONE_TYPE,ordinance,ordinancedate,previouszone")) else null }
            val cond = async { q(c, "Departmental/Planning/MapServer/17", mapOf("distance" to "0.25", "units" to "esriSRUnit_StatuteMile", "outFields" to "REF__NUM,TYPE,CONDITION,CONDITION2,CONDITION3", "returnGeometry" to "true")) }

            val zonR = zon.await(); val fluR = flu.await(); val dosR = dos.await()
            val pczR = pcz.await(); val pcfR = pcf.await(); val pcbfR = pcbf.await()
            val zoning: String? = pczR?.firstOrNull()?.let { z -> (z.s("LABEL") ?: "") + (z.s("ZONE_TYPE")?.let { " ($it)" } ?: "") }
                ?: zonR?.firstOrNull()?.let { z -> if (z.s("ZONING") == "See FLU") "Set by the future land use map" else codeLabel(z.s("Label") ?: z.s("ZONING")) }
            val fluText = pcfR?.firstOrNull()?.s("LANDUSE")
                ?: codeLabel(pcbfR?.firstOrNull()?.s("Label") ?: fluR?.firstOrNull()?.s("Label") ?: fluR?.firstOrNull()?.s("FLU_CODE")).ifEmpty { null }

            val proj = mutableListOf<Development.Project>()
            fun dist(f: GISClient.Feature): Double? = f.geometry?.let { pt.miles(it) }
            for (d in dosR ?: emptyList()) {
                val issued = time(d.attributes["DO_ISSUED"]); val applied = time(d.attributes["APPLICATION_RECEIVED"])
                proj.add(Development.Project(d.s("NAME") ?: "Project", d.s("DESCRIPTION"), d.s("TYPE"),
                    if (issued > 0) "issued " + monthYear(issued) else if (applied > 0) "applied " + monthYear(applied) else null,
                    d.s("LOCATION"), dist(d), "Bay County", if (issued > 0) issued else applied))
            }
            for (d in lhd.await() ?: emptyList()) {
                val t = time(d.attributes["City_Commission_Approval_Date"])
                val units = d.s("Number_of_Units")?.let { if (it == "N/A") null else "$it units" }
                val acres = d.s("Acres")?.let { "$it acres" }
                proj.add(Development.Project(d.s("Project") ?: "Project", listOfNotNull(units, acres).joinToString(", "), d.s("DO_Status"),
                    if (t > 0) "approved " + monthYear(t) else null, d.s("Address"), dist(d), "Lynn Haven", t))
            }
            for (d in pcbd.await() ?: emptyList()) {
                val issued = time(d.attributes["DateIssued"]); val applied = time(d.attributes["DateApplied"])
                proj.add(Development.Project(d.s("Name") ?: "Project", d.s("TYPE"), d.s("DEVTYPE"),
                    if (issued > 0) "issued " + monthYear(issued) else if (applied > 0) "applied " + monthYear(applied) else null,
                    null, dist(d), "Panama City Beach", if (issued > 0) issued else applied))
            }
            val cutoff = fiveYears.toEpochMilli().toDouble()
            val recent = proj.filter { it.time == 0.0 || it.time >= cutoff }.sortedByDescending { it.time }.take(8)

            var rz = (rez.await() ?: emptyList()).map { r ->
                RZ(bareCode(r.s("Label") ?: r.s("ZONING")), null, r.s("ORD_NUM") ?: "", time(r.attributes["ORD_DATE"]),
                    bareCode((r.s("COMMENTS") ?: "").replace(Regex("^pre\\.?\\s*", RegexOption.IGNORE_CASE), "")))
            } + (pcr.await() ?: emptyList()).map { r ->
                RZ(bareCode(r.s("LABEL")), bareCode(r.s("LABEL")), r.s("ordinance") ?: "", time(r.attributes["ordinancedate"]), bareCode(r.s("previouszone")))
            }
            val now = System.currentTimeMillis().toDouble()
            rz = rz.filter { r ->
                r.t > 0 && r.t <= now + 86_400_000 && (r.prev.isEmpty() || r.prev.split(" (")[0] != (r.zc ?: r.z).split(" (")[0])
            }
            val byOrd = LinkedHashMap<String, Development.Rezoning>()
            for (r in rz) {
                val change = (if (r.prev.isEmpty()) "to " else r.prev + " → ") + r.z
                val g = byOrd[r.o]
                if (g != null) { if (change !in g.changes) byOrd[r.o] = g.copy(changes = g.changes + change) }
                else byOrd[r.o] = Development.Rezoning(r.o, r.t, listOf(change))
            }
            val rezonings = byOrd.values.sortedByDescending { it.time }.take(5)
            val cu = (cond.await() ?: emptyList()).mapNotNull { cf ->
                val t = cf.s("TYPE") ?: return@mapNotNull null
                val detail = listOfNotNull(cf.s("CONDITION"), cf.s("CONDITION2"), cf.s("CONDITION3")).joinToString(" ")
                listOfNotNull(t, detail, cf.s("REF__NUM")?.let { "($it)" }).filter { it.isNotEmpty() }.joinToString(" ")
            }.take(4)
            Development(zoning, fluText, recent, rezonings, cu, zonR == null && fluR == null && dosR == null)
        }
    }
}

/** Flood zone in plain words (address.js renderSafe). */
object FloodText {
    fun describe(f: GISClient.Flood?): Pair<String, String?> {
        if (f == null) return "Couldn't check right now" to null
        val z = f.zone ?: return (if (f.source == GISClient.Flood.Source.COUNTY) "Outside the high-risk areas on Bay County's copy of the flood map" else "Not on FEMA's flood map here") to null
        val zone = z.s("FLD_ZONE") ?: ""; val bfe = z.n("STATIC_BFE") ?: 0.0
        val bfeText = if (bfe > 0) " · base flood elevation ${Format.number(bfe)} ft" + (z.s("V_DATUM")?.let { " ($it)" } ?: "") else ""
        var head: String
        if (z.s("SFHA_TF") == "T" || zone.startsWith("A") || zone.startsWith("V")) {
            head = "Zone $zone · FEMA high-risk area" + (if (zone.startsWith("V")) ", coastal waves" else "") + bfeText
            z.n("DEPTH")?.takeIf { it > 0 }?.let { head += " · flood depth ${Format.number(it)} ft" }
        } else if (zone == "X" && (z.s("ZONE_SUBTY") ?: "").contains("0.2")) {
            head = "Zone X (shaded) · moderate risk, outside the high-risk area (0.2% annual chance flood)"
        } else if (zone == "X") {
            head = "Zone X · minimal flood hazard on FEMA's map"
        } else if (zone == "D") {
            head = "Zone D · flood risk not determined"
        } else head = "Zone $zone$bfeText"
        val detail = mutableListOf<String>()
        f.panel?.s("FIRM_PAN")?.let { p ->
            var line = "FIRM panel $p" + (f.panel.n("EFF_DATE")?.let { ", effective " + day(it) } ?: "")
            f.lomr?.s("CASE_NO")?.let { c -> line += " · map revision (LOMR) $c" + (f.lomr.n("EFF_DATE")?.let { ", " + day(it) } ?: "") }
            detail.add(line)
        }
        if (f.source == GISClient.Flood.Source.COUNTY) {
            detail.add("FEMA's live map didn't respond, so this is Bay County's older copy, which predates the October 2024 maps.")
        }
        return head to detail.joinToString("\n").ifEmpty { null }
    }

    private val dayF = DateTimeFormatter.ofPattern("MMM d, yyyy", Locale.US).withZone(ZoneOffset.UTC)
    internal fun day(ms: Double): String = dayF.format(Instant.ofEpochMilli(ms.toLong()))
}

/** CRA spending and sales tax projects near an address (address.js nearHtml). */
data class NearbyMoney(val cra: List<CRAItem>, val projects: List<Project>) {
    data class CRAItem(val id: Int, val amount: Double?, val purpose: String, val status: String, val `when`: String?, val miles: Double, val url: String?, val cra: String)
    data class Project(val id: String, val name: String, val cost: Double?, val status: String, val percent: Double?, val government: String?, val miles: Double)

    val craTotal: Double get() = cra.filter { it.status == "Spent" || it.status == "Committed" }.mapNotNull { it.amount }.sum()

    companion object {
        suspend fun load(pt: GeoPoint, client: BayCountyClient): NearbyMoney = coroutineScope {
            val a = async { client.get("/data/cra-pay-1.json") }
            val b = async { client.get("/data/cra-pay-2.json") }
            val s = async { client.get("/data/surtax-projects.json") }
            val pays = Row.decodeList(a.await().data) + Row.decodeList(b.await().data)
            val projs = Row.decodeList(s.await().data)
            val cra = pays.mapNotNull { p ->
                if (p.bool("count") != true || p.string("placed") != "site") return@mapNotNull null
                val lat = p.number("lat") ?: return@mapNotNull null
                val lng = p.number("lng") ?: return@mapNotNull null
                val mi = pt.miles(GeoPoint(lng, lat))
                if (mi > 0.5) return@mapNotNull null
                CRAItem((p.number("id") ?: p.id.toDouble()).toInt(), p.number("amount"), p.first(listOf("purpose", "payee")) ?: "",
                    p.string("status") ?: "", p.string("when"), mi, p.url("url"), p.string("cra") ?: "")
            }.sortedBy { it.miles }
            val near = projs.mapNotNull { p ->
                val x = p.number("x") ?: return@mapNotNull null
                val y = p.number("yy") ?: return@mapNotNull null
                val mi = pt.miles(GeoPoint(x, y))
                if (mi > 1) return@mapNotNull null
                Project(p.string("id") ?: "${p.id}", p.string("n") ?: "Project", p.number("k"), p.string("s") ?: "unknown", p.number("p"), p.string("g"), mi)
            }.sortedBy { it.miles }
            NearbyMoney(cra, near)
        }

        fun statusLabel(s: String): String = mapOf("completed" to "Completed", "in_progress" to "In progress", "not_started" to "Not started")[s] ?: "Status unknown"
    }
}
