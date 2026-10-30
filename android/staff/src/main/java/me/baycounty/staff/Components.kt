package me.baycounty.staff

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import me.baycounty.kit.StaffAlert
import me.baycounty.kit.StaffFlag

@Composable
fun Card(modifier: Modifier = Modifier, radius: Dp = 16.dp, content: @Composable ColumnScope.() -> Unit) {
    Surface(modifier.fillMaxWidth(), shape = RoundedCornerShape(radius), color = Brand.surface, border = BorderStroke(1.dp, Brand.hairline)) {
        Column(content = content)
    }
}

@Composable
fun Eyebrow(text: String, modifier: Modifier = Modifier) {
    Text(text.uppercase(), style = T.eyebrow, color = Brand.secondary, modifier = modifier.padding(bottom = 8.dp))
}

@Composable
fun PrimaryButton(text: String, modifier: Modifier = Modifier, color: Color = Brand.navyFill, enabled: Boolean = true, icon: ImageVector? = null, onClick: () -> Unit) {
    Button(onClick, modifier.fillMaxWidth().heightIn(min = 48.dp), enabled = enabled, shape = RoundedCornerShape(12.dp),
        colors = ButtonDefaults.buttonColors(containerColor = color, contentColor = Color.White)) {
        if (icon != null) { Icon(icon, null, Modifier.size(18.dp)); Spacer(Modifier.width(8.dp)) }
        Text(text, style = T.bodyBold)
    }
}

@Composable
fun QuietButton(text: String, color: Color = Brand.navy, enabled: Boolean = true, onClick: () -> Unit) {
    OutlinedButton(onClick, Modifier.fillMaxWidth().heightIn(min = 48.dp), enabled = enabled, shape = RoundedCornerShape(12.dp), border = BorderStroke(1.dp, Brand.hairline)) {
        Text(text, style = T.bodyBold, color = color)
    }
}

@Composable
fun StatTile(value: Int, label: String, icon: ImageVector, modifier: Modifier = Modifier, alert: Boolean = false, tint: Color = Brand.navy) {
    val c = if (alert) Brand.salmon else tint
    Card(modifier, radius = 14.dp) {
        Column(Modifier.padding(14.dp)) {
            Box(Modifier.size(30.dp).clip(RoundedCornerShape(8.dp)).background(c.copy(alpha = 0.13f)), contentAlignment = Alignment.Center) {
                Icon(icon, null, tint = c, modifier = Modifier.size(17.dp))
            }
            Spacer(Modifier.height(8.dp))
            Text("%,d".format(value), style = T.number, color = if (alert) Brand.salmon else Brand.text)
            Text(label, style = T.footnote, color = Brand.secondary, minLines = 2, maxLines = 2, overflow = TextOverflow.Ellipsis)
        }
    }
}

/** Two tiles per row, no sideways scroll. */
@Composable
fun TileGrid(tiles: List<@Composable (Modifier) -> Unit>) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        tiles.chunked(2).forEach { row ->
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                row.forEach { it(Modifier.weight(1f)) }
                if (row.size == 1) Spacer(Modifier.weight(1f))
            }
        }
    }
}

@Composable
fun Chip(text: String, color: Color = Brand.navy) {
    Text(text, style = T.caption.copy(fontWeight = androidx.compose.ui.text.font.FontWeight.SemiBold), color = color,
        modifier = Modifier.clip(RoundedCornerShape(50)).background(color.copy(alpha = 0.13f)).padding(horizontal = 8.dp, vertical = 3.dp))
}

@Composable fun alertColor(a: StaffAlert): Color = if (a.isWaiting) Brand.amber else if (a.isLive) Brand.salmon else Brand.secondary
@Composable fun flagColor(f: StaffFlag): Color = when (f.status) { "open" -> Brand.amber; "fixed" -> Brand.good; else -> Brand.secondary }

/** A tappable row inside a card, at least 48dp tall, with a chevron. */
@Composable
fun RowLink(onClick: (() -> Unit)?, content: @Composable ColumnScope.() -> Unit, trailing: @Composable () -> Unit = {}) {
    Row(Modifier.fillMaxWidth().then(if (onClick != null) Modifier.clickable(onClick = onClick) else Modifier).heightIn(min = 56.dp)
        .padding(horizontal = 14.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f), content = content)
        trailing()
        if (onClick != null) Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, null, tint = Brand.tertiary)
    }
}

@Composable
fun Divided(items: Int, row: @Composable (Int) -> Unit) {
    Card {
        for (i in 0 until items) {
            if (i > 0) HorizontalDivider(Modifier.padding(start = 14.dp), color = Brand.hairline)
            row(i)
        }
    }
}

@Composable
fun ErrorLine(text: String?) {
    if (text.isNullOrEmpty()) return
    Row(Modifier.padding(top = 6.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(Icons.Filled.ErrorOutline, null, tint = Brand.salmon, modifier = Modifier.size(16.dp))
        Spacer(Modifier.width(6.dp))
        Text(text, style = T.footnote, color = Brand.salmon)
    }
}

@Composable
fun Detail(label: String, value: String) {
    Row(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 11.dp)) {
        Text(label, style = T.subhead, color = Brand.secondary, modifier = Modifier.width(120.dp))
        Text(value, style = T.subhead, color = Brand.text, modifier = Modifier.weight(1f))
    }
}

@Composable
fun FluxFooter() {
    Row(Modifier.fillMaxWidth().padding(vertical = 12.dp), horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically) {
        Text("Made by", style = T.caption, color = Brand.secondary)
        Spacer(Modifier.width(6.dp))
        Image(painterResource(R.drawable.flux_logo), "Flux Labs", Modifier.height(14.dp))
    }
}

