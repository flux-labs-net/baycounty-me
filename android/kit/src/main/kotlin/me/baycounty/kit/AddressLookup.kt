package me.baycounty.kit

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import kotlin.math.asin
import kotlin.math.cos
import kotlin.math.pow
import kotlin.math.sin
import kotlin.math.sqrt

/**
 * My Address (site/address.js): find a Bay County address on the county's public GIS server and look up
 * everything that applies to it. Lookups go straight to Bay County's and FEMA's map servers.
 */
object AddressParser {
    private val types: Map<String, List<String>> = run {
        val pairs = listOf(
            "DRIVE" to "DR", "DRV" to "DR", "DR" to "DR", "STREET" to "ST", "STR" to "ST", "ST" to "ST", "AVENUE" to "AVE", "AV" to "AVE", "AVN" to "AVE", "AVE" to "AVE",
            "ROAD" to "RD", "RD" to "RD", "BOULEVARD" to "BLVD", "BLV" to "BLVD", "BLVD" to "BLVD", "LANE" to "LN", "LN" to "LN", "COURT" to "CT", "CRT" to "CT", "CT" to "CT", "COURTS" to "CTS",
            "CIRCLE" to "CIR", "CIRC" to "CIR", "CIR" to "CIR", "PLACE" to "PL", "PL" to "PL", "TERRACE" to "TER", "TERR" to "TER", "TER" to "TER", "TRAIL" to "TRL", "TR" to "TRL", "TRL" to "TRL",
            "PARKWAY" to "PKWY", "PKY" to "PKWY", "PKWY" to "PKWY", "PLAZA" to "PLZ", "PLZ" to "PLZ", "POINT" to "PT", "PT" to "PT", "CROSSING" to "XING", "XING" to "XING",
            "LANDING" to "LNDG", "LNDG" to "LNDG", "MANOR" to "MNR", "MNR" to "MNR", "SQUARE" to "SQ", "SQ" to "SQ", "ALLEY" to "ALY", "ALY" to "ALY", "BEND" to "BND", "BND" to "BND",
            "GARDENS" to "GDNS", "GDNS" to "GDNS", "KNOLL" to "KNL", "KNL" to "KNL", "TRACE" to "TRCE", "TRCE" to "TRCE", "CORNER" to "COR", "COR" to "COR",
            "LOOP" to "LOOP", "RUN" to "RUN", "PATH" to "PATH", "PASS" to "PASS", "WAY" to "WAY", "TURN" to "TURN", "ISLE" to "ISLE",
        )
        val t = pairs.associate { it.first to listOf(it.second) }.toMutableMap()
        t["COVE"] = listOf("COVE", "CV"); t["CV"] = listOf("COVE", "CV")
        t
    }
    private val dirs = mapOf("NORTH" to "N", "SOUTH" to "S", "EAST" to "E", "WEST" to "W", "NORTHWEST" to "NW", "N" to "N", "S" to "S", "E" to "E", "W" to "W", "NW" to "NW")
    private val ordinals = mapOf(
        "FIRST" to "1ST", "SECOND" to "2ND", "THIRD" to "3RD", "FOURTH" to "4TH", "FIFTH" to "5TH", "SIXTH" to "6TH", "SEVENTH" to "7TH", "EIGHTH" to "8TH", "NINTH" to "9TH", "TENTH" to "10TH",
        "ELEVENTH" to "11TH", "TWELFTH" to "12TH", "THIRTEENTH" to "13TH", "FOURTEENTH" to "14TH", "FIFTEENTH" to "15TH", "SIXTEENTH" to "16TH", "SEVENTEENTH" to "17TH", "EIGHTEENTH" to "18TH", "NINETEENTH" to "19TH", "TWENTIETH" to "20TH",
    )
    private val places = listOf("PANAMA CITY BEACH", "PANAMA CITY", "LYNN HAVEN", "CALLAWAY", "SPRINGFIELD", "PARKER", "MEXICO BEACH", "SOUTHPORT", "FOUNTAIN", "YOUNGSTOWN", "TYNDALL AFB", "BAYOU GEORGE", "BAY COUNTY")

    data class Token(val alts: List<String>, val kind: Kind, val word: Boolean = false, val partial: Boolean = false) {
        enum class Kind { NAME, TYPE, DIR }
    }

    data class Parsed(val house: String, val unit: String, val place: String, val tokens: List<Token>)

    private fun re(pattern: String, s: String, template: String) = Regex(pattern).replace(s, template)

