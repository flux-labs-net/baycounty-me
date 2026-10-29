package me.baycounty.app.ui

import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.browser.customtabs.CustomTabColorSchemeParams
import androidx.browser.customtabs.CustomTabsIntent
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.FlowRowScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.wrapContentWidth
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.layout.Layout
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Constraints
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch
import me.baycounty.kit.Outdoors
import me.baycounty.app.AppStore
import me.baycounty.app.Nav
import me.baycounty.app.R
import me.baycounty.app.Route
import me.baycounty.kit.AppLinks
import me.baycounty.kit.BayCountyClient
import me.baycounty.kit.ChartTicks
import me.baycounty.kit.DatasetSpec
import me.baycounty.kit.Format
import me.baycounty.kit.Governments
import me.baycounty.kit.Row as DataRow

val LocalStore = staticCompositionLocalOf<AppStore> { error("no store") }
val LocalNav = staticCompositionLocalOf<Nav> { error("no nav") }

/** Opens a page in the in-app browser (Custom Tabs), like SFSafariViewController on iOS. */
fun openURL(context: Context, url: String?, toolbar: Int? = null) {
    if (url.isNullOrBlank()) return
    val uri = Uri.parse(url)
    if (uri.scheme == "webcal" || uri.scheme == "mailto" || uri.scheme == "tel" || uri.scheme == "geo" || isMapLink(uri)) {
        val i = Intent(Intent.ACTION_VIEW, uri).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        val fallback = when (uri.scheme) {
            "webcal" -> Intent(Intent.ACTION_VIEW, Uri.parse(url.replaceFirst("webcal://", "https://")))
            "geo" -> Outdoors.webDirections(url)?.let { Intent(Intent.ACTION_VIEW, Uri.parse(it)) }
            else -> null
        }
        runCatching { context.startActivity(i) }.onFailure { fallback?.let { f -> runCatching { context.startActivity(f.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) } } }
        return
    }
    val b = CustomTabsIntent.Builder().setShowTitle(true)
    toolbar?.let { b.setDefaultColorSchemeParams(CustomTabColorSchemeParams.Builder().setToolbarColor(it).build()) }
    val page = Uri.parse(AppLinks.tagged(url))  // BayCounty.me pages show as app traffic in the site's analytics
    runCatching { b.build().launchUrl(context, page) }.onFailure {
        runCatching { context.startActivity(Intent(Intent.ACTION_VIEW, page).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }
    }
}

/** Google Maps web links open the Maps app (it claims them), not the in-app browser. */
private fun isMapLink(uri: Uri): Boolean {
    val host = uri.host?.lowercase() ?: return false
    return host == "maps.google.com" || ((host == "google.com" || host == "www.google.com") && (uri.path ?: "").startsWith("/maps"))
}

/** `open(url)` and `openSite(path)` for composables. */
class Opener(private val context: Context, private val toolbar: Int) {
    fun open(url: String?) = openURL(context, url, toolbar)
    fun openSite(path: String) = open(BayCountyClient.SITE + (if (path.startsWith("/")) path else "/$path"))
}

@Composable
fun rememberOpener(): Opener {
    val c = LocalContext.current
    val t = Brand.surface.toArgb()
    return remember(c, t) { Opener(c, t) }
}

/** A white card with a hairline edge, so it stays distinct from the canvas in dark mode. */
@Composable
fun Modifier.card(radius: Dp = 16.dp): Modifier {
    val shape = RoundedCornerShape(radius)
    return this.clip(shape).background(Brand.surface, shape).border(1.dp, Brand.hairline, shape)
}

@Composable
fun Modifier.soft(color: Color, radius: Dp = 12.dp, alpha: Float = 0.12f): Modifier =
    this.background(color.copy(alpha = alpha), RoundedCornerShape(radius))

/** Rows on one rounded card, the grouped-list look. */
@Composable
fun CardList(modifier: Modifier = Modifier, content: @Composable () -> Unit) {
    Column(modifier.fillMaxWidth().card(16.dp)) { content() }
}

@Composable
fun RowDivider(inset: Dp = 14.dp) = HorizontalDivider(Modifier.padding(start = inset), color = Brand.hairline)

@Composable
fun Chevron() = Icon(icon("chevron.right"), null, tint = Brand.tertiary, modifier = Modifier.size(18.dp))

/** A section title with an optional text button on the right ("See all"). */
@Composable
fun SectionHeader(title: String, action: String? = null, onAction: (() -> Unit)? = null) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text(title, style = T.title3, modifier = Modifier.weight(1f).semantics { heading() })
        if (action != null && onAction != null) {
            Text(action, style = T.subheadBold, color = Brand.navy, modifier = Modifier.clip(RoundedCornerShape(8.dp)).clickable(onClick = onAction).padding(6.dp))
        }
    }
}

