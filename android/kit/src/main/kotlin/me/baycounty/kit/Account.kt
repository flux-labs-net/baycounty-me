package me.baycounty.kit

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray
import kotlinx.serialization.json.add
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

/** What's happening near one place: the answer of `/api/v1/nearby` (api/_nearby.js), the same as the Swift
 *  `NearbyFeed`. The website's My home page, the Monday email and the app's My home screen all show it. */
@Serializable
data class NearbyFeed(
    val today: String,
    val city: String? = null,
    val zip: String? = null,
    @SerialName("gov_id") val govId: String,
    @SerialName("local_government") val localGovernment: String,
    val zone: String? = null,
    @SerialName("radius_mi") val radiusMi: Double,
    @SerialName("today_card") val todayCard: TodayCard,
    val governments: List<Gov> = emptyList(),
    val sections: List<Section> = emptyList(),
    val note: String? = null,
    val home: Home? = null,
) {
    @Serializable
    data class Item(
        val kind: String,
        val title: String,
        val detail: String? = null,
        val date: String? = null,
        val url: String? = null,
        val miles: Double? = null,
        @SerialName("entity_id") val entityId: String? = null,
        val level: String? = null,
        @SerialName("all_day") val allDay: Boolean? = null,
    ) {
        val id: String get() = "$kind|$title|${date ?: ""}"
        /** Work nearby leads with its distance; everything else with its date. */
        val leadsWithDistance: Boolean get() = miles != null && (date == null || kind in setOf("development", "sales-tax", "road"))
        val tag: String?
            get() = when {
                level == "closed" -> "Closed"
                level == "warning" -> "Warning"
                else -> TAGS[kind]
            }
        /** A profile on the site for a named business, otherwise the item's own record. */
        val link: String?
            get() = entityId?.takeIf { it.startsWith("business:") }?.let { "https://baycounty.me/profile/business/" + it.removePrefix("business:") } ?: url
    }

    @Serializable
    data class Section(val id: String, val title: String, val count: Int? = null, val items: List<Item> = emptyList(), val empty: String = "")
    @Serializable
    data class Pickup(val service: String, val days: String, val provider: String? = null)
    @Serializable
    data class Beach(
        val flag: String,
        @SerialName("rip_current_risk") val ripCurrentRisk: String? = null,
        @SerialName("water_temperature") val waterTemperature: String? = null,
        @SerialName("miles_to_beach") val milesToBeach: Double? = null,
    )
    @Serializable
    data class TodayCard(val trash: List<Pickup>? = null, val beach: Beach? = null, val alerts: Int = 0)
    @Serializable
    data class Gov(@SerialName("gov_id") val govId: String, val name: String, val url: String)
    @Serializable
    data class Home(
        val label: String? = null, val address: String, val city: String? = null, val zip: String? = null,
        val zone: String? = null, @SerialName("gov_id") val govId: String? = null,
    )

    /** Month, day and time for a date tile. */
    data class When(val month: String, val day: String, val time: String?)

    companion object {
        private val TAGS = mapOf(
            "evacuation" to "Evacuation", "weather" to "Weather", "boil-water" to "Boil water", "road" to "Road", "shelter" to "Shelter",
            "utility" to "Utility", "agenda" to "Agenda", "development" to "Development", "sales-tax" to "Sales tax",
        )

        fun decode(json: String): NearbyFeed {
            val o = BCJson.parseToJsonElement(json).jsonObject
            val inner = (o["data"] as? JsonObject) ?: o
            return BCJson.decodeFromJsonElement(serializer(), inner)
        }

        /** Dates without an offset are Bay County clock times and are shown as written; dates with an offset are
         *  shown in Bay County time. The same rule as the site's page script and the Swift kit. */
        fun whenOf(s: String?): When? {
            if (s == null || s.length < 10) return null
            val bay = ZoneId.of("America/Chicago")
            val naive = !Regex("([zZ]|[+-]\\d\\d:?\\d\\d)$").containsMatchIn(s)
            val dt: LocalDateTime = try {
                when {
                    s.length == 10 -> java.time.LocalDate.parse(s).atTime(12, 0)
                    naive -> LocalDateTime.parse(s.take(19))
                    else -> OffsetDateTime.parse(s).atZoneSameInstant(bay).toLocalDateTime()
                }
            } catch (e: Exception) { return null }
            fun f(p: String) = dt.format(DateTimeFormatter.ofPattern(p, Locale.US))
            val time = if (s.length > 10) f("EEE h:mm a").replace(":00", "") else null
            return When(f("MMM").uppercase(), f("d"), time)
        }
    }
}

