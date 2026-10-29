package me.baycounty.kit

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.jsonPrimitive
import java.net.URLEncoder
import java.util.Locale
import kotlin.math.roundToInt

/** The parts of /schools added in PR #191 and #194: the scores behind each grade next to the Florida average, spending
 *  per student, school-day times, the grade mix against Florida, map and phone links, and the attendance zones for the
 *  map. Mirrors the Swift `Schools` extension (SchoolDetails.swift) and site/schools_page.py. */
object SchoolDetails {
    /** The school-zones dataset (attendance zone shapes) is big, so only the map loads it. */
    const val ZONES = "school-zones"

    /** The pieces of a Florida school grade, in the site's order: (column, label). */
    val components = listOf(
        "grade3_ela_achievement" to "3rd-grade reading", "ela_achievement" to "Reading", "ela_gains" to "Reading gains",
        "ela_gains_low25" to "Reading, lowest 25%", "math_achievement" to "Math", "math_gains" to "Math gains",
        "math_gains_low25" to "Math, lowest 25%", "science_achievement" to "Science", "social_studies_achievement" to "Social studies",
        "middle_acceleration" to "Advanced courses", "graduation_rate" to "Graduation rate", "college_career_acceleration" to "College credit",
    )

    private fun Row.year(): Int = (number("year") ?: 0.0).toInt()

    /** 2026 -> "2025-26" */
    fun yearLabel(y: Int): String = "${y - 1}-${y.toString().takeLast(2)}"

    fun latestGradeYear(grades: List<Row>): Int? = grades.mapNotNull { it.number("year")?.toInt() }.maxOrNull()

    data class GradeCounts(val year: Int, val a: Int, val graded: Int, val b: Int, val c: Int, val df: Int)

    /** The latest-year grades of the open schools. */
    fun gradeCounts(schools: List<Row>, grades: List<Row>): GradeCounts? {
        val y = latestGradeYear(grades) ?: return null
        val open = schools.filter { it.string("status") == "Open" }.mapNotNull { it.string("school_id") }.toSet()
        val g = grades.filter { it.year() == y && it.string("school_id") in open }.mapNotNull { it.string("grade") }
        return GradeCounts(y, g.count { it == "A" }, g.size, g.count { it == "B" }, g.count { it == "C" }, g.count { it == "D" || it == "F" })
    }

    data class Score(val label: String, val value: Double, val state: Double?, val change: Int?)
    data class Scores(val title: String, val stateLabel: String, val items: List<Score>)

    /** The scores behind one school's grade in the newest grade year, with the Florida average for its school type. */
    fun scores(grades: List<Row>, state: List<Row>, school: String): Scores? {
        val y = latestGradeYear(grades) ?: return null
        val g = grades.firstOrNull { it.string("school_id") == school && it.year() == y } ?: return null
        val prev = grades.firstOrNull { it.string("school_id") == school && it.year() == y - 1 }
        val type = g.string("school_type") ?: "All"
        val st = state.firstOrNull { it.year() == y && it.string("school_type") == type } ?: state.firstOrNull { it.year() == y && it.string("school_type") == "All" }
        val items = components.mapNotNull { (k, label) ->
            val v = g.number(k) ?: return@mapNotNull null
            Score(label, v, st?.number(k), prev?.number(k)?.let { Math.round(v - it).toInt() })
        }
        if (items.isEmpty()) return null
        val pts = g.number("percent_of_points")?.let { ": ${it.roundToInt()}% of possible points" } ?: ""
        val stType = st?.string("school_type")?.let { if (it == "All") null else it.lowercase() + " school" } ?: "school"
        return Scores("Scores behind the ${g.string("school_year") ?: yearLabel(y)} grade$pts", "Florida $stType average", items)
    }

    /** '13:50' -> '1:50 p.m.' */
    fun time(hhmm: String?): String {
        val p = (hhmm ?: "").split(":")
        val h = p.getOrNull(0)?.toIntOrNull() ?: return ""
        val m = p.getOrNull(1)?.toIntOrNull() ?: return ""
        return String.format(Locale.US, "%d:%02d %s", (h + 11) % 12 + 1, m, if (h < 12) "a.m." else "p.m.")
    }

    /** One school's day: "7:30 a.m. to 2:00 p.m.", or one part per grade band. */
    fun hours(bell: List<Row>, school: String): String? {
        val rows = bell.filter { it.string("kind") == "school day" && it.string("school_id") == school }
        if (rows.isEmpty()) return null
        val note = { r: Row -> r.string("note")?.let { " ($it)" } ?: "" }
        if (rows.size == 1 && rows[0].string("part") == null) return "${time(rows[0].string("start_time"))} to ${time(rows[0].string("end_time"))}${note(rows[0])}"
        return rows.joinToString("; ") { "${it.string("part") ?: ""}: ${time(it.string("start_time"))} to ${time(it.string("end_time"))}${note(it)}" }
    }

    fun bellYear(bell: List<Row>): String? = bell.firstNotNullOfOrNull { it.string("school_year") }

