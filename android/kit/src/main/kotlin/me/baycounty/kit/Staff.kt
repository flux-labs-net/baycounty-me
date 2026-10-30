package me.baycounty.kit

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.put
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.text.NumberFormat
import java.time.LocalDate
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

/** The staff app (BayCounty.me Staff): the government workspace (/staff) on a phone, through /api/gov (api/gov.js).
 *  Mirrors ios/BayCountyKit Staff.swift; the same demo answers (staff-demo.json) and tests. */
object Staff {
    val rank = mapOf("viewer" to 1, "auditor" to 1, "records" to 1, "publisher" to 2, "alert_sender" to 3, "owner" to 4)
    val roleLabel = mapOf("owner" to "Owner", "alert_sender" to "Alert sender", "publisher" to "Publisher", "records" to "Records sender", "viewer" to "Viewer", "auditor" to "Auditor")
    /** [need] is a role, or "submit" (send records): the records sender role, or publisher and up (api/_gov.js allowed). */
    fun can(role: String, need: String) =
        if (need == "submit") role == "records" || (rank[role] ?: 0) >= 2 else (rank[role] ?: 0) >= (rank[need] ?: 9)

    /** The kinds of record a government can send (labels match api/_records.js): key, label, hint. */
    val recordKinds = listOf(
        Triple("checkbook", "Checkbook (every payment)", "The check register or payments report for one or more whole months."),
        Triple("budget", "Budget vs. actual", "The budget-vs-actual report, as of a month end."),
        Triple("contracts", "Contracts awarded", "Vendor, amount and award date at least."),
        Triple("payroll", "Payroll (job titles and pay)", "A payroll or position list: job title and pay. Names are removed before anything is published."),
        Triple("appointments", "Board appointments", "Who sits on each board you appoint: board, member and term."),
        Triple("fees", "Fee or rate changes", "A new or changed fee: what it is, the new amount and when it starts."),
    )
    fun recordKindLabel(k: String) = recordKinds.firstOrNull { it.first == k }?.second ?: k.replaceFirstChar { it.uppercase() }
    const val MAX_INLINE_BYTES = 3 * 1024 * 1024

    val alertOrder = listOf("evacuation", "shelter", "boil-water", "road", "safety", "general")
    val severities = listOf("extreme" to "Extreme", "severe" to "Severe", "moderate" to "Moderate", "minor" to "Minor", "info" to "Information")
    val noticeOrder = listOf("meeting", "hearing", "bid", "utility", "road", "other")
    val hourChoices = listOf(6, 12, 24, 48, 72, 168)
    fun hoursLabel(h: Int) = if (h % 24 == 0) (if (h == 24) "1 day" else if (h == 168) "1 week" else "${h / 24} days") else "$h hours"

    val actions = mapOf(
        "signed_in" to "signed in", "notice_posted" to "posted a notice", "notice_edited" to "changed a notice", "notice_withdrawn" to "withdrew a notice",
        "event_posted" to "posted an event", "event_edited" to "changed an event", "event_withdrawn" to "withdrew an event", "job_posted" to "posted a job",
        "job_edited" to "changed a job", "job_withdrawn" to "withdrew a job", "alert_sent" to "sent an alert",
        "alert_drafted" to "saved a countywide alert for a second person to confirm", "alert_confirmed" to "confirmed an alert",
        "alert_ended" to "ended an alert", "alert_cancelled" to "cancelled an alert", "data_flagged" to "flagged record data",
        "flag_answered" to "BayCounty.me answered a flag", "member_set" to "changed access", "member_removed" to "removed access",
        "records_published" to "published records", "records_withdrawn" to "withdrew records", "records_confirmed" to "confirmed a file",
        "records_review_published" to "published a file after review", "records_review_held" to "kept a file off the site after review", "intake_senders_changed" to "changed who may email records in",
        "feed_agreed" to "agreed to a source we read", "feed_unagreed" to "took back agreement to a source",
    )

