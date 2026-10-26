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
import me.baycounty.app.screens.*
import me.baycounty.app.ui.*

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val store = (application as? BayCountyApp)?.store ?: AppStore(this)
        // For automated screenshots (see .github/workflows/android.yml): `--es screen <name>` and `--ez dark true`.
        val screen = intent?.getStringExtra("screen")
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
    TabItem(Tab.GOVERNMENTS, "Places", "mappin.and.ellipse"),
    TabItem(Tab.MONEY, "Money", "dollarsign.circle"),
    TabItem(Tab.MEETINGS, "Meetings", "calendar"),
)

@Composable
fun AppRoot(store: AppStore, screen: String? = null, nav: Nav = remember { Nav() }) {
    val saver = rememberSaveableStateHolder()
    LaunchedEffect(Unit) {
        store.loadEssentials()
    }
    LaunchedEffect(screen) { if (screen != null) openScreenshotRoute(store, nav, screen) }
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
            Box(Modifier.fillMaxSize().padding(bottom = pad.calculateBottomPadding()).consumeWindowInsets(pad)) {
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
    Tab.GOVERNMENTS -> PlacesScreen()
    Tab.MONEY -> MoneyScreen()
    Tab.MEETINGS -> MeetingsScreen()
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
        Route.Search -> SearchScreen()
        else -> PendingScreen(route)
    }
}

/** A route whose native screen isn't built yet: open the same page on the website. */
@Composable
private fun PendingScreen(route: Route) {
    val o = rememberOpener()
    Screen(route::class.simpleName ?: "BayCounty.me") {
        item {
            Unavailable("Opens on the website", "This page opens on baycounty.me for now.", "Open page", symbol = "safari") { o.openSite("/") }
        }
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
        "craincrement" to Route.CRAIncrement, "pastelections" to Route.Dataset("campaign-history"),
    )
    simple[arg]?.let { nav.replace(it); return }
    when {
        arg == "tab:search" -> nav.replace(Route.Search)
        arg == "tab:governments" -> nav.tab = Tab.GOVERNMENTS
        arg == "tab:money" -> nav.tab = Tab.MONEY
        arg == "tab:meetings" -> nav.tab = Tab.MEETINGS
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
