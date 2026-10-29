package me.baycounty.app

import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import me.baycounty.kit.AccountClient
import me.baycounty.kit.AccountMe
import me.baycounty.kit.AddressMatch
import me.baycounty.kit.NearbyFeed

/** The resident's BayCounty.me account on this phone (the iOS AccountManager): signs in with an emailed code, keeps
 *  the session token in app-private storage that isn't backed up, and loads the saved home, choices and the
 *  "near my home" feed from https://baycounty.me/api/account. */
object Account {
    private const val PREFS = "account"
    private val client = AccountClient(null)
    private var loaded = false

    var me by mutableStateOf<AccountMe?>(null); private set
    var feed by mutableStateOf<NearbyFeed?>(null); private set
    var error by mutableStateOf<String?>(null)
    var signedIn by mutableStateOf(false); private set

    fun load(context: Context) {
        if (loaded) return
        client.token = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString("token", null)
        signedIn = client.token != null
        loaded = true
    }

    private fun saveToken(context: Context, t: String?) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().apply { if (t == null) remove("token") else putString("token", t) }.apply()
        client.token = t
        signedIn = t != null
    }

    suspend fun start(email: String): Boolean {
        error = null
        return try { client.start(email); true } catch (e: Exception) { error = e.message; false }
    }

    suspend fun verify(context: Context, email: String, code: String): Boolean {
        error = null
        return try {
            val m = client.verify(email, code)
            saveToken(context, m.token)
            me = m
            linkPhone(context)
            loadFeed(context)
            true
        } catch (e: Exception) { error = e.message; false }
    }

    suspend fun refresh(context: Context) {
        load(context)
        if (!signedIn || client.token == DEMO) return
        guard(context) { me = client.me(); loadFeed(context) }
    }

    suspend fun loadFeed(context: Context) {
        if (me?.home == null) { feed = null; return }
        guard(context) { feed = client.feed() }
    }

    suspend fun saveHome(context: Context, m: AddressMatch) = guard(context) {
        me = client.saveHome(m.display + (m.zip?.let { " $it" } ?: ""), m.point.y, m.point.x)
        loadFeed(context); linkPhone(context)
    }

    suspend fun removeHome(context: Context) = guard(context) { me = client.removeHome(); feed = null }

    suspend fun save(context: Context, p: AccountMe.Prefs) = guard(context) { me = client.save(p); loadFeed(context); linkPhone(context) }

    suspend fun saveFirstName(context: Context, name: String) = guard(context) { me = client.saveFirstName(name) }

    /** Ties this phone's alerts to the account so they follow the saved home and choices. */
    suspend fun linkPhone(context: Context) {
        Push.load(context)
        val t = Push.token ?: return
        if (!signedIn || !Push.enabled || client.token == DEMO) return
        val ver = runCatching { context.packageManager.getPackageInfo(context.packageName, 0).versionName }.getOrNull()
        Push.status = if (runCatching { client.linkDevice(t, ver) }.isSuccess) "Alerts are on for this phone." else "Couldn't reach BayCounty.me. Try again later."
    }

    suspend fun unlinkPhone(pushToken: String) {
        if (!signedIn || client.token == DEMO) return
        runCatching { client.unlinkDevice(pushToken) }
    }

    /** Alerts need a signed-in phone, so signing out also stops this phone's alerts. */
    suspend fun signOut(context: Context) {
        Push.load(context)
        client.logout(Push.token)
        Push.signedOut(context)
        clear(context)
    }

    suspend fun deleteAccount(context: Context) = guard(context) { client.deleteAccount(); Push.signedOut(context); clear(context) }

    private fun clear(context: Context) { saveToken(context, null); me = null; feed = null }

    private suspend fun guard(context: Context, block: suspend () -> Unit) {
        try { block() } catch (e: AccountClient.AccountError.SignedOut) {
            clear(context); error = "You were signed out. Sign in again."
        } catch (e: kotlinx.coroutines.CancellationException) { throw e } catch (e: Exception) { error = e.message ?: "Something went wrong. Try again." }
    }

    // Screenshots

    private const val DEMO = "demo"

    /** Screenshots show a saved feed for 825 Ohio Ave so the picture doesn't need an account or the live site. */
    fun loadDemo(feedJson: String) {
        feed = NearbyFeed.decode(feedJson)
        me = AccountMe.decode(DEMO_ME)
        client.token = DEMO; signedIn = true; loaded = true
    }

    private val DEMO_ME = """
        {"user":{"email":"resident@example.com"},
         "home":{"label":"Home","address":"825 Ohio Ave","city":"Lynn Haven","zip":"32444","lat":30.2449,"lon":-85.6483,"gov_id":"lh","zone":"D"},
         "prefs":{"weekly_email":true,"alert_email":["evacuation","water"],"push_topics":["weather","evacuation","shelters","water","agenda"],"radius_mi":1,"topics":["meetings","events","projects","notices","food","business"]},
         "devices":1,
         "choices":{"topics":{"meetings":"Public meetings","events":"Things to do","projects":"Building and road work near me","notices":"Public notices","food":"Restaurant inspections in my ZIP","business":"New businesses in my ZIP"},
                    "radius_mi":[0.25,0.5,1,2,5],
                    "push_topics":{"weather":"Weather warnings","evacuation":"Evacuation orders","shelters":"Shelter openings","water":"Boil-water notices","roads":"Full road closures","agenda":"Agenda items near my saved place"},
                    "alert_email":{"evacuation":"Evacuation orders","water":"Boil-water notices","weather":"Weather warnings","shelters":"Shelter openings"}}}
    """.trimIndent()
}