    /** "Oct 30, 8:05 AM" in Bay County time; plain dates as "Nov 12, 2026". */
    fun whenOf(s: String?): String {
        if (s.isNullOrEmpty()) return ""
        return try {
            if (s.length == 10) LocalDate.parse(s).format(DateTimeFormatter.ofPattern("MMM d, yyyy", Locale.US))
            else OffsetDateTime.parse(s).atZoneSameInstant(ZoneId.of("America/Chicago")).format(DateTimeFormatter.ofPattern("MMM d, h:mm a", Locale.US))
        } catch (e: Exception) { s }
    }
}

@Serializable
data class StaffWorkspace(val id: String, val name: String, val countywide: Boolean? = null, val role: String) {
    val roleLabel get() = Staff.roleLabel[role] ?: role
    fun can(need: String) = Staff.can(role, need)
}

@Serializable
data class StaffMe(
    val email: String,
    val admin: Boolean = false,
    val workspaces: List<StaffWorkspace> = emptyList(),
    @SerialName("alert_kinds") val alertKinds: Map<String, String> = emptyMap(),
    @SerialName("notice_kinds") val noticeKinds: Map<String, String> = emptyMap(),
    val token: String? = null,
)

@Serializable
data class StaffActivity(
    val email: String,
    val action: String,
    val detail: JsonElement? = null,
    val at: String,
    @SerialName("gov_name") val govName: String? = null,
) {
    val sentence: String get() {
        var s = "$email ${Staff.actions[action] ?: action.replace('_', ' ')}"
        val t = ((detail as? JsonObject)?.get("title") as? JsonPrimitive)?.takeIf { it.isString }?.content
        if (!t.isNullOrEmpty()) s += ": $t"
        return s
    }
}

@Serializable
data class StaffHome(val role: String, val counts: Counts, val activity: List<StaffActivity> = emptyList()) {
    @Serializable
    data class Counts(
        val notices: Int = 0, val events: Int = 0, val jobs: Int = 0,
        @SerialName("live_alerts") val liveAlerts: Int = 0, @SerialName("waiting_alerts") val waitingAlerts: Int = 0,
        @SerialName("open_flags") val openFlags: Int = 0, val members: Int = 0,
    )
}

@Serializable
data class StaffAlert(
    val id: Int, val kind: String, val title: String, val message: String, val instruction: String? = null, val severity: String? = null,
    val countywide: Boolean = false, val status: String,
    @SerialName("created_by") val createdBy: String, @SerialName("created_at") val createdAt: String,
    @SerialName("confirmed_by") val confirmedBy: String? = null, @SerialName("sent_at") val sentAt: String? = null,
    @SerialName("ends_at") val endsAt: String? = null, val live: Boolean? = null, val geometry: String? = null,
    /** How many phones, inboxes and texts it was sent to ({push, email, sms}); staff and admins only. */
    val sent: Map<String, Int>? = null,
) {
    val isLive get() = live ?: (status == "sent")
    /** "2 phones, 1 inbox", or null before anything went out. */
    val sentSentence: String? get() {
        val s = sent ?: return null
        fun n(k: String, one: String, many: String) = s[k]?.takeIf { it > 0 }?.let { "$it ${if (it == 1) one else many}" }
        return listOfNotNull(n("push", "phone", "phones"), n("email", "inbox", "inboxes"), n("sms", "text", "texts")).joinToString(", ").ifEmpty { null }
    }
    val isWaiting get() = status == "pending"
    val statusLabel: String get() = when {
        isWaiting -> "Needs a second person"
        isLive -> "Live"
        status == "ended" -> "Ended"
        status == "cancelled" -> "Cancelled"
        status == "removed" -> "Removed"
        status == "sent" -> "Expired"
        else -> status.replaceFirstChar { it.uppercase() }
    }
    fun canConfirm(email: String) = isWaiting && !createdBy.equals(email, ignoreCase = true)
}

@Serializable
data class StaffAlerts(val countywide: Boolean? = null, val alerts: List<StaffAlert> = emptyList())

@Serializable
data class StaffReach(val topic: String? = null, val phones: Int? = null, val emails: Int? = null, val note: String? = null) {
    val sentence: String get() {
        if (note != null && topic == null) return note
        fun n(v: Int?, one: String, many: String) = if (v == null) "some $many" else NumberFormat.getIntegerInstance(Locale.US).format(v) + " " + (if (v == 1) one else many)
        return "Reaches ${n(phones, "phone", "phones")} and ${n(emails, "inbox", "inboxes")} now, plus the public alert timeline."
    }
}

