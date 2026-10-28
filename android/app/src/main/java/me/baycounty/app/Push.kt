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
import kotlinx.coroutines.launch

/** Phone notifications through Firebase Cloud Messaging. Alerts need a BayCounty.me account: the switch lives in
 *  My home > Settings, and the phone is tied to the account (POST /api/account device), so its alerts follow the home
 *  and choices saved there. Firebase is set up from build settings (FCM_* environment variables at build time), so a
 *  build without them still works, with phone alerts off. */
object Push {
    const val CHANNEL = "emergency"
    private const val PREFS = "push"

    var token by mutableStateOf<String?>(null); private set
    var status by mutableStateOf<String?>(null)
    var enabled by mutableStateOf(false); private set
    private var loaded = false

    /** True when this build has Firebase settings. */
    val configured: Boolean get() = BuildConfig.FCM_APP_ID.isNotBlank()

    fun load(context: Context) {
        if (loaded) return
        val p = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        enabled = p.getBoolean("enabled", false)
        token = p.getString("token", null)
        loaded = true
    }

    private fun save(context: Context) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean("enabled", enabled).putString("token", token).apply()
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

    /** Turn alerts on for the signed-in account (after the notification permission was granted): get the token, then
     *  tie this phone to the account. */
    fun enable(context: Context, onToken: () -> Unit) {
        load(context)
        if (!Account.signedIn) { status = "Sign in to get alerts."; return }
        if (!configured || FirebaseApp.getApps(context).isEmpty()) { status = "Phone alerts aren't set up in this version of the app yet."; return }
        enabled = true; status = null; save(context)
        FirebaseMessaging.getInstance().token.addOnSuccessListener { t -> token = t; save(context); onToken() }
            .addOnFailureListener { status = "Couldn't turn on alerts. Try again later." }
    }

    suspend fun disable(context: Context) {
        enabled = false; save(context)
        token?.let { Account.unlinkPhone(it) }
        status = "Alerts are off on this phone."
    }

    /** Signing out turns alerts off: the server drops this phone in the same call (Account.signOut). */
    fun signedOut(context: Context) { load(context); enabled = false; status = null; save(context) }

    fun onNewToken(context: Context, t: String) {
        load(context); token = t; save(context)
    }
}

/** Receives new tokens and shows notifications that arrive while the app is open (Firebase shows the rest itself). */
class PushService : FirebaseMessagingService() {
    override fun onNewToken(token: String) {
        Push.onNewToken(this, token)
        val app = application as? BayCountyApp ?: return
        app.store.scope.launch { Account.linkPhone(this@PushService) }
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
