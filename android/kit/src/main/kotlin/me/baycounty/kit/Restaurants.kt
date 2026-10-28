package me.baycounty.kit

import java.net.URLEncoder
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Restaurant inspections (/restaurants and /restaurants/<name>-<license>), from the restaurants dataset (one row per
 *  license, with its latest result and recent_results) and, for one restaurant, its rows in restaurant-inspections read
 *  from /api/v1 by license number. Same order, filters and wording as site/restaurants_page.py and the Swift kit. */
object Restaurants {
    val datasets = listOf("restaurants")

    /** The list's filters, the same chips as the site. */
    enum class Show(val label: String) {
        LATEST("Latest inspected"), FOLLOW("Needs a follow-up"), CLOSED("Closed this year"), NEW("New this year"), GONE("No longer licensed")
    }

    /** Result words short enough for a list row (site SHORT). */
    val short = mapOf(
        "Met inspection standards" to "Met standards", "Warning, follow-up visit set" to "Warning", "Follow-up visit: fixed" to "Fixed on follow-up",
        "Follow-up visit: more time given" to "More time given", "Fine recommended (administrative complaint)" to "Fine recommended",
        "Follow-up visit: not fixed, fine recommended" to "Fine recommended", "Follow-up after complaint: fixed" to "Fixed",
        "Follow-up after complaint: not fixed" to "Not fixed", "Follow-up after complaint: more time given" to "More time given",
        "Referred for an administrative decision" to "Referred", "Ordered closed (emergency order)" to "Closed by the state",
        "Allowed to reopen" to "Reopened", "Stayed closed: not fixed" to "Still closed", "Stayed closed: more time given" to "Still closed",
    )

    fun shortResult(result: String?): String? = result?.takeIf { it.isNotEmpty() }?.let { short[it] ?: it }

    /** How a result level is drawn: good, warning or bad (ok, warning, fine/closed). */
    enum class Tone { GOOD, WARNING, BAD, NONE }

    fun tone(level: String?): Tone = when (level) {
        "ok" -> Tone.GOOD
        "warning" -> Tone.WARNING
        "fine", "closed" -> Tone.BAD
        else -> Tone.NONE
    }

    /** The last six inspections' levels, oldest to newest, padded with "" at the start (no visit) to six. */
    fun strip(recent: String?): List<String> {
        val lv = (recent ?: "").split(" ").filter { it.isNotEmpty() }.take(6).reversed()
        return List(maxOf(0, 6 - lv.size)) { "" } + lv
    }

    /** The day a year before `today` (yyyy-MM-dd), the start of "this year" on the chips. */
    fun yearAgo(today: String): String = try { LocalDate.parse(today).minusDays(365).toString() } catch (_: Exception) { today }

    /** Latest inspected first, filtered like the site's list. A search looks at every license, licensed now or not. */
    fun list(rows: List<Row>, query: String = "", city: String? = null, show: Show = Show.LATEST, today: String): List<Row> {
        val q = query.trim().lowercase()
        val ya = yearAgo(today)
        return rows.filter { r ->
            val now = r.bool("licensed_now") == true
            if (q.isNotEmpty() && !listOfNotNull(r.string("business_name"), r.string("licensee"), r.string("address")).joinToString(" ").lowercase().contains(q)) return@filter false
            if (!city.isNullOrEmpty() && r.string("city") != city) return@filter false
            when (show) {
                Show.LATEST -> if (q.isEmpty()) now else true
                Show.FOLLOW -> now && (r.string("last_result_level") ?: "") in setOf("warning", "fine", "closed")
                Show.CLOSED -> (r.string("last_closure") ?: "") >= ya
                Show.NEW -> now && (r.string("opened") ?: "") >= ya
                Show.GONE -> !now
            }
        }.sortedWith(compareByDescending<Row> { it.string("last_inspection") ?: "" }.thenByDescending { it.string("business_name") ?: "" })
    }

    /** Cities with a licensed place, the busiest first. */
    fun cities(rows: List<Row>): List<String> =
        rows.filter { it.bool("licensed_now") == true }.mapNotNull { it.string("city") }.groupingBy { it }.eachCount().entries
            .sortedWith(compareByDescending<Map.Entry<String, Int>> { it.value }.thenBy { it.key }).map { it.key }

    /** Places last inspected in the 7 days ending on the newest inspection date: (start day, count). */
    fun week(rows: List<Row>): Pair<String, Int> {
        val latest = rows.mapNotNull { it.string("last_inspection") }.maxOrNull() ?: return "" to 0
        val start = try { LocalDate.parse(latest).minusDays(6).toString() } catch (_: Exception) { return "" to 0 }
        return start to rows.count { (it.string("last_inspection") ?: "") >= start }
    }

    /** One plain paragraph about a restaurant, from its row (the site's page says the same from every inspection). */
    fun summary(r: Row): String {
        val name = r.string("business_name") ?: "This place"
        val last = r.string("last_inspection")
        val res = r.string("last_result")
        if (last == null || res == null) return "$name has no inspections on file since 2016 yet. New licenses are inspected soon after they open."
        val out = mutableListOf("Last inspected ${dateLabel(last)}: ${res.take(1).lowercase() + res.drop(1)}.")
        val closures = (r.number("closures") ?: 0.0).toInt()
        val lc = r.string("last_closure")
        out += if (closures > 0 && lc != null) "The state has closed it ${times(closures)} since 2016, most recently ${dateLabel(lc)}."
               else "It has never been closed by the state since 2016."
        val n = (r.number("inspections") ?: 0.0).toInt()
        out += "$n inspection${if (n == 1) "" else "s"} on file."
        return out.joinToString(" ")
    }

    internal fun times(n: Int) = when (n) { 1 -> "once"; 2 -> "twice"; else -> "$n times" }

    /** The API query for one license's inspections, newest first. */
    fun inspectionsPath(license: String): String =
        "/api/v1/datasets/restaurant-inspections?license_number=${URLEncoder.encode(license, "UTF-8")}&sort=-date&limit=1000"

    /** One license's inspections, newest first (the API already filters and sorts; a full download is filtered here). */
    fun inspections(rows: List<Row>, license: String): List<Row> =
        rows.filter { (it.string("license_number") ?: "").trimStart('0') == license.trimStart('0') }
            .sortedWith(compareByDescending<Row> { it.string("date") ?: "" }.thenByDescending { it.number("visit_number") ?: 1.0 })

    /** "Follow-up visit" for a second visit, otherwise the plain inspection type. */
    fun visitLabel(r: Row): String =
        if ((r.number("visit_number") ?: 1.0) > 1) "Follow-up visit"
        else (r.string("inspection_type") ?: "").replace(" - Food", "").replace("Food-Licensing Inspection", "Licensing inspection")
            .replace("Complaint Full", "Complaint").replace("Complaint Partial", "Complaint (partial)")

    /** "2 high priority, 1 intermediate, 3 basic" or "No violations". */
    fun counts(r: Row): String {
        val h = (r.number("high_priority") ?: 0.0).toInt(); val i = (r.number("intermediate") ?: 0.0).toInt(); val b = (r.number("basic") ?: 0.0).toInt()
        return if (h + i + b == 0) "No violations" else "$h high priority, $i intermediate, $b basic"
    }

    private val label = DateTimeFormatter.ofPattern("MMM d, yyyy", Locale.US)

    fun dateLabel(s: String?): String = try { if (s == null) "" else LocalDate.parse(s.take(10)).format(label) } catch (_: Exception) { "" }

    fun pagePath(r: Row): String = r.string("page_url")?.takeIf { it.startsWith("/") } ?: "/restaurants"
}