/** A resident's account (api/_account.js): who they are, their saved home and what they want to hear about. */
@Serializable
data class AccountMe(
    val user: User,
    val home: Home? = null,
    val prefs: Prefs? = null,
    val devices: Int? = null,
    val choices: Choices? = null,
    /** Only in the answer to a sign-in from the app: the session token for the Authorization header. */
    val token: String? = null,
) {
    @Serializable
    data class User(val email: String, @SerialName("first_name") val firstName: String? = null)
    @Serializable
    data class Home(
        val label: String? = null, val address: String, val city: String? = null, val zip: String? = null,
        val lat: Double, val lon: Double, @SerialName("gov_id") val govId: String? = null, val zone: String? = null,
        @SerialName("parcel_id") val parcelId: String? = null,
    ) {
        val subtitle: String get() = listOfNotNull(city, zip).filter { it.isNotEmpty() }.joinToString(" ")

        /** The saved home as the phone's address ("825 Ohio Ave #2 32444" → street 825 OHIO AVE, unit 2), so the
         *  Today card, tax bill and trash day use the account's home on any phone the resident signs in on. Same rules
         *  as window.BCHomeLink on the site. */
        val addressMatch: AddressMatch get() {
            var s = address.trim().replace(Regex("""\s+\d{5}(-\d{4})?$"""), "")
            var unit: String? = null
            Regex("""\s*#\s*(\S+)$""").find(s)?.let { unit = it.groupValues[1].uppercase(); s = s.substring(0, it.range.first) }
            val z = zip?.take(5)?.takeIf { it.isNotEmpty() }
            return AddressMatch(s.uppercase(), unit, city, z, parcelId?.takeIf { it.isNotEmpty() }, GeoPoint(lon, lat))
        }
    }
    @Serializable
    data class Prefs(
        @SerialName("weekly_email") val weeklyEmail: Boolean = true,
        @SerialName("alert_email") val alertEmail: List<String> = emptyList(),
        @SerialName("push_topics") val pushTopics: List<String> = emptyList(),
        @SerialName("radius_mi") val radiusMi: Double = 1.0,
        val topics: List<String> = emptyList(),
    )
    @Serializable
    data class Choices(
        val topics: Map<String, String> = emptyMap(),
        @SerialName("radius_mi") val radiusMi: List<Double> = emptyList(),
        @SerialName("push_topics") val pushTopics: Map<String, String> = emptyMap(),
        @SerialName("alert_email") val alertEmail: Map<String, String> = emptyMap(),
    )

    companion object {
        fun decode(json: String): AccountMe = BCJson.decodeFromString(serializer(), json)
        val topicOrder = listOf("meetings", "events", "projects", "notices", "food", "business")
        val pushOrder = listOf("weather", "evacuation", "shelters", "water", "roads", "agenda")
        val alertEmailOrder = listOf("evacuation", "water", "weather", "shelters")
        val radii = listOf(0.25, 0.5, 1.0, 2.0, 5.0)
        fun radiusLabel(r: Double): String = when (r) {
            0.25 -> "A quarter mile"; 0.5 -> "Half a mile"; 1.0 -> "1 mile"; else -> "${r.toInt()} miles"
        }
    }
}

