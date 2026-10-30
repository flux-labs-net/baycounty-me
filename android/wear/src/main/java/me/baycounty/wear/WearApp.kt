package me.baycounty.wear

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Campaign
import androidx.compose.material.icons.filled.CloudOff
import androidx.compose.material.icons.filled.DeleteOutline
import androidx.compose.material.icons.filled.DirectionsCar
import androidx.compose.material.icons.filled.Event
import androidx.compose.material.icons.filled.Flag
import androidx.compose.material.icons.filled.House
import androidx.compose.material.icons.filled.Thunderstorm
import androidx.compose.material.icons.filled.Traffic
import androidx.compose.material.icons.filled.VerifiedUser
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material.icons.filled.WaterDrop
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.wear.compose.foundation.lazy.TransformingLazyColumn
import androidx.wear.compose.foundation.lazy.rememberTransformingLazyColumnState
import androidx.wear.compose.material3.Card
import androidx.wear.compose.material3.CardDefaults
import androidx.wear.compose.material3.ColorScheme
import androidx.wear.compose.material3.Icon
import androidx.wear.compose.material3.ListHeader
import androidx.wear.compose.material3.MaterialTheme
import androidx.wear.compose.material3.ScreenScaffold
import androidx.wear.compose.material3.Text
import androidx.wear.compose.material3.Typography
import me.baycounty.kit.WatchBrief

/** The phone app's brand colors in their dark shades (a watch is always dark). Same as ios WatchStyle. */
object WearColors {
    val navy = Color(0xFF9DB8EA)
    val blue = Color(0xFF7FA6DA)
    val salmon = Color(0xFFFF8C82)
    val amber = Color(0xFFFFC36B)
    val good = Color(0xFF5FD39A)
    val teal = Color(0xFF5CCCCC)
    val deep = Color(0xFF1E3A76)
    val card = Color(0xFF1B2433)

    fun alert(b: WatchBrief.Brief): Color = if (!b.alertsLoaded) Color.Gray else if (b.alertCount > 0) salmon else good
}

/** `fontFamily` is for the JVM screenshot tests only: the watch's own variable font doesn't draw there. */
@Composable
fun WearTheme(fontFamily: FontFamily? = null, content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = ColorScheme(primary = WearColors.navy, onPrimary = Color(0xFF0B1A38),
        primaryContainer = WearColors.deep, onPrimaryContainer = Color.White, surfaceContainer = WearColors.card),
        typography = fontFamily?.let { Typography(defaultFontFamily = it) } ?: MaterialTheme.typography, content = content)
}

fun alertIcon(b: WatchBrief.Brief): ImageVector =
    if (!b.alertsLoaded) Icons.Filled.CloudOff else if (b.alertCount > 0) Icons.Filled.Warning else Icons.Filled.VerifiedUser

fun kindIcon(kind: String): ImageVector = when (kind) {
    "evacuation" -> Icons.Filled.DirectionsCar
    "weather" -> Icons.Filled.Thunderstorm
    "shelter" -> Icons.Filled.House
    "boil-water", "utility" -> Icons.Filled.WaterDrop
    "road" -> Icons.Filled.Traffic
    else -> Icons.Filled.Campaign
}

