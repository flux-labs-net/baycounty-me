package me.baycounty.app.ui

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.util.LruCache
import androidx.compose.runtime.Composable
import androidx.compose.runtime.produceState
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URL

/** Official photos (small WebP squares from baycounty.me/photos/people/), kept in memory once loaded. */
private object PhotoCache {
    val bitmaps = object : LruCache<String, Bitmap>(8 * 1024 * 1024) {
        override fun sizeOf(key: String, value: Bitmap) = value.byteCount
    }

    suspend fun load(url: String): Bitmap? = bitmaps.get(url) ?: withContext(Dispatchers.IO) {
        runCatching {
            val c = URL(url).openConnection() as HttpURLConnection
            c.connectTimeout = 10_000
            c.readTimeout = 15_000
            try {
                c.inputStream.use { BitmapFactory.decodeStream(it) }
            } finally {
                c.disconnect()
            }
        }.getOrNull()?.also { bitmaps.put(url, it) }
    }
}

/** The photo at [url] once it loads, or null while loading, offline or when there is no photo. */
@Composable
fun rememberRemotePhoto(url: String?): ImageBitmap? {
    val state = produceState<ImageBitmap?>(initialValue = url?.let { PhotoCache.bitmaps.get(it)?.asImageBitmap() }, url) {
        if (url != null && value == null) value = PhotoCache.load(url)?.asImageBitmap()
    }
    return state.value
}
