package me.baycounty.app

import android.content.Context
import android.content.SharedPreferences
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.KSerializer
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer
import me.baycounty.kit.AppUsage
import me.baycounty.kit.AccountabilityConsole
import me.baycounty.kit.AddressMatch
import me.baycounty.kit.AddressModel
import me.baycounty.kit.Amendment3Model
import me.baycounty.kit.BCJson
import me.baycounty.kit.BayCountyClient
import me.baycounty.kit.Catalog
import me.baycounty.kit.DatasetInfo
import me.baycounty.kit.DatasetSpec
import me.baycounty.kit.DonorContracts
import me.baycounty.kit.GISClient
import me.baycounty.kit.GeoPoint
import me.baycounty.kit.Glossary
import me.baycounty.kit.Government
import me.baycounty.kit.Meeting
import me.baycounty.kit.MoneyMap
import me.baycounty.kit.PageInfo
import me.baycounty.kit.PeopleDirectory
import me.baycounty.kit.Row
import me.baycounty.kit.SiteUpdate
import me.baycounty.kit.TaxModel
import me.baycounty.kit.UtilityLookup
import me.baycounty.kit.VendorDirectory
import me.baycounty.kit.accountability
import me.baycounty.kit.appData
import java.io.File
import java.time.Instant

/** App-wide state: the catalog, governments, meetings, any dataset rows loaded so far, and the site's /data/app files. */
class AppStore(context: Context, client: BayCountyClient? = null) {
    private val app = context.applicationContext ?: context
    val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    val client = client ?: BayCountyClient(
        baseURL = apiBase,
        cacheDirectory = File(app.cacheDir, "BayCountyMe"),
        seed = { name -> runCatching { app.assets.open("seed/$name").use { it.readBytes() } }.getOrNull() },
    )
    val gis = GISClient()

    companion object {
        /** Debug builds only: `--es apiBase <url>` points the app at the store screenshot server (store/demo_server.py). */
        var apiBase: String = BayCountyClient.SITE
    }
    private val prefs: SharedPreferences = app.getSharedPreferences("baycounty", Context.MODE_PRIVATE)

    /** Anonymous usage counts: one check-in a day, which the resident can turn off in About. */
    val usage = AppUsage(object : AppUsage.Store {
        override fun getString(key: String) = prefs.getString(key, null)
        override fun putString(key: String, value: String?) { prefs.edit().apply { if (value == null) remove(key) else putString(key, value) }.apply() }
    }, "${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})")
    var shareUsage by mutableStateOf(usage.enabled)
    fun setShareUsage(on: Boolean) { usage.enabled = on; shareUsage = on }

    /** The app came to the front: count it and send today's check-in if one is due. Debug builds (Android Studio runs
     *  and the screenshot workflows) don't send, so they never show up in the counts. */
    fun becameActive() {
        usage.opened()
        if (!BuildConfig.DEBUG) scope.launch { usage.send() }
    }

    var catalog by mutableStateOf<Catalog?>(null); private set
    var governments by mutableStateOf<List<Government>>(emptyList()); private set
    var meetings by mutableStateOf<List<Meeting>>(emptyList()); private set
    val rows = mutableStateMapOf<String, List<Row>>()
    val freshness = mutableStateMapOf<String, BayCountyClient.Freshness>()
    val errors = mutableStateMapOf<String, String>()
    val loading = mutableStateListOf<String>()
    var lastRefresh by mutableStateOf<Instant?>(null); private set

    var taxModel by mutableStateOf<TaxModel?>(null); private set
    var addressModel by mutableStateOf<AddressModel?>(null); private set
    var amendment3 by mutableStateOf<Amendment3Model?>(null); private set
    var glossary by mutableStateOf<Glossary?>(null); private set
    var pages by mutableStateOf<List<PageInfo>>(emptyList()); private set
    var updates by mutableStateOf<List<SiteUpdate>>(emptyList()); private set
    var vendors by mutableStateOf<VendorDirectory?>(null); private set
    var people by mutableStateOf<PeopleDirectory?>(null); private set
    var donorContracts by mutableStateOf<DonorContracts?>(null); private set
    var moneyMap by mutableStateOf<MoneyMap?>(null); private set
    var accountability by mutableStateOf<AccountabilityConsole?>(null); private set