/** A small caps label above a group ("TRY", "BROWSE"). */
@Composable
fun EyebrowHeader(text: String) {
    Text(text.uppercase(), style = T.footnote.copy(fontWeight = FontWeight.Bold, letterSpacing = 0.8.sp), color = Brand.secondary, modifier = Modifier.semantics { heading() })
}

/** One row on a CardList: optional icon, title, a line of detail, a number on the right, and a chevron. */
@Composable
fun RowLabel(title: String, detail: String? = null, symbol: String? = null, value: String? = null, chevron: Boolean = true) {
    Row(
        Modifier.fillMaxWidth().heightIn(min = if (detail == null) 50.dp else 62.dp).padding(horizontal = 14.dp, vertical = if (detail == null) 0.dp else 10.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        if (symbol != null) Icon(icon(symbol), null, tint = Brand.navy, modifier = Modifier.size(22.dp))
        Column(Modifier.weight(1f)) {
            Text(title, style = if (detail == null) T.body else T.subheadBold, color = Brand.text)
            if (detail != null) Text(detail, style = T.caption, color = Brand.secondary, maxLines = 2, overflow = TextOverflow.Ellipsis)
        }
        if (value != null) Text(value, style = T.subheadBold.copy(fontWeight = FontWeight.Bold), color = Brand.text)
        if (chevron) Chevron()
    }
}

/** A row for a CardList that opens a route. */
@Composable
fun RouteRow(route: Route, title: String, detail: String? = null, symbol: String? = null, value: String? = null) {
    val nav = LocalNav.current
    Box(Modifier.clickable(role = Role.Button) { nav.push(route) }) { RowLabel(title, detail, symbol, value) }
}

/** A row that opens a website page in the in-app browser. */
@Composable
fun WebRow(title: String, url: String?, detail: String? = null, symbol: String? = null) {
    if (url == null) return
    val o = rememberOpener()
    Box(Modifier.clickable(role = Role.Button) { o.open(url) }) { RowLabel(title, detail, symbol ?: "safari") }
}

/** A row on a CardList that is plain text: a title, a line or two of detail, and an optional value. */
@Composable
fun TextRow(title: String, detail: String? = null, value: String? = null, badge: Pair<String, Color>? = null, modifier: Modifier = Modifier) {
    Row(modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 11.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Text(title, style = T.subheadBold, color = Brand.text)
            if (!detail.isNullOrEmpty()) Text(detail, style = T.caption, color = Brand.secondary)
            if (badge != null) Badge(badge.first, badge.second)
        }
        if (value != null) Text(value, style = T.subheadBold.copy(fontWeight = FontWeight.Bold), color = Brand.text)
    }
}

/** A row that opens a record, with the same layout as TextRow and a chevron. */
@Composable
fun RecordLinkRow(route: Route, title: String, detail: String? = null, value: String? = null) {
    val nav = LocalNav.current
    Row(Modifier.fillMaxWidth().clickable { nav.push(route) }, verticalAlignment = Alignment.CenterVertically) {
        TextRow(title, detail, value, modifier = Modifier.weight(1f))
        Box(Modifier.padding(end = 14.dp)) { Chevron() }
    }
}

/** A label and a value on one line of a card. */
@Composable
fun FactRow(label: String, value: String, detail: String? = null) {
    Row(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 11.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        Column(Modifier.weight(1f)) {
            Text(label, style = T.subhead, color = Brand.text)
            if (detail != null) Text(detail, style = T.caption, color = Brand.secondary)
        }
        Text(value, style = T.subheadBold, color = Brand.text, textAlign = TextAlign.End, modifier = Modifier.widthIn(max = 200.dp))
    }
}

