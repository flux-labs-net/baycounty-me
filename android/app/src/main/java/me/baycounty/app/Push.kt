package me.baycounty.app

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.google.firebase.FirebaseApp
import com.google.firebase.FirebaseOptions
import com.google.firebase.messaging.FirebaseMessaging
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import me.baycounty.kit.BayCountyClient
import me.baycounty.kit.Emergency
import java.net.HttpURLConnection
import java.net.URL

/** Phone notifications through Firebase Cloud Messaging. The phone signs up at https://baycounty.me/api/push with the
 *  topics, cities and saved place chosen on the Emergencies screen; only the token, the choices and a rounded map point
 *  are sent. Firebase is set up from build settings (FCM_* environment variables at build time), so a build without
 *  them still works, with phone alerts off. */
object Push {
    const val CHANNEL = "emergency"
    private const val PREFS = "push"

    var token by mutableStateOf<String?>(null); private set
    var status by mutableStateOf<String?>(null)
    var enabled by mutableStateOf(false); private set
    var topics by mutableStateOf(Emergency.defaultTopics); private set
    var govs by mutableStateOf<List<String>>(emptyList()); private set
    var radius by mutableStateOf(1.0); private set
    private var loaded = false

    /** True when this build has Firebase settings. */
    val configured: Boolean get() = BuildConfig.FCM_APP_ID.isNotBlank()

    fun load(context: Context) {
        if (loaded) return
        val p = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        enabled = p.getBoolean("enabled", false)
        topics = p.getStringSet("topics", null)?.toSet() ?: Emergency.defaultTopics
        govs = p.getString("govs", "")!!.split(",").filter { it.isNotBlank() }
        radius = p.getFloat("radius", 1f).toDouble()
        token = p.getString("token", null)
        loaded = true
    }

    private fun save(context: Context) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putBoolean("enabled", enabled).putStringSet("topics", topics).putString("govs", govs.joinToString(","))
            .putFloat("radius", radius.toFloat()).putString("token", token).apply()
    }

    /** Called once from the Application: the notification channel, and Firebase when this build has its settings. */
    fun setUp(context: Context) {
        if (Build.VERSION.SDK_INT >= 26) {
            val ch = NotificationChannel(CHANNEL, "Emergencies and alerts", NotificationManager.IMPORTANCE_HIGH)
            ch.description = "Weather warnings, evacuation orders, shelter openings, boil-water notices and agenda items near you"
            context.getSystemService(NotificationManager::class.java)?.createNotificationChannel(ch)
        }
        if (configured && FirebaseApp.getApps(context).isEmpty()) {
            runCatching {
                FirebaseApp.initializeApp(context, FirebaseOptions.Builder()
                    .setApplicationId(BuildConfig.FCM_APP_ID).setApiKey(BuildConfig.FCM_API_KEY)
                    .setProjectId(BuildConfig.FCM_PROJECT_ID).setGcmSenderId(BuildConfig.FCM_SENDER_ID).build())
            }
        }
    }

    fun setTopic(context: Context, id: String, on: Boolean) { topics = if (on) topics + id else topics - id; save(context) }
    fun toggleGov(context: Context, id: String) { govs = if (id in govs) govs - id else govs + id; save(context) }
    fun setRadius(context: Context, r: Double) { radius = r; save(context) }

    /** Turn alerts on (after the notification permission was granted): get the token, then sign up. */
    fun enable(context: Context, home: me.baycounty.kit.GeoPoint?, onDone: () -> Unit = {}) {
        load(context)
        if (!configured || FirebaseApp.getApps(context).isEmpty()) { status = "Phone alerts aren't set up in this version of the app yet."; return }
        enabled = true; save(context)
        FirebaseMessaging.getInstance().token.addOnSuccessListener { t -> token = t; save(context); onDone() }
            .addOnFailureListener { status = "Couldn't turn on alerts. Try again later." }
    }

    suspend fun disable(context: Context) {
        enabled = false; save(context)
        val t = token ?: return
        post(Emergency.unregisterBody(t, "android"))
        status = "Alerts turned off."
    }

    /** Send the current choices. `home` is the saved address's point, used for agenda items near me. */
    suspend fun sync(context: Context, home: me.baycounty.kit.GeoPoint?) {
        load(context)
        val t = token ?: return
        if (!enabled) return
        val ver = runCatching { context.packageManager.getPackageInfo(context.packageName, 0).versionName }.getOrNull()
        val ok = post(Emergency.pushBody(t, "android", topics, govs, home?.y, home?.x, radius, ver))
        status = if (ok) "Alerts are on for this phone." else "Couldn't reach BayCounty.me. Your choices will be sent next time."
    }

    private suspend fun post(body: String): Boolean = withContext(Dispatchers.IO) {
        runCatching {
            val c = URL(BayCountyClient.SITE + "/api/push").openConnection() as HttpURLConnection
            c.requestMethod = "POST"; c.doOutput = true; c.connectTimeout = 15000; c.readTimeout = 15000
            c.setRequestProperty("Content-Type", "application/json")
            c.outputStream.use { it.write(body.toByteArray()) }
            val code = c.responseCode
            c.disconnect()
            code == 200
        }.getOrDefault(false)
    }

    fun onNewToken(context: Context, t: String) {
        load(context); token = t; save(context)
    }
}

/** Receives new tokens and shows notifications that arrive while the app is open (Firebase shows the rest itself). */
class PushService : FirebaseMessagingService() {
    override fun onNewToken(token: String) {
        Push.onNewToken(this, token)
        val app = application as? BayCountyApp ?: return
        app.store.scope.launch { Push.sync(this@PushService, app.store.home?.point) }
    }

    override fun onMessageReceived(message: RemoteMessage) {
        val n = message.notification ?: return
        val url = message.data["url"]
        val open = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
            if (url != null) putExtra("url", url)
        }
        val pi = PendingIntent.getActivity(this, (message.data["notice_id"] ?: "").hashCode(), open, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val b = NotificationCompat.Builder(this, Push.CHANNEL)
            .setSmallIcon(R.drawable.ic_launcher_monochrome).setContentTitle(n.title).setContentText(n.body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(n.body)).setAutoCancel(true).setContentIntent(pi)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
        runCatching { NotificationManagerCompat.from(this).notify((message.data["notice_id"] ?: "").hashCode(), b.build()) }
    }
}
