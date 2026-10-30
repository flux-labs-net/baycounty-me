package me.baycounty.wear

import app.cash.paparazzi.DeviceConfig
import app.cash.paparazzi.Paparazzi
import app.cash.paparazzi.Snapshot
import app.cash.paparazzi.SnapshotHandler
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.Parameterized
import androidx.compose.ui.platform.ComposeView
import androidx.wear.compose.material3.AppScaffold
import java.io.File

/** Renders the Wear OS screens on the JVM from the made-up demo day (WatchData.demo), on a round and a square watch.
 *  -Dfullres=DIR writes each PNG at full size; CI uploads them. */
@RunWith(Parameterized::class)
class WearScreensTest(@Suppress("unused") private val label: String, private val screen: String, private val shape: String) {
    companion object {
        private val screens = listOf("brief", "brief-clear", "alerts", "alert")
        @JvmStatic
        @Parameterized.Parameters(name = "{0}")
        fun params(): List<Array<Any>> = screens.flatMap { s -> listOf("round", "square", "tall").map { arrayOf<Any>("${s}_$it", s, it) } }
    }

    // "tall" is a square watch stretched to show the whole list in one picture (for review, not a real watch).
    private val device = when (shape) {
        "round" -> DeviceConfig.WEAR_OS_SMALL_ROUND
        "square" -> DeviceConfig.WEAR_OS_SQUARE
        else -> DeviceConfig.WEAR_OS_SQUARE.copy(screenHeight = 1000)
    }

    @get:Rule
    val paparazzi = System.getProperty("fullres")?.let { Paparazzi(deviceConfig = device, maxPercentDifference = 1.0, showSystemUi = true, snapshotHandler = fullRes(File(it))) }
        ?: Paparazzi(deviceConfig = device, maxPercentDifference = 1.0, showSystemUi = true)

    @Test
    fun render() {
        val b = WatchData.demo(clear = screen == "brief-clear")
        // Wear lists draw from their second frame, so the picture is taken a moment in.
        val view = ComposeView(paparazzi.context)
        view.setContent {
            WearTheme {
                AppScaffold {
                    when (screen) {
                        "alerts" -> AlertsScreen(b) {}
                        "alert" -> AlertDetailScreen(b.alerts.first())
                        else -> BriefScreen(b, "8:10 AM") {}
                    }
                }
            }
        }
        paparazzi.gif(view, start = 1000, end = 1000, fps = 1)
    }
}

private fun fullRes(dir: File): SnapshotHandler = object : SnapshotHandler {
    override fun newFrameHandler(snapshot: Snapshot, frameCount: Int, fps: Int): SnapshotHandler.FrameHandler {
        val name = snapshot.testName.methodName.substringAfter("[").substringBefore("]")
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
