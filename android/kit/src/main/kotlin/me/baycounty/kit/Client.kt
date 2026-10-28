package me.baycounty.kit

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL
import java.net.URLEncoder
import java.time.Instant

/**
 * Reads BayCounty.me.
 *
 * Datasets come from the static `/downloads/<id>.json` files the site publishes on every build. Search uses
 * `/api/v1/search`. Every response is cached on disk with its ETag, revalidated on the next request, and used
 * as-is when the device is offline. A bundled seed covers the very first launch.
 */
class BayCountyClient(
    private val baseURL: String = SITE,
    private val cacheDirectory: File? = null,
    /** Returns a bundled copy of a file by its name (for example "tax.json"), or null. */
    private val seed: (String) -> ByteArray? = { null },
) {
    enum class Freshness { LIVE, CACHED, BUNDLED }

    class Response(val data: ByteArray, val freshness: Freshness, val fetchedAt: Instant?)

    sealed class ClientError(message: String) : IOException(message) {
        class Unavailable(path: String) : ClientError("Couldn't load $path and there's no saved copy yet.")
        class Http(val code: Int) : ClientError(
            if (code == 429) "Too many searches this minute. Try again shortly." else "The site returned an error ($code)."
        )
    }

    private val lock = Any()

    init { cacheDirectory?.mkdirs() }

    // Endpoints

    suspend fun catalog(): Pair<Catalog, Freshness> {
        val r = get("/downloads/index.json")
        return BCJson.decodeFromString(Catalog.serializer(), r.data.decodeToString()) to r.freshness
    }

    suspend fun rows(dataset: DatasetInfo): Pair<List<Row>, Freshness> = rowsAt(dataset.json)
    suspend fun rows(datasetID: String): Pair<List<Row>, Freshness> = rowsAt("/downloads/$datasetID.json")

    /** One restaurant's inspections, newest first: the API's filtered rows, or (offline) the full download filtered here. */
    suspend fun restaurantInspections(license: String): List<Row> = try {
        Restaurants.inspections(Row.decodeRows(get(Restaurants.inspectionsPath(license)).data), license)
    } catch (e: Exception) {
        Restaurants.inspections(rows("restaurant-inspections").first, license)
    }

    suspend fun governments(): Pair<List<Government>, Freshness> =
        rows("government-profiles").let { (r, f) -> r.map { Government(it) } to f }

    suspend fun meetings(): Pair<List<Meeting>, Freshness> =
        rows("meetings").let { (r, f) -> r.map { Meeting(it) } to f }

    suspend fun search(query: String, limit: Int = 40): List<SearchResult> = withContext(Dispatchers.IO) {
        val q = URLEncoder.encode(query, "UTF-8")
        val conn = URL("$baseURL/api/v1/search?q=$q&limit=$limit").openConnection() as HttpURLConnection
        conn.connectTimeout = 15000; conn.readTimeout = 20000
        try {
            val code = conn.responseCode
            if (code != 200) throw ClientError.Http(code)
            val body = conn.inputStream.use { it.readBytes() }
            BCJson.decodeFromString(SearchResponse.serializer(), body.decodeToString()).data
        } finally { conn.disconnect() }
    }

    /** One address's utilities and pickup days from `/api/v1/utilities`. Not cached. */
    suspend fun utilities(point: GeoPoint): UtilityLookup = withContext(Dispatchers.IO) {
        val conn = URL("$baseURL/api/v1/utilities?lat=${"%.6f".format(java.util.Locale.US, point.y)}&lon=${"%.6f".format(java.util.Locale.US, point.x)}").openConnection() as HttpURLConnection
        conn.connectTimeout = 15000; conn.readTimeout = 25000
        conn.useCaches = false
        try {
            val code = conn.responseCode
            if (code != 200) throw ClientError.Http(code)
            UtilityLookup.decode(conn.inputStream.use { it.readBytes() }.decodeToString())
        } finally { conn.disconnect() }
    }

    private suspend fun rowsAt(path: String): Pair<List<Row>, Freshness> {
        val r = get(path)
        return Row.decodeList(r.data) to r.freshness
    }

    // Conditional GET with disk cache

    suspend fun get(path: String): Response = withContext(Dispatchers.IO) {
        val url = URI(baseURL + "/").resolve(path.removePrefix("/").let { if (path.startsWith("http")) path else it }).toURL()
        val cached = readCache(path)
        try {
            val conn = url.openConnection() as HttpURLConnection
            conn.connectTimeout = 15000; conn.readTimeout = 20000
            conn.useCaches = false
            cached?.etag?.let { conn.setRequestProperty("If-None-Match", it) }
            try {
                when (val code = conn.responseCode) {
                    200 -> {
                        val data = conn.inputStream.use { it.readBytes() }
                        writeCache(path, data, conn.getHeaderField("ETag"))
                        Response(data, Freshness.LIVE, Instant.now())
                    }
                    304 -> if (cached != null) {
                        touchCache(path); Response(cached.data, Freshness.LIVE, Instant.now())
                    } else offlineCopy(path, null) ?: throw ClientError.Http(code)
                    else -> offlineCopy(path, cached) ?: throw ClientError.Http(code)
                }
            } finally { conn.disconnect() }
        } catch (e: ClientError) {
            throw e
        } catch (e: Exception) {
            offlineCopy(path, cached) ?: throw ClientError.Unavailable(path)
        }
    }

    private class Cached(val data: ByteArray, val etag: String?, val date: Instant?)

    private fun offlineCopy(path: String, cached: Cached?): Response? {
        if (cached != null) return Response(cached.data, Freshness.CACHED, cached.date)
        val name = path.substringAfterLast('/')
        return seed(name)?.let { Response(it, Freshness.BUNDLED, null) }
    }

    private fun cacheFiles(path: String): Pair<File, File>? {
        val dir = cacheDirectory ?: return null
        val key = path.replace("/", "_")
        return File(dir, key) to File(dir, "$key.etag")
    }

    private fun readCache(path: String): Cached? = synchronized(lock) {
        val (body, etagFile) = cacheFiles(path) ?: return null
        if (!body.exists()) return null
        val data = runCatching { body.readBytes() }.getOrNull() ?: return null
        val etag = runCatching { etagFile.readText().trim() }.getOrNull()?.takeIf { it.isNotEmpty() }
        Cached(data, etag, Instant.ofEpochMilli(body.lastModified()))
    }

    private fun writeCache(path: String, data: ByteArray, etag: String?): Unit = synchronized(lock) {
        val (body, etagFile) = cacheFiles(path) ?: return
        runCatching {
            val tmp = File(body.parentFile, body.name + ".tmp")
            tmp.writeBytes(data); tmp.renameTo(body)
            if (etag != null) etagFile.writeText(etag) else etagFile.delete()
        }
        Unit
    }

    private fun touchCache(path: String): Unit = synchronized(lock) {
        cacheFiles(path)?.first?.setLastModified(System.currentTimeMillis()); Unit
    }

    companion object {
        const val SITE = "https://baycounty.me"

        fun absolute(pathOrURL: String): String =
            if (pathOrURL.startsWith("http")) pathOrURL else SITE + (if (pathOrURL.startsWith("/")) "" else "/") + pathOrURL

        /** Calendar feed of upcoming meetings, for "Subscribe in Calendar". */
        fun meetingsCalendarURL(gov: String? = null): String =
            "webcal://baycounty.me/api/v1/meetings.ics" + (gov?.let { "?gov=$it" } ?: "")

        /** The same feed over https, for devices with no webcal handler. */
        fun meetingsCalendarHttpsURL(gov: String? = null): String =
            "$SITE/api/v1/meetings.ics" + (gov?.let { "?gov=$it" } ?: "")
    }
}