@Composable
fun Badge(text: String, color: Color = Brand.secondary) {
    Text(
        text, style = T.caption2.copy(fontWeight = FontWeight.SemiBold), color = color, maxLines = 1, overflow = TextOverflow.Ellipsis,
        modifier = Modifier.background(color.copy(alpha = 0.14f), CircleShape).padding(horizontal = 8.dp, vertical = 3.dp),
    )
}

/** An icon on a soft square of its tone, like the site's section icons. */
@Composable
fun ToneIcon(symbol: String, tone: Tone = Tone.BLUE, size: Dp = 30.dp) {
    val c = tone.color()
    Box(Modifier.size(size).background(c.copy(alpha = 0.13f), RoundedCornerShape(size * 0.28f)), contentAlignment = Alignment.Center) {
        Icon(icon(symbol), null, tint = c, modifier = Modifier.size(size * 0.56f))
    }
}

/** The top of a page: a badge, a small label for where it sits, the title and a line under it. */
@Composable
fun PageHero(kicker: String, title: String, subtitle: String? = null, symbol: String? = null, tone: Tone = Tone.BLUE, badge: (@Composable () -> Unit)? = null) {
    Row(Modifier.fillMaxWidth().card(18.dp).padding(16.dp), horizontalArrangement = Arrangement.spacedBy(14.dp)) {
        if (badge != null) badge() else if (symbol != null) ToneIcon(symbol, tone, 48.dp)
        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
            EyebrowHeader(kicker)
            Text(title, style = T.title2, color = Brand.text)
            if (!subtitle.isNullOrEmpty()) Text(subtitle, style = T.subhead, color = Brand.secondary)
        }
    }
}

/** A section: icon tile and heading, an optional line under it, then its content. */
@Composable
fun PageSection(title: String, symbol: String? = null, tone: Tone = Tone.BLUE, caption: String? = null, content: @Composable () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            if (symbol != null) ToneIcon(symbol, tone)
            Text(title, style = T.title3, color = Brand.text, modifier = Modifier.semantics { heading() })
        }
        if (caption != null) Text(caption, style = T.footnote, color = Brand.secondary)
        content()
    }
}

/** A headline number on a white card (the site's KPI card). */
@Composable
fun KPICard(title: String, value: String, modifier: Modifier = Modifier, caption: String? = null, symbol: String? = null, tone: Tone = Tone.BLUE) {
    Column(modifier.heightIn(min = 92.dp).card(14.dp).padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            if (symbol != null) ToneIcon(symbol, tone, 22.dp)
            Text(title, style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = Brand.secondary, maxLines = 2)
        }
        Text(value, style = T.number, color = Brand.text, maxLines = 1, overflow = TextOverflow.Ellipsis)
        if (caption != null) Text(caption, style = T.caption2, color = Brand.secondary, maxLines = 3)
    }
}

/** Two cards per line, filling the width. */
@Composable
fun <T> Grid2(items: List<T>, spacing: Dp = 10.dp, cell: @Composable (T, Modifier) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(spacing)) {
        for (pair in items.chunked(2)) {
            Row(horizontalArrangement = Arrangement.spacedBy(spacing), modifier = Modifier.fillMaxWidth().height(androidx.compose.foundation.layout.IntrinsicSize.Min)) {
                for (x in pair) cell(x, Modifier.weight(1f).fillMaxHeight())
                if (pair.size == 1) Spacer(Modifier.weight(1f))
            }
        }
    }
}

/** The government's two-letter badge (BC, PC, LH...). */
@Composable
fun GovBadge(govID: String, size: Dp = 40.dp) {
    Box(Modifier.size(size).background(Brand.navy.copy(alpha = 0.1f), RoundedCornerShape(11.dp)), contentAlignment = Alignment.Center) {
        Text(Governments.initials(govID), style = T.footnote.copy(fontWeight = FontWeight.Bold), color = Brand.navy)
    }
}

/**
 * The app's one switcher: pill buttons, one selected (navy), filling the width. Chips that don't fit wrap into
 * evenly split lines (5 become 3 + 2), so every choice is always in view with no sideways scrolling. Every chip is
 * at least 44dp tall. `counts` adds a number after a label ("Split 6").
 */