    fun parse(raw: String): Parsed? {
        var s = raw.uppercase()
        s = re("[.,'\"%_\\\\]", s, " ")
        s = re("\\s+", s, " ").trim()
        s = re("\\b(FL|FLORIDA)\\b", s, " ")
        s = re("\\b\\d{5}(-\\d{4})?\\s*$", s, " ")
        s = re("\\s+", s, " ").trim()
        var place = ""
        for (p in places) if (s.endsWith(" $p")) { place = p; s = s.dropLast(p.length + 1).trim(); break }
        var unit = ""
        val um = Regex("\\s(?:#\\s*|(?:APT|APARTMENT|UNIT|STE|SUITE|BLDG|LOT|RM|SPC|TRLR)\\s+#?\\s*)([A-Z0-9-]+)\\s*$").find(s)
        if (um != null) {
            unit = um.value.replace("#", " ").trim().split(" ").last()
            s = s.substring(0, um.range.first).trim()
        }
        val hm = Regex("^\\d+").find(s) ?: return null
        val house = hm.value
        var rest = s.substring(hm.range.last + 1).trim()
        if (rest.length >= 2 && rest[0].isLetter() && rest[1] == ' ') rest = rest.substring(2)
        var joined = rest
        joined = re("\\b(?:US|U S|SR|S R|STATE ROAD|STATE RD|CR|C R|COUNTY ROAD|COUNTY RD)\\s*(?:HWY|HIGHWAY)?\\s*(\\d+[A-Z]?)\\b", joined, "HIGHWAY $1")
        joined = re("\\bHWY\\b", joined, "HIGHWAY")
        joined = re("\\bMLK\\b", joined, "MARTIN LUTHER KING JR")
        joined = re("\\bJUNIOR\\b", joined, "JR")
        joined = re("\\bMOUNT\\b", joined, "MT")
        val w = joined.split(" ").filter { it.isNotEmpty() }
        val toks = mutableListOf<Token>()
        for ((i, t) in w.withIndex()) {
            val last = i == w.size - 1
            val o = ordinals[t]
            if (o != null) { toks.add(Token(listOf(o), Token.Kind.NAME)); continue }
            val d = dirs[t]
            if (d != null && (i == 0 || last)) { toks.add(Token(listOf(d), Token.Kind.DIR)); continue }
            if ((t == "ST" || t == "SAINT") && !last) { toks.add(Token(listOf("ST", "SAINT"), Token.Kind.NAME, word = true)); continue }
            val ty = types[t]
            if (ty != null && last && i > 0) { toks.add(Token(ty, Token.Kind.TYPE)); continue }
            toks.add(Token(listOf(t), Token.Kind.NAME, partial = last))
        }
        return Parsed(house, unit, place, toks)
    }

    private fun sq(s: String) = s.replace("'", "''")

    /** SQL where clause for Bay County's address point layer, keeping only some token kinds. */
    fun whereClause(a: Parsed, keep: List<Token.Kind>, unit: Boolean = true): String {
        val parts = mutableListOf("ADDRESS LIKE '${a.house} %'")
        for (t in a.tokens) {
            if (t.kind !in keep) continue
            val ors = t.alts.map { x ->
                if (t.kind == Token.Kind.NAME && !t.word) {
                    if (t.partial) "ADDRESS LIKE '% ${sq(x)}%'" else "(ADDRESS LIKE '% ${sq(x)} %' OR ADDRESS LIKE '% ${sq(x)}')"
                } else "(ADDRESS LIKE '% ${sq(x)} %' OR ADDRESS LIKE '% ${sq(x)}')"
            }
            parts.add("(" + ors.joinToString(" OR ") + ")")
        }
        if (unit && a.unit.isNotEmpty()) parts.add("(UNIT = '${sq(a.unit)}' OR UNIT LIKE '${sq(a.unit)}%')")
        return parts.joinToString(" AND ")
    }

    /** "1614 OHIO AVE" -> "1614 Ohio Ave"; keeps NE/NW/US/CR/SR in capitals. */
    fun titleCase(s: String): String = s.lowercase().split(" ").joinToString(" ") { w ->
        val up = w.uppercase()
        if (up in setOf("NE", "NW", "SE", "SW", "US", "CR", "SR")) up else w.capitalizeFirst()
    }
}

/** 32-bit FNV-1a, the same hash the site uses to split per-parcel files (addr_page.shard_key). */
fun parcelShard(pid: String, count: Int): String {
    var h = 0x811c9dc5.toInt()
    for (b in pid.toByteArray(Charsets.UTF_8)) h = (h xor (b.toInt() and 0xff)) * 0x01000193
    return "h${(h.toLong() and 0xffffffffL) % count}"
}

data class GeoPoint(val x: Double, val y: Double) {
    /** Great-circle distance in miles. */
    fun miles(b: GeoPoint): Double {
        val r = 3958.8; val t = Math.PI / 180
        val dLat = (b.y - y) * t; val dLon = (b.x - x) * t
        val h = sin(dLat / 2).pow(2) + cos(y * t) * cos(b.y * t) * sin(dLon / 2).pow(2)
        return 2 * r * asin(sqrt(h))
    }
}