@Serializable
data class StaffPost(
    val id: Int, val title: String, val kind: String? = null, @SerialName("kind_label") val kindLabel: String? = null,
    val published: String? = null, @SerialName("event_date") val eventDate: String? = null, val text: String? = null,
    @SerialName("pdf_url") val pdfUrl: String? = null, val geometry: String? = null, val editable: Boolean = false,
)

@Serializable
data class StaffPosts(val kind: String, val posts: List<StaffPost> = emptyList(), @SerialName("from_records") val fromRecords: List<StaffPost> = emptyList())

@Serializable
data class StaffFlag(
    val id: Int, val email: String, val dataset: String,
    @SerialName("record_label") val recordLabel: String? = null, val field: String? = null,
    @SerialName("shown_value") val shownValue: String? = null, @SerialName("correct_value") val correctValue: String? = null,
    @SerialName("evidence_url") val evidenceUrl: String? = null, val note: String? = null, val status: String,
    val reply: String? = null, @SerialName("created_at") val createdAt: String,
    @SerialName("gov_name") val govName: String? = null, @SerialName("workspace_id") val workspaceId: String? = null,
) {
    val statusLabel get() = mapOf("open" to "Open", "fixed" to "Fixed", "not_changed" to "Not changed")[status] ?: status
    val subject get() = listOfNotNull(DATASETS[dataset] ?: dataset, recordLabel, field).filter { it.isNotEmpty() }.joinToString(" · ")
    companion object {
        val DATASETS = mapOf(
            "budget-years" to "Budget by year", "officeholder-terms" to "Who held each seat", "people-directory" to "Officials and staff",
            "utility-rates" to "Utility rates", "trash-pickup" to "Trash and recycling pickup", "parks" to "Parks", "development-projects" to "Development projects",
            "public-notices" to "Public notices", "job-openings" to "Job openings", "community-events" to "Events", "other" to "Other",
        )
    }
}

@Serializable
data class StaffFlags(val flags: List<StaffFlag> = emptyList())

@Serializable
data class StaffOverview(val totals: Totals, val workspaces: List<Row> = emptyList(), val activity: List<StaffActivity> = emptyList()) {
    @Serializable
    data class Totals(
        val workspaces: Int = 0, val members: Int = 0, @SerialName("live_alerts") val liveAlerts: Int = 0,
        @SerialName("waiting_alerts") val waitingAlerts: Int = 0, @SerialName("open_flags") val openFlags: Int = 0, val notices: Int = 0,
    )
    @Serializable
    data class Row(
        val id: String, val name: String, val countywide: Boolean? = null, val members: Int = 0,
        @SerialName("last_activity") val lastActivity: String? = null, @SerialName("live_alerts") val liveAlerts: Int = 0,
        @SerialName("waiting_alerts") val waitingAlerts: Int = 0, @SerialName("open_flags") val openFlags: Int = 0, val notices: Int = 0,
    ) {
        val needsAttention get() = waitingAlerts > 0 || openFlags > 0
    }
}

/** GET ?action=submissions: what's due, the government's intake email address and every file sent. */
@Serializable
data class StaffSubmissions(val address: String? = null, val due: List<Due> = emptyList(), val files: List<StaffRecordFile> = emptyList()) {
    @Serializable
    data class Due(val kind: String, val label: String, val want: String, val have: String? = null, val current: Boolean = false, val text: String)
}

/** One file a government sent ("f12" from the finance importer, "c3" a contract list). */
@Serializable
data class StaffRecordFile(
    val id: String, val kind: String, val name: String, val status: String, val via: String? = null,
    @SerialName("sent_by") val sentBy: String? = null, @SerialName("sent_at") val sentAt: String? = null,
    @SerialName("period_start") val periodStart: String? = null, @SerialName("period_end") val periodEnd: String? = null,
    val rows: Int? = null, val problem: String? = null, @SerialName("published_at") val publishedAt: String? = null,
) {
    val statusLabel get() = mapOf("waiting" to "Waiting for your OK", "checking" to "Being checked", "in_review" to "In review", "published" to "Published",
        "held" to "Doesn’t add up", "not_published" to "Not published after review", "withdrawn" to "Withdrawn")[status] ?: status
    val canPublish get() = status == "waiting"
    val canWithdraw get() = status == "waiting" || status == "published" || status == "in_review"
    /** "Contracts awarded · 14 rows · through Sep 30, 2026". */
    val detail: String get() = listOfNotNull(
        Staff.recordKindLabel(kind),
        rows?.let { NumberFormat.getIntegerInstance(Locale.US).format(it) + if (it == 1) " row" else " rows" },
        periodEnd?.let { "through " + Staff.whenOf(it) },
    ).joinToString(" · ")
}