    fun earlyRelease(bell: List<Row>): String? {
        val rows = bell.filter { it.string("kind") == "early release" }
        if (rows.isEmpty()) return null
        return rows.joinToString(", ") { "${(it.string("part") ?: "").lowercase()} let out at ${time(it.string("end_time"))}" }
    }

    fun spendingYear(spend: List<Row>): Int? = spend.filter { it.number("total_per_student") != null }.mapNotNull { it.number("year")?.toInt() }.maxOrNull()

    /** What one school spent per student in the newest spending year. */
    fun spending(spend: List<Row>, school: String): Pair<Int, Double>? {
        val y = spendingYear(spend) ?: return null
        val v = spend.firstOrNull { it.string("school_id") == school && it.year() == y }?.number("total_per_student") ?: return null
        return y to v
    }

    data class Spend(val id: String, val name: String, val perStudent: Double)
    data class SpendRanking(val year: Int, val rows: List<Spend>, val average: Double)

    /** Open schools by spending per student in the newest year, highest first, and the enrollment-weighted average. */
    fun spendingRanking(spend: List<Row>, schools: List<Row>): SpendRanking? {
        val y = spendingYear(spend) ?: return null
        val open = schools.filter { it.string("status") == "Open" }.mapNotNull { it.string("school_id") }.toSet()
        val rs = spend.filter { it.year() == y && it.number("total_per_student") != null && it.string("school_id") in open }
        val total = rs.mapNotNull { it.number("estimated_total") }.sum()
        val students = rs.filter { it.number("estimated_total") != null }.mapNotNull { it.number("enrollment") }.sum()
        val list = rs.map { Spend(it.string("school_id") ?: "", it.string("school") ?: "", it.number("total_per_student")!!) }.sortedByDescending { it.perStudent }
        return SpendRanking(y, list, if (students > 0) total / students else 0.0)
    }

    /** Grades A to F in one year: every graded school here (closed ones too, like the site), and Florida's counts. */
    fun gradeMix(grades: List<Row>, state: List<Row>, year: Int): Pair<Map<String, Int>, Map<String, Int>?> {
        val local = mutableMapOf<String, Int>()
        for (g in grades) if (g.year() == year) g.string("grade")?.takeIf { it.length == 1 && it in "ABCDF" }?.let { local[it] = (local[it] ?: 0) + 1 }
        val fl = state.firstOrNull { it.year() == year && it.string("school_type") == "All" }
        return local to fl?.let { r -> "ABCDF".associate { it.toString() to (r.number("grade_${it.lowercaseChar()}") ?: 0.0).toInt() } }
    }

    fun aShare(mix: Map<String, Int>): Double { val n = mix.values.sum(); return if (n == 0) 0.0 else 100.0 * (mix["A"] ?: 0) / n }

    /** The school's address as a maps search (opens the maps app). */
    fun mapsURL(s: Row): String? {
        val a = s.string("address") ?: return null
        val q = listOfNotNull(s.string("name"), a, s.string("city"), "FL ${s.string("zip") ?: ""}".trim()).joinToString(", ")
        return "https://www.google.com/maps/search/?api=1&query=" + URLEncoder.encode(q, "UTF-8").replace("+", "%20")
    }

    /** "(850) 767-4400" and a tel: link, when the phone has ten digits. */
    fun phone(s: Row): Pair<String, String>? {
        val d = (s.string("phone") ?: "").filter { it.isDigit() }.takeLast(10)
        if (d.length != 10) return null
        return "(${d.substring(0, 3)}) ${d.substring(3, 6)}-${d.substring(6)}" to "tel:+1$d"
    }

    /** One attendance zone's outline rings as (latitude, longitude) pairs, from the GeoJSON in school-zones. */
    data class Zone(val id: String, val level: String, val school: String, val rings: List<List<Pair<Double, Double>>>)

    fun zones(rows: List<Row>, level: String): List<Zone> = rows.filter { it.string("level") == level }.mapNotNull { r ->
        val obj = runCatching { BCJson.parseToJsonElement(r.string("geometry") ?: return@mapNotNull null) as? JsonObject }.getOrNull() ?: return@mapNotNull null
        val type = obj["type"]?.stringValue ?: return@mapNotNull null
        val coords = obj["coordinates"] as? JsonArray ?: return@mapNotNull null
        val polys = if (type == "MultiPolygon") coords.mapNotNull { it as? JsonArray } else listOf(coords)
        val rings = polys.mapNotNull { (it.firstOrNull() as? JsonArray) }.map { ring ->
            ring.mapNotNull { p -> (p as? JsonArray)?.takeIf { it.size >= 2 }?.let { it[1].jsonPrimitive.doubleOrNull!! to it[0].jsonPrimitive.doubleOrNull!! } }
        }
        if (rings.isEmpty()) null else Zone(r.string("zone_id") ?: "${r.id}", level, r.string("school") ?: r.string("zone_name") ?: "", rings)
    }
}
