package me.baycounty.staff

import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import me.baycounty.kit.Staff
import me.baycounty.kit.StaffAlert
import me.baycounty.kit.StaffBoard
import me.baycounty.kit.StaffClient
import me.baycounty.kit.StaffDemo
import me.baycounty.kit.StaffFlag
import me.baycounty.kit.StaffHome
import me.baycounty.kit.StaffMe
import me.baycounty.kit.StaffOverview
import me.baycounty.kit.StaffPost
import me.baycounty.kit.StaffPosts
import me.baycounty.kit.StaffReach
import me.baycounty.kit.StaffRecordPreview
import me.baycounty.kit.StaffSubmissions
import me.baycounty.kit.StaffWorkspace

/** Everything the staff app shows, from /api/gov. With [demo] (screenshots, store review) it shows made-up answers
 *  from staff-demo.json and never calls the server. Same behavior as the iOS StaffStore. */
class StaffModel(private val tokens: TokenStore, val demo: StaffDemo? = null, asStaff: Boolean = false, asOfficial: Boolean = false) {
    private val client = StaffClient(if (demo == null) tokens.read() else null)

    var me by mutableStateOf<StaffMe?>(null); private set
    var overview by mutableStateOf<StaffOverview?>(null); private set
    var home by mutableStateOf<StaffHome?>(null); private set
    var alerts by mutableStateOf<List<StaffAlert>>(emptyList()); private set
    var notices by mutableStateOf<StaffPosts?>(null); private set
    var flags by mutableStateOf<List<StaffFlag>>(emptyList()); private set
    var submissions by mutableStateOf<StaffSubmissions?>(null); private set
    /** The board dashboard, for an elected official (role official). */
    var board by mutableStateOf<StaffBoard?>(null); private set
    var loading by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null)
    var workspaceId by mutableStateOf<String?>(null)
    private var token by mutableStateOf(client.token)

    val signedIn get() = demo != null || token != null
    val isOwner get() = me?.admin == true
    val workspace: StaffWorkspace? get() = me?.workspaces?.firstOrNull { it.id == workspaceId }
    val role get() = workspace?.role ?: if (isOwner) "owner" else "viewer"
    fun can(need: String) = Staff.can(role, need)
    val isOfficial get() = role == "official"
    val alertKinds get() = me?.alertKinds ?: emptyMap()
    val noticeKinds get() = me?.noticeKinds ?: emptyMap()

    init {
        if (demo != null) {
            overview = demo.overview; home = demo.home; alerts = demo.alerts.alerts; notices = demo.notices; submissions = demo.submissions
            if (asOfficial) {
                // An elected commissioner's view: their board dashboard (made-up names).
                me = demo.me.copy(email = "privera@example.gov", admin = false,
                    workspaces = listOf(StaffWorkspace("lh", "City of Lynn Haven", false, "official", "pat-rivera")))
                workspaceId = "lh"; board = demo.board; flags = emptyList()
            } else if (asStaff) {
                me = demo.me.copy(email = "utilities@example.gov", admin = false,
                    workspaces = listOf(StaffWorkspace("lh", "City of Lynn Haven", false, "alert_sender")))
                workspaceId = "lh"
                flags = demo.flags.flags.filter { it.workspaceId == "lh" }
            } else {
                me = demo.me; flags = demo.flags.flags
            }
        }
    }

    suspend fun login(email: String): Boolean {
        error = null
        return try { client.login(email); true } catch (e: Exception) { error = e.message; false }
    }

    suspend fun verify(email: String, code: String): Boolean {
        error = null
        return try {
            val m = client.verify(email, code)
            m.token?.let { tokens.save(it) }
            token = client.token
            me = m; pickDefault(); refresh(); true
        } catch (e: Exception) { error = e.message; false }
    }

    suspend fun signOut() {
        if (demo == null) client.logout()
        tokens.save(null); token = null
        me = null; overview = null; home = null; alerts = emptyList(); notices = null; flags = emptyList(); submissions = null; board = null; workspaceId = null
    }

    private fun pickDefault() {
        val m = me ?: return
        if (m.admin) workspaceId = null else if (workspace == null) workspaceId = m.workspaces.firstOrNull()?.id
    }

    suspend fun refresh() {
        if (demo != null || token == null) return
        loading = true
        try {
            if (me == null) { me = client.me(); pickDefault() }
            loadCurrent()
        } catch (e: Exception) { handle(e) } finally { loading = false }
    }

    suspend fun open(id: String?) {
        workspaceId = id
        if (demo != null) return
        loading = true
        try { loadCurrent() } catch (e: Exception) { handle(e) } finally { loading = false }
    }

    private suspend fun loadCurrent() = coroutineScope {
        val ws = workspaceId
        if (ws != null) {
            val h = async { client.home(ws) }; val a = async { client.alerts(ws) }; val n = async { client.notices(ws) }; val f = async { client.flags(ws) }
            home = h.await(); alerts = a.await().alerts; notices = n.await(); flags = f.await().flags
            submissions = if (can("submit")) runCatching { client.submissions(ws) }.getOrNull() else null
            board = if (isOfficial) client.board(ws) else null
        } else if (isOwner) {
            val o = async { client.overview() }; val f = async { client.reviewFlags("all") }
            overview = o.await(); flags = f.await().flags
            home = null; alerts = emptyList(); notices = null; submissions = null
        }
    }

    private fun handle(e: Exception) {
        if (e is StaffClient.StaffError.SignedOut) { tokens.save(null); token = null; me = null }
        error = e.message
    }

    suspend fun reach(kind: String, countywide: Boolean): StaffReach? {
        val ws = workspaceId ?: return null
        if (demo != null) return StaffReach("water", if (countywide) 9120 else 1240, if (countywide) 3810 else 512)
        return runCatching { client.reach(ws, kind, countywide) }.getOrNull()
    }

    /** Returns the server's message, or throws with the reason it didn't go. */
    suspend fun sendAlert(kind: String, title: String, message: String, instruction: String, severity: String, countywide: Boolean, hours: Int, geometry: String? = null): String {
        val ws = workspaceId ?: throw IllegalStateException("Pick a government first.")
        if (demo != null) return "Sent."
        val m = client.sendAlert(ws, kind, title, message, instruction, severity, countywide, hours, geometry)
        loadCurrent()
        return m
    }

    suspend fun confirm(a: StaffAlert) = act { client.confirmAlert(it, a.id) }
    suspend fun end(a: StaffAlert) = act { client.endAlert(it, a.id) }
    suspend fun withdraw(p: StaffPost) = act { client.withdrawNotice(it, p.id) }
    suspend fun saveNotice(id: Int?, kind: String, title: String, text: String, eventDate: String?) = act { client.saveNotice(it, id, kind, title, text, eventDate) }
    suspend fun answer(f: StaffFlag, status: String, reply: String): String? {
        if (demo != null) return null
        return try { client.answerFlag(f.id, status, reply); loadCurrent(); null } catch (e: Exception) { e.message }
    }

    /** Reads a file and saves it as waiting; nothing is public until [publishRecords]. Throws with the reason it can't be read. */
    suspend fun previewRecords(kind: String, filename: String, content: ByteArray): StaffRecordPreview {
        val ws = workspaceId ?: throw IllegalStateException("Pick a government first.")
        if (content.size > Staff.MAX_INLINE_BYTES) throw IllegalStateException("That file is over 3 MB. Send it from the web workspace or by email instead.")
        if (demo != null) return demoPreview(kind)
        val p = client.previewRecords(ws, kind, filename, content)
        submissions = runCatching { client.submissions(ws) }.getOrNull()
        return p
    }
    /** The made-up preview screenshots show. */
    fun demoPreview(kind: String) = StaffRecordPreview("c9", kind, ok = true, label = "Contracts awarded", rowCount = 6, parsedTotal = 1284310.5, skipped = 1,
        alreadyOnSite = 2, withheld = 0, period = StaffRecordPreview.Period("2026-10-02", "2026-10-27"))
    suspend fun publishRecords(id: String) = act { client.publishRecords(it, id) }
    suspend fun withdrawRecords(id: String) = act { client.withdrawRecords(it, id) }

    /** Runs one change in the open workspace; null when it worked, otherwise why not. */
    private suspend fun act(f: suspend (String) -> Unit): String? {
        val ws = workspaceId ?: return "Pick a government first."
        if (demo != null) return null
        return try { f(ws); loadCurrent(); null } catch (e: Exception) { e.message }
    }

    companion object {
        fun demoFrom(context: Context): StaffDemo = StaffDemo.decode(context.assets.open("staff-demo.json").use { it.readBytes().decodeToString() })
    }
}

/** The session token, in this app's private storage only (backups are off for the staff app). */
interface TokenStore {
    fun read(): String?
    fun save(token: String?)
}

class PrefsTokenStore(context: Context) : TokenStore {
    private val prefs = context.getSharedPreferences("staff_session", Context.MODE_PRIVATE)
    override fun read(): String? = prefs.getString("token", null)
    override fun save(token: String?) { prefs.edit().apply { if (token == null) remove("token") else putString("token", token) }.apply() }
}

object NoTokens : TokenStore {
    override fun read(): String? = null
    override fun save(token: String?) {}
}