/** POST ?action=submit-preview: what we read from a file, before anyone publishes it. */
@Serializable
data class StaffRecordPreview(
    val id: String, val kind: String, val ok: Boolean = false, val missing: List<String>? = null, val label: String? = null,
    @SerialName("row_count") val rowCount: Int? = null, @SerialName("parsed_total") val parsedTotal: Double? = null,
    @SerialName("printed_total") val printedTotal: Double? = null, val skipped: Int? = null,
    @SerialName("already_on_site") val alreadyOnSite: Int? = null, val withheld: Int? = null,
    @SerialName("already_added") val alreadyAdded: Boolean? = null, val period: Period? = null, val warnings: List<String>? = null,
) {
    @Serializable
    data class Period(val start: String? = null, val end: String? = null)
    val problem: String? get() = when {
        ok -> null
        alreadyAdded == true -> "This file was already sent."
        missing.isNullOrEmpty() -> "We couldn't read this file."
        else -> "We couldn't find: ${missing.joinToString(", ")}."
    }
}

/** Made-up answers for screenshots and store review: staff-demo.json (same file as the iOS app's). */
@Serializable
data class StaffDemo(val me: StaffMe, val overview: StaffOverview, val home: StaffHome, val alerts: StaffAlerts, val notices: StaffPosts, val flags: StaffFlags,
                     val submissions: StaffSubmissions? = null) {
    companion object { fun decode(json: String): StaffDemo = BCJson.decodeFromString(serializer(), json) }
}

/** Talks to /api/gov with the staff session token. */
class StaffClient(var token: String?, private val baseURL: String = BayCountyClient.SITE) {
    sealed class StaffError(message: String) : IOException(message) {
        class Server(message: String, val code: Int) : StaffError(message)
        class SignedOut : StaffError("Your session ended. Sign in again.")
    }
    data class Request(val url: String, val headers: Map<String, String>, val body: String?)

    fun request(action: String, query: Map<String, String> = emptyMap(), body: JsonObject? = null): Request {
        val h = mutableMapOf<String, String>()
        token?.let { h["Authorization"] = "Bearer $it" }
        if (body != null) h["Content-Type"] = "application/json"
        val qs = (listOf("action" to action) + query.toSortedMap().toList()).joinToString("&") { (k, v) -> "$k=" + URLEncoder.encode(v, "UTF-8") }
        return Request("$baseURL/api/gov?$qs", h, body?.toString())
    }

    private suspend fun call(action: String, query: Map<String, String> = emptyMap(), body: JsonObject? = null): String = withContext(Dispatchers.IO) {
        val r = request(action, query, body)
        val conn = URL(r.url).openConnection() as HttpURLConnection
        conn.connectTimeout = 15000; conn.readTimeout = 30000; conn.useCaches = false
        r.headers.forEach { (k, v) -> conn.setRequestProperty(k, v) }
        try {
            if (r.body != null) { conn.requestMethod = "POST"; conn.doOutput = true; conn.outputStream.use { it.write(r.body.toByteArray()) } }
            val code = conn.responseCode
            if (code == 401) throw StaffError.SignedOut()
            val text = (if (code == 200) conn.inputStream else conn.errorStream)?.use { it.readBytes().decodeToString() } ?: ""
            if (code != 200) {
                val msg = runCatching { BCJson.parseToJsonElement(text).jsonObject["error"]?.stringValue }.getOrNull()
                throw StaffError.Server(msg ?: "Something went wrong. Try again.", code)
            }
            text
        } finally { conn.disconnect() }
    }
    private inline fun <reified T> decode(s: String): T = BCJson.decodeFromString(s)
    private fun message(s: String) = runCatching { BCJson.parseToJsonElement(s).jsonObject["message"]?.stringValue }.getOrNull() ?: "Done."