@Composable
fun <K> ChipRow(chips: List<Pair<K, String>>, selected: K, counts: Map<K, Int> = emptyMap(), onPick: (K) -> Unit) {
    ChipLayout(spacing = 8.dp) {
        for ((id, label) in chips) {
            val on = id == selected
            Row(
                Modifier.heightIn(min = 44.dp).clip(CircleShape)
                    .background(if (on) Brand.navyFill else Brand.surface, CircleShape)
                    .border(1.dp, if (on) Color.Transparent else Brand.hairline, CircleShape)
                    .clickable(role = Role.Tab) { onPick(id) }
                    .padding(horizontal = 16.dp)
                    .semantics { contentDescription = counts[id]?.let { "$label, $it" } ?: label },
                horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(label, style = T.subheadBold, color = if (on) Color.White else Brand.text, maxLines = 1)
                counts[id]?.let {
                    Spacer(Modifier.width(5.dp))
                    Text("$it", style = T.subhead.copy(fontWeight = FontWeight.Medium), color = if (on) Color.White.copy(alpha = 0.75f) else Brand.secondary, maxLines = 1)
                }
            }
        }
    }
}

/** Lays chips out in the fewest lines whose even split fits, stretching each line to the full width. */
@Composable
fun ChipLayout(spacing: Dp = 8.dp, content: @Composable () -> Unit) {
    Layout(content, Modifier.fillMaxWidth()) { measurables, constraints ->
        val gap = spacing.roundToPx()
        val width = constraints.maxWidth
        val n = measurables.size
        if (n == 0) return@Layout layout(width, 0) {}
        val widths = measurables.map { it.maxIntrinsicWidth(Constraints.Infinity) }
        var lines: List<List<Int>> = (0 until n).map { listOf(it) }
        for (count in 1..n) {
            val per = (n + count - 1) / count
            val split = (0 until n step per).map { s -> (s until minOf(s + per, n)).toList() }
            if (split.all { l -> l.sumOf { widths[it] } + gap * (l.size - 1) <= width }) { lines = split; break }
        }
        val placed = lines.map { line ->
            val used = line.sumOf { widths[it] } + gap * (line.size - 1)
            val extra = maxOf(0, width - used) / line.size
            line.map { i ->
                val w = minOf(widths[i] + extra, width)
                measurables[i].measure(Constraints.fixedWidth(w).copy(minHeight = 0, maxHeight = Constraints.Infinity))
            }
        }
        val heights = placed.map { l -> l.maxOf { it.height } }
        val total = heights.sum() + gap * (lines.size - 1)
        layout(width, total) {
            var y = 0
            placed.forEachIndexed { li, line ->
                var x = 0
                for (p in line) { p.placeRelative(x, y); x += p.width + gap }
                y += heights[li] + gap
            }
        }
    }
}

/** Wrapping row of small items (filter chips, glossary terms). */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun Flow(spacing: Dp = 6.dp, content: @Composable FlowRowScope.() -> Unit) {
    FlowRow(horizontalArrangement = Arrangement.spacedBy(spacing), verticalArrangement = Arrangement.spacedBy(spacing), content = content)
}

/** A horizontal bar split into colored parts (the site's stack bar). */
@Composable
fun StackBar(parts: List<Triple<String, Double, Color>>, height: Dp = 14.dp) {
    val total = maxOf(parts.sumOf { it.second }, 1.0)
    Row(Modifier.fillMaxWidth().height(height).clip(RoundedCornerShape(4.dp)), horizontalArrangement = Arrangement.spacedBy(2.dp)) {
        for (p in parts) if (p.second > 0) Box(Modifier.weight((p.second / total).toFloat()).fillMaxHeight().background(p.third))
    }
}

/** One bar split into parts (yes / no / absent), with a legend underneath. */
@Composable
fun ShareBar(parts: List<Triple<String, Double, Color>>, valueText: (Double) -> String = { Format.number(it) }) {
    val total = parts.sumOf { it.second }
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(Modifier.fillMaxWidth().height(14.dp).clip(CircleShape), horizontalArrangement = Arrangement.spacedBy(2.dp)) {
            for (p in parts) if (p.second > 0) Box(Modifier.weight((p.second / maxOf(total, 1.0)).toFloat()).fillMaxHeight().background(p.third))
        }
        Flow(14.dp) {
            for (p in parts) Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(5.dp)) {
                Box(Modifier.size(10.dp).background(p.third, RoundedCornerShape(2.dp)))
                Text("${p.first} ${valueText(p.second)}", style = T.caption, color = Brand.secondary)
                if (total > 0) Text("${Math.round(p.second / total * 100)}%", style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = Brand.text)
            }
        }
    }
}

