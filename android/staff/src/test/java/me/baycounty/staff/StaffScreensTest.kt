package me.baycounty.staff

import app.cash.paparazzi.DeviceConfig
import app.cash.paparazzi.Paparazzi
import app.cash.paparazzi.Snapshot
import app.cash.paparazzi.SnapshotHandler
import com.android.resources.NightMode
import me.baycounty.kit.StaffDemo
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.Parameterized
import java.io.File

/** Renders the staff app's screens on the JVM from its made-up demo data (staff-demo.json), in light and dark.
 *  -Dfullres=DIR writes each PNG at full size; CI uploads them. */
@RunWith(Parameterized::class)
class StaffScreensTest(@Suppress("unused") private val label: String, private val screen: String, private val asStaff: Boolean, private val dark: Boolean) {
    companion object {
        private val shots = listOf(
            "owner-overview" to ("overview" to false), "owner-flags" to ("flags" to false), "owner-flag" to ("flag" to false),
            "city-home" to ("home" to true), "city-alerts" to ("alerts" to true), "city-send" to ("send" to true),
            "city-notices" to ("notices" to true), "city-notice" to ("notice" to true), "more" to ("more" to false),
            "city-records" to ("records" to true), "city-send-file" to ("send-file" to true), "city-send-file-preview" to ("send-file-preview" to true),
            "signin" to ("signin" to false), "signin-code" to ("signin-code" to false), "locked" to ("locked" to false),
        )
        @JvmStatic
        @Parameterized.Parameters(name = "{0}")
        fun params(): List<Array<Any>> = shots.flatMap { (name, s) ->
            listOf(arrayOf<Any>("${name}_light", s.first, s.second, false), arrayOf<Any>("${name}_dark", s.first, s.second, true))
        }
    }

    private val device = DeviceConfig.PIXEL_6.copy(nightMode = if (dark) NightMode.NIGHT else NightMode.NOTNIGHT, softButtons = false)

    @get:Rule
    val paparazzi = System.getProperty("fullres")?.let { Paparazzi(deviceConfig = device, maxPercentDifference = 1.0, showSystemUi = false, snapshotHandler = fullRes(File(it))) }
        ?: Paparazzi(deviceConfig = device, maxPercentDifference = 1.0, showSystemUi = false)

    @Test
    fun render() {
        val demo = StaffDemo.decode(File(System.getProperty("user.dir"), "src/main/assets/staff-demo.json").readText())
        val model = StaffModel(NoTokens, demo, asStaff = asStaff)
        paparazzi.snapshot { StaffTheme(dark) { StaffApp(model, screen = screen, locked = false, onUnlock = {}) } }
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