/** The watch's one screen: alerts first (tap for the list), then trash day, the beach flag and the next meeting. */
@Composable
fun BriefScreen(b: WatchBrief.Brief, updated: String?, onAlerts: () -> Unit) {
    val state = rememberTransformingLazyColumnState()
    ScreenScaffold(scrollState = state) { padding ->
        TransformingLazyColumn(state = state, contentPadding = padding, modifier = Modifier.fillMaxWidth()) {
            item { ListHeader { Text(b.place, color = WearColors.navy, fontWeight = FontWeight.SemiBold) } }
            item {
                Card(onClick = onAlerts, modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = WearColors.alert(b).copy(alpha = 0.22f))) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(alertIcon(b), null, tint = WearColors.alert(b), modifier = Modifier.size(18.dp))
                        Spacer(Modifier.width(6.dp))
                        Text(b.alertTitle, style = MaterialTheme.typography.titleSmall)
                    }
                    Text(if (b.alertCount > 0) b.alerts.map { it.label }.distinct().joinToString(", ") else b.headline,
                        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 3, overflow = TextOverflow.Ellipsis)
                }
            }
            b.trash?.let { t -> item { InfoRow(Icons.Filled.DeleteOutline, WearColors.teal, t.title, t.detail) } }
                ?: b.nextPickup?.let { n -> item { InfoRow(Icons.Filled.DeleteOutline, WearColors.teal, n, "Trash at your home") } }
            item { InfoRow(Icons.Filled.Flag, WearColors.amber, b.beach.title, b.beach.detail) }
            item { InfoRow(Icons.Filled.Event, WearColors.blue, b.meeting.title, b.meeting.detail) }
            if (!b.hasHome) item { Footnote("Save your home in the phone app to see your trash day here.") }
            updated?.let { item { Footnote("Updated $it") } }
        }
    }
}

@Composable
private fun InfoRow(icon: ImageVector, tint: Color, title: String, detail: String) {
    Row(Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 4.dp), verticalAlignment = Alignment.Top) {
        Icon(icon, null, tint = tint, modifier = Modifier.padding(top = 2.dp).size(18.dp))
        Spacer(Modifier.width(8.dp))
        Column(verticalArrangement = Arrangement.spacedBy(1.dp)) {
            Text(title, style = MaterialTheme.typography.labelMedium, maxLines = 2, overflow = TextOverflow.Ellipsis)
            Text(detail, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 2, overflow = TextOverflow.Ellipsis)
        }
    }
}

@Composable
private fun Footnote(text: String) {
    Text(text, style = MaterialTheme.typography.bodyExtraSmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp))
}

/** Every active alert, most serious first. Alerts posted by the home's own city say so. */
@Composable
fun AlertsScreen(b: WatchBrief.Brief, onAlert: (WatchBrief.Alert) -> Unit) {
    val state = rememberTransformingLazyColumnState()
    ScreenScaffold(scrollState = state) { padding ->
        TransformingLazyColumn(state = state, contentPadding = padding, modifier = Modifier.fillMaxWidth()) {
            item { ListHeader { Text(b.alertTitle) } }
            if (b.alerts.isEmpty()) item { Footnote(b.headline) }
            b.alerts.forEach { a ->
                item {
                    Card(onClick = { onAlert(a) }, modifier = Modifier.fillMaxWidth()) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(kindIcon(a.kind), null, tint = WearColors.salmon, modifier = Modifier.size(14.dp))
                            Spacer(Modifier.width(4.dp))
                            Text(a.label, style = MaterialTheme.typography.labelSmall, color = WearColors.salmon)
                        }
                        Text(a.title, style = MaterialTheme.typography.bodyMedium, maxLines = 3, overflow = TextOverflow.Ellipsis)
                        Text(if (a.nearHome) "Your city · ${a.posted}" else a.posted, style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
    }
}

@Composable
fun AlertDetailScreen(a: WatchBrief.Alert) {
    val state = rememberTransformingLazyColumnState()
    ScreenScaffold(scrollState = state) { padding ->
        TransformingLazyColumn(state = state, contentPadding = padding, modifier = Modifier.fillMaxWidth()) {
            item {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(kindIcon(a.kind), null, tint = WearColors.salmon, modifier = Modifier.size(14.dp))
                    Spacer(Modifier.width(4.dp))
                    Text(a.label, style = MaterialTheme.typography.labelSmall, color = WearColors.salmon)
                }
            }
            item { Text(a.title, style = MaterialTheme.typography.titleSmall, modifier = Modifier.padding(horizontal = 8.dp)) }
            if (a.summary.isNotEmpty()) item { Text(a.summary, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(horizontal = 8.dp)) }
            item { Footnote(listOf(a.source, a.posted).filter { it.isNotEmpty() }.joinToString(" · ")) }
        }
    }
}