/** A labelled amount row with a colored dot. */
@Composable
fun LegendRow(color: Color, label: String, value: String, detail: String? = null) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Box(Modifier.size(9.dp).background(color, CircleShape))
        Text(label, style = T.subhead, color = Brand.text, modifier = Modifier.weight(1f))
        if (detail != null) Text(detail, style = T.caption, color = Brand.secondary)
        Text(value, style = T.subhead, color = Brand.text)
    }
}

data class BarItem(val id: String, val label: String, val value: Double)

/** Horizontal bars comparing one number across items, with one item highlighted. */
@Composable
fun CompareBars(
    title: String, items: List<BarItem>, format: (Double) -> String, caption: String? = null, highlight: String? = null,
    labelsAbove: Boolean = false, onTap: ((String) -> Unit)? = null,
) {
    val maxV = items.maxOfOrNull { it.value } ?: 1.0
    Column(Modifier.fillMaxWidth().card(12.dp).padding(14.dp), verticalArrangement = Arrangement.spacedBy(9.dp)) {
        Text(title, style = T.subheadBold, color = Brand.text)
        if (caption != null) Text(caption, style = T.caption, color = Brand.secondary)
        for (item in items) {
            val on = highlight == null || highlight == item.id
            val bold = if (highlight == item.id) FontWeight.Bold else FontWeight.Normal
            Column(
                (if (onTap != null) Modifier.clickable { onTap(item.id) } else Modifier).semantics { contentDescription = "${item.label}: ${format(item.value)}" },
                verticalArrangement = Arrangement.spacedBy(3.dp),
            ) {
                if (labelsAbove) Text(item.label, style = T.caption.copy(fontWeight = bold), color = Brand.text, maxLines = 2)
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (!labelsAbove) Text(item.label, style = T.caption.copy(fontWeight = bold), color = Brand.text, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.width(110.dp))
                    Box(Modifier.weight(1f).height(10.dp)) {
                        val f = if (maxV > 0) (item.value / maxV).toFloat().coerceIn(0.02f, 1f) else 0.02f
                        Box(Modifier.fillMaxWidth(f).fillMaxHeight().background(if (on) Brand.navy else Brand.navy.copy(alpha = 0.25f), CircleShape))
                    }
                    Text(format(item.value), style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = Brand.text, textAlign = TextAlign.End, maxLines = 1, modifier = Modifier.width(58.dp))
                }
            }
        }
    }
}

data class ChartPoint(val label: String, val value: Double, val color: Color? = null)

/**
 * Vertical bars by year or category, following the chart rules: at most six axis labels (the last always shown),
 * nothing before 2016, and amounts on top only for the newest and biggest bar when there are many.
 */
@Composable
fun BarChart(
    points: List<ChartPoint>, height: Dp = 130.dp, format: (Double) -> String = Format::compactMoney, defaultColor: Color = Brand.navy, maxBars: Int = 12,
    selectedLabel: String? = null, onTap: ((String) -> Unit)? = null,
) {
    val shown = ChartTicks.sinceCutoff(points) { ChartTicks.yearOf(it.label) }.takeLast(maxBars)
    if (shown.isEmpty()) return
    val labelIdx = ChartTicks.labelIndices(shown.size).toSet()
    val maxV = shown.maxOf { it.value }
    val annotateAll = shown.size <= 6
    Row(Modifier.fillMaxWidth().height(height + 34.dp).semantics { contentDescription = shown.joinToString(", ") { "${it.label} ${format(it.value)}" } }, verticalAlignment = Alignment.Bottom) {
        shown.forEachIndexed { i, p ->
            val dim = selectedLabel != null && selectedLabel != p.label
            Column(
                Modifier.weight(1f).fillMaxHeight().then(if (onTap != null) Modifier.clickable { onTap(p.label) } else Modifier),
                horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Bottom,
            ) {
                if (annotateAll || i == shown.size - 1 || p.value == maxV) {
                    Text(format(p.value), style = T.caption2, color = Brand.secondary, maxLines = 1, softWrap = false, modifier = Modifier.wrapContentWidth(unbounded = true))
                }
                val f = if (maxV > 0) (p.value / (maxV * 1.0)).toFloat().coerceIn(0.01f, 1f) else 0.01f
                Box(
                    Modifier.padding(top = 3.dp).then(if (shown.size < 6) Modifier.width(34.dp) else Modifier.fillMaxWidth(0.7f))
                        .height(height * f * 0.86f).background((p.color ?: defaultColor).copy(alpha = if (dim) 0.25f else 1f), RoundedCornerShape(topStart = 3.dp, topEnd = 3.dp)),
                )
                Text(
                    if (i in labelIdx) p.label else "", style = T.caption2, color = Brand.secondary, maxLines = 1, softWrap = false,
                    modifier = Modifier.padding(top = 4.dp).wrapContentWidth(unbounded = true),
                )
            }
        }
    }
}

