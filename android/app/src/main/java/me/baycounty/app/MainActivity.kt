package me.baycounty.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import me.baycounty.app.screens.*
import me.baycounty.app.ui.*

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Store screenshots (debug builds only): `--es apiBase http://10.0.2.2:8765` reads made-up demo data instead of the live site.
        if (BuildConfig.DEBUG) intent?.getStringExtra("apiBase")?.let { AppStore.apiBase = it }
        val store = (application as? BayCountyApp)?.store ?: AppStore(this)
        // For automated screenshots (see .github/workflows/android.yml): `--es screen <name>` and `--ez dark true`.
        // A tapped notification carries its link: emergency notices open the Emergencies screen, others the page.
        val noticeURL = intent?.getStringExtra("url")
        val screen = intent?.getStringExtra("screen") ?: noticeURL?.takeIf { it.contains("/emergency") }?.let { "emergency" }
        if (noticeURL != null && screen == null) openURL(this, noticeURL)
        val forceDark = if (intent?.hasExtra("dark") == true) intent.getBooleanExtra("dark", false) else null
        setContent {
            val dark = forceDark ?: isSystemInDarkTheme()
            LaunchedEffect(dark) {
                val bars = if (dark) SystemBarStyle.dark(Color.Transparent.toArgb()) else SystemBarStyle.light(Color.Transparent.toArgb(), Color.Transparent.toArgb())
                enableEdgeToEdge(statusBarStyle = bars, navigationBarStyle = bars)
            }
            BayCountyTheme(dark) { AppRoot(store, screen) }
        }
    }
}

private data class TabItem(val tab: Tab, val label: String, val symbol: String)

private val tabs = listOf(
    TabItem(Tab.HOME, "Today", "house"),
    TabItem(Tab.LIVING, "Living here", "mappin.and.ellipse"),
    TabItem(Tab.MONEY, "Money", "dollarsign.circle"),
    TabItem(Tab.DECIDES, "Who decides", "building.columns"),
    TabItem(Tab.SEARCH, "Search", "magnifyingglass"),
)

@Composable
fun AppRoot(store: AppStore, screen: String? = null, nav: Nav = remember { Nav() }) {
    val saver = rememberSaveableStateHolder()
    LaunchedEffect(Unit) {
        store.loadEssentials()
    }
    LaunchedEffect(screen) { if (screen != null) openScreenshotRoute(store, nav, screen) }
    // Signed in: the account's saved home is the phone's address too (Today card, tax bill, trash day), so it follows
    // the resident to any phone. Signing out leaves the phone's address as it was.
    val context = LocalContext.current
    LaunchedEffect(Unit) { Account.load(context); if (Account.signedIn && Account.me == null) Account.refresh(context) }
    val accountHome = Account.me?.home
    LaunchedEffect(accountHome) {
        val m = accountHome?.addressMatch ?: return@LaunchedEffect
        if (store.home?.id != m.id || store.home?.point != m.point) store.saveHome(m)
    }
    CompositionLocalProvider(LocalStore provides store, LocalNav provides nav) {
        BackHandler(enabled = nav.stack().isNotEmpty() || nav.tab != Tab.HOME) {
            if (!nav.pop()) nav.tab = Tab.HOME
        }
        Scaffold(
            containerColor = Brand.canvas,
            bottomBar = {
                NavigationBar(containerColor = Brand.surface) {
                    for (t in tabs) {
                        NavigationBarItem(
                            selected = nav.tab == t.tab, onClick = { nav.select(t.tab) },
                            icon = { Icon(icon(t.symbol), null) }, label = { Text(t.label, style = T.caption2) },
                            colors = NavigationBarItemDefaults.colors(
                                selectedIconColor = Brand.navy, selectedTextColor = Brand.navy,
                                indicatorColor = Brand.navy.copy(alpha = 0.12f),
                                unselectedIconColor = Brand.secondary, unselectedTextColor = Brand.secondary,
                            ),
                        )
                    }
                }
            },
        ) { pad ->
            // pad holds the status bar on top and the tab bar below. Padding by both keeps every screen's title bar
            // below the clock and camera (the top bars then see those insets as already used).
            Box(Modifier.fillMaxSize().padding(pad).consumeWindowInsets(pad)) {
                val stack = nav.stack()
                val top = stack.lastOrNull()
                val key = "${nav.tab}/${stack.size}/${top?.hashCode() ?: 0}"
                saver.SaveableStateProvider(key) {
                    if (top == null) TabRoot(nav.tab) else RouteScreen(top)
                }
            }
        }
        store.presentedTerm?.let { TermSheet(it) { store.presentedTerm = null } }
    }
}

@Composable
private fun TabRoot(tab: Tab) = when (tab) {
    Tab.HOME -> HomeScreen()
    Tab.LIVING -> LivingHereScreen()
    Tab.MONEY -> MoneyScreen()
    Tab.DECIDES -> PlacesScreen()
    Tab.SEARCH -> SearchScreen()
}

