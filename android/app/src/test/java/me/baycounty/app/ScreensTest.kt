package me.baycounty.app

import app.cash.paparazzi.DeviceConfig
import app.cash.paparazzi.Paparazzi
import app.cash.paparazzi.Snapshot
import app.cash.paparazzi.SnapshotHandler
import com.android.resources.NightMode
import kotlinx.coroutines.runBlocking
import me.baycounty.kit.BayCountyClient
import java.io.File
import androidx.compose.runtime.CompositionLocalProvider
import me.baycounty.app.ui.BayCountyTheme
import me.baycounty.app.ui.LocalScrollStart
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.Parameterized

/**
 * Renders screens on the JVM (no emulator) from the bundled seed data, in light and dark,
 * so layout problems show up in a pull request. `./gradlew :app:recordPaparazziDebug` writes the PNGs.
 */
@RunWith(Parameterized::class)
class ScreensTest(@Suppress("unused") private val label: String, private val screen: String, private val dark: Boolean) {
    companion object {
        val screens = (System.getProperty("screens") ?: "home,tab:governments,tab:money,tab:meetings,tab:search").split(",").filter { it.isNotBlank() }

        @JvmStatic
        @Parameterized.Parameters(name = "{0}")
        fun params(): List<Array<Any>> = screens.flatMap { s ->
            val l = s.replace(Regex("[^A-Za-z0-9]+"), "_")
            listOf(arrayOf<Any>("${l}_light", s, false), arrayOf<Any>("${l}_dark", s, true))
        }
    }

    private val device = DeviceConfig.PIXEL_6.copy(
        nightMode = if (dark) NightMode.NIGHT else NightMode.NOTNIGHT, softButtons = false,
        // -Dtall=6000 renders the whole page for review instead of one phone screen.
        screenHeight = System.getProperty("tall")?.toIntOrNull() ?: DeviceConfig.PIXEL_6.screenHeight,
    )

    @get:Rule
    val paparazzi = System.getProperty("fullres")?.let { dir ->
        Paparazzi(deviceConfig = device, maxPercentDifference = 1.0, showSystemUi = false, snapshotHandler = fullResHandler(File(dir)))
    } ?: Paparazzi(deviceConfig = device, maxPercentDifference = 1.0, showSystemUi = false)

    @Test
    fun render() {
        val store = AppStore(paparazzi.context, offlineClient())
        val nav = Nav()
        runBlocking {
            store.loadEssentials()
            store.loadTax(); store.loadAmendment3(); store.loadPeople(); store.loadVendors()
            if (screen != "home") openScreenshotRoute(store, nav, screen)
            preload(store, nav.stack().lastOrNull())
        }
        // -Dpages=3 also captures the page scrolled down one and two screens.
        val pages = System.getProperty("pages")?.toIntOrNull() ?: 1
        for (p in 0 until pages) {
            paparazzi.snapshot(if (pages > 1) "p$p" else null) {
                CompositionLocalProvider(LocalScrollStart provides p * 1900, androidx.activity.compose.LocalActivityResultRegistryOwner provides noResults) { BayCountyTheme(dark) { AppRoot(store, nav = nav) } }
            }
        }
    }
}

private val repo = File(System.getProperty("repoRoot") ?: "../..")

/** Reads the files the site publishes in this repo, never the network, so the pictures don't change between runs. */
fun offlineClient() = BayCountyClient(baseURL = "https://offline.invalid", seed = { name ->
    // Same choice as android/scripts/sync_seed.sh: the catalog's index.json, every other name from /data/app first.
    val dirs = if (name == "index.json") listOf("downloads") else listOf("data/app", "data", "downloads")
    dirs.map { File(repo, "site/public/$it/$name") }.firstOrNull { it.exists() }?.readBytes()
})

/** Permission prompts can't open in a snapshot; this owner just ignores them. */
private val noResults = object : androidx.activity.result.ActivityResultRegistryOwner {
    override val activityResultRegistry = object : androidx.activity.result.ActivityResultRegistry() {
        override fun <I, O> onLaunch(requestCode: Int, contract: androidx.activity.result.contract.ActivityResultContract<I, O>, input: I, options: androidx.core.app.ActivityOptionsCompat?) {}
    }
}

/** Loads what a screen's LaunchedEffect would load, since a snapshot is taken before effects finish. */
suspend fun preload(store: AppStore, route: Route?) {
    store.loadGlossary()
    when (route) {
        is Route.Gov -> store.load(listOf("officeholder-terms", "budget-years", "debt", "bonds", "audit-findings", "savings-opportunities", "cra-agencies"))
        is Route.Person -> { store.loadDonorContracts(); store.load(me.baycounty.kit.RecordLinks.personDatasets) }
        is Route.Vendor -> { store.loadDonorContracts(); store.load(me.baycounty.kit.RecordLinks.vendorDatasets + "votes") }
        Route.DonorContracts -> store.loadDonorContracts()
        Route.MoneyMap -> store.loadMoneyMap()
        Route.CRA -> store.load("cra-payments")
        is Route.BudgetCompare -> store.load("budget-years")
        is Route.TaxCalculator, is Route.GovBudget -> store.loadTax()
        is Route.Amendment3 -> store.loadAmendment3()
        Route.Accountability, is Route.AccountabilityProject -> store.loadAccountability()
        Route.CRAIncrement -> store.load(listOf("cra-agencies", "cra-tax-increment", "cra-increment-checks"))
        is Route.Dataset -> store.load(route.id)
        is Route.Record -> {
            store.load(route.datasetID); store.loadVendors(); store.loadPeople()
            val row = store.rows[route.datasetID]?.firstOrNull { it.id == route.rowID }
            if (row != null) {
                val ids = me.baycounty.kit.RecordProfile.groups(route.datasetID, row).map { it.datasetID }.toMutableSet()
                if (me.baycounty.kit.RecordProfile.refs(route.datasetID, row).any { it.kind == "nonprofit" }) ids += "nonprofits"
                if (me.baycounty.kit.RecordLinks.voteIDs(row).isNotEmpty()) ids += "votes"
                store.load(ids.toList())
            }
        }
        else -> {}
    }
}

/** Writes each snapshot at full size (Paparazzi's own report shrinks tall pages), for reviewing whole pages. */
fun fullResHandler(dir: File): SnapshotHandler = object : SnapshotHandler {
    override fun newFrameHandler(snapshot: Snapshot, frameCount: Int, fps: Int): SnapshotHandler.FrameHandler {
        val name = snapshot.testName.methodName.substringAfter("[").substringBefore("]") + (snapshot.name?.let { "_$it" } ?: "")
        // java.awt isn't on the Android compile classpath, so the image is handled by reflection.
        return java.lang.reflect.Proxy.newProxyInstance(javaClass.classLoader, arrayOf(SnapshotHandler.FrameHandler::class.java)) { _, m, args ->
            if (m.name == "handle") {
                dir.mkdirs()
                val io = Class.forName("javax.imageio.ImageIO")
                io.getMethod("write", Class.forName("java.awt.image.RenderedImage"), String::class.java, File::class.java).invoke(null, args!![0], "png", File(dir, "$name.png"))
            }
            null
        } as SnapshotHandler.FrameHandler
    }
    override fun close() {}
}