    /** Utility lookups by address id, kept in memory only (never on disk), so going back doesn't ask again. */
    val utilities = mutableStateMapOf<String, UtilityLookup>()

    suspend fun loadUtilities(m: AddressMatch, force: Boolean = false): UtilityLookup {
        if (!force) utilities[m.id]?.let { return it }
        return client.utilities(m.point).also { utilities[m.id] = it }
    }

    /** A glossary term shown in a sheet. */
    var presentedTerm by mutableStateOf<Glossary.Term?>(null)

    @Serializable private data class SavedHome(val address: String, val unit: String?, val community: String?, val zip: String?, val renum: String?, val x: Double, val y: Double)

    /** The saved home address, kept only on this phone. */
    var home by mutableStateOf(loadHome())
        private set

    fun saveHome(m: AddressMatch?) {
        home = m
        prefs.edit().apply {
            if (m == null) remove("home")
            else putString("home", BCJson.encodeToString(SavedHome.serializer(), SavedHome(m.address, m.unit, m.community, m.zip, m.renum, m.point.x, m.point.y)))
        }.apply()
    }

    private fun loadHome(): AddressMatch? = prefs.getString("home", null)?.let { s ->
        runCatching { BCJson.decodeFromString(SavedHome.serializer(), s) }.getOrNull()?.let {
            AddressMatch(it.address, it.unit, it.community, it.zip, it.renum, GeoPoint(it.x, it.y))
        }
    }

    /** The tax district last picked in the calculator (Today shows its bill). */
    var savedDistrict by mutableStateOf(prefs.getString("taxDistrict", "") ?: "")
        private set

    fun saveDistrict(id: String) { savedDistrict = id; prefs.edit().putString("taxDistrict", id).apply() }

    /** True when anything on screen came from a saved or bundled copy rather than the live site. */
    val isShowingSavedData: Boolean get() = freshness.values.any { it != BayCountyClient.Freshness.LIVE }

    suspend fun loadEssentials() {
        coroutineScope {
            listOf(
                async { loadCatalog() }, async { loadGovernments() }, async { loadMeetings() }, async { loadGlossary() },
                async { loadApp("pages.json", ListSerializer(PageInfo.serializer())) { pages = it } }, async { loadUpdates() },
            ).awaitAll()
        }
        lastRefresh = Instant.now()
    }

    suspend fun refreshAll() {
        loadEssentials()
        for (id in rows.keys.toList()) load(id, force = true)
    }

    private suspend fun <T> attempt(key: String, block: suspend () -> Pair<T, BayCountyClient.Freshness>, assign: (T) -> Unit) {
        try {
            val (v, f) = block()
            assign(v); freshness[key] = f; errors.remove(key)
        } catch (e: Exception) {
            errors[key] = e.message ?: "Couldn't load."
        }
    }

    suspend fun loadCatalog() = attempt("catalog", { client.catalog() }) { catalog = it }
    suspend fun loadGovernments() = attempt("government-profiles", { client.governments() }) { governments = it }
    suspend fun loadMeetings() = attempt("meetings", { client.meetings() }) { meetings = it }

    suspend fun load(id: String, force: Boolean = false) {
        if ((!force && rows[id] != null) || id in loading) return
        loading.add(id)
        try {
            // A row with same_as is a post listed twice (a re-posted alert, one event on two calendars); its kept row stands for it.
            attempt(id, { withContext(Dispatchers.Default) { client.rows(id) } }) { r -> rows[id] = r.filter { it.string("same_as").isNullOrEmpty() } }
        } finally { loading.remove(id) }
    }