/** A small bar chart of amounts by year on a card (a company's contracts, an official's pay). */
@Composable
fun YearBars(title: String, points: List<Pair<String, Double>>, format: (Double) -> String = Format::compactMoney) {
    Column(Modifier.fillMaxWidth().card(12.dp).padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(title, style = T.subheadBold, color = Brand.text)
        BarChart(points.map { ChartPoint(it.first, it.second) }, format = format)
    }
}

/** Topics as a two-column grid of cards with an icon, a title and a short line. */
data class Topic(val title: String, val symbol: String, val detail: String, val route: Route)

@Composable
fun TopicGrid(topics: List<Topic>) {
    val nav = LocalNav.current
    Grid2(topics) { t, m ->
        Column(m.heightIn(min = 128.dp).card(14.dp).clickable { nav.push(t.route) }.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Box(Modifier.size(36.dp).background(Brand.navy.copy(alpha = 0.1f), RoundedCornerShape(9.dp)), contentAlignment = Alignment.Center) {
                Icon(icon(t.symbol), null, tint = Brand.navy)
            }
            Text(t.title, style = T.subheadBold, color = Brand.text, maxLines = 2)
            Text(t.detail, style = T.caption, color = Brand.secondary, maxLines = 3)
        }
    }
}

/** A big number with a small bar chart of how it splits across governments, biggest first. */
@Composable
fun NumberTile(value: String, label: String, bars: List<Double>, color: Color, route: Route, modifier: Modifier = Modifier) {
    val nav = LocalNav.current
    Column(modifier.card(16.dp).clickable { nav.push(route) }.padding(14.dp).semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(8.dp)) {
        val top = bars.sortedDescending().take(5)
        val peak = maxOf(top.firstOrNull() ?: 1.0, 1.0)
        Row(Modifier.fillMaxWidth().height(28.dp), verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            top.forEachIndexed { i, v ->
                Box(Modifier.weight(1f).height(maxOf(3.0, 28 * v / peak).dp).background(color.copy(alpha = 1f - i * 0.16f), RoundedCornerShape(3.dp)))
            }
        }
        Text(value, style = T.bigNumber, color = Brand.text, maxLines = 1)
        Text(label, style = T.caption, color = Brand.secondary, maxLines = 1)
    }
}

/** "Source" link under a section. */
@Composable
fun SourceLink(url: String?, title: String = "Source") {
    if (url == null) return
    val o = rememberOpener()
    Row(Modifier.clip(RoundedCornerShape(6.dp)).clickable { o.open(url) }.padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(5.dp)) {
        Icon(icon("doc.text.magnifyingglass"), null, tint = Brand.navy, modifier = Modifier.size(16.dp))
        Text(title, style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = Brand.navy)
    }
}

/** A link styled as a line of navy text with an icon. */
@Composable
fun LinkLine(text: String, symbol: String, onClick: () -> Unit) {
    Row(Modifier.clip(RoundedCornerShape(8.dp)).clickable(onClick = onClick).padding(vertical = 6.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Icon(icon(symbol), null, tint = Brand.navy, modifier = Modifier.size(18.dp))
        Text(text, style = T.subhead.copy(fontWeight = FontWeight.Medium), color = Brand.navy)
    }
}

fun shortMoney(v: Double?): String = v?.let { Format.compactMoney(it) } ?: "—"

/** "Showing saved data" note when the device is offline. */
@Composable
fun FreshnessNote(key: String? = null) {
    val store = LocalStore.current
    val f = key?.let { store.freshness[it] }
    if ((key == null && store.isShowingSavedData) || (f != null && f != BayCountyClient.Freshness.LIVE)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            Icon(icon("wifi.slash"), null, tint = Brand.secondary, modifier = Modifier.size(14.dp))
            Text(
                if (f == BayCountyClient.Freshness.BUNDLED) "Offline. Showing data that came with the app." else "Offline. Showing your last saved copy.",
                style = T.caption, color = Brand.secondary,
            )
        }
    }
}