/** Every route resolves to the same screen from any tab. */
@Composable
fun RouteScreen(route: Route) {
    when (route) {
        is Route.MeetingDetail -> MeetingDetailScreen(route.id)
        is Route.Gov -> GovernmentScreen(route.govID)
        Route.People -> PeopleScreen()
        is Route.Person -> PersonScreen(route.id)
        Route.Vendors -> VendorsScreen()
        is Route.Vendor -> VendorScreen(route.id)
        Route.DonorContracts -> DonorContractsScreen()
        Route.MoneyMap -> MoneyMapScreen()
        is Route.Dataset -> DatasetScreen(route.id, route.filters)
        is Route.Record -> RecordScreen(route.datasetID, route.rowID)
        Route.Explore -> ExploreScreen()
        Route.Search -> SearchScreen()
        Route.CRA -> CRAScreen()
        Route.CRAIncrement -> CRAIncrementScreen()
        Route.Chambers -> ChambersScreen()
        Route.Events -> EventsScreen()
        Route.Beaches -> BeachesScreen()
        Route.Parks -> ParksScreen()
        Route.Schools -> SchoolsScreen()
        Route.Emergency -> EmergencyScreen()
        Route.HurricanePrep -> HurricanePrepScreen()
        is Route.Utilities -> UtilitiesScreen(route.match)
        Route.Volunteer -> VolunteerScreen()
        Route.Military -> MilitaryScreen()
        Route.Restaurants -> RestaurantsScreen()
        is Route.Restaurant -> RestaurantDetailScreen(route.license)
        Route.MyHome -> MyHomeScreen()
        Route.AccountSettings -> AccountSettingsScreen()
        Route.Meetings -> MeetingsScreen()
        is Route.BudgetCompare -> BudgetCompareScreen(route.govID)
        is Route.TaxCalculator -> TaxCalculatorScreen(route)
        is Route.GovBudget -> GovBudgetScreen(route.id)
        is Route.Amendment3 -> Amendment3Screen(route)
        Route.Glossary -> GlossaryScreen()
        Route.Updates -> UpdatesScreen()
        Route.About -> AboutScreen()
        Route.MyAddress -> MyAddressScreen()
        is Route.Address -> AddressReportScreen(route.match)
        Route.Accountability -> AccountabilityScreen()
        is Route.AccountabilityProject -> AccountabilityProjectScreen(route.id)
    }
}

/** The same `-screen` names as the iOS app, so both apps' screenshots line up. */
suspend fun openScreenshotRoute(store: AppStore, nav: Nav, arg: String) {
    val simple: Map<String, Route> = mapOf(
        "tax" to Route.TaxCalculator("Lynn Haven", 250_000.0, true), "amendment3" to Route.Amendment3("Panama City", 300_000.0, true),
        "glossary" to Route.Glossary, "vendors" to Route.Vendors, "people" to Route.People, "moneymap" to Route.MoneyMap,
        "donors" to Route.DonorContracts, "updates" to Route.Updates, "about" to Route.About, "cra" to Route.CRA,
        "myaddress" to Route.MyAddress, "contracts" to Route.Dataset("contracts"), "vendor" to Route.Vendor("roberts-and-roberts"),
        "person" to Route.Person("clair-pease"), "explore" to Route.Explore, "votes" to Route.Dataset("votes"),
        "salaries" to Route.Dataset("salary-positions"), "accountability" to Route.Accountability,
        "accproject" to Route.AccountabilityProject("pcb-fbr-seg3"), "budget" to Route.BudgetCompare("lh"),
        "craincrement" to Route.CRAIncrement, "chambers" to Route.Chambers, "events" to Route.Events, "beaches" to Route.Beaches, "parks" to Route.Parks, "schools" to Route.Schools, "emergency" to Route.Emergency, "hurricaneprep" to Route.HurricanePrep, "utilities" to Route.Utilities(UTILITIES_SAMPLE), "volunteer" to Route.Volunteer, "military" to Route.Military, "myhome" to Route.MyHome, "pastelections" to Route.Dataset("campaign-history"),
        "roads" to Route.Dataset("road-contracts"), "development" to Route.Dataset("development-projects"),
        "restaurants" to Route.Restaurants, "restaurant" to Route.Restaurant("1305433"), "newbusinesses" to Route.Dataset("new-businesses"),
    )
    simple[arg]?.let { nav.replace(it); return }
    if (arg == "myhome:settings") { nav.replace(Route.MyHome); nav.push(Route.AccountSettings); return }
    when {
        arg == "tab:search" -> nav.tab = Tab.SEARCH
        arg == "tab:living" -> nav.tab = Tab.LIVING
        arg == "tab:governments" || arg == "tab:decides" -> nav.tab = Tab.DECIDES
        arg == "tab:money" -> nav.tab = Tab.MONEY
        arg == "tab:meetings" -> nav.replace(Route.Meetings)
        arg.startsWith("gov:") -> nav.replace(Route.Gov(arg.removePrefix("gov:")))
        arg == "record:contract" || arg == "record:vote" -> {
            val ds = if (arg == "record:contract") "contracts" else "votes"
            store.load(ds)
            val rows = store.rows[ds] ?: emptyList()
            val pick = if (ds == "contracts") rows.firstOrNull { it.string("vendor") == "Ten-8 Fire & Safety, LLC" }
                       else rows.firstOrNull { it.string("headline") == "Approved \$62.45 million FY2027 general fund budget" }
            (pick ?: rows.firstOrNull())?.let { nav.replace(Route.Record(ds, it.id)) }
        }
        arg == "record:board" || arg == "record:nonprofit" -> {
            val ds = if (arg == "record:board") "nonprofit-board-members" else "nonprofits"
            store.load(ds)
            val rows = store.rows[ds] ?: emptyList()
            val pick = rows.firstOrNull { it.string("nonprofit_id") == "np-sb-n01000008288" && (ds == "nonprofits" || it.string("person") == "Kathy Bass") }
            (pick ?: rows.firstOrNull())?.let { nav.replace(Route.Record(ds, it.id)) }
        }
        arg.startsWith("address:") -> {
            val m = runCatching { store.gis.search(arg.removePrefix("address:")).matches.firstOrNull() }.getOrNull()
            m?.let { nav.replace(Route.Address(it)) }
        }
    }
}
