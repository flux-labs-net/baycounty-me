package me.baycounty.kit

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.KSerializer
import kotlinx.serialization.SerialName
import kotlinx.serialization.descriptors.PrimitiveKind
import kotlinx.serialization.descriptors.PrimitiveSerialDescriptor
import kotlinx.serialization.encoding.Decoder
import kotlinx.serialization.encoding.Encoder
import kotlinx.serialization.json.JsonDecoder
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonPrimitive
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
    val rank = mapOf("viewer" to 1, "auditor" to 1, "publisher" to 2, "alert_sender" to 3, "owner" to 4)
    val roleLabel = mapOf("owner" to "Owner", "alert_sender" to "Alert sender", "publisher" to "Publisher", "viewer" to "Viewer", "auditor" to "Auditor")
    fun can(role: String, need: String) = (rank[role] ?: 0) >= (rank[need] ?: 9)

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
    @Serializable(with = RecordId::class) val id: Int, val kind: String, val title: String, val message: String, val instruction: String? = null, val severity: String? = null,
    val countywide: Boolean = false, val status: String,
    @SerialName("created_by") val createdBy: String, @SerialName("created_at") val createdAt: String,
    @SerialName("confirmed_by") val confirmedBy: String? = null, @SerialName("sent_at") val sentAt: String? = null,
    @SerialName("ends_at") val endsAt: String? = null, val live: Boolean? = null, val geometry: String? = null,
) {
    val isLive get() = live ?: (status == "sent")
    val isWaiting get() = status == "pending"
    val statusLabel: String get() = when {
        isWaiting -> "Needs a second person"
        isLive -> "Live"
        status == "ended" -> "Ended"
        status == "cancelled" -> "Cancelled"
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
    @Serializable(with = RecordId::class) val id: Int, val title: String, val kind: String? = null, @SerialName("kind_label") val kindLabel: String? = null,
    val published: String? = null, @SerialName("event_date") val eventDate: String? = null, val text: String? = null,
    @SerialName("pdf_url") val pdfUrl: String? = null, val geometry: String? = null, val editable: Boolean = false,
)

@Serializable
data class StaffPosts(val kind: String, val posts: List<StaffPost> = emptyList(), @SerialName("from_records") val fromRecords: List<StaffPost> = emptyList())

@Serializable
data class StaffFlag(
    @Serializable(with = RecordId::class) val id: Int, val email: String, val dataset: String,
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

/** Made-up answers for screenshots and store review: staff-demo.json (same file as the iOS app's). */
@Serializable
data class StaffDemo(val me: StaffMe, val overview: StaffOverview, val home: StaffHome, val alerts: StaffAlerts, val notices: StaffPosts, val flags: StaffFlags) {
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
        // The verify answer carries only the token, so the account (workspaces, admin) comes from `me` right after.
        val signed: StaffMe = decode(call("verify", body = buildJsonObject { put("email", email); put("code", code); put("client", "app") }))
        token = signed.token ?: throw StaffError.Server("Sign-in didn't return a session. Try again.", 500)
        return me().copy(token = token)
    }
    suspend fun me(): StaffMe = decode(call("me"))
    suspend fun logout() { runCatching { call("logout", body = JsonObject(emptyMap())) }; token = null }
    suspend fun overview(): StaffOverview = decode(call("overview"))
    suspend fun home(ws: String): StaffHome = decode(call("home", mapOf("workspace" to ws)))
    suspend fun alerts(ws: String): StaffAlerts = decode(call("alerts", mapOf("workspace" to ws)))
    suspend fun reach(ws: String, kind: String, countywide: Boolean): StaffReach =
        decode(call("reach", mapOf("workspace" to ws, "kind" to kind) + (if (countywide) mapOf("countywide" to "1") else emptyMap())))
    suspend fun sendAlert(ws: String, kind: String, title: String, message: String, instruction: String, severity: String, countywide: Boolean, hours: Int): String =
        message(call("alert", body = buildJsonObject {
            put("workspace", ws); put("kind", kind); put("title", title); put("message", message); put("instruction", instruction)
            put("severity", severity); put("countywide", countywide); put("hours", hours)
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
}

/** Database ids are bigints, which the server sends as strings ("12"); older answers and the demo file use numbers. */
object RecordId : KSerializer<Int> {
    override val descriptor = PrimitiveSerialDescriptor("RecordId", PrimitiveKind.INT)
    override fun deserialize(decoder: Decoder): Int {
        val p = (decoder as? JsonDecoder)?.decodeJsonElement()?.jsonPrimitive ?: return decoder.decodeInt()
        return p.intOrNull ?: p.content.toIntOrNull() ?: throw IllegalArgumentException("Not a record id: ${p.content}")
    }
    override fun serialize(encoder: Encoder, value: Int) = encoder.encodeInt(value)
}