@Composable
fun PoweredByFlux() {
    val o = rememberOpener()
    Row(Modifier.fillMaxWidth().clickable { o.open("https://fluxlabs.net/") }.padding(vertical = 10.dp), horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically) {
        Text("Powered by", style = T.footnote, color = Brand.secondary)
        Spacer(Modifier.width(8.dp))
        androidx.compose.foundation.Image(painterResource(R.drawable.flux_logo), "Flux Labs", modifier = Modifier.height(18.dp))
    }
}

/** Shown while a /data/app file loads, or with a retry button when it couldn't be loaded. */
@Composable
fun AppDataPending(file: String, title: String = "Couldn't load this page", retry: suspend () -> Unit) {
    val store = LocalStore.current
    val scope = rememberCoroutineScope()
    val e = store.appError(file)
    if (e != null) Unavailable(title, e, "Try again") { scope.launch { retry() } } else Loading()
}

@Composable
fun Loading() = Box(Modifier.fillMaxWidth().padding(32.dp), contentAlignment = Alignment.Center) { CircularProgressIndicator(color = Brand.navy) }

@Composable
fun Unavailable(title: String, message: String? = null, action: String? = null, symbol: String = "wifi.slash", onAction: (() -> Unit)? = null) {
    Column(Modifier.fillMaxWidth().padding(vertical = 40.dp, horizontal = 16.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Icon(icon(symbol), null, tint = Brand.secondary, modifier = Modifier.size(36.dp))
        Text(title, style = T.headline, color = Brand.text, textAlign = TextAlign.Center)
        if (message != null) Text(message, style = T.subhead, color = Brand.secondary, textAlign = TextAlign.Center)
        if (action != null && onAction != null) OutlinedButton(onClick = onAction, border = BorderStroke(1.dp, Brand.hairline)) { Text(action, color = Brand.navy) }
    }
}

/** The website page's lead paragraph and "how it works" explainer, with its glossary terms as chips. */
@Composable
fun PageIntro(path: String?) {
    val store = LocalStore.current
    val page = store.page(path) ?: return
    if (page.lede == null && page.explainer == null) return
    var expanded by remember { mutableStateOf(false) }
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        page.lede?.let { Text(it, style = T.subhead, color = Brand.text) }
        page.explainer?.let { ex ->
            Row(Modifier.clip(RoundedCornerShape(6.dp)).clickable { expanded = !expanded }.padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(ex.heading, style = T.footnote.copy(fontWeight = FontWeight.SemiBold), color = Brand.navy, modifier = Modifier.weight(1f))
                Icon(icon(if (expanded) "chevron.up" else "chevron.down"), null, tint = Brand.navy, modifier = Modifier.size(18.dp))
            }
            if (expanded) ex.paragraphs.forEach { Text(it, style = T.footnote, color = Brand.secondary) }
        }
        TermChips(listOfNotNull(page.lede).plus(page.explainer?.paragraphs ?: emptyList()).joinToString(" "))
    }
}

/** Glossary terms that appear in some text, as tappable chips that open the plain-English explanation. */
@Composable
fun TermChips(text: String, limit: Int = 6) {
    val store = LocalStore.current
    val terms = (store.glossary?.termsIn(text) ?: emptyList()).take(limit)
    if (terms.isEmpty()) return
    Flow {
        Icon(icon("character.book.closed"), null, tint = Brand.secondary, modifier = Modifier.size(16.dp).align(Alignment.CenterVertically))
        for (t in terms) {
            Text(
                t.matchWords.lastOrNull() ?: t.term, style = T.caption.copy(fontWeight = FontWeight.Medium), color = Brand.navy,
                modifier = Modifier.clip(CircleShape).background(Brand.navy.copy(alpha = 0.1f)).clickable { store.presentedTerm = t }
                    .padding(horizontal = 10.dp, vertical = 5.dp).semantics { contentDescription = "Explain ${t.term}" },
            )
        }
    }
}