    /** One restaurant's inspections by license number, newest first (from /api/v1, kept in memory). */
    val restaurantVisits = mutableStateMapOf<String, List<Row>>()

    suspend fun loadRestaurantVisits(license: String, force: Boolean = false) {
        if (!force && restaurantVisits[license] != null) return
        try {
            restaurantVisits[license] = withContext(Dispatchers.Default) { client.restaurantInspections(license) }
            errors.remove("visits:$license")
        } catch (e: Exception) { errors["visits:$license"] = e.message ?: "Couldn't load" }
    }

    suspend fun load(ids: List<String>) = coroutineScope { ids.map { async { load(it) } }.awaitAll(); Unit }

    private val loaded = mutableSetOf<String>()

    private suspend fun <T> loadApp(name: String, serializer: KSerializer<T>, force: Boolean = false, assign: (T) -> Unit) {
        if (!force && errors["app:$name"] == null && name in loaded) return
        attempt("app:$name", { withContext(Dispatchers.Default) { client.appData(name, serializer) } }) { assign(it); loaded.add(name) }
    }

    suspend fun loadGlossary() = loadApp("glossary.json", Glossary.serializer()) { glossary = it }
    suspend fun loadUpdates() = loadApp("updates.json", ListSerializer(SiteUpdate.serializer())) { updates = it }
    suspend fun loadTax() = loadApp("tax.json", TaxModel.serializer()) { taxModel = it }
    suspend fun loadAddressModel() = loadApp("address.json", AddressModel.serializer()) { addressModel = it }
    suspend fun loadAmendment3() = loadApp("amendment3.json", Amendment3Model.serializer()) { amendment3 = it }
    suspend fun loadVendors() = loadApp("vendors.json", VendorDirectory.serializer()) { vendors = it }
    suspend fun loadPeople() = loadApp("people.json", PeopleDirectory.serializer()) { people = it }
    suspend fun loadDonorContracts() = loadApp("donor-contracts.json", DonorContracts.serializer()) { donorContracts = it }
    suspend fun loadMoneyMap() = loadApp("money-map.json", MoneyMap.serializer()) { moneyMap = it }

    suspend fun loadAccountability(force: Boolean = false) {
        val key = "app:accountability.json"
        if (!force && accountability != null && errors[key] == null) return
        attempt(key, { withContext(Dispatchers.Default) { client.accountability() } }) { accountability = it }
    }

    fun appError(name: String): String? = errors["app:$name"]
    fun info(id: String): DatasetInfo? = catalog?.dataset(id)
    fun government(govID: String): Government? = governments.firstOrNull { it.govID == govID }
    fun page(path: String?): PageInfo? = path?.let { p -> pages.firstOrNull { it.path == "/$p" || it.path == p } }
    fun vendor(id: String) = vendors?.vendors?.firstOrNull { it.id == id }
    fun person(id: String) = people?.people?.firstOrNull { it.id == id }
    fun term(id: String) = glossary?.terms?.firstOrNull { it.id == id }

    fun matches(row: Row, query: String): Boolean {
        if (query.isBlank()) return true
        val text = row.searchText
        return query.lowercase().split(" ").filter { it.isNotEmpty() }.all { it in text }
    }

    /** Datasets in Explore, grouped the way the website's menu groups them. */
    val exploreSections: List<Pair<DatasetSpec.Section, List<DatasetInfo>>>
        get() {
            val shown = (catalog?.datasets ?: emptyList()).filter { it.id !in DatasetSpec.ownScreens && it.rows != 0 }  // empty datasets wait until they have rows
            return DatasetSpec.Section.entries.mapNotNull { s ->
                val ds = shown.filter { DatasetSpec.forId(it.id).section == s }
                if (ds.isEmpty()) null else s to ds
            }
        }

    fun explain(termID: String) { presentedTerm = term(termID) }

    fun launch(block: suspend CoroutineScope.() -> Unit) = scope.launch(block = block)
}