    suspend fun login(email: String): String = message(call("login", body = buildJsonObject { put("email", email) }))
    suspend fun verify(email: String, code: String): StaffMe {
        val me: StaffMe = decode(call("verify", body = buildJsonObject { put("email", email); put("code", code); put("client", "app") }))
        token = me.token
        return me
    }
    suspend fun me(): StaffMe = decode(call("me"))
    suspend fun logout() { runCatching { call("logout", body = JsonObject(emptyMap())) }; token = null }
    suspend fun overview(): StaffOverview = decode(call("overview"))
    suspend fun home(ws: String): StaffHome = decode(call("home", mapOf("workspace" to ws)))
    suspend fun alerts(ws: String): StaffAlerts = decode(call("alerts", mapOf("workspace" to ws)))
    suspend fun reach(ws: String, kind: String, countywide: Boolean): StaffReach =
        decode(call("reach", mapOf("workspace" to ws, "kind" to kind) + (if (countywide) mapOf("countywide" to "1") else emptyMap())))
    /** geometry: the map of where it applies (AlertArea.pinsGeoJSON), or null for none. */
    suspend fun sendAlert(ws: String, kind: String, title: String, message: String, instruction: String, severity: String, countywide: Boolean, hours: Int, geometry: String? = null): String =
        message(call("alert", body = buildJsonObject {
            put("workspace", ws); put("kind", kind); put("title", title); put("message", message); put("instruction", instruction)
            put("severity", severity); put("countywide", countywide); put("hours", hours)
            if (geometry != null) put("geometry", geometry)
        }))
    suspend fun confirmAlert(ws: String, id: Int) { call("alert-confirm", body = buildJsonObject { put("workspace", ws); put("id", id) }) }
    suspend fun endAlert(ws: String, id: Int) { call("alert-end", body = buildJsonObject { put("workspace", ws); put("id", id) }) }
    suspend fun notices(ws: String): StaffPosts = decode(call("posts", mapOf("workspace" to ws, "kind" to "notice")))
    /** `kind` names the post kind for the server; the notice type travels as notice_kind. */
    suspend fun saveNotice(ws: String, id: Int?, kind: String, title: String, text: String, eventDate: String?) {
        call("post", body = buildJsonObject {
            put("workspace", ws); put("kind", "notice"); put("notice_kind", kind); put("title", title); put("text", text)
            if (id != null) put("id", id)
            if (!eventDate.isNullOrEmpty()) put("event_date", eventDate)
        })
    }
    suspend fun withdrawNotice(ws: String, id: Int) { call("withdraw", body = buildJsonObject { put("workspace", ws); put("kind", "notice"); put("id", id) }) }
    suspend fun flags(ws: String): StaffFlags = decode(call("flags", mapOf("workspace" to ws)))
    suspend fun reviewFlags(status: String = "open"): StaffFlags = decode(call("review-flags", mapOf("status" to status)))
    suspend fun answerFlag(id: Int, status: String, reply: String) { call("review-flag", body = buildJsonObject { put("id", id); put("status", status); put("reply", reply) }) }

    // Send records (records sender, or publisher and up). Files up to 3 MB go inline.
    suspend fun submissions(ws: String): StaffSubmissions = decode(call("submissions", mapOf("workspace" to ws)))
    suspend fun previewRecords(ws: String, kind: String, filename: String, content: ByteArray, asOf: String? = null, printedTotal: Double? = null): StaffRecordPreview =
        decode(call("submit-preview", body = buildJsonObject {
            put("workspace", ws); put("kind", kind); put("filename", filename); put("content", java.util.Base64.getEncoder().encodeToString(content))
            if (!asOf.isNullOrEmpty()) put("as_of", asOf)
            if (printedTotal != null) put("printed_total", printedTotal)
        }))
    suspend fun publishRecords(ws: String, id: String): String = message(call("submit-confirm", body = buildJsonObject { put("workspace", ws); put("id", id) }))
    suspend fun withdrawRecords(ws: String, id: String) { call("submit-withdraw", body = buildJsonObject { put("workspace", ws); put("id", id) }) }
}