/** One record in a list, laid out from its dataset's spec. */
@Composable
fun RecordRow(spec: DatasetSpec, row: DataRow, onClick: () -> Unit) {
    val title = spec.title(row)
    Column(Modifier.fillMaxWidth().clickable(onClick = onClick).padding(horizontal = 14.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(title, style = T.subhead.copy(fontWeight = FontWeight.Medium), color = Brand.text, maxLines = 2, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
            spec.amount(row)?.let { Text(Format.compactMoney(it), style = T.subhead, color = Brand.text) }
        }
        spec.detail(row)?.takeIf { it != title }?.let { Text(it, style = T.caption, color = Brand.secondary, maxLines = 2, overflow = TextOverflow.Ellipsis) }
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(spec.subtitle(row), style = T.caption, color = Brand.secondary, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
            spec.badge(row)?.let { Badge(it, statusColor(it)) }
            if (row.bool("count") == false && row["status"] != null) Icon(icon("minus.circle"), "Not in totals", tint = Brand.secondary, modifier = Modifier.size(14.dp))
        }
    }
}

/** The app icon's mark: Bay County's outline with a salmon dot for Panama City. Navy in light mode, light blue in dark. */
@Composable
fun BayMark(modifier: Modifier = Modifier) {
    val navy = Brand.navy
    val salmon = Brand.salmon
    Canvas(modifier.aspectRatio(563f / 685f)) {
        val p = Path()
        BAY_OUTLINE.forEachIndexed { i, (x, y) ->
            val px = (x - 230f) / 563f * size.width; val py = (y - 170f) / 685f * size.height
            if (i == 0) p.moveTo(px, py) else p.lineTo(px, py)
        }
        p.close()
        drawPath(p, navy)
        drawCircle(salmon, radius = size.width * 0.08f, center = Offset(size.width * 0.548f, size.height * 0.633f))
    }
}

private val BAY_OUTLINE = listOf(
    698f to 170f, 793f to 170f, 790f to 855f, 775f to 838f, 760f to 828f, 720f to 815f, 700f to 815f, 680f to 805f,
    650f to 780f, 612f to 735f, 605f to 715f, 590f to 712f, 545f to 690f, 505f to 670f, 470f to 645f, 435f to 610f,
    400f to 585f, 350f to 555f, 300f to 525f, 230f to 488f, 233f to 358f, 360f to 303f, 696f to 308f,
)

/** Rounded shape helper. */
fun rounded(r: Dp): Shape = RoundedCornerShape(r)

/** A padded column with the standard spacing for screen content. */
val PagePadding = PaddingValues(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 28.dp)

@Composable
fun RowScope.Fill() = Spacer(Modifier.weight(1f))

/** A pill that opens a menu of choices (the iOS Menu picker), for long lists like fiscal years. */
@Composable
fun <K> MenuPicker(label: String, options: List<Pair<K, String>>, description: String = label, filled: Boolean = false, onPick: (K) -> Unit) {
    var open by remember { mutableStateOf(false) }
    Box {
        Row(
            Modifier.heightIn(min = 44.dp).then(if (filled) Modifier.clip(CircleShape).background(Brand.navyFill) else Modifier.card(22.dp))
                .clickable(role = Role.Button) { open = true }.padding(horizontal = 16.dp)
                .semantics { contentDescription = description },
            verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(label, style = T.subheadBold, color = if (filled) Color.White else Brand.text)
            Icon(icon("chevron.up.chevron.down"), null, tint = if (filled) Color.White else Brand.secondary, modifier = Modifier.size(16.dp))
        }
        androidx.compose.material3.DropdownMenu(open, { open = false }, containerColor = Brand.surface) {
            for ((k, t) in options) androidx.compose.material3.DropdownMenuItem(text = { Text(t, style = T.body, color = Brand.text) }, onClick = { open = false; onPick(k) })
        }
    }
}

/** "All 12 findings" / "Show fewer" at the bottom of a CardList. */
@Composable
fun ShowMoreRow(expanded: Boolean, moreLabel: String, onToggle: () -> Unit) {
    Box(Modifier.fillMaxWidth().heightIn(min = 44.dp).clickable(role = Role.Button, onClick = onToggle), contentAlignment = Alignment.Center) {
        Text(if (expanded) "Show fewer" else moreLabel, style = T.subheadBold, color = Brand.navy)
    }
}