/** One address point from Bay County's address layer. */
data class AddressMatch(val address: String, val unit: String?, val community: String?, val zip: String?, val renum: String?, val point: GeoPoint) {
    val id: String get() = address + (unit ?: "") + (zip ?: "")
    val display: String get() = AddressParser.titleCase(address) + (if (unit.isNullOrBlank()) "" else " #$unit")
    val subtitle: String get() = listOfNotNull(community, zip).filter { it.isNotEmpty() }.joinToString(" ")
}

/** A small GET helper for servers other than BayCounty.me. */
internal object Http {
    suspend fun get(url: String, timeoutMs: Int = 15000): ByteArray = withContext(Dispatchers.IO) {
        val c = URL(url).openConnection() as HttpURLConnection
        c.connectTimeout = timeoutMs; c.readTimeout = timeoutMs
        c.setRequestProperty("User-Agent", "BayCounty.me Android")
        try {
            val code = c.responseCode
            if (code != 200) throw IOException("HTTP $code")
            c.inputStream.use { it.readBytes() }
        } finally { c.disconnect() }
    }

    fun enc(s: String): String = URLEncoder.encode(s, "UTF-8").replace("+", "%20")
}

/** Bay County GIS and FEMA flood map queries (ArcGIS REST). */
class GISClient {
    data class Feature(val attributes: Map<String, JsonElement>, val geometry: GeoPoint?) {
        fun s(k: String): String? {
            val v = attributes[k] ?: return null
            if (v.isEmptyValue) return null
            return v.stringValue?.trim()
        }
        fun n(k: String): Double? = attributes[k]?.doubleValue
    }

    class GISError(m: String) : IOException("Bay County's map server didn't answer ($m).")

    suspend fun query(base: String, path: String, params: Map<String, String>, timeoutMs: Int = 15000): List<Feature> {
        val p = sortedMapOf("f" to "json", "returnGeometry" to "false", "outFields" to "*")
        p.putAll(params)
        val q = p.entries.joinToString("&") { "${it.key}=${Http.enc(it.value)}" }
        val bytes = try { Http.get("$base/$path/query?$q", timeoutMs) } catch (e: IOException) { throw GISError(e.message ?: "error") }
        val root = BCJson.parseToJsonElement(bytes.decodeToString()).jsonObject
        (root["error"] as? JsonObject)?.let { throw GISError(it["message"]?.stringValue ?: "error") }
        return (root["features"]?.arrayValue ?: emptyList()).map { f ->
            val o = f.jsonObject
            val g = o["geometry"] as? JsonObject
            val x = g?.get("x")?.doubleValue; val y = g?.get("y")?.doubleValue
            Feature((o["attributes"] as? JsonObject) ?: emptyMap(), if (x != null && y != null) GeoPoint(x, y) else null)
        }
    }

    internal suspend fun atPoint(path: String, pt: GeoPoint, base: String = COUNTY, extra: Map<String, String> = emptyMap()): List<Feature>? {
        val p = mutableMapOf("geometry" to pointJSON(pt), "geometryType" to "esriGeometryPoint", "inSR" to "4326", "spatialRel" to "esriSpatialRelIntersects")
        p.putAll(extra)
        return runCatching { query(base, path, p) }.getOrNull()
    }

    internal suspend fun nearest(layer: Int, pt: GeoPoint): Pair<Feature, Double>? {
        val p = mapOf(
            "geometry" to pointJSON(pt), "geometryType" to "esriGeometryPoint", "inSR" to "4326", "distance" to "10",
            "units" to "esriSRUnit_StatuteMile", "returnGeometry" to "true", "outSR" to "4326",
        )
        val fs = runCatching { query(COUNTY, "Admin_A12/MapServer/$layer", p) }.getOrNull() ?: return null
        return fs.mapNotNull { f -> f.geometry?.let { f to pt.miles(it) } }.minByOrNull { it.second }
    }

    data class SearchResult(val matches: List<AddressMatch>, val relaxed: Boolean)