/** Talks to /api/account with the session token the app keeps in encrypted storage. */
class AccountClient(var token: String?, val platform: String = "android", private val baseURL: String = BayCountyClient.SITE) {
    sealed class AccountError(message: String) : IOException(message) {
        class Server(message: String, val code: Int) : AccountError(message)
        class SignedOut : AccountError("Sign in first.")
    }

    /** The URL, headers and body of one call, so tests can check them without the network. */
    data class Request(val url: String, val headers: Map<String, String>, val body: String?)

    fun request(action: String, body: JsonObject?): Request {
        val h = mutableMapOf<String, String>()
        token?.let { h["Authorization"] = "Bearer $it" }
        if (body != null) h["Content-Type"] = "application/json"
        return Request("$baseURL/api/account?action=$action", h, body?.toString())
    }

    private suspend fun call(action: String, body: JsonObject? = null): String = withContext(Dispatchers.IO) {
        val r = request(action, body)
        val conn = URL(r.url).openConnection() as HttpURLConnection
        conn.connectTimeout = 15000; conn.readTimeout = 30000; conn.useCaches = false
        r.headers.forEach { (k, v) -> conn.setRequestProperty(k, v) }
        try {
            if (r.body != null) {
                conn.requestMethod = "POST"; conn.doOutput = true
                conn.outputStream.use { it.write(r.body.toByteArray()) }
            }
            val code = conn.responseCode
            if (code == 401) throw AccountError.SignedOut()
            val text = (if (code == 200) conn.inputStream else conn.errorStream)?.use { it.readBytes().decodeToString() } ?: ""
            if (code != 200) {
                val msg = runCatching { BCJson.parseToJsonElement(text).jsonObject["error"]?.stringValue }.getOrNull()
                throw AccountError.Server(msg ?: "Something went wrong. Try again.", code)
            }
            text
        } finally { conn.disconnect() }
    }

    suspend fun start(email: String) { call("start", buildJsonObject { put("email", email); put("client", platform) }) }
    suspend fun verify(email: String, code: String): AccountMe {
        val me = AccountMe.decode(call("verify", buildJsonObject { put("email", email); put("code", code); put("client", platform) }))
        token = me.token
        return me
    }
    suspend fun me(): AccountMe = AccountMe.decode(call("me"))
    suspend fun feed(): NearbyFeed = NearbyFeed.decode(call("feed"))
    suspend fun saveHome(address: String, lat: Double?, lon: Double?): AccountMe = AccountMe.decode(call("home", buildJsonObject {
        put("address", address)
        if (lat != null && lon != null) { put("lat", lat); put("lon", lon) }
    }))
    suspend fun removeHome(): AccountMe = AccountMe.decode(call("home_delete", JsonObject(emptyMap())))
    suspend fun save(p: AccountMe.Prefs): AccountMe = AccountMe.decode(call("prefs", buildJsonObject {
        put("weekly_email", p.weeklyEmail)
        putJsonArray("alert_email") { p.alertEmail.forEach { add(it) } }
        putJsonArray("push_topics") { p.pushTopics.forEach { add(it) } }
        put("radius_mi", p.radiusMi)
        putJsonArray("topics") { p.topics.forEach { add(it) } }
    }))
    suspend fun saveFirstName(name: String): AccountMe = AccountMe.decode(call("profile", buildJsonObject { put("first_name", name) }))
    suspend fun linkDevice(pushToken: String, appVersion: String?) {
        call("device", buildJsonObject { put("token", pushToken); put("platform", platform); put("app_version", appVersion ?: "") })
    }
    suspend fun unlinkDevice(pushToken: String) {
        call("device", buildJsonObject { put("token", pushToken); put("platform", platform); put("off", true) })
    }
    /** Ends the session; with this phone's push token, the phone stops getting alerts too. */
    suspend fun logout(pushToken: String? = null) {
        runCatching { call("logout", buildJsonObject { if (pushToken != null) put("token", pushToken) }) }; token = null
    }
    suspend fun deleteAccount() { call("delete_account", JsonObject(emptyMap())); token = null }
}
