package me.baycounty.kit

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL
import java.time.DayOfWeek
import java.time.LocalDate
import java.time.temporal.TemporalAdjusters

/**
 * Anonymous app usage counts (POST /api/app-usage, shown in /admin > App usage). The iOS app's AppUsage.
 *
 * The app counts how often it's opened and which screens are viewed, on the phone. Once a day it sends those totals
 * with the platform, app version and whether this is the phone's first check-in ever, this month and this week, then
 * starts counting again. No device id, account, address or search is sent, so a phone can be counted but not followed.
 * The resident can turn it off ([enabled]), and nothing is counted or sent while it's off.
 */
class AppUsage(private val store: Store, private val version: String, private val platform: String = "android") {
    /** Where the counts live on the phone (SharedPreferences in the app, a map in tests). */
    interface Store {
        fun getString(key: String): String?
        fun putString(key: String, value: String?)
    }

    companion object {
        const val ENABLED_KEY = "usage.enabled"
        private const val LAST = "usage.last"
        private const val EVER = "usage.ever"
        private const val OPENS = "usage.opens"
        private const val SCREENS = "usage.screens"
        private val NAME = Regex("^[a-z0-9][a-z0-9:/_-]{0,59}$")

        /** Lowercase letters, digits and `:/_-`, at most 60 characters, or null. */
        fun screenName(raw: String): String? = raw.lowercase().takeIf { NAME.matches(it) }
    }

    private val lock = Any()

    /** On unless the resident turned it off. */
    var enabled: Boolean
        get() = store.getString(ENABLED_KEY) != "false"
        set(on) = synchronized(lock) {
            store.putString(ENABLED_KEY, on.toString())
            if (!on) { store.putString(OPENS, null); store.putString(SCREENS, null) }
        }

    private fun screens(): Map<String, Int> = runCatching {
        Json.parseToJsonElement(store.getString(SCREENS) ?: "{}").let { it as JsonObject }.mapValues { it.value.jsonPrimitive.int }
    }.getOrDefault(emptyMap())

    /** The app came to the front. */
    fun opened() {
        if (!enabled) return
        synchronized(lock) { store.putString(OPENS, ((store.getString(OPENS)?.toIntOrNull() ?: 0) + 1).toString()) }
    }

    /** A screen was shown. [raw] is a short screen name such as "restaurants" or "dataset/votes". */
    fun viewed(raw: String) {
        if (!enabled) return
        val name = screenName(raw) ?: return
        synchronized(lock) {
            val s = screens().toMutableMap()
            if (s[name] == null && s.size >= 120) return
            s[name] = (s[name] ?: 0) + 1
            store.putString(SCREENS, JsonObject(s.mapValues { JsonPrimitive(it.value) }).toString())
        }
    }

    /** Today's check-in body, or null when it's off or this phone already checked in today. */
    fun checkIn(today: LocalDate = LocalDate.now()): JsonObject? {
        if (!enabled) return null
        synchronized(lock) {
            val last = store.getString(LAST)?.let { runCatching { LocalDate.parse(it) }.getOrNull() }
            if (last == today) return null
            val monday = { d: LocalDate -> d.with(TemporalAdjusters.previousOrSame(DayOfWeek.MONDAY)) }
            val sameMonth = last != null && last.year == today.year && last.month == today.month
            val sameWeek = last != null && monday(last) == monday(today)
            return buildJsonObject {
                put("platform", platform)
                put("version", version)
                put("new", store.getString(EVER) != "true")
                put("month", !sameMonth)
                put("week", !sameWeek)
                put("opens", maxOf(1, store.getString(OPENS)?.toIntOrNull() ?: 0))
                put("screens", JsonObject(screens().mapValues { JsonPrimitive(it.value) }))
            }
        }
    }

    /** The check-in went through: remember the day and start counting again. */
    fun sent(today: LocalDate = LocalDate.now()) = synchronized(lock) {
        store.putString(LAST, today.toString())
        store.putString(EVER, "true")
        store.putString(OPENS, null)
        store.putString(SCREENS, null)
    }

    /** Sends today's check-in if one is due. Errors are ignored; the next launch tries again. */
    suspend fun send(baseURL: String = BayCountyClient.SITE) = withContext(Dispatchers.IO) {
        val body = checkIn() ?: return@withContext
        runCatching {
            val c = URL("$baseURL/api/app-usage").openConnection() as HttpURLConnection
            c.requestMethod = "POST"; c.doOutput = true; c.connectTimeout = 15000; c.readTimeout = 15000
            c.setRequestProperty("Content-Type", "application/json")
            c.outputStream.use { it.write(body.toString().toByteArray()) }
            val ok = c.responseCode in 200..299
            c.disconnect()
            if (ok) sent()
        }
    }
}

/**
 * Links into BayCounty.me opened from the app carry `utm_source=android-app` and `utm_medium=app`, so the website's
 * analytics shows them as app traffic instead of "Unknown".
 */
object AppLinks {
    fun tagged(url: String, source: String = "android-app"): String {
        val u = runCatching { URI(url) }.getOrNull() ?: return url
        val host = u.host?.lowercase() ?: return url
        if (host != "baycounty.me" && host != "www.baycounty.me") return url
        val q = u.rawQuery
        if (q != null && q.split('&').any { it.substringBefore('=') == "utm_source" }) return url
        val add = "utm_source=$source&utm_medium=app"
        val query = if (q.isNullOrEmpty()) add else "$q&$add"
        return buildString {
            append(u.scheme).append("://").append(u.rawAuthority).append(u.rawPath ?: "")
            append('?').append(query)
            u.rawFragment?.let { append('#').append(it) }
        }
    }
}