    suspend fun search(text: String): SearchResult {
        val a = AddressParser.parse(text) ?: return SearchResult(emptyList(), false)
        if (a.tokens.isEmpty()) return SearchResult(emptyList(), false)
        val opts = mapOf("outFields" to "ADDRESS,UNIT,CMNTY,ZIP,RENUM", "returnGeometry" to "true", "outSR" to "4326", "resultRecordCount" to "25", "orderByFields" to "ADDRESS")
        var found: List<Feature> = emptyList()
        var relaxed = false
        for (keep in listOf(listOf(AddressParser.Token.Kind.NAME, AddressParser.Token.Kind.TYPE, AddressParser.Token.Kind.DIR), listOf(AddressParser.Token.Kind.NAME))) {
            found = query(COUNTY, "Admin_A12/MapServer/3", opts + ("where" to AddressParser.whereClause(a, keep)))
            if (found.isNotEmpty()) { relaxed = keep.size == 1 && a.tokens.any { it.kind != AddressParser.Token.Kind.NAME }; break }
        }
        if (found.isEmpty() && a.unit.isNotEmpty()) {
            found = query(COUNTY, "Admin_A12/MapServer/3", opts + ("where" to AddressParser.whereClause(a, listOf(AddressParser.Token.Kind.NAME), unit = false)))
            relaxed = found.isNotEmpty()
        }
        var matches = found.mapNotNull(::match)
        if (a.place.isNotEmpty()) matches = matches.sortedBy { if ((it.community ?: "").uppercase() == a.place) 0 else 1 }
        return SearchResult(matches.take(10), relaxed)
    }

    /** The address points nearest a location (for "Use my location"). */
    suspend fun addressesNear(pt: GeoPoint): List<AddressMatch> {
        val p = mapOf(
            "geometry" to pointJSON(pt), "geometryType" to "esriGeometryPoint", "inSR" to "4326", "distance" to "150", "units" to "esriSRUnit_Foot",
            "outFields" to "ADDRESS,UNIT,CMNTY,ZIP,RENUM", "returnGeometry" to "true", "outSR" to "4326", "resultRecordCount" to "40",
        )
        val seen = HashSet<String>()
        return query(COUNTY, "Admin_A12/MapServer/3", p).mapNotNull(::match)
            .sortedBy { pt.miles(it.point) }.filter { seen.add(it.address) }.take(8)
    }

    // Flood map

    private suspend fun femaAt(layer: Int, pt: GeoPoint, fields: String): List<Feature> = query(
        FEMA, "$layer",
        mapOf("geometry" to pointJSON(pt), "geometryType" to "esriGeometryPoint", "inSR" to "4326", "spatialRel" to "esriSpatialRelIntersects", "outFields" to fields),
    )

    data class Flood(val source: Source, val zone: Feature?, val panel: Feature?, val lomr: Feature?) {
        enum class Source { FEMA, COUNTY }
    }

    suspend fun flood(pt: GeoPoint): Flood? = try {
        coroutineScope {
            val fields = "FLD_ZONE,ZONE_SUBTY,SFHA_TF,STATIC_BFE,V_DATUM,DEPTH"
            val zonesQ = async { try { femaAt(28, pt, fields) } catch (e: IOException) { femaAt(28, pt, fields) } }
            val panelsQ = async { runCatching { femaAt(3, pt, "FIRM_PAN,EFF_DATE") }.getOrNull() }
            val lomrQ = async { runCatching { femaAt(1, pt, "CASE_NO,EFF_DATE") }.getOrNull() }
            fun rank(z: Feature): Double = (if (z.s("SFHA_TF") == "T") 1000.0 else 0.0) + (if ((z.s("FLD_ZONE") ?: "").startsWith("V")) 500.0 else 0.0) +
                maxOf(0.0, z.n("STATIC_BFE") ?: 0.0) + (if ((z.s("ZONE_SUBTY") ?: "").contains("0.2")) 100.0 else 0.0)
            val zones = zonesQ.await().sortedByDescending(::rank)
            Flood(Flood.Source.FEMA, zones.firstOrNull(), panelsQ.await()?.firstOrNull(), lomrQ.await()?.firstOrNull())
        }
    } catch (e: IOException) {
        atPoint("Admin_A12/MapServer/51", pt)?.let { Flood(Flood.Source.COUNTY, it.firstOrNull(), null, null) }
    }

    companion object {
        const val COUNTY = "https://gis.baycountyfl.gov/arcgis/rest/services"
        const val FEMA = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer"
        const val PANAMA_CITY = "https://services3.arcgis.com/RfAh242jlP6Nb5vP/arcgis/rest/services"
        const val AGOL = "https://services1.arcgis.com/QB0VWfqR9MD4lF0F/arcgis/rest/services"

        fun pointJSON(pt: GeoPoint): String = "{\"x\":${pt.x},\"y\":${pt.y},\"spatialReference\":{\"wkid\":4326}}"

        fun match(f: Feature): AddressMatch? {
            val addr = f.s("ADDRESS") ?: return null
            val g = f.geometry ?: return null
            return AddressMatch(addr, f.s("UNIT"), f.s("CMNTY"), f.s("ZIP"), f.s("RENUM"), g)
        }
    }
}
