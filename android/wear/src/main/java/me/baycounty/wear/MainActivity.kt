package me.baycounty.wear

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.wear.compose.material3.AppScaffold
import androidx.wear.compose.material3.CircularProgressIndicator
import androidx.wear.compose.navigation.SwipeDismissableNavHost
import androidx.wear.compose.navigation.composable
import androidx.wear.compose.navigation.rememberSwipeDismissableNavController
import kotlinx.coroutines.launch
import me.baycounty.kit.WatchBrief
import java.time.LocalTime
import java.time.format.DateTimeFormatter
import java.util.Locale

/** BayCounty.me for Wear OS: today's alerts, the saved home's trash day, the beach flag and the next meeting.
 *  Alerts reach the watch as the phone's notifications, which Wear OS shows on the wrist. */
class MainActivity : ComponentActivity() {
    private var brief by mutableStateOf<WatchBrief.Brief?>(null)
    private var updated by mutableStateOf<String?>(null)
    private var reloads by mutableIntStateOf(0)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val demo = intent.getBooleanExtra("demo", false)
        if (!demo) PhoneLink.sync(this) { reloads++ }
        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) { reload(demo) }
        }
        setContent {
            WearTheme {
                LaunchedEffect(reloads) { if (reloads > 0) reload(demo) }
                WearApp(brief, updated, startOnAlerts = intent.getStringExtra("screen") == "alerts")
            }
        }
    }

    private suspend fun reload(demo: Boolean) {
        brief = if (demo) WatchData.demo() else WatchData.load(this)
        updated = LocalTime.now().format(DateTimeFormatter.ofPattern("h:mm a", Locale.US))
        if (!demo) WatchData.refreshComplications(this)
    }
}

@androidx.compose.runtime.Composable
fun WearApp(brief: WatchBrief.Brief?, updated: String?, startOnAlerts: Boolean = false) {
    AppScaffold {
        if (brief == null) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            return@AppScaffold
        }
        val nav = rememberSwipeDismissableNavController()
        var alert by remember { mutableStateOf<WatchBrief.Alert?>(null) }
        SwipeDismissableNavHost(nav, startDestination = if (startOnAlerts) "alerts" else "brief") {
            composable("brief") { BriefScreen(brief, updated) { nav.navigate("alerts") } }
            composable("alerts") { AlertsScreen(brief) { alert = it; nav.navigate("alert") } }
            composable("alert") { alert?.let { AlertDetailScreen(it) } }
        }
    }
}
